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
    """AI-powered autonomous Bitcoin trader."""

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

    def run_once(self) -> None:
        """Single analysis + execution cycle."""
        symbol = self.config.symbol
        logger.info("=" * 60)
        logger.info("Lilith analysis cycle | %s", symbol)

        # 1. Collect all data
        data = self._collect_data()

        # 2. Build prompt
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

        # 3. Ask AI
        logger.info("Sending data to AI for analysis...")
        response = self.ai.analyze(SYSTEM_PROMPT, user_prompt)

        market = response.get("market_assessment", "neutral")
        actions = response.get("actions", [])
        notes = response.get("notes", "")

        logger.info("AI assessment: %s | Actions: %d", market, len(actions))
        for a in actions:
            logger.info("  -> %s: %s", a.get("type", "?"), a.get("reasoning", "")[:100])

        # 4. Execute actions
        self.order_manager.execute_actions(actions, symbol, market)

        # 5. Save notes
        if notes:
            self.notes_manager.save(notes, market)

    def run(self) -> None:
        """Main loop - runs forever with configured interval."""
        logger.info(
            "Lilith v2 starting | symbol=%s | interval=%ds | AI=%s",
            self.config.symbol,
            self.config.analysis_interval_seconds,
            self.ai.config.model,
        )

        while True:
            try:
                self.run_once()
            except Exception:
                logger.exception("Unhandled error in main loop")

            logger.info(
                "Next analysis in %d seconds...",
                self.config.analysis_interval_seconds,
            )
            time.sleep(self.config.analysis_interval_seconds)
