from django.contrib import admin
from django.http import JsonResponse
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

api = [
    path("auth/", include("apps.accounts.urls")),
    path("", include("apps.market.urls")),
    path("", include("apps.news.urls")),
    path("", include("apps.trading.urls")),
    path("portfolio/", include("apps.portfolio.urls")),
    path("", include("apps.watchlists.urls")),
    path("", include("apps.explain.urls")),
    path("", include("apps.rules.urls")),
    path("assistant/", include("apps.assistant.urls")),
    path("", include("apps.social.urls")),
    path("schema/", SpectacularAPIView.as_view(), name="schema"),
    path("docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="docs"),
]

urlpatterns = [
    path("admin/", admin.site.urls),
    path("healthz", lambda r: JsonResponse({"ok": True})),
    path("api/v1/", include(api)),
]
