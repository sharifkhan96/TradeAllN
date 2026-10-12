import pytest
from pydantic import ValidationError

from apps.rules.compiler import CompileError, compile_regex, compile_text
from apps.rules.evaluator import rsi, run_all, sma
from apps.rules.models import RuleExecution, TradingRule
from apps.rules.spec import RuleSpec, describe

from .conftest import set_price

pytestmark = pytest.mark.django_db(transaction=True)


def test_regex_compiles_percent_drop_buy(stocks):
    raw = compile_regex("if tesla drops 3% today, buy $1000")
    spec = RuleSpec.model_validate(raw)
    c = spec.condition.clauses[0]
    assert (c.metric, c.symbol, c.op, c.value) == ("pct_change", "TSLA", "<=", -3.0)
    assert spec.action.type == "buy_notional" and spec.action.amount == 1000


def test_regex_alert(stocks):
    spec = RuleSpec.model_validate(compile_regex("alert me when AAPL goes above 240"))
    assert spec.action.type == "notify"
    assert describe(spec)["when"]["items"] == ["AAPL price ≥ $240.00"]


def test_unknown_text_without_ai_gives_helpful_error(stocks, settings):
    settings.ANTHROPIC_API_KEY = ""
    with pytest.raises(CompileError, match="simple rules"):
        compile_text("when the 50 day crosses the 200 day buy some")


def test_spec_rejects_unsafe_shapes():
    with pytest.raises(ValidationError):
        RuleSpec.model_validate({"name": "x", "condition": {"logic": "all", "clauses": [
            {"metric": "price", "op": "<", "value": 1}]}, "action": {"type": "notify"}})  # no symbol
    with pytest.raises(ValidationError):
        RuleSpec.model_validate({"name": "x", "condition": {"logic": "all", "clauses": [
            {"metric": "eval('rm -rf')", "symbol": "AAPL", "op": "<", "value": 1}]},
            "action": {"type": "notify"}})


def test_indicators():
    assert sma([1, 2, 3, 4], 2) == 3.5
    assert rsi([float(i) for i in range(30)]) == 100.0
    assert rsi([1.0] * 5) is None


def test_rule_is_edge_triggered_and_fires_once(user, account):
    spec = RuleSpec.model_validate(compile_regex("if AAPL falls below 90, buy 2"))
    rule = TradingRule.objects.create(user=user, account=account, name=spec.name,
                                      spec=spec.model_dump(mode="json"))
    set_price("AAPL", 95.0)
    assert run_all() == 0
    set_price("AAPL", 89.0)
    import apps.rules.evaluator as ev

    ev._active_cache = (0.0, [])
    assert run_all() == 1
    assert run_all() == 0  # still true, but no new edge
    rule.refresh_from_db()
    assert rule.status == "triggered"
    ex = RuleExecution.objects.get(rule=rule)
    assert ex.success and ex.order.status == "filled"
