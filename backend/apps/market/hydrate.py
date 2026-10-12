"""Load real data for tickers: profile, price history, quote, and news.

The full US universe (~11k symbols) is listed from the Nasdaq directory, but detailed data is
only loaded for popular tickers at startup and for any other ticker the first time someone
opens it (a few seconds), just like a broker app fetching a page.
"""
import logging
import threading
import time
from decimal import Decimal

from django.core.cache import cache
from django.db import close_old_connections
from django.utils import timezone

from . import quotes
from .models import PriceBar, Stock

log = logging.getLogger(__name__)
HISTORY = [("1d", "2y", "1d"), ("5m", "60d", "5m"), ("1m", "7d", "1m")]


def quote_from_db(stock: Stock) -> dict | None:
    """The latest session's quote (a weekend shows Friday's close and change, like any broker)."""
    daily = list(PriceBar.objects.filter(stock=stock, timeframe="1d").order_by("-ts")[:2])
    if not daily:
        return None
    last = daily[0]
    prev = float(daily[1].close) if len(daily) > 1 else float(last.open)
    minute = PriceBar.objects.filter(stock=stock, timeframe="1m").order_by("-ts").first()
    price = float(minute.close) if minute and minute.ts >= last.ts else float(last.close)
    return {"symbol": stock.symbol, "price": round(price, 4), "prev_close": round(prev, 4),
            "open": float(last.open), "high": float(last.high), "low": float(last.low),
            "volume": last.volume, "change": round(price - prev, 4),
            "change_pct": round((price / prev - 1) * 100, 4) if prev else 0, "t": int(time.time())}


def _apply_profile(stock: Stock, p: dict):
    stock.name = p.get("name") or stock.name
    if p.get("exchange"):
        stock.exchange = p["exchange"]
    stock.sector = p.get("sector", "")
    stock.sector_etf = p.get("sector_etf", "")
    stock.industry = p.get("industry", "")
    stock.market_cap = p.get("market_cap")
    stock.pe_ratio = Decimal(str(p["pe_ratio"])) if p.get("pe_ratio") else None
    stock.dividend_yield = Decimal(str(p["dividend_yield"])) if p.get("dividend_yield") is not None else None
    stock.beta = Decimal(str(p.get("beta") or 1))
    stock.description = p.get("description", "")
    stock.is_etf = p.get("is_etf", stock.is_etf)
    stock.ceo = p.get("ceo", "")
    stock.employees = p.get("employees")
    stock.website = p.get("website", "")
    stock.hq = p.get("hq", "")


def hydrate(symbols: list[str], news: bool = True, log_fn=None) -> list[str]:
    from .providers import yahoo

    say = log_fn or (lambda m: log.info(m))
    stocks = {s.symbol: s for s in Stock.objects.filter(symbol__in=symbols)}
    if not stocks:
        return []
    say(f"Loading profiles for {len(stocks)} tickers from Yahoo Finance…")
    profs = yahoo.profiles(list(stocks))
    for sym, st in stocks.items():
        p = profs.get(sym) or {}
        if p.get("has_data"):
            _apply_profile(st, p)
            st.save()
    got_bars = set()
    for tf, period, interval in HISTORY:
        say(f"Downloading {interval} bars ({period})…")
        syms = list(stocks)
        n = 0
        for i in range(0, len(syms), 25):
            data = yahoo.download(syms[i:i + 25], period=period, interval=interval)
            rows = []
            for sym, bars in data.items():
                got_bars.add(sym)
                rows += [PriceBar(stock=stocks[sym], timeframe=tf, ts=b.ts, open=round(b.o, 4),
                                  high=round(b.h, 4), low=round(b.l, 4), close=round(b.c, 4),
                                  volume=b.v) for b in bars]
            PriceBar.objects.bulk_create(rows, batch_size=5000, update_conflicts=True,
                                         unique_fields=["stock", "timeframe", "ts"],
                                         update_fields=["open", "high", "low", "close", "volume"])
            n += len(rows)
        say(f"  {n:,} bars")
    now = timezone.now()
    done = []
    for sym in got_bars:
        st = stocks[sym]
        q = quote_from_db(st)
        if q:
            quotes.set_quote(sym, q)
        st.hydrated_at = now
        st.is_tradable = True
        st.save(update_fields=["hydrated_at", "is_tradable"])
        done.append(sym)
    for sym in set(stocks) - got_bars:
        cache.set(f"hydrate:failed:{sym}", 1, 3600)  # Yahoo has no data; don't retry for an hour
    from apps.news import ingest

    from .resolve import reset_cache

    reset_cache()
    ingest.reset_tagger()
    if news and done:
        say("Loading real news, filings and earnings…")
        n = ingest.backfill(symbols=done, log_fn=say)
        say(f"  {n:,} news items")
    return done


def ensure_hydrated(stock: Stock, wait: float = 25.0) -> bool:
    """Make sure a ticker has real data before showing it. Prices now, news in the background."""
    if stock.hydrated_at:
        return True
    if cache.get(f"hydrate:failed:{stock.symbol}"):
        return False
    if cache.add(f"hydrate:lock:{stock.symbol}", 1, 120):
        try:
            ok = bool(hydrate([stock.symbol], news=False))
        finally:
            cache.delete(f"hydrate:lock:{stock.symbol}")
        if ok:
            def bg(sym=stock.symbol):
                close_old_connections()
                try:
                    from apps.news import ingest

                    ingest.backfill(symbols=[sym], log_fn=lambda m: None)
                finally:
                    close_old_connections()

            threading.Thread(target=bg, daemon=True).start()
        stock.refresh_from_db()
        return ok
    deadline = time.monotonic() + wait
    while time.monotonic() < deadline:  # someone else is loading it
        time.sleep(0.5)
        stock.refresh_from_db(fields=["hydrated_at"])
        if stock.hydrated_at:
            return True
    return False


def note_viewed(symbol: str):
    """Recently viewed tickers join the live-tracked set for a while."""
    quotes.r().zadd("viewed", {symbol: time.time()})
