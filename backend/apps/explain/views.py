from django.conf import settings
from django.shortcuts import get_object_or_404
from django.utils.dateparse import parse_datetime
from rest_framework.decorators import api_view
from rest_framework.response import Response

from apps.assistant import llm
from apps.market.bars import RANGES, TIMEFRAMES, bars_for_range, get_bars
from apps.market.models import Stock

from . import service
from .models import PriceMove


@api_view(["GET"])
def moves(request, symbol):
    """Detected moves with explanations, for chart markers and 'Story of the day'."""
    stock = get_object_or_404(Stock, symbol=symbol.upper())
    rng = request.query_params.get("range", "1D")
    if rng not in RANGES:
        return Response({"detail": f"range must be one of {list(RANGES)}"}, status=400)
    tf, bars = bars_for_range(stock, rng)
    mvs = service.build_moves(stock, tf, bars, persist=(tf != "1s"),
                              max_segments=12 if rng in ("LIVE", "1D") else 16)
    service.ensure_explained(stock, mvs, fetch_news=settings.MARKET_DATA_PROVIDER != "mock")
    return Response({"symbol": stock.symbol, "timeframe": tf, "range": rng,
                     "moves": [service.serialize_move(m) for m in mvs]})


@api_view(["POST"])
def deep_explain(request, pk):
    """Upgrade one move's explanation with Claude (falls back to rules)."""
    mv = get_object_or_404(PriceMove.objects.select_related("stock"), pk=pk)
    use_llm = llm.enabled() and request.user.ai_enabled
    if use_llm:
        try:
            llm.check_quota(request.user)
        except llm.LLMUnavailable as e:
            return Response({"detail": str(e)}, status=429)
    result = service.explain(mv.stock, mv, use_llm=use_llm, fetch_news=True)
    service.save_explanation(mv, result)
    return Response({**service.serialize_move(mv), "ai_available": llm.enabled()})


@api_view(["GET"])
def explain_range(request, symbol):
    """Explain any window the user drag-selects on the chart."""
    stock = get_object_or_404(Stock, symbol=symbol.upper())
    tf = request.query_params.get("timeframe", "5m")
    if tf not in TIMEFRAMES:
        return Response({"detail": "bad timeframe"}, status=400)
    start = parse_datetime(request.query_params.get("start") or "")
    end = parse_datetime(request.query_params.get("end") or "")
    if not start or not end or end <= start:
        return Response({"detail": "start and end (ISO 8601) are required"}, status=400)
    bars = get_bars(stock, tf, start=start, end=end, limit=5000)
    use_llm = llm.enabled() and request.user.ai_enabled
    if use_llm:
        try:
            llm.check_quota(request.user)
        except llm.LLMUnavailable:
            use_llm = False
    return Response({**service.explain_range(stock, tf, bars, use_llm),
                     "ai_used": use_llm, "timeframe": tf})
