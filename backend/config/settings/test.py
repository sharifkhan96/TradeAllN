from .base import *  # noqa: F401,F403

CHANNEL_LAYERS = {"default": {"BACKEND": "channels.layers.InMemoryChannelLayer"}}
CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
ANTHROPIC_API_KEY = ""
CELERY_TASK_ALWAYS_EAGER = True
MARKET_DATA_PROVIDER = "mock"
MOCK_MARKET_ALWAYS_OPEN = True
