from fastapi import APIRouter
from fastapi.responses import FileResponse
from datetime import datetime, timedelta, date
from collections import deque
import pandas as pd
import requests as req

from app.services.news_fetcher import fetch_news
from app.services.vwap_calculator import get_vwap
from app.services.expiry_analyzer import analyze_expiry_days, run_vwap_backtest
from app.services.dhan_live import get_live_straddle, get_dhan

router = APIRouter()

# ── IN-MEMORY STRADDLE HISTORY ─────────────────────────────────────────────
# Stores today's 1-min straddle data — persists until backend restarts
today_straddle_history: deque = deque(maxlen=500)  # ~8 hours of 1-min data


@router.get("/test")
async def test():
    return {"status": "running", "message": "Trading Dashboard API is live!"}


@router.get("/news")
async def get_news():
    return fetch_news()


@router.get("/vwap")
async def get_vwap_data():
    return get_vwap("NIFTY")


@router.get("/expiry-analysis")
async def get_expiry_analysis():
    return analyze_expiry_days(months=6)


@router.get("/vwap-backtest")
async def get_vwap_backtest(months: int = 12):
    return run_vwap_backtest(months)


@router.get("/straddle-csv")
async def get_straddle_csv():
    return FileResponse(
        "data/nifty_straddle_history.csv",
        media_type="text/csv",
        filename="nifty_straddle_history.csv"
    )


@router.get("/daily-straddle")
async def get_daily_straddle(months: int = 3):
    try:
        df           = pd.read_csv("data/nifty_straddle_history.csv")
        cutoff       = (datetime.today() - timedelta(days=months * 30)).strftime("%Y-%m-%d")
        df           = df[df["date"] >= cutoff]
        df           = df.sort_values("date", ascending=False)
        df           = df.fillna("")
        results      = df.to_dict(orient="records")
        avg_straddle = round(df["straddle_close"].mean(), 2)
        return {
            "status": "success",
            "summary": {
                "total_days":         len(results),
                "avg_straddle_close": avg_straddle,
                "analysis_period":    f"Last {months} months",
                "data_source":        "Dhan (VWAP) + FinanceDeft (Options)",
                "last_updated":       datetime.now().strftime("%d %b %Y %I:%M %p"),
            },
            "results": results,
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}


@router.get("/live-straddle")
async def live_straddle(symbol: str = "NIFTY"):
    return get_live_straddle(symbol)


@router.get("/record-straddle")
async def record_straddle(symbol: str = "NIFTY"):
    """Called every minute to record live straddle into memory"""
    try:
        data = get_live_straddle(symbol)
        if data["status"] == "success":
            now = datetime.now()
            point = {
                "time":     now.strftime("%I:%M %p"),
                "straddle": data["straddle"],
                "spot":     data["spot"],
                "ce":       data["ce_price"],
                "pe":       data["pe_price"],
                "strike":   data["atm"],
            }
            today_straddle_history.append(point)
            return {"status": "ok", "points": len(today_straddle_history), "latest": point}
        return {"status": "error", "message": "Live straddle fetch failed"}
    except Exception as e:
        return {"status": "error", "message": str(e)}


@router.get("/today-straddle")
async def get_today_straddle(symbol: str = "NIFTY"):
    """Return full today's straddle history from memory"""
    return {
        "status": "success",
        "data":   list(today_straddle_history),
        "points": len(today_straddle_history),
    }