from django.db.models import Max
from django.shortcuts import get_object_or_404
from rest_framework.decorators import api_view
from rest_framework.response import Response

from apps.market import quotes
from apps.market.models import Stock

from .models import Watchlist, WatchlistItem


def _serialize(wl: Watchlist):
    items = list(wl.items.select_related("stock"))
    qs = quotes.get_quotes([i.stock.symbol for i in items])
    return {
        "id": wl.id, "name": wl.name,
        "items": [{"symbol": i.stock.symbol, "name": i.stock.name, "quote": qs.get(i.stock.symbol)}
                  for i in items],
    }


@api_view(["GET", "POST"])
def watchlists(request):
    if request.method == "POST":
        name = (request.data.get("name") or "").strip()[:60] or "New list"
        pos = (request.user.watchlists.aggregate(m=Max("position"))["m"] or 0) + 1
        wl = Watchlist.objects.create(user=request.user, name=name, position=pos)
        return Response(_serialize(wl), status=201)
    return Response([_serialize(w) for w in request.user.watchlists.all()])


@api_view(["GET", "PATCH", "DELETE"])
def watchlist_detail(request, pk):
    wl = get_object_or_404(Watchlist, pk=pk, user=request.user)
    if request.method == "DELETE":
        wl.delete()
        return Response(status=204)
    if request.method == "PATCH":
        if name := (request.data.get("name") or "").strip():
            wl.name = name[:60]
            wl.save()
        if order := request.data.get("order"):  # list of symbols in new order
            pos = {s: i for i, s in enumerate(order)}
            for item in wl.items.select_related("stock"):
                item.position = pos.get(item.stock.symbol, len(pos))
                item.save(update_fields=["position"])
    return Response(_serialize(wl))


@api_view(["POST"])
def add_item(request, pk):
    wl = get_object_or_404(Watchlist, pk=pk, user=request.user)
    stock = get_object_or_404(Stock, symbol=(request.data.get("symbol") or "").upper())
    pos = (wl.items.aggregate(m=Max("position"))["m"] or 0) + 1
    WatchlistItem.objects.get_or_create(watchlist=wl, stock=stock, defaults={"position": pos})
    return Response(_serialize(wl), status=201)


@api_view(["DELETE"])
def remove_item(request, pk, symbol):
    wl = get_object_or_404(Watchlist, pk=pk, user=request.user)
    WatchlistItem.objects.filter(watchlist=wl, stock__symbol=symbol.upper()).delete()
    return Response(_serialize(wl))
