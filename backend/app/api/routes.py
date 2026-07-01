from fastapi import APIRouter
from datetime import datetime
from app.services.dhan_live import get_live_straddle, get_intraday_vwap, calculate_max_pain
from app.services.news_fetcher import fetch_news

router = APIRouter()


@router.get("/live-straddle")
async def live_straddle(symbol: str = "NIFTY"):
    """Get live straddle data with VWAP and Max Pain"""
    return get_live_straddle(symbol)


@router.get("/vwap")
async def vwap(symbol: str = "NIFTY"):
    """Get VWAP data"""
    return get_intraday_vwap(symbol)


@router.get("/max-pain")
async def max_pain(symbol: str = "NIFTY"):
    """Get Max Pain analysis"""
    try:
        straddle_data = get_live_straddle(symbol)
        
        if straddle_data.get("status") != "success":
            return {"status": "error", "message": straddle_data.get("message")}
        
        max_pain_data = calculate_max_pain(
            straddle_data.get("option_chain", []),
            straddle_data.get("spot")
        )
        
        return {
            "status": "success",
            "symbol": symbol,
            "spot": straddle_data.get("spot"),
            "max_pain_level": max_pain_data.get("max_pain_level"),
            "pain_value": max_pain_data.get("pain_value"),
            "distance": max_pain_data.get("distance_from_spot"),
            "bias": max_pain_data.get("bias"),
            "signal": max_pain_data.get("signal"),
            "pcr": max_pain_data.get("pcr"),
            "market_pressure": max_pain_data.get("market_pressure"),
            "last_updated": datetime.now().strftime("%I:%M:%S %p")
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}


@router.get("/news")
async def news():
    """Get latest financial news"""
    return fetch_news()


@router.get("/daily-straddle")
async def daily_straddle(months: int = 6):
    """Get historical straddle data for research"""
    try:
        from app.services.expiry_analyzer import run_daily_straddle
        result = run_daily_straddle(months)
        return result
    except Exception as e:
        return {"status": "error", "message": str(e)}


@router.get("/expiry-analysis")
async def expiry_analysis(months: int = 6):
    """Get expiry day analysis for research"""
    try:
        from app.services.expiry_analyzer import analyze_expiry_days
        result = analyze_expiry_days(months)
        return result
    except Exception as e:
        return {"status": "error", "message": str(e)}


@router.get("/vwap-backtest")
async def vwap_backtest(months: int = 12):
    """Get VWAP backtest results for research"""
    try:
        from app.services.expiry_analyzer import run_vwap_backtest
        result = run_vwap_backtest(months)
        return result
    except Exception as e:
        return {"status": "error", "message": str(e)}


@router.get("/health")
async def health():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat()
    }