"""Build the simulated market (2 years of bars + news) and demo accounts.

    python manage.py seed_demo            # idempotent: skips if data already exists
    python manage.py seed_demo --reset    # wipe market data and regenerate
"""
import random
import time
from datetime import datetime, timedelta
from decimal import Decimal

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.market import quotes
from apps.market.hours import ET, is_trading_day
from apps.market.models import PriceBar, Stock
from apps.market.sim import SIM_SOURCE, dedupe_hash, generate_history
from apps.market.universe import DESCRIPTIONS, ETFS, SECTOR_ETFS, STOCKS, real_universe
from apps.news.models import MarketEvent, NewsArticle
from apps.portfolio.models import PortfolioSnapshot
from apps.trading.models import LedgerEntry, Position, Trade, TradingAccount

DEMO_EMAIL, DEMO_PASSWORD = "demo@tradeall.app", "demo-trader-2026"
BOTS = [("Ava Chen", "ava"), ("Marcus Reid", "marcus"), ("Priya Nair", "priya"),
        ("Leo Fischer", "leo"), ("Sofia Alvarez", "sofia"), ("Kenji Watanabe", "kenji")]


class Command(BaseCommand):
    help = "Seed the simulated market and demo users."

    def add_arguments(self, parser):
        parser.add_argument("--reset", action="store_true")
        parser.add_argument("--days", type=int, default=504)
        parser.add_argument("--intraday-days", type=int, default=10)

    def handle(self, *args, reset=False, days=504, intraday_days=10, **opts):
        real = settings.MARKET_DATA_PROVIDER != "mock"
        if PriceBar.objects.exists() and not reset:
            have_sim = NewsArticle.objects.filter(is_simulated=True).exists()
            if have_sim == real:  # switching between simulated and real data: rebuild
                self.stdout.write("Data source changed "
                                  f"({'simulated → real' if real else 'real → simulated'}); rebuilding.")
                reset = True
            elif real and Stock.objects.count() < 1000:
                # Upgrade from the old fixed list to the full US universe, keeping accounts.
                self.stdout.write("Upgrading to the full US ticker universe…")
                self._load_real()
                self._quotes_from_db()
                return
            else:
                self.stdout.write("Market data already present; skipping (use --reset to rebuild).")
                self._quotes_from_db()
                self._demo_trade_history()
                return
        t0 = time.monotonic()
        if reset:
            self._wipe()
        if real:
            stocks = self._load_real()
        else:
            stocks = self._load_sim(days, intraday_days)
        self._quotes_from_db()
        self._users(stocks)
        self.stdout.write(self.style.SUCCESS(f"Seeded in {time.monotonic() - t0:.1f}s. "
                                             f"Demo login: {DEMO_EMAIL} / {DEMO_PASSWORD}"))

    def _wipe(self):
        self.stdout.write("Wiping market data…")
        from apps.explain.models import PriceMove
        from apps.rules.models import TradingRule
        from apps.trading.models import Order

        PriceMove.objects.all().delete()
        get_user_model().objects.filter(email__in=[DEMO_EMAIL] + [
            f"{h}@bots.tradeall.app" for _, h in BOTS]).delete()
        TradingRule.objects.all().delete()
        Trade.objects.all().delete()
        Order.objects.all().delete()
        Position.objects.all().delete()
        PortfolioSnapshot.objects.all().delete()
        PriceBar.objects.all().delete()
        NewsArticle.objects.all().delete()
        MarketEvent.objects.all().delete()
        # every account restarts from its starting cash
        for acct in TradingAccount.objects.all():
            acct.cash_balance, acct.reserved_cash = acct.starting_cash, 0
            acct.save()
        quotes.r().delete("quotes")
        for k in quotes.r().scan_iter("bars1s:*"):
            quotes.r().delete(k)

    def _load_sim(self, days, intraday_days):
        self._stocks()
        end = timezone.now().astimezone(ET).date() - timedelta(days=1)
        while not is_trading_day(end):
            end -= timedelta(days=1)
        self.stdout.write(f"Generating {days} simulated trading days ending {end}…")
        hist = generate_history(end, n_days=days, intraday_days=intraday_days)
        stocks = {s.symbol: s for s in Stock.objects.all()}
        self._bars(hist, stocks)
        self._news(hist, stocks)
        return stocks

    def _load_real(self):
        from apps.market import directory
        from apps.market.hydrate import hydrate

        self.stdout.write("Syncing the full US ticker list (Nasdaq Trader symbol directory)…")
        directory.sync(log_fn=self.stdout.write)
        core = real_universe()
        Stock.objects.filter(symbol__in=core).update(is_popular=True)
        done = hydrate(core, news=True, log_fn=self.stdout.write)
        self.stdout.write(f"Loaded real data for {len(done)} popular tickers; "
                          "every other US ticker loads on first view.")
        return {s.symbol: s for s in Stock.objects.filter(symbol__in=done)}

    # ------------------------------------------------------------------------------------
    def _stocks(self):
        for sym, name, ex, sector, _p, beta, _v, cap, pe in STOCKS:
            short = name.split(",")[0].replace(" Inc.", "")
            Stock.objects.update_or_create(symbol=sym, defaults=dict(
                name=name, exchange=ex, sector=sector, sector_etf=SECTOR_ETFS[sector],
                industry=sector, beta=Decimal(str(beta)), market_cap=cap * 1_000_000_000,
                pe_ratio=Decimal(str(pe)) if pe else None,
                dividend_yield=Decimal(str(round(random.Random(sym).uniform(0, 3), 2))),
                description=f"{short} {DESCRIPTIONS[sector]}", is_etf=False))
        for sym, name, _p, mkt, _s, _v in ETFS:
            Stock.objects.update_or_create(symbol=sym, defaults=dict(
                name=name, exchange="NYSE Arca", sector="", sector_etf="",
                beta=Decimal(str(mkt)), is_etf=True,
                description=f"{name} is an exchange-traded fund."))
        from apps.market.resolve import reset_cache

        reset_cache()

    def _bars(self, hist, stocks):
        rows = []
        for sym, bars in hist.daily.items():
            for b in bars:
                rows.append(PriceBar(stock=stocks[sym], timeframe="1d", ts=b.ts, open=round(b.o, 4),
                                     high=round(b.h, 4), low=round(b.l, 4), close=round(b.c, 4),
                                     volume=b.v))
        for sym, bars in hist.minute.items():
            for b in bars:
                rows.append(PriceBar(stock=stocks[sym], timeframe="1m", ts=b.ts, open=round(b.o, 4),
                                     high=round(b.h, 4), low=round(b.l, 4), close=round(b.c, 4),
                                     volume=b.v))
        self.stdout.write(f"Inserting {len(rows):,} bars…")
        PriceBar.objects.bulk_create(rows, batch_size=5000, ignore_conflicts=True)

    def _news(self, hist, stocks):
        self.stdout.write(f"Inserting {len(hist.catalysts):,} news items…")
        with transaction.atomic():
            for c in hist.catalysts:
                a = NewsArticle.objects.create(
                    headline=c.headline[:400], summary=c.summary, kind=c.kind,
                    source="SEC EDGAR (simulated)" if c.kind == "sec_filing" else SIM_SOURCE,
                    published_at=c.ts, sentiment=c.sentiment, importance=c.importance,
                    sector=c.sector or "", is_simulated=True, dedupe_hash=dedupe_hash(c))
                if c.symbol:
                    a.stocks.add(stocks[c.symbol])
                if c.kind == "earnings" and c.symbol:
                    MarketEvent.objects.create(stock=stocks[c.symbol], kind="earnings", ts=c.ts,
                                               title=c.headline[:200],
                                               payload={**c.payload, "move_pct": round(
                                                   c.impact * 100, 2)})
                if c.macro:
                    MarketEvent.objects.create(kind=c.payload.get("event", "cpi"), ts=c.ts,
                                               title=c.headline[:200],
                                               payload={"move_pct": round(c.impact * 100, 2)})
            for c in hist.upcoming:
                MarketEvent.objects.create(stock=stocks.get(c.symbol) if c.symbol else None,
                                           kind="earnings" if c.symbol else c.kind, ts=c.ts,
                                           title=c.headline[:200], payload={"upcoming": True})

    def _quotes_from_db(self):
        n = 0
        qs = Stock.objects.filter(is_active=True)
        if settings.MARKET_DATA_PROVIDER != "mock":
            qs = qs.filter(hydrated_at__isnull=False)
        for stock in qs:
            daily = list(PriceBar.objects.filter(stock=stock, timeframe="1d").order_by("-ts")[:2])
            if not daily:
                continue
            last_min = PriceBar.objects.filter(stock=stock, timeframe="1m").order_by("-ts").first()
            today = timezone.now().astimezone(ET).date()
            last_day = daily[0]
            real = settings.MARKET_DATA_PROVIDER != "mock"
            # Real data: the quote shows the latest session (like any broker on a weekend).
            if (real or last_day.ts.astimezone(ET).date() == today) and len(daily) > 1:
                prev_close, o, h, lo, v = (float(daily[1].close), float(last_day.open),
                                           float(last_day.high), float(last_day.low),
                                           last_day.volume)
            else:
                prev_close = float(last_day.close)
                o = h = lo = prev_close
                v = 0
            price = float(last_min.close) if last_min and last_min.ts > last_day.ts else \
                float(last_day.close)
            quotes.set_quote(stock.symbol, _quote(stock.symbol, price, prev_close, o, h, lo, v))
            n += 1
        if n:
            self.stdout.write(f"Initialised {n} quotes.")

    def _users(self, stocks):
        User = get_user_model()
        demo, created = User.objects.get_or_create(email=DEMO_EMAIL, defaults={
            "username": DEMO_EMAIL, "display_name": "Demo Trader"})
        if created:
            demo.set_password(DEMO_PASSWORD)
            demo.save()
        self._backfill(demo, ["AAPL", "NVDA", "MSFT", "JPM", "XOM", "LLY", "AMZN", "SPY"],
                       seed=1, days_ago=120)
        self._demo_trade_history()
        wl = demo.watchlists.first()
        if wl and not wl.items.exists():
            from apps.watchlists.models import WatchlistItem

            for i, sym in enumerate(["TSLA", "META", "AMD", "NFLX", "COST", "GS"]):
                WatchlistItem.objects.create(watchlist=wl, stock=stocks[sym], position=i)
        if not demo.rules.exists():
            from apps.rules.models import TradingRule
            from apps.rules.spec import RuleSpec

            acct = demo.accounts.first()
            for spec in [
                {"name": "Buy the NVDA dip", "condition": {"logic": "all", "clauses": [
                    {"metric": "pct_change", "symbol": "NVDA", "window": "since_prev_close",
                     "op": "<=", "value": -4}]},
                 "action": {"type": "buy_notional", "symbol": "NVDA", "amount": 2000},
                 "mode": "once"},
                {"name": "Alert: TSLA momentum", "condition": {"logic": "all", "clauses": [
                    {"metric": "pct_change", "symbol": "TSLA", "window": "15m", "op": ">=",
                     "value": 2}]},
                 "action": {"type": "notify", "message": "TSLA is ripping: +2% in 15 minutes"},
                 "mode": "repeat", "cooldown_seconds": 1800},
            ]:
                s = RuleSpec.model_validate(spec)
                TradingRule.objects.create(user=demo, account=acct, name=s.name,
                                           spec=s.model_dump(mode="json"),
                                           expires_at=timezone.now() + timedelta(days=90))
        rng = random.Random(42)
        pool = [s for s in stocks if not stocks[s].is_etf]
        for i, (name, handle) in enumerate(BOTS):
            email = f"{handle}@bots.tradeall.app"
            u, created = User.objects.get_or_create(email=email, defaults={
                "username": email, "display_name": name})
            if created:
                u.set_unusable_password()
                u.save()
            self._backfill(u, rng.sample(pool, rng.randint(4, 8)), seed=100 + i,
                           days_ago=rng.randint(40, 200))

    def _demo_trade_history(self, n_trades: int = 32):
        """Closed round trips at real historical closes, so performance analytics have data."""
        demo = get_user_model().objects.filter(email=DEMO_EMAIL).first()
        if not demo:
            return
        acct = demo.accounts.first()
        if Trade.objects.filter(account=acct, side="sell").exists():
            return
        from apps.trading.models import Order

        held = set(Position.objects.filter(account=acct, quantity__gt=0)
                   .values_list("stock__symbol", flat=True))
        pool = ["TSLA", "AMD", "PLTR", "META", "NFLX", "COIN", "SHOP", "UBER", "CRM", "BA", "DIS",
                "SOFI", "HOOD", "NKE", "SBUX", "INTC", "MU", "AVGO", "GOOGL", "ORCL", "SNOW", "CRWD"]
        stocks = {s.symbol: s for s in Stock.objects.filter(symbol__in=[p for p in pool if p not in held])}
        closes = {}
        for sym, st in stocks.items():
            rows = list(PriceBar.objects.filter(stock=st, timeframe="1d").order_by("-ts")[:170])
            if len(rows) > 60:
                closes[sym] = list(reversed(rows))
        if not closes:
            return
        rng = random.Random(2026)
        trips = []
        for _ in range(n_trades):
            sym = rng.choice(list(closes))
            bars = closes[sym]
            i = rng.randint(5, len(bars) - 30)
            k = rng.choice([2, 3, 4, 6, 8, 10, 14, 19, 25])
            trips.append((bars[i], bars[min(i + k, len(bars) - 2)], sym, Decimal(rng.randint(1500, 4500))))
        trips.sort(key=lambda t: t[1].ts)
        realized_by_day: dict = {}
        with transaction.atomic():
            acct = TradingAccount.objects.select_for_update().get(pk=acct.pk)
            cash = acct.cash_balance
            for buy_bar, sell_bar, sym, dollars in trips:
                st = stocks[sym]
                qty = (dollars / buy_bar.close).quantize(Decimal("0.0001"))
                t_buy = buy_bar.ts.astimezone(ET).replace(hour=10, minute=12)
                t_sell = sell_bar.ts.astimezone(ET).replace(hour=14, minute=47)
                cost = (qty * buy_bar.close).quantize(Decimal("0.01"))
                proceeds = (qty * sell_bar.close).quantize(Decimal("0.01"))
                realized = proceeds - cost
                for side, ts, px, amt in (("buy", t_buy, buy_bar.close, -cost),
                                          ("sell", t_sell, sell_bar.close, proceeds)):
                    o = Order.objects.create(account=acct, stock=st, side=side, type="market",
                                             quantity=qty, filled_qty=qty, avg_fill_price=px,
                                             status="filled", filled_at=ts)
                    Order.objects.filter(pk=o.pk).update(created_at=ts)
                    Trade.objects.create(order=o, account=acct, stock=st, side=side, quantity=qty,
                                         price=px, executed_at=ts,
                                         realized_pnl=realized if side == "sell" else None)
                    cash += amt
                    LedgerEntry.objects.create(account=acct, type=f"trade_{side}", amount=amt,
                                               balance_after=cash, reference=str(o.pk), created_at=ts)
                pos, _ = Position.objects.get_or_create(account=acct, stock=st,
                                                        defaults={"avg_cost": buy_bar.close})
                pos.realized_pnl += realized
                pos.save()
                d = t_sell.date()
                realized_by_day[d] = realized_by_day.get(d, Decimal(0)) + realized
            acct.cash_balance = cash
            acct.save(update_fields=["cash_balance"])
            # carry realized P&L into the daily equity history
            running = Decimal(0)
            days = sorted(realized_by_day)
            for snap in PortfolioSnapshot.objects.filter(account=acct).order_by("date"):
                while days and days[0] <= snap.date:
                    running += realized_by_day.pop(days.pop(0))
                if running:
                    snap.cash += running
                    snap.total_equity += running
                    snap.save(update_fields=["cash", "total_equity"])
        self.stdout.write(f"Added {len(trips)} closed demo trades for performance analytics.")

    def _backfill(self, user, symbols, seed, days_ago):
        """Buy a basket at historical closes and write daily equity snapshots since then."""
        acct = user.accounts.first()
        if acct.trades.exists():
            return
        rng = random.Random(seed)
        closes = {}
        for s in symbols:
            closes[s] = {b.ts.astimezone(ET).date(): b.close for b in
                         PriceBar.objects.filter(stock__symbol=s, timeframe="1d").order_by("ts")}
        dates = sorted(closes[symbols[0]])[-days_ago:]
        start = dates[0]
        budget = acct.cash_balance * Decimal("0.85")
        weights = [rng.uniform(0.5, 1.5) for _ in symbols]
        total_w = sum(weights)
        stocks = {s.symbol: s for s in Stock.objects.filter(symbol__in=symbols)}
        holdings = {}
        with transaction.atomic():
            cash = acct.cash_balance
            for s, w in zip(symbols, weights, strict=True):
                px = closes[s][start]
                qty = (budget * Decimal(w / total_w) / px).to_integral_value(rounding="ROUND_DOWN")
                if qty <= 0:
                    continue
                at = datetime.combine(start, datetime.min.time(), ET).replace(hour=15, minute=55)
                from apps.trading.models import Order

                o = Order.objects.create(account=acct, stock=stocks[s], side="buy", type="market",
                                         quantity=qty, filled_qty=qty, avg_fill_price=px,
                                         status="filled", filled_at=at)
                Order.objects.filter(pk=o.pk).update(created_at=at)
                Trade.objects.create(order=o, account=acct, stock=stocks[s], side="buy",
                                     quantity=qty, price=px, executed_at=at)
                cash -= qty * px
                LedgerEntry.objects.create(account=acct, type="trade_buy", amount=-(qty * px),
                                           balance_after=cash, reference=str(o.pk), created_at=at)
                Position.objects.create(account=acct, stock=stocks[s], quantity=qty, avg_cost=px,
                                        opened_at=at)
                holdings[s] = qty
            acct.cash_balance = cash
            acct.save()
            TradingAccount.objects.filter(pk=acct.pk).update(
                created_at=datetime.combine(start, datetime.min.time(), ET))
            snaps = []
            for d in dates:
                mv = sum(holdings[s] * closes[s].get(d, closes[s][start]) for s in holdings)
                snaps.append(PortfolioSnapshot(account=acct, date=d, cash=cash, positions_value=mv,
                                               total_equity=cash + mv))
            PortfolioSnapshot.objects.bulk_create(snaps, ignore_conflicts=True)


def _quote(symbol, price, prev_close, o, h, lo, v):
    return {"symbol": symbol, "price": round(price, 4), "prev_close": round(prev_close, 4),
            "open": round(o, 4), "high": round(h, 4), "low": round(lo, 4), "volume": int(v),
            "change": round(price - prev_close, 4),
            "change_pct": round((price / prev_close - 1) * 100, 4) if prev_close else 0,
            "t": int(time.time())}
