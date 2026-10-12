from django.db import models


class Stock(models.Model):
    symbol = models.CharField(max_length=12, unique=True)
    name = models.CharField(max_length=160)
    exchange = models.CharField(max_length=16, default="NASDAQ")
    sector = models.CharField(max_length=64, blank=True)
    industry = models.CharField(max_length=96, blank=True)
    sector_etf = models.CharField(max_length=8, blank=True)
    description = models.TextField(blank=True)
    market_cap = models.BigIntegerField(null=True, blank=True)
    pe_ratio = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    dividend_yield = models.DecimalField(max_digits=6, decimal_places=3, null=True, blank=True)
    beta = models.DecimalField(max_digits=5, decimal_places=2, default=1)
    is_etf = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    is_tradable = models.BooleanField(default=True)
    # Full US universe comes from the Nasdaq symbol directory; detailed data is loaded on demand.
    is_popular = models.BooleanField(default=False, db_index=True)
    hydrated_at = models.DateTimeField(null=True, blank=True, db_index=True)
    ceo = models.CharField(max_length=120, blank=True)
    employees = models.IntegerField(null=True, blank=True)
    website = models.URLField(blank=True)
    hq = models.CharField(max_length=120, blank=True)

    class Meta:
        ordering = ["symbol"]

    @property
    def yahoo_symbol(self) -> str:
        return self.symbol.replace(".", "-")

    def __str__(self):
        return self.symbol


class PriceBar(models.Model):
    TIMEFRAMES = [("1m", "1 minute"), ("5m", "5 minutes"), ("1d", "1 day")]

    stock = models.ForeignKey(Stock, on_delete=models.CASCADE, related_name="bars")
    timeframe = models.CharField(max_length=3, choices=TIMEFRAMES)
    ts = models.DateTimeField()
    open = models.DecimalField(max_digits=18, decimal_places=4)
    high = models.DecimalField(max_digits=18, decimal_places=4)
    low = models.DecimalField(max_digits=18, decimal_places=4)
    close = models.DecimalField(max_digits=18, decimal_places=4)
    volume = models.BigIntegerField(default=0)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["stock", "timeframe", "ts"], name="uniq_bar")
        ]
        indexes = [models.Index(fields=["stock", "timeframe", "-ts"])]
