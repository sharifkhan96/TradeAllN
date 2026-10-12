from celery import shared_task

from apps.trading.models import TradingAccount

from .services import take_snapshot


@shared_task
def snapshot_portfolios():
    for acct in TradingAccount.objects.all():
        take_snapshot(acct)
