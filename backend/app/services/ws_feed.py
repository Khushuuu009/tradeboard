import asyncio
import json
import logging
import os
from datetime import datetime, date
from typing import Set
from fastapi import WebSocket, WebSocketDisconnect
from dhanhq import marketfeed, dhanhq
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

# ── PATHS ─────────────────────────────────────────────────────────────────────
DATA_DIR = "data"
os.makedirs(DATA_DIR, exist_ok=True)

def today_file():
    return os.path.join(DATA_DIR, f"straddle_{date.today().strftime('%Y-%m-%d')}.json")

# ── HARDCODED FALLBACK EXPIRY ─────────────────────────────────────────────────
# Update this every week on Tuesday
FALLBACK_EXPIRY = "2026-03-24"

# ── IN-MEMORY STORE ───────────────────────────────────────────────────────────
connected_clients: Set[WebSocket] = set()
today_chart: list = []

live = {
    "spot": None, "ce": None, "pe": None, "straddle": None,
    "atm": None, "ce_id": None, "pe_id": None, "expiry": None,
    "open": None, "high": None, "low": None, "time": None,
}

_dhan_client = None

def get_dhan_client():
    global _dhan_client
    if _dhan_client is None:
        _dhan_client = dhanhq(os.getenv('DHAN_CLIENT_ID'), os.getenv('DHAN_ACCESS_TOKEN'))
    return _dhan_client

def get_atm_strike(spot, gap=50):
    return round(spot / gap) * gap

# ── DISK PERSISTENCE ──────────────────────────────────────────────────────────

def load_today_from_disk():
    global today_chart
    path = today_file()
    if os.path.exists(path):
        try:
            with open(path, "r") as f:
                today_chart = json.load(f)
            logger.info(f"Loaded {len(today_chart)} chart points from {path}")
        except Exception as e:
            logger.error(f"Load error: {e}")
            today_chart = []
    else:
        today_chart = []
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

# ── EXPIRY + OPTION IDs ───────────────────────────────────────────────────────

def get_nearest_expiry():
    """Get nearest expiry — falls back to hardcoded if API fails"""
    try:
        dhan     = get_dhan_client()
        expiries = dhan.expiry_list(under_security_id=13, under_exchange_segment="IDX_I")
        data     = expiries.get("data", {})
        if isinstance(data, dict):
            lst = data.get("data", [])
            if lst and isinstance(lst, list):
                return lst[0]
        logger.warning(f"Expiry API returned unexpected format: {expiries} — using fallback")
        return FALLBACK_EXPIRY
    except Exception as e:
        logger.warning(f"Expiry API failed ({e}) — using fallback: {FALLBACK_EXPIRY}")
        return FALLBACK_EXPIRY

def get_option_ids(expiry, spot_hint=None):
    """Get ATM CE/PE security IDs. Uses spot_hint if available."""
    try:
        dhan    = get_dhan_client()
        chain   = dhan.option_chain(
            under_security_id=13, under_exchange_segment="IDX_I", expiry=expiry
        )
        data    = chain["data"]["data"]
        spot    = data["last_price"]
        if spot == 0 and spot_hint:
            spot = spot_hint
        oc      = data["oc"]
        atm     = get_atm_strike(spot)
        atm_key = f"{float(atm):.6f}"
        if atm_key not in oc:
            return None, None, atm
        ce_id = oc[atm_key]["ce"]["security_id"]
        pe_id = oc[atm_key]["pe"]["security_id"]
        return ce_id, pe_id, atm
    except Exception as e:
        logger.error(f"get_option_ids error: {e}")
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

# ── MAIN FEED LOOP ────────────────────────────────────────────────────────────

async def dhan_feed_loop():
    load_today_from_disk()

    client_id    = os.getenv('DHAN_CLIENT_ID')
    access_token = os.getenv('DHAN_ACCESS_TOKEN')

    ce_id  = None
    pe_id  = None
    atm    = None
    expiry = None
    last_broadcast = 0
    last_minute    = ""
    retry_delay    = 5

    while True:
        try:
            # ── Get expiry ──
            expiry = get_nearest_expiry()
            live["expiry"] = expiry

            # ── Get option IDs — retry until market opens ──
            spot_hint = live.get("spot")
            ce_id, pe_id, atm = get_option_ids(expiry, spot_hint)

            if not ce_id or not pe_id:
                logger.info(f"Option IDs not available yet (market may be pre-open) — retrying in {retry_delay}s")
                await asyncio.sleep(retry_delay)
                retry_delay = min(retry_delay * 1.5, 60)  # back off up to 60s
                continue

            retry_delay = 5  # reset on success
            live.update({"atm": atm, "ce_id": ce_id, "pe_id": pe_id, "expiry": expiry})
            logger.info(f"✅ Subscribing: NIFTY + CE({ce_id}) + PE({pe_id}) ATM={atm} expiry={expiry}")

            instruments = [
                (marketfeed.IDX,     "13",       marketfeed.Quote),
                (marketfeed.NSE_FNO, str(ce_id), marketfeed.Quote),
                (marketfeed.NSE_FNO, str(pe_id), marketfeed.Quote),
            ]

            feed = marketfeed.DhanFeed(
                client_id=client_id, access_token=access_token,
                instruments=instruments, version='v2'
            )

            await feed.connect()
            logger.info("🟢 Dhan WebSocket connected!")

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

                # Broadcast at max 10/sec
                now_t = asyncio.get_event_loop().time()
                if now_t - last_broadcast >= 0.1:
                    last_broadcast = now_t
                    await broadcast({"type": "tick", **live})

                # Save chart point every minute
                if live["straddle"] and live["spot"]:
                    minute = datetime.now().strftime("%I:%M %p")
                    if minute != last_minute:
                        last_minute = minute
                        add_chart_point(
                            straddle=live["straddle"], spot=live["spot"],
                            ce=live["ce"], pe=live["pe"],
                            atm=live["atm"], time_str=minute,
                        )
                        logger.info(f"📊 Chart point saved: {minute} straddle={live['straddle']} total={len(today_chart)}")

                # Refresh ATM every 5 min
                if asyncio.get_event_loop().time() - start_time > 300:
                    logger.info("🔄 Refreshing ATM strike...")
                    await feed.disconnect()
                    ce_id = pe_id = atm = None
                    break

        except Exception as e:
            logger.error(f"Feed error: {e} — reconnecting in 5s")
            await asyncio.sleep(5)

# ── WEBSOCKET ENDPOINT ────────────────────────────────────────────────────────

async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    connected_clients.add(websocket)
    logger.info(f"Frontend connected. Clients: {len(connected_clients)}")

    # Send latest live tick immediately
    if live["spot"]:
        await websocket.send_text(json.dumps({"type": "tick", **live}))

    # Send full chart history
    if today_chart:
        await websocket.send_text(json.dumps({
            "type": "history", "data": today_chart, "count": len(today_chart)
        }))

    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        connected_clients.discard(websocket)
        logger.info(f"Frontend disconnected. Clients: {len(connected_clients)}")