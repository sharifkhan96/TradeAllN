from django.db import models


class PortfolioSnapshot(models.Model):
    account = models.ForeignKey("trading.TradingAccount", on_delete=models.CASCADE,
                                related_name="snapshots")
    date = models.DateField()
    cash = models.DecimalField(max_digits=18, decimal_places=4)
    positions_value = models.DecimalField(max_digits=18, decimal_places=4)
    total_equity = models.DecimalField(max_digits=18, decimal_places=4)

    class Meta:
        ordering = ["date"]
        constraints = [models.UniqueConstraint(fields=["account", "date"], name="uniq_snapshot")]
