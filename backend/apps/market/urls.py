from django.urls import path

from . import views

urlpatterns = [
    path("stocks", views.stock_list),
    path("stocks/<str:symbol>", views.stock_detail),
    path("stocks/<str:symbol>/quote", views.stock_quote),
    path("stocks/<str:symbol>/bars", views.stock_bars),
    path("stocks/<str:symbol>/insights", views.stock_insights),
    path("quotes", views.batch_quotes),
    path("discover", views.discover),
    path("logos/<str:symbol>", views.logo),
    path("market/status", views.market_status),
    path("market/overview", views.market_overview),
]
