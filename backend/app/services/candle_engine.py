# app/services/candle_engine.py
import math
from collections import deque
from typing import Dict, Optional, List
from dataclasses import dataclass, field

@dataclass
class Candle:
    time: int
    open: float
    high: float
    low: float
    close: float
    volume: int

@dataclass
class CandleBuilder:
    timeframe_seconds: int
    current_candle: Optional[Candle] = None
    finalized_candles: deque = field(default_factory=lambda: deque(maxlen=3000))

    def add_tick(self, price: float, ts_seconds: int, volume: int = 1):
        bucket_start = (ts_seconds // self.timeframe_seconds) * self.timeframe_seconds
        if self.current_candle is None:
            self.current_candle = Candle(bucket_start, price, price, price, price, volume)
            return None
        if bucket_start == self.current_candle.time:
            self.current_candle.high = max(self.current_candle.high, price)
            self.current_candle.low = min(self.current_candle.low, price)
            self.current_candle.close = price
            self.current_candle.volume += volume
            return None
        finalized = self.current_candle
        self.finalized_candles.append(finalized)
        self.current_candle = Candle(bucket_start, price, price, price, price, volume)
        return finalized

class MultiTimeframeCandleEngine:
    def __init__(self):
        self.timeframes = {
            '1S': 1, '30S': 30, '1M': 60, '3M': 180,
            '5M': 300, '10M': 600, '15M': 900,
            '30M': 1800, '1H': 3600
        }
        self.builders = {name: CandleBuilder(seconds) for name, seconds in self.timeframes.items()}

    def process_tick(self, price: float, timestamp_ms: int, volume: int = 1):
        ts_sec = timestamp_ms // 1000
        finalized = {}
        for name, builder in self.builders.items():
            candle = builder.add_tick(price, ts_sec, volume)
            if candle:
                finalized[name] = {
                    'time': candle.time,
                    'open': candle.open,
                    'high': candle.high,
                    'low': candle.low,
                    'close': candle.close,
                    'volume': candle.volume
                }
        return finalized

    def get_all_current_candles(self):
        result = {}
        for name, builder in self.builders.items():
            if builder.current_candle:
                c = builder.current_candle
                result[name] = {
                    'time': c.time, 'open': c.open, 'high': c.high,
                    'low': c.low, 'close': c.close, 'volume': c.volume
                }
        return result

    def get_historical_candles(self, tf_name: str, limit: int = 500):
        builder = self.builders.get(tf_name)
        if not builder:
            return []
        candles = list(builder.finalized_candles)
        return [{
            'time': c.time, 'open': c.open, 'high': c.high,
            'low': c.low, 'close': c.close, 'volume': c.volume
        } for c in candles[-limit:]]