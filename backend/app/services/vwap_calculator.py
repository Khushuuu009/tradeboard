from datetime import datetime, timedelta, time
from app.services.angel_auth import get_smartapi, INDEX_TOKENS
import logging

logger = logging.getLogger(__name__)

# ── IN-MEMORY STORE ───────────────────────────────────────────────────────────

CLOSING_VWAP_HISTORY = {
    "NIFTY":     [],
    "BANKNIFTY": [],
    "FINNIFTY":  [],
    "SENSEX":    [],
}

LAST_KNOWN_VWAP = {
    "NIFTY":     None,
    "BANKNIFTY": None,
    "FINNIFTY":  None,
    "SENSEX":    None,
}

# ── MARKET HELPERS ────────────────────────────────────────────────────────────

def is_market_open():
    now = datetime.now()
    if now.weekday() >= 5:
        return False
    market_open  = now.replace(hour=9,  minute=15, second=0, microsecond=0)
    market_close = now.replace(hour=15, minute=30, second=0, microsecond=0)
    return market_open <= now <= market_close


def is_closing_auction():
    now = datetime.now()
    if now.weekday() >= 5:
        return False
    start = now.replace(hour=15, minute=0,  second=0, microsecond=0)
    end   = now.replace(hour=15, minute=15, second=0, microsecond=0)
    return start <= now <= end


# ── VWAP CALCULATION ──────────────────────────────────────────────────────────

def calculate_vwap(candles):
    """VWAP = Σ(Typical Price × Volume) / Σ(Volume)"""
    tp_vol    = 0
    total_vol = 0
    for c in candles:
        typical_price  = (c["high"] + c["low"] + c["close"]) / 3
        tp_vol        += typical_price * c["volume"]
        total_vol     += c["volume"]
    if total_vol == 0:
        return 0
    return round(tp_vol / total_vol, 2)


def get_trend_signal(history):
    """Bull/bear signal from closing VWAP history — unchanged from original"""
    if len(history) < 2:
        return {
            "signal":        "Neutral ➡️",
            "description":   "Not enough history yet",
            "straddle_bias": "No bias"
        }

    values  = [d["closing_vwap"] for d in history[-5:]]
    rising  = sum(1 for i in range(1, len(values)) if values[i] > values[i-1])
    falling = sum(1 for i in range(1, len(values)) if values[i] < values[i-1])

    if rising >= 3:
        return {"signal": "🚀 STRONG BULLISH", "description": f"Institutions accumulating for {rising} days",    "straddle_bias": "Favor calls"}
    elif rising == 2:
        return {"signal": "📈 BULLISH",         "description": "Closing VWAP rising for 2 days",                 "straddle_bias": "Slight call bias"}
    elif falling >= 3:
        return {"signal": "💀 STRONG BEARISH",  "description": f"Institutions distributing for {falling} days",  "straddle_bias": "Favor puts"}
    elif falling == 2:
        return {"signal": "📉 BEARISH",         "description": "Closing VWAP falling for 2 days",                "straddle_bias": "Slight put bias"}
    else:
        return {"signal": "Neutral ➡️",         "description": "No clear trend in closing VWAP",                 "straddle_bias": "No bias"}


# ── ANGEL ONE CANDLE FETCH ────────────────────────────────────────────────────

def get_intraday_candles(symbol="NIFTY"):
    """
    Fetch today's 5-min candles from Angel One
    Replaces the old NSE session scraper
    """
    try:
        obj      = get_smartapi()
        token    = INDEX_TOKENS.get(symbol, INDEX_TOKENS["NIFTY"])
        exchange = "BSE" if symbol == "SENSEX" else "NSE"

        today     = datetime.now().strftime("%Y-%m-%d")
        from_date = f"{today} 09:15"
        to_date   = f"{today} 15:30"

        params = {
            "exchange":    exchange,
            "symboltoken": token,
            "interval":    "FIVE_MINUTE",
            "fromdate":    from_date,
            "todate":      to_date,
        }

        response = obj.getCandleData(params)

        if not response or response.get("status") is False:
            logger.error(f"Candle fetch failed: {response}")
            return []

        raw = response.get("data", [])

        # Angel One format: [timestamp, open, high, low, close, volume]
        candles = []
        for c in raw:
            candles.append({
                "timestamp": c[0],
                "open":      float(c[1]),
                "high":      float(c[2]),
                "low":       float(c[3]),
                "close":     float(c[4]),
                "volume":    float(c[5]),
            })

        return candles

    except Exception as e:
        logger.error(f"get_intraday_candles error: {str(e)}")
        return []


# ── MAIN FUNCTION ─────────────────────────────────────────────────────────────

def get_vwap(symbol="NIFTY"):
    """
    Live VWAP using Angel One intraday candles
    Drop-in replacement for old NSE scraper version
    Same response format — frontend needs zero changes
    """
    try:
        now = datetime.now()

        # ── MARKET CLOSED ──
        if not is_market_open():
            last    = LAST_KNOWN_VWAP[symbol]
            history = CLOSING_VWAP_HISTORY[symbol]
            signal  = get_trend_signal(history)
            return {
                "symbol":               symbol,
                "market_status":        "closed",
                "intraday_vwap":        last["intraday_vwap"] if last else "N/A",
                "closing_vwap":         last["closing_vwap"]  if last else "N/A",
                "closing_vwap_history": history,
                "trend_signal":         signal,
                "message":              "Market closed. Showing last saved VWAP.",
                "status":               "market_closed"
            }

        # ── MARKET OPEN: fetch candles from Angel One ──
        all_candles = get_intraday_candles(symbol)

        if not all_candles:
            return {
                "symbol":        symbol,
                "market_status": "open",
                "message":       "Waiting for candle data from Angel One...",
                "status":        "waiting"
            }

        # Separate closing auction candles (3:00 PM - 3:15 PM)
        closing_candles = []
        for c in all_candles:
            try:
                # Angel One returns ISO timestamp string
                candle_time = datetime.fromisoformat(str(c["timestamp"])).time()
                if time(15, 0) <= candle_time <= time(15, 15):
                    closing_candles.append(c)
            except Exception:
                pass

        # Calculate VWAPs
        intraday_vwap = calculate_vwap(all_candles)
        closing_vwap  = calculate_vwap(closing_candles) if closing_candles else None

        # Spot = last candle close
        spot_price = all_candles[-1]["close"]

        # Bias signal
        if spot_price > intraday_vwap:
            intraday_bias = "🟢 Above VWAP - Bullish"
        elif spot_price < intraday_vwap:
            intraday_bias = "🔴 Below VWAP - Bearish"
        else:
            intraday_bias = "🟡 At VWAP - Neutral"

        # Save closing VWAP history (once per day)
        if closing_vwap:
            today   = now.strftime("%d %b %Y")
            history = CLOSING_VWAP_HISTORY[symbol]
            if not history or history[-1]["date"] != today:
                history.append({"date": today, "closing_vwap": closing_vwap})
                if len(history) > 5:
                    history.pop(0)

        # Always update last known VWAP
        LAST_KNOWN_VWAP[symbol] = {
            "intraday_vwap": intraday_vwap,
            "closing_vwap":  closing_vwap,
            "saved_at":      now.strftime("%d %b %Y %I:%M %p")
        }

        signal = get_trend_signal(CLOSING_VWAP_HISTORY[symbol])

        # ── CLOSING AUCTION (3:00 - 3:15 PM) ──
        if is_closing_auction():
            return {
                "symbol":               symbol,
                "market_status":        "closing_auction",
                "spot_price":           spot_price,
                "intraday_vwap":        intraday_vwap,
                "closing_vwap":         closing_vwap,
                "closing_vwap_history": CLOSING_VWAP_HISTORY[symbol],
                "trend_signal":         signal,
                "message":              f"Closing auction in progress. Likely closing at {closing_vwap}",
                "last_updated":         now.strftime("%d %b %Y %I:%M %p"),
                "status":               "success"
            }

        # ── NORMAL HOURS ──
        return {
            "symbol":               symbol,
            "market_status":        "open",
            "spot_price":           spot_price,
            "intraday_vwap":        intraday_vwap,
            "intraday_bias":        intraday_bias,
            "closing_vwap":         closing_vwap,
            "closing_vwap_history": CLOSING_VWAP_HISTORY[symbol],
            "trend_signal":         signal,
            "last_updated":         now.strftime("%d %b %Y %I:%M %p"),
            "status":               "success"
        }

    except Exception as e:
        logger.error(f"get_vwap error: {str(e)}")
        return {
            "symbol":  symbol,
            "status":  "error",
            "message": str(e)
        }