"""Finnhub (free key): real-time US trade ticks over WebSocket, plus company/market news.

https://finnhub.io/docs/api/websocket-trades - the free tier streams up to 50 symbols.
"""
from __future__ import annotations

import json
import logging
import threading
import time
from datetime import UTC, date, datetime

import httpx
from django.conf import settings

log = logging.getLogger(__name__)
REST = "https://finnhub.io/api/v1"


def enabled() -> bool:
    return bool(settings.FINNHUB_API_KEY)


class FinnhubStream:
    """Keeps the last trade price per symbol, reconnecting with backoff."""

    def __init__(self, symbols: list[str]):
        self.symbols = symbols[:50]
        self.prices: dict[str, float] = {}
        self.last_trade_at = 0.0
        self._stop = threading.Event()
        threading.Thread(target=self._run, name="finnhub-ws", daemon=True).start()

    def stop(self):
        self._stop.set()

    def _run(self):
        from websockets.sync.client import connect

        backoff = 1
        while not self._stop.is_set():
            try:
                with connect(f"wss://ws.finnhub.io?token={settings.FINNHUB_API_KEY}",
                             open_timeout=10) as ws:
                    subscribed: set[str] = set()
                    backoff = 1
                    log.info("finnhub stream connected (%d symbols)", len(self.symbols))
                    while not self._stop.is_set():
                        want = set(self.symbols[:50])
                        for s in want - subscribed:
                            ws.send(json.dumps({"type": "subscribe", "symbol": s}))
                        for s in subscribed - want:
                            ws.send(json.dumps({"type": "unsubscribe", "symbol": s}))
                        subscribed = want
                        try:
                            msg = json.loads(ws.recv(timeout=30))
                        except TimeoutError:
                            ws.send(json.dumps({"type": "ping"}))
                            continue
                        if msg.get("type") == "trade":
                            for t in msg.get("data") or []:
                                self.prices[t["s"]] = float(t["p"])
                            self.last_trade_at = time.time()
            except Exception:
                log.warning("finnhub stream dropped; retrying in %ss", backoff, exc_info=True)
                self._stop.wait(backoff)
                backoff = min(backoff * 2, 60)


def _get(path: str, **params):
    r = httpx.get(f"{REST}{path}", params={**params, "token": settings.FINNHUB_API_KEY}, timeout=15)
    r.raise_for_status()
    return r.json()


def company_news(symbol: str, start: date, end: date) -> list[dict]:
    return _get("/company-news", symbol=symbol, **{"from": start.isoformat(), "to": end.isoformat()})


def market_news() -> list[dict]:
    return _get("/news", category="general")


def ts(epoch: int) -> datetime:
    return datetime.fromtimestamp(epoch, UTC)
