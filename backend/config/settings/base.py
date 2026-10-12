from datetime import timedelta
from decimal import Decimal
from pathlib import Path

import environ
from celery.schedules import crontab

BASE_DIR = Path(__file__).resolve().parent.parent.parent
REPO_ROOT = BASE_DIR.parent

env = environ.Env()
if (REPO_ROOT / ".env").exists():
    env.read_env(str(REPO_ROOT / ".env"), parse_comments=True)

SECRET_KEY = env("DJANGO_SECRET_KEY", default="insecure-dev-key")
DEBUG = env.bool("DJANGO_DEBUG", default=False)
ALLOWED_HOSTS = env.list("DJANGO_ALLOWED_HOSTS", default=["localhost", "127.0.0.1"])
CORS_ALLOWED_ORIGINS = env.list("CORS_ALLOWED_ORIGINS", default=[])
CORS_ALLOW_CREDENTIALS = True
CSRF_TRUSTED_ORIGINS = env.list("CSRF_TRUSTED_ORIGINS", default=[])

INSTALLED_APPS = [
    "daphne",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "corsheaders",
    "django_filters",
    "drf_spectacular",
    "channels",
    "apps.accounts",
    "apps.market",
    "apps.news",
    "apps.trading",
    "apps.portfolio",
    "apps.watchlists",
    "apps.explain",
    "apps.rules",
    "apps.assistant",
    "apps.social",
    "apps.realtime",
]

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ]
        },
    }
]
WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

DATABASES = {"default": env.db("DATABASE_URL")}
DATABASES["default"]["CONN_MAX_AGE"] = 60

AUTH_USER_MODEL = "accounts.User"
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True
STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.IsAuthenticated"],
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_FILTER_BACKENDS": ["django_filters.rest_framework.DjangoFilterBackend"],
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.LimitOffsetPagination",
    "PAGE_SIZE": 50,
    "COERCE_DECIMAL_TO_STRING": True,
    "DEFAULT_THROTTLE_RATES": {"auth": "20/min", "orders": "120/min", "ai": "30/min"},
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=env.int("JWT_ACCESS_LIFETIME_MIN", default=15)),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=env.int("JWT_REFRESH_LIFETIME_DAYS", default=7)),
    "ROTATE_REFRESH_TOKENS": True,
    "UPDATE_LAST_LOGIN": True,
}
REFRESH_COOKIE_NAME = "tradeall_refresh"

SPECTACULAR_SETTINGS = {"TITLE": "TradeAllN API", "VERSION": "1.0.0"}

REDIS_URL = env("REDIS_URL", default="redis://localhost:6379/0")
CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {"hosts": [env("CHANNEL_LAYER_URL", default="redis://localhost:6379/2")]},
    }
}
CACHES = {"default": {"BACKEND": "django.core.cache.backends.redis.RedisCache", "LOCATION": REDIS_URL}}

CELERY_BROKER_URL = env("CELERY_BROKER_URL", default="redis://localhost:6379/1")
CELERY_TIMEZONE = "America/New_York"
CELERY_BEAT_SCHEDULE = {
    "snapshot-portfolios": {
        "task": "apps.portfolio.tasks.snapshot_portfolios",
        "schedule": crontab(minute=15, hour=16, day_of_week="mon-fri"),
    },
    "expire-day-orders": {
        "task": "apps.trading.tasks.expire_day_orders",
        "schedule": crontab(minute=0, hour=16, day_of_week="mon-fri"),
    },
    "explain-recent-moves": {
        "task": "apps.explain.tasks.explain_recent_moves",
        "schedule": crontab(minute=0, hour=18),
    },
    "expire-rules": {"task": "apps.rules.tasks.expire_rules", "schedule": crontab(minute=5, hour=0)},
}

EMAIL_BACKEND = env("EMAIL_BACKEND", default="django.core.mail.backends.console.EmailBackend")
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", default="TradeAllN <no-reply@tradeall.local>")

# ---- Market data ----
# yahoo (real prices, no key) | finnhub (yahoo + real-time ticks, needs key) | alpaca | mock
MARKET_DATA_PROVIDER = env("MARKET_DATA_PROVIDER", default="yahoo")
QUOTE_POLL_SECONDS = env.int("QUOTE_POLL_SECONDS", default=15)
EXTRA_SYMBOLS = [s.strip().upper() for s in env.list("EXTRA_SYMBOLS", default=[]) if s.strip()]
FINNHUB_API_KEY = env("FINNHUB_API_KEY", default="")
MOCK_MARKET_ALWAYS_OPEN = env.bool("MOCK_MARKET_ALWAYS_OPEN", default=True)
MOCK_TICK_SECONDS = env.float("MOCK_TICK_SECONDS", default=1.0)
ALPACA_API_KEY = env("ALPACA_API_KEY", default="")
ALPACA_API_SECRET = env("ALPACA_API_SECRET", default="")
ALPACA_DATA_FEED = env("ALPACA_DATA_FEED", default="iex")

# ---- News ----
NEWS_POLL_MINUTES = env.int("NEWS_POLL_MINUTES", default=5)
NEWS_BACKFILL_DAYS = env.int("NEWS_BACKFILL_DAYS", default=30)
# SEC asks for a descriptive User-Agent with contact details.
SEC_USER_AGENT = env("SEC_USER_AGENT", default="TradeAllN/1.0 (personal research; set SEC_USER_AGENT)")

# ---- Trading ----
BROKER_BACKEND = env("BROKER_BACKEND", default="simulated")
STARTING_CASH = Decimal(env("STARTING_CASH", default="100000.00"))
SIMULATED_SLIPPAGE_BPS = env.int("SIMULATED_SLIPPAGE_BPS", default=5)
COMMISSION_PER_TRADE = Decimal(env("COMMISSION_PER_TRADE", default="0.00"))

# ---- AI ----
ANTHROPIC_API_KEY = env("ANTHROPIC_API_KEY", default="")
LLM_MODEL = env("LLM_MODEL", default="claude-opus-5-5")
LLM_EFFORT = env("LLM_EFFORT", default="medium")
AI_FEATURES_ENABLED = env.bool("AI_FEATURES_ENABLED", default=True)
AI_DAILY_REQUESTS_PER_USER = env.int("AI_DAILY_REQUESTS_PER_USER", default=100)

# ---- Rules ----
MAX_ACTIVE_RULES_PER_USER = env.int("MAX_ACTIVE_RULES_PER_USER", default=25)
MAX_RULE_ORDER_VALUE = Decimal(env("MAX_RULE_ORDER_VALUE", default="25000"))

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {"plain": {"format": "%(asctime)s %(levelname)s %(name)s: %(message)s"}},
    "handlers": {"console": {"class": "logging.StreamHandler", "formatter": "plain"}},
    "root": {"handlers": ["console"], "level": env("LOG_LEVEL", default="INFO")},
    "loggers": {"httpx": {"level": "WARNING"}, "httpx2": {"level": "WARNING"},
                "daphne": {"level": "WARNING"}},
}
