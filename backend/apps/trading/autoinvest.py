"""Recurring investments (auto-invest) and dividend payouts, run by the ingestor."""
import calendar
import logging
from datetime import UTC, date, datetime, timedelta
from decimal import ROUND_HALF_EVEN, Decimal

from django.core.cache import cache
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.market.hours import ET, is_trading_day

from .engine import OrderError, OrderRequest, submit_order
from .models import DividendPayment, LedgerEntry, Position, RecurringInvestment, TradingAccount

log = logging.getLogger(__name__)


def next_trading_day(d: date) -> date:
    d += timedelta(days=1)
    while not is_trading_day(d):
        d += timedelta(days=1)
    return d


def advance(d: date, frequency: str) -> date:
    if frequency == "daily":
        return next_trading_day(d)
    if frequency in ("weekly", "biweekly"):
        nd = d + timedelta(days=7 if frequency == "weekly" else 14)
    else:
        m = d.month % 12 + 1
        y = d.year + (d.month == 12)
        nd = d.replace(year=y, month=m, day=min(d.day, calendar.monthrange(y, m)[1]))
    while not is_trading_day(nd):
        nd += timedelta(days=1)
    return nd


def run_recurring(now: datetime | None = None) -> int:
    """Place today's scheduled buys (call while the market is open)."""
    now = now or timezone.now()
    today = now.astimezone(ET).date()
    n = 0
    for rec in RecurringInvestment.objects.filter(active=True, next_run__lte=today).select_related(
            "account", "stock"):
        req = OrderRequest(symbol=rec.stock.symbol, side="buy", type="market", notional=rec.amount,
                           source="recurring", client_order_id=f"rec-{rec.pk}-{today.isoformat()}")
        try:
            order = submit_order(rec.account, req)
            rec.last_result = f"Bought ${rec.amount} of {rec.stock.symbol} ({order.status})"
            if order.status in ("filled", "open"):
                rec.total_invested += rec.amount
        except OrderError as e:
            rec.last_result = f"Skipped: {e}"
        rec.last_run_at = now
        rec.next_run = advance(max(rec.next_run, today), rec.frequency)
        rec.save()
        n += 1
        from apps.realtime.notify import notify_user

        notify_user(rec.account.user_id, "recurring_run",
                    {"symbol": rec.stock.symbol, "message": rec.last_result})
    return n


def pay_dividends() -> int:
    """Credit real dividends (Yahoo history) for positions held on the ex-date."""
    import yfinance as yf

    from apps.market.providers.yahoo import ysym

    paid = 0
    held = (Position.objects.filter(quantity__gt=0).select_related("stock", "account")
            .exclude(stock__hydrated_at__isnull=True))
    by_symbol: dict[str, list[Position]] = {}
    for p in held:
        by_symbol.setdefault(p.stock.symbol, []).append(p)
    since = date.today() - timedelta(days=10)
    for sym, positions in by_symbol.items():
        key = f"divs:{sym}"
        divs = cache.get(key)
        if divs is None:
            try:
                s = yf.Ticker(ysym(sym)).dividends
                divs = [(ts.date(), float(v)) for ts, v in s.tail(6).items()]
            except Exception:
                divs = []
            cache.set(key, divs, 6 * 3600)
        for ex_date, per_share in divs:
            if ex_date < since or ex_date > date.today():
                continue
            for p in positions:
                if p.opened_at and p.opened_at.astimezone(ET).date() >= ex_date:
                    continue  # bought on/after the ex-date: not entitled
                amount = (p.quantity * Decimal(str(per_share))).quantize(Decimal("0.01"), ROUND_HALF_EVEN)
                if amount <= 0:
                    continue
                try:
                    with transaction.atomic():
                        acct = TradingAccount.objects.select_for_update().get(pk=p.account_id)
                        DividendPayment.objects.create(account=acct, stock=p.stock, ex_date=ex_date,
                                                       per_share=Decimal(str(per_share)),
                                                       quantity=p.quantity, amount=amount,
                                                       paid_at=datetime.now(UTC))
                        acct.cash_balance += amount
                        acct.save(update_fields=["cash_balance"])
                        LedgerEntry.objects.create(account=acct, type="dividend", amount=amount,
                                                   balance_after=acct.cash_balance,
                                                   reference=f"{sym} {ex_date}",
                                                   created_at=datetime.now(UTC))
                    paid += 1
                    from apps.realtime.notify import notify_user

                    notify_user(acct.user_id, "dividend",
                                {"symbol": sym, "amount": float(amount), "per_share": per_share})
                except IntegrityError:
                    continue  # already paid
    return paid
