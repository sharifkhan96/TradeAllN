from datetime import timedelta

from django.conf import settings
from django.shortcuts import get_object_or_404
from django.utils import timezone
from pydantic import ValidationError
from rest_framework.decorators import api_view
from rest_framework.response import Response

from apps.trading.services import primary_account

from .compiler import CompileError, compile_text
from .evaluator import backtest, evaluate
from .models import TradingRule
from .serializers import serialize_rule
from .spec import RuleSpec, describe


def _preview(spec: RuleSpec, user, method: str, text: str = "") -> dict:
    probe = TradingRule(user=user, account=primary_account(user), spec=spec.model_dump(mode="json"))
    try:
        now_true, snapshot = evaluate(probe)
    except Exception:
        now_true, snapshot = False, {}
    return {"spec": spec.model_dump(mode="json"), "readable": describe(spec), "method": method,
            "source_text": text, "currently_true": now_true, "snapshot": snapshot,
            "backtest": backtest(spec)}


@api_view(["POST"])
def compile_rule(request):
    """Plain English -> validated rule + readable form + backtest. Does not activate it."""
    text = request.data.get("text", "")
    try:
        spec, method = compile_text(text, request.user)
    except CompileError as e:
        return Response({"detail": str(e)}, status=400)
    return Response(_preview(spec, request.user, method, text))


@api_view(["POST"])
def preview_rule(request):
    """Preview a rule built in the visual builder (already structured)."""
    try:
        spec = RuleSpec.model_validate(request.data.get("spec") or {})
    except ValidationError as e:
        return Response({"detail": e.errors()[0]["msg"]}, status=400)
    return Response(_preview(spec, request.user, "builder"))


@api_view(["GET", "POST"])
def rules(request):
    if request.method == "GET":
        qs = TradingRule.objects.filter(user=request.user)
        return Response([serialize_rule(r) for r in qs])
    try:
        spec = RuleSpec.model_validate(request.data.get("spec") or {})
    except ValidationError as e:
        return Response({"detail": e.errors()[0]["msg"]}, status=400)
    active = TradingRule.objects.filter(user=request.user, status="active").count()
    if active >= settings.MAX_ACTIVE_RULES_PER_USER:
        return Response({"detail": f"You can have at most {settings.MAX_ACTIVE_RULES_PER_USER} "
                                   "active rules."}, status=400)
    rule = TradingRule.objects.create(
        user=request.user, account=primary_account(request.user), name=spec.name,
        source_text=(request.data.get("source_text") or "")[:1000],
        spec=spec.model_dump(mode="json"),
        expires_at=spec.expires_at or timezone.now() + timedelta(days=90),
    )
    return Response(serialize_rule(rule), status=201)


@api_view(["GET", "DELETE"])
def rule_detail(request, pk):
    rule = get_object_or_404(TradingRule, pk=pk, user=request.user)
    if request.method == "DELETE":
        rule.delete()
        return Response(status=204)
    return Response(serialize_rule(rule, with_executions=True))


@api_view(["POST"])
def rule_action(request, pk, action):
    rule = get_object_or_404(TradingRule, pk=pk, user=request.user)
    if action == "pause" and rule.status == "active":
        rule.status = "paused"
    elif action == "resume" and rule.status in ("paused", "error", "triggered", "expired"):
        rule.status, rule.status_message, rule.last_condition = "active", "", False
        rule.expires_at = max(rule.expires_at or timezone.now(),
                              timezone.now() + timedelta(days=90))
    else:
        return Response({"detail": f"Can't {action} a rule that is {rule.status}."}, status=400)
    rule.save()
    return Response(serialize_rule(rule))


@api_view(["POST"])
def rule_backtest(request, pk):
    rule = get_object_or_404(TradingRule, pk=pk, user=request.user)
    return Response(backtest(RuleSpec.model_validate(rule.spec)))
