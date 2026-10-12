from django.urls import path

from . import views

urlpatterns = [
    path("watchlists", views.watchlists),
    path("watchlists/<int:pk>", views.watchlist_detail),
    path("watchlists/<int:pk>/items", views.add_item),
    path("watchlists/<int:pk>/items/<str:symbol>", views.remove_item),
]
