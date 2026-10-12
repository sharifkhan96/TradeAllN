"""The full US-listed universe from Nasdaq Trader's official symbol directory (free, daily).

nasdaqlisted.txt covers Nasdaq listings; otherlisted.txt covers NYSE, NYSE American,
NYSE Arca and Cboe. We keep common stocks, ADRs and ETFs, and drop warrants, rights, units,
preferreds, notes and test issues, much like a retail broker's tradable list.
"""
import logging
import re

import httpx

from .models import Stock

log = logging.getLogger(__name__)
NASDAQ = "https://www.nasdaqtrader.com/dynamic/SymDir/nasdaqlisted.txt"
OTHER = "https://www.nasdaqtrader.com/dynamic/SymDir/otherlisted.txt"
EXCHANGES = {"A": "NYSE American", "N": "NYSE", "P": "NYSE Arca", "Z": "Cboe BZX", "V": "IEX"}
SKIP = re.compile(r"\b(warrants?|rights?|units?|preferred|notes? due|debentures?|"
                  r"subordinated|when issued|%)\b", re.I)
SUFFIX = re.compile(
    r"\s*[-–]\s*(Class [A-Z] )?(Common Stock|Ordinary Shares|Common Shares|Class [A-Z] Ordinary Shares)"
    r".*$|\s+(Class [A-Z] )?(Common Stock|Ordinary Shares|Common Shares)( Class [A-Z])?\s*$", re.I)


def _rows(url: str) -> list[dict]:
    r = httpx.get(url, timeout=30, headers={"User-Agent": "Mozilla/5.0 TradeAllN/1.0"})
    r.raise_for_status()
    lines = [ln for ln in r.text.splitlines() if ln and not ln.startswith("File Creation Time")]
    head = lines[0].split("|")
    return [dict(zip(head, ln.split("|"), strict=False)) for ln in lines[1:]]


def clean_name(name: str) -> str:
    name = SUFFIX.sub("", name.strip())
    return name.split(" - ")[0].strip() or name.strip()


def fetch() -> list[dict]:
    out = []
    for r in _rows(NASDAQ):
        if r.get("Test Issue") == "Y":
            continue
        out.append({"symbol": r["Symbol"], "name": r["Security Name"], "exchange": "NASDAQ",
                    "is_etf": r.get("ETF") == "Y"})
    for r in _rows(OTHER):
        if r.get("Test Issue") == "Y":
            continue
        out.append({"symbol": r["ACT Symbol"], "name": r["Security Name"],
                    "exchange": EXCHANGES.get(r.get("Exchange"), r.get("Exchange", "")),
                    "is_etf": r.get("ETF") == "Y"})
    keep = []
    for r in out:
        sym = r["symbol"].strip().upper()
        if not sym or any(c in sym for c in "$=^+ ") or SKIP.search(r["name"]):
            continue
        keep.append({**r, "symbol": sym, "name": clean_name(r["name"])[:160]})
    return keep


def sync(log_fn=print) -> int:
    rows = fetch()
    symbols = {r["symbol"] for r in rows}
    hydrated = set(Stock.objects.filter(hydrated_at__isnull=False).values_list("symbol", flat=True))
    # Directory data must not overwrite richer profiles already loaded from Yahoo.
    fresh = [Stock(symbol=r["symbol"], name=r["name"], exchange=r["exchange"], is_etf=r["is_etf"],
                   is_active=True) for r in rows if r["symbol"] not in hydrated]
    Stock.objects.bulk_create(fresh, batch_size=2000, update_conflicts=True,
                              unique_fields=["symbol"],
                              update_fields=["name", "exchange", "is_etf", "is_active"])
    gone = Stock.objects.exclude(symbol__in=symbols).filter(is_active=True)
    n_gone = gone.update(is_active=False, is_tradable=False)
    Stock.objects.filter(symbol__in=symbols).update(is_tradable=True)
    log_fn(f"  {len(rows):,} tradable US stocks & ETFs ({n_gone} delisted)")
    return len(rows)
