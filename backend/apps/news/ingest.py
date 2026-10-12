"""News ingestion: fetch from free sources, dedupe, tag tickers, classify, store, broadcast."""
from __future__ import annotations

import hashlib
import logging
import re
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, date, datetime, timedelta

from django.conf import settings
from django.core.cache import cache
from django.db import IntegrityError, transaction

from apps.market.models import Stock

from .classify import classify
from .models import MarketEvent, NewsArticle
from .sources import extra, rss, sec
from .sources.base import RawItem

log = logging.getLogger(__name__)


def _norm(headline: str) -> str:
    return re.sub(r"[^a-z0-9 ]", "", headline.lower())[:160]


def dedupe_key(item: RawItem) -> str:
    # Same story from several feeds: normalised headline + day is the key.
    return hashlib.sha256(f"{_norm(item.headline)}|{item.published_at.date()}".encode()).hexdigest()


def _short(name: str) -> str:
    return re.sub(r",? (Inc\.?|Corporation|Corp\.?|Company|Co\.|Incorporated|plc|Ltd\.?|"
                  r"Class [AB])$", "", name).replace("The ", "").strip()


# First words of company names that are too generic to identify the company on their own.
GENERIC_FIRST_WORDS = {
    "first", "general", "american", "united", "bank", "advanced", "international", "state",
    "national", "global", "eli", "walt", "home", "royal", "taiwan", "applied", "texas",
    "ishares", "invesco", "spdr", "vanguard", "select", "digital", "public", "southern",
}

_name_index: list[tuple[re.Pattern, str]] | None = None


def _tagger():
    global _name_index
    if _name_index is None:
        idx = []
        for s in Stock.objects.filter(is_active=True, is_etf=False, hydrated_at__isnull=False):
            short = _short(s.name)
            first = short.split()[0]
            names = {short}
            if len(first) > 3 and first.lower() not in GENERIC_FIRST_WORDS:
                names.add(first)
            pat = "|".join(re.escape(n) for n in sorted(names, key=len, reverse=True))
            # bare tickers only when unambiguous (V, GE, MA, KO… are ordinary words)
            bare = f"|{s.symbol}" if len(s.symbol) >= 3 else ""
            idx.append((re.compile(rf"(?<![\w$])(?:{pat}{bare})\b|\${s.symbol}\b|\({s.symbol}\)"),
                        s.symbol))
        _name_index = idx
    return _name_index


def reset_tagger():
    global _name_index
    _name_index = None


def ingest(items: list[RawItem], broadcast: bool = False) -> list[NewsArticle]:
    stocks = {s.symbol: s for s in Stock.objects.filter(is_active=True)}
    tagger = _tagger()
    created = []
    now = datetime.now(UTC)
    seen = set()
    for it in items:
        if not it.headline or it.published_at > now + timedelta(minutes=5):
            continue
        key = dedupe_key(it)
        if key in seen:
            continue
        seen.add(key)
        syms = {s for s in it.symbols if s in stocks}
        for pat, sym in tagger:  # mentions of other tracked companies
            if pat.search(it.headline):
                syms.add(sym)
        c = classify(it.headline, it.summary, it.kind)
        if it.sentiment is not None:
            c["sentiment"] = it.sentiment
        if it.importance is not None:
            c["importance"] = it.importance
        if not syms and c["kind"] not in ("macro",):
            # market-wide coverage without a tracked company: keep only macro-like items
            c["kind"] = "macro" if re.search(r"\b(stocks?|market|s&p|nasdaq|dow|wall street)\b",
                                             it.headline, re.I) else c["kind"]
            if c["kind"] != "macro":
                continue
        try:
            with transaction.atomic():
                art = NewsArticle.objects.create(
                    headline=it.headline[:400], summary=it.summary[:2000], source=it.source[:120],
                    url=it.url[:600], kind=c["kind"], published_at=it.published_at,
                    sentiment=c["sentiment"], importance=c["importance"], sector=it.sector,
                    is_simulated=False, dedupe_hash=key)
                if syms:
                    art.stocks.add(*[stocks[s] for s in syms])
        except IntegrityError:
            continue
        created.append(art)
    if broadcast and created:
        from apps.realtime.notify import broadcast_all

        from .serializers import NewsArticleSerializer

        recent = [a for a in created if a.published_at > now - timedelta(hours=2)]
        for a in sorted(recent, key=lambda a: a.published_at)[-10:]:
            broadcast_all("news", {"article": NewsArticleSerializer(a).data})
    return created


def _tracked(symbols: list[str] | None = None):
    qs = Stock.objects.filter(is_active=True, is_etf=False, hydrated_at__isnull=False)
    if symbols is not None:
        qs = qs.filter(symbol__in=symbols)
    return list(qs.values_list("symbol", "name"))


def _parallel(fn, args, workers=8):
    out = []
    with ThreadPoolExecutor(workers) as ex:
        for res in ex.map(lambda a: _safe(fn, *a), args):
            out.extend(res)
    return out


def _safe(fn, *a):
    try:
        return fn(*a)
    except Exception as e:
        log.info("news source %s failed for %s: %s", getattr(fn, "__name__", fn), a[:1], type(e).__name__)
        return []


# ------------------------------------------------------------------------------------------
# Live polling (every NEWS_POLL_MINUTES, from the ingestor)
# ------------------------------------------------------------------------------------------
def poll_latest(symbols: list[str] | None = None) -> int:
    tracked = _tracked(symbols)
    items: list[RawItem] = []
    items += _parallel(rss.yahoo, [(s,) for s, _ in tracked])
    items += _safe(rss.google_market, 1)
    items += extra.finnhub_market()
    if settings.FINNHUB_API_KEY:
        today = date.today()
        items += _parallel(extra.finnhub_company, [(s, today - timedelta(days=1), today)
                                                   for s, _ in tracked], workers=4)
    items += extra.alpaca([s for s, _ in tracked], date.today() - timedelta(days=1))
    # SEC filings change slowly; check every 30 minutes
    if not cache.get("news:sec_polled"):
        cache.set("news:sec_polled", 1, 1800)
        since = date.today() - timedelta(days=3)
        items += _parallel(sec.filings, [(s, n, since) for s, n in tracked], workers=3)
    created = ingest(items, broadcast=True)
    log.info("news poll: %d fetched, %d new", len(items), len(created))
    return len(created)


# ------------------------------------------------------------------------------------------
# Backfill (on first load)
# ------------------------------------------------------------------------------------------
def backfill(days: int | None = None, log_fn=print, symbols: list[str] | None = None) -> int:
    days = days or settings.NEWS_BACKFILL_DAYS
    tracked = _tracked(symbols)
    if not tracked:
        return 0
    since = date.today() - timedelta(days=days)
    total = 0

    log_fn(f"  earnings history for {len(tracked)} companies…")
    results = _parallel(lambda s, n: [extra.earnings_items(s, n)], [(s, n) for s, n in tracked], workers=6)
    items: list[RawItem] = []
    for (sym, _), (past, upcoming) in zip(tracked, results, strict=True):
        items += past
        stock = Stock.objects.get(symbol=sym)
        MarketEvent.objects.filter(stock=stock, kind="earnings").delete()
        for e in past:
            MarketEvent.objects.create(stock=stock, kind="earnings", ts=e.published_at,
                                       title=e.headline[:200], payload={})
        for u in upcoming:
            MarketEvent.objects.create(stock=stock, kind="earnings", ts=u["ts"],
                                       title=f"{_short(stock.name)} earnings",
                                       payload={"upcoming": True, "eps_estimate": u["estimate"]})
    total += len(ingest(items))

    log_fn("  SEC EDGAR filings (2 years)…")
    total += len(ingest(_parallel(sec.filings, [(s, n, date.today() - timedelta(days=730))
                                                for s, n in tracked], workers=3)))

    log_fn(f"  headlines from Google News ({days} days) and Yahoo Finance…")
    items = _parallel(rss.google_company, [(s, n, None, None, days) for s, n in tracked], workers=6)
    items += _parallel(rss.yahoo, [(s,) for s, _ in tracked])
    if symbols is None or len(symbols) > 5:
        items += _safe(rss.google_market, min(days, 7))
    if settings.FINNHUB_API_KEY:
        items += _parallel(extra.finnhub_company, [(s, since, date.today()) for s, _ in tracked], workers=2)
    items += extra.alpaca([s for s, _ in tracked], since)
    total += len(ingest(items))
    return total


# ------------------------------------------------------------------------------------------
# On demand: news for a specific past window (used when explaining an old move)
# ------------------------------------------------------------------------------------------
def fetch_window(stock: Stock, start: datetime, end: datetime) -> int:
    if stock.is_etf or settings.MARKET_DATA_PROVIDER == "mock":
        return 0
    d0, d1 = (start - timedelta(days=1)).date(), end.date()
    key = f"news:window:{stock.symbol}:{d0}:{d1}"
    if cache.get(key):
        return 0
    cache.set(key, 1, 30 * 86400)
    items = _safe(rss.google_company, stock.symbol, stock.name, d0, d1)
    if settings.FINNHUB_API_KEY:
        items += extra.finnhub_company(stock.symbol, d0, d1)
    return len(ingest(items))
