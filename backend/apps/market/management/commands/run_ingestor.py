"""The live loop: prices -> Redis quotes -> WebSocket -> order matching -> rules.

Real mode (default, MARKET_DATA_PROVIDER=yahoo|finnhub|alpaca): a background poller pulls real
quotes and minute bars from Yahoo Finance (plus real-time trade ticks from Finnhub when a key is
set), and a second thread polls real news. Mock mode drives the offline simulator.
Either way the downstream pipeline is identical.
"""
import json
import logging
import math
import signal
import threading
import time
from collections import deque
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import close_old_connections
from django.utils import timezone

from apps.explain.detection import Segment
from apps.explain.models import PriceMove
from apps.explain.service import rules_attribution
from apps.market import hours, quotes
from apps.market.hours import ET
from apps.market.models import PriceBar, Stock
from apps.market.sim import SIM_SOURCE, LiveSim, dedupe_hash
from apps.news.models import NewsArticle
from apps.news.serializers import NewsArticleSerializer
from apps.realtime.notify import broadcast_all
from apps.rules import evaluator
from apps.trading import engine

log = logging.getLogger("ingestor")


class MinuteBar:
    __slots__ = ("t", "o", "h", "l", "c", "v")

    def __init__(self, t, price):
        self.t, self.o, self.h, self.l, self.c, self.v = t, price, price, price, price, 0

    def update(self, price, vol):
        self.h, self.l, self.c = max(self.h, price), min(self.l, price), price
        self.v += vol


class Command(BaseCommand):
    help = "Run the live market data loop."

    def handle(self, *args, **opts):
        self.running = True
        signal.signal(signal.SIGTERM, lambda *_: setattr(self, "running", False))
        signal.signal(signal.SIGINT, lambda *_: setattr(self, "running", False))
        self.real = settings.MARKET_DATA_PROVIDER != "mock"
        for _ in range(200):  # in Docker the API container may still be loading data
            qs = Stock.objects.filter(is_active=True)
            if self.real:
                qs = qs.filter(hydrated_at__isnull=False)
            self.stocks = {s.symbol: s for s in qs}
            if self.stocks and PriceBar.objects.exists():
                break
            self.stdout.write("Waiting for market data (run `python manage.py seed_demo`)…")
            time.sleep(3)
        else:
            self.stderr.write("No stocks found. Run `python manage.py seed_demo` first.")
            return
        self.day = timezone.now().astimezone(ET).date()
        self.was_open = hours.is_open()
        self.state = {}
        self.minute: dict[str, MinuteBar] = {}
        self.avg_vol = {}
        self.pending_spikes = deque()
        if self.real:
            hot, warm = self._live_set()
            for sym in hot + warm:
                self._add_symbol(sym)
        else:
            for sym in self.stocks:
                self._add_symbol(sym)

        if self.real:
            self._start_real()
            interval = 1.0
        else:
            self.sim = LiveSim({s: q["price"] for s, q in self.state.items()},
                               tick_seconds=settings.MOCK_TICK_SECONDS)
            interval = settings.MOCK_TICK_SECONDS
        self.stdout.write(self.style.SUCCESS(
            f"Ingestor running ({settings.MARKET_DATA_PROVIDER}) for {len(self.state)} symbols · "
            f"market {hours.status()['label'].lower()}"))
        ticks = 0
        while self.running:
            started = time.monotonic()
            try:
                close_old_connections()
                self.tick()
                ticks += 1
                if ticks % 300 == 0:
                    log.info("tick %s ok", ticks)
            except Exception:
                log.exception("tick failed")
            time.sleep(max(0.0, interval - (time.monotonic() - started)))
        if not self.real:
            self._flush_minutes()
        self.stdout.write("Ingestor stopped.")

    # ------------------------------------------------------------------------------------
    # Real data
    # ------------------------------------------------------------------------------------
    def _add_symbol(self, sym: str):
        if sym in self.state:
            return
        stock = self.stocks.get(sym) or Stock.objects.filter(symbol=sym).first()
        if not stock:
            return
        self.stocks[sym] = stock
        q = quotes.get_quote(sym)
        if not q:
            last = PriceBar.objects.filter(stock=stock, timeframe="1d").order_by("-ts").first()
            if not last:
                return
            p = float(last.close)
            q = {"symbol": sym, "price": p, "prev_close": p, "open": p, "high": p, "low": p,
                 "volume": 0, "change": 0, "change_pct": 0}
        self.state[sym] = q
        vols = list(PriceBar.objects.filter(stock=stock, timeframe="1d")
                    .order_by("-ts").values_list("volume", flat=True)[:20])
        self.avg_vol[sym] = (sum(vols) / len(vols)) if vols else 1_000_000
        if hasattr(self, "ret_hist"):
            self.ret_hist.setdefault(sym, deque(maxlen=60))

    def _live_set(self) -> tuple[list[str], list[str]]:
        """Hot: what users hold, watch, view or have orders/automations on. Warm: popular list."""
        from apps.rules.models import TradingRule
        from apps.trading.models import Order, Position, RecurringInvestment
        from apps.watchlists.models import WatchlistItem

        hot = set(Position.objects.filter(quantity__gt=0).values_list("stock__symbol", flat=True))
        hot |= set(WatchlistItem.objects.values_list("stock__symbol", flat=True))
        hot |= set(Order.objects.filter(status__in=Order.OPEN_STATES)
                   .values_list("stock__symbol", flat=True))
        hot |= set(RecurringInvestment.objects.filter(active=True)
                   .values_list("stock__symbol", flat=True))
        for spec in TradingRule.objects.filter(status="active").values_list("spec", flat=True):
            for c in (spec or {}).get("condition", {}).get("clauses", []):
                if isinstance(c, dict) and c.get("symbol"):
                    hot.add(c["symbol"])
        cutoff = time.time() - 3 * 3600
        hot |= set(quotes.r().zrangebyscore("viewed", cutoff, "+inf"))
        hot |= {"SPY", "QQQ", "DIA", "IWM"}
        hydrated = set(Stock.objects.filter(hydrated_at__isnull=False, is_active=True)
                       .values_list("symbol", flat=True))
        hot &= hydrated
        warm = sorted(set(Stock.objects.filter(is_popular=True, hydrated_at__isnull=False)
                          .values_list("symbol", flat=True)) - hot)
        return sorted(hot)[:150], warm[:250]

    def _refresh_live_set(self):
        hot, warm = self._live_set()
        for sym in hot + warm:
            self._add_symbol(sym)
        self.yahoo.set_symbols(hot, warm)
        if self.stream and hasattr(self.stream, "symbols"):
            self.stream.symbols = sorted(hot, key=lambda s: self.stocks[s].is_etf)[:50]

    def _start_real(self):
        from apps.market.providers.yahoo import YahooPoller

        hot, warm = self._live_set()
        self.ret_hist: dict[str, deque] = {s: deque(maxlen=60) for s in self.state}
        self.yahoo = YahooPoller(hot, warm, interval=settings.QUOTE_POLL_SECONDS)
        self.stream = None
        if settings.FINNHUB_API_KEY:
            from apps.market.providers.finnhub import FinnhubStream

            # the free tier streams 50 symbols: what people hold/watch first
            self.stream = FinnhubStream(sorted(hot, key=lambda s: self.stocks[s].is_etf))
        elif settings.MARKET_DATA_PROVIDER == "alpaca" and settings.ALPACA_API_KEY:
            from apps.market.providers.alpaca import AlpacaPoller

            self.stream = AlpacaPoller(hot)
        self.last_version = -1
        self.written_minute: dict[str, int] = {}
        self.spike_cooldown: dict[str, float] = {}
        self.last_live_refresh = time.monotonic()
        self.last_recurring = 0.0
        self.session = hours.status()["status"]
        threading.Thread(target=self._news_loop, name="news-poller", daemon=True).start()
        threading.Thread(target=self._maintenance_loop, name="maintenance", daemon=True).start()

    def _maintenance_loop(self):
        """Dividends every 6 hours, ticker directory once a day."""
        from apps.market import directory
        from apps.trading.autoinvest import pay_dividends

        time.sleep(30)
        last_sync = 0.0
        while self.running:
            try:
                close_old_connections()
                n = pay_dividends()
                if n:
                    log.info("paid %d dividends", n)
                if time.time() - last_sync > 86400:
                    directory.sync(log_fn=log.info)
                    last_sync = time.time()
            except Exception:
                log.warning("maintenance failed", exc_info=True)
            for _ in range(6 * 3600):
                if not self.running:
                    return
                time.sleep(1)

    def _news_loop(self):
        from apps.news.ingest import poll_latest

        time.sleep(5)
        while self.running:
            try:
                close_old_connections()
                hot, warm = self._live_set()
                poll_latest(hot + warm[:60])
            except Exception:
                log.warning("news poll failed", exc_info=True)
            for _ in range(settings.NEWS_POLL_MINUTES * 60):
                if not self.running:
                    return
                time.sleep(1)

    def _real_prices(self):
        prices, day, minute_bars, version = self.yahoo.snapshot()
        if self.stream:
            if isinstance(getattr(self.stream, "prices", None), dict) and \
                    not hasattr(self.stream, "poll"):
                live = self.stream.prices
            else:
                live = self.stream.poll()
            if hours.is_open():  # stream prints override the (slightly delayed) Yahoo price
                prices = {**prices, **{s: p for s, p in live.items() if s in self.state}}
        return prices, day, minute_bars, version

    # ------------------------------------------------------------------------------------
    def tick(self):
        now = timezone.now()
        self._maybe_roll_day(now)
        cat = None
        day, minute_bars, version = {}, {}, None
        if self.real:
            if time.monotonic() - self.last_live_refresh > 30:
                self.last_live_refresh = time.monotonic()
                self._refresh_live_set()
            prices, day, minute_bars, version = self._real_prices()
        else:
            prices, cat = self.sim.step(now)
        if cat:
            self._publish_catalyst(cat, now)
        sec = int(now.timestamp())
        minute_t = sec - sec % 60
        changed = {}
        compact = {}
        for sym, q in self.state.items():
            price = prices.get(sym)
            if price is None or not math.isfinite(price):
                price = q["price"]
            prev_price = q["price"]
            if self.real:
                d = day.get(sym)
                if d:
                    q.update(prev_close=d["prev_close"], open=d["open"], volume=d["volume"],
                             high=max(d["high"], price), low=min(d["low"], price))
                    ext = d.get("ext_price")
                    q["ext_price"] = round(ext, 4) if ext else None
                    q["ext_session"] = d.get("ext_session") if ext else None
                    q["ext_change_pct"] = round((ext / price - 1) * 100, 4) if ext and price else None
                vol = 0
            else:
                base = self.avg_vol[sym] / 23400
                vol = int(base * (0.4 + 25 * abs(price / prev_price - 1) * 100))
                q.update(high=max(q["high"], price), low=min(q["low"], price),
                         volume=q["volume"] + vol)
            q.update(price=round(price, 4), t=sec)
            q["change"] = round(price - q["prev_close"], 4)
            q["change_pct"] = round((price / q["prev_close"] - 1) * 100, 4) if q["prev_close"] else 0
            changed[sym] = q
            if not self.real or hours.is_open():
                quotes.push_second_bar(sym, {"t": sec, "o": prev_price, "h": max(prev_price, price),
                                             "l": min(prev_price, price), "c": price, "v": vol})
            if not self.real:
                mb = self.minute.get(sym)
                if mb is None or mb.t != minute_t:
                    if mb is not None:
                        self._write_minute(sym, mb)
                    mb = self.minute[sym] = MinuteBar(minute_t, prev_price)
                mb.update(price, vol)
            compact[sym] = [q["price"], q["change_pct"], q["volume"], q.get("ext_price"),
                            q.get("ext_change_pct")]
        quotes.r().hset("quotes", mapping={s: json.dumps(q) for s, q in changed.items()})
        broadcast_all("quotes", {"t": sec, "q": compact})
        if self.real and version != self.last_version:
            self.last_version = version
            self._store_real_bars(minute_bars, day, now)
        engine.process_ticks({s: Decimal(str(q["price"])) for s, q in changed.items()},
                             {s: Decimal(str(q["ext_price"])) for s, q in changed.items()
                              if q.get("ext_price")})
        if self.real and hours.is_open() and time.monotonic() - self.last_recurring > 60:
            self.last_recurring = time.monotonic()
            from apps.trading.autoinvest import run_recurring

            run_recurring(now)
        evaluator.run_all(now)
        self._process_spikes(now)

    # ------------------------------------------------------------------------------------
    def _store_real_bars(self, minute_bars, day, now):
        """Upsert Yahoo's real minute bars and today's daily bar; watch for sudden moves."""
        rows = []
        for sym, bars in minute_bars.items():
            stock = self.stocks.get(sym)
            if not stock or not bars:
                continue
            last_written = self.written_minute.get(sym, 0)
            # the newest bar may still be forming, so always rewrite the last few
            for b in bars[-5:]:
                rows.append(PriceBar(stock=stock, timeframe="1m", ts=b.ts, open=round(b.o, 4),
                                     high=round(b.h, 4), low=round(b.l, 4), close=round(b.c, 4),
                                     volume=b.v))
            complete = bars[:-1]
            for i, b in enumerate(complete):
                if i and int(b.ts.timestamp()) > last_written and last_written:
                    self._watch_spike(sym, complete[i - 1].c, b, now)
            self.written_minute[sym] = int(complete[-1].ts.timestamp()) if complete else last_written
        if rows:
            PriceBar.objects.bulk_create(rows, update_conflicts=True,
                                         unique_fields=["stock", "timeframe", "ts"],
                                         update_fields=["open", "high", "low", "close", "volume"])
        daily = []
        for sym, d in day.items():
            stock = self.stocks.get(sym)
            if not stock or sym not in self.state:
                continue
            ts = datetime.combine(datetime.fromisoformat(d["session"]).date(), datetime.min.time(), ET)
            q = self.state[sym]
            daily.append(PriceBar(stock=stock, timeframe="1d", ts=ts, open=round(d["open"], 4),
                                  high=round(q["high"], 4), low=round(q["low"], 4),
                                  close=round(q["price"], 4), volume=d["volume"]))
        if daily:
            PriceBar.objects.bulk_create(daily, update_conflicts=True,
                                         unique_fields=["stock", "timeframe", "ts"],
                                         update_fields=["open", "high", "low", "close", "volume"])

    def _watch_spike(self, sym, prev_close, bar, now):
        if not prev_close or not hours.is_open():
            return
        r = math.log(bar.c / prev_close)
        hist = self.ret_hist[sym]
        if len(hist) >= 20:
            mean = sum(hist) / len(hist)
            sd = math.sqrt(sum((x - mean) ** 2 for x in hist) / (len(hist) - 1)) or 1e-4
            if abs(r) > max(4 * sd, 0.006) and now.timestamp() - self.spike_cooldown.get(sym, 0) > 900:
                self.spike_cooldown[sym] = now.timestamp()
                # give the news feeds a moment, then explain
                self.pending_spikes.append((now + timedelta(seconds=45), sym, None,
                                            prev_close, bar.ts))
        hist.append(r)

    # ------------------------------------------------------------------------------------
    # Simulated data
    # ------------------------------------------------------------------------------------
    def _write_minute(self, sym, mb: MinuteBar):
        stock = self.stocks[sym]
        ts = datetime.fromtimestamp(mb.t, UTC)
        PriceBar.objects.update_or_create(
            stock=stock, timeframe="1m", ts=ts,
            defaults=dict(open=round(mb.o, 4), high=round(mb.h, 4), low=round(mb.l, 4),
                          close=round(mb.c, 4), volume=mb.v))
        q = self.state[sym]
        day_ts = datetime.combine(self.day, datetime.min.time(), ET)
        PriceBar.objects.update_or_create(
            stock=stock, timeframe="1d", ts=day_ts,
            defaults=dict(open=round(q["open"], 4), high=round(q["high"], 4),
                          low=round(q["low"], 4), close=round(q["price"], 4),
                          volume=q["volume"]))

    def _flush_minutes(self):
        for sym, mb in self.minute.items():
            try:
                self._write_minute(sym, mb)
            except Exception:
                log.exception("flush %s", sym)

    def _close_session(self, session_day):
        from apps.portfolio.services import take_snapshot
        from apps.trading.models import TradingAccount

        n = engine.expire_day_orders()
        for acct in TradingAccount.objects.all():
            take_snapshot(acct, session_day)
        log.info("session %s closed: %d day orders expired, snapshots taken", session_day, n)

    def _maybe_roll_day(self, now):
        if self.real:
            # Real market: close out the session when the bell rings.
            open_now = hours.is_open(now)
            if self.was_open and not open_now:
                self._close_session(now.astimezone(ET).date())
            self.was_open = open_now
            session = hours.status(now)["status"]
            if self.session == "after_hours" and session == "closed":
                engine.expire_day_orders(extended=True)  # extended-hours DAY orders end at 8pm
            self.session = session
            return
        today = now.astimezone(ET).date()
        if today == self.day:
            return
        log.info("New simulated session %s", today)
        self._flush_minutes()
        self._close_session(self.day)
        self.day = today
        for q in self.state.values():
            q.update(prev_close=q["price"], open=q["price"], high=q["price"], low=q["price"],
                     volume=0)

    # ------------------------------------------------------------------------------------
    def _publish_catalyst(self, cat, now):
        art = NewsArticle.objects.create(
            headline=cat.headline[:400], summary=cat.summary, kind=cat.kind,
            source="SEC EDGAR (simulated)" if cat.kind == "sec_filing" else SIM_SOURCE,
            published_at=now, sentiment=cat.sentiment, importance=cat.importance,
            sector=cat.sector or "", is_simulated=True, dedupe_hash=dedupe_hash(cat))
        if cat.symbol:
            art.stocks.add(self.stocks[cat.symbol])
        broadcast_all("news", {"article": NewsArticleSerializer(art).data})
        targets = [cat.symbol] if cat.symbol else (
            [self.stocks[s].sector_etf for s in self.stocks
             if self.stocks[s].sector == cat.sector][:1] if cat.sector else ["SPY"])
        for sym in targets:
            if sym in self.state:
                self.pending_spikes.append((now + timedelta(seconds=12), sym, art.pk,
                                            self.state[sym]["price"], now))

    def _process_spikes(self, now):
        """Once a reaction has played out, explain it live from the freshest news (no LLM)."""
        while self.pending_spikes and self.pending_spikes[0][0] <= now:
            _, sym, art_id, p0, t0 = self.pending_spikes.popleft()
            try:
                self._explain_spike(sym, art_id, p0, t0, now)
            except Exception:
                log.exception("spike explanation failed")

    def _explain_spike(self, sym, art_id, p0, t0, now):
        stock = self.stocks[sym]
        p1 = self.state[sym]["price"]
        pct = (p1 / p0 - 1) * 100
        if art_id:
            art = NewsArticle.objects.get(pk=art_id)
        else:
            art = (NewsArticle.objects.filter(stocks=stock, published_at__gte=t0 - timedelta(minutes=45),
                                              published_at__lte=now)
                   .order_by("-importance", "-published_at").first())
        spy = self.state.get("SPY", {})
        mv = PriceMove(stock=stock, timeframe="1m", start_ts=t0, end_ts=now, start_price=p0,
                       end_price=p1, pct_change=pct,
                       direction="up" if pct > 0.05 else "down" if pct < -0.05 else "flat",
                       magnitude_z=0, market_pct=spy.get("change_pct"), sector_pct=None,
                       residual_pct=pct, volume_ratio=None)
        mv._seg = Segment(0, 0, int(t0.timestamp()), int(now.timestamp()), p0, p1, 0)
        mv._bars = []
        if art:
            market_driven = not art.stocks.filter(pk=stock.pk).exists()
            result = rules_attribution(stock, mv, [art], drivers=[{
                "t": int(now.timestamp()), "when": "", "pct": pct, "market_pct": mv.market_pct,
                "article": art, "market_driven": market_driven}])
            summary, category = result["summary"], result["category"]
        elif abs(pct) >= 1.0:
            summary = (f"{'Jumped' if pct > 0 else 'Dropped'} {abs(pct):.2f}% within minutes. "
                       "No matching headline yet; we'll attach one if it appears.")
            category = "no_clear_catalyst"
        else:
            return
        broadcast_all("move_explained", {
            "symbol": sym, "pct": pct, "start_t": int(t0.timestamp()), "end_t": int(now.timestamp()),
            "summary": summary, "category": category,
            "article": NewsArticleSerializer(art).data if art else None,
        })
