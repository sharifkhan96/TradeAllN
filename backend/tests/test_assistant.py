from decimal import Decimal

import pytest

from apps.assistant import service
from apps.assistant.parser import parse_regex
from apps.trading.engine import OrderRequest, submit_order

pytestmark = pytest.mark.django_db(transaction=True)


@pytest.mark.parametrize("text,expected", [
    ("buy 10 aapl", ("AAPL", "buy", "shares", 10)),
    ("buy $500 of tesla", ("TSLA", "buy", "dollars", 500)),
    ("sell half my apple", ("AAPL", "sell", "pct_position", 50)),
    ("sell all tsla", ("TSLA", "sell", "all_position", None)),
])
def test_fast_path_orders(stocks, text, expected):
    r = parse_regex(text)
    o = r["orders"][0]
    assert (o["symbol"], o["side"], o["qty_type"], o["amount"]) == expected


def test_limit_and_tif(stocks):
    o = parse_regex("buy 5 aapl at 98.5 gtc")["orders"][0]
    assert o["order_type"] == "limit" and o["limit_price"] == 98.5 and o["time_in_force"] == "gtc"


def test_intents(stocks):
    assert parse_regex("if AAPL drops 5% buy 1")["intent"] == "rule"
    assert parse_regex("why is my portfolio down?")["intent"] == "question"
    assert parse_regex("cancel my tsla orders")["cancel"]["symbols"] == ["TSLA"]


def test_preview_then_confirm_executes_and_is_single_use(user, account):
    submit_order(account, OrderRequest(symbol="AAPL", side="buy", quantity=Decimal(10)))
    cmd = service.handle(user, "sell half my apple")
    item = cmd.preview["items"][0]
    assert item["quantity"] == 5 and not item.get("error")
    res = service.confirm(cmd)
    assert res["results"][0]["ok"]
    with pytest.raises(service.AssistantError):
        service.confirm(cmd)


def test_preview_flags_errors_instead_of_guessing(user):
    cmd = service.handle(user, "sell 5 tsla")
    assert "don't own any TSLA" in cmd.preview["items"][0]["error"]
    assert cmd.preview["executable"] is False
