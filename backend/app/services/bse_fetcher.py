from datetime import datetime

# Stores last known BSE snapshot
CLOSING_SNAPSHOT_BSE = {
    "SENSEX": None,
    "BANKEX": None,
}

def is_market_open():
    # Monday-Friday 9:15 AM to 3:30 PM only
    now = datetime.now()
    if now.weekday() >= 5:
        return False
    market_open  = now.replace(hour=9,  minute=15, second=0, microsecond=0)
    market_close = now.replace(hour=15, minute=30, second=0, microsecond=0)
    return market_open <= now <= market_close

def generate_bse_mock_data(symbol="SENSEX"):
    # Mock closing prices for BSE instruments
    # Will be replaced with real BSE API when going live

    base_prices = {
        "SENSEX": {"spot": 73850.45, "atm": 73800, "interval": 100},
        "BANKEX":  {"spot": 55230.15, "atm": 55200, "interval": 100},
    }

    base      = base_prices.get(symbol, base_prices["SENSEX"])
    spot_price = base["spot"]
    atm_strike = base["atm"]
    interval   = base["interval"]

    # Generate 10 strikes above and below ATM
    strikes_data = []

    for i in range(10, -11, -1):
        strike = atm_strike + (i * interval)
        is_atm = strike == atm_strike
        distance = abs(i)

        if is_atm:
            ce_price = 320.50
            pe_price = 310.25
        elif i > 0:
            # Above ATM
            ce_price = max(5.0,   320.50 - (distance * 32.0))
            pe_price = min(650.0, 310.25 + (distance * 31.0))
        else:
            # Below ATM
            ce_price = min(650.0, 320.50 + (distance * 32.0))
            pe_price = max(5.0,   310.25 - (distance * 31.0))

        ce_price = round(ce_price, 2)
        pe_price = round(pe_price, 2)
        straddle = round(ce_price + pe_price, 2)

        strikes_data.append({
            "strike":   strike,
            "ce_price": ce_price,
            "pe_price": pe_price,
            "straddle": straddle,
            "is_atm":   is_atm
        })

    # ATM summary
    atm_row  = next(s for s in strikes_data if s["is_atm"])
    ce_price = atm_row["ce_price"]
    pe_price = atm_row["pe_price"]
    straddle = atm_row["straddle"]

    return {
        "symbol":           symbol,
        "spot_price":       spot_price,
        "atm_strike":       atm_strike,
        "ce_price":         ce_price,
        "pe_price":         pe_price,
        "straddle_premium": straddle,
        "weekly_expiry":    "14-Mar-2026",
        "strikes":          strikes_data,
        "saved_at":         datetime.now().strftime("%d %b %Y %I:%M %p")
    }

def get_bse_option_chain(symbol="SENSEX"):
    try:
        if is_market_open():
            # Market OPEN → fetch live data
            data = generate_bse_mock_data(symbol)
            CLOSING_SNAPSHOT_BSE[symbol] = data
            return {
                **data,
                "market_status": "open",
                "status":        "success"
            }
        else:
            # Market CLOSED → show closing prices
            data = generate_bse_mock_data(symbol)
            return {
                **data,
                "market_status": "closed",
                "message":       "Closing prices — Market opens Monday 9:15 AM",
                "status":        "success"
            }

    except Exception as e:
        return {
            "symbol":  symbol,
            "status":  "error",
            "message": str(e)
        }