from datetime import timedelta

from django.conf import settings
from django.core.cache import cache
from django.db.models import Avg, Max, Min, Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from . import hours, insights, quotes
from .bars import RANGES, TIMEFRAMES, bars_for_range, get_bars
from .hydrate import ensure_hydrated, note_viewed
from .models import PriceBar, Stock
from .serializers import StockDetailSerializer, StockSerializer
from .universe import SECTOR_ETFS


@api_view(["GET"])
def stock_list(request):
    """Search every US-listed stock and ETF. Popular / loaded tickers rank first."""
    q = (request.query_params.get("search") or "").strip()
    limit = min(int(request.query_params.get("limit", 20)), 100)
    qs = Stock.objects.filter(is_active=True, is_tradable=True)
    if q:
        up = q.upper()
        cands = list(qs.filter(Q(symbol__istartswith=q) | Q(name__icontains=q))
                     .only("symbol", "name", "exchange", "sector", "industry", "is_etf",
                           "is_popular", "hydrated_at")[:400])
        words = q.lower()

        def rank(s):
            return (s.symbol != up, not s.symbol.startswith(up),
                    not s.name.lower().startswith(words), not s.is_popular,
                    s.hydrated_at is None, len(s.symbol), s.symbol)

        rows = sorted(cands, key=rank)[:limit]
    else:
        rows = list(qs.filter(is_popular=True).order_by("symbol")[:limit])
    ctx = {"quotes": quotes.get_quotes([s.symbol for s in rows])}
    return Response(StockSerializer(rows, many=True, context=ctx).data)


@api_view(["GET"])
def stock_detail(request, symbol):
    stock = get_object_or_404(Stock, symbol=symbol.upper(), is_active=True)
    if settings.MARKET_DATA_PROVIDER != "mock":
        if not ensure_hydrated(stock):
            return Response({"detail": f"No market data available for {stock.symbol} right now."},
                            status=503)
        note_viewed(stock.symbol)
    data = StockDetailSerializer(stock).data
    year = PriceBar.objects.filter(stock=stock, timeframe="1d",
                                   ts__gte=timezone.now() - timedelta(days=365))
    agg = year.aggregate(hi=Max("high"), lo=Min("low"))
    avg_vol = (PriceBar.objects.filter(stock=stock, timeframe="1d",
                                       ts__gte=timezone.now() - timedelta(days=45))
               .aggregate(v=Avg("volume"))["v"])
    data["stats"] = {
        "week52_high": float(agg["hi"]) if agg["hi"] else None,
        "week52_low": float(agg["lo"]) if agg["lo"] else None,
        "avg_volume": int(avg_vol) if avg_vol else None,
    }
    if stock.sector:
        base = Stock.objects.filter(is_etf=False, hydrated_at__isnull=False).exclude(pk=stock.pk)
        peers = list(base.filter(industry=stock.industry)[:6]) if stock.industry else []
        if len(peers) < 4:
            peers += list(base.filter(sector=stock.sector).exclude(pk__in=[p.pk for p in peers])
                          .order_by("-market_cap")[: 6 - len(peers)])
        ctx = {"quotes": quotes.get_quotes([p.symbol for p in peers])}
        data["peers"] = StockSerializer(peers, many=True, context=ctx).data
    return Response(data)


@api_view(["GET"])
def stock_quote(request, symbol):
    q = quotes.get_quote(symbol)
    return Response(q or {"detail": "No quote"}, status=200 if q else 404)


@api_view(["GET"])
def stock_bars(request, symbol):
    from django.utils.dateparse import parse_datetime

    stock = get_object_or_404(Stock, symbol=symbol.upper())
    rng = request.query_params.get("range")
    if rng:
        if rng not in RANGES:
            return Response({"detail": f"range must be one of {list(RANGES)}"}, status=400)
        tf, rows = bars_for_range(stock, rng)
        return Response({"symbol": stock.symbol, "timeframe": tf, "range": rng, "bars": rows})
    tf = request.query_params.get("timeframe", "1d")
    if tf not in TIMEFRAMES:
        return Response({"detail": f"timeframe must be one of {TIMEFRAMES}"}, status=400)
    start = parse_datetime(request.query_params.get("from") or "") or None
    end = parse_datetime(request.query_params.get("to") or "") or None
    limit = min(int(request.query_params.get("limit", 1000)), 5000)
    return Response({"symbol": stock.symbol, "timeframe": tf,
                     "bars": get_bars(stock, tf, start, end, limit)})


@api_view(["GET"])
def market_status(request):
    return Response(hours.status())


@api_view(["GET"])
def market_overview(request):
    allq = quotes.all_quotes()
    names = dict(Stock.objects.filter(Q(is_popular=True) | Q(is_etf=True), is_active=True)
                 .values_list("symbol", "name"))
    base = Stock.objects.filter(is_etf=False, is_active=True)
    if settings.MARKET_DATA_PROVIDER != "mock":
        base = base.filter(is_popular=True, hydrated_at__isnull=False)
    sector_of = dict(base.values_list("symbol", "sector"))

    def row(sym):
        q = allq.get(sym)
        return {"symbol": sym, "name": names.get(sym, sym), **(q or {})} if q else None

    eq = [row(s) for s in sector_of if s in allq]
    by_change = sorted(eq, key=lambda r: r["change_pct"])
    return Response({
        "status": hours.status(),
        "indices": [row(s) for s in ["SPY", "QQQ", "DIA", "IWM"] if s in allq],
        "sectors": [{**row(etf), "sector": sector} for sector, etf in SECTOR_ETFS.items()
                    if etf in allq],
        "gainers": list(reversed(by_change[-6:])),
        "losers": by_change[:6],
        "active": sorted(eq, key=lambda r: -r.get("volume", 0))[:6],
        "heatmap": [{**r, "sector": sector_of[r["symbol"]]} for r in eq],
    })


@api_view(["GET"])
def stock_insights(request, symbol):
    stock = get_object_or_404(Stock, symbol=symbol.upper(), is_active=True)
    if settings.MARKET_DATA_PROVIDER == "mock":
        return Response({"symbol": stock.symbol, "unavailable": True})
    return Response(insights.insights(stock))


@api_view(["GET"])
def batch_quotes(request):
    syms = [s for s in (request.query_params.get("symbols") or "").upper().split(",") if s]
    return Response(insights.snapshot(syms))


@api_view(["GET"])
def discover(request):
    lists = []
    all_syms = {s for c in insights.COLLECTIONS for s in c["symbols"]}
    names = dict(Stock.objects.filter(symbol__in=all_syms).values_list("symbol", "name"))
    qs = insights.snapshot(list(all_syms)) if settings.MARKET_DATA_PROVIDER != "mock" else \
        quotes.get_quotes(list(all_syms))
    for c in insights.COLLECTIONS:
        items = [{"symbol": s, "name": names.get(s, s), "quote": qs.get(s)} for s in c["symbols"]
                 if s in names]
        ch = [i["quote"]["change_pct"] for i in items if i["quote"]]
        lists.append({**{k: c[k] for k in ("slug", "name", "emoji")}, "items": items,
                      "avg_change_pct": sum(ch) / len(ch) if ch else None})
    real = settings.MARKET_DATA_PROVIDER != "mock"
    return Response({
        "gainers": insights.screener("day_gainers") if real else [],
        "losers": insights.screener("day_losers") if real else [],
        "active": insights.screener("most_actives") if real else [],
        "popular": insights.popular_on_platform(),
        "collections": lists,
        "status": hours.status(),
    })


# Parqet serves full-colour brand tiles; FMP (transparent PNGs) is the fallback.
LOGO_SOURCES = ["https://assets.parqet.com/logos/symbol/{s}?format=png",
                "https://financialmodelingprep.com/image-stock/{s}.png"]


@api_view(["GET"])
@authentication_classes([])
@permission_classes([AllowAny])
def logo(request, symbol):
    """Company logos, proxied and cached so the browser never calls third parties directly."""
    import httpx

    sym = symbol.upper().replace(".", "-")[:12]
    key = f"logo:{sym}"
    hit = cache.get(key)
    if hit == b"":
        return HttpResponse(status=404)
    if hit is None:
        hit = b""
        for url in LOGO_SOURCES:
            try:
                r = httpx.get(url.format(s=sym), timeout=6, follow_redirects=True,
                              headers={"User-Agent": "Mozilla/5.0"})
                if r.status_code == 200 and r.headers.get("content-type", "").startswith("image") \
                        and len(r.content) > 200:
                    hit = r.content
                    break
            except httpx.HTTPError:
                continue
        cache.set(key, hit, 7 * 86400 if hit else 86400)
        if not hit:
            return HttpResponse(status=404)
    resp = HttpResponse(hit, content_type="image/png")
    resp["Cache-Control"] = "public, max-age=604800"
    return resp
