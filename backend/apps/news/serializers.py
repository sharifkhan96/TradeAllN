from rest_framework import serializers

from .models import MarketEvent, NewsArticle


class NewsArticleSerializer(serializers.ModelSerializer):
    symbols = serializers.SerializerMethodField()

    class Meta:
        model = NewsArticle
        fields = ["id", "headline", "summary", "source", "url", "kind", "published_at",
                  "sentiment", "importance", "sector", "is_simulated", "symbols"]

    def get_symbols(self, obj):
        return [s.symbol for s in obj.stocks.all()]


class MarketEventSerializer(serializers.ModelSerializer):
    symbol = serializers.CharField(source="stock.symbol", default=None)

    class Meta:
        model = MarketEvent
        fields = ["id", "symbol", "kind", "ts", "title", "payload"]
