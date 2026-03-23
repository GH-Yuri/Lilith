from __future__ import annotations

import logging
from decimal import Decimal

from alpaca.trading.client import TradingClient
from alpaca.trading.requests import MarketOrderRequest
from alpaca.trading.enums import OrderSide, TimeInForce
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame

from src.config import AlpacaConfig

logger = logging.getLogger(__name__)


class AlpacaClient:
    """Thin wrapper around the Alpaca SDK for trading and market data."""

    def __init__(self, config: AlpacaConfig) -> None:
        self.trading = TradingClient(
            api_key=config.api_key,
            secret_key=config.api_secret,
            paper=config.paper,
        )
        self.data = StockHistoricalDataClient(
            api_key=config.api_key,
            secret_key=config.api_secret,
        )

    def get_account(self):
        return self.trading.get_account()

    def get_positions(self) -> list:
        return self.trading.get_all_positions()

    def get_bars(self, symbol: str, request: StockBarsRequest):
        return self.data.get_stock_bars(request)

    def submit_market_order(
        self,
        symbol: str,
        qty: Decimal,
        side: OrderSide,
    ):
        order_data = MarketOrderRequest(
            symbol=symbol,
            qty=qty,
            side=side,
            time_in_force=TimeInForce.DAY,
        )
        logger.info("Submitting %s order: %s x %s", side.value, symbol, qty)
        return self.trading.submit_order(order_data)

    def is_market_open(self) -> bool:
        clock = self.trading.get_clock()
        return clock.is_open
