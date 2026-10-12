"""Yahoo Finance and Google News RSS (no keys)."""
import logging
import re
from datetime import UTC, date, datetime, timedelta
from email.utils import parsedate_to_datetime
from urllib.parse import quote_plus

import feedparser
import httpx

from .base import RawItem

log = logging.getLogger(__name__)
UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) TradeAllN/1.0"}


def _get(url: str) -> list:
    try:
        r = httpx.get(url, headers=UA, timeout=15, follow_redirects=True)
        r.raise_for_status()
        return feedparser.parse(r.text).entries
    except Exception as e:
        log.info("rss fetch failed: %s (%s)", url[:80], type(e).__name__)
        return []


def _when(e) -> datetime | None:
    raw = e.get("published") or e.get("updated")
    if not raw:
        return None
    try:
        d = parsedate_to_datetime(raw)
        return d if d.tzinfo else d.replace(tzinfo=UTC)
    except (TypeError, ValueError):
        return None


def _strip_html(s: str) -> str:
    return re.sub(r"<[^>]+>", " ", s or "").replace("&nbsp;", " ").strip()


def yahoo(symbol: str) -> list[RawItem]:
    url = f"https://feeds.finance.yahoo.com/rss/2.0/headline?s={symbol}&region=US&lang=en-US"
    out = []
    for e in _get(url):
        ts = _when(e)
        if ts and e.get("title"):
            out.append(RawItem(headline=e.title.strip(), published_at=ts, source="Yahoo Finance",
                               url=e.get("link", ""), summary=_strip_html(e.get("summary", ""))[:600],
                               symbols=[symbol]))
    return out


def _google(query: str, symbols: list[str], kind: str | None = None) -> list[RawItem]:
    url = f"https://news.google.com/rss/search?q={quote_plus(query)}&hl=en-US&gl=US&ceid=US:en"
    out = []
    for e in _get(url):
        ts = _when(e)
        title = (e.get("title") or "").strip()
        if not ts or not title:
            continue
        src = (e.get("source") or {}).get("title") or "Google News"
        # Google appends " - Publisher" to titles
        if title.endswith(f" - {src}"):
            title = title[: -len(src) - 3]
        out.append(RawItem(headline=title, published_at=ts, source=src, url=e.get("link", ""),
                           symbols=list(symbols), kind=kind))
    return out


def google_company(symbol: str, name: str, start: date | None = None, end: date | None = None,
                   days: int = 7) -> list[RawItem]:
    short = re.sub(r",? (Inc\.?|Corporation|Corp\.?|Company|Co\.|Incorporated|plc|Ltd\.?)$", "",
                   name).replace("The ", "")
    q = f'"{short}" {symbol} stock'
    if start and end:
        q += f" after:{start.isoformat()} before:{(end + timedelta(days=1)).isoformat()}"
    else:
        q += f" when:{days}d"
    return _google(q, [symbol])


def google_market(days: int = 2) -> list[RawItem]:
    q = (f"(stock market OR Wall Street OR S&P 500) (Fed OR inflation OR CPI OR jobs report OR "
         f"Treasury yields OR tariffs OR earnings season) when:{days}d")
    return _google(q, [])


def utcnow() -> datetime:
    return datetime.now(UTC)
