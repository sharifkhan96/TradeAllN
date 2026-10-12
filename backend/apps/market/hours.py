"""NYSE trading hours. In mock mode the market can be simulated as always open."""
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from django.conf import settings
from django.utils import timezone

ET = ZoneInfo("America/New_York")
OPEN, CLOSE = time(9, 30), time(16, 0)

HOLIDAYS = {
    date(2025, 1, 1), date(2025, 1, 20), date(2025, 2, 17), date(2025, 4, 18), date(2025, 5, 26),
    date(2025, 6, 19), date(2025, 7, 4), date(2025, 9, 1), date(2025, 11, 27), date(2025, 12, 25),
    date(2026, 1, 1), date(2026, 1, 19), date(2026, 2, 16), date(2026, 4, 3), date(2026, 5, 25),
    date(2026, 6, 19), date(2026, 7, 3), date(2026, 9, 7), date(2026, 11, 26), date(2026, 12, 25),
    date(2027, 1, 1), date(2027, 1, 18), date(2027, 2, 15), date(2027, 3, 26), date(2027, 5, 31),
    date(2027, 6, 18), date(2027, 7, 5), date(2027, 9, 6), date(2027, 11, 25), date(2027, 12, 24),
}


def simulated() -> bool:
    return settings.MARKET_DATA_PROVIDER == "mock" and settings.MOCK_MARKET_ALWAYS_OPEN


def is_trading_day(d: date) -> bool:
    return d.weekday() < 5 and d not in HOLIDAYS


def status(now: datetime | None = None) -> dict:
    now = (now or timezone.now()).astimezone(ET)
    if simulated():
        return {"status": "open", "simulated": True, "label": "Market open · simulated 24/7",
                "now": now.isoformat(), "provider": "mock", "source": "Simulated data"}
    if not is_trading_day(now.date()):
        state = "closed"
    elif now.time() < time(4, 0) or now.time() >= time(20, 0):
        state = "closed"
    elif now.time() < OPEN:
        state = "pre_market"
    elif now.time() < CLOSE:
        state = "open"
    else:
        state = "after_hours"
    labels = {"open": "Market open", "pre_market": "Pre-market", "after_hours": "After hours",
              "closed": "Market closed"}
    out = {"status": state, "simulated": False, "label": labels[state], "now": now.isoformat(),
           "provider": settings.MARKET_DATA_PROVIDER,
           "source": "Yahoo Finance" + (" + Finnhub real-time" if settings.FINNHUB_API_KEY else "")}
    if state == "open":
        out["closes_at"] = datetime.combine(now.date(), CLOSE, ET).isoformat()
    else:
        out["opens_at"] = next_open(now).isoformat()
    return out


def next_open(now: datetime) -> datetime:
    d = now.date()
    if now.time() >= OPEN or not is_trading_day(d):
        d += timedelta(days=1)
    while not is_trading_day(d):
        d += timedelta(days=1)
    return datetime.combine(d, OPEN, ET)


def is_open(now: datetime | None = None) -> bool:
    return status(now)["status"] == "open"


def et_today() -> date:
    return timezone.now().astimezone(ET).date()
