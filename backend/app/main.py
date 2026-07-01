from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import asyncio
import logging

from app.api.routes import router
from app.services.ws_feed import dhan_feed_loop, websocket_endpoint

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("🚀 TradeBoard Backend Starting...")
    task = asyncio.create_task(dhan_feed_loop())
    logger.info("✅ Dhan feed loop started")
    yield
    logger.info("🛑 TradeBoard Backend Shutting down...")
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        logger.info("Dhan feed loop cancelled successfully")


app = FastAPI(
    title="TradeBoard API",
    version="3.0",
    lifespan=lifespan
)

# Allow all CORS for development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router, prefix="/api")

# ❌ REMOVE THIS LINE – it's not needed for Next.js frontend
# app.mount("/static", StaticFiles(directory="static"), name="static")

@app.websocket("/ws")
async def ws_route(websocket: WebSocket):
    await websocket_endpoint(websocket)


@app.get("/")
async def home():
    return {"status": "running", "message": "TradeBoard Live"}


@app.get("/health")
async def health():
    from datetime import datetime
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)