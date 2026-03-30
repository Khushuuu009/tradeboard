# ⬡ TradeBoard

> Real-time NIFTY options straddle dashboard — built for Indian options traders

**Live Demo:** [tradeboard-eight.vercel.app](https://tradeboard-eight.vercel.app)

---

## What is TradeBoard?

TradeBoard is a personal live trading dashboard that tracks NIFTY 50 straddle premiums in real time. It connects directly to Dhan's WebSocket API to stream live CE and PE prices, calculates straddle premium on every tick, and builds a full-day intraday chart minute by minute.

Built by an options trader, for options traders.

> **Note:** The live demo runs in demo mode (sample expiry day data). To see real live data, run the backend locally and connect your Dhan API credentials.

---

## Features

- ⚡ **Real-time straddle price** via Dhan WebSocket — CE + PE updates on every tick
- 📊 **Live intraday chart** — builds from 9:15 AM, persists to disk after market close
- 🔗 **Option chain** — full ±5 strike chain with ATM highlighted in real time
- 📋 **Info bar** — DTE, Spot, Open, High, Low, ATM, CE, PE, Synthetic Future, Expiry
- 📈 **VWAP analysis** — calculated from Dhan 1-min candles with real volume
- 🔬 **Research portal** — 545+ days of daily straddle history, expiry day analysis, VWAP backtest
- 📰 **Market news** — live RSS feed with impact tagging
- 🔄 **Auto-reconnect** — WebSocket reconnects automatically, falls back to demo mode

---

## Tech Stack

| Layer | Tech |
|-------|------|
| Frontend | Next.js 14, TypeScript, Recharts |
| Backend | FastAPI, Python 3.11 |
| Live Data | Dhan WebSocket API (v2) |
| Historical | Dhan 1-min candles + FinanceDeft straddle history |
| Storage | Local JSON files (no database needed) |

---

## Project Structure

```
tradeboard/
├── backend/
│   ├── app/
│   │   ├── api/routes.py              # All REST API endpoints
│   │   └── services/
│   │       ├── ws_feed.py             # Dhan WebSocket → FastAPI WebSocket
│   │       ├── dhan_live.py           # Live option chain via Dhan REST
│   │       ├── dhan_fetcher.py        # 1-min NIFTY candles + VWAP cache
│   │       ├── vwap_calculator.py     # VWAP on Dhan candles
│   │       ├── expiry_analyzer.py     # CSV-based backtest engine
│   │       └── news_fetcher.py        # RSS market news
│   ├── data/
│   │   ├── nifty_straddle_history.csv # 545+ days of daily straddle data
│   │   └── vwap_cache.json            # Dhan 1-min candle cache
│   ├── main.py
│   └── requirements.txt
└── frontend/
    └── app/
        ├── page.tsx                   # Main straddle dashboard
        └── research/page.tsx          # Research portal (password protected)
```

---

## Local Setup

### Prerequisites
- Python 3.11+
- Node.js 18+
- Dhan trading account with API access

### Backend

```bash
cd backend
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

Create `.env` in `backend/`:
```
DHAN_CLIENT_ID=your_client_id
DHAN_ACCESS_TOKEN=your_access_token
```

> ⚠️ Dhan access token expires daily — regenerate at web.dhan.co every morning

```bash
uvicorn app.main:app --reload --port 8000
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:3001`

---

## How the WebSocket Works

```
Dhan WS (NIFTY spot + ATM CE + ATM PE)
         ↓ every tick (~1 sec)
FastAPI background task
         ↓ CE + PE → straddle recalculated instantly
         ↓ broadcasts at max 10/sec
Frontend WebSocket
         ↓ updates UI in real time
         ↓ saves chart point every minute to disk
```

ATM strike auto-refreshes every 5 minutes to track the market.

---

## API Endpoints

| Endpoint | Description |
|----------|-------------|
| `GET /api/live-straddle?symbol=NIFTY` | Live ATM straddle via Dhan |
| `GET /api/vwap` | Intraday VWAP from 1-min candles |
| `GET /api/daily-straddle?months=3` | Historical daily straddle from CSV |
| `GET /api/vwap-backtest?months=12` | VWAP backtest results |
| `GET /api/expiry-analysis` | Expiry day VWAP accuracy analysis |
| `GET /api/news` | Live market news |
| `WS  /ws` | Real-time straddle + spot WebSocket |

---

## Research Portal

Access at `/research` — Password: `tradeboard2026`

- Daily straddle closing history (545+ days from Jan 2024)
- Expiry day VWAP accuracy analysis
- VWAP backtest with signal history

---

## Notes

- NIFTY expiry is **Tuesday** — update `FALLBACK_EXPIRY` in `ws_feed.py` weekly
- Chart data persists to `data/straddle_YYYY-MM-DD.json` after market close
- Demo mode activates automatically when backend is unreachable

---

## Disclaimer

Personal tool built for educational and research purposes. Not financial advice. Options trading involves significant risk.

---

Built with ☕ by [Harshu](https://github.com/Khushuuu009)