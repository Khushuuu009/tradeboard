import pandas as pd
import numpy as np
import json
import requests
from datetime import datetime, timedelta
from pathlib import Path
from app.services.dhan_fetcher import fetch_1min_candles_dhan, calculate_vwap
from app.services.financedeft_fetcher import get_lowest_straddle
import logging
import time as time_module

logger = logging.getLogger(__name__)

STRIKE_GAP = 50
BASE_URL   = "https://straddle-chart.financedeft.com/history"
META_URL   = f"{BASE_URL}/history_meta.json"
HEADERS    = {"User-Agent": "Mozilla/5.0"}


# ── PART 1: EXPIRY DAY ANALYSIS (from CSV or Mock) ───────────────────────────────────

def analyze_expiry_days(months=6):
    try:
        csv_file = Path(__file__).parent.parent.parent / "data" / "nifty_straddle_history.csv"
        
        # If CSV doesn't exist, return mock data for research portal
        if not csv_file.exists():
            logger.warning("CSV not found. Returning mock data for research portal.")
            return get_mock_expiry_analysis(months)

        df = pd.read_csv(csv_file)
        cutoff = (datetime.today() - timedelta(days=months * 30)).strftime("%Y-%m-%d")
        df = df[df["date"] >= cutoff].copy()
        df = df.sort_values("date", ascending=False)

        expiry_days = df[df["is_expiry"] == "YES"].copy()

        if expiry_days.empty:
            return get_mock_expiry_analysis(months)

        expiry_analysis = []
        for _, row in expiry_days.iterrows():
            expiry_analysis.append({
                "date": row["date"],
                "weekday": row.get("weekday", ""),
                "atm_strike": row["atm_strike"],
                "ce_close": row["ce_close"],
                "pe_close": row["pe_close"],
                "straddle_close": row["straddle_close"],
                "spot_close": row["spot_close"],
                "vwap_320": row["vwap_320"] if row["vwap_320"] != "" else None,
                "signal": row.get("signal", "N/A"),
            })

        total = len(expiry_analysis)
        avg_straddle = round(expiry_days["straddle_close"].mean(), 2)

        return {
            "status": "success",
            "summary": {
                "total_expiry_days": total,
                "avg_straddle_close": avg_straddle,
                "analysis_period": f"Last {months} months",
                "data_source": "FinanceDeft (cached CSV)",
                "last_updated": datetime.now().strftime("%d %b %Y %I:%M %p")
            },
            "expiry_days": expiry_analysis,
        }
    except Exception as e:
        logger.error(f"Expiry analysis error: {e}")
        return get_mock_expiry_analysis(months)


# ── PART 2: VWAP BACKTEST (from CSV or Mock) ─────────────────────────────────────────

def run_vwap_backtest(months=12):
    try:
        csv_file = Path(__file__).parent.parent.parent / "data" / "nifty_straddle_history.csv"
        
        if not csv_file.exists():
            logger.warning("CSV not found. Returning mock VWAP backtest data.")
            return get_mock_vwap_backtest(months)

        df = pd.read_csv(csv_file)
        cutoff = (datetime.today() - timedelta(days=months * 30)).strftime("%Y-%m-%d")
        df = df[df["date"] >= cutoff].copy()

        df = df[df["vwap_320"] != ""].copy()
        df = df[df["signal"] != ""].copy()
        df = df.sort_values("date", ascending=False)
        df = df.fillna("")

        results = df.to_dict(orient="records")

        if not results:
            return get_mock_vwap_backtest(months)

        total = len(results)
        avg_straddle = round(df["straddle_close"].mean(), 2)
        avg_ce = round(df["ce_close"].mean(), 2)
        avg_pe = round(df["pe_close"].mean(), 2)
        above_vwap = len(df[df["signal"] == "ABOVE VWAP"])

        return {
            "status": "success",
            "summary": {
                "total_expiry_days": total,
                "avg_straddle_close": avg_straddle,
                "avg_ce_close": avg_ce,
                "avg_pe_close": avg_pe,
                "above_vwap_count": above_vwap,
                "below_vwap_count": total - above_vwap,
                "analysis_period": f"Last {months} months",
                "data_source": "Dhan (VWAP) + FinanceDeft (Options)",
                "last_updated": datetime.now().strftime("%d %b %Y %I:%M %p"),
            },
            "expiry_results": results,
        }
    except Exception as e:
        logger.error(f"VWAP backtest error: {e}")
        return get_mock_vwap_backtest(months)


# ── PART 3: DAILY STRADDLE (from CSV or Mock) ────────────────────────────────────────

def run_daily_straddle(months=3):
    try:
        csv_file = Path(__file__).parent.parent.parent / "data" / "nifty_straddle_history.csv"
        
        if not csv_file.exists():
            logger.warning("CSV not found. Returning mock daily straddle data.")
            return get_mock_daily_straddle(months)

        df = pd.read_csv(csv_file)
        cutoff = (datetime.today() - timedelta(days=months * 30)).strftime("%Y-%m-%d")
        df = df[df["date"] >= cutoff].copy()
        df = df.sort_values("date", ascending=False)
        df = df.fillna("")

        results = df.to_dict(orient="records")
        avg_straddle = round(df["straddle_close"].mean(), 2)

        return {
            "status": "success",
            "summary": {
                "total_days": len(results),
                "avg_straddle_close": avg_straddle,
                "analysis_period": f"Last {months} months",
                "data_source": "Dhan (VWAP) + FinanceDeft (Options)",
                "last_updated": datetime.now().strftime("%d %b %Y %I:%M %p"),
            },
            "results": results,
        }
    except Exception as e:
        logger.error(f"Daily straddle error: {e}")
        return get_mock_daily_straddle(months)


# ── MOCK DATA FUNCTIONS (for when CSV doesn't exist) ─────────────────────────────────

def get_mock_expiry_analysis(months=6):
    """Return mock expiry analysis data for research portal"""
    # Generate last 10 expiry dates
    expiry_dates = []
    today = datetime.now()
    
    # Find Thursdays (NIFTY expiry day)
    for i in range(min(months, 6)):
        days_ahead = (3 - today.weekday()) % 7  # Thursday = 3
        if days_ahead == 0:
            days_ahead = 7
        expiry_date = today + timedelta(days=days_ahead - (i * 7))
        expiry_dates.append(expiry_date.strftime("%Y-%m-%d"))
    
    expiry_analysis = []
    for i, date_str in enumerate(expiry_dates[:10]):
        expiry_analysis.append({
            "date": date_str,
            "weekday": "Thursday",
            "atm_strike": 24800 + (i * 50),
            "ce_close": round(120 - (i * 8), 2),
            "pe_close": round(115 - (i * 7), 2),
            "straddle_close": round(235 - (i * 15), 2),
            "spot_close": 24800 + (i * 20),
            "vwap_320": 24750 + (i * 15) if i < 5 else None,
            "signal": "ABOVE VWAP" if i < 3 else "BELOW VWAP" if i > 6 else "N/A",
        })
    
    return {
        "status": "success",
        "summary": {
            "total_expiry_days": len(expiry_analysis),
            "avg_straddle_close": 180.50,
            "analysis_period": f"Last {months} months",
            "data_source": "Mock Data (CSV not found)",
            "last_updated": datetime.now().strftime("%d %b %Y %I:%M %p")
        },
        "expiry_days": expiry_analysis,
    }


def get_mock_vwap_backtest(months=12):
    """Return mock VWAP backtest data"""
    results = []
    today = datetime.now()
    
    for i in range(min(months * 4, 20)):  # ~4 expiry days per month
        date = (today - timedelta(days=i * 7)).strftime("%Y-%m-%d")
        above = i % 2 == 0
        results.append({
            "date": date,
            "straddle_close": round(200 + (i * 2), 2),
            "ce_close": round(100 + i, 2),
            "pe_close": round(100 + i, 2),
            "signal": "ABOVE VWAP" if above else "BELOW VWAP",
        })
    
    return {
        "status": "success",
        "summary": {
            "total_expiry_days": len(results),
            "avg_straddle_close": 210.50,
            "avg_ce_close": 110.25,
            "avg_pe_close": 105.75,
            "above_vwap_count": len([r for r in results if r["signal"] == "ABOVE VWAP"]),
            "below_vwap_count": len([r for r in results if r["signal"] == "BELOW VWAP"]),
            "analysis_period": f"Last {months} months",
            "data_source": "Mock Data (CSV not found)",
            "last_updated": datetime.now().strftime("%d %b %Y %I:%M %p"),
        },
        "expiry_results": results,
    }


def get_mock_daily_straddle(months=3):
    """Return mock daily straddle data"""
    results = []
    today = datetime.now()
    
    for i in range(min(months * 20, 60)):  # ~20 trading days per month
        date = (today - timedelta(days=i)).strftime("%Y-%m-%d")
        results.append({
            "date": date,
            "straddle_close": round(180 + (i * 0.5), 2),
            "ce_close": round(90 + (i * 0.3), 2),
            "pe_close": round(90 + (i * 0.2), 2),
            "spot_close": 24800 + (i * 2),
            "atm_strike": 24800 + ((i // 5) * 50),
        })
    
    return {
        "status": "success",
        "summary": {
            "total_days": len(results),
            "avg_straddle_close": 195.50,
            "analysis_period": f"Last {months} months",
            "data_source": "Mock Data (CSV not found)",
            "last_updated": datetime.now().strftime("%d %b %Y %I:%M %p"),
        },
        "results": results,
    }