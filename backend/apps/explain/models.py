from django.db import models


class PriceMove(models.Model):
    DIRECTIONS = [("up", "Up"), ("down", "Down"), ("flat", "Flat")]
    stock = models.ForeignKey("market.Stock", on_delete=models.CASCADE, related_name="moves")
    timeframe = models.CharField(max_length=4)
    start_ts = models.DateTimeField()
    end_ts = models.DateTimeField()
    start_price = models.DecimalField(max_digits=18, decimal_places=4)
    end_price = models.DecimalField(max_digits=18, decimal_places=4)
    pct_change = models.FloatField()
    direction = models.CharField(max_length=4, choices=DIRECTIONS)
    magnitude_z = models.FloatField(default=0)
    market_pct = models.FloatField(null=True)
    sector_pct = models.FloatField(null=True)
    residual_pct = models.FloatField(null=True)
    volume_ratio = models.FloatField(null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["start_ts"]
        constraints = [models.UniqueConstraint(fields=["stock", "timeframe", "start_ts", "end_ts"],
                                               name="uniq_move")]


class MoveExplanation(models.Model):
    CATEGORIES = [
        ("company_news", "Company news"), ("earnings", "Earnings"), ("analyst", "Analyst action"),
        ("filing", "SEC filing"), ("sector", "Sector move"), ("market_wide", "Market-wide"),
        ("macro", "Macro data"), ("no_clear_catalyst", "No clear catalyst"),
        ("quiet", "Quiet trading"),
    ]
    move = models.OneToOneField(PriceMove, on_delete=models.CASCADE, related_name="explanation")
    summary = models.TextField()
    category = models.CharField(max_length=20, choices=CATEGORIES)
    confidence = models.CharField(max_length=6, default="medium")
    method = models.CharField(max_length=16, default="rules")  # rules | llm
    model = models.CharField(max_length=60, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)


class MoveCitation(models.Model):
    explanation = models.ForeignKey(MoveExplanation, on_delete=models.CASCADE,
                                    related_name="citations")
    article = models.ForeignKey("news.NewsArticle", on_delete=models.CASCADE)
    relevance = models.CharField(max_length=12, default="primary")
    rank = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["rank"]
