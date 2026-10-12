from datetime import timedelta

from django.db.models import Q
from django.utils import timezone
from rest_framework.decorators import api_view
from rest_framework.response import Response

from apps.trading.models import Position

from .models import MarketEvent, NewsArticle
from .serializers import MarketEventSerializer, NewsArticleSerializer


def _news_for(symbols, limit=40):
    qs = NewsArticle.objects.prefetch_related("stocks").filter(published_at__lte=timezone.now())
    if symbols:
        from apps.market.models import Stock

        sectors = set(Stock.objects.filter(symbol__in=symbols).values_list("sector", flat=True))
        qs = qs.filter(Q(stocks__symbol__in=symbols) | Q(kind="macro") | Q(sector__in=sectors))
    return qs.distinct()[:limit]


@api_view(["GET"])
def news(request):
    symbol = request.query_params.get("symbol")
    symbols = [symbol.upper()] if symbol else []
    limit = min(int(request.query_params.get("limit", 40)), 100)
    return Response(NewsArticleSerializer(_news_for(symbols, limit), many=True).data)


@api_view(["GET"])
def portfolio_news(request):
    symbols = list(
        Position.objects.filter(account__user=request.user, quantity__gt=0)
        .values_list("stock__symbol", flat=True)
    )
    return Response(NewsArticleSerializer(_news_for(symbols, 40), many=True).data)


@api_view(["GET"])
def calendar(request):
    now = timezone.now()
    qs = MarketEvent.objects.select_related("stock").filter(
        ts__gte=now - timedelta(days=1), ts__lte=now + timedelta(days=30)
    )
    symbol = request.query_params.get("symbol")
    if symbol:
        qs = qs.filter(Q(stock__symbol=symbol.upper()) | Q(stock__isnull=True))
    return Response(MarketEventSerializer(qs[:100], many=True).data)
