from __future__ import annotations

import logging
from decimal import Decimal

from alpaca.trading.enums import OrderSide

from src.alpaca_client import AlpacaClient
from src.memory import TradeLogger

logger = logging.getLogger(__name__)


class OrderManager:
    """Translates AI actions into Alpaca API calls."""

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
                elif action_type == "CLOSE_POSITION":
                    self._close_position(symbol, reasoning, market_assessment)
                elif action_type == "UPDATE_STOP_LOSS":
                    self._update_stop_loss(action, symbol, reasoning, market_assessment)
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
        side_str = action.get("side", "buy").lower()
        side = OrderSide.BUY if side_str == "buy" else OrderSide.SELL
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
            side=side,
            take_profit_price=take_profit,
            stop_loss_price=stop_loss,
        )

        self.trade_logger.log_action(
            action_type=f"OPEN_{side_str.upper()}",
            symbol=symbol,
            reasoning=reasoning,
            qty=str(qty),
            price=str(getattr(order, "filled_avg_price", "pending")),
            take_profit=take_profit,
            stop_loss=stop_loss,
            market_assessment=market_assessment,
        )

    def _close_position(
        self,
        symbol: str,
        reasoning: str,
        market_assessment: str,
    ) -> None:
        position = self.client.get_position(symbol)
        if not position:
            logger.info("No position in %s to close", symbol)
            return

        # Cancel associated TP/SL orders first
        open_orders = self.client.get_open_orders(symbol)
        for order in open_orders:
            self.client.cancel_order(str(order.id))

        self.client.close_position(symbol)

        self.trade_logger.log_action(
            action_type="CLOSE",
            symbol=symbol,
            reasoning=reasoning,
            qty=str(position.qty),
            price=str(position.current_price),
            market_assessment=market_assessment,
        )

    def _update_stop_loss(
        self,
        action: dict,
        symbol: str,
        reasoning: str,
        market_assessment: str,
    ) -> None:
        new_stop = float(action.get("stop_loss", 0))
        if new_stop <= 0:
            logger.error("Invalid new stop-loss price: %s", new_stop)
            return

        position = self.client.get_position(symbol)
        if not position:
            logger.info("No position to update stop-loss for %s", symbol)
            return

        # Find and cancel existing stop-loss order, then create a new one
        open_orders = self.client.get_open_orders(symbol)
        for order in open_orders:
            if order.stop_price is not None:
                self.client.cancel_order(str(order.id))
                logger.info("Cancelled old stop-loss order %s", order.id)

        # Submit a new stop-loss order
        from alpaca.trading.requests import StopOrderRequest
        from alpaca.trading.enums import TimeInForce

        side = OrderSide.SELL if float(position.qty) > 0 else OrderSide.BUY
        stop_order = StopOrderRequest(
            symbol=symbol,
            qty=abs(Decimal(str(position.qty))),
            side=side,
            stop_price=new_stop,
            time_in_force=TimeInForce.GTC,
        )
        self.client.trading.submit_order(stop_order)

        self.trade_logger.log_action(
            action_type="UPDATE_SL",
            symbol=symbol,
            reasoning=reasoning,
            stop_loss=new_stop,
            market_assessment=market_assessment,
        )
