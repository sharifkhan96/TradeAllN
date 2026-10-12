"""The rule AST: a small, safe, JSON language. No code, only whitelisted metrics and actions."""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

Metric = Literal[
    "price", "pct_change", "rsi", "sma", "ema", "volume_ratio", "position_pnl_pct",
    "position_qty", "cash", "portfolio_value", "time_of_day", "news_sentiment",
    "earnings_released",
]
Op = Literal["<", "<=", ">", ">=", "crosses_above", "crosses_below"]
Window = Literal["since_prev_close", "since_open", "5m", "15m", "60m", "5d"]
SYMBOL_METRICS = {"price", "pct_change", "rsi", "sma", "ema", "volume_ratio",
                  "position_pnl_pct", "position_qty", "news_sentiment", "earnings_released"}
INDICATORS = {"rsi", "sma", "ema"}


class RefMetric(BaseModel):
    """Right-hand side that is itself an indicator, e.g. price crosses_above sma(50)."""
    metric: Literal["sma", "ema", "price"]
    period: int | None = Field(default=None, ge=2, le=250)
    timeframe: Literal["1m", "1d"] = "1d"


class Clause(BaseModel):
    metric: Metric
    symbol: str | None = None
    op: Op
    value: float | None = None
    time_value: str | None = None  # HH:MM for time_of_day
    ref: RefMetric | None = None
    period: int | None = Field(default=None, ge=2, le=250)
    timeframe: Literal["1m", "1d"] = "1d"
    window: Window = "since_prev_close"

    @field_validator("symbol")
    @classmethod
    def upper(cls, v):
        return v.upper().strip() if v else v

    @model_validator(mode="after")
    def check(self):
        if self.metric in SYMBOL_METRICS and not self.symbol:
            raise ValueError(f"{self.metric} needs a symbol")
        if self.metric in INDICATORS and not self.period:
            self.period = 14 if self.metric == "rsi" else 20
        if self.metric == "time_of_day":
            if not self.time_value or len(self.time_value) != 5 or self.time_value[2] != ":":
                raise ValueError("time_of_day needs time_value like 15:00")
        elif self.value is None and self.ref is None:
            raise ValueError("a value or a reference metric is required")
        if self.op.startswith("crosses") and self.metric == "time_of_day":
            raise ValueError("time can't cross")
        return self


class Condition(BaseModel):
    logic: Literal["all", "any", "not"] = "all"
    clauses: list[Clause | Condition] = Field(min_length=1, max_length=8)

    def depth(self) -> int:
        return 1 + max((c.depth() for c in self.clauses if isinstance(c, Condition)), default=0)

    def all_clauses(self):
        for c in self.clauses:
            if isinstance(c, Condition):
                yield from c.all_clauses()
            else:
                yield c


Condition.model_rebuild()


class Action(BaseModel):
    type: Literal["buy_qty", "buy_notional", "sell_qty", "sell_pct", "close_position", "notify"]
    symbol: str | None = None
    quantity: float | None = Field(default=None, gt=0)
    amount: float | None = Field(default=None, gt=0)
    pct: float | None = Field(default=None, gt=0, le=100)
    order_type: Literal["market", "limit"] = "market"
    limit_price: float | None = Field(default=None, gt=0)
    message: str | None = Field(default=None, max_length=200)

    @field_validator("symbol")
    @classmethod
    def upper(cls, v):
        return v.upper().strip() if v else v

    @model_validator(mode="after")
    def check(self):
        if self.type != "notify" and not self.symbol:
            raise ValueError("trading actions need a symbol")
        need = {"buy_qty": "quantity", "sell_qty": "quantity", "buy_notional": "amount",
                "sell_pct": "pct"}.get(self.type)
        if need and getattr(self, need) is None:
            raise ValueError(f"{self.type} needs {need}")
        if self.order_type == "limit" and not self.limit_price:
            raise ValueError("limit orders need limit_price")
        return self


class RuleSpec(BaseModel):
    name: str = Field(max_length=80)
    condition: Condition
    action: Action
    mode: Literal["once", "repeat"] = "once"
    cooldown_seconds: int = Field(default=3600, ge=60, le=7 * 86400)
    expires_at: datetime | None = None

    @model_validator(mode="after")
    def check(self):
        if self.condition.depth() > 4:
            raise ValueError("conditions can nest at most 4 levels")
        return self

    def symbols(self) -> set[str]:
        out = {c.symbol for c in self.condition.all_clauses() if c.symbol}
        if self.action.symbol:
            out.add(self.action.symbol)
        return out


# ---------------------------------------------------------------------------------------
# Human-readable rendering (shown back to the user before activation)
# ---------------------------------------------------------------------------------------
OP_WORDS = {"<": "<", "<=": "≤", ">": ">", ">=": "≥", "crosses_above": "crosses above",
            "crosses_below": "crosses below"}
WINDOW_WORDS = {"since_prev_close": "since previous close", "since_open": "since today's open",
                "5m": "over 5 min", "15m": "over 15 min", "60m": "over 1 hour", "5d": "over 5 days"}


def describe_clause(c: Clause) -> str:
    op = OP_WORDS[c.op]
    if c.ref:
        rhs = f"{c.ref.metric.upper()}({c.ref.period})" if c.ref.period else c.ref.metric
        rhs += "" if c.ref.timeframe == "1d" else f" on {c.ref.timeframe} bars"
    else:
        rhs = ""
    val = c.value
    m = c.metric
    tf = " daily" if c.timeframe == "1d" else " 1-min"
    if m == "price":
        return f"{c.symbol} price {op} {rhs or f'${val:,.2f}'}"
    if m == "pct_change":
        return f"{c.symbol} change {WINDOW_WORDS[c.window]} {op} {val:+g}%"
    if m in INDICATORS:
        return f"{c.symbol} {m.upper()}({c.period},{tf.strip()}) {op} {rhs or f'{val:g}'}"
    if m == "volume_ratio":
        return f"{c.symbol} volume {op} {val:g}× its 20-day average"
    if m == "position_pnl_pct":
        return f"your {c.symbol} position P&L {op} {val:+g}%"
    if m == "position_qty":
        return f"your {c.symbol} shares {op} {val:g}"
    if m == "cash":
        return f"cash {op} ${val:,.0f}"
    if m == "portfolio_value":
        return f"portfolio value {op} ${val:,.0f}"
    if m == "time_of_day":
        return f"time {op} {c.time_value} ET"
    if m == "news_sentiment":
        return f"{c.symbol} news sentiment (last hour) {op} {val:+g}"
    if m == "earnings_released":
        return f"{c.symbol} has reported earnings in the last 24h"
    return m


def describe_condition(cond: Condition) -> dict:
    return {
        "logic": cond.logic,
        "items": [describe_condition(c) if isinstance(c, Condition) else describe_clause(c)
                  for c in cond.clauses],
    }


def describe_action(a: Action) -> str:
    how = f" at limit ${a.limit_price:,.2f}" if a.order_type == "limit" else " at market"
    return {
        "buy_qty": lambda: f"Buy {a.quantity:g} {a.symbol}{how}",
        "buy_notional": lambda: f"Buy ${a.amount:,.0f} of {a.symbol}{how}",
        "sell_qty": lambda: f"Sell {a.quantity:g} {a.symbol}{how}",
        "sell_pct": lambda: f"Sell {a.pct:g}% of your {a.symbol} position{how}",
        "close_position": lambda: f"Sell your entire {a.symbol} position{how}",
        "notify": lambda: "Notify me" + (f": “{a.message}”" if a.message else ""),
    }[a.type]()


def describe(spec: RuleSpec) -> dict:
    return {"when": describe_condition(spec.condition), "then": describe_action(spec.action),
            "mode": "once" if spec.mode == "once" else
            f"every time (cooldown {spec.cooldown_seconds // 60} min)"}
