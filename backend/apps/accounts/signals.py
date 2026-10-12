from django.conf import settings
from django.db.models.signals import post_save
from django.dispatch import receiver


@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def create_paper_account(sender, instance, created, **kwargs):
    if not created:
        return
    from apps.trading.services import open_paper_account
    from apps.watchlists.models import Watchlist

    open_paper_account(instance)
    Watchlist.objects.create(user=instance, name="My Watchlist", position=0)
