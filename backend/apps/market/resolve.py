"""Resolve what a user typed ("apple", "Tesla", "nvda", "google") to a ticker."""
import re

from django.db import models

from .models import Stock

ALIASES = {
    "google": "GOOGL", "alphabet": "GOOGL", "facebook": "META", "meta": "META",
    "coke": "KO", "coca cola": "KO", "coca-cola": "KO", "j&j": "JNJ", "johnson": "JNJ",
    "goldman": "GS", "jp morgan": "JPM", "jpmorgan": "JPM", "chase": "JPM",
    "bank of america": "BAC", "bofa": "BAC", "lilly": "LLY", "eli lilly": "LLY",
    "exxon": "XOM", "chevron": "CVX", "boeing": "BA", "caterpillar": "CAT",
    "procter": "PG", "p&g": "PG", "walmart": "WMT", "costco": "COST", "mcdonalds": "MCD",
    "mcdonald's": "MCD", "s&p": "SPY", "s&p 500": "SPY", "the market": "SPY", "nasdaq": "QQQ",
    "dow": "DIA", "russell": "IWM", "unitedhealth": "UNH", "united health": "UNH",
    "broadcom": "AVGO", "salesforce": "CRM", "starbucks": "SBUX", "nike": "NKE",
}

_cache: dict[str, str] | None = None


def _index() -> dict[str, str]:
    global _cache
    if _cache is None:
        idx = {}
        # every listed ticker resolves by symbol…
        for sym in Stock.objects.filter(is_active=True).values_list("symbol", flat=True):
            idx[sym.lower()] = sym
        # …but company names only for well-known tickers, so "first" or "american" don't misfire
        named = Stock.objects.filter(is_active=True).filter(
            models.Q(is_popular=True) | models.Q(hydrated_at__isnull=False)).order_by("-market_cap")
        for sym, name in named.values_list("symbol", "name"):
            words = re.split(r"[\s,.]", name.lower())
            first = words[0]
            if first not in ("the", "first", "american", "united", "general", "bank") and len(first) > 2:
                idx.setdefault(first, sym)
        idx.update(ALIASES)
        _cache = idx
    return _cache


def resolve_symbol(text: str | None) -> str | None:
    if not text:
        return None
    t = text.lower().strip().strip("$.,!?").removeprefix("my ").removesuffix(" stock") \
        .removesuffix(" shares").removesuffix("'s").strip()
    idx = _index()
    if t in idx:
        return idx[t]
    for word in t.split():
        if word in idx:
            return idx[word]
    return None


def reset_cache():
    global _cache
    _cache = None
