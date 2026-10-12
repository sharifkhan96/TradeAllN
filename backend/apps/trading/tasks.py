from celery import shared_task

from . import engine


@shared_task
def expire_day_orders():
    return engine.expire_day_orders()
