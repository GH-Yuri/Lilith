"""Explore what data Alpaca provides us."""

from dotenv import load_dotenv

load_dotenv()

from alpaca.trading.client import TradingClient
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.historical.news import NewsClient
from alpaca.data.requests import (
    NewsRequest,
    StockBarsRequest,
    StockLatestQuoteRequest,
    StockSnapshotRequest,
)
from alpaca.data.timeframe import TimeFrame
from alpaca.common.enums import BaseURL
from datetime import datetime, timedelta

from src.config import AlpacaConfig

c = AlpacaConfig.from_env()
tc = TradingClient(api_key=c.api_key, secret_key=c.api_secret, paper=True)
dc = StockHistoricalDataClient(
    api_key=c.api_key,
    secret_key=c.api_secret,
)
nc = NewsClient(api_key=c.api_key, secret_key=c.api_secret)

# --- 1. ACCOUNT ---
print("=" * 60)
print("1. ACCOUNT INFO")
print("=" * 60)
acc = tc.get_account()
fields = [
    "id", "status", "currency", "buying_power", "portfolio_value",
    "cash", "equity", "last_equity", "long_market_value",
    "short_market_value", "initial_margin", "maintenance_margin",
    "daytrade_count", "daytrading_buying_power", "pattern_day_trader",
    "trading_blocked", "account_blocked",
]
for attr in fields:
    val = getattr(acc, attr, "n/a")
    print(f"  {attr}: {val}")

# --- 2. CLOCK & CALENDAR ---
print()
print("=" * 60)
print("2. MARKET CLOCK")
print("=" * 60)
clock = tc.get_clock()
print(f"  Markt offen: {clock.is_open}")
print(f"  Naechste Oeffnung: {clock.next_open}")
print(f"  Naechste Schliessung: {clock.next_close}")

# --- 3. POSITIONEN ---
print()
print("=" * 60)
print("3. OFFENE POSITIONEN")
print("=" * 60)
positions = tc.get_all_positions()
if not positions:
    print("  Keine offenen Positionen")
else:
    for p in positions:
        print(f"  {p.symbol}: qty={p.qty}, avg_entry={p.avg_entry_price}, "
              f"current={p.current_price}, unrealized_pl={p.unrealized_pl}")

# --- 4. HISTORISCHE BARS (IEX Feed) ---
print()
print("=" * 60)
print("4. HISTORISCHE BARS (AAPL, letzte 10 Tage, IEX Feed)")
print("=" * 60)
try:
    req = StockBarsRequest(
        symbol_or_symbols="AAPL",
        timeframe=TimeFrame.Day,
        start=datetime.now() - timedelta(days=14),
        end=datetime.now() - timedelta(days=1),
    )
    bars = dc.get_stock_bars(req)
    df = bars.df
    print(f"  Verfuegbare Spalten: {list(df.columns)}")
    print(df.to_string())
except Exception as e:
    print(f"  Fehler: {e}")

# --- 5. LATEST QUOTE ---
print()
print("=" * 60)
print("5. LATEST QUOTE (AAPL)")
print("=" * 60)
try:
    quote = dc.get_stock_latest_quote(
        StockLatestQuoteRequest(symbol_or_symbols="AAPL")
    )
    for sym, q in quote.items():
        print(f"  {sym}: ask={q.ask_price} x {q.ask_size}, "
              f"bid={q.bid_price} x {q.bid_size}, "
              f"timestamp={q.timestamp}")
except Exception as e:
    print(f"  Fehler: {e}")

# --- 6. SNAPSHOT ---
print()
print("=" * 60)
print("6. SNAPSHOT (AAPL)")
print("=" * 60)
try:
    snap = dc.get_stock_snapshot(
        StockSnapshotRequest(symbol_or_symbols="AAPL")
    )
    for sym, s in snap.items():
        print(f"  {sym}:")
        print(f"    Latest Trade: price={s.latest_trade.price}, size={s.latest_trade.size}")
        print(f"    Latest Quote: ask={s.latest_quote.ask_price}, bid={s.latest_quote.bid_price}")
        print(f"    Daily Bar: O={s.daily_bar.open} H={s.daily_bar.high} "
              f"L={s.daily_bar.low} C={s.daily_bar.close} V={s.daily_bar.volume}")
        if s.previous_daily_bar:
            print(f"    Prev Day: O={s.previous_daily_bar.open} "
                  f"C={s.previous_daily_bar.close} V={s.previous_daily_bar.volume}")
except Exception as e:
    print(f"  Fehler: {e}")

# --- 7. NEWS ---
print()
print("=" * 60)
print("7. NEWS (AAPL, letzte 5 Artikel)")
print("=" * 60)
try:
    req = NewsRequest(symbols="AAPL", limit=5)
    news = nc.get_news(req)
    for article in news:
        print(f"  [{article.created_at}] {article.headline}")
        print(f"    Source: {article.source}")
        print(f"    Symbols: {article.symbols}")
        summary = article.summary[:150] if article.summary else "n/a"
        print(f"    Summary: {summary}...")
        print()
except Exception as e:
    print(f"  Fehler: {e}")

# --- 8. ASSETS (verfuegbare Instrumente) ---
print()
print("=" * 60)
print("8. HANDELBARE ASSETS (erste 10)")
print("=" * 60)
assets = tc.get_all_assets()
tradeable = [a for a in assets if a.tradable and a.status == "active"]
print(f"  Total handelbare Assets: {len(tradeable)}")
crypto = [a for a in tradeable if a.asset_class == "crypto"]
stocks = [a for a in tradeable if a.asset_class == "us_equity"]
print(f"    - US Aktien: {len(stocks)}")
print(f"    - Crypto: {len(crypto)}")
print()
print("  Beispiel Aktien:")
for a in stocks[:5]:
    print(f"    {a.symbol}: {a.name} (exchange={a.exchange}, "
          f"shortable={a.shortable}, fractionable={a.fractionable})")
print()
print("  Beispiel Crypto:")
for a in crypto[:5]:
    print(f"    {a.symbol}: {a.name}")
