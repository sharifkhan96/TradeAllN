from celery import shared_task
from django.utils import timezone

from .models import TradingRule


@shared_task
def expire_rules():
    return TradingRule.objects.filter(status__in=["active", "paused"],
                                      expires_at__lt=timezone.now()).update(status="expired")
