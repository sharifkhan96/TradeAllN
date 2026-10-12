from django.conf import settings
from django.db import transaction
from django.utils import timezone

from .models import LedgerEntry, TradingAccount


def open_paper_account(user, name="Paper Account", cash=None) -> TradingAccount:
    cash = settings.STARTING_CASH if cash is None else cash
    with transaction.atomic():
        acct = TradingAccount.objects.create(user=user, name=name, cash_balance=cash,
                                             starting_cash=cash)
        LedgerEntry.objects.create(account=acct, type="deposit", amount=cash, balance_after=cash,
                                   reference="initial", created_at=timezone.now())
    return acct


def primary_account(user) -> TradingAccount:
    acct = user.accounts.order_by("id").first()
    return acct or open_paper_account(user)


def reset_account(account: TradingAccount) -> None:
    with transaction.atomic():
        acct = TradingAccount.objects.select_for_update().get(pk=account.pk)
        acct.orders.filter(status__in=["open", "partially_filled"]).update(status="cancelled")
        acct.positions.all().delete()
        acct.cash_balance = acct.starting_cash
        acct.reserved_cash = 0
        acct.save()
        LedgerEntry.objects.create(account=acct, type="reset", amount=0,
                                   balance_after=acct.cash_balance, created_at=timezone.now())
        from apps.portfolio.models import PortfolioSnapshot

        PortfolioSnapshot.objects.filter(account=acct).delete()
