# TradeAllN

A stock-only paper-trading platform with **real market prices and real news**, where every price move is explained and you can trade and automate in plain English. Money is virtual; prices are not.

**Stack:** Django 5 · DRF · Channels (WebSockets) · Celery · PostgreSQL · Redis · React 18 + TypeScript · Vite · Tailwind · TradingView lightweight-charts · Claude API · Docker

## Quick start (Docker)

```bash
cp .env.example .env          # optional: add ANTHROPIC_API_KEY for the AI features
docker compose up --build     # or: make up
```

Open **http://localhost:5180** and sign in with `demo@tradeall.app` / `demo-trader-2026`.

The first start migrates the database and loads **real data** (about 2 minutes): company profiles, 2 years of daily bars, 60 days of 5-minute bars and 7 days of 1-minute bars from Yahoo Finance, plus several thousand real headlines, SEC filings and earnings results. It also creates a demo portfolio (bought at real historical prices), a watchlist, automations and leaderboard bots.

## What you can trade

**Every US-listed stock and ETF**, about 11,600 tickers, synced daily from Nasdaq Trader's official symbol directory (NYSE, Nasdaq, NYSE American, NYSE Arca, Cboe). That's the same universe Robinhood offers. Search by ticker or company name with `⌘K`. About 180 popular tickers are preloaded; any other ticker loads its real history, profile and news the first time you open it (a couple of seconds). Live price tracking follows what you hold, watch, view or have orders on.

Broker-style features:
- **Fractional shares and dollar-based orders** ("buy $25 of NVDA"), market/limit/stop/stop-limit, DAY/GTC
- **Extended-hours trading:** limit orders can fill pre-market (4:00–9:30 ET) and after hours (16:00–20:00 ET); pre/after-hours prices shown under the quote
- **Recurring investments** (daily/weekly/biweekly/monthly auto-invest with fractional shares)
- **Real dividends** credited to your cash for shares held before the ex-date
- **Stock page:** real logo, analyst ratings and price targets, EPS history (beat/miss), CEO/employees/HQ, fundamentals, dividends, "people also own"
- **Discover:** real top gainers/losers/most active across the whole market, curated lists (Magnificent 7, AI & chips, popular ETFs, dividends, crypto-linked…), and what traders here hold

## Real data sources

| Data | Source | Key needed? |
|---|---|---|
| Prices: quotes, minute/daily bars, history | Yahoo Finance (`yfinance`), refreshed every 15 s while the market is open | No |
| Company profile: sector, market cap, P/E, beta, description | Yahoo Finance | No |
| Earnings: EPS vs estimate, surprise, upcoming dates | Yahoo Finance | No |
| Company and market headlines | Yahoo Finance RSS, Google News RSS (including date-range searches for old moves) | No |
| Filings: 8-K, 10-Q, 10-K, Form 4 | SEC EDGAR (set `SEC_USER_AGENT` to your name and email) | No |
| Full ticker list | Nasdaq Trader symbol directory | No |
| Analyst ratings, price targets, dividends, market movers | Yahoo Finance | No |
| Company logos | Parqet / Financial Modeling Prep logo images (proxied and cached by the backend) | No |
| Real-time trade ticks + more news | Finnhub WebSocket/REST: set `FINNHUB_API_KEY` | Free key |
| News archive back to 2015 | Alpaca news API: set `ALPACA_API_KEY`/`ALPACA_API_SECRET` | Free key |

The app follows **real NYSE hours and holidays**. Outside them, quotes show the last session (like any broker), the live 1-second chart pauses, and orders are queued and fill from the opening bell. DAY orders expire at the close. Yahoo prices can be delayed by up to ~15 minutes for some exchanges; add a Finnhub key for real-time prints.

Want the offline simulator instead (24/7 market, generated prices and news)? Set `MARKET_DATA_PROVIDER=mock`. Switching between real and simulated data rebuilds the database automatically on the next start.

| Service | What it does |
|---|---|
| `backend` | Django API + WebSockets (Daphne) on :8010. Migrates and seeds on start |
| `ingestor` | Live loop: prices → Redis → WebSocket → order matching → automations → live "why it moved" |
| `worker`, `beat` | Celery: end-of-day snapshots, DAY-order expiry, nightly explanations, rule expiry |
| `frontend` | Vite dev server on :5180 (proxies `/api` and `/ws`) |
| `db`, `redis` | Postgres 16 on host port 5435, Redis 7 on host port 6381 |

Production-style build (nginx serving the built SPA, no exposed infra ports): `make prod` → http://localhost:8080.

## Features

- **Real market data**: real prices, real company fundamentals, real news, filings and earnings, refreshed live during market hours, with an opening/closing countdown.
- **Why did it move?** Every chart, from the 1-second live view to 2 years, is split into up, down and flat moves. Each move is compared against SPY and its sector ETF, then attributed to news, filings, earnings or macro releases published *before* the move (no lookahead). Click any part of the chart, read the "Story", or drag across any range to explain it. With an API key, "Deeper AI analysis" has Claude write the explanation using structured output, and it may only cite the provided news IDs.
- **Natural-language trading.** Press `⌘K` / `Ctrl+K` and type "buy $500 of apple", "sell half my nvidia", "buy 5 msft at 400 gtc", "cancel my tsla orders", or, with AI, "close all my tech positions". The model only produces an intent. Deterministic code works out symbols and quantities, the engine validates, and **you confirm** a preview before anything executes.
- **Natural-language automations.** "if NVDA drops 5% today buy $2000", "alert me when AAPL goes above 240", "when MSFT's 50-day crosses above its 200-day, buy 10". These compile to a safe JSON rule AST validated by Pydantic. You see a readable "When → Then" preview and a 1-year "would have triggered" backtest. A deterministic engine evaluates rules every second (edge-triggered, idempotent, with size limits and a kill switch). No AI runs when a rule fires.
- **Ask your portfolio.** Chat that answers "why is my portfolio down today?" from your holdings plus move explanations. It uses read-only tools and can't trade.
- **Trading engine.** Market, limit, stop and stop-limit orders with DAY/GTC, cash and share reservations, slippage, an append-only cash ledger, row-level locking (no double-spend), and idempotent `client_order_id`s.
- **Pro UI.** Live ticker tape, flashing prices, a live equity number, candles or area charts with move markers, heatmap, sector bars, catalyst calendar, leaderboard, and dark/light themes.

Without `ANTHROPIC_API_KEY` everything still works. The instant parser handles common order and rule shapes, explanations use the rules engine, and portfolio Q&A answers common questions.

## Configuration

All settings come from `.env` (see `.env.example`). The key ones:

| Variable | Default | Notes |
|---|---|---|
| `MARKET_DATA_PROVIDER` | `yahoo` | `yahoo` (real, no key), `finnhub`/`alpaca` (with keys), or `mock` (offline simulator) |
| `QUOTE_POLL_SECONDS` | `15` | How often Yahoo is polled during market hours |
| `EXTRA_SYMBOLS` | — | More tickers to track, e.g. `PLTR,UBER,SHOP`. Run `make reseed` after changing |
| `FINNHUB_API_KEY` | — | Real-time ticks over WebSocket + extra news |
| `SEC_USER_AGENT` | placeholder | Put your name and email here; SEC requires it |
| `NEWS_POLL_MINUTES` | `5` | How often news is refreshed |
| `ANTHROPIC_API_KEY` | — | Enables the Claude-powered features |
| `LLM_MODEL` | `claude-opus-5-5` | |
| `AI_DAILY_REQUESTS_PER_USER` | `100` | Cost guardrail |
| `STARTING_CASH` | `100000.00` | |
| `MAX_RULE_ORDER_VALUE` | `25000` | Per-trigger cap for automations |

Keep comments on their own lines in `.env`. Inline `# comments` become part of the value.

## Development without Docker for the app

```bash
make dev-infra       # Postgres + Redis in Docker
make dev-backend     # terminal 1: migrate, seed, API on :8010
make dev-ingestor    # terminal 2: live prices
make dev-frontend    # terminal 3: http://localhost:5180
```

Tests: `make test` (in Docker) or `cd backend && .venv/bin/pytest` (31 tests: engine incl. fractional and extended hours, market hours, concurrency, recurring investments, rules, parser, news, explanations). Lint: `ruff check .`. Frontend type-check: `npm run typecheck`.

## Project layout

```
backend/apps/
  accounts/   email login, JWT access token + httpOnly refresh cookie
  market/     stocks, bars, Redis quotes, hours, simulator (sim.py), providers/, ingestor + seed commands
  news/       news items, filings and the catalyst calendar
  trading/    accounts, orders, fills, positions, ledger, engine.py
  portfolio/  summary, equity history, analytics, snapshots
  explain/    move detection (detection.py) and attribution (service.py)
  rules/      rule AST (spec.py), NL compiler, evaluator and backtest
  assistant/  Claude client (llm.py), intent parser, preview/confirm, Ask
  social/     leaderboard
  realtime/   WebSocket consumer, JWT middleware, push helpers
frontend/src/
  pages/      Dashboard, Stock, Markets, Portfolio, Orders, Rules, Leaderboard, Settings, Login
  components/ chart/, explain/, rules/, trading/, layout/, CommandPalette, AskPanel, ui/
```

See [PLAN.md](PLAN.md) for the full product plan and roadmap.

> Paper trading with virtual money. Market data comes from Yahoo Finance and other free sources for personal, non-commercial use and may be delayed. Nothing here is investment advice.
