"""Order validation, reservation, matching and fills (the simulated broker).

Every balance or position change happens inside `transaction.atomic()` with row locks
(`select_for_update`) on the account, position and order, so concurrent orders can't
double-spend and a fill can't race a cancel.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from decimal import ROUND_DOWN, ROUND_HALF_EVEN, Decimal

from django.conf import settings
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.market import hours, quotes
from apps.market.models import Stock
from apps.realtime.notify import notify_user

from .models import LedgerEntry, Order, Position, Trade, TradingAccount

log = logging.getLogger(__name__)
CENT = Decimal("0.01")
PRICE_Q = Decimal("0.0001")
BUY_BUFFER = Decimal("1.02")  # reserve 2% headroom for market/stop buys


class OrderError(Exception):
    pass


@dataclass
class OrderRequest:
    symbol: str
    side: str
    type: str = "market"
    quantity: Decimal | None = None
    notional: Decimal | None = None
    limit_price: Decimal | None = None
    stop_price: Decimal | None = None
    time_in_force: str = "day"
    client_order_id: str | None = None
    source: str = "manual"
    extended_hours: bool = False


def _d(x) -> Decimal | None:
    if x is None or x == "":
        return None
    return Decimal(str(x))


def _slip(price: Decimal, side: str) -> Decimal:
    bps = Decimal(settings.SIMULATED_SLIPPAGE_BPS) / Decimal(10_000)
    return (price * (1 + bps if side == "buy" else 1 - bps)).quantize(PRICE_Q, ROUND_HALF_EVEN)


SHARE_Q = Decimal("0.000001")  # fractional shares to 6 decimal places
MIN_NOTIONAL = Decimal("1.00")


def resolve_quantity(req: OrderRequest, price: Decimal) -> Decimal:
    if req.quantity is not None:
        qty = _d(req.quantity).quantize(SHARE_Q, ROUND_DOWN)
    elif req.notional is not None:
        if _d(req.notional) < MIN_NOTIONAL:
            raise OrderError(f"The minimum order is ${MIN_NOTIONAL}.")
        ref = _d(req.limit_price) or price
        qty = (_d(req.notional) / ref).quantize(SHARE_Q, ROUND_DOWN)
    else:
        raise OrderError("Provide a quantity or a dollar amount.")
    if qty <= 0:
        raise OrderError("Quantity must be greater than zero.")
    if qty != qty.to_integral_value() and req.type in ("stop", "stop_limit"):
        raise OrderError("Stop orders need whole shares.")
    if qty * price < Decimal("0.01"):
        raise OrderError("That order is too small.")
    return qty


def validate(req: OrderRequest, account: TradingAccount) -> tuple[Stock, Decimal, Decimal]:
    """Static checks shared by manual, assistant and rule orders. Returns stock, qty, last price."""
    if req.side not in ("buy", "sell"):
        raise OrderError("Side must be buy or sell.")
    if req.type not in dict(Order.TYPES):
        raise OrderError("Unknown order type.")
    if req.time_in_force not in ("day", "gtc"):
        raise OrderError("Time in force must be day or gtc.")
    stock = Stock.objects.filter(symbol=req.symbol.upper()).first()
    if not stock or not stock.is_active:
        raise OrderError(f"Unknown symbol {req.symbol.upper()}.")
    if not stock.is_tradable:
        raise OrderError(f"{stock.symbol} is not tradable right now.")
    price = quotes.last_price(stock.symbol)
    if price is None and not stock.hydrated_at and settings.MARKET_DATA_PROVIDER != "mock":
        from apps.market.hydrate import ensure_hydrated

        ensure_hydrated(stock)
        price = quotes.last_price(stock.symbol)
    if price is None:
        raise OrderError(f"No live price for {stock.symbol} yet.")
    limit, stop = _d(req.limit_price), _d(req.stop_price)
    if req.type in ("limit", "stop_limit") and not limit:
        raise OrderError("Limit price is required.")
    if req.type in ("stop", "stop_limit") and not stop:
        raise OrderError("Stop price is required.")
    for p in (limit, stop):
        if p is not None and (p <= 0 or p > price * 2 or p < price / 2):
            raise OrderError(f"Price ${p} is too far from the current price ${price:,.2f}.")
    if req.extended_hours and req.type != "limit":
        raise OrderError("Extended-hours trading supports limit orders only.")
    qty = resolve_quantity(req, price)
    return stock, qty, price


def estimate_cost(req: OrderRequest, qty: Decimal, price: Decimal) -> Decimal:
    ref = {
        "market": price * BUY_BUFFER,
        "limit": _d(req.limit_price),
        "stop": max(price, _d(req.stop_price) or price) * BUY_BUFFER,
        "stop_limit": _d(req.limit_price),
    }[req.type]
    return (qty * ref + settings.COMMISSION_PER_TRADE).quantize(CENT, ROUND_HALF_EVEN)


def submit_order(account: TradingAccount, req: OrderRequest) -> Order:
    if req.client_order_id:
        existing = Order.objects.filter(account=account, client_order_id=req.client_order_id).first()
        if existing:
            return existing
    stock, qty, price = validate(req, account)
    try:
        with transaction.atomic():
            acct = TradingAccount.objects.select_for_update().get(pk=account.pk)
            order = Order(
                account=acct, stock=stock, side=req.side, type=req.type,
                time_in_force=req.time_in_force, quantity=qty,
                limit_price=_d(req.limit_price), stop_price=_d(req.stop_price),
                client_order_id=req.client_order_id, source=req.source,
                extended_hours=req.extended_hours, notional=_d(req.notional),
            )
            if req.side == "buy":
                cost = estimate_cost(req, qty, price)
                if cost > acct.buying_power:
                    raise OrderError(
                        f"Insufficient buying power: need ${cost:,.2f}, "
                        f"have ${acct.buying_power:,.2f}."
                    )
                acct.reserved_cash += cost
                acct.save(update_fields=["reserved_cash"])
                order.reserved_amount = cost
            else:
                pos = Position.objects.select_for_update().filter(account=acct, stock=stock).first()
                available = (pos.quantity - pos.reserved_qty) if pos else Decimal(0)
                if qty > available:
                    raise OrderError(
                        f"You can sell at most {available.normalize():f} {stock.symbol} "
                        "(short selling isn't supported)."
                    )
                pos.reserved_qty += qty
                pos.save(update_fields=["reserved_qty"])
            order.save()
    except IntegrityError:
        return Order.objects.get(account=account, client_order_id=req.client_order_id)
    transaction.on_commit(lambda: _push(order))
    # Marketable orders execute immediately.
    try_execute(order.pk, price)
    order.refresh_from_db()
    return order


def _trigger_price(order: Order, price: Decimal) -> Decimal | None:
    """Returns the execution reference price if the order should fill at this price."""
    if order.type == "market":
        return price
    if order.type in ("stop", "stop_limit") and not order.stop_triggered:
        hit = price >= order.stop_price if order.side == "buy" else price <= order.stop_price
        if not hit:
            return None
        if order.type == "stop":
            return price
        Order.objects.filter(pk=order.pk).update(stop_triggered=True)
        order.stop_triggered = True
    if order.type == "stop":
        return price
    # limit or triggered stop-limit
    if order.side == "buy" and price <= order.limit_price:
        return min(price, order.limit_price)
    if order.side == "sell" and price >= order.limit_price:
        return max(price, order.limit_price)
    return None


def try_execute(order_id, price: Decimal, ext_price: Decimal | None = None) -> bool:
    order = Order.objects.select_related("stock").get(pk=order_id)
    if order.status not in Order.OPEN_STATES:
        return False
    if not hours.is_open():
        # Outside regular hours only extended-hours limit orders can trade, at extended prices.
        session = hours.status()["status"]
        if not (order.extended_hours and session in ("pre_market", "after_hours") and ext_price):
            return False
        price = ext_price
    ref = _trigger_price(order, price)
    if ref is None:
        return False
    fill_price = _slip(ref, order.side) if order.type in ("market", "stop") else ref
    if order.type == "limit" or order.type == "stop_limit":
        # never fill worse than the limit, even after slippage
        fill_price = min(fill_price, order.limit_price) if order.side == "buy" \
            else max(fill_price, order.limit_price)
    return fill(order.pk, fill_price)


def fill(order_id, fill_price: Decimal) -> bool:
    now = timezone.now()
    with transaction.atomic():
        order = Order.objects.select_for_update().select_related("stock").get(pk=order_id)
        if order.status not in Order.OPEN_STATES:
            return False
        acct = TradingAccount.objects.select_for_update().get(pk=order.account_id)
        pos, _ = Position.objects.select_for_update().get_or_create(
            account=acct, stock=order.stock, defaults={"opened_at": now}
        )
        qty = order.quantity - order.filled_qty
        notional = (qty * fill_price).quantize(CENT, ROUND_HALF_EVEN)
        commission = settings.COMMISSION_PER_TRADE
        realized = None
        if order.side == "buy":
            # Release the reservation, then charge the actual cost.
            acct.reserved_cash -= order.reserved_amount
            debit = notional + commission
            if debit > acct.cash_balance:
                acct.save(update_fields=["reserved_cash"])
                order.status, order.reject_reason = "rejected", "Insufficient cash at execution."
                order.reserved_amount = 0
                order.save()
                transaction.on_commit(lambda: _push(order))
                return False
            new_qty = pos.quantity + qty
            pos.avg_cost = ((pos.quantity * pos.avg_cost + qty * fill_price) / new_qty).quantize(
                PRICE_Q, ROUND_HALF_EVEN)
            if pos.quantity == 0:
                pos.opened_at = now
            pos.quantity = new_qty
            acct.cash_balance -= debit
            order.reserved_amount = 0
            entry_type, amount = "trade_buy", -debit
        else:
            realized = ((fill_price - pos.avg_cost) * qty).quantize(CENT, ROUND_HALF_EVEN) \
                - commission
            pos.quantity -= qty
            pos.reserved_qty -= qty
            pos.realized_pnl += realized
            credit = notional - commission
            acct.cash_balance += credit
            entry_type, amount = "trade_sell", credit
        pos.save()
        acct.save(update_fields=["cash_balance", "reserved_cash"])
        Trade.objects.create(order=order, account=acct, stock=order.stock, side=order.side,
                             quantity=qty, price=fill_price, commission=commission,
                             realized_pnl=realized, executed_at=now)
        LedgerEntry.objects.create(account=acct, type=entry_type, amount=amount,
                                   balance_after=acct.cash_balance, reference=str(order.pk),
                                   created_at=now)
        order.filled_qty = order.quantity
        order.avg_fill_price = fill_price
        order.status = "filled"
        order.filled_at = now
        order.save()
        transaction.on_commit(lambda: _push(order, filled=True))
    return True


def cancel_order(order: Order, reason: str = "", status: str = "cancelled") -> Order:
    with transaction.atomic():
        order = Order.objects.select_for_update().get(pk=order.pk)
        if order.status not in Order.OPEN_STATES:
            raise OrderError(f"Order is already {order.status}.")
        acct = TradingAccount.objects.select_for_update().get(pk=order.account_id)
        remaining = order.quantity - order.filled_qty
        if order.side == "buy":
            acct.reserved_cash -= order.reserved_amount
            acct.save(update_fields=["reserved_cash"])
            order.reserved_amount = 0
        else:
            pos = Position.objects.select_for_update().get(account=acct, stock=order.stock)
            pos.reserved_qty -= remaining
            pos.save(update_fields=["reserved_qty"])
        order.status = status
        order.reject_reason = reason
        order.save()
        transaction.on_commit(lambda: _push(order))
    return order


def process_ticks(prices: dict[str, Decimal], ext_prices: dict[str, Decimal] | None = None) -> int:
    """Called by the ingestor on every price update. Returns number of fills."""
    fills = 0
    ext_prices = ext_prices or {}
    open_orders = Order.objects.filter(status__in=Order.OPEN_STATES,
                                       stock__symbol__in=list(prices)).select_related("stock")
    for order in open_orders:
        try:
            if try_execute(order.pk, prices[order.stock.symbol], ext_prices.get(order.stock.symbol)):
                fills += 1
        except Exception:  # never let one bad order stop the tick loop
            log.exception("failed to process order %s", order.pk)
    return fills


def expire_day_orders(extended: bool = False) -> int:
    """At 4pm regular DAY orders expire; extended-hours DAY orders live until 8pm."""
    n = 0
    for order in Order.objects.filter(status__in=Order.OPEN_STATES, time_in_force="day",
                                      extended_hours=extended):
        try:
            cancel_order(order, "Day order expired at market close.", status="expired")
            n += 1
        except OrderError:
            pass
    return n


def _push(order: Order, filled: bool = False):
    from .serializers import OrderSerializer

    notify_user(order.account.user_id, "order_update",
                {"order": OrderSerializer(order).data, "filled": filled})
