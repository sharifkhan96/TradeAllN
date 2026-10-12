"""Trading performance analytics: win rate, profit factor, expectancy, streaks, holding times,
P&L breakdowns, return distribution, and risk ratios vs. the S&P 500.

A "closed trade" is one sell fill. Its P&L is the realized P&L the engine booked (average-cost
basis, like most brokers). Holding time is matched FIFO against earlier buys.
"""
from __future__ import annotations

import math
from collections import defaultdict, deque
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from apps.market.hours import ET
from apps.market.models import PriceBar
from apps.trading.models import Order, Trade, TradingAccount

from .services import history, positions

PERIODS = {"30d": 30, "90d": 90, "1y": 365}


def _period_start(period: str) -> datetime | None:
    now = datetime.now(UTC)
    if period == "ytd":
        return datetime(now.year, 1, 1, tzinfo=ET)
    if period in PERIODS:
        return now - timedelta(days=PERIODS[period])
    return None


def closed_trades(account: TradingAccount) -> list[dict]:
    """Every sell fill with its P&L, return %, and FIFO holding period."""
    lots: dict[int, deque] = defaultdict(deque)  # stock_id -> [qty, price, time]
    out = []
    for t in Trade.objects.filter(account=account).select_related("stock").order_by("executed_at", "id"):
        q = Decimal(t.quantity)
        if t.side == "buy":
            lots[t.stock_id].append([q, Decimal(t.price), t.executed_at])
            continue
        remaining, weighted_days, opened = q, 0.0, None
        while remaining > 0 and lots[t.stock_id]:
            lot = lots[t.stock_id][0]
            take = min(lot[0], remaining)
            weighted_days += float(take) * (t.executed_at - lot[2]).total_seconds() / 86400
            opened = opened or lot[2]
            lot[0] -= take
            remaining -= take
            if lot[0] <= 0:
                lots[t.stock_id].popleft()
        pnl = float(t.realized_pnl or 0)
        proceeds = float(t.price * q)
        cost = proceeds - pnl
        out.append({
            "symbol": t.stock.symbol, "name": t.stock.name, "sector": t.stock.sector or "ETF",
            "opened_at": opened.isoformat() if opened else None,
            "closed_at": t.executed_at.isoformat(), "quantity": float(q),
            "entry": cost / float(q) if q else None, "exit": float(t.price),
            "pnl": pnl, "return_pct": pnl / cost * 100 if cost > 0 else 0.0,
            "held_days": weighted_days / float(q) if q else 0.0,
            "commission": float(t.commission),
        })
    return out


def _streaks(results: list[bool]) -> dict:
    best_w = best_l = cur = 0
    cur_kind = None
    for won in results:
        if won == cur_kind:
            cur += 1
        else:
            cur_kind, cur = won, 1
        if won:
            best_w = max(best_w, cur)
        else:
            best_l = max(best_l, cur)
    return {"max_win_streak": best_w, "max_loss_streak": best_l,
            "current": {"kind": "win" if cur_kind else "loss" if cur_kind is False else None,
                        "length": cur}}


def _histogram(values: list[float]) -> list[dict]:
    edges = [-math.inf, -20, -10, -5, -2, 0, 2, 5, 10, 20, math.inf]
    labels = ["< -20%", "-20 to -10%", "-10 to -5%", "-5 to -2%", "-2 to 0%", "0 to 2%",
              "2 to 5%", "5 to 10%", "10 to 20%", "> 20%"]
    counts = [0] * len(labels)
    for v in values:
        for i in range(len(labels)):
            if edges[i] <= v < edges[i + 1]:
                counts[i] += 1
                break
    return [{"bucket": lab, "count": c, "positive": i >= 5} for i, (lab, c) in enumerate(zip(labels, counts, strict=True))]


def _risk(account: TradingAccount) -> dict:
    hist = history(account, days=400)
    eq = [h["equity"] for h in hist]
    dates = [h["date"] for h in hist]
    rets = [eq[i] / eq[i - 1] - 1 for i in range(1, len(eq)) if eq[i - 1]]
    out: dict = {"days": len(rets)}
    if len(rets) < 5:
        return out
    mean = sum(rets) / len(rets)
    downside = [r for r in rets if r < 0]
    dd = math.sqrt(sum(r * r for r in downside) / len(rets)) if downside else 0
    out["sortino"] = mean / dd * math.sqrt(252) if dd else None
    best = max(range(len(rets)), key=lambda i: rets[i])
    worst = min(range(len(rets)), key=lambda i: rets[i])
    out["best_day"] = {"date": dates[best + 1], "pct": rets[best] * 100}
    out["worst_day"] = {"date": dates[worst + 1], "pct": rets[worst] * 100}
    out["positive_days_pct"] = sum(r > 0 for r in rets) / len(rets) * 100
    # beta / alpha vs the S&P 500 (SPY), daily
    spy = {b.ts.astimezone(ET).date().isoformat(): float(b.close)
           for b in PriceBar.objects.filter(stock__symbol="SPY", timeframe="1d", ts__date__gte=dates[0])}
    pairs = []
    for i in range(1, len(dates)):
        a, b = spy.get(dates[i - 1]), spy.get(dates[i])
        if a and b and eq[i - 1]:
            pairs.append((eq[i] / eq[i - 1] - 1, b / a - 1))
    if len(pairs) >= 10:
        mp = sum(p for p, _ in pairs) / len(pairs)
        mm = sum(m for _, m in pairs) / len(pairs)
        cov = sum((p - mp) * (m - mm) for p, m in pairs) / (len(pairs) - 1)
        var = sum((m - mm) ** 2 for _, m in pairs) / (len(pairs) - 1)
        if var:
            beta = cov / var
            out["beta"] = beta
            out["alpha_annual_pct"] = (mp - beta * mm) * 252 * 100
            corr_den = math.sqrt(var * sum((p - mp) ** 2 for p, _ in pairs) / (len(pairs) - 1))
            out["correlation"] = cov / corr_den if corr_den else None
    peak, mdd = eq[0], 0.0
    for v in eq:
        peak = max(peak, v)
        mdd = min(mdd, v / peak - 1) if peak else mdd
    years = len(rets) / 252
    cagr = (eq[-1] / eq[0]) ** (1 / years) - 1 if years > 0 and eq[0] > 0 else None
    out["cagr_pct"] = cagr * 100 if cagr is not None else None
    out["calmar"] = cagr / abs(mdd) if cagr is not None and mdd else None
    return out


def performance(account: TradingAccount, period: str = "all") -> dict:
    start = _period_start(period)
    trades = closed_trades(account)
    if start:
        trades = [t for t in trades if datetime.fromisoformat(t["closed_at"]) >= start]
    wins = [t for t in trades if t["pnl"] > 0.005]
    losses = [t for t in trades if t["pnl"] < -0.005]
    gross_win = sum(t["pnl"] for t in wins)
    gross_loss = -sum(t["pnl"] for t in losses)
    n = len(trades)
    avg_win = gross_win / len(wins) if wins else None
    avg_loss = -gross_loss / len(losses) if losses else None
    win_rate = len(wins) / n * 100 if n else None

    by_symbol: dict[str, dict] = {}
    for t in trades:
        s = by_symbol.setdefault(t["symbol"], {"symbol": t["symbol"], "name": t["name"], "pnl": 0.0,
                                               "trades": 0, "wins": 0})
        s["pnl"] += t["pnl"]
        s["trades"] += 1
        s["wins"] += t["pnl"] > 0
    by_sector: dict[str, float] = defaultdict(float)
    for t in trades:
        by_sector[t["sector"]] += t["pnl"]
    monthly: dict[str, dict] = {}
    for t in trades:
        m = t["closed_at"][:7]
        row = monthly.setdefault(m, {"month": m, "pnl": 0.0, "trades": 0, "wins": 0})
        row["pnl"] += t["pnl"]
        row["trades"] += 1
        row["wins"] += t["pnl"] > 0
    cum, curve = 0.0, []
    for t in trades:
        cum += t["pnl"]
        curve.append({"date": t["closed_at"][:10], "pnl": round(cum, 2)})

    orders = Order.objects.filter(account=account)
    if start:
        orders = orders.filter(created_at__gte=start)
    open_pos = positions(account)
    return {
        "period": period,
        "summary": {
            "closed_trades": n, "wins": len(wins), "losses": len(losses),
            "breakeven": n - len(wins) - len(losses), "win_rate_pct": win_rate,
            "net_pnl": gross_win - gross_loss, "gross_profit": gross_win, "gross_loss": gross_loss,
            "profit_factor": gross_win / gross_loss if gross_loss else None,
            "avg_win": avg_win, "avg_loss": avg_loss,
            "payoff_ratio": avg_win / abs(avg_loss) if avg_win and avg_loss else None,
            "expectancy": (gross_win - gross_loss) / n if n else None,
            "avg_return_pct": sum(t["return_pct"] for t in trades) / n if n else None,
            "largest_win": max(trades, key=lambda t: t["pnl"]) if wins else None,
            "largest_loss": min(trades, key=lambda t: t["pnl"]) if losses else None,
            "avg_hold_days_win": sum(t["held_days"] for t in wins) / len(wins) if wins else None,
            "avg_hold_days_loss": sum(t["held_days"] for t in losses) / len(losses) if losses else None,
            "fees": sum(t["commission"] for t in trades),
            **_streaks([t["pnl"] > 0 for t in trades if abs(t["pnl"]) > 0.005]),
        },
        "activity": {
            "orders": orders.count(),
            "filled": orders.filter(status="filled").count(),
            "cancelled": orders.filter(status__in=["cancelled", "expired"]).count(),
            "rejected": orders.filter(status="rejected").count(),
            "by_source": {s: orders.filter(source=s).count() for s, _ in Order.SOURCES},
            "buy_volume": float(sum(t.price * t.quantity for t in
                                    Trade.objects.filter(account=account, side="buy",
                                                         **({"executed_at__gte": start} if start else {})))),
        },
        "open_positions": {
            "count": len(open_pos),
            "winners": sum(p["unrealized_pnl"] > 0 for p in open_pos),
            "losers": sum(p["unrealized_pnl"] < 0 for p in open_pos),
            "unrealized_pnl": sum(p["unrealized_pnl"] for p in open_pos),
            "best": max(open_pos, key=lambda p: p["unrealized_pct"], default=None),
            "worst": min(open_pos, key=lambda p: p["unrealized_pct"], default=None),
        },
        "by_symbol": sorted(by_symbol.values(), key=lambda s: -abs(s["pnl"]))[:12],
        "by_sector": [{"sector": k, "pnl": v} for k, v in sorted(by_sector.items(), key=lambda kv: -kv[1])],
        "monthly": sorted(monthly.values(), key=lambda r: r["month"]),
        "distribution": _histogram([t["return_pct"] for t in trades]),
        "cumulative": curve,
        "recent": list(reversed(trades))[:25],
        "risk": _risk(account),
    }

