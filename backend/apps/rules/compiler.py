"""Natural language -> RuleSpec. Regex for common shapes, Claude for everything else.

The output is always validated by the RuleSpec Pydantic model before the user sees it.
"""
from __future__ import annotations

import re

from pydantic import ValidationError

from apps.assistant import llm
from apps.market.resolve import resolve_symbol
from apps.market.universe import ETFS, STOCKS

from .spec import RuleSpec


class CompileError(Exception):
    pass


NUM = r"\$?[\d,]*\.?\d+"
DIR_WORDS = {"above": ">=", "over": ">=", "below": "<=", "under": "<="}
SUBJECT_VERBS = r"(?:goes|is|trades|gets|rises|falls|drops|moves|hits|reaches|climbs|dips)?"


def _num(s: str) -> float:
    return float(s.replace("$", "").replace(",", ""))


def _action(act: str | None, amt: str | None, sym: str) -> dict:
    act = (act or "").lower()
    if not act or "alert" in act or "notify" in act:
        return {"type": "notify"}
    amt = (amt or "").lower()
    if act == "buy":
        if amt.startswith("$"):
            return {"type": "buy_notional", "symbol": sym, "amount": _num(amt)}
        if not amt:
            raise CompileError("How much should I buy? e.g. “buy 10” or “buy $500”.")
        return {"type": "buy_qty", "symbol": sym, "quantity": _num(amt)}
    if amt in ("all", "everything", "it"):
        return {"type": "close_position", "symbol": sym}
    if amt == "half":
        return {"type": "sell_pct", "symbol": sym, "pct": 50}
    if amt.endswith("%"):
        return {"type": "sell_pct", "symbol": sym, "pct": _num(amt[:-1])}
    if not amt:
        return {"type": "close_position", "symbol": sym}
    return {"type": "sell_qty", "symbol": sym, "quantity": _num(amt)}


PATTERNS = [
    # alert me when AAPL goes above 250
    re.compile(rf"^(?:alert|notify|tell|ping)\s+me\s+(?:when|if)\s+(?P<sym>.+?)\s+{SUBJECT_VERBS}\s*"
               rf"(?P<dir>above|over|below|under)\s+(?P<px>{NUM})$", re.I),
    # if TSLA falls below 200, buy 5 (shares)
    re.compile(rf"^(?:if|when|whenever)\s+(?P<sym>.+?)\s+{SUBJECT_VERBS}\s*"
               rf"(?P<dir>above|over|below|under)\s+(?P<px>{NUM})\s*,?\s*(?:then\s+)?"
               rf"(?P<act>buy|sell|alert me|notify me)(?:\s+(?P<amt>{NUM}|all|half|\d+%))?"
               rf"(?:\s+shares?)?(?:\s+(?:of|worth of)\s+(?P<sym2>[\w .&'-]+))?$", re.I),
    # if NVDA drops 5% (today), buy $1000
    re.compile(rf"^(?:if|when|whenever)\s+(?P<sym>.+?)\s+(?P<verb>drops|falls|is down|declines|"
               rf"sinks|rises|jumps|is up|gains|rallies)\s+(?:more than\s+|over\s+|by\s+|at least\s+)?"
               rf"(?P<pct>[\d.]+)\s*%(?:\s+today)?\s*,?\s*(?:then\s+)?(?P<act>buy|sell|alert me|notify me)"
               rf"(?:\s+(?P<amt>{NUM}|all|half|\d+%))?(?:\s+shares?)?"
               rf"(?:\s+(?:of|worth of)\s+(?P<sym2>[\w .&'-]+))?$", re.I),
]


def compile_regex(text: str) -> dict | None:
    t = re.sub(r"\s+", " ", text.strip().rstrip(".!"))
    for p in PATTERNS:
        m = p.match(t)
        if not m:
            continue
        g = m.groupdict()
        sym = resolve_symbol(g["sym"])
        if not sym:
            raise CompileError(f"I couldn't find a stock called “{g['sym']}”.")
        target = resolve_symbol(g.get("sym2")) or sym
        if g.get("dir"):
            clause = {"metric": "price", "symbol": sym, "op": DIR_WORDS[g["dir"].lower()],
                      "value": _num(g["px"])}
            label = f"{sym} {g['dir'].lower()} ${_num(g['px']):,.2f}"
        else:
            down = g["verb"].lower() in ("drops", "falls", "is down", "declines", "sinks")
            pct = float(g["pct"])
            clause = {"metric": "pct_change", "symbol": sym, "window": "since_prev_close",
                      "op": "<=" if down else ">=", "value": -pct if down else pct}
            label = f"{sym} {'down' if down else 'up'} {pct:g}% today"
        action = _action(g.get("act"), g.get("amt"), target)
        verb = {"notify": "Alert"}.get(action["type"], action["type"].split("_")[0].title())
        return {"name": f"{verb}: {label}", "condition": {"logic": "all", "clauses": [clause]},
                "action": action, "mode": "once"}
    return None


# ------------------------------------------------------------------------------------------
# LLM compiler
# ------------------------------------------------------------------------------------------
def _nullable(t: dict) -> dict:
    return {"anyOf": [t, {"type": "null"}]}


RULE_SCHEMA = {
    "type": "object",
    "properties": {
        "name": {"type": "string"},
        "logic": {"type": "string", "enum": ["all", "any"]},
        "clauses": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "metric": {"type": "string", "enum": [
                        "price", "pct_change", "rsi", "sma", "ema", "volume_ratio",
                        "position_pnl_pct", "position_qty", "cash", "portfolio_value",
                        "time_of_day", "news_sentiment", "earnings_released"]},
                    "symbol": _nullable({"type": "string"}),
                    "op": {"type": "string",
                           "enum": ["<", "<=", ">", ">=", "crosses_above", "crosses_below"]},
                    "value": _nullable({"type": "number"}),
                    "time_value": _nullable({"type": "string"}),
                    "period": _nullable({"type": "integer"}),
                    "timeframe": {"type": "string", "enum": ["1m", "1d"]},
                    "window": {"type": "string", "enum": [
                        "since_prev_close", "since_open", "5m", "15m", "60m", "5d"]},
                    "ref_metric": {"type": "string", "enum": ["none", "sma", "ema", "price"]},
                    "ref_period": _nullable({"type": "integer"}),
                },
                "required": ["metric", "symbol", "op", "value", "time_value", "period",
                             "timeframe", "window", "ref_metric", "ref_period"],
                "additionalProperties": False,
            },
        },
        "action": {
            "type": "object",
            "properties": {
                "type": {"type": "string", "enum": ["buy_qty", "buy_notional", "sell_qty",
                                                    "sell_pct", "close_position", "notify"]},
                "symbol": _nullable({"type": "string"}),
                "quantity": _nullable({"type": "number"}),
                "amount": _nullable({"type": "number"}),
                "pct": _nullable({"type": "number"}),
                "order_type": {"type": "string", "enum": ["market", "limit"]},
                "limit_price": _nullable({"type": "number"}),
                "message": _nullable({"type": "string"}),
            },
            "required": ["type", "symbol", "quantity", "amount", "pct", "order_type",
                         "limit_price", "message"],
            "additionalProperties": False,
        },
        "mode": {"type": "string", "enum": ["once", "repeat"]},
        "cooldown_minutes": {"type": "integer"},
        "clarification": _nullable({"type": "string"}),
    },
    "required": ["name", "logic", "clauses", "action", "mode", "cooldown_minutes",
                 "clarification"],
    "additionalProperties": False,
}

UNIVERSE = ", ".join(f"{s[0]} ({s[1]})" for s in STOCKS) + ", " + \
    ", ".join(f"{e[0]} ({e[1]})" for e in ETFS)

RULE_SYSTEM = f"""You convert a trader's plain-English automation into a structured rule for a
paper-trading app. Output only the JSON object described by the schema.

Metrics (clause.metric):
- price: last price in dollars. pct_change: percent change over `window`
  (since_prev_close = "today", since_open, 5m, 15m, 60m, 5d). Drops are negative values,
  e.g. "drops 5%" -> op "<=", value -5.
- rsi / sma / ema: indicator with `period` (RSI default 14) on `timeframe` (1d daily, 1m minute).
- Crosses: use op crosses_above / crosses_below. To compare against another indicator, set
  ref_metric (sma/ema/price) and ref_period, and set value to null. E.g. "50-day crosses above
  200-day" -> metric sma period 50, op crosses_above, ref_metric sma, ref_period 200.
- volume_ratio: today's volume / 20-day average (e.g. "3x normal volume" -> >= 3).
- position_pnl_pct: unrealized % gain/loss on the user's position. position_qty: shares held.
- cash, portfolio_value: dollars. time_of_day: set time_value "HH:MM" (24h, US Eastern) and
  value null, e.g. "before 3pm" -> op "<", time_value "15:00".
- news_sentiment: average sentiment of the last hour of news, -1..1.
- earnings_released: op ">=", value 1 when the rule should fire after the company reports.
Set unused fields to null; use timeframe "1d", window "since_prev_close", ref_metric "none"
when they don't apply.

Actions: buy_qty (quantity), buy_notional (amount in dollars), sell_qty (quantity),
sell_pct (pct of position), close_position, notify (message). Use order_type "limit" only if the
user gives a limit price. "Alert/notify/tell me" means notify.
mode: "once" unless the user says every time/whenever/each time; cooldown_minutes default 60.
name: short label, at most 6 words.

Tickers available: {UNIVERSE}. These are the most popular tickers; any other US-listed stock or ETF ticker is also valid.
Map company names to tickers. If the request needs a
stock outside this list, a capability not listed (short selling, options, crypto), or is too
ambiguous to act on safely, put a short question or explanation in `clarification` and still
fill the other fields with your best guess."""


def compile_llm(text: str) -> dict:
    out = llm.structured(RULE_SYSTEM, text, RULE_SCHEMA, effort="low", max_tokens=3000)
    if out.get("clarification"):
        raise CompileError(out["clarification"])
    clauses = []
    for c in out["clauses"]:
        clause = {k: c[k] for k in ("metric", "symbol", "op", "value", "time_value", "period",
                                    "timeframe", "window") if c.get(k) is not None}
        if c.get("ref_metric") and c["ref_metric"] != "none":
            clause["ref"] = {"metric": c["ref_metric"], "period": c.get("ref_period"),
                             "timeframe": c.get("timeframe") or "1d"}
        clauses.append(clause)
    action = {k: v for k, v in out["action"].items() if v is not None}
    return {"name": out["name"][:80], "condition": {"logic": out["logic"], "clauses": clauses},
            "action": action, "mode": out["mode"],
            "cooldown_seconds": max(60, out.get("cooldown_minutes", 60) * 60)}


def compile_text(text: str, user=None) -> tuple[RuleSpec, str]:
    """Returns (spec, method). Raises CompileError with a user-facing message."""
    text = text.strip()
    if not text:
        raise CompileError("Describe the rule, e.g. “if NVDA drops 5% today, buy $1,000”.")
    raw, method = compile_regex(text), "regex"
    if raw is None:
        if not llm.enabled() or (user and not user.ai_enabled):
            raise CompileError(
                "I can only understand simple rules without AI, like “if AAPL falls below 200, "
                "buy 5” or “alert me when TSLA goes above 300”. Use the rule builder for more, "
                "or set ANTHROPIC_API_KEY to enable natural-language rules.")
        if user:
            llm.check_quota(user)
        try:
            raw, method = compile_llm(text), "llm"
        except llm.LLMUnavailable as e:
            raise CompileError(str(e)) from e
    try:
        spec = RuleSpec.model_validate(raw)
    except ValidationError as e:
        msg = "; ".join(err["msg"].removeprefix("Value error, ") for err in e.errors()[:3])
        raise CompileError(f"That rule isn't valid: {msg}") from e
    from apps.market.models import Stock

    known = set(Stock.objects.filter(symbol__in=spec.symbols()).values_list("symbol", flat=True))
    if missing := spec.symbols() - known:
        raise CompileError(f"Unknown symbol(s): {', '.join(sorted(missing))}.")
    return spec, method
