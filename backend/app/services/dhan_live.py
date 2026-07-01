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


def calculate_vwap_from_candles(candles):
    """Calculate VWAP from candle data"""
    if not candles:
        return None
    
    tp_vol = 0
    total_vol = 0
    
    for candle in candles:
        typical_price = (candle['high'] + candle['low'] + candle['close']) / 3
        tp_vol += typical_price * candle['volume']
        total_vol += candle['volume']
    
    if total_vol == 0:
        return None
    
    return round(tp_vol / total_vol, 2)


def get_intraday_vwap(symbol="NIFTY"):
    """Get intraday VWAP using Dhan 1-minute candles"""
    try:
        dhan = get_dhan()
        config = INDICES.get(symbol, INDICES["NIFTY"])
        today = datetime.now().strftime("%Y-%m-%d")
        
        # Fetch 1-minute intraday data
        data = dhan.intraday_minute_data(
            security_id=config["security_id"],
            exchange_segment=config["segment"],
            instrument_type="INDEX",
            from_date=today,
            to_date=today,
            interval=1
        )
        
        if data.get('status') != 'success':
            logger.error(f"VWAP fetch failed: {data.get('remarks')}")
            return None
        
        candles_raw = data.get('data', {})
        timestamps = candles_raw.get('timestamp', [])
        highs = candles_raw.get('high', [])
        lows = candles_raw.get('low', [])
        closes = candles_raw.get('close', [])
        volumes = candles_raw.get('volume', [])
        
        if not timestamps:
            return None
        
        candles = []
        for i in range(len(timestamps)):
            candles.append({
                'high': float(highs[i]),
                'low': float(lows[i]),
                'close': float(closes[i]),
                'volume': float(volumes[i])
            })
        
        vwap = calculate_vwap_from_candles(candles)
        
        # Get current spot price
        spot = closes[-1] if closes else None
        
        # Determine bias
        if spot and vwap:
            if spot > vwap:
                bias = "BULLISH - Above VWAP"
            elif spot < vwap:
                bias = "BEARISH - Below VWAP"
            else:
                bias = "NEUTRAL - At VWAP"
        else:
            bias = "N/A"
        
        return {
            'vwap': vwap,
            'spot': spot,
            'bias': bias,
            'last_updated': datetime.now().strftime("%I:%M:%S %p")
        }
    
    except Exception as e:
        logger.error(f"get_intraday_vwap error: {e}")
        return None


def calculate_max_pain(option_chain_data, spot_price):
    """Calculate Max Pain from option chain"""
    if not option_chain_data or spot_price is None:
        return {
            'max_pain_level': None,
            'pain_value': None,
            'distance_from_spot': None,
            'bias': 'NEUTRAL',
            'pcr': None,
            'market_pressure': 'NO DATA',
            'signal': 'Waiting for data'
        }
    
    pain_calculation = []
    total_ce_oi = 0
    total_pe_oi = 0
    
    for strike_data in option_chain_data:
        strike = strike_data['strike']
        ce_oi = strike_data.get('ce_oi', 0)
        pe_oi = strike_data.get('pe_oi', 0)
        
        total_ce_oi += ce_oi
        total_pe_oi += pe_oi
        
        # Call pain (OTM calls only)
        call_pain = 0
        if strike > spot_price:
            call_pain = ce_oi * (strike - spot_price)
        
        # Put pain (OTM puts only)
        put_pain = 0
        if strike < spot_price:
            put_pain = pe_oi * (spot_price - strike)
        
        total_pain = call_pain + put_pain
        
        pain_calculation.append({
            'strike': strike,
            'call_pain': round(call_pain, 2),
            'put_pain': round(put_pain, 2),
            'total_pain': round(total_pain, 2)
        })
    
    if not pain_calculation:
        return None
    
    # Find strike with minimum total pain
    max_pain_strike = min(pain_calculation, key=lambda x: x['total_pain'])
    max_pain_level = max_pain_strike['strike']
    pain_value = max_pain_strike['total_pain']
    
    # Calculate PCR
    pcr = round(total_pe_oi / total_ce_oi, 2) if total_ce_oi > 0 else 1
    
    # Determine bias
    if spot_price < max_pain_level:
        bias = 'BULLISH'
        signal = f"Price below Max Pain ({max_pain_level}) - Expect UP move"
    elif spot_price > max_pain_level:
        bias = 'BEARISH'
        signal = f"Price above Max Pain ({max_pain_level}) - Expect DOWN move"
    else:
        bias = 'NEUTRAL'
        signal = f"At Max Pain ({max_pain_level}) - Range bound"
    
    # Market pressure based on PCR
    if pcr > 1.2:
        pressure = "🟢 SELLING PRESSURE - Put writing heavy (Bearish)"
    elif pcr < 0.8:
        pressure = "🔴 BUYING PRESSURE - Call writing heavy (Bullish)"
    else:
        pressure = "🟡 NEUTRAL - Balanced OI"
    
    return {
        'max_pain_level': max_pain_level,
        'pain_value': round(pain_value, 2),
        'distance_from_spot': round(max_pain_level - spot_price, 2),
        'bias': bias,
        'signal': signal,
        'pcr': pcr,
        'market_pressure': pressure,
        'pcr_signal': 'BULLISH' if pcr < 0.8 else 'BEARISH' if pcr > 1.2 else 'NEUTRAL'
    }


def get_live_straddle(symbol="NIFTY"):
    """Get live straddle data with VWAP and Max Pain"""
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

        # Calculate VWAP
        vwap_data = get_intraday_vwap(symbol)
        
        # Calculate Max Pain
        max_pain_data = calculate_max_pain(strikes, spot)

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
            "vwap":           vwap_data.get('vwap') if vwap_data else None,
            "vwap_bias":      vwap_data.get('bias') if vwap_data else None,
            "max_pain":       max_pain_data.get('max_pain_level') if max_pain_data else None,
            "max_pain_signal": max_pain_data.get('signal') if max_pain_data else None,
            "market_pressure": max_pain_data.get('market_pressure') if max_pain_data else None,
            "max_pain_distance": max_pain_data.get('distance_from_spot') if max_pain_data else None,
            "last_updated":   datetime.now().strftime("%I:%M:%S %p"),
        }

    except Exception as e:
        logger.error(f"get_live_straddle error: {e}")
        return {"status": "error", "message": str(e)}