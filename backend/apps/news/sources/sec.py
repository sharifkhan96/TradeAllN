"""SEC EDGAR filings (no key; requires a descriptive User-Agent, max 10 requests/second)."""
import logging
import time
from datetime import UTC, date, datetime

import httpx
from django.conf import settings
from django.core.cache import cache

from .base import RawItem

log = logging.getLogger(__name__)

FORMS = {
    "8-K": ("Current report (8-K)", 0.6),
    "10-Q": ("Quarterly report (10-Q)", 0.5),
    "10-K": ("Annual report (10-K)", 0.55),
    "4": ("Insider transaction (Form 4)", 0.3),
    "SC 13D": ("Activist stake disclosure (13D)", 0.7),
    "S-1": ("Registration statement (S-1)", 0.5),
}
ITEMS_8K = {
    "1.01": "material agreement", "1.02": "termination of a material agreement",
    "2.01": "acquisition or disposition", "2.02": "results of operations",
    "2.05": "restructuring costs", "2.06": "impairment", "3.01": "delisting notice",
    "4.02": "non-reliance on prior financials", "5.02": "executive or director change",
    "5.07": "shareholder vote results", "7.01": "Regulation FD disclosure", "8.01": "other events",
}


def _headers():
    return {"User-Agent": settings.SEC_USER_AGENT, "Accept-Encoding": "gzip, deflate"}


def cik_map() -> dict[str, str]:
    m = cache.get("sec:cik_map")
    if m:
        return m
    r = httpx.get("https://www.sec.gov/files/company_tickers.json", headers=_headers(), timeout=20)
    r.raise_for_status()
    m = {v["ticker"].upper(): str(v["cik_str"]).zfill(10) for v in r.json().values()}
    cache.set("sec:cik_map", m, 86400)
    return m


def filings(symbol: str, name: str, since: date) -> list[RawItem]:
    cik = cik_map().get(symbol.upper())
    if not cik:
        return []
    try:
        r = httpx.get(f"https://data.sec.gov/submissions/CIK{cik}.json", headers=_headers(), timeout=20)
        r.raise_for_status()
    except Exception:
        log.info("sec fetch failed for %s", symbol, exc_info=True)
        return []
    finally:
        time.sleep(0.12)  # stay well under SEC's 10 req/s
    rec = r.json()["filings"]["recent"]
    out = []
    form4_days = set()
    for i, form in enumerate(rec["form"]):
        if form not in FORMS:
            continue
        filed = datetime.fromisoformat(rec["acceptanceDateTime"][i].replace("Z", "+00:00")).astimezone(UTC)
        if filed.date() < since:
            break
        if form == "4":  # many per day; keep one per day
            if filed.date() in form4_days:
                continue
            form4_days.add(filed.date())
        label, importance = FORMS[form]
        items = [ITEMS_8K.get(x.strip()) for x in (rec["items"][i] or "").split(",") if x.strip()]
        items = [x for x in items if x]
        detail = f": {', '.join(items)}" if items else ""
        if form == "8-K" and any(x in ("results of operations",) for x in items):
            importance = 0.75
        acc = rec["accessionNumber"][i].replace("-", "")
        url = f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{acc}/{rec['primaryDocument'][i]}"
        out.append(RawItem(headline=f"{name} files {label}{detail}", published_at=filed,
                           source="SEC EDGAR", url=url, symbols=[symbol], kind="sec_filing",
                           sentiment=0.0, importance=importance))
    return out
