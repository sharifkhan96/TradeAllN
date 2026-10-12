from django.urls import path

from .consumers import StreamConsumer

websocket_urlpatterns = [path("ws/", StreamConsumer.as_asgi())]
