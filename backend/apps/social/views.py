from rest_framework.decorators import api_view
from rest_framework.response import Response

from apps.portfolio.services import summary
from apps.trading.models import TradingAccount


@api_view(["GET"])
def leaderboard(request):
    rows = []
    for acct in TradingAccount.objects.select_related("user").filter(user__is_active=True):
        s = summary(acct)
        rows.append({"account_id": acct.id, "name": acct.user.name,
                     "is_you": acct.user_id == request.user.pk,
                     "equity": s["equity"], "return_pct": s["total_pct"],
                     "day_pct": s["day_pct"], "positions": s["positions_count"]})
    rows.sort(key=lambda r: -r["return_pct"])
    for i, r in enumerate(rows, 1):
        r["rank"] = i
    return Response(rows[:100])
