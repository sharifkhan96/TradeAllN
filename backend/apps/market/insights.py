"""Broker-style research data: analyst ratings, price targets, earnings, fundamentals,
dividends, market movers and curated lists. All from free Yahoo Finance data, cached."""
from __future__ import annotations

import logging
import math
import time
from datetime import UTC, datetime

import yfinance as yf
from django.core.cache import cache
from django.db.models import Count

from . import quotes
from .models import Stock
from .providers.yahoo import _clean, download, earnings, ysym

log = logging.getLogger(__name__)


def _num(x):
    v = _clean(x)
    return None if v is None or math.isinf(v) else v


def insights(stock: Stock) -> dict:
    key = f"insights:{stock.symbol}"
    hit = cache.get(key)
    if hit:
        return hit
    t = yf.Ticker(ysym(stock.symbol))
    out: dict = {"symbol": stock.symbol}
    try:
        info = t.info or {}
    except Exception:
        info = {}

    # analyst consensus
    try:
        rec = t.recommendations
        row = rec.iloc[0].to_dict() if rec is not None and not rec.empty else None
    except Exception:
        row = None
    if row:
        buy = int(row.get("strongBuy", 0)) + int(row.get("buy", 0))
        hold = int(row.get("hold", 0))
        sell = int(row.get("sell", 0)) + int(row.get("strongSell", 0))
        total = buy + hold + sell
        out["analysts"] = {"buy": buy, "hold": hold, "sell": sell, "total": total,
                           "buy_pct": buy / total * 100 if total else None,
                           "consensus": (info.get("recommendationKey") or "").replace("_", " ")}
    try:
        pt = t.analyst_price_targets or {}
        if pt.get("mean"):
            out["price_target"] = {k: _num(pt.get(k)) for k in ("low", "mean", "median", "high", "current")}
    except Exception:
        pass

    # earnings history + next date
    eps = earnings(stock.symbol, limit=12)
    now = datetime.now(UTC)
    out["earnings"] = [{"date": e["ts"].date().isoformat(), "estimate": e["estimate"],
                        "actual": e["actual"], "surprise_pct": e["surprise_pct"]}
                       for e in sorted(eps, key=lambda e: e["ts"]) if e["ts"] <= now][-8:]
    nxt = [e for e in eps if e["ts"] > now]
    out["next_earnings"] = min(nxt, key=lambda e: e["ts"])["ts"].isoformat() if nxt else None

    # dividends
    try:
        div = t.dividends
        out["dividends"] = [{"date": ts.date().isoformat(), "amount": float(v)}
                            for ts, v in div.tail(8).items()] if div is not None else []
    except Exception:
        out["dividends"] = []
    exd = info.get("exDividendDate")
    out["ex_dividend_date"] = datetime.fromtimestamp(exd, UTC).date().isoformat() if exd else None
    out["dividend_rate"] = _num(info.get("dividendRate"))

    # fundamentals
    out["fundamentals"] = {
        "forward_pe": _num(info.get("forwardPE")), "eps": _num(info.get("trailingEps")),
        "revenue": _num(info.get("totalRevenue")), "profit_margin": _num(info.get("profitMargins")),
        "revenue_growth": _num(info.get("revenueGrowth")),
        "shares_outstanding": _num(info.get("sharesOutstanding")),
        "short_pct_float": _num(info.get("shortPercentOfFloat")),
        "avg_volume": _num(info.get("averageVolume")),
        "week52_high": _num(info.get("fiftyTwoWeekHigh")), "week52_low": _num(info.get("fiftyTwoWeekLow")),
        "expense_ratio": _num(info.get("netExpenseRatio")) if stock.is_etf else None,
        "aum": _num(info.get("totalAssets")) if stock.is_etf else None,
    }
    out["extended"] = {"pre": _num(info.get("preMarketPrice")), "post": _num(info.get("postMarketPrice"))}
    cache.set(key, out, 6 * 3600)
    return out


# --------------------------------------------------------------------------------------------
# Quotes for arbitrary symbols (search results, lists)
# --------------------------------------------------------------------------------------------
def snapshot(symbols: list[str], max_age: int = 120) -> dict[str, dict]:
    """Quotes for any tickers: from the live cache when fresh, else one batched Yahoo call."""
    symbols = [s.upper() for s in symbols][:60]
    have = quotes.get_quotes(symbols)
    now = time.time()
    stale = [s for s in symbols if s not in have or now - have[s].get("t", 0) > max_age]
    if stale:
        fetched_key = "snapshot:" + ",".join(sorted(stale))
        if not cache.get(fetched_key):
            cache.set(fetched_key, 1, 60)
            try:
                data = download(stale, period="5d", interval="1d")
            except Exception:
                data = {}
            for sym, bars in data.items():
                if not bars:
                    continue
                last, prev = bars[-1], (bars[-2].c if len(bars) > 1 else bars[-1].o)
                q = {"symbol": sym, "price": round(last.c, 4), "prev_close": round(prev, 4),
                     "open": last.o, "high": last.h, "low": last.l, "volume": last.v,
                     "change": round(last.c - prev, 4),
                     "change_pct": round((last.c / prev - 1) * 100, 4) if prev else 0, "t": now}
                live = have.get(sym)
                if not live or now - live.get("t", 0) > max_age:
                    quotes.set_quote(sym, q)
                have[sym] = q
    return have


# --------------------------------------------------------------------------------------------
# Discover
# --------------------------------------------------------------------------------------------
COLLECTIONS = [
    {"slug": "magnificent-7", "name": "Magnificent 7", "emoji": "👑",
     "symbols": ["AAPL", "MSFT", "NVDA", "GOOGL", "AMZN", "META", "TSLA"]},
    {"slug": "ai-chips", "name": "AI & Semiconductors", "emoji": "🧠",
     "symbols": ["NVDA", "AMD", "AVGO", "TSM", "ARM", "MU", "SMCI", "MRVL", "ASML", "PLTR", "ANET"]},
    {"slug": "popular-etfs", "name": "Popular ETFs", "emoji": "🧺",
     "symbols": ["SPY", "VOO", "VTI", "QQQ", "SCHD", "VGT", "ARKK", "SMH", "GLD", "TLT"]},
    {"slug": "dividends", "name": "Dividend favourites", "emoji": "💵",
     "symbols": ["KO", "PEP", "JNJ", "PG", "XOM", "CVX", "VZ", "T", "ABBV", "SCHD", "JEPI", "MCD"]},
    {"slug": "fintech", "name": "Fintech & brokers", "emoji": "💳",
     "symbols": ["HOOD", "SOFI", "PYPL", "XYZ", "AFRM", "NU", "COIN", "V", "MA", "SCHW"]},
    {"slug": "crypto", "name": "Crypto-linked", "emoji": "₿",
     "symbols": ["COIN", "MSTR", "MARA", "RIOT", "CLSK", "IBIT", "ETHA", "HOOD"]},
    {"slug": "ev", "name": "Electric vehicles", "emoji": "⚡",
     "symbols": ["TSLA", "RIVN", "LCID", "NIO", "GM", "F"]},
    {"slug": "quantum", "name": "Quantum computing", "emoji": "⚛️",
     "symbols": ["IONQ", "RGTI", "QBTS", "IBM", "GOOGL"]},
    {"slug": "travel", "name": "Travel & leisure", "emoji": "✈️",
     "symbols": ["DAL", "UAL", "AAL", "LUV", "CCL", "RCL", "NCLH", "MAR", "ABNB"]},
    {"slug": "banks", "name": "Big banks", "emoji": "🏦",
     "symbols": ["JPM", "BAC", "WFC", "C", "GS", "MS"]},
]


def screener(name: str, count: int = 12) -> list[dict]:
    key = f"screener:{name}"
    hit = cache.get(key)
    if hit is not None:
        return hit
    try:
        res = yf.screen(name, count=count)
        rows = [{"symbol": q["symbol"].replace("-", "."),
                 "name": q.get("shortName") or q.get("longName") or q["symbol"],
                 "price": q.get("regularMarketPrice"), "change_pct": q.get("regularMarketChangePercent"),
                 "volume": q.get("regularMarketVolume"), "market_cap": q.get("marketCap")}
                for q in res.get("quotes", [])]
    except Exception:
        log.info("screener %s failed", name, exc_info=True)
        rows = []
    known = set(Stock.objects.filter(symbol__in=[r["symbol"] for r in rows], is_active=True)
                .values_list("symbol", flat=True))
    rows = [r for r in rows if r["symbol"] in known]  # only tickers we can trade
    cache.set(key, rows, 60)
    return rows


def popular_on_platform(limit: int = 10) -> list[dict]:
    from apps.trading.models import Position

    rows = (Position.objects.filter(quantity__gt=0).values("stock__symbol", "stock__name")
            .annotate(holders=Count("account", distinct=True)).order_by("-holders")[:limit])
    return [{"symbol": r["stock__symbol"], "name": r["stock__name"], "holders": r["holders"]}
            for r in rows]
