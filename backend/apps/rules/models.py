from django.conf import settings
from django.db import models


class TradingRule(models.Model):
    STATUSES = [("active", "Active"), ("paused", "Paused"), ("triggered", "Triggered"),
                ("expired", "Expired"), ("error", "Error")]
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                             related_name="rules")
    account = models.ForeignKey("trading.TradingAccount", on_delete=models.CASCADE)
    name = models.CharField(max_length=80)
    source_text = models.TextField(blank=True)
    spec = models.JSONField()
    status = models.CharField(max_length=10, choices=STATUSES, default="active", db_index=True)
    status_message = models.CharField(max_length=300, blank=True)
    last_condition = models.BooleanField(default=False)
    state = models.JSONField(default=dict, blank=True)  # previous values for crosses_* clauses
    last_evaluated_at = models.DateTimeField(null=True, blank=True)
    last_triggered_at = models.DateTimeField(null=True, blank=True)
    trigger_count = models.PositiveIntegerField(default=0)
    expires_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]


class RuleExecution(models.Model):
    rule = models.ForeignKey(TradingRule, on_delete=models.CASCADE, related_name="executions")
    triggered_at = models.DateTimeField()
    window_key = models.CharField(max_length=40)
    snapshot = models.JSONField(default=dict)
    order = models.ForeignKey("trading.Order", null=True, blank=True, on_delete=models.SET_NULL)
    result = models.CharField(max_length=300)
    success = models.BooleanField(default=True)

    class Meta:
        ordering = ["-triggered_at"]
        constraints = [models.UniqueConstraint(fields=["rule", "window_key"],
                                               name="uniq_rule_window")]
