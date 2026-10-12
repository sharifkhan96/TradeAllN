from datetime import date, timedelta

from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.decorators import api_view, throttle_classes
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle

from .engine import OrderError, OrderRequest, cancel_order, submit_order
from .models import Order, Trade
from .serializers import (
    AccountSerializer,
    LedgerSerializer,
    OrderCreateSerializer,
    OrderSerializer,
    TradeSerializer,
)
from .services import primary_account, reset_account


class OrderThrottle(ScopedRateThrottle):
    scope = "orders"

    def get_cache_key(self, request, view):
        if request.method != "POST":
            return None
        return self.cache_format % {"scope": self.scope, "ident": request.user.pk}


@api_view(["GET"])
def accounts(request):
    primary_account(request.user)
    return Response(AccountSerializer(request.user.accounts.all(), many=True).data)


@api_view(["POST"])
def reset(request):
    reset_account(primary_account(request.user))
    return Response(AccountSerializer(primary_account(request.user)).data)


@api_view(["GET", "POST"])
@throttle_classes([OrderThrottle])
def orders(request):
    account = primary_account(request.user)
    if request.method == "POST":
        ser = OrderCreateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        try:
            order = submit_order(account, OrderRequest(**ser.validated_data))
        except OrderError as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(OrderSerializer(order).data, status=status.HTTP_201_CREATED)
    qs = Order.objects.filter(account=account).select_related("stock")
    st = request.query_params.get("status")
    if st == "open":
        qs = qs.filter(status__in=Order.OPEN_STATES)
    elif st:
        qs = qs.filter(status__in=st.split(","))
    if sym := request.query_params.get("symbol"):
        qs = qs.filter(stock__symbol=sym.upper())
    return Response(OrderSerializer(qs[:200], many=True).data)


@api_view(["GET", "DELETE"])
def order_detail(request, pk):
    order = get_object_or_404(Order, pk=pk, account__user=request.user)
    if request.method == "DELETE":
        try:
            order = cancel_order(order, "Cancelled by user.")
        except OrderError as e:
            return Response({"detail": str(e)}, status=400)
    return Response(OrderSerializer(order).data)


@api_view(["GET"])
def trades(request):
    qs = Trade.objects.filter(account__user=request.user).select_related("stock")
    if sym := request.query_params.get("symbol"):
        qs = qs.filter(stock__symbol=sym.upper())
    return Response(TradeSerializer(qs[:300], many=True).data)


@api_view(["GET"])
def ledger(request):
    acct = primary_account(request.user)
    return Response(LedgerSerializer(acct.ledger.all()[:300], many=True).data)


def _rec(r):
    return {"id": r.id, "symbol": r.stock.symbol, "name": r.stock.name, "amount": str(r.amount),
            "frequency": r.frequency, "next_run": r.next_run, "active": r.active,
            "last_run_at": r.last_run_at, "last_result": r.last_result,
            "total_invested": str(r.total_invested), "created_at": r.created_at}


@api_view(["GET", "POST"])
def recurring(request):
    from decimal import Decimal, InvalidOperation

    from django.utils import timezone

    from apps.market.hours import ET
    from apps.market.models import Stock

    from .autoinvest import next_trading_day
    from .models import RecurringInvestment

    account = primary_account(request.user)
    if request.method == "GET":
        return Response([_rec(r) for r in RecurringInvestment.objects.filter(account=account)
                         .select_related("stock")])
    sym = (request.data.get("symbol") or "").upper()
    stock = Stock.objects.filter(symbol=sym, is_active=True).first()
    if not stock:
        return Response({"detail": f"Unknown symbol {sym}."}, status=400)
    try:
        amount = Decimal(str(request.data.get("amount")))
    except (InvalidOperation, TypeError):
        return Response({"detail": "Enter an amount."}, status=400)
    if amount < 1 or amount > 100000:
        return Response({"detail": "Amount must be between $1 and $100,000."}, status=400)
    freq = request.data.get("frequency", "weekly")
    if freq not in dict(RecurringInvestment.FREQUENCIES):
        return Response({"detail": "Unknown frequency."}, status=400)
    today = timezone.now().astimezone(ET).date()
    start = request.data.get("start")
    first = date.fromisoformat(start) if start else next_trading_day(today - timedelta(days=1))
    r = RecurringInvestment.objects.create(account=account, stock=stock, amount=amount,
                                           frequency=freq, next_run=first)
    return Response(_rec(r), status=201)


@api_view(["PATCH", "DELETE"])
def recurring_detail(request, pk):
    from .models import RecurringInvestment

    r = get_object_or_404(RecurringInvestment, pk=pk, account__user=request.user)
    if request.method == "DELETE":
        r.delete()
        return Response(status=204)
    if "active" in request.data:
        r.active = bool(request.data["active"])
    r.save()
    return Response(_rec(r))


@api_view(["GET"])
def dividends(request):
    from .models import DividendPayment

    acct = primary_account(request.user)
    rows = DividendPayment.objects.filter(account=acct).select_related("stock")[:200]
    return Response([{"symbol": d.stock.symbol, "ex_date": d.ex_date, "per_share": str(d.per_share),
                      "quantity": str(d.quantity), "amount": str(d.amount), "paid_at": d.paid_at}
                     for d in rows])
