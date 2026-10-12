"""Latest quotes live in Redis so every process (API, ingestor, workers) shares them."""
import json
from decimal import Decimal

import redis
from django.conf import settings

_client = None


def r() -> redis.Redis:
    global _client
    if _client is None:
        _client = redis.Redis.from_url(settings.REDIS_URL, decode_responses=True)
    return _client


def set_quote(symbol: str, quote: dict) -> None:
    r().hset("quotes", symbol, json.dumps(quote))


def get_quote(symbol: str) -> dict | None:
    raw = r().hget("quotes", symbol.upper())
    return json.loads(raw) if raw else None


def get_quotes(symbols) -> dict[str, dict]:
    symbols = [s.upper() for s in symbols]
    if not symbols:
        return {}
    return {s: json.loads(v) for s, v in zip(symbols, r().hmget("quotes", symbols), strict=True) if v}


def all_quotes() -> dict[str, dict]:
    return {k: json.loads(v) for k, v in r().hgetall("quotes").items()}


def last_price(symbol: str) -> Decimal | None:
    q = get_quote(symbol)
    return Decimal(str(q["price"])) if q else None


def push_second_bar(symbol: str, bar: dict, keep: int = 3600) -> None:
    key = f"bars1s:{symbol}"
    pipe = r().pipeline()
    pipe.rpush(key, json.dumps(bar))
    pipe.ltrim(key, -keep, -1)
    pipe.execute()


def second_bars(symbol: str, limit: int = 900) -> list[dict]:
    return [json.loads(x) for x in r().lrange(f"bars1s:{symbol.upper()}", -limit, -1)]
