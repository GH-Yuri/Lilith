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
    """AI-powered autonomous Bitcoin trader — daily long-only strategy
    with analysis window and deadline."""

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

        self._decision_made_date: str | None = None
        self._last_ai_call: datetime | None = None

    # ── Data Collection ───────────────────────────────────────

    def _collect_data(self) -> dict:
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

    # ── AI Analysis ───────────────────────────────────────────

    def _run_analysis(self, *, is_deadline: bool = False) -> bool:
        """Run one AI analysis cycle.

        Returns True if a BUY was placed.
        """
        symbol = self.config.symbol
        label = "DEADLINE" if is_deadline else "pre-deadline"
        logger.info("=" * 60)
        logger.info("Lilith %s analysis | %s", label, symbol)

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
            is_deadline=is_deadline,
            deadline_hour_utc=self.config.daily_deadline_hour_utc,
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

        self._last_ai_call = datetime.now(UTC)

        bought = any(
            a.get("type", "").upper() == "OPEN_POSITION" for a in actions
        )
        return bought

    # ── Position Management ───────────────────────────────────

    def _has_open_position(self) -> bool:
        position = self.client.get_position(self.config.symbol)
        return position is not None

    def _check_and_force_close(self) -> bool:
        """Force-close if position exceeds max hold time. Returns True if closed."""
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

    # ── Analysis Window Logic ─────────────────────────────────

    def _ai_cooldown_ok(self) -> bool:
        """True if enough time has passed since the last AI call."""
        if self._last_ai_call is None:
            return True
        elapsed = (datetime.now(UTC) - self._last_ai_call).total_seconds()
        return elapsed >= self.config.analysis_cooldown_minutes * 60

    def _is_deadline_hour(self) -> bool:
        return datetime.now(UTC).hour == self.config.daily_deadline_hour_utc

    def _is_past_deadline(self) -> bool:
        return datetime.now(UTC).hour > self.config.daily_deadline_hour_utc

    def _mark_decision_done(self) -> None:
        self._decision_made_date = datetime.now(UTC).strftime("%Y-%m-%d")

    def _decision_done_today(self) -> bool:
        return self._decision_made_date == datetime.now(UTC).strftime("%Y-%m-%d")

    # ── Main Loop ─────────────────────────────────────────────

    def run(self) -> None:
        logger.info(
            "Lilith v4 starting | symbol=%s | deadline %02d:00 UTC "
            "| max hold %dh | AI cooldown %d min | check every %ds",
            self.config.symbol,
            self.config.daily_deadline_hour_utc,
            self.config.max_hold_hours,
            self.config.analysis_cooldown_minutes,
            self.config.check_interval_seconds,
        )

        while True:
            try:
                self._tick()
            except Exception:
                logger.exception("Unhandled error in main loop")

            time.sleep(self.config.check_interval_seconds)

    def _tick(self) -> None:
        """Single iteration of the main loop."""
        now = datetime.now(UTC)

        # Phase A: position is open → monitor expiry
        if self._has_open_position():
            self._check_and_force_close()
            return

        # Phase B: no position, already decided today → wait for tomorrow
        if self._decision_done_today():
            if self._is_past_deadline():
                logger.info(
                    "Today's decision done | waiting for tomorrow "
                    "(deadline %02d:00 UTC)",
                    self.config.daily_deadline_hour_utc,
                )
            return

        # Phase C: deadline hour → mandatory final analysis
        if self._is_deadline_hour():
            logger.info("DEADLINE reached — running mandatory analysis")
            bought = self._run_analysis(is_deadline=True)
            self._mark_decision_done()
            if bought:
                logger.info("Deadline decision: BUY placed")
            else:
                logger.info("Deadline decision: HOLD — no trade today")
            return

        # Phase D: past deadline but no decision recorded (bot restarted mid-day)
        if self._is_past_deadline():
            logger.info(
                "Past deadline, no decision on record — marking today as done"
            )
            self._mark_decision_done()
            return

        # Phase E: before deadline → pre-deadline analysis window
        if self._ai_cooldown_ok():
            logger.info(
                "Pre-deadline analysis window | now %02d:%02d UTC | "
                "deadline %02d:00 UTC",
                now.hour, now.minute,
                self.config.daily_deadline_hour_utc,
            )
            bought = self._run_analysis(is_deadline=False)
            if bought:
                logger.info("Early BUY placed — decision done for today")
                self._mark_decision_done()
        else:
            cooldown_left = self.config.analysis_cooldown_minutes * 60
            if self._last_ai_call:
                elapsed = (now - self._last_ai_call).total_seconds()
                cooldown_left = max(0, cooldown_left - elapsed)
            logger.info(
                "AI cooldown | next analysis in ~%.0f min",
                cooldown_left / 60,
            )
