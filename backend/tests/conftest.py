import json
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone

from apps.market import quotes
from apps.market.models import Stock


class FakeRedis:
    """In-memory stand-in for the quotes hash and 1s bar lists."""

    def __init__(self):
        self.h, self.lists = {}, {}

    def hset(self, key, field=None, value=None, mapping=None):
        d = self.h.setdefault(key, {})
        if mapping:
            d.update(mapping)
        else:
            d[field] = value

    def hget(self, key, field):
        return self.h.get(key, {}).get(field)

    def hmget(self, key, fields):
        return [self.h.get(key, {}).get(f) for f in fields]

    def hgetall(self, key):
        return dict(self.h.get(key, {}))

    def lrange(self, key, a, b):
        return self.lists.get(key, [])[a:] if b == -1 else self.lists.get(key, [])[a:b + 1]

    def pipeline(self):
        return self

    def rpush(self, key, v):
        self.lists.setdefault(key, []).append(v)

    def ltrim(self, *a):
        pass

    def execute(self):
        pass

    def delete(self, *keys):
        for k in keys:
            self.h.pop(k, None)


@pytest.fixture(autouse=True)
def fake_redis(monkeypatch):
    fr = FakeRedis()
    monkeypatch.setattr(quotes, "_client", fr)
    monkeypatch.setattr(quotes, "r", lambda: fr)
    return fr


def set_price(symbol, price, prev_close=None):
    prev_close = prev_close or price
    quotes.set_quote(symbol, {"symbol": symbol, "price": price, "prev_close": prev_close,
                              "open": prev_close, "high": price, "low": price, "volume": 1000,
                              "change": price - prev_close,
                              "change_pct": (price / prev_close - 1) * 100})


@pytest.fixture
def stocks(db):
    out = {}
    for sym, name, sector, etf in [("AAPL", "Apple Inc.", "Technology", "XLK"),
                                   ("TSLA", "Tesla, Inc.", "Consumer Discretionary", "XLY"),
                                   ("SPY", "SPDR S&P 500 ETF Trust", "", "")]:
        out[sym] = Stock.objects.create(symbol=sym, name=name, sector=sector,
                                        sector_etf=etf, is_etf=sym == "SPY", beta=Decimal("1.1"),
                                        is_popular=True, hydrated_at=timezone.now())
        set_price(sym, 100.0)
    from apps.market.resolve import reset_cache
    from apps.news.ingest import reset_tagger

    reset_cache()
    reset_tagger()
    return out


@pytest.fixture
def user(db, stocks):
    return get_user_model().objects.create_user(email="t@example.com", password="pw-123456789")


@pytest.fixture
def account(user):
    return user.accounts.first()


__all__ = ["set_price", "json"]
