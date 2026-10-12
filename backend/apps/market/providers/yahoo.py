"""Yahoo Finance (via yfinance): real prices, history, fundamentals and earnings. No API key.

Yahoo's data is for personal/non-commercial use. Intraday history limits: 1m = last 7 days,
5m = last 60 days; daily goes back decades.
"""
from __future__ import annotations

import logging
import math
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime

import pandas as pd
import yfinance as yf

from apps.market.hours import ET

log = logging.getLogger(__name__)

# Yahoo's sector names -> ours (and the matching SPDR sector ETF)
SECTOR_MAP = {
    "Technology": ("Technology", "XLK"),
    "Communication Services": ("Communication Services", "XLC"),
    "Consumer Cyclical": ("Consumer Discretionary", "XLY"),
    "Consumer Defensive": ("Consumer Staples", "XLP"),
    "Financial Services": ("Financials", "XLF"),
    "Healthcare": ("Health Care", "XLV"),
    "Energy": ("Energy", "XLE"),
    "Industrials": ("Industrials", "XLI"),
    "Basic Materials": ("Materials", "XLB"),
    "Real Estate": ("Real Estate", "XLRE"),
    "Utilities": ("Utilities", "XLU"),
}


@dataclass
class YBar:
    ts: datetime
    o: float
    h: float
    l: float  # noqa: E741
    c: float
    v: int


def _clean(x) -> float | None:
    try:
        f = float(x)
    except (TypeError, ValueError):
        return None
    return None if math.isnan(f) else f


def ysym(symbol: str) -> str:
    return symbol.replace(".", "-")


def profile(symbol: str) -> dict:
    """Name, sector, fundamentals and description for one ticker."""
    try:
        info = yf.Ticker(ysym(symbol)).info or {}
    except Exception:
        log.warning("yahoo profile failed for %s", symbol, exc_info=True)
        return {}
    sector, etf = SECTOR_MAP.get(info.get("sector") or "", (info.get("sector") or "", ""))
    is_etf = (info.get("quoteType") or "").upper() == "ETF"
    dy = _clean(info.get("dividendYield"))
    return {
        "name": info.get("longName") or info.get("shortName") or symbol,
        "exchange": {"NMS": "NASDAQ", "NGM": "NASDAQ", "NCM": "NASDAQ", "NYQ": "NYSE",
                     "PCX": "NYSE Arca", "ASE": "NYSE American"}.get(info.get("exchange"),
                                                                     info.get("exchange") or ""),
        "sector": "" if is_etf else sector,
        "sector_etf": "" if is_etf else etf,
        "industry": info.get("industry") or "",
        "market_cap": int(info["marketCap"]) if info.get("marketCap") else None,
        "pe_ratio": round(_clean(info.get("trailingPE")), 2) if _clean(info.get("trailingPE")) else None,
        # yfinance reports dividendYield already in percent for equities
        "dividend_yield": round(dy, 3) if dy is not None else None,
        "beta": round(_clean(info.get("beta")) or 1.0, 2),
        "description": (info.get("longBusinessSummary") or "")[:2000],
        "is_etf": is_etf,
        "ceo": ((info.get("companyOfficers") or [{}])[0].get("name") or "")[:120],
        "employees": info.get("fullTimeEmployees"),
        "website": (info.get("website") or "")[:200],
        "hq": ", ".join(x for x in [info.get("city"), info.get("state") or info.get("country")] if x)[:120],
        "has_data": bool(info.get("regularMarketPrice") or info.get("previousClose") or info.get("longName")),
    }


def profiles(symbols: list[str], workers: int = 6) -> dict[str, dict]:
    with ThreadPoolExecutor(workers) as ex:
        return dict(zip(symbols, ex.map(profile, symbols), strict=True))


def _frame_to_bars(df: pd.DataFrame, daily: bool) -> list[YBar]:
    out = []
    for ts, row in df.iterrows():
        o, h, lo, c = (_clean(row.get(k)) for k in ("Open", "High", "Low", "Close"))
        if None in (o, h, lo, c):
            continue
        if daily:
            ts = datetime.combine(ts.date(), datetime.min.time(), ET)  # midnight ET, like the sim
        else:
            ts = ts.to_pydatetime()
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=ET)
        out.append(YBar(ts, o, h, lo, c, int(_clean(row.get("Volume")) or 0)))
    return out


def download(symbols: list[str], period: str, interval: str,
             prepost: bool = False) -> dict[str, list[YBar]]:
    """Batch download bars. Returns {} for symbols Yahoo didn't return."""
    if not symbols:
        return {}
    ymap = {ysym(s): s for s in symbols}
    df = yf.download(list(ymap), period=period, interval=interval, group_by="ticker",
                     auto_adjust=False, progress=False, threads=True, prepost=prepost)
    out: dict[str, list[YBar]] = {}
    if df is None or df.empty:
        return out
    daily = interval in ("1d", "1wk")
    for ys, sym in ymap.items():
        try:
            sub = df[ys] if isinstance(df.columns, pd.MultiIndex) else df
        except KeyError:
            continue
        bars = _frame_to_bars(sub.dropna(how="all"), daily)
        if bars:
            out[sym] = bars
    return out


def earnings(symbol: str, limit: int = 12) -> list[dict]:
    """Past and upcoming earnings dates with EPS estimate / actual / surprise."""
    try:
        df = yf.Ticker(ysym(symbol)).get_earnings_dates(limit=limit)
    except Exception:
        log.info("no earnings dates for %s", symbol)
        return []
    if df is None or df.empty:
        return []
    out = []
    for ts, row in df.iterrows():
        out.append({
            "ts": ts.to_pydatetime(),
            "estimate": _clean(row.get("EPS Estimate")),
            "actual": _clean(row.get("Reported EPS")),
            "surprise_pct": _clean(row.get("Surprise(%)")),
        })
    return out


# --------------------------------------------------------------------------------------------
# Live polling
# --------------------------------------------------------------------------------------------
def _regular(ts: datetime) -> bool:
    t = ts.astimezone(ET).time()
    return datetime.strptime("09:30", "%H:%M").time() <= t < datetime.strptime("16:00", "%H:%M").time()


class YahooPoller:
    """Polls Yahoo in a background thread; the ingestor reads the latest snapshot every tick.

    "Hot" symbols (held, watched, recently viewed, open orders) refresh every `interval` seconds;
    "warm" ones (the popular list) every fourth cycle. Each refresh is two batched requests:
    1-minute bars including pre/after-hours (latest prints, chart bars, extended-hours prices)
    and recent daily bars (previous close, session open/high/low/volume).
    """

    provides_bars = True

    def __init__(self, hot: list[str], warm: list[str] | None = None, interval: int = 15):
        self.hot, self.warm = list(hot), list(warm or [])
        self.interval = interval
        self.prices: dict[str, float] = {}
        self.day: dict[str, dict] = {}
        self.minute_bars: dict[str, list[YBar]] = {}
        self.version = 0
        self.cycle = 0
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self.thread = threading.Thread(target=self._run, name="yahoo-poller", daemon=True)
        self.thread.start()

    def set_symbols(self, hot: list[str], warm: list[str]):
        new = [s for s in hot if s not in self.day]
        with self._lock:
            self.hot, self.warm = list(hot), [s for s in warm if s not in hot]
        if new:  # newly viewed/held tickers: fetch right away
            threading.Thread(target=self._refresh_safe, args=(new,), daemon=True).start()

    def stop(self):
        self._stop.set()

    def _refresh_safe(self, symbols):
        try:
            self.refresh(symbols)
        except Exception:
            log.warning("yahoo refresh failed", exc_info=True)

    def _run(self):
        from apps.market.hours import status

        while not self._stop.is_set():
            started = time.monotonic()
            with self._lock:
                syms = self.hot + (self.warm if self.cycle % 4 == 0 else [])
            self.cycle += 1
            for i in range(0, len(syms), 80):
                self._refresh_safe(syms[i:i + 80])
            # fast during the regular session, moderate in extended hours, slow overnight
            st = status()["status"]
            wait = self.interval if st == "open" else 60 if st in ("pre_market", "after_hours") else 600
            self._stop.wait(max(1.0, wait - (time.monotonic() - started)))

    def refresh(self, symbols: list[str]):
        daily = download(symbols, period="5d", interval="1d")
        minute = download(symbols, period="1d", interval="1m", prepost=True)
        day, prices, mins = {}, {}, {}
        for sym, bars in daily.items():
            last = bars[-1]
            prev = bars[-2].c if len(bars) > 1 else last.o
            day[sym] = {"session": last.ts.date().isoformat(), "prev_close": prev, "open": last.o,
                        "high": last.h, "low": last.l, "volume": last.v, "ext_price": None,
                        "ext_session": None}
            prices[sym] = last.c
        for sym, bars in minute.items():
            if not bars:
                continue
            mins[sym] = bars
            regular = [b for b in bars if _regular(b.ts)]
            d = day.get(sym)
            if regular:
                prices[sym] = regular[-1].c
                if d and regular[-1].ts.date().isoformat() == d["session"]:
                    d["high"] = max(d["high"], max(b.h for b in regular))
                    d["low"] = min(d["low"], min(b.l for b in regular))
            last = bars[-1]
            if d and not _regular(last.ts):
                d["ext_price"] = last.c
                # extended-hours change is measured against the last regular close
                d["ext_session"] = "pre" if last.ts.astimezone(ET).hour < 12 else "post"
        with self._lock:
            self.prices.update(prices)
            self.day.update(day)
            self.minute_bars.update(mins)
            self.version += 1

    def snapshot(self):
        with self._lock:
            return dict(self.prices), dict(self.day), dict(self.minute_bars), self.version
