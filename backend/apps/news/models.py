from django.db import models


class NewsArticle(models.Model):
    KINDS = [
        ("news", "News"), ("press_release", "Press release"), ("sec_filing", "SEC filing"),
        ("analyst", "Analyst rating"), ("earnings", "Earnings"), ("macro", "Macro"),
        ("sector", "Sector"),
    ]
    stocks = models.ManyToManyField("market.Stock", related_name="news", blank=True)
    headline = models.CharField(max_length=400)
    summary = models.TextField(blank=True)
    source = models.CharField(max_length=120)
    url = models.URLField(max_length=600, blank=True)
    kind = models.CharField(max_length=16, choices=KINDS, default="news")
    published_at = models.DateTimeField(db_index=True)
    sentiment = models.FloatField(default=0)  # -1 .. 1
    importance = models.FloatField(default=0.5)  # 0 .. 1
    sector = models.CharField(max_length=64, blank=True)  # for sector-wide items
    is_simulated = models.BooleanField(default=False)
    dedupe_hash = models.CharField(max_length=64, unique=True)

    class Meta:
        ordering = ["-published_at"]

    def __str__(self):
        return self.headline


class MarketEvent(models.Model):
    KINDS = [("earnings", "Earnings"), ("dividend", "Dividend"), ("split", "Split"),
             ("fomc", "FOMC"), ("cpi", "CPI"), ("jobs", "Jobs report"), ("halt", "Halt")]
    stock = models.ForeignKey("market.Stock", null=True, blank=True, on_delete=models.CASCADE,
                              related_name="events")
    kind = models.CharField(max_length=16, choices=KINDS)
    ts = models.DateTimeField(db_index=True)
    title = models.CharField(max_length=200)
    payload = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["ts"]
