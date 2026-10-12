"""Alpaca Market Data (REST). Used when MARKET_DATA_PROVIDER=alpaca.

Polls latest trades for the tracked universe; history can be loaded with
`python manage.py load_alpaca_history`. Requires ALPACA_API_KEY / ALPACA_API_SECRET.
"""
import logging

import httpx
from django.conf import settings

log = logging.getLogger(__name__)
BASE = "https://data.alpaca.markets"


def _client() -> httpx.Client:
    if not settings.ALPACA_API_KEY:
        raise RuntimeError("ALPACA_API_KEY is not set")
    return httpx.Client(base_url=BASE, timeout=10, headers={
        "APCA-API-KEY-ID": settings.ALPACA_API_KEY,
        "APCA-API-SECRET-KEY": settings.ALPACA_API_SECRET,
    })


def latest_trades(symbols: list[str]) -> dict[str, float]:
    with _client() as c:
        r = c.get("/v2/stocks/trades/latest",
                  params={"symbols": ",".join(symbols), "feed": settings.ALPACA_DATA_FEED})
        r.raise_for_status()
        return {s: t["p"] for s, t in r.json().get("trades", {}).items()}


def bars(symbol: str, timeframe: str, start: str, end: str | None = None) -> list[dict]:
    """timeframe: '1Min' or '1Day'. Returns Alpaca bar dicts (t, o, h, l, c, v)."""
    out, token = [], None
    with _client() as c:
        while True:
            params = {"timeframe": timeframe, "start": start, "limit": 10000,
                      "feed": settings.ALPACA_DATA_FEED, "adjustment": "split"}
            if end:
                params["end"] = end
            if token:
                params["page_token"] = token
            r = c.get(f"/v2/stocks/{symbol}/bars", params=params)
            r.raise_for_status()
            data = r.json()
            out.extend(data.get("bars") or [])
            token = data.get("next_page_token")
            if not token:
                return out


def news(symbols: list[str], start: str, limit: int = 50) -> list[dict]:
    with _client() as c:
        r = c.get("/v1beta1/news", params={"symbols": ",".join(symbols), "start": start,
                                           "limit": limit, "sort": "desc"})
        r.raise_for_status()
        return r.json().get("news", [])


class AlpacaPoller:
    def __init__(self, symbols: list[str]):
        self.symbols = symbols
        self.last: dict[str, float] = {}

    def poll(self) -> dict[str, float]:
        try:
            self.last.update(latest_trades(self.symbols))
        except Exception:
            log.warning("alpaca poll failed", exc_info=True)
        return dict(self.last)
