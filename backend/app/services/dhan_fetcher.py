import os
import logging
import json
import time as time_module
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv
from dhanhq import dhanhq

load_dotenv()
logger = logging.getLogger(__name__)

# ── DHAN CLIENT ───────────────────────────────────────────────────────────────
_dhan_client = None

def get_dhan():
    global _dhan_client
    if _dhan_client is None:
        client_id    = os.getenv('DHAN_CLIENT_ID')
        access_token = os.getenv('DHAN_ACCESS_TOKEN')
        if not client_id or not access_token:
            raise Exception("DHAN_CLIENT_ID or DHAN_ACCESS_TOKEN missing from .env")
        _dhan_client = dhanhq(client_id, access_token)
        logger.info("Dhan client initialized")
    return _dhan_client

NIFTY_SECURITY_ID = '13'
NIFTY_SEGMENT     = 'IDX_I'
NIFTY_INSTRUMENT  = 'INDEX'

# ── LOCAL CACHE ───────────────────────────────────────────────────────────────
CACHE_DIR  = Path(__file__).parent.parent.parent / "data"
VWAP_CACHE = CACHE_DIR / "vwap_cache.json"

def load_vwap_cache():
    try:
        if VWAP_CACHE.exists():
            with open(VWAP_CACHE, "r") as f:
                return json.load(f)
    except Exception as e:
        logger.error(f"VWAP cache load error: {e}")
    return {}

def save_vwap_cache(cache):
    try:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        with open(VWAP_CACHE, "w") as f:
            json.dump(cache, f, indent=2)
    except Exception as e:
        logger.error(f"VWAP cache save error: {e}")


# ── FETCH 1-MIN CANDLES ───────────────────────────────────────────────────────

def fetch_1min_candles_dhan(date_str):
    """Fetch 1-min NIFTY candles — checks cache first"""
    cache     = load_vwap_cache()
    cache_key = f"NIFTY_{date_str}"

    # Return from cache if available
    if cache_key in cache:
        logger.info(f"VWAP Cache HIT: {cache_key}")
        return cache[cache_key]

    # Fetch from Dhan
    try:
        dhan = get_dhan()
        data = dhan.intraday_minute_data(
            security_id      = NIFTY_SECURITY_ID,
            exchange_segment = NIFTY_SEGMENT,
            instrument_type  = NIFTY_INSTRUMENT,
            from_date        = date_str,
            to_date          = date_str,
            interval         = 1
        )

        if data.get('status') != 'success':
            logger.error(f"Dhan fetch failed for {date_str}: {data.get('remarks')}")
            return []

        candles_raw = data.get('data', {})
        timestamps  = candles_raw.get('timestamp', [])
        opens       = candles_raw.get('open',      [])
        highs       = candles_raw.get('high',      [])
        lows        = candles_raw.get('low',       [])
        closes      = candles_raw.get('close',     [])
        volumes     = candles_raw.get('volume',    [])

        if not timestamps:
            return []

        candles = []
        for i in range(len(timestamps)):
            ts = timestamps[i]
            dt = datetime.fromtimestamp(ts / 1000) if ts > 1e10 else datetime.fromtimestamp(ts)
            if dt.hour == 15 and dt.minute > 20:
                continue
            candles.append({
                "timestamp": dt.strftime("%Y-%m-%dT%H:%M:%S"),
                "open":      float(opens[i]),
                "high":      float(highs[i]),
                "low":       float(lows[i]),
                "close":     float(closes[i]),
                "volume":    float(volumes[i]),
            })

        if candles:
            cache[cache_key] = candles
            save_vwap_cache(cache)
            logger.info(f"VWAP cached: {cache_key} ({len(candles)} candles)")

        return candles

    except Exception as e:
        logger.error(f"fetch_1min_candles_dhan error for {date_str}: {str(e)}")
        return []


# ── CALCULATE VWAP ────────────────────────────────────────────────────────────

def calculate_vwap(candles):
    if not candles:
        return None
    tp_vol    = 0
    total_vol = 0
    for c in candles:
        tp         = (c["high"] + c["low"] + c["close"]) / 3
        tp_vol    += tp * c["volume"]
        total_vol += c["volume"]
    if total_vol == 0:
        return None
    return round(tp_vol / total_vol, 2)