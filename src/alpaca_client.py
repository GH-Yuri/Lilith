from __future__ import annotations

import logging
from decimal import Decimal

from alpaca.trading.client import TradingClient
from alpaca.trading.requests import (
    MarketOrderRequest,
    TakeProfitRequest,
    StopLossRequest,
    GetOrdersRequest,
)
from alpaca.trading.enums import OrderSide, TimeInForce, OrderClass, QueryOrderStatus
from alpaca.data.historical import CryptoHistoricalDataClient
from alpaca.data.historical.news import NewsClient
from alpaca.data.requests import (
    CryptoBarsRequest,
    CryptoLatestQuoteRequest,
    CryptoSnapshotRequest,
    NewsRequest,
)
from alpaca.data.timeframe import TimeFrame

from src.config import AlpacaConfig

logger = logging.getLogger(__name__)


class AlpacaClient:
    """Wrapper around Alpaca SDK for crypto trading and market data."""

    def __init__(self, config: AlpacaConfig) -> None:
        self.trading = TradingClient(
            api_key=config.api_key,
            secret_key=config.api_secret,
            paper=config.paper,
        )
        self.crypto_data = CryptoHistoricalDataClient(
            api_key=config.api_key,
            secret_key=config.api_secret,
        )
        self.news_client = NewsClient(
            api_key=config.api_key,
            secret_key=config.api_secret,
        )

    # ── Account & Positions ──────────────────────────────────

    def get_account(self):
        return self.trading.get_account()

    def get_positions(self) -> list:
        return self.trading.get_all_positions()

    def get_position(self, symbol: str):
        try:
            return self.trading.get_open_position(symbol)
        except Exception:
            return None

    # ── Market Data (Crypto) ─────────────────────────────────

    def get_crypto_bars(self, symbol: str, timeframe: TimeFrame, start, end):
        request = CryptoBarsRequest(
            symbol_or_symbols=symbol,
            timeframe=timeframe,
            start=start,
            end=end,
        )
        return self.crypto_data.get_crypto_bars(request)

    def get_crypto_quote(self, symbol: str):
        request = CryptoLatestQuoteRequest(symbol_or_symbols=symbol)
        quotes = self.crypto_data.get_crypto_latest_quote(request)
        return quotes.get(symbol)

    def get_crypto_snapshot(self, symbol: str):
        request = CryptoSnapshotRequest(symbol_or_symbols=symbol)
        snapshots = self.crypto_data.get_crypto_snapshot(request)
        return snapshots.get(symbol)

    # ── News ─────────────────────────────────────────────────

    def get_news(self, symbol: str, limit: int = 10) -> list[dict]:
        search_symbol = symbol.split("/")[0] if "/" in symbol else symbol
        request = NewsRequest(symbols=search_symbol, limit=limit)
        raw = self.news_client.get_news(request)

        articles = []
        for item in raw:
            if isinstance(item, tuple) and len(item) == 2 and item[0] == "data":
                news_list = item[1].get("news", [])
                for article in news_list:
                    articles.append({
                        "headline": getattr(article, "headline", str(article)),
                        "source": getattr(article, "source", "unknown"),
                        "created_at": str(getattr(article, "created_at", "")),
                        "summary": getattr(article, "summary", ""),
                        "symbols": getattr(article, "symbols", []),
                    })
                break
        return articles[:limit]

    # ── Orders ───────────────────────────────────────────────

    def submit_bracket_order(
        self,
        symbol: str,
        qty: Decimal,
        side: OrderSide,
        take_profit_price: float,
        stop_loss_price: float,
    ):
        order_data = MarketOrderRequest(
            symbol=symbol,
            qty=qty,
            side=side,
            time_in_force=TimeInForce.GTC,
            order_class=OrderClass.BRACKET,
            take_profit=TakeProfitRequest(limit_price=take_profit_price),
            stop_loss=StopLossRequest(stop_price=stop_loss_price),
        )
        logger.info(
            "Bracket %s: %s x %s | TP=%.2f SL=%.2f",
            side.value, symbol, qty, take_profit_price, stop_loss_price,
        )
        return self.trading.submit_order(order_data)

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
            time_in_force=TimeInForce.GTC,
        )
        logger.info("Market %s: %s x %s", side.value, symbol, qty)
        return self.trading.submit_order(order_data)

    def get_open_orders(self, symbol: str | None = None) -> list:
        request = GetOrdersRequest(status=QueryOrderStatus.OPEN)
        orders = self.trading.get_orders(request)
        if symbol:
            orders = [o for o in orders if o.symbol == symbol]
        return orders

    def cancel_order(self, order_id: str):
        logger.info("Cancelling order %s", order_id)
        return self.trading.cancel_order_by_id(order_id)

    def cancel_all_orders(self):
        logger.info("Cancelling all open orders")
        return self.trading.cancel_orders()

    def close_position(self, symbol: str):
        logger.info("Closing position: %s", symbol)
        return self.trading.close_position(symbol)
