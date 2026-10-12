"""Text -> intent. A regex fast path handles the common shapes for free and instantly;
Claude (structured output) handles everything else. The output is only an *intent*: the
resolver turns it into concrete orders with deterministic code."""
from __future__ import annotations

import re

from apps.market.resolve import resolve_symbol
from apps.market.universe import ETFS, SECTOR_ETFS, STOCKS

from . import llm

RULE_START = re.compile(r"^\s*(if|when|whenever|alert me|notify me|tell me|ping me)\b", re.I)
QUESTION = re.compile(r"(\?\s*$)|^\s*(what|why|how|which|who|when did|is my|am i|show me my|"
                      r"explain)\b", re.I)
NUM = r"\$?[\d,]*\.?\d+"
ORDER = re.compile(
    rf"^\s*(?P<side>buy|sell|purchase|get)\s+(?P<amt>{NUM}|all(?: of)?|half(?: of)?|\d+%(?: of)?)"
    rf"\s*(?:shares?\s+(?:of\s+)?|worth\s+of\s+|of\s+|x\s+)?(?:my\s+)?(?P<sym>[a-z][\w .&'-]*?)"
    rf"(?:\s+shares?)?(?:\s+(?:at|@|for)\s+(?P<px>{NUM})(?:\s+or\s+better|\s+limit)?)?"
    rf"(?:\s+(?P<tif>gtc|good till cancell?ed|day))?\s*$", re.I)
CANCEL = re.compile(r"^\s*cancel\s+(?:all\s+)?(?:my\s+)?(?:open\s+)?(?P<sym>[\w .&'-]+?)?\s*"
                    r"orders?\s*$", re.I)


def _order_from_match(m) -> dict | None:
    sym = resolve_symbol(m["sym"])
    if not sym:
        return None
    side = "sell" if m["side"].lower() == "sell" else "buy"
    amt = m["amt"].lower().replace(" of", "")
    o = {"symbol": sym, "side": side, "order_type": "market", "limit_price": None,
         "stop_price": None, "stop_offset_pct": None, "limit_offset_pct": None,
         "time_in_force": "gtc" if (m["tif"] or "").lower().startswith(("gtc", "good")) else "day"}
    if amt == "all":
        o.update(qty_type="all_position", amount=None)
    elif amt == "half":
        o.update(qty_type="pct_position", amount=50)
    elif amt.endswith("%"):
        o.update(qty_type="pct_position", amount=float(amt[:-1]))
    elif amt.startswith("$"):
        o.update(qty_type="dollars", amount=float(amt[1:].replace(",", "")))
    else:
        o.update(qty_type="shares", amount=float(amt.replace(",", "")))
    if m["px"]:
        o.update(order_type="limit", limit_price=float(m["px"].replace("$", "").replace(",", "")))
    return o


def parse_regex(text: str) -> dict | None:
    if RULE_START.match(text):
        return {"intent": "rule"}
    if m := CANCEL.match(text):
        sym = resolve_symbol(m["sym"]) if m["sym"] and m["sym"].strip().lower() not in (
            "all", "my", "open") else None
        if m["sym"] and m["sym"].strip() and not sym and m["sym"].strip().lower() not in (
                "all", "my", "open", "all my", "all my open"):
            return None
        return {"intent": "cancel", "cancel": {"symbols": [sym] if sym else [], "all": not sym}}
    if m := ORDER.match(text.rstrip(".!")):
        o = _order_from_match(m)
        if o:
            return {"intent": "orders", "orders": [o], "selector": None}
    if QUESTION.search(text):
        return {"intent": "question"}
    sym = resolve_symbol(text) if len(text.split()) <= 3 else None
    if sym:
        return {"intent": "navigate", "symbol": sym}
    return None


def _nullable(t):
    return {"anyOf": [t, {"type": "null"}]}


ORDER_ITEM = {
    "type": "object",
    "properties": {
        "symbol": {"type": "string"},
        "side": {"type": "string", "enum": ["buy", "sell"]},
        "qty_type": {"type": "string",
                     "enum": ["shares", "dollars", "pct_position", "all_position", "pct_cash"]},
        "amount": _nullable({"type": "number"}),
        "order_type": {"type": "string", "enum": ["market", "limit", "stop", "stop_limit"]},
        "limit_price": _nullable({"type": "number"}),
        "stop_price": _nullable({"type": "number"}),
        "limit_offset_pct": _nullable({"type": "number"}),
        "stop_offset_pct": _nullable({"type": "number"}),
        "time_in_force": {"type": "string", "enum": ["day", "gtc"]},
    },
    "required": ["symbol", "side", "qty_type", "amount", "order_type", "limit_price",
                 "stop_price", "limit_offset_pct", "stop_offset_pct", "time_in_force"],
    "additionalProperties": False,
}

INTENT_SCHEMA = {
    "type": "object",
    "properties": {
        "intent": {"type": "string", "enum": ["orders", "cancel", "rule", "question", "navigate",
                                              "clarify", "unsupported"]},
        "orders": {"type": "array", "items": ORDER_ITEM},
        "selector": _nullable({
            "type": "object",
            "properties": {
                "scope": {"type": "string", "enum": ["symbols", "sector", "all_positions"]},
                "symbols": {"type": "array", "items": {"type": "string"}},
                "sector": _nullable({"type": "string", "enum": list(SECTOR_ETFS) + ["ETF"]}),
            },
            "required": ["scope", "symbols", "sector"],
            "additionalProperties": False,
        }),
        "cancel": _nullable({
            "type": "object",
            "properties": {"symbols": {"type": "array", "items": {"type": "string"}},
                           "all": {"type": "boolean"}},
            "required": ["symbols", "all"],
            "additionalProperties": False,
        }),
        "symbol": _nullable({"type": "string"}),
        "message": _nullable({"type": "string"}),
    },
    "required": ["intent", "orders", "selector", "cancel", "symbol", "message"],
    "additionalProperties": False,
}

UNIVERSE = ", ".join(f"{s[0]} {s[1]} [{s[3]}]" for s in STOCKS) + ", " + \
    ", ".join(f"{e[0]} {e[1]} [ETF]" for e in ETFS)

SYSTEM = f"""You turn a trader's message into a structured intent for a US-stock paper-trading
app. You never execute anything: the app shows the user a preview and they confirm.

Intents:
- orders: one or more orders. qty_type: shares (amount = share count), dollars (amount = $),
  pct_position (amount = % of the current position, "half" = 50), all_position (sell
  everything; amount null), pct_cash (amount = % of buying power).
  Prices: limit_price/stop_price in dollars, OR limit_offset_pct/stop_offset_pct as a percent
  distance from the current price ("stop loss 8% below" -> order_type stop, side sell,
  stop_offset_pct 8). "at X or better" means a limit order.
  For an action across many holdings ("close all my tech positions", "stop loss under all my
  positions") emit ONE order with symbol "*" and set selector: scope all_positions, sector
  (with the sector name), or symbols.
  "Split $X equally between A and B" -> one dollars order per symbol.
- cancel: cancel open orders (symbols, or all=true).
- rule: anything conditional or in the future ("if", "when", "alert me") - the rules engine
  handles it; just return intent rule.
- question: questions about the portfolio, performance, or why something moved.
- navigate: the user only named a stock ("show me nvidia") -> symbol.
- clarify: ambiguous request (put the question in message), e.g. unclear quantity.
- unsupported: short selling, options, crypto, forex, futures, non-listed tickers (explain in
  message).
Unused fields: empty arrays or null. time_in_force defaults to day.

Tickers (symbol, name, sector): {UNIVERSE}. These are the most popular tickers; any other US-listed stock or ETF ticker is also valid.
Map company names to tickers."""


def parse_llm(text: str, context: str) -> dict:
    return llm.structured(SYSTEM, f"{context}\n\nUser message: {text}", INTENT_SCHEMA,
                          effort="low", max_tokens=3000)
