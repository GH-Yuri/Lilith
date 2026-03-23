# Lilith - AI Trading Bot

Automated trading bot powered by [Alpaca Markets](https://alpaca.markets), designed to run as a [Render](https://render.com) Background Worker.

## Architecture

```
main.py              Entry point
src/
  config.py          Environment-based configuration
  alpaca_client.py   Alpaca SDK wrapper (trading + market data)
  strategy.py        Trading strategies (mean-reversion SMA crossover)
  bot.py             Orchestrator loop
```

## Quick Start

### 1. Prerequisites

- Python 3.12+
- [Alpaca account](https://app.alpaca.markets) (paper trading recommended for testing)

### 2. Local Development

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env
# Edit .env with your Alpaca API keys

python main.py
```

### 3. Deploy to Render

1. Push this repo to GitHub
2. Go to [Render Dashboard](https://dashboard.render.com)
3. Click **New > Blueprint** and connect this repo
4. Render reads `render.yaml` and creates a Background Worker
5. Set `ALPACA_API_KEY` and `ALPACA_API_SECRET` in the Render environment

## Configuration

| Variable | Default | Description |
|---|---|---|
| `ALPACA_API_KEY` | *required* | Alpaca API key |
| `ALPACA_API_SECRET` | *required* | Alpaca API secret |
| `ALPACA_PAPER` | `true` | Use paper trading |
| `TRADE_SYMBOLS` | `AAPL,MSFT,GOOGL` | Comma-separated stock symbols |
| `CHECK_INTERVAL_SECONDS` | `60` | Seconds between strategy evaluations |
| `MAX_POSITION_PCT` | `0.05` | Max portfolio % per position |

## Strategy

Currently uses a **mean-reversion SMA crossover**:

- Computes a short (5-day) and long (20-day) simple moving average
- **BUY** when short SMA drops below long SMA by >2%
- **SELL** when short SMA rises above long SMA by >2%
- **HOLD** otherwise

## Disclaimer

This bot is for educational purposes. Trading involves risk. Always test with paper trading before using real money.

## License

MIT
