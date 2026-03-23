from __future__ import annotations

import logging
from datetime import datetime, timedelta
from enum import Enum

import pandas as pd
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame
from alpaca.trading.enums import OrderSide

from src.alpaca_client import AlpacaClient

logger = logging.getLogger(__name__)


class Signal(Enum):
    BUY = "buy"
    SELL = "sell"
    HOLD = "hold"


class MeanReversionStrategy:
    """
    Simple mean-reversion strategy using a short vs. long SMA crossover.
    When price drops below the long SMA by a threshold -> BUY signal.
    When price rises above the long SMA by a threshold -> SELL signal.
    """

    def __init__(
        self,
        short_window: int = 5,
        long_window: int = 20,
        threshold_pct: float = 0.02,
    ) -> None:
        self.short_window = short_window
        self.long_window = long_window
        self.threshold_pct = threshold_pct

    def evaluate(self, symbol: str, client: AlpacaClient) -> Signal:
        end = datetime.now()
        start = end - timedelta(days=self.long_window * 2)

        request = StockBarsRequest(
            symbol_or_symbols=symbol,
            timeframe=TimeFrame.Day,
            start=start,
            end=end,
        )
        bars = client.get_bars(symbol, request)
        df = bars.df

        if df.empty or len(df) < self.long_window:
            logger.warning("Not enough data for %s, holding", symbol)
            return Signal.HOLD

        df["sma_short"] = df["close"].rolling(window=self.short_window).mean()
        df["sma_long"] = df["close"].rolling(window=self.long_window).mean()

        latest = df.iloc[-1]
        sma_short = latest["sma_short"]
        sma_long = latest["sma_long"]

        if pd.isna(sma_short) or pd.isna(sma_long):
            return Signal.HOLD

        deviation = (sma_short - sma_long) / sma_long

        if deviation < -self.threshold_pct:
            logger.info("%s: BUY signal (deviation=%.4f)", symbol, deviation)
            return Signal.BUY
        elif deviation > self.threshold_pct:
            logger.info("%s: SELL signal (deviation=%.4f)", symbol, deviation)
            return Signal.SELL

        logger.info("%s: HOLD (deviation=%.4f)", symbol, deviation)
        return Signal.HOLD
