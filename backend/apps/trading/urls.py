from django.urls import path

from . import views

urlpatterns = [
    path("accounts", views.accounts),
    path("accounts/reset", views.reset),
    path("orders", views.orders),
    path("orders/<uuid:pk>", views.order_detail),
    path("trades", views.trades),
    path("ledger", views.ledger),
    path("recurring", views.recurring),
    path("recurring/<int:pk>", views.recurring_detail),
    path("dividends", views.dividends),
]
