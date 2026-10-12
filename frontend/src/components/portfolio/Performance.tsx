import { Activity, Award, CalendarRange, Flame, Gauge, Scale, Target, Timer, TrendingDown, TrendingUp } from "lucide-react";
import { useState, type ReactNode } from "react";
import { Link } from "react-router-dom";
import { Area, AreaChart, Bar, BarChart, CartesianGrid, Cell, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { StockLogo } from "@/components/Live";
import { Badge, Card, CardHeader, Empty, Segmented, Skeleton } from "@/components/ui";
import { cn } from "@/lib/cn";
import { money, pct, qty, shortDate, tone } from "@/lib/format";
import { usePerformance, type Performance } from "@/lib/queries";

const PERIODS = [
  { value: "30d", label: "30D" },
  { value: "90d", label: "90D" },
  { value: "ytd", label: "YTD" },
  { value: "1y", label: "1Y" },
  { value: "all", label: "All" },
] as const;

const tip = { background: "rgb(var(--panel))", border: "1px solid rgb(var(--line))", borderRadius: 10, fontSize: 12 };
const axis = { fill: "rgb(var(--faint))", fontSize: 11 };
const days = (d: number | null | undefined) => (d == null ? "—" : d < 1 ? `${Math.round(d * 24)}h` : `${d.toFixed(1)}d`);
const num = (v: number | null | undefined, digits = 2) => (v == null || !Number.isFinite(v) ? "—" : v.toFixed(digits));

function Kpi({ icon, label, value, sub, className }: { icon: ReactNode; label: string; value: ReactNode; sub?: ReactNode; className?: string }) {
  return (
    <Card className={cn("p-4", className)}>
      <div className="flex items-center gap-2 text-muted">
        <span className="grid h-7 w-7 place-items-center rounded-lg bg-panel2">{icon}</span>
        <span className="label">{label}</span>
      </div>
      <div className="num mt-3 text-2xl font-semibold tracking-tight">{value}</div>
      {sub && <div className="mt-1 text-xs text-muted">{sub}</div>}
    </Card>
  );
}

function WinRateRing({ s }: { s: Performance["summary"] }) {
  const rate = s.win_rate_pct ?? 0;
  const r = 38;
  const c = 2 * Math.PI * r;
  return (
    <Card className="flex items-center gap-5 p-5 lg:col-span-2">
      <div className="relative h-28 w-28 shrink-0">
        <svg viewBox="0 0 100 100" className="h-full w-full -rotate-90">
          <circle cx="50" cy="50" r={r} fill="none" stroke="rgb(var(--down) / 0.25)" strokeWidth="11" />
          <circle cx="50" cy="50" r={r} fill="none" stroke="rgb(var(--up))" strokeWidth="11" strokeLinecap="round" strokeDasharray={`${(rate / 100) * c} ${c}`} />
        </svg>
        <div className="absolute inset-0 grid place-items-center text-center">
          <div>
            <div className="num text-2xl font-semibold">{s.win_rate_pct != null ? `${s.win_rate_pct.toFixed(0)}%` : "—"}</div>
            <div className="text-2xs text-muted">win rate</div>
          </div>
        </div>
      </div>
      <div className="grid flex-1 grid-cols-2 gap-x-6 gap-y-3">
        <div>
          <div className="label">Wins</div>
          <div className="num text-xl font-semibold text-up">{s.wins}</div>
        </div>
        <div>
          <div className="label">Losses</div>
          <div className="num text-xl font-semibold text-down">{s.losses}</div>
        </div>
        <div>
          <div className="label">Closed trades</div>
          <div className="num text-xl font-semibold">{s.closed_trades}</div>
        </div>
        <div>
          <div className="label">Net realized</div>
          <div className={cn("num text-xl font-semibold", tone(s.net_pnl))}>{money(s.net_pnl, { sign: true })}</div>
        </div>
        <div className="col-span-2 flex items-center gap-2 border-t border-line pt-2.5 text-xs text-muted">
          <Flame className="h-3.5 w-3.5" />
          Current streak{" "}
          <b className={s.current.kind === "win" ? "text-up" : s.current.kind === "loss" ? "text-down" : "text-fg"}>
            {s.current.length} {s.current.kind === "win" ? (s.current.length === 1 ? "win" : "wins") : s.current.kind === "loss" ? (s.current.length === 1 ? "loss" : "losses") : "—"}
          </b>
          · best run <b className="text-up">{s.max_win_streak}W</b> · worst run <b className="text-down">{s.max_loss_streak}L</b>
        </div>
      </div>
    </Card>
  );
}

function AvgWinLoss({ s }: { s: Performance["summary"] }) {
  const w = s.avg_win ?? 0;
  const l = Math.abs(s.avg_loss ?? 0);
  const max = Math.max(w, l) || 1;
  return (
    <Card className="p-4">
      <div className="flex items-center gap-2 text-muted">
        <span className="grid h-7 w-7 place-items-center rounded-lg bg-panel2"><Scale className="h-3.5 w-3.5" /></span>
        <span className="label">Avg win vs avg loss</span>
      </div>
      <div className="mt-3 space-y-2">
        {[
          { l: "Win", v: w, c: "bg-up", t: "text-up" },
          { l: "Loss", v: l, c: "bg-down", t: "text-down" },
        ].map((x) => (
          <div key={x.l} className="flex items-center gap-2 text-xs">
            <span className="w-8 text-muted">{x.l}</span>
            <div className="h-2.5 flex-1 overflow-hidden rounded-full bg-panel2">
              <div className={cn("h-full rounded-full", x.c)} style={{ width: `${(x.v / max) * 100}%` }} />
            </div>
            <span className={cn("num w-20 text-right font-medium", x.t)}>{x.l === "Loss" ? "−" : "+"}{money(x.v)}</span>
          </div>
        ))}
      </div>
      <div className="mt-2 text-xs text-muted">Payoff ratio <span className="num text-fg">{num(s.payoff_ratio)}×</span></div>
    </Card>
  );
}

function ExtremeTrade({ label, t, good }: { label: string; t: Performance["summary"]["largest_win"]; good: boolean }) {
  return (
    <Card className="p-4">
      <div className="flex items-center gap-2 text-muted">
        <span className="grid h-7 w-7 place-items-center rounded-lg bg-panel2">{good ? <TrendingUp className="h-3.5 w-3.5 text-up" /> : <TrendingDown className="h-3.5 w-3.5 text-down" />}</span>
        <span className="label">{label}</span>
      </div>
      {t ? (
        <Link to={`/stocks/${t.symbol}`} className="mt-3 flex items-center gap-3">
          <StockLogo symbol={t.symbol} className="h-9 w-9" />
          <div className="min-w-0">
            <div className={cn("num text-xl font-semibold", good ? "text-up" : "text-down")}>{money(t.pnl, { sign: true })}</div>
            <div className="truncate text-xs text-muted">
              {t.symbol} · {pct(t.return_pct, 1)} · held {days(t.held_days)}
            </div>
          </div>
        </Link>
      ) : (
        <div className="mt-3 text-sm text-muted">None yet</div>
      )}
    </Card>
  );
}

export function PerformanceSection() {
  const [period, setPeriod] = useState<(typeof PERIODS)[number]["value"]>("all");
  const { data, isLoading } = usePerformance(period);
  const s = data?.summary;
  const r = data?.risk;

  return (
    <section className="space-y-4">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h2 className="flex items-center gap-2 text-base font-semibold tracking-tight"><Award className="h-4 w-4 text-ai" /> Trading performance</h2>
          <p className="text-xs text-muted">Every closed trade (sell fill) in the period. P&amp;L on an average-cost basis; holding time matched first-in-first-out.</p>
        </div>
        <Segmented value={period} onChange={setPeriod} options={PERIODS.map((p) => ({ value: p.value, label: p.label }))} />
      </div>

      {isLoading || !data || !s ? (
        <div className="grid gap-3 md:grid-cols-4">{Array.from({ length: 8 }).map((_, i) => <Skeleton key={i} className="h-28" />)}</div>
      ) : s.closed_trades === 0 ? (
        <Card><Empty icon={<Activity className="h-5 w-5" />} title="No closed trades in this period" hint="Win rate, profit factor and the rest appear once you sell a position." /></Card>
      ) : (
        <>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <WinRateRing s={s} />
            <Kpi icon={<Gauge className="h-3.5 w-3.5" />} label="Profit factor" value={<span className={cn(s.profit_factor != null && (s.profit_factor >= 1 ? "text-up" : "text-down"))}>{num(s.profit_factor)}</span>} sub={<>Gross {money(s.gross_profit)} won / {money(s.gross_loss)} lost</>} />
            <Kpi icon={<Target className="h-3.5 w-3.5" />} label="Expectancy" value={<span className={tone(s.expectancy)}>{money(s.expectancy, { sign: true })}</span>} sub={<>per trade · avg return {pct(s.avg_return_pct, 1)}</>} />
            <AvgWinLoss s={s} />
            <ExtremeTrade label="Largest win" t={s.largest_win} good />
            <ExtremeTrade label="Largest loss" t={s.largest_loss} good={false} />
            <Kpi
              icon={<Timer className="h-3.5 w-3.5" />}
              label="Avg holding time"
              value={<span className="text-base"><span className="text-up">{days(s.avg_hold_days_win)}</span> <span className="text-xs text-muted">winners</span> · <span className="text-down">{days(s.avg_hold_days_loss)}</span> <span className="text-xs text-muted">losers</span></span>}
              sub={s.avg_hold_days_loss != null && s.avg_hold_days_win != null && s.avg_hold_days_loss > s.avg_hold_days_win ? "You hold losers longer than winners" : "You let winners run longer than losers"}
            />
          </div>

          <div className="grid gap-4 lg:grid-cols-2">
            <Card>
              <CardHeader title="Monthly realized P&L" icon={<CalendarRange className="h-4 w-4" />} subtitle={`${data.monthly.filter((m) => m.pnl > 0).length} of ${data.monthly.length} months profitable`} />
              <div className="h-56 px-2 pb-3 pt-2">
                <ResponsiveContainer>
                  <BarChart data={data.monthly} margin={{ top: 8, right: 12, left: 4, bottom: 0 }}>
                    <CartesianGrid vertical={false} stroke="rgb(var(--line))" strokeOpacity={0.5} />
                    <XAxis dataKey="month" tickFormatter={(m) => new Date(`${m}-15`).toLocaleDateString("en-US", { month: "short", year: "2-digit" })} tick={axis} axisLine={false} tickLine={false} />
                    <YAxis tickFormatter={(v) => `$${Math.round(v)}`} tick={axis} axisLine={false} tickLine={false} width={52} />
                    <ReferenceLine y={0} stroke="rgb(var(--faint))" />
                    <Tooltip cursor={{ fill: "rgb(var(--panel-2))" }} contentStyle={tip} formatter={(v: number, _n, p) => [money(v, { sign: true }), `${(p.payload as { trades: number }).trades} trades`]} />
                    <Bar dataKey="pnl" radius={[4, 4, 4, 4]}>
                      {data.monthly.map((m) => <Cell key={m.month} fill={m.pnl >= 0 ? "rgb(var(--up))" : "rgb(var(--down))"} />)}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </Card>
            <Card>
              <CardHeader title="Cumulative realized P&L" icon={<TrendingUp className="h-4 w-4" />} subtitle="Running total across closed trades" />
              <div className="h-56 px-2 pb-3 pt-2">
                <ResponsiveContainer>
                  <AreaChart data={data.cumulative} margin={{ top: 8, right: 12, left: 4, bottom: 0 }}>
                    <defs>
                      <linearGradient id="cumpnl" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="0" stopColor="rgb(var(--ai))" stopOpacity={0.35} />
                        <stop offset="1" stopColor="rgb(var(--ai))" stopOpacity={0} />
                      </linearGradient>
                    </defs>
                    <CartesianGrid vertical={false} stroke="rgb(var(--line))" strokeOpacity={0.5} />
                    <XAxis dataKey="date" tickFormatter={(d) => shortDate(d).replace(/, \d{4}/, "")} tick={axis} axisLine={false} tickLine={false} minTickGap={40} />
                    <YAxis tickFormatter={(v) => `$${Math.round(v)}`} tick={axis} axisLine={false} tickLine={false} width={52} />
                    <ReferenceLine y={0} stroke="rgb(var(--faint))" />
                    <Tooltip contentStyle={tip} labelFormatter={(d) => shortDate(String(d))} formatter={(v: number) => [money(v, { sign: true }), "Realized to date"]} />
                    <Area type="stepAfter" dataKey="pnl" stroke="rgb(var(--ai))" strokeWidth={2} fill="url(#cumpnl)" isAnimationActive={false} />
                  </AreaChart>
                </ResponsiveContainer>
              </div>
            </Card>
            <Card>
              <CardHeader title="Return per trade" icon={<Activity className="h-4 w-4" />} subtitle="How your closed trades are distributed" />
              <div className="h-56 px-2 pb-3 pt-2">
                <ResponsiveContainer>
                  <BarChart data={data.distribution} margin={{ top: 8, right: 12, left: 0, bottom: 0 }}>
                    <CartesianGrid vertical={false} stroke="rgb(var(--line))" strokeOpacity={0.5} />
                    <XAxis dataKey="bucket" tick={{ ...axis, fontSize: 9 }} axisLine={false} tickLine={false} interval={0} angle={-25} textAnchor="end" height={42} />
                    <YAxis allowDecimals={false} tick={axis} axisLine={false} tickLine={false} width={28} />
                    <Tooltip cursor={{ fill: "rgb(var(--panel-2))" }} contentStyle={tip} formatter={(v: number) => [v, "trades"]} />
                    <Bar dataKey="count" radius={[4, 4, 0, 0]}>
                      {data.distribution.map((d) => <Cell key={d.bucket} fill={d.positive ? "rgb(var(--up))" : "rgb(var(--down))"} fillOpacity={0.85} />)}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </Card>
            <Card>
              <CardHeader title="P&L by stock" subtitle="Where your gains and losses came from" />
              <div className="space-y-2 p-5">
                {data.by_symbol.slice(0, 8).map((b) => {
                  const max = Math.max(...data.by_symbol.map((x) => Math.abs(x.pnl))) || 1;
                  return (
                    <Link key={b.symbol} to={`/stocks/${b.symbol}`} className="flex items-center gap-3 text-sm hover:opacity-90">
                      <StockLogo symbol={b.symbol} className="h-6 w-6" />
                      <span className="w-14 font-medium">{b.symbol}</span>
                      <div className="relative h-2 flex-1 rounded-full bg-panel2">
                        <div className={cn("absolute top-0 h-2 rounded-full", b.pnl >= 0 ? "left-1/2 bg-up" : "right-1/2 bg-down")} style={{ width: `${(Math.abs(b.pnl) / max) * 50}%` }} />
                      </div>
                      <span className="w-10 text-right text-2xs text-muted">{b.wins}/{b.trades}</span>
                      <span className={cn("num w-24 text-right", tone(b.pnl))}>{money(b.pnl, { sign: true })}</span>
                    </Link>
                  );
                })}
              </div>
            </Card>
          </div>
        </>
      )}

      {r && r.days >= 5 && (
        <Card>
          <CardHeader title="Risk-adjusted returns" icon={<Gauge className="h-4 w-4" />} subtitle={`From ${r.days} days of equity history, vs the S&P 500 (SPY)`} />
          <div className="grid grid-cols-2 gap-x-6 gap-y-4 p-5 sm:grid-cols-4 lg:grid-cols-8">
            {[
              { l: "Sortino", v: num(r.sortino) },
              { l: "Beta", v: num(r.beta) },
              { l: "Alpha (ann.)", v: <span className={tone(r.alpha_annual_pct)}>{pct(r.alpha_annual_pct, 1)}</span> },
              { l: "Correlation", v: num(r.correlation) },
              { l: "CAGR", v: <span className={tone(r.cagr_pct)}>{pct(r.cagr_pct, 1)}</span> },
              { l: "Calmar", v: num(r.calmar) },
              { l: "Best day", v: <span className="text-up">{pct(r.best_day?.pct)}</span>, sub: r.best_day && shortDate(r.best_day.date) },
              { l: "Worst day", v: <span className="text-down">{pct(r.worst_day?.pct)}</span>, sub: r.worst_day && shortDate(r.worst_day.date) },
            ].map((x) => (
              <div key={x.l}>
                <div className="label">{x.l}</div>
                <div className="num mt-1 text-lg font-semibold">{x.v}</div>
                {x.sub && <div className="text-2xs text-faint">{x.sub}</div>}
              </div>
            ))}
          </div>
          {r.positive_days_pct != null && <p className="px-5 pb-4 text-xs text-muted">Up on {r.positive_days_pct.toFixed(0)}% of days.</p>}
        </Card>
      )}

      {data && (
        <div className="grid gap-4 lg:grid-cols-[1fr_1fr]">
          <Card className="p-5">
            <div className="label mb-3">Open positions</div>
            <div className="flex items-center gap-6">
              <div><div className="num text-2xl font-semibold">{data.open_positions.count}</div><div className="text-2xs text-muted">held</div></div>
              <div><div className="num text-2xl font-semibold text-up">{data.open_positions.winners}</div><div className="text-2xs text-muted">in profit</div></div>
              <div><div className="num text-2xl font-semibold text-down">{data.open_positions.losers}</div><div className="text-2xs text-muted">at a loss</div></div>
              <div className="ml-auto text-right"><div className={cn("num text-lg font-semibold", tone(data.open_positions.unrealized_pnl))}>{money(data.open_positions.unrealized_pnl, { sign: true })}</div><div className="text-2xs text-muted">unrealized</div></div>
            </div>
            {data.open_positions.best && (
              <p className="mt-3 text-xs text-muted">
                Best: <b className="text-fg">{data.open_positions.best.symbol}</b> <span className="text-up">{pct(data.open_positions.best.unrealized_pct, 1)}</span>
                {data.open_positions.worst && <> · Worst: <b className="text-fg">{data.open_positions.worst.symbol}</b> <span className={tone(data.open_positions.worst.unrealized_pct)}>{pct(data.open_positions.worst.unrealized_pct, 1)}</span></>}
              </p>
            )}
          </Card>
          <Card className="p-5">
            <div className="label mb-3">Order activity</div>
            <div className="flex items-center gap-6">
              <div><div className="num text-2xl font-semibold">{data.activity.orders}</div><div className="text-2xs text-muted">orders</div></div>
              <div><div className="num text-2xl font-semibold text-up">{data.activity.filled}</div><div className="text-2xs text-muted">filled</div></div>
              <div><div className="num text-2xl font-semibold text-muted">{data.activity.cancelled}</div><div className="text-2xs text-muted">cancelled</div></div>
              <div><div className="num text-2xl font-semibold text-down">{data.activity.rejected}</div><div className="text-2xs text-muted">rejected</div></div>
              <div className="ml-auto text-right"><div className="num text-lg font-semibold">{money(data.activity.buy_volume, { whole: true })}</div><div className="text-2xs text-muted">bought</div></div>
            </div>
            <div className="mt-3 flex flex-wrap gap-1.5">
              {Object.entries(data.activity.by_source).filter(([, n]) => n > 0).map(([k, n]) => (
                <Badge key={k} tone={k === "rule" ? "ai" : k === "assistant" ? "accent" : "neutral"}>{k} · {n}</Badge>
              ))}
            </div>
          </Card>
        </div>
      )}

      {data && data.recent.length > 0 && (
        <Card className="overflow-x-auto">
          <CardHeader title="Closed trades" subtitle="Most recent first" />
          <table className="mt-2 w-full min-w-[720px] text-sm">
            <thead>
              <tr>
                {["Stock", "Opened", "Closed", "Held", "Shares", "Entry", "Exit", "Return", "P&L"].map((h, i) => (
                  <th key={h} className={cn("label px-4 pb-2 text-left font-medium first:pl-5 last:pr-5", i >= 3 && "text-right")}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {data.recent.map((t, i) => (
                <tr key={i} className="border-t border-line/70">
                  <td className="py-2.5 pl-5 pr-4">
                    <Link to={`/stocks/${t.symbol}`} className="flex items-center gap-2.5">
                      <StockLogo symbol={t.symbol} className="h-7 w-7" />
                      <span className="font-semibold">{t.symbol}</span>
                    </Link>
                  </td>
                  <td className="px-4 text-xs text-muted">{t.opened_at ? shortDate(t.opened_at) : "—"}</td>
                  <td className="px-4 text-xs text-muted">{shortDate(t.closed_at)}</td>
                  <td className="num px-4 text-right text-muted">{days(t.held_days)}</td>
                  <td className="num px-4 text-right">{qty(t.quantity)}</td>
                  <td className="num px-4 text-right">{money(t.entry)}</td>
                  <td className="num px-4 text-right">{money(t.exit)}</td>
                  <td className={cn("num px-4 text-right", tone(t.return_pct))}>{pct(t.return_pct, 1)}</td>
                  <td className={cn("num pl-4 pr-5 text-right font-medium", tone(t.pnl))}>{money(t.pnl, { sign: true })}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      )}
    </section>
  );
}
