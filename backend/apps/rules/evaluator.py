"""Deterministic rule evaluation. Runs inside the ingestor on every tick; no LLM involved."""
from __future__ import annotations

import logging
import time as _time
from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.db import IntegrityError, transaction
from django.db.models import Avg
from django.utils import timezone

from apps.market import quotes
from apps.market.hours import ET
from apps.market.models import PriceBar
from apps.news.models import NewsArticle
from apps.realtime.notify import notify_user
from apps.trading.engine import OrderError, OrderRequest, submit_order
from apps.trading.models import Position

from .models import RuleExecution, TradingRule
from .spec import Clause, Condition, RuleSpec, describe_action

log = logging.getLogger(__name__)


# ------------------------------------------------------------------------------------------
# Indicators
# ------------------------------------------------------------------------------------------
def sma(values: list[float], n: int) -> float | None:
    return sum(values[-n:]) / n if len(values) >= n else None


def ema(values: list[float], n: int) -> float | None:
    if len(values) < n:
        return None
    k = 2 / (n + 1)
    e = sum(values[:n]) / n
    for v in values[n:]:
        e = v * k + e * (1 - k)
    return e


def rsi(values: list[float], n: int = 14) -> float | None:
    if len(values) < n + 1:
        return None
    gains = losses = 0.0
    for i in range(1, n + 1):
        d = values[i] - values[i - 1]
        gains += max(d, 0)
        losses += max(-d, 0)
    ag, al = gains / n, losses / n
    for i in range(n + 1, len(values)):
        d = values[i] - values[i - 1]
        ag = (ag * (n - 1) + max(d, 0)) / n
        al = (al * (n - 1) + max(-d, 0)) / n
    if al == 0:
        return 100.0
    return 100 - 100 / (1 + ag / al)


INDICATOR_FN = {"sma": sma, "ema": ema, "rsi": rsi}


class Context:
    """Lazily computes metric values, caching history per symbol for a short time."""

    _history: dict[tuple[str, str], tuple[float, list[float], float]] = {}
    TTL = 30.0

    def __init__(self, rule: TradingRule):
        self.rule = rule
        self._summary = None

    def closes(self, symbol: str, timeframe: str) -> list[float]:
        key = (symbol, timeframe)
        hit = self._history.get(key)
        if hit and _time.monotonic() - hit[0] < self.TTL:
            base = hit[1]
        else:
            qs = PriceBar.objects.filter(stock__symbol=symbol, timeframe=timeframe)
            if timeframe == "1d":
                qs = qs.filter(ts__lt=timezone.now().astimezone(ET).replace(
                    hour=0, minute=0, second=0, microsecond=0))
            base = [float(c) for c in reversed(qs.order_by("-ts").values_list("close", flat=True)
                                               [:300])]
            self._history[key] = (_time.monotonic(), base, 0)
        price = self.price(symbol)
        return base + ([price] if price is not None else [])

    def price(self, symbol: str) -> float | None:
        q = quotes.get_quote(symbol)
        return q["price"] if q else None

    def indicator(self, metric: str, symbol: str, period: int, timeframe: str) -> float | None:
        if metric == "price":
            return self.price(symbol)
        return INDICATOR_FN[metric](self.closes(symbol, timeframe), period)

    def pct_change(self, symbol: str, window: str) -> float | None:
        q = quotes.get_quote(symbol)
        if not q:
            return None
        p = q["price"]
        if window == "since_prev_close":
            ref = q.get("prev_close")
        elif window == "since_open":
            ref = q.get("open")
        elif window == "5d":
            closes = self.closes(symbol, "1d")
            ref = closes[-6] if len(closes) >= 6 else None
        else:
            minutes = int(window[:-1])
            sec = quotes.second_bars(symbol, limit=minutes * 60 + 5)
            if len(sec) >= minutes * 60 * 0.8:
                ref = sec[0]["c"]
            else:
                bar = PriceBar.objects.filter(
                    stock__symbol=symbol, timeframe="1m",
                    ts__lte=timezone.now() - timedelta(minutes=minutes)).order_by("-ts").first()
                ref = float(bar.close) if bar else None
        return (p / ref - 1) * 100 if ref else None

    def summary(self):
        if self._summary is None:
            from apps.portfolio.services import summary

            self._summary = summary(self.rule.account)
        return self._summary

    def value(self, c: Clause) -> float | None:
        m = c.metric
        if m == "price":
            return self.price(c.symbol)
        if m == "pct_change":
            return self.pct_change(c.symbol, c.window)
        if m in INDICATOR_FN:
            return self.indicator(m, c.symbol, c.period, c.timeframe)
        if m == "volume_ratio":
            q = quotes.get_quote(c.symbol) or {}
            avg = PriceBar.objects.filter(stock__symbol=c.symbol, timeframe="1d").order_by(
                "-ts")[:20].aggregate(v=Avg("volume"))["v"]
            return q.get("volume", 0) / avg if avg else None
        if m in ("position_pnl_pct", "position_qty"):
            pos = Position.objects.filter(account=self.rule.account, stock__symbol=c.symbol).first()
            if not pos or pos.quantity <= 0:
                return 0.0 if m == "position_qty" else None
            if m == "position_qty":
                return float(pos.quantity)
            p = self.price(c.symbol)
            return (p / float(pos.avg_cost) - 1) * 100 if p and pos.avg_cost else None
        if m == "cash":
            return float(self.rule.account.cash_balance)
        if m == "portfolio_value":
            return self.summary()["equity"]
        if m == "news_sentiment":
            vals = list(NewsArticle.objects.filter(
                stocks__symbol=c.symbol, published_at__gte=timezone.now() - timedelta(hours=1)
            ).values_list("sentiment", flat=True))
            return sum(vals) / len(vals) if vals else 0.0
        if m == "earnings_released":
            return float(NewsArticle.objects.filter(
                stocks__symbol=c.symbol, kind="earnings",
                published_at__gte=timezone.now() - timedelta(hours=24)).exists())
        return None

    def rhs(self, c: Clause) -> float | None:
        if c.ref:
            return self.indicator(c.ref.metric, c.symbol, c.ref.period or 20, c.ref.timeframe)
        return c.value


def _compare(op: str, a: float, b: float) -> bool:
    return {"<": a < b, "<=": a <= b, ">": a > b, ">=": a >= b}[op]


def eval_clause(c: Clause, ctx: Context, state: dict, key: str, snap: dict) -> bool:
    if c.metric == "time_of_day":
        now = timezone.now().astimezone(ET).strftime("%H:%M")
        snap[key] = now
        return _compare(c.op, now, c.time_value) if not c.op.startswith("crosses") else False
    if c.metric == "earnings_released":
        v = ctx.value(c)
        snap[key] = v
        return bool(v)
    a, b = ctx.value(c), ctx.rhs(c)
    snap[key] = {"value": a, "ref": b}
    if a is None or b is None:
        return False
    if c.op.startswith("crosses"):
        diff = a - b
        prev = state.get(key)
        state[key] = diff
        if prev is None:
            return False
        return prev <= 0 < diff if c.op == "crosses_above" else prev >= 0 > diff
    return _compare(c.op, a, b)


def eval_condition(cond: Condition, ctx: Context, state: dict, prefix: str, snap: dict) -> bool:
    results = []
    for i, item in enumerate(cond.clauses):
        key = f"{prefix}.{i}"
        if isinstance(item, Condition):
            results.append(eval_condition(item, ctx, state, key, snap))
        else:
            results.append(eval_clause(item, ctx, state, key, snap))
    if cond.logic == "all":
        return all(results)
    if cond.logic == "any":
        return any(results)
    return not any(results)


def evaluate(rule: TradingRule) -> tuple[bool, dict]:
    spec = RuleSpec.model_validate(rule.spec)
    snap: dict = {}
    state = dict(rule.state or {})
    ok = eval_condition(spec.condition, Context(rule), state, "c", snap)
    if state != (rule.state or {}):
        rule.state = state
        TradingRule.objects.filter(pk=rule.pk).update(state=state)
    return ok, snap


# ------------------------------------------------------------------------------------------
# Execution
# ------------------------------------------------------------------------------------------
def _order_request(spec: RuleSpec, rule: TradingRule) -> OrderRequest | None:
    a = spec.action
    if a.type == "notify":
        return None
    limit = Decimal(str(a.limit_price)) if a.limit_price else None
    base = dict(symbol=a.symbol, type=a.order_type, limit_price=limit, source="rule",
                time_in_force="day")
    if a.type == "buy_qty":
        return OrderRequest(side="buy", quantity=Decimal(str(a.quantity)), **base)
    if a.type == "buy_notional":
        return OrderRequest(side="buy", notional=Decimal(str(a.amount)), **base)
    if a.type == "sell_qty":
        return OrderRequest(side="sell", quantity=Decimal(str(a.quantity)), **base)
    pos = Position.objects.filter(account=rule.account, stock__symbol=a.symbol).first()
    available = (pos.quantity - pos.reserved_qty) if pos else Decimal(0)
    qty = available if a.type == "close_position" else \
        (available * Decimal(str(a.pct)) / 100).to_integral_value(rounding="ROUND_DOWN")
    if qty <= 0:
        raise OrderError(f"No {a.symbol} shares available to sell.")
    return OrderRequest(side="sell", quantity=qty, **base)


def execute(rule: TradingRule, snap: dict) -> RuleExecution | None:
    spec = RuleSpec.model_validate(rule.spec)
    now = timezone.now()
    window_key = now.strftime("%Y%m%dT%H%M%S") if spec.mode == "repeat" else "once"
    order, success = None, True
    try:
        with transaction.atomic():
            ex = RuleExecution.objects.create(rule=rule, triggered_at=now, window_key=window_key,
                                              snapshot=snap, result="pending")
    except IntegrityError:
        return None  # already fired for this window (idempotent)
    try:
        req = _order_request(spec, rule)
        if req:
            price = quotes.last_price(req.symbol) or Decimal(0)
            est = (req.quantity * price) if req.quantity else (req.notional or 0)
            if est > settings.MAX_RULE_ORDER_VALUE:
                raise OrderError(f"Order value ${est:,.0f} exceeds the per-rule limit of "
                                 f"${settings.MAX_RULE_ORDER_VALUE:,.0f}.")
            req.client_order_id = f"rule-{rule.pk}-{window_key}"
            order = submit_order(rule.account, req)
            result = f"{describe_action(spec.action)} → order {order.status}"
            if order.status == "rejected":
                success = False
        else:
            result = spec.action.message or f"Rule “{rule.name}” triggered"
    except OrderError as e:
        result, success = f"Order failed: {e}", False
    ex.order, ex.result, ex.success = order, result[:300], success
    ex.save()
    rule.last_triggered_at = now
    rule.trigger_count += 1
    if not success:
        rule.status, rule.status_message = "error", result[:300]
    elif spec.mode == "once":
        rule.status, rule.status_message = "triggered", result[:300]
    rule.save(update_fields=["last_triggered_at", "trigger_count", "status", "status_message"])
    from .serializers import serialize_rule

    notify_user(rule.user_id, "rule_triggered", {
        "rule": serialize_rule(rule), "message": result, "success": success,
    })
    return ex


_active_cache: tuple[float, list] = (0.0, [])


def run_all(now=None) -> int:
    """Evaluate every active rule once. Edge-triggered: fires on false -> true."""
    global _active_cache
    if _time.monotonic() - _active_cache[0] > 3:
        rules = list(TradingRule.objects.filter(status="active", user__rules_paused=False)
                     .select_related("account"))
        _active_cache = (_time.monotonic(), rules)
    fired = 0
    now = now or timezone.now()
    for rule in _active_cache[1]:
        try:
            rule.refresh_from_db(fields=["status", "last_condition", "state", "last_triggered_at"])
            if rule.status != "active":
                continue
            if rule.expires_at and rule.expires_at < now:
                TradingRule.objects.filter(pk=rule.pk).update(status="expired")
                continue
            ok, snap = evaluate(rule)
            spec = RuleSpec.model_validate(rule.spec)
            cooling = (spec.mode == "repeat" and rule.last_triggered_at and
                       (now - rule.last_triggered_at).total_seconds() < spec.cooldown_seconds)
            if ok and not rule.last_condition and not cooling:
                execute(rule, snap)
                fired += 1
            if ok != rule.last_condition:
                TradingRule.objects.filter(pk=rule.pk).update(last_condition=ok)
            TradingRule.objects.filter(pk=rule.pk).update(last_evaluated_at=now)
        except Exception as e:
            log.exception("rule %s failed", rule.pk)
            TradingRule.objects.filter(pk=rule.pk).update(status="error",
                                                          status_message=str(e)[:300])
    return fired


# ------------------------------------------------------------------------------------------
# Backtest ("would have triggered")
# ------------------------------------------------------------------------------------------
BACKTESTABLE = {"price", "pct_change", "rsi", "sma", "ema", "volume_ratio", "time_of_day"}


def backtest(spec: RuleSpec, days: int = 252) -> dict:
    clauses = list(spec.condition.all_clauses())
    unsupported = sorted({c.metric for c in clauses if c.metric not in BACKTESTABLE})
    symbols = sorted({c.symbol for c in clauses if c.symbol})
    series: dict[str, list] = {}
    for s in symbols:
        rows = list(PriceBar.objects.filter(stock__symbol=s, timeframe="1d").order_by("-ts")
                    .values_list("ts", "close", "volume")[: days + 260])
        series[s] = list(reversed(rows))
    if not symbols or any(not v for v in series.values()):
        return {"supported": False, "note": "Not enough history to backtest.", "triggers": []}
    n = min(len(v) for v in series.values())
    start = max(1, n - days)

    def val(c: Clause, i: int, s: str):
        rows = series[s][len(series[s]) - n:]
        closes = [float(r[1]) for r in rows[: i + 1]]
        if c.metric == "price":
            return closes[-1]
        if c.metric == "pct_change":
            back = 5 if c.window == "5d" else 1
            return (closes[-1] / closes[-1 - back] - 1) * 100 if len(closes) > back else None
        if c.metric in INDICATOR_FN:
            return INDICATOR_FN[c.metric](closes, c.period)
        if c.metric == "volume_ratio":
            vols = [r[2] for r in rows[max(0, i - 20): i]]
            return rows[i][2] / (sum(vols) / len(vols)) if vols else None
        return None

    def ref(c: Clause, i: int):
        if not c.ref:
            return c.value
        rows = series[c.symbol][len(series[c.symbol]) - n:]
        closes = [float(r[1]) for r in rows[: i + 1]]
        if c.ref.metric == "price":
            return closes[-1]
        return INDICATOR_FN[c.ref.metric](closes, c.ref.period or 20)

    def check(cond: Condition, i: int) -> bool:
        res = []
        for c in cond.clauses:
            if isinstance(c, Condition):
                res.append(check(c, i))
            elif c.metric not in BACKTESTABLE or c.metric == "time_of_day":
                res.append(True)
            else:
                a, b = val(c, i, c.symbol), ref(c, i)
                if a is None or b is None:
                    res.append(False)
                elif c.op.startswith("crosses"):
                    pa, pb = val(c, i - 1, c.symbol), ref(c, i - 1)
                    if pa is None or pb is None:
                        res.append(False)
                    else:
                        res.append(pa - pb <= 0 < a - b if c.op == "crosses_above"
                                   else pa - pb >= 0 > a - b)
                else:
                    res.append(_compare(c.op, a, b))
        return all(res) if cond.logic == "all" else any(res) if cond.logic == "any" \
            else not any(res)

    triggers, prev = [], False
    act_sym = spec.action.symbol or symbols[0]
    act_rows = series.get(act_sym) or series[symbols[0]]
    act_rows = act_rows[len(act_rows) - n:]
    for i in range(start, n):
        ok = check(spec.condition, i)
        if ok and not prev:
            triggers.append({"date": act_rows[i][0].date().isoformat(),
                             "price": float(act_rows[i][1])})
        prev = ok
    last = float(act_rows[-1][1])
    for t in triggers:
        t["return_since_pct"] = (last / t["price"] - 1) * 100
    series_out = [{"date": r[0].date().isoformat(), "close": float(r[1])}
                  for r in act_rows[start:]]
    note = None
    if unsupported:
        note = f"Ignored in backtest (live-only): {', '.join(unsupported)}."
    return {"supported": True, "triggers": triggers, "note": note, "symbol": act_sym,
            "series": series_out, "days": n - start}
