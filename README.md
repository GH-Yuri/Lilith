# Lilith - AI-Powered Autonomous Bitcoin Trader

An autonomous BTC/USD trading bot powered by AI (GPT-4o, Grok, Claude - swappable), using [Alpaca Markets](https://alpaca.markets) for execution and deployed as a [Render](https://render.com) Background Worker.

## How It Works

Every 5 minutes, Lilith:

1. **Collects data** from Alpaca: BTC/USD price bars, live quotes, news, account state
2. **Computes indicators**: RSI, MACD, Bollinger Bands, SMAs, volume analysis
3. **Loads memory**: previous trade log and self-written notes
4. **Asks AI** to analyze everything and decide on an action
5. **Executes orders**: Bracket orders with Take-Profit and Stop-Loss
6. **Saves memory**: logs the trade and AI notes for the next cycle

## Architecture

```
src/
  config.py          Environment-based configuration (Alpaca + AI + Bot)
  alpaca_client.py   Alpaca SDK wrapper (crypto trading, bracket orders, news)
  indicators.py      Technical indicators (RSI, MACD, Bollinger Bands)
  ai_client.py       OpenAI-compatible AI client (works with GPT, Grok, Claude)
  prompt_builder.py  Prompt engineering (system prompt + context builder)
  order_manager.py   Translates AI decisions into Alpaca orders
  memory.py          Trade log + AI notes persistence (JSON files)
  bot.py             Main orchestrator loop
data/
  trade_log.json     Trade history with reasoning (created at runtime)
  ai_notes.json      AI's notes to itself (created at runtime)
```

## Quick Start

### 1. Prerequisites

- Python 3.12+
- [Alpaca account](https://app.alpaca.markets) (paper trading)
- AI API key (OpenAI, Grok/xAI, or Anthropic/Claude)

### 2. Local Development

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env
# Edit .env with your Alpaca + AI API keys

python main.py
```

### 3. Deploy to Render

1. Push this repo to GitHub
2. Go to [Render Dashboard](https://dashboard.render.com)
3. Click **New > Blueprint** and connect this repo
4. Set secret env vars: `ALPACA_API_KEY`, `ALPACA_API_SECRET`, `AI_API_KEY`

## Configuration

| Variable | Default | Description |
|---|---|---|
| `ALPACA_API_KEY` | *required* | Alpaca API key |
| `ALPACA_API_SECRET` | *required* | Alpaca API secret |
| `ALPACA_PAPER` | `true` | Use paper trading |
| `AI_API_KEY` | *required* | AI provider API key |
| `AI_BASE_URL` | `https://api.openai.com/v1` | AI API endpoint |
| `AI_MODEL` | `gpt-4o-mini` | AI model name |
| `AI_TEMPERATURE` | `0.3` | AI response randomness (0-1) |
| `TRADE_SYMBOL` | `BTC/USD` | Trading pair |
| `ANALYSIS_INTERVAL_SECONDS` | `300` | Seconds between AI analyses |

## Switching AI Models

Change `AI_BASE_URL` and `AI_MODEL` to switch providers:

| Provider | `AI_BASE_URL` | `AI_MODEL` |
|---|---|---|
| OpenAI | `https://api.openai.com/v1` | `gpt-4o-mini`, `gpt-4o` |
| Grok (xAI) | `https://api.x.ai/v1` | `grok-3` |
| Claude | `https://api.anthropic.com/v1` | `claude-sonnet-4-20250514` |
| DeepSeek | `https://api.deepseek.com/v1` | `deepseek-chat` |

## Disclaimer

This bot is for educational and experimental purposes. Trading involves risk. This is a paper trading proof-of-concept.

## License

MIT
