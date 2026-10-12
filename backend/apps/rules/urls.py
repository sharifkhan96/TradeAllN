from django.urls import path

from . import views

urlpatterns = [
    path("rules", views.rules),
    path("rules/compile", views.compile_rule),
    path("rules/preview", views.preview_rule),
    path("rules/<int:pk>", views.rule_detail),
    path("rules/<int:pk>/backtest", views.rule_backtest),
    path("rules/<int:pk>/<str:action>", views.rule_action),
]
