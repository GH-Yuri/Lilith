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
class BotConfig:
    symbols: list[str]
    check_interval_seconds: int
    max_position_pct: float  # max % of portfolio per position

    @classmethod
    def from_env(cls) -> "BotConfig":
        symbols_raw = os.getenv("TRADE_SYMBOLS", "AAPL,MSFT,GOOGL")
        return cls(
            symbols=[s.strip() for s in symbols_raw.split(",")],
            check_interval_seconds=int(os.getenv("CHECK_INTERVAL_SECONDS", "60")),
            max_position_pct=float(os.getenv("MAX_POSITION_PCT", "0.05")),
        )
