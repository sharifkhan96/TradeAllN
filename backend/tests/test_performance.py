from decimal import Decimal

import pytest

from apps.portfolio.performance import performance
from apps.trading.engine import OrderRequest, submit_order

from .conftest import set_price

pytestmark = pytest.mark.django_db(transaction=True)


def _round_trip(account, symbol, buy, sell, qty=10):
    set_price(symbol, buy)
    submit_order(account, OrderRequest(symbol=symbol, side="buy", quantity=Decimal(qty)))
    set_price(symbol, sell)
    submit_order(account, OrderRequest(symbol=symbol, side="sell", quantity=Decimal(qty)))


def test_win_rate_profit_factor_expectancy_and_streaks(account, settings):
    settings.SIMULATED_SLIPPAGE_BPS = 0
    _round_trip(account, "AAPL", 100, 110)   # +100
    _round_trip(account, "AAPL", 100, 95)    # -50
    _round_trip(account, "TSLA", 100, 120)   # +200
    _round_trip(account, "TSLA", 100, 130)   # +300
    s = performance(account)["summary"]
    assert (s["closed_trades"], s["wins"], s["losses"]) == (4, 3, 1)
    assert s["win_rate_pct"] == 75
    assert s["net_pnl"] == pytest.approx(550)
    assert s["profit_factor"] == pytest.approx(600 / 50)
    assert s["expectancy"] == pytest.approx(137.5)
    assert s["avg_loss"] == pytest.approx(-50)
    assert s["largest_win"]["symbol"] == "TSLA" and s["largest_win"]["pnl"] == pytest.approx(300)
    assert s["max_win_streak"] == 2 and s["max_loss_streak"] == 1
    assert s["current"] == {"kind": "win", "length": 2}


def test_no_trades_is_empty_not_an_error(account):
    p = performance(account, "30d")
    assert p["summary"]["closed_trades"] == 0 and p["summary"]["win_rate_pct"] is None
