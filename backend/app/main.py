from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import asyncio
import logging

from app.api.routes import router
from app.services.ws_feed import dhan_feed_loop, websocket_endpoint

logging.basicConfig(level=logging.INFO)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Start Dhan WebSocket feed in background on startup
    task = asyncio.create_task(dhan_feed_loop())
    yield
    task.cancel()

app = FastAPI(
    title       = "TradeBoard API",
    description = "Live NIFTY Options + VWAP",
    version     = "2.0.0",
    lifespan    = lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins     = ["http://localhost:3001"],
    allow_credentials = True,
    allow_methods     = ["*"],
    allow_headers     = ["*"],
)

app.include_router(router, prefix="/api")

# WebSocket endpoint for frontend
@app.websocket("/ws")
async def ws_route(websocket: WebSocket):
    await websocket_endpoint(websocket)

@app.get("/")
async def home():
    return {"status": "running", "message": "TradeBoard API live!"}