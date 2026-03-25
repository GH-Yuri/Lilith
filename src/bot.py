from __future__ import annotations

import logging
import time
from datetime import UTC, datetime, timedelta

from alpaca.data.timeframe import TimeFrame

from src.ai_client import AIClient
from src.alpaca_client import AlpacaClient
from src.config import AIConfig, AlpacaConfig, BotConfig
from src.indicators import compute_all
from src.memory import NotesManager, TradeLogger
from src.order_manager import OrderManager
from src.prompt_builder import (
    SYSTEM_PROMPT,
    build_context,
    format_account,
    format_bars_summary,
    format_indicators_summary,
    format_orders,
    format_positions,
    format_quote,
)

logger = logging.getLogger(__name__)


class Lilith:
    """AI-powered autonomous Bitcoin trader — daily long-only strategy."""

    def __init__(
        self,
        alpaca_config: AlpacaConfig,
        ai_config: AIConfig,
        bot_config: BotConfig,
    ) -> None:
        self.client = AlpacaClient(alpaca_config)
        self.ai = AIClient(ai_config)
        self.config = bot_config

        self.trade_logger = TradeLogger(bot_config.data_dir)
        self.notes_manager = NotesManager(bot_config.data_dir)
        self.order_manager = OrderManager(self.client, self.trade_logger)

        self._last_analysis_date: str | None = None

    def _collect_data(self) -> dict:
        """Gather all data needed for the AI analysis."""
        symbol = self.config.symbol

        account = self.client.get_account()
        positions = self.client.get_positions()
        btc_positions = [p for p in positions if p.symbol == symbol]
        open_orders = self.client.get_open_orders(symbol)

        end = datetime.now(UTC)
        start = end - timedelta(days=60)
        try:
            bars_raw = self.client.get_crypto_bars(symbol, TimeFrame.Day, start, end)
            bars_df = bars_raw.df
            if hasattr(bars_df.index, "droplevel") and bars_df.index.nlevels > 1:
                bars_df = bars_df.droplevel(0)
        except Exception:
            logger.exception("Failed to fetch crypto bars")
            bars_df = None

        indicators_df = None
        if bars_df is not None and len(bars_df) >= 20:
            try:
                indicators_df = compute_all(bars_df)
            except Exception:
                logger.exception("Failed to compute indicators")

        try:
            quote = self.client.get_crypto_quote(symbol)
        except Exception:
            logger.warning("Failed to fetch quote")
            quote = None

        try:
            news = self.client.get_news(symbol, limit=10)
        except Exception:
            logger.warning("Failed to fetch news")
            news = []

        trade_log = self.trade_logger.get_recent(50)
        notes = self.notes_manager.load()

        return {
            "account": format_account(account),
            "positions": format_positions(btc_positions),
            "open_orders": format_orders(open_orders),
            "bars_df": indicators_df if indicators_df is not None else bars_df,
            "quote": format_quote(quote),
            "news": news,
            "trade_log": trade_log,
            "notes": notes,
        }

    def _run_analysis(self) -> None:
        """Single daily analysis + execution cycle."""
        symbol = self.config.symbol
        logger.info("=" * 60)
        logger.info("Lilith DAILY analysis | %s", symbol)

        data = self._collect_data()

        user_prompt = build_context(
            account=data["account"],
            positions=data["positions"],
            open_orders=data["open_orders"],
            bars_summary=format_bars_summary(data["bars_df"]),
            indicators_summary=format_indicators_summary(data["bars_df"]),
            quote=data["quote"],
            news=data["news"],
            trade_log=data["trade_log"],
            notes=data["notes"],
        )

        logger.info("Sending data to AI for analysis...")
        response = self.ai.analyze(SYSTEM_PROMPT, user_prompt)

        market = response.get("market_assessment", "neutral")
        actions = response.get("actions", [])
        notes = response.get("notes", "")

        logger.info("AI assessment: %s | Actions: %d", market, len(actions))
        for a in actions:
            logger.info("  -> %s: %s", a.get("type", "?"), a.get("reasoning", "")[:100])

        self.order_manager.execute_actions(actions, symbol, market)

        if notes:
            self.notes_manager.save(notes, market)

    def _has_open_position(self) -> bool:
        """Check if there is an open BTC position on Alpaca."""
        position = self.client.get_position(self.config.symbol)
        return position is not None

    def _check_and_force_close(self) -> bool:
        """If the open position exceeds max_hold_hours, force-close it.

        Returns True if a force-close happened.
        """
        open_time = self.trade_logger.get_last_open_time(self.config.symbol)
        if open_time is None:
            logger.warning("Position exists but no OPEN_BUY in trade log — force-closing")
            self.order_manager.force_close_position(self.config.symbol)
            return True

        now = datetime.now(UTC)
        if open_time.tzinfo is None:
            open_time = open_time.replace(tzinfo=UTC)

        held_hours = (now - open_time).total_seconds() / 3600
        remaining = self.config.max_hold_hours - held_hours

        if held_hours >= self.config.max_hold_hours:
            logger.info(
                "Position held for %.1fh (max %dh) — force-closing",
                held_hours, self.config.max_hold_hours,
            )
            self.order_manager.force_close_position(self.config.symbol)
            return True

        logger.info(
            "Position open for %.1fh | %.1fh remaining until auto-close",
            held_hours, remaining,
        )
        return False

    def _is_analysis_time(self) -> bool:
        """Check if it's the configured daily analysis hour and we haven't
        already run an analysis today."""
        now = datetime.now(UTC)
        today = now.strftime("%Y-%m-%d")

        if self._last_analysis_date == today:
            return False

        target_hour = self.config.daily_analysis_hour_utc
        return now.hour == target_hour

    def run(self) -> None:
        """Main loop — monitors every 5 min, analyzes once per day."""
        logger.info(
            "Lilith v3 starting | symbol=%s | daily analysis at %02d:00 UTC "
            "| max hold %dh | check interval %ds",
            self.config.symbol,
            self.config.daily_analysis_hour_utc,
            self.config.max_hold_hours,
            self.config.analysis_interval_seconds,
        )

        while True:
            try:
                if self._has_open_position():
                    self._check_and_force_close()
                elif self._is_analysis_time():
                    self._run_analysis()
                    self._last_analysis_date = datetime.now(UTC).strftime("%Y-%m-%d")
                else:
                    now = datetime.now(UTC)
                    logger.info(
                        "No position | next analysis at %02d:00 UTC (now %02d:%02d UTC)",
                        self.config.daily_analysis_hour_utc,
                        now.hour, now.minute,
                    )
            except Exception:
                logger.exception("Unhandled error in main loop")

            time.sleep(self.config.analysis_interval_seconds)
