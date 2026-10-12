import math
from decimal import Decimal

from apps.market import quotes
from apps.market.hours import et_today
from apps.market.models import PriceBar, Stock
from apps.trading.models import Position, Trade, TradingAccount

from .models import PortfolioSnapshot


def positions(account: TradingAccount) -> list[dict]:
    rows = list(Position.objects.filter(account=account, quantity__gt=0).select_related("stock"))
    qs = quotes.get_quotes([p.stock.symbol for p in rows])
    out = []
    for p in rows:
        q = qs.get(p.stock.symbol) or {}
        price = Decimal(str(q.get("price", p.avg_cost)))
        prev = Decimal(str(q.get("prev_close", price)))
        value = p.quantity * price
        cost = p.quantity * p.avg_cost
        out.append({
            "symbol": p.stock.symbol, "name": p.stock.name, "sector": p.stock.sector or "ETF",
            "quantity": float(p.quantity), "available": float(p.quantity - p.reserved_qty),
            "avg_cost": float(p.avg_cost), "price": float(price),
            "market_value": float(value), "cost_basis": float(cost),
            "unrealized_pnl": float(value - cost),
            "unrealized_pct": float((price / p.avg_cost - 1) * 100) if p.avg_cost else 0.0,
            "day_pnl": float(p.quantity * (price - prev)),
            "day_pct": float((price / prev - 1) * 100) if prev else 0.0,
            "realized_pnl": float(p.realized_pnl),
            "opened_at": p.opened_at,
        })
    total = sum(r["market_value"] for r in out) or 1
    for r in out:
        r["weight"] = r["market_value"] / total * 100
    return sorted(out, key=lambda r: -r["market_value"])


def summary(account: TradingAccount) -> dict:
    pos = positions(account)
    mv = sum(p["market_value"] for p in pos)
    cash = float(account.cash_balance)
    equity = cash + mv
    day_pnl = sum(p["day_pnl"] for p in pos)
    start = float(account.starting_cash)
    realized = float(sum((p.realized_pnl for p in account.positions.all()), Decimal(0)))
    return {
        "equity": equity, "cash": cash, "buying_power": float(account.buying_power),
        "reserved_cash": float(account.reserved_cash), "positions_value": mv,
        "day_pnl": day_pnl, "day_pct": day_pnl / (equity - day_pnl) * 100 if equity else 0,
        "total_pnl": equity - start, "total_pct": (equity / start - 1) * 100 if start else 0,
        "unrealized_pnl": sum(p["unrealized_pnl"] for p in pos), "realized_pnl": realized,
        "starting_cash": start, "positions_count": len(pos),
    }


def take_snapshot(account: TradingAccount, date=None) -> PortfolioSnapshot:
    s = summary(account)
    snap, _ = PortfolioSnapshot.objects.update_or_create(
        account=account, date=date or et_today(),
        defaults={"cash": s["cash"], "positions_value": s["positions_value"],
                  "total_equity": s["equity"]},
    )
    return snap


def history(account: TradingAccount, days: int = 365) -> list[dict]:
    snaps = list(PortfolioSnapshot.objects.filter(account=account).order_by("-date")[:days])
    rows = [{"date": s.date.isoformat(), "equity": float(s.total_equity)} for s in reversed(snaps)]
    today = et_today().isoformat()
    live = {"date": today, "equity": summary(account)["equity"]}
    if rows and rows[-1]["date"] == today:
        rows[-1] = live
    else:
        if not rows:
            rows.append({"date": account.created_at.date().isoformat(),
                         "equity": float(account.starting_cash)})
        rows.append(live)
    # benchmark: SPY scaled to the starting equity
    spy = Stock.objects.filter(symbol="SPY").first()
    if spy and rows:
        closes = {b.ts.date().isoformat(): float(b.close) for b in PriceBar.objects.filter(
            stock=spy, timeframe="1d", ts__date__gte=rows[0]["date"])}
        base = closes.get(rows[0]["date"])
        last = base
        for r in rows:
            c = closes.get(r["date"]) or last
            if r["date"] == today:
                c = (quotes.get_quote("SPY") or {}).get("price", c)
            last = c
            r["benchmark"] = rows[0]["equity"] * c / base if base and c else None
    return rows


def analytics(account: TradingAccount) -> dict:
    hist = history(account)
    eq = [h["equity"] for h in hist]
    rets = [eq[i] / eq[i - 1] - 1 for i in range(1, len(eq)) if eq[i - 1]]
    peak, mdd = (eq[0] if eq else 0), 0.0
    for v in eq:
        peak = max(peak, v)
        if peak:
            mdd = min(mdd, v / peak - 1)
    mean = sum(rets) / len(rets) if rets else 0
    sd = math.sqrt(sum((r - mean) ** 2 for r in rets) / (len(rets) - 1)) if len(rets) > 1 else 0
    sharpe = (mean / sd) * math.sqrt(252) if sd else None
    trades = list(Trade.objects.filter(account=account, side="sell", realized_pnl__isnull=False))
    wins = [t for t in trades if t.realized_pnl > 0]
    pos = positions(account)
    sectors: dict[str, float] = {}
    for p in pos:
        sectors[p["sector"]] = sectors.get(p["sector"], 0) + p["market_value"]
    bench = [h.get("benchmark") for h in hist if h.get("benchmark")]
    return {
        "total_return_pct": (eq[-1] / eq[0] - 1) * 100 if len(eq) > 1 and eq[0] else 0,
        "benchmark_return_pct": (bench[-1] / bench[0] - 1) * 100 if len(bench) > 1 else None,
        "volatility_pct": sd * math.sqrt(252) * 100,
        "sharpe": sharpe,
        "max_drawdown_pct": mdd * 100,
        "win_rate_pct": len(wins) / len(trades) * 100 if trades else None,
        "closed_trades": len(trades),
        "best_trade": max((float(t.realized_pnl) for t in trades), default=None),
        "worst_trade": min((float(t.realized_pnl) for t in trades), default=None),
        "sector_allocation": [{"sector": k, "value": v}
                              for k, v in sorted(sectors.items(), key=lambda kv: -kv[1])],
        "top_weight_pct": max((p["weight"] for p in pos), default=0),
    }
