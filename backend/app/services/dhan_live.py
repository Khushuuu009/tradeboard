import os
import logging
from datetime import datetime
from dotenv import load_dotenv
from dhanhq import dhanhq

load_dotenv()
logger = logging.getLogger(__name__)

_dhan_client = None

def get_dhan():
    global _dhan_client
    if _dhan_client is None:
        _dhan_client = dhanhq(os.getenv('DHAN_CLIENT_ID'), os.getenv('DHAN_ACCESS_TOKEN'))
    return _dhan_client

INDICES = {
    "NIFTY":     {"security_id": 13,  "segment": "IDX_I", "strike_gap": 50},
    "BANKNIFTY": {"security_id": 25,  "segment": "IDX_I", "strike_gap": 100},
    "SENSEX":    {"security_id": 51,  "segment": "IDX_I", "strike_gap": 100},
}


def get_nearest_expiry(symbol="NIFTY"):
    try:
        dhan    = get_dhan()
        config  = INDICES.get(symbol, INDICES["NIFTY"])
        result  = dhan.expiry_list(
            under_security_id      = config["security_id"],
            under_exchange_segment = config["segment"]
        )
        expiries = result.get("data", {}).get("data", [])
        if not expiries:
            return None
        return expiries[0]
    except Exception as e:
        logger.error(f"get_nearest_expiry error: {e}")
        return None


def get_live_straddle(symbol="NIFTY"):
    try:
        dhan   = get_dhan()
        config = INDICES.get(symbol, INDICES["NIFTY"])
        expiry = get_nearest_expiry(symbol)

        if not expiry:
            return {"status": "error", "message": "Could not fetch expiry"}

        chain = dhan.option_chain(
            under_security_id      = config["security_id"],
            under_exchange_segment = config["segment"],
            expiry                 = expiry
        )

        if chain.get("status") != "success":
            return {"status": "error", "message": "Option chain fetch failed"}

        spot       = chain["data"]["data"]["last_price"]
        oc         = chain["data"]["data"]["oc"]
        strike_gap = config["strike_gap"]
        atm        = round(spot / strike_gap) * strike_gap
        atm_key    = f"{float(atm):.6f}"

        if atm_key not in oc:
            return {"status": "error", "message": f"ATM strike {atm} not found"}

        ce_data = oc[atm_key]["ce"]
        pe_data = oc[atm_key]["pe"]
        ce      = ce_data["last_price"]
        pe      = pe_data["last_price"]

        # Build option chain ± 5 strikes
        strikes = []
        for strike_str, data in oc.items():
            strike = float(strike_str)
            if abs(strike - atm) <= strike_gap * 5:
                strikes.append({
                    "strike":     int(strike),
                    "ce_price":   data["ce"]["last_price"],
                    "ce_oi":      data["ce"]["oi"],
                    "pe_price":   data["pe"]["last_price"],
                    "pe_oi":      data["pe"]["oi"],
                    "straddle":   round(data["ce"]["last_price"] + data["pe"]["last_price"], 2),
                })
        strikes.sort(key=lambda x: x["strike"])

        return {
            "status":         "success",
            "symbol":         symbol,
            "spot":           spot,
            "atm":            atm,
            "expiry":         expiry,
            "ce_price":       ce,
            "pe_price":       pe,
            "straddle":       round(ce + pe, 2),
            "ce_oi":          ce_data["oi"],
            "pe_oi":          pe_data["oi"],
            "pcr":            round(pe_data["oi"] / ce_data["oi"], 2) if ce_data["oi"] else 0,
            "option_chain":   strikes,
            "last_updated":   datetime.now().strftime("%I:%M:%S %p"),
        }

    except Exception as e:
        logger.error(f"get_live_straddle error: {e}")
        return {"status": "error", "message": str(e)}