"""Segment a bar series into up / down / flat moves, normalised by volatility.

A zigzag pass starts a new segment whenever price reverses by more than `k` standard
deviations of the series' per-bar returns (scaled by sqrt of segment length so long
quiet drifts aren't chopped into noise). Segments whose total move is small relative to
volatility are labelled flat.
"""
import math
from dataclasses import dataclass


@dataclass
class Segment:
    i0: int
    i1: int  # inclusive
    start_t: int
    end_t: int
    p0: float
    p1: float
    z: float

    @property
    def pct(self) -> float:
        return (self.p1 / self.p0 - 1) * 100 if self.p0 else 0.0

    @property
    def direction(self) -> str:
        if abs(self.z) < 1.2 and abs(self.pct) < 1.5:
            return "flat"
        return "up" if self.p1 > self.p0 else "down"


def per_bar_sigma(bars) -> float:
    rets = [math.log(bars[i]["c"] / bars[i - 1]["c"]) for i in range(1, len(bars))
            if bars[i - 1]["c"] > 0]
    if len(rets) < 2:
        return 0.0
    mean = sum(rets) / len(rets)
    # robust: median absolute deviation, so the jumps we want to find don't inflate sigma
    mad = sorted(abs(r - mean) for r in rets)[len(rets) // 2]
    return max(mad * 1.4826, 1e-6)


def segment(bars: list[dict], k: float = 2.0, max_segments: int = 40,
            sigma: float | None = None) -> list[Segment]:
    if len(bars) < 2:
        return []
    sigma = sigma or per_bar_sigma(bars)
    window = max(3, len(bars) // 40)  # reversal scale grows with the visible range
    thresh = k * sigma * math.sqrt(window)
    closes = [b["c"] for b in bars]
    pivots, trend, ext = [0], 0, 0
    for i in range(1, len(bars)):
        c = closes[i]
        if trend == 0:
            d = math.log(c / closes[0])
            if abs(d) > thresh:
                trend, ext = (1 if d > 0 else -1), i
        elif trend == 1:
            if c >= closes[ext]:
                ext = i
            elif math.log(closes[ext] / c) > thresh:
                pivots.append(ext)
                trend, ext = -1, i
        else:
            if c <= closes[ext]:
                ext = i
            elif math.log(c / closes[ext]) > thresh:
                pivots.append(ext)
                trend, ext = 1, i
    if ext > pivots[-1]:
        pivots.append(ext)
    if pivots[-1] != len(bars) - 1:
        pivots.append(len(bars) - 1)

    segs = []
    for a, b in zip(pivots, pivots[1:], strict=False):
        p0 = bars[a]["c"] if a > 0 else bars[a]["o"]
        p1 = bars[b]["c"]
        n = max(1, b - a)
        z = math.log(p1 / p0) / (sigma * math.sqrt(n)) if p0 > 0 else 0.0
        segs.append(Segment(a, b, bars[a]["t"], bars[b]["t"], p0, p1, z))

    # merge adjacent flat segments; cap the count by merging the smallest moves
    merged: list[Segment] = []
    for s in segs:
        if merged and merged[-1].direction == "flat" and s.direction == "flat":
            m = merged[-1]
            n = max(1, s.i1 - m.i0)
            z = math.log(s.p1 / m.p0) / (sigma * math.sqrt(n))
            merged[-1] = Segment(m.i0, s.i1, m.start_t, s.end_t, m.p0, s.p1, z)
        else:
            merged.append(s)
    while len(merged) > max_segments:
        j = min(range(len(merged) - 1), key=lambda i: abs(merged[i].z) + abs(merged[i + 1].z))
        a, b = merged[j], merged[j + 1]
        n = max(1, b.i1 - a.i0)
        z = math.log(b.p1 / a.p0) / (sigma * math.sqrt(n))
        merged[j:j + 2] = [Segment(a.i0, b.i1, a.start_t, b.end_t, a.p0, b.p1, z)]
    return merged
