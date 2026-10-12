from django.urls import path

from . import views

urlpatterns = [
    path("parse", views.parse),
    path("confirm/<uuid:pk>", views.confirm),
    path("reject/<uuid:pk>", views.reject),
    path("ask", views.ask),
    path("status", views.status),
    path("history", views.history),
]
