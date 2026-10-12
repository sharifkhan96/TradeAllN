from datetime import UTC, datetime, timedelta

import pytest

from apps.explain.detection import segment
from apps.explain.service import candidates
from apps.news.models import NewsArticle


def _bars(prices, start=1_700_000_000, step=60):
    return [{"t": start + i * step, "o": p, "h": p, "l": p, "c": p, "v": 100}
            for i, p in enumerate(prices)]


def test_segments_find_a_jump_and_quiet_periods():
    import random

    rnd = random.Random(1)
    prices, p = [], 100.0
    for i in range(200):
        p *= 1 + rnd.gauss(0, 0.0005) + (0.03 if i == 120 else 0)
        prices.append(p)
    segs = segment(_bars(prices))
    big = max(segs, key=lambda s: abs(s.pct))
    assert big.direction == "up" and big.i0 <= 120 <= big.i1
    assert big.pct > 2.5


@pytest.mark.django_db
def test_no_lookahead_news_after_move_is_excluded(stocks):
    aapl = stocks["AAPL"]
    start = datetime(2026, 1, 5, 15, 0, tzinfo=UTC)
    end = start + timedelta(minutes=30)
    before = NewsArticle.objects.create(headline="before", source="s", published_at=start - timedelta(minutes=5),
                                        dedupe_hash="a")
    after = NewsArticle.objects.create(headline="after", source="s", published_at=end + timedelta(minutes=10),
                                       dedupe_hash="b")
    before.stocks.add(aapl)
    after.stocks.add(aapl)
    got = {a.headline for a in candidates(aapl, start, end, "1m")}
    assert got == {"before"}
