import uuid
from decimal import Decimal

from django.conf import settings
from django.db import models

MONEY = {"max_digits": 18, "decimal_places": 4}
QTY = {"max_digits": 18, "decimal_places": 6}


class TradingAccount(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                             related_name="accounts")
    name = models.CharField(max_length=60, default="Paper Account")
    type = models.CharField(max_length=10, default="paper", choices=[("paper", "Paper"),
                                                                    ("live", "Live")])
    cash_balance = models.DecimalField(**MONEY, default=0)
    reserved_cash = models.DecimalField(**MONEY, default=0)
    starting_cash = models.DecimalField(**MONEY, default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    @property
    def buying_power(self) -> Decimal:
        return self.cash_balance - self.reserved_cash

    def __str__(self):
        return f"{self.user} · {self.name}"


class Position(models.Model):
    account = models.ForeignKey(TradingAccount, on_delete=models.CASCADE, related_name="positions")
    stock = models.ForeignKey("market.Stock", on_delete=models.PROTECT)
    quantity = models.DecimalField(**QTY, default=0)
    reserved_qty = models.DecimalField(**QTY, default=0)
    avg_cost = models.DecimalField(**MONEY, default=0)
    realized_pnl = models.DecimalField(**MONEY, default=0)
    opened_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["account", "stock"], name="uniq_position")]


class Order(models.Model):
    SIDES = [("buy", "Buy"), ("sell", "Sell")]
    TYPES = [("market", "Market"), ("limit", "Limit"), ("stop", "Stop"),
             ("stop_limit", "Stop limit")]
    TIF = [("day", "Day"), ("gtc", "Good till cancelled")]
    STATUSES = [("open", "Open"), ("partially_filled", "Partially filled"), ("filled", "Filled"),
                ("cancelled", "Cancelled"), ("rejected", "Rejected"), ("expired", "Expired")]
    SOURCES = [("manual", "Manual"), ("assistant", "Assistant"), ("rule", "Rule"),
               ("recurring", "Recurring")]
    OPEN_STATES = ("open", "partially_filled")

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    account = models.ForeignKey(TradingAccount, on_delete=models.CASCADE, related_name="orders")
    stock = models.ForeignKey("market.Stock", on_delete=models.PROTECT)
    side = models.CharField(max_length=4, choices=SIDES)
    type = models.CharField(max_length=10, choices=TYPES)
    time_in_force = models.CharField(max_length=3, choices=TIF, default="day")
    quantity = models.DecimalField(**QTY)
    limit_price = models.DecimalField(**MONEY, null=True, blank=True)
    stop_price = models.DecimalField(**MONEY, null=True, blank=True)
    stop_triggered = models.BooleanField(default=False)
    filled_qty = models.DecimalField(**QTY, default=0)
    avg_fill_price = models.DecimalField(**MONEY, null=True, blank=True)
    reserved_amount = models.DecimalField(**MONEY, default=0)
    status = models.CharField(max_length=20, choices=STATUSES, default="open", db_index=True)
    reject_reason = models.CharField(max_length=200, blank=True)
    client_order_id = models.CharField(max_length=64, null=True, blank=True)
    source = models.CharField(max_length=10, choices=SOURCES, default="manual")
    extended_hours = models.BooleanField(default=False)
    notional = models.DecimalField(**MONEY, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    filled_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(fields=["account", "client_order_id"],
                                    name="uniq_client_order_id",
                                    condition=models.Q(client_order_id__isnull=False))
        ]
        indexes = [models.Index(fields=["status", "stock"])]


class Trade(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="trades")
    account = models.ForeignKey(TradingAccount, on_delete=models.CASCADE, related_name="trades")
    stock = models.ForeignKey("market.Stock", on_delete=models.PROTECT)
    side = models.CharField(max_length=4)
    quantity = models.DecimalField(**QTY)
    price = models.DecimalField(**MONEY)
    commission = models.DecimalField(**MONEY, default=0)
    realized_pnl = models.DecimalField(**MONEY, null=True, blank=True)
    executed_at = models.DateTimeField()

    class Meta:
        ordering = ["-executed_at"]


class LedgerEntry(models.Model):
    TYPES = [("deposit", "Deposit"), ("trade_buy", "Buy"), ("trade_sell", "Sell"),
             ("commission", "Commission"), ("reset", "Reset"), ("dividend", "Dividend")]
    account = models.ForeignKey(TradingAccount, on_delete=models.CASCADE, related_name="ledger")
    type = models.CharField(max_length=12, choices=TYPES)
    amount = models.DecimalField(**MONEY)
    balance_after = models.DecimalField(**MONEY)
    reference = models.CharField(max_length=64, blank=True)
    created_at = models.DateTimeField()

    class Meta:
        ordering = ["-created_at", "-id"]


class RecurringInvestment(models.Model):
    """Auto-invest a fixed dollar amount on a schedule (fractional shares)."""

    FREQUENCIES = [("daily", "Every trading day"), ("weekly", "Weekly"),
                   ("biweekly", "Every 2 weeks"), ("monthly", "Monthly")]
    account = models.ForeignKey(TradingAccount, on_delete=models.CASCADE, related_name="recurring")
    stock = models.ForeignKey("market.Stock", on_delete=models.PROTECT)
    amount = models.DecimalField(**MONEY)
    frequency = models.CharField(max_length=10, choices=FREQUENCIES, default="weekly")
    next_run = models.DateField()
    active = models.BooleanField(default=True)
    last_run_at = models.DateTimeField(null=True, blank=True)
    last_result = models.CharField(max_length=200, blank=True)
    total_invested = models.DecimalField(**MONEY, default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["next_run", "id"]


class DividendPayment(models.Model):
    account = models.ForeignKey(TradingAccount, on_delete=models.CASCADE, related_name="dividends")
    stock = models.ForeignKey("market.Stock", on_delete=models.PROTECT)
    ex_date = models.DateField()
    per_share = models.DecimalField(**MONEY)
    quantity = models.DecimalField(**QTY)
    amount = models.DecimalField(**MONEY)
    paid_at = models.DateTimeField()

    class Meta:
        ordering = ["-ex_date"]
        constraints = [models.UniqueConstraint(fields=["account", "stock", "ex_date"],
                                               name="uniq_dividend")]
