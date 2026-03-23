from __future__ import annotations

import pandas as pd


def compute_rsi(df: pd.DataFrame, period: int = 14) -> pd.Series:
    delta = df["close"].diff()
    gain = delta.where(delta > 0, 0.0)
    loss = -delta.where(delta < 0, 0.0)
    avg_gain = gain.ewm(alpha=1 / period, min_periods=period).mean()
    avg_loss = loss.ewm(alpha=1 / period, min_periods=period).mean()
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def compute_macd(
    df: pd.DataFrame,
    fast: int = 12,
    slow: int = 26,
    signal: int = 9,
) -> pd.DataFrame:
    ema_fast = df["close"].ewm(span=fast, adjust=False).mean()
    ema_slow = df["close"].ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    histogram = macd_line - signal_line
    return pd.DataFrame({
        "macd": macd_line,
        "macd_signal": signal_line,
        "macd_histogram": histogram,
    }, index=df.index)


def compute_bollinger(
    df: pd.DataFrame,
    period: int = 20,
    num_std: float = 2.0,
) -> pd.DataFrame:
    sma = df["close"].rolling(window=period).mean()
    std = df["close"].rolling(window=period).std()
    upper = sma + num_std * std
    lower = sma - num_std * std
    percent_b = (df["close"] - lower) / (upper - lower)
    return pd.DataFrame({
        "bb_upper": upper,
        "bb_middle": sma,
        "bb_lower": lower,
        "bb_percent_b": percent_b,
    }, index=df.index)


def compute_all(df: pd.DataFrame) -> pd.DataFrame:
    """Compute all indicators and merge into a single DataFrame."""
    result = df.copy()
    result["rsi"] = compute_rsi(df)
    macd_df = compute_macd(df)
    result = pd.concat([result, macd_df], axis=1)
    bb_df = compute_bollinger(df)
    result = pd.concat([result, bb_df], axis=1)
    result["sma_5"] = df["close"].rolling(window=5).mean()
    result["sma_20"] = df["close"].rolling(window=20).mean()
    result["volume_sma_20"] = df["volume"].rolling(window=20).mean()
    return result
