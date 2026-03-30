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


# ── PART 1: EXPIRY DAY ANALYSIS (from CSV) ───────────────────────────────────

def analyze_expiry_days(months=6):
    try:
        csv_file = Path(__file__).parent.parent.parent / "data" / "nifty_straddle_history.csv"
        if not csv_file.exists():
            return {"status": "error", "message": "CSV not found. Run cache builder first."}

        df     = pd.read_csv(csv_file)
        cutoff = (datetime.today() - timedelta(days=months * 30)).strftime("%Y-%m-%d")
        df     = df[df["date"] >= cutoff].copy()
        df     = df.sort_values("date", ascending=False)

        # Filter expiry days only
        expiry_days = df[df["is_expiry"] == "YES"].copy()

        if expiry_days.empty:
            return {"status": "error", "message": "No expiry day data found"}

        expiry_analysis = []
        for _, row in expiry_days.iterrows():
            expiry_analysis.append({
                "date":          row["date"],
                "weekday":       row.get("weekday", ""),
                "atm_strike":    row["atm_strike"],
                "ce_close":      row["ce_close"],
                "pe_close":      row["pe_close"],
                "straddle_close": row["straddle_close"],
                "spot_close":    row["spot_close"],
                "vwap_320":      row["vwap_320"] if row["vwap_320"] != "" else None,
                "signal":        row.get("signal", "N/A"),
            })

        total        = len(expiry_analysis)
        avg_straddle = round(expiry_days["straddle_close"].mean(), 2)

        return {
            "status": "success",
            "summary": {
                "total_expiry_days":   total,
                "avg_straddle_close":  avg_straddle,
                "analysis_period":     f"Last {months} months",
                "data_source":         "FinanceDeft (cached CSV)",
                "last_updated":        datetime.now().strftime("%d %b %Y %I:%M %p")
            },
            "expiry_days": expiry_analysis,
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}


# ── PART 2: VWAP BACKTEST (from CSV) ─────────────────────────────────────────

def run_vwap_backtest(months=12):
    try:
        csv_file = Path(__file__).parent.parent.parent / "data" / "nifty_straddle_history.csv"
        if not csv_file.exists():
            return {"status": "error", "message": "CSV not found."}

        df     = pd.read_csv(csv_file)
        cutoff = (datetime.today() - timedelta(days=months * 30)).strftime("%Y-%m-%d")
        df     = df[df["date"] >= cutoff].copy()

        # Only rows where we have VWAP data (expiry Mondays)
        df = df[df["vwap_320"] != ""].copy()
        df = df[df["signal"] != ""].copy()
        df = df.sort_values("date", ascending=False)
        df = df.fillna("")

        results = df.to_dict(orient="records")

        if not results:
            return {"status": "error", "message": "No VWAP data found."}

        total        = len(results)
        avg_straddle = round(df["straddle_close"].mean(), 2)
        avg_ce       = round(df["ce_close"].mean(), 2)
        avg_pe       = round(df["pe_close"].mean(), 2)
        above_vwap   = len(df[df["signal"] == "ABOVE VWAP"])

        return {
            "status": "success",
            "summary": {
                "total_expiry_days":  total,
                "avg_straddle_close": avg_straddle,
                "avg_ce_close":       avg_ce,
                "avg_pe_close":       avg_pe,
                "above_vwap_count":   above_vwap,
                "below_vwap_count":   total - above_vwap,
                "analysis_period":    f"Last {months} months",
                "data_source":        "Dhan (VWAP) + FinanceDeft (Options)",
                "last_updated":       datetime.now().strftime("%d %b %Y %I:%M %p"),
            },
            "expiry_results": results,
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}


# ── PART 3: DAILY STRADDLE (from CSV) ────────────────────────────────────────

def run_daily_straddle(months=3):
    try:
        csv_file = Path(__file__).parent.parent.parent / "data" / "nifty_straddle_history.csv"
        if not csv_file.exists():
            return {"status": "error", "message": "CSV not found."}

        df     = pd.read_csv(csv_file)
        cutoff = (datetime.today() - timedelta(days=months * 30)).strftime("%Y-%m-%d")
        df     = df[df["date"] >= cutoff].copy()
        df     = df.sort_values("date", ascending=False)
        df     = df.fillna("")

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