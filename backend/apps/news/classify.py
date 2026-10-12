"""Turn a raw headline into kind / sentiment / importance, without any paid API.

A small finance lexicon (in the spirit of Loughran-McDonald) plus event keywords. It is
deliberately conservative: unknown wording scores neutral rather than guessing.
"""
import re

POSITIVE = {
    "beat", "beats", "tops", "surpass", "surpasses", "exceeds", "record", "raises", "raised",
    "upgrade", "upgrades", "upgraded", "outperform", "buy rating", "strong", "surge", "surges",
    "soar", "soars", "jump", "jumps", "rally", "rallies", "gain", "gains", "climb", "climbs",
    "rise", "rises", "boost", "boosts", "approval", "approved", "wins", "win", "growth",
    "profit", "profits", "bullish", "higher", "rebound", "rebounds", "buyback", "repurchase",
    "dividend increase", "partnership", "expands", "breakthrough", "upbeat", "optimistic",
    "cools", "eases", "cut rates", "rate cut",
}
NEGATIVE = {
    "miss", "misses", "missed", "falls", "fall", "drop", "drops", "plunge", "plunges", "sink",
    "sinks", "slump", "slumps", "tumble", "tumbles", "slide", "slides", "decline", "declines",
    "downgrade", "downgrades", "downgraded", "underperform", "sell rating", "cut", "cuts",
    "lowers", "lowered", "weak", "warning", "warns", "probe", "investigation", "lawsuit", "sued",
    "recall", "recalls", "loss", "losses", "layoffs", "layoff", "bearish", "lower", "fraud",
    "resigns", "departure", "delay", "delays", "halt", "halted", "antitrust", "fine", "fined",
    "hot inflation", "runs hot", "selloff", "sell-off", "crash", "fears", "concerns",
}
NEGATORS = {"not", "no", "fails", "without"}

KIND_RULES = [
    ("earnings", r"\b(earnings|eps|quarterly results|q[1-4] results|revenue (beat|miss)|guidance)\b"),
    ("analyst", r"\b(upgrade[sd]?|downgrade[sd]?|price target|initiates coverage|rating|outperform|underperform|overweight|underweight)\b"),
    ("sec_filing", r"\b(8-k|10-q|10-k|form 4|sec filing|13f|s-1)\b"),
    ("macro", r"\b(fed|fomc|powell|inflation|cpi|pce|ppi|jobs report|payrolls|nonfarm|unemployment rate|treasury yields?|rate (cut|hike)s?|gdp|recession|tariffs?)\b"),
]
IMPORTANT = re.compile(
    r"\b(earnings|guidance|downgrade|upgrade|fda|acquisition|acquire|merger|lawsuit|probe|"
    r"investigation|ceo|cfo|resign|recall|buyback|layoffs|bankruptcy|split|halt|record|"
    r"plunge|soar|surge|tumble|fed|cpi|jobs report)\b", re.I)
LOW_VALUE = re.compile(r"\b(\d+ stocks? to|top \d+|should you buy|is it time to|motley fool|"
                       r"here's why|what to know|prediction|could be|might|ways to)\b", re.I)


def classify(headline: str, summary: str = "", kind_hint: str | None = None) -> dict:
    text = f"{headline}. {summary}".lower()
    words = re.findall(r"[a-z][a-z\-']*", text)
    score = 0
    for i, w in enumerate(words):
        two = f"{w} {words[i + 1]}" if i + 1 < len(words) else ""
        hit = 1 if (w in POSITIVE or two in POSITIVE) else -1 if (w in NEGATIVE or two in NEGATIVE) else 0
        if hit and i > 0 and words[i - 1] in NEGATORS:
            hit = -hit
        # headline words count double
        score += hit * (2 if w in headline.lower() else 1)
    sentiment = max(-1.0, min(1.0, score / 4))
    kind = kind_hint
    if not kind:
        kind = "news"
        for k, pattern in KIND_RULES:
            if re.search(pattern, text):
                kind = k
                break
    importance = 0.45
    if IMPORTANT.search(headline):
        importance += 0.25
    if kind in ("earnings", "analyst", "sec_filing"):
        importance += 0.1
    if LOW_VALUE.search(headline):
        importance -= 0.25
    return {"kind": kind, "sentiment": round(sentiment, 3),
            "importance": round(max(0.05, min(1.0, importance)), 3)}
