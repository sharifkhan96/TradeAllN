"""Earnings results (Yahoo data) and optional keyed news sources (Finnhub, Alpaca)."""
import logging
from datetime import UTC, date, datetime

from django.conf import settings

from .base import RawItem

log = logging.getLogger(__name__)


def earnings_items(symbol: str, name: str) -> tuple[list[RawItem], list[dict]]:
    """Past results become news items; future dates become calendar events."""
    from apps.market.providers import yahoo

    items, upcoming = [], []
    now = datetime.now(UTC)
    for e in yahoo.earnings(symbol):
        ts = e["ts"].astimezone(UTC)
        if ts > now or e["actual"] is None:
            upcoming.append({"ts": ts, "estimate": e["estimate"]})
            continue
        est, act, sur = e["estimate"], e["actual"], e["surprise_pct"]
        if est is not None:
            verb = "beats" if act > est else "misses" if act < est else "meets"
            headline = f"{name} {verb} estimates: EPS ${act:.2f} vs ${est:.2f} expected"
            if sur is not None:
                headline += f" ({sur:+.1f}% surprise)"
        else:
            headline = f"{name} reports quarterly EPS of ${act:.2f}"
        s = 0.0 if sur is None else max(-1.0, min(1.0, sur / 10))
        items.append(RawItem(headline=headline, published_at=ts, source="Yahoo Finance (earnings data)",
                             symbols=[symbol], kind="earnings", sentiment=s, importance=0.95))
    return items, upcoming


def finnhub_company(symbol: str, start: date, end: date) -> list[RawItem]:
    if not settings.FINNHUB_API_KEY:
        return []
    from apps.market.providers import finnhub

    try:
        rows = finnhub.company_news(symbol, start, end)
    except Exception:
        log.info("finnhub news failed for %s", symbol, exc_info=True)
        return []
    return [RawItem(headline=r["headline"], published_at=finnhub.ts(r["datetime"]),
                    source=r.get("source") or "Finnhub", url=r.get("url", ""),
                    summary=(r.get("summary") or "")[:600], symbols=[symbol])
            for r in rows if r.get("headline")]


def finnhub_market() -> list[RawItem]:
    if not settings.FINNHUB_API_KEY:
        return []
    from apps.market.providers import finnhub

    try:
        rows = finnhub.market_news()
    except Exception:
        return []
    return [RawItem(headline=r["headline"], published_at=finnhub.ts(r["datetime"]),
                    source=r.get("source") or "Finnhub", url=r.get("url", ""),
                    summary=(r.get("summary") or "")[:600]) for r in rows if r.get("headline")]


def alpaca(symbols: list[str], start: date) -> list[RawItem]:
    if not settings.ALPACA_API_KEY:
        return []
    from apps.market.providers import alpaca as ap

    try:
        rows = ap.news(symbols, start.isoformat(), limit=50)
    except Exception:
        log.info("alpaca news failed", exc_info=True)
        return []
    return [RawItem(headline=r["headline"],
                    published_at=datetime.fromisoformat(r["created_at"].replace("Z", "+00:00")),
                    source=r.get("source") or "Alpaca/Benzinga", url=r.get("url", ""),
                    summary=(r.get("summary") or "")[:600],
                    symbols=[s for s in r.get("symbols", []) if s in symbols]) for r in rows]
