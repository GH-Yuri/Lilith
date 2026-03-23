from __future__ import annotations

import logging
import time
from decimal import Decimal

from alpaca.trading.enums import OrderSide

from src.alpaca_client import AlpacaClient
from src.config import AlpacaConfig, BotConfig
from src.strategy import MeanReversionStrategy, Signal

logger = logging.getLogger(__name__)


class Lilith:
    """Main trading bot orchestrator."""

    def __init__(
        self,
        alpaca_config: AlpacaConfig,
        bot_config: BotConfig,
    ) -> None:
        self.client = AlpacaClient(alpaca_config)
        self.config = bot_config
        self.strategy = MeanReversionStrategy()

    def _portfolio_value(self) -> Decimal:
        account = self.client.get_account()
        return Decimal(account.portfolio_value)

    def _current_position_qty(self, symbol: str) -> Decimal:
        positions = self.client.get_positions()
        for pos in positions:
            if pos.symbol == symbol:
                return Decimal(pos.qty)
        return Decimal(0)

    def _calculate_order_qty(self, symbol: str) -> Decimal:
        account = self.client.get_account()
        buying_power = Decimal(account.buying_power)
        portfolio_value = Decimal(account.portfolio_value)
        max_spend = portfolio_value * Decimal(str(self.config.max_position_pct))
        available = min(buying_power, max_spend)
        # Rough estimate: 1 share (to be refined with current price)
        return Decimal(1)

    def run_once(self) -> None:
        if not self.client.is_market_open():
            logger.info("Market is closed, skipping cycle")
            return

        account = self.client.get_account()
        logger.info(
            "Portfolio: $%s | Buying power: $%s",
            account.portfolio_value,
            account.buying_power,
        )

        for symbol in self.config.symbols:
            try:
                signal = self.strategy.evaluate(symbol, self.client)

                if signal == Signal.BUY:
                    qty = self._calculate_order_qty(symbol)
                    if qty > 0:
                        self.client.submit_market_order(symbol, qty, OrderSide.BUY)

                elif signal == Signal.SELL:
                    held = self._current_position_qty(symbol)
                    if held > 0:
                        self.client.submit_market_order(symbol, held, OrderSide.SELL)

            except Exception:
                logger.exception("Error processing %s", symbol)

    def run(self) -> None:
        logger.info(
            "Lilith starting | symbols=%s | interval=%ds",
            self.config.symbols,
            self.config.check_interval_seconds,
        )

        while True:
            try:
                self.run_once()
            except Exception:
                logger.exception("Unhandled error in main loop")

            logger.info(
                "Sleeping %d seconds...", self.config.check_interval_seconds
            )
            time.sleep(self.config.check_interval_seconds)
