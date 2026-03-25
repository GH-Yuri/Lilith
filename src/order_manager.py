from __future__ import annotations

import logging
from decimal import Decimal

from alpaca.trading.enums import OrderSide

from src.alpaca_client import AlpacaClient
from src.memory import TradeLogger

logger = logging.getLogger(__name__)


class OrderManager:
    """Translates AI actions into Alpaca API calls (long-only)."""

    def __init__(self, client: AlpacaClient, trade_logger: TradeLogger) -> None:
        self.client = client
        self.trade_logger = trade_logger

    def execute_actions(
        self,
        actions: list[dict],
        symbol: str,
        market_assessment: str = "neutral",
    ) -> None:
        for action in actions:
            action_type = action.get("type", "HOLD").upper()
            reasoning = action.get("reasoning", "No reasoning provided")

            try:
                if action_type == "OPEN_POSITION":
                    self._open_position(action, symbol, reasoning, market_assessment)
                elif action_type == "HOLD":
                    logger.info("HOLD: %s", reasoning)
                    self.trade_logger.log_action(
                        action_type="HOLD",
                        symbol=symbol,
                        reasoning=reasoning,
                        market_assessment=market_assessment,
                    )
                else:
                    logger.warning("Unknown action type: %s", action_type)
            except Exception:
                logger.exception("Failed to execute action: %s", action_type)

    def _open_position(
        self,
        action: dict,
        symbol: str,
        reasoning: str,
        market_assessment: str,
    ) -> None:
        qty = Decimal(str(action.get("qty", "0.001")))
        take_profit = float(action.get("take_profit", 0))
        stop_loss = float(action.get("stop_loss", 0))

        if take_profit <= 0 or stop_loss <= 0:
            logger.error("Invalid TP/SL prices: TP=%s SL=%s", take_profit, stop_loss)
            return

        existing = self.client.get_position(symbol)
        if existing:
            logger.info("Already have a position in %s, skipping OPEN", symbol)
            return

        order = self.client.submit_bracket_order(
            symbol=symbol,
            qty=qty,
            side=OrderSide.BUY,
            take_profit_price=take_profit,
            stop_loss_price=stop_loss,
        )

        self.trade_logger.log_action(
            action_type="OPEN_BUY",
            symbol=symbol,
            reasoning=reasoning,
            qty=str(qty),
            price=str(getattr(order, "filled_avg_price", "pending")),
            take_profit=take_profit,
            stop_loss=stop_loss,
            market_assessment=market_assessment,
        )

    def force_close_position(self, symbol: str) -> None:
        """Auto-close a position after the max hold time has elapsed."""
        position = self.client.get_position(symbol)
        if not position:
            logger.info("No position in %s to force-close", symbol)
            return

        open_orders = self.client.get_open_orders(symbol)
        for order in open_orders:
            self.client.cancel_order(str(order.id))

        self.client.close_position(symbol)

        self.trade_logger.log_action(
            action_type="FORCE_CLOSE_18H",
            symbol=symbol,
            reasoning="Position automatically closed after max hold time (18h)",
            qty=str(position.qty),
            price=str(position.current_price),
        )
        logger.info(
            "Force-closed %s | qty=%s | P&L=%s",
            symbol, position.qty, position.unrealized_pl,
        )
