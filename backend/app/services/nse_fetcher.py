from datetime import datetime, timedelta
from app.services.angel_auth import get_smartapi, INDEX_TOKENS
import logging

logger = logging.getLogger(__name__)

# ── MARKET HELPERS ────────────────────────────────────────────────────────────

def is_market_open():
    now = datetime.now()
    if now.weekday() >= 5:
        return False
    market_open  = now.replace(hour=9,  minute=15, second=0, microsecond=0)
    market_close = now.replace(hour=15, minute=30, second=0, microsecond=0)
    return market_open <= now <= market_close


def get_next_expiry(index="NIFTY"):
    """
    Get upcoming weekly expiry date for each index
    NIFTY     → Monday
    BANKNIFTY → Wednesday
    FINNIFTY  → Tuesday
    SENSEX    → Friday
    """
    expiry_weekday = {
        "NIFTY":      0,
        "BANKNIFTY":  2,
        "FINNIFTY":   1,
        "SENSEX":     4,
    }
    target_day = expiry_weekday.get(index, 0)
    today      = datetime.now()
    days_ahead = target_day - today.weekday()
    if days_ahead <= 0:
        days_ahead += 7
    expiry = today + timedelta(days=days_ahead)
    return expiry.strftime("%d%b%Y").upper()   # e.g. "17MAR2026"


def format_expiry_display(index="NIFTY"):
    """Human readable expiry e.g. '17 Mar 2026'"""
    expiry_weekday = {
        "NIFTY":     0,
        "BANKNIFTY": 2,
        "FINNIFTY":  1,
        "SENSEX":    4,
    }
    target_day = expiry_weekday.get(index, 0)
    today      = datetime.now()
    days_ahead = target_day - today.weekday()
    if days_ahead <= 0:
        days_ahead += 7
    expiry = today + timedelta(days=days_ahead)
    return expiry.strftime("%d %b %Y")


def get_atm_strike(spot_price, index="NIFTY"):
    """Round spot to nearest valid strike"""
    strike_gap = {
        "NIFTY":     50,
        "BANKNIFTY": 100,
        "FINNIFTY":  50,
        "SENSEX":    100,
    }
    gap = strike_gap.get(index, 50)
    return round(spot_price / gap) * gap


# ── ANGEL ONE DATA FETCHERS ───────────────────────────────────────────────────

def get_ltp(symbol="NIFTY"):
    """Get spot price (Last Traded Price) from Angel One"""
    try:
        obj      = get_smartapi()
        token    = INDEX_TOKENS.get(symbol)
        exchange = "BSE" if symbol == "SENSEX" else "NSE"

        response = obj.ltpData(exchange, symbol, token)

        if response and response.get("status"):
            return round(float(response["data"]["ltp"]), 2)
        return None

    except Exception as e:
        logger.error(f"get_ltp error for {symbol}: {str(e)}")
        return None


def search_option_token(symbol, exchange="NFO"):
    """Search Angel One for option contract token by symbol name"""
    try:
        obj      = get_smartapi()
        response = obj.searchScrip(exchange, symbol)

        if response and response.get("status"):
            data = response.get("data", [])
            if data:
                return data[0]["symboltoken"]
        return None

    except Exception as e:
        logger.error(f"search_option_token error for {symbol}: {str(e)}")
        return None


def get_option_ltp(token, exchange="NFO"):
    """Get LTP of an option contract using its token"""
    try:
        obj      = get_smartapi()
        response = obj.ltpData(exchange, "", token)

        if response and response.get("status"):
            return round(float(response["data"]["ltp"]), 2)
        return 0.0

    except Exception as e:
        logger.error(f"get_option_ltp error: {str(e)}")
        return 0.0


# ── MAIN FUNCTION ─────────────────────────────────────────────────────────────

# Stores last known snapshot when market is closed
CLOSING_SNAPSHOT = {
    "NIFTY":     None,
    "BANKNIFTY": None,
    "FINNIFTY":  None,
    "SENSEX":    None,
}


def get_option_chain(symbol="NIFTY"):
    """
    Fetch live option chain from Angel One
    Replaces the old mock data generator
    Returns CE + PE prices for ATM ± 4 strikes
    """
    try:
        exchange = "BFO" if symbol == "SENSEX" else "NFO"

        # ── MARKET CLOSED ──
        if not is_market_open():
            snapshot = CLOSING_SNAPSHOT.get(symbol)
            if snapshot:
                return {
                    **snapshot,
                    "market_status": "closed",
                    "message":       "Closing prices — Market opens at 9:15 AM",
                }
            return {
                "symbol":        symbol,
                "market_status": "closed",
                "message":       "Market closed. No closing snapshot available yet.",
                "strikes":       [],
                "weekly_expiry": format_expiry_display(symbol),
            }

        # ── MARKET OPEN ──
        # Step 1: Get spot price
        spot_price = get_ltp(symbol)
        if not spot_price:
            return {
                "symbol":        symbol,
                "market_status": "open",
                "message":       "Could not fetch spot price from Angel One.",
                "strikes":       [],
            }

        # Step 2: Calculate ATM strike
        atm_strike  = get_atm_strike(spot_price, symbol)
        expiry_str  = get_next_expiry(symbol)
        expiry_disp = format_expiry_display(symbol)

        # Step 3: Build strikes list (ATM ± 4)
        strike_gap      = 50 if symbol in ["NIFTY", "FINNIFTY"] else 100
        strikes_to_fetch = [atm_strike + (i * strike_gap) for i in range(-4, 5)]

        # Step 4: Fetch CE + PE price for each strike
        strikes_data = []
        atm_ce = 0.0
        atm_pe = 0.0

        for strike in strikes_to_fetch:
            ce_symbol = f"{symbol}{expiry_str}{int(strike)}CE"
            pe_symbol = f"{symbol}{expiry_str}{int(strike)}PE"

            ce_token = search_option_token(ce_symbol, exchange)
            pe_token = search_option_token(pe_symbol, exchange)

            ce_price = get_option_ltp(ce_token, exchange) if ce_token else 0.0
            pe_price = get_option_ltp(pe_token, exchange) if pe_token else 0.0
            straddle = round(ce_price + pe_price, 2)
            is_atm   = (strike == atm_strike)

            if is_atm:
                atm_ce = ce_price
                atm_pe = pe_price

            strikes_data.append({
                "strike":   strike,
                "ce_price": ce_price,
                "pe_price": pe_price,
                "straddle": straddle,
                "is_atm":   is_atm,
            })

        result = {
            "symbol":            symbol,
            "market_status":     "open",
            "spot_price":        spot_price,
            "atm_strike":        atm_strike,
            "ce_price":          atm_ce,
            "pe_price":          atm_pe,
            "straddle_premium":  round(atm_ce + atm_pe, 2),
            "weekly_expiry":     expiry_disp,
            "strikes":           strikes_data,
            "last_updated":      datetime.now().strftime("%d %b %Y %I:%M:%S %p"),
            "status":            "success",
        }

        # Save snapshot for when market closes
        CLOSING_SNAPSHOT[symbol] = result
        return result

    except Exception as e:
        logger.error(f"get_option_chain error: {str(e)}")
        return {
            "symbol":  symbol,
            "status":  "error",
            "message": str(e),
            "strikes": [],
        }