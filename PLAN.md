# TradeAllN — Stock Trading App: Project Plan

A modern, real-time **stock-only** trading platform. Users sign up, get a funded
paper-trading account, watch live prices, place orders, track their portfolio, and
compete on a leaderboard. The architecture leaves room to plug in a real broker later.

**Stack:** Django + Django REST Framework (Python) · React (TypeScript, Vite) ·
PostgreSQL · Redis · `.env`-based configuration · Docker Compose

---

## 1. Product scope

### 1.1 Guiding decisions

| Decision | Choice | Why |
|---|---|---|
| Real money vs. simulated | **Paper trading first** | Real-money brokerage requires broker-dealer registration (SEC/FINRA in the US) or a licensed partner. Simulated trading lets us ship everything else now. |
| Asset classes | **US equities and ETFs only** | Keeps the data model, market hours and order rules simple. No crypto, options, forex or futures. |
| Market data source | **Alpaca Market Data API** (primary), Finnhub as fallback | Alpaca has a free tier, WebSocket streaming, and a paper-trading API we can switch to later. |
| Execution | **In-house simulated matching engine** behind a `Broker` interface | Swap in `AlpacaBroker` later without touching the rest of the app. |

### 1.2 Feature roadmap

**MVP (v1): core trading**
- Sign up, log in, email verification, password reset
- Each new user gets a paper account with $100,000 virtual cash
- Stock search by ticker or company name
- Stock detail page: live price, candlestick chart (1D/1W/1M/1Y/5Y), key stats, company profile
- Orders: **market, limit, stop, stop-limit**; time-in-force **DAY** and **GTC**
- Order book view: open, filled, cancelled and rejected orders, with cancel
- Portfolio: holdings, average cost, market value, unrealized and realized P&L, cash, buying power
- Transaction history
- Watchlists (several per user)
- Live price updates over WebSockets
- Market hours awareness (open, closed, pre-market, holidays)

**v2: the "cool" layer**
- Price alerts (above/below, % move) via in-app toast, email and web push
- Portfolio analytics: equity curve, daily returns, Sharpe ratio, max drawdown, sector allocation donut, benchmark vs. SPY
- Stock screener: filter by sector, market cap, P/E, volume, % change, 52-week high/low
- News feed per ticker and per portfolio, with a sentiment badge
- **Leaderboard and competitions**: weekly and monthly leagues, private leagues with invite codes
- Achievements and badges ("First Trade", "Diamond Hands: held 30 days", "Beat SPY this month")
- Command palette (`Ctrl/Cmd+K`) for quick ticker jump and quick order entry
- Dark and light themes

**v2.5: the AI layer (signature features, detailed in §9)**
- **"Why did it move?"**: for any past window on any timeframe (second, minute, hour, day, week), the chart explains why the price went up, went down or stayed flat, linked to the news, filings or market events behind it
- **Natural-language trading**: "buy $500 of Apple", "sell half my Tesla", "close everything in tech"
- **Natural-language conditional rules**: "if NVDA drops 5% today and RSI is under 30, buy 10 shares", "when AAPL earnings come out, sell half if it gaps down more than 3%"
- **Ask your portfolio**: "what was my worst trade this month and why?", "how exposed am I to semiconductors?"

**v3: power features**
- Strategy backtester (SMA crossover, RSI and similar) on historical bars
- Recurring buys (dollar-cost averaging)
- Fractional shares
- Technical indicators on the chart (SMA, EMA, RSI, MACD, Bollinger Bands)
- Pluggable live broker (Alpaca live) behind a feature flag and KYC flow
- Mobile app (React Native, reusing the API)

### 1.3 More proposed features

Each of these is plausible with the data the app already collects.

| Feature | What it does |
|---|---|
| **Time Machine** | Scrub the chart back to any date and replay the market at 1×–1000× speed with that day's news popping up as it happened. Paper-trade the replay ("could you have survived March 2020?") and score yourself against what actually happened. |
| **Catalyst Calendar** | Upcoming earnings, dividends, splits, Fed meetings and CPI releases for your holdings and watchlist, with the stock's average historical move on similar events ("AAPL has moved ±4.1% on average after the last 8 earnings reports"). |
| **Earnings Prediction Game** | Before earnings, users predict up or down and by how much. Points for accuracy, with its own leaderboard. |
| **Trade Journal + AI Coach** | Each trade can carry a note ("why I bought"). Weekly, the coach reviews your trades for patterns: "You sell winners after +3% on average but hold losers to −11%." |
| **What-If Simulator** | "What if I'd bought $1,000 of NVDA every month since 2020?" or "What if I hadn't sold MSFT in June?" Shows the counterfactual equity curve next to your real one. |
| **Copy-a-Portfolio** | Follow top leaderboard players' public paper portfolios, get notified of their trades, optionally mirror them with a size cap. |
| **Sentiment Heatmap** | Treemap of the S&P 500 sized by market cap and colored by price change, with a toggle to color by news sentiment instead. Spots "price up, news negative" divergences. |
| **Unusual Activity Radar** | Flags stocks trading at 3×+ normal volume or making outsized moves, each with an auto-generated "why" (from §9.1). |
| **Risk X-Ray** | Portfolio beta, concentration warnings, correlation matrix between holdings, worst-case day estimate (historical VaR), and "your 3 tech stocks move together, so you're less diversified than you think." |
| **Rebalance Assistant** | Set target weights ("40% ETFs, 30% tech, 30% other"); it proposes the trades to get there, shown as a confirmable order basket. |
| **Bracket and OCO orders** | Buy with an attached take-profit and stop-loss; one-cancels-other pairs. |
| **Voice trading** | Hold the mic button and speak a natural-language order (browser speech-to-text → same NL pipeline as §9.2, same confirmation step). |
| **Daily Briefing** | Morning email or push before the open: what moved your holdings overnight and why, today's catalysts, rule status. End-of-day recap after the close. |
| **Learn Mode** | Hover any term (P/E, stop-limit, beta) for a plain-English explanation; beginner tooltips on the order ticket; short lessons that unlock achievements. |

---

## 2. System architecture

```
                ┌───────────────────────────┐
                │   React SPA (Vite + TS)   │
                │  REST (axios/TanStack Q)  │
                │  WebSocket (live prices)  │
                └──────────┬────────────────┘
                           │ HTTPS / WSS
                    ┌──────▼──────┐
                    │    Nginx    │  static files, TLS, reverse proxy
                    └──┬───────┬──┘
             REST /api │       │ /ws
                ┌──────▼───┐ ┌─▼──────────────┐
                │ Django   │ │ Django Channels│
                │ + DRF    │ │ (Daphne/Uvicorn│
                │ (Gunicorn│ │  ASGI)         │
                │ /Uvicorn)│ └─┬──────────────┘
                └──┬───┬───┘   │ channel layer
                   │   │       │
        ┌──────────▼┐ ┌▼───────▼──────┐     ┌─────────────────────┐
        │PostgreSQL │ │     Redis     │◄────┤ Market data ingestor│◄── Alpaca WS
        │ (source   │ │ cache, pub/sub│     │ (long-running proc) │
        │  of truth)│ │ Celery broker │     └─────────────────────┘
        └─────▲─────┘ └──────▲────────┘
              │              │
        ┌─────┴──────────────┴─────┐
        │ Celery workers + Beat    │  order matching, alerts, EOD snapshots,
        │                          │  leaderboard, emails, data backfill
        └──────────────────────────┘
```

**Price flow:** the ingestor subscribes to the provider's WebSocket for tracked
symbols → writes the latest quote to Redis (`quote:AAPL`) → publishes to a Channels
group `ticker.AAPL` → browsers subscribed to that group get the update. The
matching engine listens to the same ticks to trigger limit and stop orders.

---

## 3. Tech stack details

### Backend
| Concern | Library |
|---|---|
| Framework | Django 5.x, Python 3.12+ |
| REST API | Django REST Framework |
| Auth | `djangorestframework-simplejwt` (access token in memory, refresh token in an httpOnly cookie) |
| Realtime | Django Channels + `channels-redis` |
| Background jobs | Celery + Celery Beat (Redis broker) |
| Config / env | `django-environ` (reads `.env`) |
| DB driver | `psycopg` (v3) |
| API docs | `drf-spectacular` (OpenAPI + Swagger UI) |
| Filtering | `django-filter` |
| CORS | `django-cors-headers` |
| Rate limiting | DRF throttling + `django-ratelimit` on auth endpoints |
| Market calendar | `exchange_calendars` (NYSE holidays and half days) |
| Data provider SDK | `alpaca-py`, `httpx` |
| LLM | `anthropic` Python SDK (Claude API): tool use, structured outputs, prompt caching, Message Batches |
| Text search on news | Postgres full-text search + `pgvector` for semantic news matching |
| Indicators | `pandas` + `pandas-ta` (RSI, MACD, SMA, ATR for rules and move detection) |
| Testing | `pytest`, `pytest-django`, `factory_boy`, `freezegun`, `responses` |
| Lint / format | `ruff`, `black`, `mypy` + `django-stubs` |

### Frontend
| Concern | Library |
|---|---|
| Build | Vite + React 18 + TypeScript |
| Routing | React Router |
| Server state | TanStack Query |
| Client state | Zustand (auth session, UI, live quotes cache) |
| Styling | Tailwind CSS + shadcn/ui components |
| Charts | TradingView **lightweight-charts** (candles), Recharts (portfolio/analytics) |
| Forms | React Hook Form + Zod |
| Realtime | Native WebSocket with a small reconnecting wrapper |
| Animations | Framer Motion (price flash green/red, toasts) |
| Testing | Vitest + React Testing Library, Playwright (E2E) |

### Infrastructure
- Docker Compose for local dev: `db`, `redis`, `backend`, `asgi`, `worker`, `beat`, `ingestor`, `frontend`
- GitHub Actions CI: lint, type-check, tests, build images
- Deploy: a single VPS with Docker Compose for v1; Render, Railway or AWS ECS + RDS + ElastiCache later
- Monitoring: Sentry (frontend and backend), structured JSON logs, `/healthz` endpoint

---

## 4. Repository layout

```
TradeAllN/
├── .env.example               # committed template, never real secrets
├── .env                       # local only, gitignored
├── docker-compose.yml
├── docker-compose.prod.yml
├── Makefile                   # make up, make migrate, make test, make seed
├── PLAN.md
├── backend/
│   ├── Dockerfile
│   ├── pyproject.toml
│   ├── manage.py
│   ├── config/
│   │   ├── settings/
│   │   │   ├── base.py        # reads env via django-environ
│   │   │   ├── dev.py
│   │   │   ├── test.py
│   │   │   └── prod.py
│   │   ├── urls.py
│   │   ├── asgi.py            # HTTP + WebSocket routing
│   │   ├── wsgi.py
│   │   └── celery.py
│   └── apps/
│       ├── accounts/          # custom User, profile, auth endpoints
│       ├── market/            # Stock, PriceBar, quotes, search, providers/
│       ├── trading/           # Account, Order, Trade, Position, matching engine, brokers/
│       ├── portfolio/         # snapshots, analytics, performance
│       ├── watchlists/
│       ├── alerts/
│       ├── social/            # leaderboard, leagues, achievements
│       ├── news/              # ingestion, dedupe, entity tagging, embeddings
│       ├── explain/           # move detection, news attribution ("why did it move?")
│       ├── assistant/         # NL parsing (Claude), command confirmation, chat
│       ├── rules/             # conditional rules: AST, evaluator, triggers
│       └── realtime/          # Channels consumers, routing
└── frontend/
    ├── Dockerfile
    ├── package.json
    ├── vite.config.ts
    ├── .env.example           # VITE_API_URL, VITE_WS_URL
    └── src/
        ├── api/               # axios client, typed endpoint functions
        ├── hooks/             # useQuote, usePortfolio, useOrders...
        ├── stores/            # zustand stores
        ├── components/        # ui/, charts/, trading/, layout/
        ├── pages/             # Dashboard, Stock, Portfolio, Orders, Watchlists,
        │                      # Screener, Leaderboard, Settings, Auth
        ├── lib/               # ws client, formatters (money, %), market hours
        └── types/             # generated from OpenAPI (openapi-typescript)
```

---

## 5. Environment configuration (`.env`)

All configuration comes from environment variables, read by `django-environ` on the
backend and `import.meta.env` (with the `VITE_` prefix) on the frontend. Commit
`.env.example`; never commit `.env`.

```dotenv
# ---------- Django ----------
DJANGO_SETTINGS_MODULE=config.settings.dev
DJANGO_SECRET_KEY=change-me
DJANGO_DEBUG=True
DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1
CORS_ALLOWED_ORIGINS=http://localhost:5173
CSRF_TRUSTED_ORIGINS=http://localhost:5173

# ---------- PostgreSQL ----------
POSTGRES_DB=tradeall
POSTGRES_USER=tradeall
POSTGRES_PASSWORD=tradeall
POSTGRES_HOST=db
POSTGRES_PORT=5432
DATABASE_URL=postgres://tradeall:tradeall@db:5432/tradeall

# ---------- Redis / Celery ----------
REDIS_URL=redis://redis:6379/0
CELERY_BROKER_URL=redis://redis:6379/1
CHANNEL_LAYER_URL=redis://redis:6379/2

# ---------- Auth ----------
JWT_ACCESS_LIFETIME_MIN=15
JWT_REFRESH_LIFETIME_DAYS=7

# ---------- Market data ----------
MARKET_DATA_PROVIDER=alpaca          # alpaca | finnhub | mock
ALPACA_API_KEY=
ALPACA_API_SECRET=
ALPACA_DATA_FEED=iex                 # iex (free) | sip (paid)
FINNHUB_API_KEY=

# ---------- Trading ----------
BROKER_BACKEND=simulated             # simulated | alpaca_paper | alpaca_live
STARTING_CASH=100000.00
SIMULATED_SLIPPAGE_BPS=5
COMMISSION_PER_TRADE=0.00

# ---------- AI ----------
ANTHROPIC_API_KEY=
LLM_MODEL=claude-opus-5-5
LLM_EFFORT=medium                    # low | medium | high
AI_FEATURES_ENABLED=True
AI_DAILY_REQUESTS_PER_USER=100       # cost guardrail
NEWS_PROVIDERS=alpaca,finnhub        # comma-separated
SEC_EDGAR_USER_AGENT=TradeAllN admin@example.com

# ---------- Rules ----------
MAX_ACTIVE_RULES_PER_USER=25
RULE_ACTION_REQUIRES_CONFIRMATION=False   # True = rules only notify, never auto-trade

# ---------- Email ----------
EMAIL_BACKEND=django.core.mail.backends.console.EmailBackend
EMAIL_HOST=
EMAIL_PORT=587
EMAIL_HOST_USER=
EMAIL_HOST_PASSWORD=
DEFAULT_FROM_EMAIL=TradeAllN <no-reply@tradeall.local>

# ---------- Observability ----------
SENTRY_DSN=
LOG_LEVEL=INFO
```

Frontend `frontend/.env`:
```dotenv
VITE_API_URL=http://localhost:8000/api/v1
VITE_WS_URL=ws://localhost:8000/ws
```

`MARKET_DATA_PROVIDER=mock` runs a random-walk price generator, so the whole app
works offline and in CI without API keys.

---

## 6. Data model (PostgreSQL)

Money and prices use `NumericField` (`DecimalField(max_digits=18, decimal_places=4)`),
never floats. Quantities are `DecimalField(max_digits=18, decimal_places=6)` so
fractional shares work later.

```
User (custom, AbstractUser)
 ├─ email (unique, login field), display_name, avatar, timezone, is_verified

Stock
 ├─ symbol (unique, indexed), name, exchange (NYSE/NASDAQ/AMEX), sector, industry
 ├─ market_cap, logo_url, description, is_active, is_tradable, is_etf
 └─ search_vector (GIN index, Postgres full-text search on symbol + name)

PriceBar                         # historical OHLCV
 ├─ stock FK, timeframe (1m/5m/1h/1d), ts, open, high, low, close, volume
 └─ unique(stock, timeframe, ts); index (stock, timeframe, ts DESC)
    (partition by month, or use the TimescaleDB extension, if volume grows)

TradingAccount                   # one per user in v1, more later (competitions)
 ├─ user FK, name, type (paper/live), cash_balance, reserved_cash
 ├─ starting_cash, created_at
 └─ buying_power = cash_balance - reserved_cash (for open buy orders)

Position
 ├─ account FK, stock FK, quantity, avg_cost, realized_pnl, reserved_qty
 └─ unique(account, stock)

Order
 ├─ id (UUID), account FK, stock FK, side (buy/sell)
 ├─ type (market/limit/stop/stop_limit), time_in_force (day/gtc)
 ├─ quantity, limit_price, stop_price, filled_qty, avg_fill_price
 ├─ status (pending/open/partially_filled/filled/cancelled/rejected/expired)
 ├─ reject_reason, client_order_id (idempotency, unique per account)
 ├─ created_at, updated_at, filled_at, expires_at
 └─ index (status, stock) for the matching engine

Trade (Fill)
 ├─ order FK, account FK, stock FK, side, quantity, price, commission, executed_at

LedgerEntry                      # append-only audit trail of every cash movement
 ├─ account FK, type (deposit/trade_buy/trade_sell/commission/reset)
 ├─ amount (+/-), balance_after, reference (order/trade id), created_at

PortfolioSnapshot                # end-of-day equity for charts and analytics
 ├─ account FK, date, cash, positions_value, total_equity, day_pnl
 └─ unique(account, date)

Watchlist / WatchlistItem
 ├─ user FK, name, position (ordering) / watchlist FK, stock FK, added_at

PriceAlert
 ├─ user FK, stock FK, condition (above/below/pct_change), target_value
 ├─ channels (in_app/email/push), is_active, triggered_at

League / LeagueMember            # competitions
 ├─ name, invite_code, starts_at, ends_at, starting_cash, is_public
 └─ league FK, user FK, account FK (a dedicated paper account per league)

Achievement / UserAchievement
NewsArticle
 ├─ stocks M2M, headline, summary, source, url (unique), published_at (indexed)
 ├─ kind (news/press_release/sec_filing/analyst_rating/macro), sentiment (-1..1)
 ├─ dedupe_hash, embedding (pgvector), importance (0..1)

MarketEvent                      # scheduled/structured catalysts
 ├─ stock FK (nullable for macro), kind (earnings/dividend/split/fomc/cpi/jobs/halt)
 ├─ ts, payload JSON (EPS actual vs estimate, rate decision…)

PriceMove                        # a detected segment worth explaining
 ├─ stock FK, timeframe, start_ts, end_ts, start_price, end_price, pct_change
 ├─ direction (up/down/flat), magnitude_z (move vs. normal volatility)
 ├─ relative_to_market (pct_change − SPY), relative_to_sector
 └─ unique(stock, timeframe, start_ts, end_ts)

MoveExplanation
 ├─ move FK (1:1), summary (1–2 sentences), category (company_news/earnings/
 │    analyst/sector/market_wide/macro/no_clear_catalyst)
 ├─ confidence (low/medium/high), model, created_at
 └─ MoveCitation (explanation FK, article FK or event FK, relevance, rank)

TradingRule                      # natural-language conditional rules
 ├─ user FK, account FK, source_text (what the user typed), name
 ├─ condition JSON (validated AST, see §9.3), action JSON
 ├─ status (draft/active/paused/triggered/expired/error), mode (once/repeat)
 ├─ cooldown_seconds, expires_at, last_evaluated_at, last_triggered_at
 └─ RuleExecution (rule FK, triggered_at, snapshot JSON of inputs, order FK, result)

AssistantCommand                 # audit log of every NL request
 ├─ user FK, input_text, parsed JSON, status (parsed/confirmed/rejected/failed)
 ├─ resulting order/rule FKs, tokens_in, tokens_out, latency_ms, created_at
```

**Invariant:** `cash_balance` always equals the sum of that account's `LedgerEntry`
amounts. A nightly Celery task reconciles this and alerts if it ever drifts.

---

## 7. REST API (`/api/v1`)

| Area | Endpoints |
|---|---|
| Auth | `POST auth/register`, `POST auth/login`, `POST auth/refresh`, `POST auth/logout`, `POST auth/verify-email`, `POST auth/password-reset`, `GET/PATCH auth/me` |
| Market | `GET stocks?search=`, `GET stocks/{symbol}`, `GET stocks/{symbol}/quote`, `GET stocks/{symbol}/bars?timeframe=1d&from=&to=`, `GET market/status`, `GET market/movers` (gainers/losers/most active) |
| Screener | `GET screener?sector=&min_cap=&max_pe=&sort=` |
| Trading | `GET accounts`, `GET accounts/{id}`, `POST orders`, `GET orders?status=`, `GET orders/{id}`, `DELETE orders/{id}` (cancel), `GET trades` |
| Portfolio | `GET portfolio/positions`, `GET portfolio/summary`, `GET portfolio/history?range=1M`, `GET portfolio/analytics`, `POST accounts/{id}/reset` |
| Watchlists | full CRUD on `watchlists` and `watchlists/{id}/items` |
| Alerts | full CRUD on `alerts` |
| Social | `GET leaderboard?period=week`, `leagues` CRUD, `POST leagues/join`, `GET achievements` |
| News | `GET news?symbol=`, `GET news/portfolio` |
| Explain | `GET stocks/{symbol}/moves?timeframe=1h&from=&to=` (detected moves + explanations for chart markers), `GET stocks/{symbol}/explain?start=&end=` (explain any arbitrary window the user selects; cached) |
| Assistant | `POST assistant/parse` (text → structured intent + preview), `POST assistant/confirm/{command_id}` (executes the previewed orders/rule), `POST assistant/ask` (portfolio Q&A, streamed) |
| Rules | full CRUD on `rules`, `POST rules/{id}/pause`, `POST rules/{id}/resume`, `GET rules/{id}/executions`, `POST rules/{id}/backtest` |
| Docs | `GET schema/`, `GET docs/` (Swagger) |

**Example: place an order**
```http
POST /api/v1/orders
{
  "account_id": "…",
  "symbol": "AAPL",
  "side": "buy",
  "type": "limit",
  "quantity": "10",
  "limit_price": "185.50",
  "time_in_force": "gtc",
  "client_order_id": "b7f1…"     // idempotency key generated by the frontend
}
→ 201 { "id": "…", "status": "open", … }
```

### WebSocket channels (`/ws/?token=<jwt>`)
Client → server: `{"action": "subscribe", "symbols": ["AAPL", "MSFT"]}` /
`{"action": "unsubscribe", ...}`

Server → client:
- `{"type": "quote", "symbol": "AAPL", "price": "187.22", "change_pct": "1.12", "ts": …}`
- `{"type": "order_update", "order": {…}}` (private, user group `user.<id>`)
- `{"type": "alert", "alert": {…}}`
- `{"type": "market_status", "status": "open"}`
- `{"type": "move_explained", "symbol": "AAPL", "move": {…}}` (a live move just got an explanation)
- `{"type": "rule_triggered", "rule": {…}, "order": {…}}`

Throttle quote pushes to at most ~4 per second per symbol so the UI stays smooth.

---

## 8. The trading engine (core logic)

### 8.1 Order lifecycle
```
           validate
 submit ──────────────► PENDING ──► OPEN ──► PARTIALLY_FILLED ──► FILLED
   │                       │          │                │
   └─► REJECTED            │          ├──► CANCELLED ◄─┘ (user)
       (insufficient       │          └──► EXPIRED (DAY order at close)
        funds, halted,     └──► FILLED (market order during open hours)
        bad price, etc.)
```

### 8.2 Validation on submit
1. Stock exists, `is_tradable`, and the market is open, or the order is queued for the next open (market orders) / accepted as GTC
2. Quantity > 0; limit/stop prices > 0 and within a sane band (±50% of last price)
3. **Buy:** `quantity × price_estimate × (1 + slippage buffer) + commission ≤ buying_power` → reserve that cash
4. **Sell:** `quantity ≤ position.quantity - position.reserved_qty` → reserve the shares (no short selling in v1)
5. Idempotency: a duplicate `client_order_id` returns the existing order

### 8.3 Execution (`SimulatedBroker`)
- **Market orders:** fill immediately at the latest quote ± `SIMULATED_SLIPPAGE_BPS` (buy at ask-ish, sell at bid-ish).
- **Limit/stop orders:** a Celery worker consumes price ticks from Redis pub/sub. For each tick on symbol `S`, it queries open orders for `S` (indexed) and fills those whose condition is met:
  - Buy limit: `price ≤ limit_price`; sell limit: `price ≥ limit_price`
  - Buy stop: `price ≥ stop_price` → becomes a market order; sell stop: `price ≤ stop_price`
  - Stop-limit: when the stop triggers, it converts to a limit order
- **Expiry:** a Celery Beat job at 16:00 ET expires all DAY orders and releases reservations.

### 8.4 Fill transaction (must be atomic)
```python
with transaction.atomic():
    account = TradingAccount.objects.select_for_update().get(pk=order.account_id)
    position = Position.objects.select_for_update().get_or_create(...)
    order = Order.objects.select_for_update().get(pk=order.pk)
    if order.status not in OPEN_STATES:   # someone cancelled it in the meantime
        return
    # 1. create Trade
    # 2. update Position: qty, avg_cost (buys), realized_pnl (sells)
    # 3. update cash and release the reservation
    # 4. append LedgerEntry rows
    # 5. update Order: filled_qty, avg_fill_price, status
transaction.on_commit(lambda: push_order_update(order))   # WebSocket notify
```
Row-level locks (`select_for_update`) prevent double-spending when a user fires
concurrent orders, and stop a fill racing a cancel.

### 8.5 Broker interface
```python
class Broker(Protocol):
    def submit(self, order: Order) -> None: ...
    def cancel(self, order: Order) -> None: ...
    def sync(self, account: TradingAccount) -> None: ...

# brokers/simulated.py, brokers/alpaca.py — chosen by BROKER_BACKEND
```

---

## 9. AI features

Two principles apply to every feature in this section:
1. **The LLM translates and explains. It never decides or executes.** Orders and rules are always turned into a validated, structured object that deterministic code checks, the user confirms, and the normal trading engine (§8) executes.
2. **Untrusted text never reaches a model that holds trading tools.** News articles are read only by the explanation pipeline, which has no tools that act. The trading assistant never sees news text. A malicious headline therefore can't place an order.

### 9.1 "Why did it move?": explanations for every timeframe

**Goal:** on any chart, at any zoom level (1s, 1m, 5m, 1h, 1d, 1w), every stretch of the price line has a short reason attached: why it went up, why it went down, or why it stayed flat. Each reason cites its sources.

**The key idea: explain moves, not candles.** News doesn't arrive every second, so explaining each candle on its own would produce noise or invented reasons. Instead, the series is cut into **move segments** (runs of meaningful up, down or flat movement). Every candle belongs to exactly one segment, so hovering any candle (even a 1-second one) shows the reason for the segment it sits in.

```
 price
   │            ╭──╮  ③ flat: "consolidated; no new news,
   │      ② ↑  ╭╯  ╰────────╮    volume back to normal"
   │     ╭─────╯             ╰╮
   │ ①   │ "Q3 EPS $1.52 vs   ╰─╮ ④ ↓ "fell with the market after
   │─────╯  $1.39 est; raised   ╰──  hotter-than-expected CPI print
   │ flat   guidance (Reuters,       (SPY −1.4%)"
   │        8-K filing)"
   └──────────────────────────────────────────────────► time
```

**Pipeline**

1. **Collect catalysts** (`news` app, continuously):
   - News headlines from Alpaca News and Finnhub; press releases
   - **SEC EDGAR** filings (8-K, 10-Q/10-K, Form 4 insider trades) from the free EDGAR feeds
   - Analyst upgrades, downgrades and price-target changes
   - Earnings results (actual vs. estimate), dividends, splits, trading halts
   - Macro calendar: CPI, jobs report, FOMC decisions, GDP
   - Each item is tagged to tickers, deduplicated (the same story from 5 sources counts once), embedded with pgvector, and scored for importance

2. **Detect moves** (`explain` app), per symbol and timeframe:
   - Normalize by volatility: the same 1% is huge for a 1-minute KO bar and nothing for a daily TSLA bar. Compute each return as a z-score against the rolling volatility at that timeframe (ATR or standard deviation).
   - Segment with a zigzag-style algorithm (a new segment starts when price reverses more than *k*·σ) or with change-point detection (`ruptures`, PELT). A segment with |z| < 1 is labelled **flat**.

3. **Decompose the move** before involving any LLM:
   - `stock move = β × market (SPY) + sector (e.g. XLK, SMH) + idiosyncratic residual`
   - If the residual is small, the explanation is deterministic and free: *"Moved in line with the market (SPY −1.2%) after the Fed held rates."* Most small moves end here.
   - Only moves with a large stock-specific residual go to attribution.

4. **Find candidate catalysts:** items for this ticker, its sector and macro events, published in `[start − lookback, end]`. The lookback scales with the timeframe:

   | Timeframe | Lookback | Notes |
   |---|---|---|
   | seconds | 2 min | Mostly halts, breaking headlines, and large prints |
   | minutes | 15 min | Breaking news, analyst notes |
   | hours | 2 h | Including pre-market news for the opening hour |
   | day | previous close → close | Includes overnight news and earnings after the bell |
   | week | the week | Summarizes that week's daily explanations |

   Candidates are ranked by time proximity, importance and semantic similarity to the ticker, keeping the top ~10.

   **No lookahead:** only items published **before or during** the move (plus a 60-second grace for feed lag) can explain it.

5. **Attribute with Claude:** send the move statistics plus the candidate list (each item with an ID) and get back a **structured output**:
   ```json
   {
     "summary": "Jumped after Q3 earnings beat estimates and the company raised full-year guidance.",
     "category": "earnings",
     "confidence": "high",
     "citations": [{"item_id": "n_8812", "relevance": "primary"},
                   {"item_id": "f_0291", "relevance": "supporting"}]
   }
   ```
   - The model may cite **only IDs from the list it was given**, and the server rejects any other ID.
   - When nothing fits, it must return `"category": "no_clear_catalyst"`, which the UI shows honestly: *"No clear news. Volume was 0.8× normal; likely ordinary trading flow."*

6. **Keep zoom levels consistent:** a day's explanation is built from its hour explanations, and a week's from its days. Zooming in and out tells one consistent story rather than contradicting itself.

**When explanations are generated**

| Timeframe | Strategy |
|---|---|
| Day / week | Precomputed nightly for all tracked symbols with the **Message Batches API** (asynchronous, half price) |
| Hour | Precomputed nightly for popular and held symbols; on demand for the rest |
| Minute / second | On demand when the user zooms in, cached forever (the past doesn't change) |
| Live | When the ingestor sees a spike (\|z\| > 4 on 1-minute bars), explain it immediately and push a `move_explained` WebSocket event plus a "breaking" toast to holders and watchers |

**UI**
- Small colored dots on the chart at segment boundaries; hovering shows the reason card with source links
- A **"Story of the day"** side panel: a vertical timeline of the day's segments and their reasons
- **Drag-select any range** on the chart → "Explain this range" → `GET stocks/{symbol}/explain?start=&end=`
- Confidence badge, plus the line "Explanations are AI-generated from news timing and may not reflect true causes."

### 9.2 Natural-language trading

Users can type (or say) what they want into a command bar on every page.

| User says | Parsed into |
|---|---|
| "buy 10 apple" | market buy 10 AAPL |
| "buy $500 of microsoft at 410 or better" | limit buy ⌊500 / 410⌋ = 1 MSFT @ 410 (or 1.219 shares once fractional shares ship) |
| "sell half my tesla" | market sell `floor(position × 0.5)` TSLA |
| "close all my tech positions" | basket: market sell every holding with sector = Technology |
| "put a stop loss 8% under all my positions" | basket of stop orders, one per holding |
| "cancel my open nvidia orders" | cancel the matching open orders |
| "move 20% of my cash into SPY and QQQ equally" | basket: two market buys |
| "if amd falls under 140 buy 5" | creates a **rule** (§9.3), not an order |

**Flow**
```
text ─► fast path regex ("buy 10 AAPL")? ──yes──┐
          │ no                                  │
          ▼                                     ▼
   Claude (strict tools) ─► intent JSON ─► resolver ─► validator ─► PREVIEW CARD
                                         (symbols,    (same rules     │ user clicks
                                          quantities,  as §8.2)       │ Confirm
                                          positions)                  ▼
                                                              trading engine (§8)
```

- **Claude's tools:** `place_orders` (a list of orders), `cancel_orders`, `create_rule`, `ask_clarification`, `answer_question`. All are `strict: true` JSON schemas, so the output always matches the schema.
- **The resolver does the math, not the model:** "Apple" → `AAPL` via the Stock search table, "half my position" → an exact quantity from the `Position` row, "$500" → a share count from the live quote.
- **Ambiguity becomes a question, never a guess:** "Alphabet has two share classes: GOOGL (voting) or GOOG?" or "You hold 0 TSLA. Did you mean to buy?"
- **Every action needs confirmation.** The preview card shows each order with its estimated cost and resulting buying power. Baskets of more than one order, or orders over 25% of equity, get an extra warning.
- Every request is logged in `AssistantCommand` for auditing and debugging.
- **Voice:** the browser's Web Speech API turns speech into text, which then goes through the same pipeline and the same confirmation.

### 9.3 Natural-language conditional rules

Users describe automations in plain English. They are compiled into a **rule AST**: a small, safe, JSON-based language that a deterministic engine evaluates. **No LLM runs when a rule is checked.**

**Example:** *"If NVDA drops 5% today and RSI is below 30, buy $2,000 worth — but only once, and only before 3pm"*

```json
{
  "condition": {
    "all": [
      {"metric": "pct_change", "symbol": "NVDA", "window": "since_prev_close", "op": "<=", "value": -5},
      {"metric": "rsi", "symbol": "NVDA", "period": 14, "timeframe": "1d", "op": "<", "value": 30},
      {"metric": "time_of_day", "tz": "America/New_York", "op": "<", "value": "15:00"}
    ]
  },
  "action": {"type": "buy_notional", "symbol": "NVDA", "amount": "2000", "order_type": "market"},
  "mode": "once",
  "expires_at": null
}
```

**Building blocks**

| Kind | Available |
|---|---|
| Price metrics | `price`, `pct_change` (since previous close / open / N minutes / N days), `gap_pct`, `distance_from_52w_high` |
| Indicators | `rsi`, `sma`, `ema`, `macd_signal_cross`, `bollinger_position`, `atr`, `volume_ratio` (vs. 20-day average) |
| Crosses | `crosses_above` / `crosses_below` (e.g. price crosses SMA50, SMA50 crosses SMA200) |
| Portfolio | `position_pnl_pct`, `position_qty`, `cash`, `portfolio_value`, `portfolio_drawdown_pct` |
| Events | `earnings_released` (with `eps_surprise_pct`), `news_sentiment_below`, `analyst_downgrade`, `halt_resumed` |
| Time | `time_of_day`, `day_of_week`, `date_after`, `minutes_after_open` |
| Logic | `all`, `any`, `not`, nesting allowed (max depth 4) |
| Actions | `buy_qty`, `buy_notional`, `sell_qty`, `sell_pct_of_position`, `close_position`, `place_bracket`, `notify`, `pause_rule`, `activate_rule` (chains rules) |

**Creation flow**
1. The user types the rule, and Claude returns the AST through **structured outputs** (`output_config.format` with the rule's JSON schema).
2. The server validates it with Pydantic: known metrics only, sane values, symbols exist, action size within limits.
3. The UI shows it back as **plain-English blocks** that can be edited without retyping:
   `WHEN` NVDA ≤ −5% since prev close `AND` RSI(14, daily) < 30 `AND` before 3:00 PM ET → `THEN` buy $2,000 NVDA at market · `ONCE`
4. **"Would have triggered" preview:** a quick backtest over the last 12 months shows the dates the rule would have fired and the hypothetical result.
5. The user clicks **Activate**.

There is also a visual **rule builder** (dropdowns and blocks) for users who prefer clicking, or for when AI is disabled. Both produce the same AST.

**Evaluation engine (`rules` app)**
- Rules are indexed by the symbols they reference (Redis set `rules:by_symbol:NVDA`). On each tick, only the rules for that symbol are evaluated.
- Indicator values are computed incrementally and cached per symbol and timeframe in Redis, so they aren't recomputed per rule.
- Time conditions are checked by a Celery Beat tick every 15 seconds. Event conditions are driven by the news and event ingestion (an internal event bus over Redis pub/sub).
- **Edge-triggered:** a rule fires when its condition changes from false to true, not on every tick while it stays true. There is also a per-rule `cooldown_seconds`.
- **Idempotent execution:** a `RuleExecution` row is written in the same transaction as the order (unique on rule + trigger window), so a rule never fires twice for the same event.
- Orders from rules go through exactly the same validation as manual orders. If the order is rejected (for example, insufficient cash), the rule moves to `error` and the user is notified.
- **Safety limits:** max active rules per user; a max order value per trigger; a global "pause all rules" kill switch in settings; rules auto-expire after 90 days unless renewed.

### 9.4 Ask your portfolio

A chat panel answers questions using **read-only tools** that query the user's own data:
`get_positions`, `get_trades(range)`, `get_performance(range)`, `get_move_explanations(symbol, range)`, `get_sector_exposure`, `get_risk_metrics`.

Examples: *"Why is my portfolio down today?"* (combines holdings with §9.1 explanations) · *"What's my win rate on trades held under a week?"* · *"Which holding is most correlated with NVDA?"*

Answers stream to the UI over Server-Sent Events. This assistant has no order-placing tools. To act, it can only hand off a pre-filled command to §9.2.

### 9.5 LLM integration details

| Concern | Approach |
|---|---|
| Provider / SDK | Claude API through the official `anthropic` Python SDK, wrapped in one `assistant/llm.py` client (retries, timeouts, metrics) |
| Model | `claude-opus-5-5` by default, set with the `LLM_MODEL` env var so it can be changed per deployment |
| Effort | `low` for command and rule parsing (fast, cheap), `medium` for move explanations and portfolio Q&A (`LLM_EFFORT`) |
| Structured data | `strict: true` tools for the command parser; `output_config.format` JSON schemas for rule ASTs and move explanations; every response is also validated with Pydantic before use |
| Prompt caching | Static system prompts and tool definitions go first with `cache_control`; per-user context (holdings, cash) goes after the cache breakpoint, so the shared prefix stays cached |
| Bulk work | Nightly explanation backfill goes through the **Message Batches API** (half price; results matched by `custom_id`) |
| Cost guardrails | Per-user daily quota (`AI_DAILY_REQUESTS_PER_USER`), global monthly budget alarm, regex fast path for simple orders, cached explanations (past moves never change) |
| Quality | A test set of ~300 natural-language commands and ~100 rules with expected parses runs in CI on prompt changes; a sample of explanations is spot-checked against the cited articles |
| Degradation | `AI_FEATURES_ENABLED=False` or an API outage → regex parser, visual rule builder, and deterministic-only explanations ("moved with market" / "news near this time: …") |

---

## 10. Market data pipeline

| Job | When | What |
|---|---|---|
| `sync_symbols` | daily, 06:00 ET | Pull the list of tradable US equities and ETFs, upsert `Stock` |
| `backfill_bars` | on demand + nightly | Daily bars (5y) and intraday bars (30d) for active symbols |
| `ingestor` process | market hours | Streams trades/quotes for symbols that are subscribed or held, writes `quote:*` to Redis, publishes ticks |
| `snapshot_portfolios` | 16:15 ET | Write `PortfolioSnapshot` for every account |
| `compute_leaderboard` | every 15 min + EOD | Rank accounts by % return; cache in a Redis sorted set |
| `check_alerts` | on every tick (debounced) | Fire matching alerts, deactivate one-shot alerts |
| `fetch_news` | every 10 min | Fetch headlines for popular and held tickers |
| `reconcile_ledgers` | nightly | Check the cash vs. ledger invariant |
| `ingest_filings` | every 5 min | Fetch SEC EDGAR 8-K, 10-Q/K and Form 4 filings, tag them to tickers |
| `ingest_macro_calendar` | daily | Load CPI, FOMC, jobs and earnings dates into `MarketEvent` |
| `embed_news` | on ingest | Deduplicate, tag tickers, compute embedding and importance |
| `detect_moves` | on bar close (1m/1h/1d) | Segment new bars into `PriceMove` rows, decompose vs. SPY and sector |
| `explain_moves_batch` | nightly, 18:00 ET | Submit unexplained day and hour moves to the Message Batches API, store results |
| `explain_spike` | on live spike (\|z\| > 4) | Explain immediately, push `move_explained` |
| `rules_time_tick` | every 15 s in market hours | Evaluate time-based rule conditions |
| `expire_rules` | daily | Expire rules older than 90 days, notify owners |

**Caching:** latest quotes live in Redis (TTL 1 day); company profiles and
fundamentals in Redis (TTL 24h); bar requests are served from Postgres first and
only fetched from the provider on a cache miss.

**Free-tier limits:** subscribe only to symbols that someone is viewing, holds or
has an open order or alert on. Keep a reference-counted subscription set in Redis.

---

## 11. Frontend pages and UX

| Page | Key components |
|---|---|
| **Dashboard** | Total equity with animated counter, day P&L, equity sparkline, holdings table with live flashing prices, market movers, watchlist sidebar, market status pill |
| **Stock detail** `/stocks/:symbol` | Candlestick chart with timeframe tabs and indicators, live quote header, key stats grid, company profile, news, your position card, **order ticket** panel |
| **Order ticket** | Buy/Sell toggle, order type tabs, quantity or dollar amount input, estimated cost, buying power, review-and-confirm modal, keyboard shortcuts (`B` / `S`) |
| **Portfolio** | Allocation donut (by stock and sector), equity curve vs. SPY, analytics cards (return, Sharpe, max drawdown, win rate) |
| **Orders** | Tabs for Open / Filled / Cancelled; cancel button; live status updates |
| **Watchlists** | Drag-and-drop ordering, multiple lists, live prices, quick-trade button |
| **Screener** | Filter sidebar, sortable results table, save-a-screen |
| **Leaderboard** | Weekly/monthly/all-time tabs, league switcher, your rank highlighted |
| **Settings** | Profile, notification preferences, theme, reset paper account, AI on/off, "pause all rules" kill switch |
| **Command bar** (global, `/` or `Ctrl+K`) | Type or speak an order, rule or question → preview card → Confirm |
| **Rules** | List with status, last evaluated and next trigger estimate; rule editor (natural language or visual blocks); "would have triggered" backtest chart; execution history |
| **Chart explanations** | Move markers on every chart, hover reason cards with sources, "Story of the day" panel, drag-select "Explain this range" |
| **Ask** panel | Slide-over chat about your portfolio, streamed answers, links into charts and trades |

**UX details that make it feel premium**
- Prices flash green or red on change; numbers use tabular figures
- Optimistic UI for cancels; toasts for fills ("Bought 10 AAPL @ $187.22")
- Skeleton loaders, not spinners
- A clear "Market closed — orders will execute at next open" banner
- Command palette: `Ctrl+K` → type `AAPL` → Enter jumps to the stock; `buy 10 aapl` opens a prefilled ticket
- Responsive down to phone width; installable PWA

**Auth handling:** the access token is kept in memory (Zustand). The refresh token is
an httpOnly, Secure, SameSite=Strict cookie. An axios interceptor refreshes on 401
and retries once.

---

## 12. Security and correctness checklist

- [ ] All money math uses `Decimal`; rounding with `ROUND_HALF_EVEN` at defined points only
- [ ] `select_for_update` + `transaction.atomic` around every balance or position change
- [ ] Idempotency keys on order submission
- [ ] Object-level permissions: users can only see and act on their own accounts and orders (filter querysets by `request.user`; tests for IDOR)
- [ ] Rate limits on login, register, password reset and order placement
- [ ] Strong password validation; optional TOTP 2FA (`django-otp`) in v2
- [ ] HTTPS only in prod, HSTS, secure cookies, CSRF on cookie-based endpoints
- [ ] Secrets only via env vars; `DEBUG=False` and a strict `ALLOWED_HOSTS` in prod
- [ ] WebSocket authenticated with the JWT on connect; reject anonymous sockets
- [ ] Validate and whitelist all screener and sort query parameters
- [ ] LLM output is never executed directly: everything goes through schema validation, the deterministic resolver and validator, and user confirmation
- [ ] News and filing text only reaches the explanation pipeline, which has no action tools (prompt-injection isolation)
- [ ] Rule AST allows only whitelisted metrics and actions, with nesting-depth and order-size limits; no `eval`, no user-supplied code
- [ ] Per-user AI quotas, and `ANTHROPIC_API_KEY` kept server-side only (never sent to the frontend)
- [ ] Explanation citations limited to IDs from the candidate list; no lookahead (only news published before the move ends)
- [ ] Dependency scanning (`pip-audit`, `npm audit`, Dependabot)
- [ ] Clear disclaimer: "Simulated trading. Not investment advice." Market data attribution as the provider's terms require

---

## 13. Testing strategy

| Layer | What to test |
|---|---|
| Unit (pytest) | Order validation rules, fill math (avg cost, realized P&L), slippage, market-hours logic (holidays, half days via `freezegun`), analytics formulas |
| Concurrency | Two simultaneous buys that together exceed buying power → exactly one succeeds (threaded test against real Postgres) |
| API | Every endpoint: auth required, permission isolation, validation errors, pagination |
| WebSocket | Channels `WebsocketCommunicator`: subscribe, receive a quote, private order updates go only to their owner |
| Frontend | Vitest for formatters, hooks and the order ticket form; MSW to mock the API |
| E2E | Playwright: sign up → search AAPL → buy → see the position → sell → see realized P&L (using the `mock` provider) |
| AI parsing | Golden test sets: ~300 NL commands and ~100 rules → expected structured output; run on every prompt or model change (live API, nightly) and with recorded responses in normal CI |
| Rules engine | Property-based tests (`hypothesis`) for the evaluator; edge-trigger and cooldown; no double-fire under concurrent ticks; replay historical bars and compare with backtest results |
| Explanations | Move detection on synthetic series with known breakpoints; lookahead guard; citation-ID validation; "no clear catalyst" when the candidate list is empty |
| Coverage target | 85%+ on `trading/`, `portfolio/` and `rules/`, which hold the money logic |

---

## 14. Milestones

Estimates assume one full-time developer.

| # | Milestone | Duration | Deliverable |
|---|---|---|---|
| 0 | **Foundation** | 3–4 days | Repo, Docker Compose (Postgres, Redis, Django, Vite), split settings, `.env.example`, CI pipeline, ruff/eslint, health check |
| 1 | **Auth** | 3–4 days | Custom User, JWT + refresh cookie, register/login/verify/reset, React auth pages, protected routes |
| 2 | **Market data** | 1 week | Provider abstraction (alpaca + mock), `Stock` sync, search with Postgres FTS, bars endpoint, stock page with candlestick chart |
| 3 | **Realtime** | 4–5 days | Ingestor process, Redis quotes, Channels consumer, `useQuote` hook, flashing prices |
| 4 | **Trading engine** | 1.5–2 weeks | Accounts, orders, fills, positions, ledger, `SimulatedBroker`, matching worker, DAY expiry, order ticket UI, orders page, concurrency tests |
| 5 | **Portfolio** | 1 week | Positions and summary, EOD snapshots, equity chart, allocation, dashboard |
| 6 | **Watchlists and alerts** | 4–5 days | CRUD, drag-and-drop, alert engine, in-app and email notifications |
| 7 | **Polish and launch v1** | 1 week | Error states, empty states, responsive pass, Sentry, prod Compose, Nginx + TLS, seed data, docs |
| 8 | **v2: social and analytics** | 2–3 weeks | Leaderboard, leagues, achievements, screener, news + sentiment, analytics metrics, command palette, PWA |
| 9 | **News and catalyst foundation** | 1 week | News + EDGAR + macro ingestion, dedupe, ticker tagging, pgvector embeddings, Catalyst Calendar |
| 10 | **"Why did it move?"** | 2 weeks | Move detection, market/sector decomposition, Claude attribution with structured output, nightly batches, chart markers, Story of the day, Explain this range, live spike explanations |
| 11 | **Natural-language trading** | 1.5 weeks | Command bar, regex fast path, Claude strict-tool parser, resolver, preview and confirm, baskets, voice input, golden test set |
| 12 | **Conditional rules** | 2 weeks | Rule AST + Pydantic schema, NL → AST, visual builder, evaluation engine (tick, time, event), backtest preview, safety limits |
| 13 | **Ask your portfolio + AI coach** | 1 week | Read-only tool chat, trade journal, weekly coaching report, daily briefing |
| 14 | **v3: power** | ongoing | Backtester, indicators, DCA, fractional shares, Alpaca paper/live broker |

**MVP (milestones 0–7): about 7–9 weeks. AI layer (milestones 9–13): about 7–8 more weeks.** Milestones 9–10 can start in parallel with 8, since they only depend on market data (milestone 2).

---

## 15. Risks and mitigations

| Risk | Mitigation |
|---|---|
| Market data rate limits or cost | Subscribe only on demand, cache aggressively, keep a mock provider, allow switching providers via env |
| Race conditions corrupting balances | Row locks, atomic transactions, ledger with nightly reconciliation, concurrency tests |
| Stale prices filling orders unfairly | Reject fills if the quote is older than N seconds; show quote age in the UI |
| Legal exposure with real money | Stay paper-only until a licensed broker partnership (Alpaca Broker API) and KYC are in place |
| LLM gives a wrong order parse | Strict schemas, deterministic resolver, mandatory preview and confirm, golden test set in CI |
| Made-up or misleading "why" explanations | Citations only from provided items, no lookahead, "no clear catalyst" allowed, confidence badge, disclaimer, market/sector decomposition before any LLM call |
| Prompt injection via news text | The explanation pipeline has no action tools; the trading assistant never reads news |
| Runaway rules (loops, repeated firing) | Edge-triggering, cooldowns, idempotent `RuleExecution`, per-trigger size caps, kill switch, auto-expiry |
| LLM cost growth | Caching (past explanations never change), batch processing, regex fast path, per-user quotas, budget alarm |
| News API licensing | Show headline + source + link only (no full article text); follow each provider's display terms |
| WebSocket scaling | Channels with a Redis layer scales horizontally; move to a dedicated pub/sub gateway if needed |
| Timezone bugs | Store everything in UTC; convert to `America/New_York` only for market-hours logic and to the user's timezone for display |

---

## 16. Getting started (first commands)

```bash
cp .env.example .env                 # fill in ALPACA keys, or use MARKET_DATA_PROVIDER=mock
docker compose up -d --build
docker compose exec backend python manage.py migrate
docker compose exec backend python manage.py createsuperuser
docker compose exec backend python manage.py sync_symbols
docker compose exec backend python manage.py backfill_bars --symbols AAPL,MSFT,NVDA,TSLA,SPY
# Frontend → http://localhost:5173   API docs → http://localhost:8000/api/docs
```
