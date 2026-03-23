from __future__ import annotations

import json
import logging
import os
from datetime import UTC, datetime

logger = logging.getLogger(__name__)


class TradeLogger:
    """Append-only trade log stored as a JSON file."""

    def __init__(self, data_dir: str) -> None:
        self.path = os.path.join(data_dir, "trade_log.json")
        os.makedirs(data_dir, exist_ok=True)

    def _load_all(self) -> list[dict]:
        if not os.path.exists(self.path):
            return []
        try:
            with open(self.path, "r") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            logger.warning("Corrupted trade log, starting fresh")
            return []

    def _save(self, entries: list[dict]) -> None:
        with open(self.path, "w") as f:
            json.dump(entries, f, indent=2, default=str)

    def log_action(
        self,
        action_type: str,
        symbol: str,
        reasoning: str,
        qty: str | None = None,
        price: str | None = None,
        take_profit: float | None = None,
        stop_loss: float | None = None,
        market_assessment: str = "neutral",
    ) -> None:
        entries = self._load_all()
        entry = {
            "timestamp": datetime.now(UTC).isoformat(),
            "action": action_type,
            "symbol": symbol,
            "reasoning": reasoning,
            "market_assessment": market_assessment,
        }
        if qty:
            entry["qty"] = qty
        if price:
            entry["price"] = price
        if take_profit:
            entry["take_profit"] = take_profit
        if stop_loss:
            entry["stop_loss"] = stop_loss

        entries.append(entry)

        # Keep only last 200 entries to prevent unbounded growth
        if len(entries) > 200:
            entries = entries[-200:]

        self._save(entries)
        logger.info("Logged: %s %s - %s", action_type, symbol, reasoning[:80])

    def get_recent(self, n: int = 50) -> list[dict]:
        entries = self._load_all()
        return entries[-n:]


class NotesManager:
    """Simple key-value store for AI notes between cycles."""

    def __init__(self, data_dir: str) -> None:
        self.path = os.path.join(data_dir, "ai_notes.json")
        os.makedirs(data_dir, exist_ok=True)

    def save(self, notes: str, market_assessment: str = "neutral") -> None:
        data = {
            "updated_at": datetime.now(UTC).isoformat(),
            "notes": notes,
            "market_assessment": market_assessment,
        }
        with open(self.path, "w") as f:
            json.dump(data, f, indent=2)

    def load(self) -> str:
        if not os.path.exists(self.path):
            return ""
        try:
            with open(self.path, "r") as f:
                data = json.load(f)
                return data.get("notes", "")
        except (json.JSONDecodeError, IOError):
            return ""
