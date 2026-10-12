from rest_framework.decorators import api_view
from rest_framework.response import Response

from apps.trading.services import primary_account

from . import services


@api_view(["GET"])
def summary(request):
    return Response(services.summary(primary_account(request.user)))


@api_view(["GET"])
def positions(request):
    return Response(services.positions(primary_account(request.user)))


@api_view(["GET"])
def history(request):
    return Response(services.history(primary_account(request.user)))


@api_view(["GET"])
def analytics(request):
    return Response(services.analytics(primary_account(request.user)))


@api_view(["GET"])
def performance(request):
    from .performance import PERIODS
    from .performance import performance as perf

    period = request.query_params.get("period", "all")
    if period not in {*PERIODS, "ytd", "all"}:
        return Response({"detail": "period must be 30d, 90d, ytd, 1y or all"}, status=400)
    return Response(perf(primary_account(request.user), period))
