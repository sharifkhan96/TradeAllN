from django.urls import path

from . import views

urlpatterns = [
    path("summary", views.summary),
    path("positions", views.positions),
    path("history", views.history),
    path("analytics", views.analytics),
    path("performance", views.performance),
]
