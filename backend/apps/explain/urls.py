from django.urls import path

from . import views

urlpatterns = [
    path("stocks/<str:symbol>/moves", views.moves),
    path("stocks/<str:symbol>/explain", views.explain_range),
    path("moves/<int:pk>/deep", views.deep_explain),
]
