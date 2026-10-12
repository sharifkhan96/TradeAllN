import threading
from decimal import Decimal

import pytest
from django.db import connection

from apps.trading.engine import OrderError, OrderRequest, cancel_order, process_ticks, submit_order
from apps.trading.models import LedgerEntry, Order, Position, TradingAccount

from .conftest import set_price

pytestmark = pytest.mark.django_db(transaction=True)


def test_market_buy_fills_and_updates_cash_position_ledger(account):
    o = submit_order(account, OrderRequest(symbol="AAPL", side="buy", quantity=Decimal(10)))
    assert o.status == "filled"
    account.refresh_from_db()
    pos = Position.objects.get(account=account, stock__symbol="AAPL")
    assert pos.quantity == 10
    # 5 bps slippage on a $100 buy
    assert o.avg_fill_price == Decimal("100.0500")
    assert account.cash_balance == Decimal("100000") - Decimal("1000.50")
    assert account.reserved_cash == 0
    assert sum(e.amount for e in LedgerEntry.objects.filter(account=account)) == account.cash_balance


def test_sell_more_than_held_is_rejected(account):
    submit_order(account, OrderRequest(symbol="AAPL", side="buy", quantity=Decimal(3)))
    with pytest.raises(OrderError, match="at most 3"):
        submit_order(account, OrderRequest(symbol="AAPL", side="sell", quantity=Decimal(4)))


def test_insufficient_buying_power(account):
    with pytest.raises(OrderError, match="Insufficient buying power"):
        submit_order(account, OrderRequest(symbol="AAPL", side="buy", quantity=Decimal(5000)))


def test_dollar_order_buys_fractional_shares(account):
    o = submit_order(account, OrderRequest(symbol="AAPL", side="buy", notional=Decimal(550)))
    assert o.quantity == Decimal("5.5") and o.status == "filled"
    o = submit_order(account, OrderRequest(symbol="AAPL", side="buy", notional=Decimal("10")))
    assert o.quantity == Decimal("0.1")


def test_extended_hours_limit_fills_on_extended_price(account, monkeypatch):
    from apps.market import hours

    monkeypatch.setattr(hours, "is_open", lambda now=None: False)
    monkeypatch.setattr(hours, "status", lambda now=None: {"status": "after_hours"})
    with pytest.raises(OrderError, match="limit orders only"):
        submit_order(account, OrderRequest(symbol="AAPL", side="buy", quantity=Decimal(1),
                                           extended_hours=True))
    o = submit_order(account, OrderRequest(symbol="AAPL", side="buy", type="limit", quantity=Decimal(1),
                                           limit_price=Decimal(99), extended_hours=True))
    assert o.status == "open"
    assert process_ticks({"AAPL": Decimal("100")}, {"AAPL": Decimal("98.5")}) == 1
    o.refresh_from_db()
    assert o.status == "filled" and o.avg_fill_price <= Decimal(99)


def test_limit_order_waits_then_fills_at_or_better(account):
    o = submit_order(account, OrderRequest(symbol="AAPL", side="buy", type="limit", quantity=Decimal(2),
                                           limit_price=Decimal(95)))
    assert o.status == "open"
    account.refresh_from_db()
    assert account.reserved_cash == Decimal("190.00")
    set_price("AAPL", 96.0)
    assert process_ticks({"AAPL": Decimal("96")}) == 0
    set_price("AAPL", 94.0)
    assert process_ticks({"AAPL": Decimal("94")}) == 1
    o.refresh_from_db()
    assert o.status == "filled" and o.avg_fill_price <= Decimal(95)
    account.refresh_from_db()
    assert account.reserved_cash == 0


def test_stop_loss_triggers_on_drop(account):
    submit_order(account, OrderRequest(symbol="AAPL", side="buy", quantity=Decimal(10)))
    o = submit_order(account, OrderRequest(symbol="AAPL", side="sell", type="stop", quantity=Decimal(10),
                                           stop_price=Decimal(90), time_in_force="gtc"))
    assert o.status == "open"
    process_ticks({"AAPL": Decimal("89")})
    o.refresh_from_db()
    assert o.status == "filled"
    pos = Position.objects.get(account=account, stock__symbol="AAPL")
    assert pos.quantity == 0 and pos.realized_pnl < 0


def test_cancel_releases_reservation(account):
    o = submit_order(account, OrderRequest(symbol="AAPL", side="buy", type="limit", quantity=Decimal(10),
                                           limit_price=Decimal(80)))
    cancel_order(o)
    account.refresh_from_db()
    assert account.reserved_cash == 0
    assert Order.objects.get(pk=o.pk).status == "cancelled"


def test_idempotent_client_order_id(account):
    a = submit_order(account, OrderRequest(symbol="AAPL", side="buy", quantity=Decimal(1), client_order_id="x1"))
    b = submit_order(account, OrderRequest(symbol="AAPL", side="buy", quantity=Decimal(1), client_order_id="x1"))
    assert a.pk == b.pk
    assert Order.objects.filter(account=account).count() == 1


def test_concurrent_buys_cannot_double_spend(account):
    """Two orders that each fit, but not together: exactly one may succeed."""
    TradingAccount.objects.filter(pk=account.pk).update(cash_balance=Decimal("1500"))
    results = []

    def buy():
        try:
            o = submit_order(TradingAccount.objects.get(pk=account.pk),
                             OrderRequest(symbol="AAPL", side="buy", type="limit", quantity=Decimal(10),
                                          limit_price=Decimal(99)))
            results.append(o.status)
        except OrderError:
            results.append("rejected")
        finally:
            connection.close()

    threads = [threading.Thread(target=buy) for _ in range(2)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    assert sorted(results) == ["filled", "rejected"] or sorted(results) == ["open", "rejected"] \
        or results.count("rejected") == 1
    account.refresh_from_db()
    assert account.cash_balance >= 0


def test_orders_wait_while_market_is_closed(account, monkeypatch):
    from apps.market import hours

    monkeypatch.setattr(hours, "is_open", lambda now=None: False)
    o = submit_order(account, OrderRequest(symbol="AAPL", side="buy", quantity=Decimal(1)))
    assert o.status == "open"  # queued for the opening bell
    assert process_ticks({"AAPL": Decimal("100")}) == 0
    monkeypatch.setattr(hours, "is_open", lambda now=None: True)
    assert process_ticks({"AAPL": Decimal("100")}) == 1
