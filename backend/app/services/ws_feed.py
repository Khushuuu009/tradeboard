import asyncio
import json
import logging
import os
import time
import random
from datetime import datetime, date, timedelta
from typing import Set
from fastapi import WebSocket, WebSocketDisconnect
from dhanhq import marketfeed, dhanhq
from dotenv import load_dotenv
from app.services.dhan_live import get_intraday_vwap, calculate_max_pain
from app.services.candle_engine import MultiTimeframeCandleEngine

load_dotenv()
logger = logging.getLogger(__name__)

# ── DHAN UNDERLYING SECURITY IDs ──
UNDERLYING_IDS = {
    "NIFTY": 13,
    "SENSEX": 14,
    "BANKNIFTY": 17,
    "FINNIFTY": 27,
}
DEFAULT_INDEX = "NIFTY"

# ── MOCK MODE ──────────────────────────────────────────────────────────────────
MOCK_MODE = True  # Set to False for real Dhan data

# ── PATHS ─────────────────────────────────────────────────────────────────────
DATA_DIR = "data"
os.makedirs(DATA_DIR, exist_ok=True)

def today_file():
    return os.path.join(DATA_DIR, f"straddle_{date.today().strftime('%Y-%m-%d')}.json")

# ── HARDCODED FALLBACK EXPIRY ─────────────────────────────────────────────────
FALLBACK_EXPIRY = "2026-05-20"

# ── IN-MEMORY STORE ───────────────────────────────────────────────────────────
connected_clients: Set[WebSocket] = set()
today_chart: list = []
historical_candles_for_today: dict = {}

live = {
    "spot": None, "ce": None, "pe": None, "straddle": None,
    "atm": None, "ce_id": None, "pe_id": None, "expiry": None,
    "open": None, "high": None, "low": None, "time": None,
    "vwap": None, "vwap_bias": None,
    "straddle_vwap": None,  # Straddle VWAP
}

# ── VWAP ACCUMULATORS ────────────────────────────────────────────────────────
current_atm_tracker = None
straddle_vwap_accum = {"price_volume": 0.0, "volume": 0}
vwap_initialized = False
current_symbol = DEFAULT_INDEX  # <-- NEW: Track current symbol

# ── CANDLE ENGINE ─────────────────────────────────────────────────────────────
candle_engine = MultiTimeframeCandleEngine()

_dhan_client = None

def get_dhan_client():
    global _dhan_client
    if _dhan_client is None:
        _dhan_client = dhanhq(os.getenv('DHAN_CLIENT_ID'), os.getenv('DHAN_ACCESS_TOKEN'))
    return _dhan_client

def get_atm_strike(spot, gap=50):
    return round(spot / gap) * gap

# ── VWAP RESET ────────────────────────────────────────────────────────────────
def reset_straddle_vwap():
    global straddle_vwap_accum, vwap_initialized, current_atm_tracker
    straddle_vwap_accum = {"price_volume": 0.0, "volume": 0}
    vwap_initialized = True
    logger.info(f"🔄 Straddle VWAP reset. New ATM: {live.get('atm')}")

# ── BUILD HISTORICAL CANDLES FROM SNAPSHOTS ──────────────────────────────────
def build_candles_from_snapshots(snapshots):
    if not snapshots:
        return {}
    candles = []
    today_date = date.today()
    for snap in snapshots:
        time_str = snap.get("time")
        if not time_str:
            continue
        try:
            dt = datetime.strptime(time_str, "%I:%M %p")
            dt = datetime.combine(today_date, dt.time())
            ts = int(dt.timestamp())
        except Exception:
            continue
        straddle = snap.get("straddle")
        if straddle is None:
            continue
        candles.append({
            "time": ts,
            "open": straddle,
            "high": straddle,
            "low": straddle,
            "close": straddle,
            "volume": 1
        })
    candles.sort(key=lambda x: x["time"])
    candles = candles[-500:]
    return {"1M": candles} if candles else {}

# ── DISK PERSISTENCE ──────────────────────────────────────────────────────────

def load_today_from_disk():
    global today_chart, historical_candles_for_today
    path = today_file()
    if os.path.exists(path):
        try:
            with open(path, "r") as f:
                today_chart = json.load(f)
            logger.info(f"Loaded {len(today_chart)} chart points from {path}")
            historical_candles_for_today = build_candles_from_snapshots(today_chart)
        except Exception as e:
            logger.error(f"Load error: {e}")
            today_chart = []
            historical_candles_for_today = {}
    else:
        today_chart = []
        historical_candles_for_today = {}
        logger.info("No chart data for today — starting fresh")

def save_today_to_disk():
    try:
        with open(today_file(), "w") as f:
            json.dump(today_chart, f)
    except Exception as e:
        logger.error(f"Save error: {e}")

def add_chart_point(straddle, spot, ce, pe, atm, time_str):
    global today_chart
    point = {"time": time_str, "straddle": straddle, "spot": spot, "ce": ce, "pe": pe, "atm": atm}
    if today_chart and today_chart[-1]["time"] == time_str:
        today_chart[-1] = point
    else:
        today_chart.append(point)
    if len(today_chart) > 500:
        today_chart = today_chart[-500:]
    save_today_to_disk()

# ── EXPIRY + OPTION IDs (DYNAMIC) ───────────────────────────────────────────

def get_nearest_expiry(symbol="NIFTY"):
    """Get nearest expiry for a given symbol"""
    try:
        dhan = get_dhan_client()
        sec_id = UNDERLYING_IDS.get(symbol, 13)
        expiries = dhan.expiry_list(under_security_id=sec_id, under_exchange_segment="IDX_I")
        data = expiries.get("data", {})
        if isinstance(data, dict):
            lst = data.get("data", [])
            if lst and isinstance(lst, list):
                return lst[0]
        logger.warning(f"Expiry API for {symbol} returned unexpected format — using fallback")
        return FALLBACK_EXPIRY
    except Exception as e:
        logger.warning(f"Expiry API for {symbol} failed ({e}) — using fallback: {FALLBACK_EXPIRY}")
        return FALLBACK_EXPIRY

def get_option_ids(expiry, spot_hint=None, symbol="NIFTY"):
    """Get ATM CE/PE security IDs for a given symbol"""
    try:
        dhan = get_dhan_client()
        sec_id = UNDERLYING_IDS.get(symbol, 13)
        chain = dhan.option_chain(
            under_security_id=sec_id, under_exchange_segment="IDX_I", expiry=expiry
        )
        data = chain["data"]["data"]
        spot = data["last_price"]
        if spot == 0 and spot_hint:
            spot = spot_hint
        oc = data["oc"]
        atm = get_atm_strike(spot)
        atm_key = f"{float(atm):.6f}"
        if atm_key not in oc:
            return None, None, atm
        ce_id = oc[atm_key]["ce"]["security_id"]
        pe_id = oc[atm_key]["pe"]["security_id"]
        return ce_id, pe_id, atm
    except Exception as e:
        logger.error(f"get_option_ids error for {symbol}: {e}")
        return None, None, None

# ── BROADCAST ─────────────────────────────────────────────────────────────────

async def broadcast(data: dict):
    dead = set()
    for ws in connected_clients:
        try:
            await ws.send_text(json.dumps(data))
        except Exception:
            dead.add(ws)
    for ws in dead:
        connected_clients.discard(ws)

# ── MAIN FEED LOOP (DYNAMIC) ─────────────────────────────────────────────────

async def dhan_feed_loop():
    global current_symbol, current_atm_tracker, straddle_vwap_accum, vwap_initialized
    load_today_from_disk()

    # ── MOCK MODE ──────────────────────────────────────────────────────────────
    if MOCK_MODE:
        logger.info("🎭 MOCK MODE ENABLED – Generating fake straddle data for testing")
        
        reset_straddle_vwap()
        
        # Initial mock values
        spot_base = 24500
        straddle_price = 200.0
        ce_price = 110.0
        pe_price = 90.0
        atm = 24500
        expiry = (date.today() + timedelta(days=5)).strftime("%Y-%m-%d")
        
        # Generate initial candles (120 ticks = 2 minutes of history)
        logger.info("📊 Generating mock historical candles...")
        for i in range(120):
            straddle_price += random.uniform(-1.5, 1.5)
            straddle_price = max(150, min(300, straddle_price))
            if random.random() < 0.02:
                straddle_price += 30
            if straddle_price > 220:
                straddle_price -= random.uniform(1, 5)
            
            spot = spot_base + random.uniform(-50, 50)
            atm = round(spot / 50) * 50
            ce_price = max(0, straddle_price - 50 + random.uniform(-5, 5))
            pe_price = max(0, straddle_price - ce_price + random.uniform(-3, 3))
            
            volume = 1
            straddle_vwap_accum["price_volume"] += straddle_price * volume
            straddle_vwap_accum["volume"] += volume
            
            ts_ms = int((datetime.now() - timedelta(minutes=2) + timedelta(seconds=i)).timestamp() * 1000)
            candle_engine.process_tick(straddle_price, ts_ms, volume=1)
        
        # Main mock tick loop
        last_broadcast = 0
        last_minute = ""
        mock_count = 0
        
        while True:
            try:
                straddle_price += random.uniform(-1.2, 1.2)
                straddle_price = max(150, min(350, straddle_price))
                
                if random.random() < 0.015:
                    straddle_price += random.uniform(25, 40)
                    logger.info(f"💥 MOCK SPIKE! Straddle jumped to {straddle_price:.2f}")
                
                if straddle_price > 230:
                    straddle_price -= random.uniform(0.5, 3)
                
                spot = spot_base + random.uniform(-60, 60)
                new_atm = round(spot / 50) * 50
                
                if current_atm_tracker != new_atm:
                    current_atm_tracker = new_atm
                    reset_straddle_vwap()
                    await broadcast({"type": "vwap_reset", "new_atm": new_atm})
                    logger.info(f"🔄 ATM changed to {new_atm}, VWAP reset")
                
                atm = new_atm
                ce_price = max(0, straddle_price * 0.55 + random.uniform(-5, 5))
                pe_price = max(0, straddle_price - ce_price + random.uniform(-3, 3))
                
                volume = 1
                straddle_vwap_accum["price_volume"] += straddle_price * volume
                straddle_vwap_accum["volume"] += volume
                straddle_vwap = straddle_vwap_accum["price_volume"] / straddle_vwap_accum["volume"] if straddle_vwap_accum["volume"] > 0 else straddle_price
                
                live.update({
                    "spot": round(spot, 2),
                    "ce": round(ce_price, 2),
                    "pe": round(pe_price, 2),
                    "straddle": round(straddle_price, 2),
                    "straddle_vwap": round(straddle_vwap, 2),
                    "atm": atm,
                    "expiry": expiry,
                    "open": round(spot - 20, 2),
                    "high": round(spot + 10, 2),
                    "low": round(spot - 15, 2),
                    "time": datetime.now().strftime("%H:%M:%S"),
                    "vwap": round(spot - random.uniform(-5, 5), 2),
                    "vwap_bias": "BULLISH" if random.random() > 0.5 else "BEARISH",
                })
                
                ts_ms = int(time.time() * 1000)
                finalized = candle_engine.process_tick(live["straddle"], ts_ms, volume=1)
                if finalized:
                    await broadcast({
                        "type": "candles",
                        "data": finalized,
                        "timestamp": ts_ms
                    })
                
                current_time = asyncio.get_event_loop().time()
                if current_time - last_broadcast >= 0.1:
                    last_broadcast = current_time
                    await broadcast({
                        "type": "tick",
                        **live
                    })
                
                if live["straddle"] and live["spot"]:
                    minute = datetime.now().strftime("%I:%M %p")
                    if minute != last_minute:
                        last_minute = minute
                        add_chart_point(
                            straddle=live["straddle"],
                            spot=live["spot"],
                            ce=live["ce"],
                            pe=live["pe"],
                            atm=live["atm"],
                            time_str=minute,
                        )
                
                mock_count += 1
                if mock_count % 100 == 0:
                    logger.info(f"🎭 Mock ticks sent: {mock_count}")
                
                await asyncio.sleep(0.5)
                
            except Exception as e:
                logger.error(f"Mock loop error: {e}")
                await asyncio.sleep(1)
        
        return
    
    # ── REAL DHAN MODE ──────────────────────────────────────────────────────────
    else:
        logger.info(f"🔴 REAL DHAN MODE – Connecting to live feed for {current_symbol}")
        
        client_id    = os.getenv('DHAN_CLIENT_ID')
        access_token = os.getenv('DHAN_ACCESS_TOKEN')
        
        ce_id  = None
        pe_id  = None
        atm    = None
        expiry = None
        last_broadcast = 0
        last_minute    = ""
        last_vwap_calc = 0
        retry_delay    = 5
        symbol = current_symbol
        
        while True:
            try:
                expiry = get_nearest_expiry(symbol)
                live["expiry"] = expiry
                
                spot_hint = live.get("spot")
                ce_id, pe_id, atm = get_option_ids(expiry, spot_hint, symbol)
                
                if not ce_id or not pe_id:
                    logger.info(f"Option IDs for {symbol} not available — retrying in {retry_delay}s")
                    await asyncio.sleep(retry_delay)
                    retry_delay = min(retry_delay * 1.5, 60)
                    continue
                
                retry_delay = 5
                live.update({"atm": atm, "ce_id": ce_id, "pe_id": pe_id, "expiry": expiry})
                logger.info(f"✅ Subscribing: {symbol} + CE({ce_id}) + PE({pe_id}) ATM={atm} expiry={expiry}")
                
                instruments = [
                    (marketfeed.IDX,     "13",       marketfeed.Quote),  # NIFTY spot is always 13 on Dhan
                    (marketfeed.NSE_FNO, str(ce_id), marketfeed.Quote),
                    (marketfeed.NSE_FNO, str(pe_id), marketfeed.Quote),
                ]
                
                feed = marketfeed.DhanFeed(
                    client_id=client_id, access_token=access_token,
                    instruments=instruments, version='v2'
                )
                
                await feed.connect()
                logger.info(f"🟢 Dhan WebSocket connected for {symbol}!")
                
                start_time = asyncio.get_event_loop().time()
                
                while True:
                    tick = await feed.get_instrument_data()
                    if not tick:
                        continue
                    
                    sec_id = str(tick.get("security_id", ""))
                    ltp    = tick.get("LTP")
                    if ltp is None:
                        continue
                    
                    ltp = float(ltp)
                    if ltp == 0:
                        continue
                    
                    # ---- Update live dict ----
                    if sec_id == "13":
                        live["spot"] = ltp
                        live["open"] = float(tick.get("open", 0) or 0)
                        live["high"] = float(tick.get("high", 0) or 0)
                        live["low"]  = float(tick.get("low",  0) or 0)
                        live["time"] = tick.get("LTT", datetime.now().strftime("%H:%M:%S"))
                    elif sec_id == str(ce_id):
                        live["ce"] = ltp
                    elif sec_id == str(pe_id):
                        live["pe"] = ltp
                    
                    if live["ce"] and live["pe"]:
                        live["straddle"] = round(live["ce"] + live["pe"], 2)
                    
                    # ---- VWAP calculation (with ATM reset) ----
                    if live["straddle"] is not None:
                        if current_atm_tracker != live["atm"]:
                            current_atm_tracker = live["atm"]
                            reset_straddle_vwap()
                            await broadcast({"type": "vwap_reset", "new_atm": live["atm"]})
                        
                        volume = 1
                        straddle_vwap_accum["price_volume"] += live["straddle"] * volume
                        straddle_vwap_accum["volume"] += volume
                        straddle_vwap = straddle_vwap_accum["price_volume"] / straddle_vwap_accum["volume"] if straddle_vwap_accum["volume"] > 0 else live["straddle"]
                        live["straddle_vwap"] = round(straddle_vwap, 2)
                    
                    # ---- Process candle engine ----
                    if live["straddle"] is not None:
                        ltt = tick.get("LTT")
                        if ltt:
                            try:
                                dt = datetime.strptime(ltt, "%H:%M:%S")
                                ts_ms = int(datetime.combine(date.today(), dt.time()).timestamp() * 1000)
                            except Exception:
                                ts_ms = int(time.time() * 1000)
                        else:
                            ts_ms = int(time.time() * 1000)
                        
                        finalized = candle_engine.process_tick(live["straddle"], ts_ms, volume=1)
                        if finalized:
                            await broadcast({
                                "type": "candles",
                                "data": finalized,
                                "timestamp": ts_ms
                            })
                    
                    # ---- VWAP calculation (every 30s) ----
                    current_time = asyncio.get_event_loop().time()
                    if current_time - last_vwap_calc >= 30:
                        last_vwap_calc = current_time
                        try:
                            vwap_result = get_intraday_vwap(symbol)
                            if vwap_result:
                                live["vwap"] = vwap_result.get('vwap')
                                live["vwap_bias"] = vwap_result.get('bias')
                        except Exception as vwap_err:
                            logger.error(f"VWAP calculation error: {vwap_err}")
                    
                    # ---- Broadcast tick ----
                    if current_time - last_broadcast >= 0.1:
                        last_broadcast = current_time
                        await broadcast({
                            "type": "tick",
                            **live
                        })
                    
                    # ---- Save chart point every minute ----
                    if live["straddle"] and live["spot"]:
                        minute = datetime.now().strftime("%I:%M %p")
                        if minute != last_minute:
                            last_minute = minute
                            add_chart_point(
                                straddle=live["straddle"], spot=live["spot"],
                                ce=live["ce"], pe=live["pe"],
                                atm=live["atm"], time_str=minute,
                            )
                    
                    # ---- Refresh ATM every 5 min ----
                    if asyncio.get_event_loop().time() - start_time > 300:
                        logger.info(f"🔄 Refreshing ATM strike for {symbol}...")
                        await feed.disconnect()
                        ce_id = pe_id = atm = None
                        break
                
            except Exception as e:
                logger.error(f"Feed error: {e} — reconnecting in 5s")
                await asyncio.sleep(5)

# ── WEBSOCKET ENDPOINT (WITH SYMBOL SWITCHING) ──────────────────────────────

async def websocket_endpoint(websocket: WebSocket):
    global current_symbol
    await websocket.accept()
    connected_clients.add(websocket)
    logger.info(f"Frontend connected. Clients: {len(connected_clients)}")

    # Send latest live tick immediately
    if live["spot"]:
        await websocket.send_text(json.dumps({"type": "tick", **live}))

    # Send full chart history (1-min snapshots)
    if today_chart:
        await websocket.send_text(json.dumps({
            "type": "history", "data": today_chart, "count": len(today_chart)
        }))

    # ---- Send historical candles if no live engine data yet ----
    has_candles = any(len(builder.finalized_candles) > 0 for builder in candle_engine.builders.values())
    if not has_candles and historical_candles_for_today:
        await websocket.send_text(json.dumps({
            "type": "historical_candles",
            "data": historical_candles_for_today
        }))

    # ---- Send current unfinalized candles ----
    current_candles = candle_engine.get_all_current_candles()
    if current_candles:
        await websocket.send_text(json.dumps({
            "type": "initial_candles",
            "data": current_candles
        }))

    # Send historical candles from engine if any
    historical = {}
    for tf_name in candle_engine.timeframes.keys():
        hist = candle_engine.get_historical_candles(tf_name, limit=500)
        if hist:
            historical[tf_name] = hist
    if historical:
        await websocket.send_text(json.dumps({
            "type": "historical_candles",
            "data": historical
        }))

    try:
        while True:
            message = await websocket.receive_text()
            try:
                data = json.loads(message)
                if data.get("type") == "set_symbol":
                    new_symbol = data.get("symbol", DEFAULT_INDEX)
                    if new_symbol in UNDERLYING_IDS:
                        current_symbol = new_symbol
                        logger.info(f"🔄 Switching feed to {current_symbol}")
                        # Reset ATM tracker to force VWAP reset on next tick
                        reset_straddle_vwap()
                        # Send acknowledgement
                        await websocket.send_text(json.dumps({
                            "type": "symbol_changed",
                            "symbol": current_symbol
                        }))
                    else:
                        logger.warning(f"Invalid symbol requested: {new_symbol}")
                        await websocket.send_text(json.dumps({
                            "type": "error",
                            "message": f"Invalid symbol: {new_symbol}"
                        }))
            except json.JSONDecodeError:
                logger.warning("Received non-JSON WebSocket message")
                
    except WebSocketDisconnect:
        connected_clients.discard(websocket)
        logger.info(f"Frontend disconnected. Clients: {len(connected_clients)}")