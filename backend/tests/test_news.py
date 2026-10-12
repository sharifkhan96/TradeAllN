from datetime import UTC, datetime, timedelta

import pytest

from apps.news.classify import classify
from apps.news.ingest import ingest
from apps.news.models import NewsArticle
from apps.news.sources.base import RawItem


def test_classifier_kinds_and_sentiment():
    up = classify("Apple beats estimates and raises guidance")
    assert up["kind"] == "earnings" and up["sentiment"] > 0 and up["importance"] >= 0.7
    down = classify("Analyst downgrades Tesla to Underperform")
    assert down["kind"] == "analyst" and down["sentiment"] < 0
    assert classify("Fed holds rates as inflation cools")["kind"] == "macro"
    assert classify("3 stocks to buy now")["importance"] < 0.4


@pytest.mark.django_db
def test_ingest_dedupes_and_tags_mentioned_companies(stocks):
    now = datetime.now(UTC) - timedelta(minutes=5)
    items = [
        RawItem(headline="Apple and Tesla rally as tech rebounds", published_at=now, source="A",
                symbols=["AAPL"]),
        RawItem(headline="Apple and Tesla rally as tech rebounds!", published_at=now, source="B"),
        RawItem(headline="Gardening tips for autumn", published_at=now, source="C"),
    ]
    created = ingest(items)
    assert len(created) == 1  # duplicate merged, irrelevant item dropped
    art = NewsArticle.objects.get()
    assert set(art.stocks.values_list("symbol", flat=True)) == {"AAPL", "TSLA"}
    assert art.sentiment > 0
