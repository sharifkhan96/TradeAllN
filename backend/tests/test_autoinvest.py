from datetime import date
from decimal import Decimal

import pytest

from apps.trading.autoinvest import advance, run_recurring
from apps.trading.models import Order, RecurringInvestment

pytestmark = pytest.mark.django_db(transaction=True)


def test_schedule_skips_weekends_and_clamps_month_end():
    assert advance(date(2026, 10, 9), "daily") == date(2026, 10, 12)  # Fri -> Mon
    assert advance(date(2026, 1, 30), "monthly") == date(2026, 3, 2)  # Feb 28 is a Saturday
    assert advance(date(2026, 10, 12), "weekly") == date(2026, 10, 19)


def test_recurring_buys_fractional_dollar_amount_once_per_day(account, stocks):
    rec = RecurringInvestment.objects.create(account=account, stock=stocks["AAPL"], amount=Decimal("25"),
                                             frequency="weekly", next_run=date(2020, 1, 1))
    assert run_recurring() == 1
    o = Order.objects.get(source="recurring")
    assert o.quantity == Decimal("0.25") and o.status == "filled"
    rec.refresh_from_db()
    assert rec.next_run > date.today() and rec.total_invested == Decimal("25")
    assert run_recurring() == 0  # not due again
