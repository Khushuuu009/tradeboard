import requests
import logging
import json
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

BASE_URL  = "https://straddle-chart.financedeft.com/history"
META_URL  = f"{BASE_URL}/history_meta.json"
HEADERS   = {"User-Agent": "Mozilla/5.0", "Accept": "application/json"}

CACHE_DIR  = Path(__file__).parent.parent.parent / "data"
CACHE_FILE = CACHE_DIR / "straddle_cache.json"


def load_cache():
    try:
        if CACHE_FILE.exists():
            with open(CACHE_FILE, "r") as f:
                return json.load(f)
    except Exception as e:
        logger.error(f"Cache load error: {e}")
    return {}


def save_cache(cache):
    try:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        with open(CACHE_FILE, "w") as f:
            json.dump(cache, f, indent=2)
    except Exception as e:
        logger.error(f"Cache save error: {e}")


def cache_key(date_str, expiry_str):
    return f"NIFTY_{date_str}_{expiry_str}"


def get_lowest_straddle(date_str, cache=None):
    """
    For a given date, return lowest straddle closing across all expiries.
    Pass cache dict to avoid reloading from disk every call.
    """
    if cache is None:
        cache = load_cache()

    # Get expiries from metadata
    dates   = cache.get("META_NIFTY", [])
    entry   = next((d for d in dates if d["value"] == date_str), None)
    if not entry:
        return None

    expiries = [e["value"] for e in entry.get("expiries", [])]
    results  = []

    for expiry_str in expiries:
        key = cache_key(date_str, expiry_str)
        pl  = cache.get(key)
        if not pl:
            continue
        last = pl[-1]
        results.append({
            "expiry":         expiry_str,
            "strike":         last["straddle_strike"],
            "ce_close":       last["ce_price"],
            "pe_close":       last["pe_price"],
            "straddle_close": round(last["ce_price"] + last["pe_price"], 2),
            "spot_close":     last["spot"],
            "time":           last["time"],
        })

    if not results:
        return None

    return min(results, key=lambda x: x["straddle_close"])


def get_expiry_straddle_data(expiry_date_str, index="NIFTY", category="equity"):
    return get_lowest_straddle(expiry_date_str)


def get_expiries_for_date(date_str):
    cache  = load_cache()
    dates  = cache.get("META_NIFTY", [])
    entry  = next((d for d in dates if d["value"] == date_str), None)
    if not entry:
        return []
    return [e["value"] for e in entry.get("expiries", [])]