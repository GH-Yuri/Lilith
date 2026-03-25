import os
from dataclasses import dataclass


@dataclass(frozen=True)
class AlpacaConfig:
    api_key: str
    api_secret: str
    base_url: str
    paper: bool

    @classmethod
    def from_env(cls) -> "AlpacaConfig":
        paper = os.getenv("ALPACA_PAPER", "true").lower() == "true"
        base_url = os.getenv(
            "ALPACA_BASE_URL",
            "https://paper-api.alpaca.markets" if paper else "https://api.alpaca.markets",
        )
        return cls(
            api_key=os.environ["ALPACA_API_KEY"],
            api_secret=os.environ["ALPACA_API_SECRET"],
            base_url=base_url,
            paper=paper,
        )


@dataclass(frozen=True)
class AIConfig:
    model: str
    base_url: str
    api_key: str
    temperature: float

    @classmethod
    def from_env(cls) -> "AIConfig":
        return cls(
            model=os.getenv("AI_MODEL", "gpt-4o-mini"),
            base_url=os.getenv("AI_BASE_URL", "https://api.openai.com/v1"),
            api_key=os.environ["AI_API_KEY"],
            temperature=float(os.getenv("AI_TEMPERATURE", "0.3")),
        )


@dataclass(frozen=True)
class BotConfig:
    symbol: str
    analysis_interval_seconds: int
    data_dir: str
    max_hold_hours: int
    daily_analysis_hour_utc: int

    @classmethod
    def from_env(cls) -> "BotConfig":
        return cls(
            symbol=os.getenv("TRADE_SYMBOL", "BTC/USD"),
            analysis_interval_seconds=int(os.getenv("ANALYSIS_INTERVAL_SECONDS", "300")),
            data_dir=os.getenv("DATA_DIR", "data"),
            max_hold_hours=int(os.getenv("MAX_HOLD_HOURS", "18")),
            daily_analysis_hour_utc=int(os.getenv("DAILY_ANALYSIS_HOUR_UTC", "8")),
        )
