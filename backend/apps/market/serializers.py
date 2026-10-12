from rest_framework import serializers

from . import quotes
from .models import Stock


class StockSerializer(serializers.ModelSerializer):
    quote = serializers.SerializerMethodField()

    class Meta:
        model = Stock
        fields = ["symbol", "name", "exchange", "sector", "industry", "is_etf", "quote"]

    def get_quote(self, obj):
        cache = self.context.get("quotes")
        return cache.get(obj.symbol) if cache is not None else quotes.get_quote(obj.symbol)


class StockDetailSerializer(StockSerializer):
    class Meta(StockSerializer.Meta):
        fields = StockSerializer.Meta.fields + [
            "description", "market_cap", "pe_ratio", "dividend_yield", "beta", "sector_etf",
            "is_tradable", "ceo", "employees", "website", "hq",
        ]
