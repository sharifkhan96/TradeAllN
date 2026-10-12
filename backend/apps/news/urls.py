from django.urls import path

from . import views

urlpatterns = [
    path("news", views.news),
    path("news/portfolio", views.portfolio_news),
    path("calendar", views.calendar),
]
