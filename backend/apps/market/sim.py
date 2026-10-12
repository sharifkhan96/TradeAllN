"""Simulated market: a factor model with news-driven jumps.

Every instrument's return is   exposures · factor returns  +  idiosyncratic noise  +  own catalysts.
Factors are the market and each sector; catalysts are news items (earnings, analyst calls,
company news, macro releases, sector news). Each catalyst is written as a NewsArticle that is
published *before* (or exactly when) the price reacts, which is what lets the explanation
engine attribute moves to news without lookahead.

Everything here is labelled simulated in the UI.
"""
from __future__ import annotations

import hashlib
import math
import random
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta

from .hours import ET, is_trading_day
from .universe import ETFS, SECTOR_ETFS, STOCKS

SIM_SOURCE = "Simulated Newswire"
BROKERS = ["Halden & Co.", "Northbridge Securities", "Merriton Capital", "Ashgrove Research",
           "Calder Partners"]
MINUTES = 390  # regular session minutes


# --------------------------------------------------------------------------------------------
# Instruments
# --------------------------------------------------------------------------------------------
@dataclass
class Instrument:
    symbol: str
    name: str
    price: float
    vol: float  # daily idiosyncratic vol
    exposures: dict[str, float]  # factor -> loading ("mkt" or sector name)
    sector: str = ""
    is_etf: bool = False
    short: str = ""

    @property
    def label(self):
        return self.short or self.name


def instruments() -> list[Instrument]:
    out = []
    for sym, name, _ex, sector, price, beta, vol, _cap, _pe in STOCKS:
        short = (name.replace(", Inc.", "").replace(" Inc.", "").replace(" Corporation", "")
                 .replace(" Incorporated", "").replace(" Company", "").replace("The ", "")
                 .replace(" & Co.", "").replace(" Class A", "").replace(" Group", ""))
        out.append(Instrument(sym, name, price, vol, {"mkt": beta, sector: 0.8}, sector, False,
                              short.strip()))
    for sym, name, price, mkt, sectors, vol in ETFS:
        out.append(Instrument(sym, name, price, vol, {"mkt": mkt, **dict(sectors)}, "", True, sym))
    return out


# --------------------------------------------------------------------------------------------
# Catalyst templates
# --------------------------------------------------------------------------------------------
@dataclass
class Catalyst:
    ts: datetime
    kind: str
    headline: str
    summary: str
    impact: float  # log-return applied to the target
    symbol: str | None = None  # company catalyst
    sector: str | None = None  # sector-wide catalyst
    macro: bool = False
    source: str = SIM_SOURCE
    importance: float = 0.6
    payload: dict = field(default_factory=dict)

    @property
    def sentiment(self) -> float:
        if abs(self.impact) < 0.002:
            return 0.0
        return max(-1.0, min(1.0, self.impact * 18))


def _q(d: date) -> int:
    return (d.month - 1) // 3 + 1


def company_catalyst(rng: random.Random, inst: Instrument, ts: datetime, up: bool,
                     size: float) -> Catalyst:
    n = inst.label
    if up:
        pick = rng.choice([
            ("analyst", f"{rng.choice(BROKERS)} upgrades {n} to Buy, lifts target to "
                        f"${inst.price * (1 + size * 4):,.0f}",
             f"The analyst cited accelerating demand and margin expansion at {n}."),
            ("press_release", f"{n} announces ${rng.randint(5, 60)}B share buyback program",
             f"{n}'s board authorized a new repurchase plan, signalling confidence in cash flow."),
            ("news", f"{n} wins multi-year contract worth an estimated ${rng.randint(2, 15)}B",
             "The deal is expected to add to revenue starting next fiscal year."),
            ("news", f"{n} unveils new product line, early reviews strong",
             f"Analysts said the launch could expand {n}'s addressable market."),
            ("sec_filing", f"Form 4: {n} director buys ${rng.randint(1, 9)}.{rng.randint(0, 9)}M "
                           f"of shares on the open market",
             "Insider purchases of this size are uncommon and often read as a vote of confidence."),
            ("news", f"Regulators clear {n}'s pending acquisition",
             "The approval removes a key overhang on the stock."),
        ])
    else:
        pick = rng.choice([
            ("analyst", f"{rng.choice(BROKERS)} downgrades {n} to Underperform on valuation",
             f"The note flagged slowing growth and stretched multiples at {n}."),
            ("news", f"{n} faces regulatory probe over business practices",
             "Officials opened an inquiry; the company said it will cooperate."),
            ("sec_filing", f"8-K: {n} announces unexpected CFO departure",
             "The filing said the executive is leaving to pursue other opportunities."),
            ("news", f"{n} recalls products over safety concerns",
             "The company expects a one-time charge in the current quarter."),
            ("news", f"Key customer reportedly shifts orders away from {n}",
             "The report cited people familiar with the matter."),
            ("press_release", f"{n} cuts full-year outlook citing softer demand",
             "Management lowered revenue guidance at the midpoint."),
        ])
    kind, headline, summary = pick
    return Catalyst(ts, kind, headline, summary, size if up else -size, symbol=inst.symbol,
                    importance=0.55 + min(0.4, size * 6))


def earnings_catalyst(rng: random.Random, inst: Instrument, ts: datetime, size: float,
                      up: bool) -> Catalyst:
    n = inst.label
    est = round(rng.uniform(0.4, 6.0), 2)
    surprise = rng.uniform(0.04, 0.18) * (1 if up else -1)
    actual = round(est * (1 + surprise), 2)
    q = _q(ts.date())
    if up:
        headline = f"{n} beats Q{q} estimates: EPS ${actual} vs ${est} expected; raises guidance"
        summary = f"Revenue also topped forecasts. {n} lifted its full-year outlook."
    else:
        headline = f"{n} misses Q{q} estimates: EPS ${actual} vs ${est} expected"
        summary = f"{n} reported weaker margins and gave cautious commentary on the next quarter."
    return Catalyst(ts, "earnings", headline, summary, size if up else -size, symbol=inst.symbol,
                    importance=0.95,
                    payload={"eps_actual": actual, "eps_estimate": est,
                             "surprise_pct": round(surprise * 100, 1)})


def noise_catalyst(rng: random.Random, inst: Instrument, ts: datetime) -> Catalyst:
    n = inst.label
    headline = rng.choice([
        f"{n} to present at upcoming industry conference",
        f"{n} declares regular quarterly dividend",
        f"{n} names new head of investor relations",
        f"{n} publishes annual sustainability report",
    ])
    return Catalyst(ts, "press_release", headline, "Routine company announcement.", 0.0,
                    symbol=inst.symbol, importance=0.15)


MACRO = {
    "cpi": [("CPI cools to {v}% y/y, softer than expected; rate-cut bets rise", True),
            ("CPI runs hot at {v}% y/y, above forecasts; Treasury yields jump", False)],
    "jobs": [("Payrolls beat with {n}K jobs added; wage growth steady", True),
             ("Hiring slows sharply: only {n}K jobs added, unemployment ticks up", False)],
    "fomc": [("Fed holds rates, signals cuts are coming later this year", True),
             ("Fed holds rates but warns inflation fight is not over; fewer cuts projected", False)],
}

SECTOR_NEWS = {
    "Technology": [("Chip stocks rally as cloud providers raise AI spending plans", True),
                   ("Tech sells off on new export-control fears for semiconductors", False)],
    "Communication Services": [("Digital ad market rebounds, industry data shows", True),
                               ("Lawmakers advance tougher rules for online platforms", False)],
    "Consumer Discretionary": [("Retail sales beat estimates as shoppers keep spending", True),
                               ("Consumer confidence falls to a one-year low", False)],
    "Financials": [("Banks climb as yield curve steepens", True),
                   ("Regulators propose higher capital requirements for large banks", False)],
    "Health Care": [("Drugmakers rise after favorable pricing ruling", True),
                    ("Health stocks slide on drug-pricing reform proposal", False)],
    "Energy": [("Oil jumps after OPEC+ agrees to deeper output cuts", True),
               ("Crude slumps as inventories swell more than expected", False)],
    "Industrials": [("Factory activity expands for third straight month (ISM)", True),
                    ("Industrial orders contract unexpectedly", False)],
    "Consumer Staples": [("Investors rotate into defensive consumer names", True),
                         ("Staples slip as input-cost pressures return", False)],
}


def macro_catalyst(rng: random.Random, kind: str, ts: datetime, size: float, up: bool) -> Catalyst:
    template = MACRO[kind][0 if up else 1][0]
    headline = template.format(v=round(rng.uniform(2.1, 3.6), 1), n=rng.randint(60, 320))
    titles = {"cpi": "Consumer Price Index", "jobs": "Employment Situation", "fomc": "FOMC decision"}
    return Catalyst(ts, "macro", headline, f"{titles[kind]} release.", size if up else -size,
                    macro=True, importance=0.9, payload={"event": kind})


def sector_catalyst(rng: random.Random, sector: str, ts: datetime, size: float,
                    up: bool) -> Catalyst:
    headline = SECTOR_NEWS[sector][0 if up else 1][0]
    return Catalyst(ts, "sector", headline, f"Sector-wide move across {sector}.",
                    size if up else -size, sector=sector, importance=0.7)


# --------------------------------------------------------------------------------------------
# Historical generation
# --------------------------------------------------------------------------------------------
@dataclass
class Bar:
    ts: datetime
    o: float
    h: float
    l: float  # noqa: E741
    c: float
    v: int


@dataclass
class History:
    daily: dict[str, list[Bar]]
    minute: dict[str, list[Bar]]
    catalysts: list[Catalyst]
    upcoming: list[Catalyst]


def _session_ts(d: date, minute: int) -> datetime:
    return datetime.combine(d, time(9, 30), ET) + timedelta(minutes=minute)


def trading_days_back(end: date, n: int) -> list[date]:
    days, d = [], end
    while len(days) < n:
        if is_trading_day(d):
            days.append(d)
        d -= timedelta(days=1)
    return list(reversed(days))


def generate_history(end: date, n_days: int = 504, intraday_days: int = 10,
                     seed: int = 7) -> History:
    rng = random.Random(seed)
    insts = instruments()
    days = trading_days_back(end, n_days)
    sectors = list(SECTOR_ETFS)
    factors = ["mkt", *sectors]
    catalysts: list[Catalyst] = []

    # Factor daily returns split into an overnight part and an intraday part.
    # Intraday factor jumps are remembered with their minute for the minute paths.
    f_over = {f: [0.0] * len(days) for f in factors}
    f_intra = {f: [0.0] * len(days) for f in factors}
    f_jumps: dict[str, dict[int, list[tuple[int, float]]]] = {f: {} for f in factors}

    macro_cycle = ["cpi", "jobs", "fomc"]
    for i, d in enumerate(days):
        f_over["mkt"][i] = rng.gauss(0.0002, 0.003)
        f_intra["mkt"][i] = rng.gauss(0.0002, 0.0065)
        if i % 14 == 7:  # a macro release roughly every 3 weeks
            kind = macro_cycle[(i // 14) % 3]
            up = rng.random() < 0.55
            size = rng.uniform(0.008, 0.02)
            if kind == "fomc":
                minute = 270  # 2:00 pm ET
                ts = _session_ts(d, minute)
                f_jumps["mkt"].setdefault(i, []).append((minute, size if up else -size))
                f_intra["mkt"][i] += size if up else -size
            else:
                ts = datetime.combine(d, time(8, 30), ET)
                f_over["mkt"][i] += size if up else -size
            catalysts.append(macro_catalyst(rng, kind, ts, size, up))
        for s in sectors:
            f_over[s][i] = rng.gauss(0, 0.002)
            f_intra[s][i] = rng.gauss(0, 0.0045)
            if rng.random() < 1 / 38:
                up = rng.random() < 0.5
                size = rng.uniform(0.012, 0.028)
                minute = rng.randint(30, 360)
                f_jumps[s].setdefault(i, []).append((minute, size if up else -size))
                f_intra[s][i] += size if up else -size
                catalysts.append(sector_catalyst(rng, s, _session_ts(d, minute), size, up))

    # Shared minute-level factor paths for the intraday window.
    intra_start = len(days) - intraday_days
    f_minute: dict[str, dict[int, list[float]]] = {f: {} for f in factors}
    for f in factors:
        for i in range(intra_start, len(days)):
            steps = [rng.gauss(0, 1) for _ in range(MINUTES)]
            jumps = dict()
            for minute, size in f_jumps[f].get(i, []):
                for k in range(3):  # spread jump over 3 minutes
                    jumps[minute + k] = jumps.get(minute + k, 0) + size / 3
            noise_target = f_intra[f][i] - sum(j for j in jumps.values())
            scale = 0.0065 / math.sqrt(MINUTES) if f == "mkt" else 0.0045 / math.sqrt(MINUTES)
            path = [s * scale for s in steps]
            drift = (noise_target - sum(path)) / MINUTES
            f_minute[f][i] = [p + drift + jumps.get(k, 0) for k, p in enumerate(path)]

    daily: dict[str, list[Bar]] = {}
    minute: dict[str, list[Bar]] = {}
    upcoming: list[Catalyst] = []
    for idx, inst in enumerate(insts):
        own_over = [0.0] * len(days)
        own_intra = [0.0] * len(days)
        own_jumps: dict[int, list[tuple[int, float]]] = {}
        if not inst.is_etf:
            earn_offset = (idx * 7) % 63
            for i, d in enumerate(days):
                scale = inst.vol / 0.018
                if i % 63 == earn_offset:  # quarterly earnings, published pre-market
                    up = rng.random() < 0.58
                    size = rng.uniform(0.03, 0.09) * scale
                    own_over[i] += size if up else -size
                    catalysts.append(earnings_catalyst(rng, inst, datetime.combine(d, time(7, 0), ET),
                                                       size, up))
                elif rng.random() < 1 / 9:
                    up = rng.random() < 0.55
                    size = rng.uniform(0.015, 0.05) * scale
                    m = rng.randint(15, 370)
                    own_jumps.setdefault(i, []).append((m, size if up else -size))
                    own_intra[i] += size if up else -size
                    catalysts.append(company_catalyst(rng, inst, _session_ts(d, m), up, size))
                elif rng.random() < 1 / 30:
                    catalysts.append(noise_catalyst(rng, inst, _session_ts(d, rng.randint(10, 380))))
            # next earnings date for the catalyst calendar
            days_since = (len(days) - 1 - earn_offset) % 63
            ahead = 63 - days_since
            nxt = end
            while ahead > 0:
                nxt += timedelta(days=1)
                if is_trading_day(nxt):
                    ahead -= 1
            upcoming.append(Catalyst(datetime.combine(nxt, time(7, 0), ET), "earnings",
                                     f"{inst.label} Q{_q(nxt)} earnings (expected)", "", 0.0,
                                     symbol=inst.symbol))

        # Walk backwards from today's reference price so the latest price lands near base price.
        total = 0.0
        rets = []
        for i in range(len(days)):
            over = sum(w * f_over[f][i] for f, w in inst.exposures.items()) + own_over[i] \
                + rng.gauss(0, inst.vol * 0.2)
            intra = sum(w * f_intra[f][i] for f, w in inst.exposures.items()) + own_intra[i] \
                + rng.gauss(0, inst.vol * 0.65)
            rets.append((over, intra))
            total += over + intra
        price = inst.price * math.exp(-total)
        base_vol = 2_000_000 + rng.randint(0, 30_000_000)
        bars = []
        mbars = []
        for i, d in enumerate(days):
            over, intra = rets[i]
            o = price * math.exp(over)
            c = o * math.exp(intra)
            surprise = (abs(over) + abs(intra)) / max(inst.vol, 1e-4)
            v = int(base_vol * (0.7 + 0.25 * surprise + rng.random() * 0.3))
            if i >= intra_start:
                # minute path = factor minute paths + own noise + own jumps, bridged to close
                jumps = {}
                for m, size in own_jumps.get(i, []):
                    for k in range(3):
                        jumps[m + k] = jumps.get(m + k, 0) + size / 3
                steps = []
                for k in range(MINUTES):
                    s = sum(w * f_minute[f][i][k] for f, w in inst.exposures.items() if f in f_minute)
                    s += rng.gauss(0, inst.vol * 0.65 / math.sqrt(MINUTES)) + jumps.get(k, 0)
                    steps.append(s)
                drift = (intra - sum(steps)) / MINUTES
                p = o
                hi, lo = o, o
                for k in range(MINUTES):
                    nxt = p * math.exp(steps[k] + drift)
                    wig = abs(rng.gauss(0, inst.vol * 0.12 / math.sqrt(MINUTES / 10)))
                    bh, bl = max(p, nxt) * (1 + wig), min(p, nxt) * (1 - wig)
                    mv = int(v / MINUTES * (2.2 if k < 30 or k > 360 else 0.85)
                             * (1 + 40 * abs(steps[k])) * (0.6 + rng.random() * 0.8))
                    mbars.append(Bar(_session_ts(d, k), p, bh, bl, nxt, mv))
                    hi, lo = max(hi, bh), min(lo, bl)
                    p = nxt
                c = p
                h, low = hi, lo
            else:
                wig = abs(rng.gauss(0, inst.vol * 0.45))
                h = max(o, c) * (1 + wig)
                low = min(o, c) * (1 - abs(rng.gauss(0, inst.vol * 0.45)))
            bars.append(Bar(datetime.combine(d, time(0, 0), ET), o, h, low, c, v))
            price = c
        daily[inst.symbol] = bars
        minute[inst.symbol] = mbars
        inst.price = price

    # Upcoming macro events for the calendar.
    d, count = end, 0
    while count < 3:
        d += timedelta(days=1)
        if is_trading_day(d) and d.day in (2, 3, 10, 11, 12, 17, 18, 24, 25):
            kind = macro_cycle[count % 3]
            title = {"cpi": "CPI report", "jobs": "Jobs report", "fomc": "FOMC rate decision"}[kind]
            ts = datetime.combine(d, time(14, 0) if kind == "fomc" else time(8, 30), ET)
            upcoming.append(Catalyst(ts, kind, title, "", 0.0, macro=True))
            count += 1
    return History(daily, minute, sorted(catalysts, key=lambda c: c.ts), upcoming)


def dedupe_hash(c: Catalyst) -> str:
    return hashlib.sha256(f"{c.headline}|{c.ts.isoformat()}|{c.symbol}".encode()).hexdigest()


# --------------------------------------------------------------------------------------------
# Live simulation (one step per tick)
# --------------------------------------------------------------------------------------------
@dataclass
class PendingJump:
    remaining: float
    steps_left: int


class LiveSim:
    """Advances prices one tick at a time. Catalysts are published, then the price reacts."""

    def __init__(self, prices: dict[str, float], seed: int | None = None, tick_seconds: float = 1.0):
        self.rng = random.Random(seed)
        self.insts = {i.symbol: i for i in instruments() if i.symbol in prices}
        for s, p in prices.items():
            if s in self.insts:
                self.insts[s].price = p
        self.factor_jumps: dict[str, PendingJump] = {}
        self.own_jumps: dict[str, PendingJump] = {}
        # Per-tick volatility, mildly accelerated vs. reality (~0.7%/hour for a typical stock)
        # so movement is visible on a 1-second chart.
        self.k = 0.00012 * math.sqrt(tick_seconds)

    def _maybe_catalyst(self, now: datetime) -> Catalyst | None:
        roll = self.rng.random()
        stocks = [i for i in self.insts.values() if not i.is_etf]
        if roll < 1 / 300 and stocks:
            inst = self.rng.choice(stocks)
            up = self.rng.random() < 0.55
            size = self.rng.uniform(0.012, 0.035) * inst.vol / 0.018
            cat = company_catalyst(self.rng, inst, now, up, size)
            self.own_jumps[inst.symbol] = PendingJump(cat.impact, 6)
            return cat
        if roll < 1 / 300 + 1 / 1200:
            sector = self.rng.choice(list(SECTOR_ETFS))
            up = self.rng.random() < 0.5
            cat = sector_catalyst(self.rng, sector, now, self.rng.uniform(0.008, 0.016), up)
            self.factor_jumps[sector] = PendingJump(cat.impact, 8)
            return cat
        if roll < 1 / 300 + 1 / 1200 + 1 / 3600:
            kind = self.rng.choice(["cpi", "jobs", "fomc"])
            up = self.rng.random() < 0.55
            cat = macro_catalyst(self.rng, kind, now, self.rng.uniform(0.004, 0.009), up)
            self.factor_jumps["mkt"] = PendingJump(cat.impact, 10)
            return cat
        return None

    @staticmethod
    def _drain(jumps: dict[str, PendingJump], key: str) -> float:
        j = jumps.get(key)
        if not j:
            return 0.0
        step = j.remaining / j.steps_left
        j.remaining -= step
        j.steps_left -= 1
        if j.steps_left <= 0:
            del jumps[key]
        return step

    def step(self, now: datetime) -> tuple[dict[str, float], Catalyst | None]:
        """Returns new prices and, if one fired this tick, the catalyst (published before moving)."""
        cat = self._maybe_catalyst(now)
        shocks = {"mkt": self.rng.gauss(0, self.k * 0.55) + self._drain(self.factor_jumps, "mkt")}
        for s in SECTOR_ETFS:
            shocks[s] = self.rng.gauss(0, self.k * 0.4) + self._drain(self.factor_jumps, s)
        out = {}
        for sym, inst in self.insts.items():
            r = sum(w * shocks.get(f, 0) for f, w in inst.exposures.items())
            r += self.rng.gauss(0, self.k * inst.vol / 0.018 * (0.3 if inst.is_etf else 1))
            r += self._drain(self.own_jumps, sym)
            inst.price *= math.exp(r)
            out[sym] = inst.price
        return out, cat
