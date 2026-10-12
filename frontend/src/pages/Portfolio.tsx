import { useQuery, useQueryClient } from "@tanstack/react-query";
import { CalendarClock, Coins, Trash2 } from "lucide-react";
import { toast } from "sonner";
import { StockLogo } from "@/components/Live";
import { Cell, Pie, PieChart, ResponsiveContainer, Tooltip } from "recharts";
import { PerformanceSection } from "@/components/portfolio/Performance";
import { Holdings } from "@/pages/Dashboard";
import { Badge, Button, Card, CardHeader, Empty, Stat, Switch } from "@/components/ui";
import { api } from "@/lib/api";
import { cn } from "@/lib/cn";
import { etTime, money, pct, qty, shortDate, tone } from "@/lib/format";
import { useAnalytics, useDividends, useRecurring, useSummary } from "@/lib/queries";

const COLORS = ["rgb(var(--accent))", "rgb(var(--ai))", "rgb(var(--up))", "rgb(var(--warn))", "#ec4899", "#14b8a6", "#f97316", "#a3e635", "rgb(var(--faint))"];

type Trade = { id: number; symbol: string; side: string; quantity: string; price: string; realized_pnl: string | null; executed_at: string };

export function PortfolioPage() {
  const { data: s } = useSummary();
  const { data: a } = useAnalytics();
  const { data: trades } = useQuery({ queryKey: ["portfolio", "trades"], queryFn: () => api<Trade[]>("/trades") });
  const total = (a?.sector_allocation ?? []).reduce((x, y) => x + y.value, 0) || 1;

  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-xl font-semibold tracking-tight">Portfolio</h1>
        <p className="text-sm text-muted">Performance, risk and allocation of your paper account.</p>
      </div>
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        {[
          { l: "Total equity", v: money(s?.equity), sub: <span className={tone(s?.total_pct)}>{pct(s?.total_pct)} all time</span> },
          { l: "Cash", v: money(s?.cash), sub: <span className="text-muted">{money(s?.reserved_cash)} reserved for orders</span> },
          { l: "Return vs S&P 500", v: <span className={tone(a?.total_return_pct)}>{pct(a?.total_return_pct)}</span>, sub: <span className="text-muted">S&P {pct(a?.benchmark_return_pct)}</span> },
          { l: "Realized P&L", v: <span className={tone(s?.realized_pnl)}>{money(s?.realized_pnl, { sign: true })}</span>, sub: <span className="text-muted">{a?.closed_trades ?? 0} closed trades</span> },
        ].map((x) => (
          <Card key={x.l} className="p-4">
            <Stat label={x.l} value={x.v} sub={x.sub} className="[&>div:nth-child(2)]:text-xl" />
          </Card>
        ))}
      </div>

      <PerformanceSection />

      <div className="grid gap-5 lg:grid-cols-[1fr_1.4fr]">
        <Card>
          <CardHeader title="Allocation by sector" />
          <div className="flex items-center gap-4 p-5">
            <div className="h-44 w-44 shrink-0">
              <ResponsiveContainer>
                <PieChart>
                  <Pie data={a?.sector_allocation ?? []} dataKey="value" nameKey="sector" innerRadius={52} outerRadius={80} paddingAngle={2} stroke="none">
                    {(a?.sector_allocation ?? []).map((_, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
                  </Pie>
                  <Tooltip
                    contentStyle={{ background: "rgb(var(--panel))", border: "1px solid rgb(var(--line))", borderRadius: 8, fontSize: 12 }}
                    formatter={(v: number) => [money(v), "Value"]}
                  />
                </PieChart>
              </ResponsiveContainer>
            </div>
            <div className="min-w-0 flex-1 space-y-2">
              {(a?.sector_allocation ?? []).map((x, i) => (
                <div key={x.sector} className="flex items-center gap-2 text-sm">
                  <span className="h-2.5 w-2.5 rounded-sm" style={{ background: COLORS[i % COLORS.length] }} />
                  <span className="flex-1 truncate">{x.sector}</span>
                  <span className="num text-muted">{((x.value / total) * 100).toFixed(1)}%</span>
                </div>
              ))}
              {!a?.sector_allocation.length && <p className="text-sm text-muted">No positions.</p>}
            </div>
          </div>
        </Card>
        <Card>
          <CardHeader title="Risk & performance" subtitle="From your daily equity history" />
          <div className="grid grid-cols-2 gap-5 p-5 sm:grid-cols-3">
            <Stat label="Volatility (ann.)" value={pct(a?.volatility_pct, 1, false)} />
            <Stat label="Sharpe ratio" value={a?.sharpe != null ? a.sharpe.toFixed(2) : "—"} />
            <Stat label="Max drawdown" value={<span className="text-down">{pct(a?.max_drawdown_pct, 1)}</span>} />
            <Stat label="Win rate" value={a?.win_rate_pct != null ? pct(a.win_rate_pct, 0, false) : "—"} />
            <Stat label="Best trade" value={<span className="text-up">{a?.best_trade != null ? money(a.best_trade, { sign: true }) : "—"}</span>} />
            <Stat label="Worst trade" value={<span className="text-down">{a?.worst_trade != null ? money(a.worst_trade, { sign: true }) : "—"}</span>} />
          </div>
          {a && a.top_weight_pct > 30 && (
            <div className="mx-5 mb-5 rounded-lg border border-warn/30 bg-warn/10 px-3 py-2 text-xs text-warn">
              Concentration: your largest holding is {a.top_weight_pct.toFixed(0)}% of invested value.
            </div>
          )}
        </Card>
      </div>

      <Card>
        <CardHeader title="Positions" />
        <Holdings />
      </Card>

      <div className="grid gap-5 lg:grid-cols-2">
        <RecurringCard />
        <DividendsReceived />
      </div>

      <Card>
        <CardHeader title="Trade history" />
        <div className="overflow-x-auto">
          <table className="w-full min-w-[560px] text-sm">
            <thead>
              <tr>
                {["Date", "Symbol", "Side", "Shares", "Price", "Realized P&L"].map((h, i) => (
                  <th key={h} className={cn("label px-5 pb-2 pt-3 text-left font-medium", i > 2 && "text-right")}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {(trades ?? []).map((t) => (
                <tr key={t.id} className="border-t border-line/70">
                  <td className="px-5 py-2.5 text-muted">{etTime(t.executed_at)}</td>
                  <td className="px-5 font-semibold">{t.symbol}</td>
                  <td className="px-5"><Badge tone={t.side === "buy" ? "up" : "down"}>{t.side.toUpperCase()}</Badge></td>
                  <td className="num px-5 text-right">{qty(t.quantity)}</td>
                  <td className="num px-5 text-right">{money(t.price)}</td>
                  <td className={cn("num px-5 text-right", tone(t.realized_pnl))}>{t.realized_pnl != null ? money(t.realized_pnl, { sign: true }) : "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {!trades?.length && <Empty title="No trades yet" />}
        </div>
      </Card>
    </div>
  );
}

function RecurringCard() {
  const { data } = useRecurring();
  const qc = useQueryClient();
  const act = async (id: number, body: Record<string, unknown> | null) => {
    try {
      if (body) await api(`/recurring/${id}`, { method: "PATCH", json: body });
      else await api(`/recurring/${id}`, { method: "DELETE" });
      qc.invalidateQueries({ queryKey: ["portfolio", "recurring"] });
    } catch (e) {
      toast.error((e as Error).message);
    }
  };
  return (
    <Card>
      <CardHeader title="Recurring investments" icon={<CalendarClock className="h-4 w-4" />} subtitle="Auto-invest a fixed amount on a schedule" />
      <div className="p-2">
        {(data ?? []).map((r) => (
          <div key={r.id} className="flex items-center gap-3 rounded-lg px-3 py-2.5 hover:bg-panel2/40">
            <StockLogo symbol={r.symbol} className="h-8 w-8" />
            <div className="min-w-0 flex-1">
              <div className="text-sm font-medium">
                {money(r.amount)} of {r.symbol} <span className="text-xs font-normal text-muted">· {r.frequency}</span>
              </div>
              <div className="truncate text-2xs text-muted">
                {r.active ? `Next: ${shortDate(r.next_run)}` : "Paused"} · invested {money(r.total_invested)}
                {r.last_result && ` · ${r.last_result}`}
              </div>
            </div>
            <Switch checked={r.active} onChange={(v) => act(r.id, { active: v })} label="Active" />
            <Button size="icon" variant="ghost" onClick={() => act(r.id, null)} aria-label="Delete"><Trash2 className="h-3.5 w-3.5" /></Button>
          </div>
        ))}
        {!data?.length && <Empty title="No recurring investments" hint="Open any stock and choose “Invest regularly” to auto-invest with fractional shares." />}
      </div>
    </Card>
  );
}

function DividendsReceived() {
  const { data } = useDividends();
  const total = (data ?? []).reduce((s, d) => s + Number(d.amount), 0);
  return (
    <Card>
      <CardHeader title="Dividends received" icon={<Coins className="h-4 w-4" />} subtitle={data?.length ? `${money(total)} total` : "Real payouts on your holdings"} />
      <div className="p-2">
        {(data ?? []).slice(0, 8).map((d) => (
          <div key={`${d.symbol}-${d.ex_date}`} className="flex items-center gap-3 rounded-lg px-3 py-2">
            <StockLogo symbol={d.symbol} className="h-7 w-7" />
            <div className="min-w-0 flex-1">
              <div className="text-sm font-medium">{d.symbol}</div>
              <div className="text-2xs text-muted">{qty(d.quantity)} sh × {money(d.per_share)} · ex {shortDate(d.ex_date)}</div>
            </div>
            <span className="num text-sm text-up">+{money(d.amount)}</span>
          </div>
        ))}
        {!data?.length && <Empty title="No dividends yet" hint="Hold dividend stocks through their ex-date and the real payout lands in your cash." />}
      </div>
    </Card>
  );
}
