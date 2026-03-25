from __future__ import annotations

import json
from datetime import UTC, datetime


SYSTEM_PROMPT = """You are Lilith, an autonomous Bitcoin trader managing a paper trading portfolio on Alpaca Markets.

You make ONE decision per day: Will BTC/USD go UP in the next hours, or not?

## Your Trading Model
- You are called once per day at a fixed time.
- If you believe BTC will rise: BUY (go long).
- If you are not confident BTC will rise: HOLD (do nothing).
- You can ONLY go long. Short selling is not available for crypto on Alpaca.
- Your position will be AUTOMATICALLY closed after 18 hours if still open.
- Alpaca's bracket orders handle your take-profit and stop-loss automatically.

## Your Trading Philosophy
- Only buy when you see a clear edge that BTC will rise in the next hours.
- The best decision is often HOLD. Only trade with high conviction.
- Always use asymmetric risk/reward: take-profit distance >= 2x stop-loss distance.
- Consider the 18h time limit when setting targets — be realistic about how far BTC can move.
- Pay attention to volume — unusual volume often precedes price moves.
- News sentiment can move Bitcoin faster than technicals.

## Bitcoin-Specific Knowledge
- Bitcoin trades 24/7 — consider session dynamics (Asia, Europe, US).
- Bitcoin correlates with risk assets (Nasdaq, S&P500) but can decouple.
- Large volume spikes may indicate whale activity.
- Weekend volatility can differ significantly from weekday patterns.
- Halving cycles, ETF flows, and regulatory news are major catalysts.

## Rules
- You MUST respond with valid JSON matching the schema below.
- Your action MUST include a "reasoning" field explaining your logic.
- For OPEN_POSITION: you MUST specify qty, take_profit, and stop_loss prices.
- take_profit distance from entry should be >= 2x stop_loss distance from entry.
- You can only have ONE open BTC/USD position at a time.
- When uncertain, choose HOLD. Missing a move is better than a bad entry.

## JSON Response Schema
{
  "actions": [
    {
      "type": "OPEN_POSITION | HOLD",
      "qty": 0.001,
      "take_profit": 95000.00,
      "stop_loss": 88000.00,
      "reasoning": "Explanation of your decision"
    }
  ],
  "notes": "Your notes for the next day. Write down observations, levels to watch, pending catalysts, patterns you noticed, etc.",
  "market_assessment": "bullish | bearish | neutral"
}

For HOLD actions, only "type" and "reasoning" are required.
For OPEN_POSITION, include "type", "qty", "take_profit", "stop_loss", and "reasoning".
"""


def build_context(
    account: dict,
    positions: list[dict],
    open_orders: list[dict],
    bars_summary: str,
    indicators_summary: str,
    quote: dict | None,
    news: list[dict],
    trade_log: list[dict],
    notes: str,
) -> str:
    """Build the user prompt with all current market context."""
    now = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")

    sections = [f"## Current Time\n{now}"]

    # Account
    sections.append(
        f"## Account\n"
        f"- Portfolio Value: ${account.get('portfolio_value', 'N/A')}\n"
        f"- Cash: ${account.get('cash', 'N/A')}\n"
        f"- Buying Power: ${account.get('buying_power', 'N/A')}"
    )

    # Current Position
    if positions:
        pos_lines = []
        for p in positions:
            pos_lines.append(
                f"- {p['symbol']}: qty={p['qty']}, entry={p['avg_entry_price']}, "
                f"current={p['current_price']}, unrealized_pl={p['unrealized_pl']}"
            )
        sections.append("## Current Position\n" + "\n".join(pos_lines))
    else:
        sections.append("## Current Position\nNo open position.")

    # Open Orders (TP/SL)
    if open_orders:
        order_lines = []
        for o in open_orders:
            order_lines.append(
                f"- {o['type']} {o['side']} {o['symbol']}: "
                f"limit={o.get('limit_price', 'N/A')}, stop={o.get('stop_price', 'N/A')}"
            )
        sections.append("## Open Orders (TP/SL)\n" + "\n".join(order_lines))
    else:
        sections.append("## Open Orders\nNone.")

    # Live Quote
    if quote:
        sections.append(
            f"## Live Quote (BTC/USD)\n"
            f"- Bid: ${quote.get('bid', 'N/A')}\n"
            f"- Ask: ${quote.get('ask', 'N/A')}\n"
            f"- Spread: ${quote.get('spread', 'N/A')}"
        )

    # Price Bars + Indicators
    sections.append(f"## Price History (Daily Bars with Indicators)\n{bars_summary}")
    sections.append(f"## Latest Indicator Values\n{indicators_summary}")

    # News
    if news:
        news_lines = []
        for n in news[:7]:
            news_lines.append(
                f"- [{n.get('created_at', '')}] {n.get('headline', 'N/A')} "
                f"(source: {n.get('source', 'N/A')})"
            )
            if n.get("summary"):
                news_lines.append(f"  Summary: {n['summary'][:200]}")
        sections.append("## Recent News\n" + "\n".join(news_lines))
    else:
        sections.append("## Recent News\nNo recent news available.")

    # Trade Log
    if trade_log:
        log_lines = []
        for entry in trade_log[-20:]:
            log_lines.append(
                f"- [{entry.get('timestamp', '')}] {entry.get('action', '')} | "
                f"{entry.get('reasoning', '')}"
            )
        sections.append("## Your Recent Trading Log\n" + "\n".join(log_lines))
    else:
        sections.append("## Your Recent Trading Log\nNo previous trades.")

    # AI Notes from previous cycle
    if notes:
        sections.append(f"## Your Notes from Previous Analysis\n{notes}")
    else:
        sections.append("## Your Notes from Previous Analysis\nNo previous notes.")

    sections.append(
        "## Your Task\n"
        "Analyze all the data above. Decide your action and respond with valid JSON."
    )

    return "\n\n".join(sections)


def format_account(account) -> dict:
    return {
        "portfolio_value": str(account.portfolio_value),
        "cash": str(account.cash),
        "buying_power": str(account.buying_power),
    }


def format_positions(positions: list) -> list[dict]:
    result = []
    for p in positions:
        result.append({
            "symbol": p.symbol,
            "qty": str(p.qty),
            "avg_entry_price": str(p.avg_entry_price),
            "current_price": str(p.current_price),
            "unrealized_pl": str(p.unrealized_pl),
            "market_value": str(p.market_value),
        })
    return result


def format_orders(orders: list) -> list[dict]:
    result = []
    for o in orders:
        result.append({
            "id": str(o.id),
            "type": str(o.order_type),
            "side": str(o.side),
            "symbol": o.symbol,
            "qty": str(o.qty),
            "limit_price": str(o.limit_price) if o.limit_price else None,
            "stop_price": str(o.stop_price) if o.stop_price else None,
            "status": str(o.status),
        })
    return result


def format_quote(quote) -> dict | None:
    if not quote:
        return None
    bid = float(quote.bid_price) if quote.bid_price else 0
    ask = float(quote.ask_price) if quote.ask_price else 0
    return {
        "bid": f"{bid:.2f}",
        "ask": f"{ask:.2f}",
        "spread": f"{ask - bid:.2f}",
    }


def format_bars_summary(df) -> str:
    if df is None or df.empty:
        return "No bar data available."
    cols = ["open", "high", "low", "close", "volume", "vwap",
            "rsi", "macd", "macd_signal", "macd_histogram",
            "bb_upper", "bb_middle", "bb_lower", "bb_percent_b",
            "sma_5", "sma_20"]
    available = [c for c in cols if c in df.columns]
    tail = df[available].tail(10)
    return tail.to_string()


def format_indicators_summary(df) -> str:
    if df is None or df.empty:
        return "No indicator data available."
    latest = df.iloc[-1]
    lines = []
    indicator_cols = {
        "rsi": "RSI(14)",
        "macd": "MACD",
        "macd_signal": "MACD Signal",
        "macd_histogram": "MACD Histogram",
        "bb_upper": "Bollinger Upper",
        "bb_middle": "Bollinger Middle (SMA20)",
        "bb_lower": "Bollinger Lower",
        "bb_percent_b": "Bollinger %B",
        "sma_5": "SMA(5)",
        "sma_20": "SMA(20)",
        "volume_sma_20": "Volume SMA(20)",
    }
    for col, label in indicator_cols.items():
        if col in latest.index and not latest.isna()[col]:
            val = latest[col]
            lines.append(f"- {label}: {val:.2f}")
    if "close" in latest.index:
        lines.insert(0, f"- Current Close: {latest['close']:.2f}")
    if "volume" in latest.index:
        lines.append(f"- Current Volume: {latest['volume']:.0f}")
    return "\n".join(lines) if lines else "No indicator data available."
