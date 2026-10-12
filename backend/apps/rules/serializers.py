from .models import TradingRule
from .spec import RuleSpec, describe


def serialize_rule(rule: TradingRule, with_executions: bool = False) -> dict:
    try:
        readable = describe(RuleSpec.model_validate(rule.spec))
    except Exception:
        readable = None
    data = {
        "id": rule.id, "name": rule.name, "source_text": rule.source_text, "spec": rule.spec,
        "readable": readable, "status": rule.status, "status_message": rule.status_message,
        "last_condition": rule.last_condition, "last_evaluated_at": rule.last_evaluated_at,
        "last_triggered_at": rule.last_triggered_at, "trigger_count": rule.trigger_count,
        "expires_at": rule.expires_at, "created_at": rule.created_at,
    }
    if with_executions:
        data["executions"] = [
            {"id": e.id, "triggered_at": e.triggered_at, "result": e.result, "success": e.success,
             "order_id": e.order_id, "snapshot": e.snapshot}
            for e in rule.executions.all()[:50]
        ]
    return data
