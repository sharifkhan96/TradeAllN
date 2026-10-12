"""Bar access + on-the-fly aggregation. Stored timeframes: 1m and 1d (1s bars live in Redis)."""
from datetime import UTC, datetime, timedelta

from django.utils import timezone

from . import quotes
from .hours import ET
from .models import PriceBar

MINUTE_AGG = {"1m": 1, "5m": 5, "15m": 15, "30m": 30, "1h": 60}
TIMEFRAMES = ["1s", "1m", "5m", "15m", "30m", "1h", "1d", "1w"]


def _row(ts: datetime, o, h, l, c, v):  # noqa: E741
    return {"t": int(ts.timestamp()), "o": float(o), "h": float(h), "l": float(l),
            "c": float(c), "v": int(v)}


def _aggregate(rows, bucket_of):
    out, cur, key = [], None, None
    for r in rows:
        k = bucket_of(r)
        if k != key:
            if cur:
                out.append(cur)
            key = k
            cur = dict(r)
            cur["t"] = k
        else:
            cur["h"] = max(cur["h"], r["h"])
            cur["l"] = min(cur["l"], r["l"])
            cur["c"] = r["c"]
            cur["v"] += r["v"]
    if cur:
        out.append(cur)
    return out


def get_bars(stock, timeframe: str, start: datetime | None = None, end: datetime | None = None,
             limit: int = 2000) -> list[dict]:
    if timeframe == "1s":
        rows = quotes.second_bars(stock.symbol, limit=min(limit, 3600))
        if start:
            rows = [r for r in rows if r["t"] >= start.timestamp()]
        if end:
            rows = [r for r in rows if r["t"] <= end.timestamp()]
        return rows
    if timeframe in MINUTE_AGG:
        n = MINUTE_AGG[timeframe]

        def load(tf, lo=None, cap=None):
            qs = PriceBar.objects.filter(stock=stock, timeframe=tf)
            if lo:
                qs = qs.filter(ts__gt=lo)
            if start:
                qs = qs.filter(ts__gte=start)
            if end:
                qs = qs.filter(ts__lte=end)
            raw = qs.order_by("-ts").values_list("ts", "open", "high", "low", "close", "volume")
            return [_row(*x) for x in reversed(list(raw[:cap] if cap else raw))]

        if n == 1:
            return load("1m", cap=limit)
        # Longer history lives in stored 5m bars (real data); newer minutes come from 1m bars.
        five = load("5m", cap=limit * n // 5 + 5) if n % 5 == 0 else []
        last5 = datetime.fromtimestamp(five[-1]["t"], UTC) if five else None
        ones = load("1m", lo=last5 + timedelta(minutes=4) if last5 else None,
                    cap=None if last5 else limit * n)
        rows = five + ones
        return _aggregate(rows, lambda r: r["t"] - (r["t"] % (n * 60)))[-limit:]
    qs = PriceBar.objects.filter(stock=stock, timeframe="1d")
    if start:
        qs = qs.filter(ts__gte=start)
    if end:
        qs = qs.filter(ts__lte=end)
    raw = list(qs.order_by("-ts").values_list("ts", "open", "high", "low", "close", "volume")
               [: limit * (5 if timeframe == "1w" else 1)])
    rows = [_row(*x) for x in reversed(raw)]
    if timeframe == "1w":

        def week(r):
            d = datetime.fromtimestamp(r["t"], ET)
            monday = (d - timedelta(days=d.weekday())).replace(hour=0, minute=0, second=0)
            return int(monday.timestamp())

        return _aggregate(rows, week)[-limit:]
    return rows


RANGES = {
    # range: (timeframe, lookback)
    "LIVE": ("1s", timedelta(minutes=15)),
    "1D": ("1m", timedelta(days=1)),
    "5D": ("5m", timedelta(days=7)),
    "1M": ("1h", timedelta(days=31)),
    "6M": ("1d", timedelta(days=183)),
    "1Y": ("1d", timedelta(days=366)),
    "2Y": ("1w", timedelta(days=731)),
}


def bars_for_range(stock, rng: str) -> tuple[str, list[dict]]:
    timeframe, lookback = RANGES.get(rng, RANGES["1D"])
    if rng == "1D":
        # a rolling session's worth of minute bars, so the chart is never empty at the open
        rows = get_bars(stock, "1m", limit=390)
        return (timeframe, rows) if rows else ("1d", get_bars(stock, "1d", limit=30))
    start = timezone.now() - lookback
    if timeframe == "1h":
        rows = get_bars(stock, "1h", start=start, limit=1000)
        if len(rows) < 40:  # not enough intraday history: fall back to daily
            return "1d", get_bars(stock, "1d", start=start)
        return timeframe, rows
    return timeframe, get_bars(stock, timeframe, start=start, limit=3000)
