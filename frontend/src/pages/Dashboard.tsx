import { ArrowRight, Eye, Newspaper, Plus, Sparkles, Workflow, Zap } from "lucide-react";
import { useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Area, AreaChart, CartesianGrid, Line, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { NewsItem } from "@/components/explain/Explain";
import { ChangePill, LiveChange, LivePrice, StockLogo } from "@/components/Live";
import { Badge, Button, Card, CardHeader, Empty, Segmented, Skeleton } from "@/components/ui";
import { cn } from "@/lib/cn";
import { money, pct, qty, shortDate, timeAgo, tone } from "@/lib/format";
import { useHistory, useNews, useOverview, usePositions, useRules, useSummary, useWatchlists } from "@/lib/queries";
import type { Position } from "@/lib/types";
import { useAuth } from "@/stores/auth";
import { useLive } from "@/stores/live";
import { useUI } from "@/stores/ui";

/** Equity recomputed every tick from live quotes, so the headline number moves in real time. */
function useLiveEquity(positions: Position[] | undefined, cash: number | undefined) {
  const quotes = useLive((s) => s.quotes);
  return useMemo(() => {
    if (!positions || cash == null) return null;
    let mv = 0;
    let day = 0;
    for (const p of positions) {
      const live = quotes[p.symbol]?.p ?? p.price;
      mv += p.quantity * live;
      const prevClose = p.price / (1 + p.day_pct / 100);
      day += p.quantity * (live - prevClose);
    }
    const equity = cash + mv;
    return { equity, mv, day, dayPct: (day / (equity - day)) * 100 };
  }, [positions, cash, quotes]);
}

function EquityHero() {
  const { data: s } = useSummary();
  const { data: positions } = usePositions();
  const { data: hist } = useHistory();
  const live = useLiveEquity(positions, s?.cash);
  const [range, setRange] = useState<"1M" | "3M" | "6M" | "ALL">("3M");
  const user = useAuth((st) => st.user);
  const data = useMemo(() => {
    if (!hist) return [];
    const days = { "1M": 31, "3M": 92, "6M": 183, ALL: 100000 }[range];
    const cutoff = Date.now() - days * 86400000;
    const rows = hist.filter((h) => new Date(h.date).getTime() >= cutoff);
    if (live && rows.length) rows[rows.length - 1] = { ...rows[rows.length - 1], equity: live.equity };
    return rows;
  }, [hist, range, live]);
  const first = data[0]?.equity;
  const last = data[data.length - 1]?.equity;
  const rangePct = first ? (last / first - 1) * 100 : 0;
  const up = rangePct >= 0;
  const equity = live?.equity ?? s?.equity;

  return (
    <Card className="relative overflow-hidden">
      <div className="pointer-events-none absolute inset-0 opacity-50 [background:radial-gradient(50%_60%_at_0%_0%,rgb(var(--ai)/0.12),transparent)]" />
      <div className="relative flex flex-wrap items-start justify-between gap-4 px-6 pt-5">
        <div>
          <p className="text-sm text-muted">Good {greeting()}, {user?.name}</p>
          <div className="mt-1 text-[40px] font-semibold leading-tight tracking-tight">
            {equity != null ? <span className="num">{money(equity)}</span> : <Skeleton className="h-10 w-56" />}
          </div>
          <div className="mt-1 flex flex-wrap items-center gap-3 text-sm">
            {live && (
              <span className={cn("num font-medium", tone(live.day))}>
                {money(live.day, { sign: true })} ({pct(live.dayPct)}) <span className="font-sans font-normal text-muted">today</span>
              </span>
            )}
            {s && (
              <span className={cn("num", tone(s.total_pnl))}>
                {money(s.total_pnl, { sign: true })} ({pct(s.total_pct)}) <span className="font-sans text-muted">all time</span>
              </span>
            )}
          </div>
        </div>
        <Segmented value={range} onChange={setRange} options={(["1M", "3M", "6M", "ALL"] as const).map((r) => ({ value: r, label: r }))} />
      </div>
      <div className="relative h-56 px-2 pb-2 pt-4">
        {data.length > 1 ? (
          <ResponsiveContainer>
            <AreaChart data={data} margin={{ top: 4, right: 12, left: 12, bottom: 0 }}>
              <defs>
                <linearGradient id="eq" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0" stopColor={up ? "rgb(var(--up))" : "rgb(var(--down))"} stopOpacity={0.3} />
                  <stop offset="1" stopColor={up ? "rgb(var(--up))" : "rgb(var(--down))"} stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid vertical={false} stroke="rgb(var(--line))" strokeOpacity={0.5} />
              <XAxis dataKey="date" tickFormatter={(d) => shortDate(d).replace(/, \d{4}/, "")} tick={{ fill: "rgb(var(--faint))", fontSize: 11 }} axisLine={false} tickLine={false} minTickGap={40} />
              <YAxis domain={["auto", "auto"]} orientation="right" tickFormatter={(v) => `$${(v / 1000).toFixed(0)}k`} tick={{ fill: "rgb(var(--faint))", fontSize: 11 }} axisLine={false} tickLine={false} width={48} />
              <Tooltip
                contentStyle={{ background: "rgb(var(--panel))", border: "1px solid rgb(var(--line))", borderRadius: 10, fontSize: 12 }}
                labelFormatter={(d) => shortDate(String(d))}
                formatter={(v: number, name) => [money(v), name === "equity" ? "Portfolio" : "S&P 500 (same start)"]}
              />
              <Line type="monotone" dataKey="benchmark" stroke="rgb(var(--faint))" strokeDasharray="4 4" dot={false} strokeWidth={1.25} isAnimationActive={false} />
              <Area type="monotone" dataKey="equity" stroke={up ? "rgb(var(--up))" : "rgb(var(--down))"} strokeWidth={2} fill="url(#eq)" isAnimationActive={false} />
            </AreaChart>
          </ResponsiveContainer>
        ) : (
          <div className="grid h-full place-items-center text-sm text-muted">Your equity curve will appear after your first trading day.</div>
        )}
      </div>
      <div className="relative grid grid-cols-2 border-t border-line sm:grid-cols-4">
        {[
          { l: "Buying power", v: money(s?.buying_power) },
          { l: "Invested", v: money(live?.mv ?? s?.positions_value) },
          { l: `${range} return`, v: <span className={tone(rangePct)}>{pct(rangePct)}</span> },
          { l: "Unrealized P&L", v: <span className={tone(s?.unrealized_pnl)}>{money(s?.unrealized_pnl, { sign: true })}</span> },
        ].map((x, i) => (
          <div key={x.l} className={cn("px-6 py-3.5", i > 0 && "border-l border-line", i === 2 && "border-l-0 sm:border-l")}>
            <div className="label">{x.l}</div>
            <div className="num mt-1 text-[15px] font-semibold">{x.v}</div>
          </div>
        ))}
      </div>
    </Card>
  );
}

function greeting() {
  const h = new Date().getHours();
  return h < 12 ? "morning" : h < 18 ? "afternoon" : "evening";
}

export function Holdings({ limit }: { limit?: number }) {
  const { data, isLoading } = usePositions();
  const quotes = useLive((s) => s.quotes);
  const navigate = useNavigate();
  const rows = (data ?? []).slice(0, limit);
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="text-left">
            {["Symbol", "Price", "Today", "Shares", "Value", "Total return", "Weight"].map((h, i) => (
              <th key={h} className={cn("label px-4 pb-2 pt-3 font-medium first:pl-5 last:pr-5", i > 0 && "text-right", i === 3 && "hidden 2xl:table-cell", i === 6 && "hidden md:table-cell")}>{h}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {isLoading &&
            Array.from({ length: 4 }).map((_, i) => (
              <tr key={i}><td colSpan={7} className="px-5 py-2"><Skeleton className="h-8" /></td></tr>
            ))}
          {rows.map((p) => {
            const live = quotes[p.symbol]?.p ?? p.price;
            const value = p.quantity * live;
            const unreal = value - p.cost_basis;
            return (
              <tr key={p.symbol} onClick={() => navigate(`/stocks/${p.symbol}`)} className="cursor-pointer border-t border-line/70 transition-colors hover:bg-panel2/50">
                <td className="px-5 py-2.5">
                  <div className="flex items-center gap-3">
                    <StockLogo symbol={p.symbol} />
                    <div className="min-w-0">
                      <div className="font-semibold">{p.symbol}</div>
                      <div className="max-w-[160px] truncate text-xs text-muted">{p.name}</div>
                    </div>
                  </div>
                </td>
                <td className="px-4 text-right"><LivePrice symbol={p.symbol} fallback={{ price: p.price, change_pct: p.day_pct } as never} /></td>
                <td className="px-4 text-right"><LiveChange symbol={p.symbol} fallback={{ price: p.price, change_pct: p.day_pct } as never} /></td>
                <td className="num hidden px-4 text-right text-muted 2xl:table-cell">{qty(p.quantity)}</td>
                <td className="num px-4 text-right font-medium">{money(value)}</td>
                <td className={cn("num px-4 text-right", tone(unreal))}>
                  <div>{money(unreal, { sign: true })}</div>
                  <div className="text-xs">{pct((live / p.avg_cost - 1) * 100)}</div>
                </td>
                <td className="hidden pr-5 text-right md:table-cell">
                  <div className="ml-auto flex w-20 items-center gap-2">
                    <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-panel2">
                      <div className="h-full rounded-full bg-accent" style={{ width: `${Math.min(100, p.weight)}%` }} />
                    </div>
                    <span className="num w-9 text-xs text-muted">{p.weight.toFixed(0)}%</span>
                  </div>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
      {!isLoading && !rows.length && (
        <Empty
          icon={<Zap className="h-5 w-5" />}
          title="No positions yet"
          hint="Press ⌘K and type “buy $1000 of Apple” to place your first trade."
          action={<Button variant="ai" size="sm" onClick={() => useUI.getState().openPalette("buy $1000 of apple")}>Try it</Button>}
        />
      )}
    </div>
  );
}

function WatchlistCard() {
  const { data } = useWatchlists();
  const wl = data?.[0];
  return (
    <Card>
      <CardHeader
        title={wl?.name ?? "Watchlist"}
        icon={<Eye className="h-4 w-4" />}
        action={<Button variant="ghost" size="icon" onClick={() => useUI.getState().openPalette()} title="Find a stock"><Plus className="h-4 w-4" /></Button>}
      />
      <div className="p-2">
        {wl?.items.map((i) => (
          <Link key={i.symbol} to={`/stocks/${i.symbol}`} className="flex items-center gap-3 rounded-lg px-3 py-2 hover:bg-panel2/60">
            <StockLogo symbol={i.symbol} className="h-7 w-7" />
            <div className="min-w-0 flex-1">
              <div className="text-sm font-semibold">{i.symbol}</div>
              <div className="truncate text-2xs text-muted">{i.name}</div>
            </div>
            <div className="text-right">
              <LivePrice symbol={i.symbol} fallback={i.quote} className="text-sm" />
              <div><LiveChange symbol={i.symbol} fallback={i.quote} pill={false} className="text-xs" /></div>
            </div>
          </Link>
        ))}
        {!wl?.items.length && <Empty title="Nothing watched yet" hint="Open a stock and press Watch." />}
      </div>
    </Card>
  );
}

function AutomationsCard() {
  const { data } = useRules();
  const active = (data ?? []).filter((r) => r.status === "active");
  return (
    <Card>
      <CardHeader
        title="Automations"
        icon={<Workflow className="h-4 w-4" />}
        subtitle={`${active.length} active`}
        action={<Link to="/rules" className="text-xs text-muted hover:text-fg">Manage</Link>}
      />
      <div className="space-y-1 p-2">
        {(data ?? []).slice(0, 4).map((r) => (
          <Link key={r.id} to="/rules" className="flex items-center gap-3 rounded-lg px-3 py-2 hover:bg-panel2/60">
            <span className={cn("h-2 w-2 rounded-full", r.status === "active" ? "bg-up" : r.status === "triggered" ? "bg-ai" : r.status === "error" ? "bg-down" : "bg-faint")} />
            <div className="min-w-0 flex-1">
              <div className="truncate text-sm">{r.name}</div>
              <div className="truncate text-2xs text-muted">{r.readable?.then}</div>
            </div>
            <Badge tone={r.status === "active" ? "up" : r.status === "triggered" ? "ai" : r.status === "error" ? "down" : "neutral"}>{r.status}</Badge>
          </Link>
        ))}
        <button
          onClick={() => useUI.getState().openPalette("if ")}
          className="flex w-full items-center gap-2 rounded-lg px-3 py-2 text-left text-sm text-ai hover:bg-ai/5"
        >
          <Sparkles className="h-4 w-4" /> Describe a new automation…
        </button>
      </div>
    </Card>
  );
}

function LiveWhyFeed() {
  const moves = useLive((s) => s.liveMoves);
  const liveNews = useLive((s) => s.news);
  const { data: news } = useNews();
  const items = [...liveNews, ...(news ?? [])].slice(0, 8);
  return (
    <Card>
      <CardHeader title="Why things are moving" icon={<Newspaper className="h-4 w-4" />} subtitle="Live, explained as it happens" />
      <div className="px-5 pb-3">
        {moves.slice(0, 3).map((m, i) => (
          <Link key={i} to={`/stocks/${m.symbol}`} className="mt-3 block animate-fadeIn rounded-lg border border-ai/25 bg-ai/5 p-3 hover:bg-ai/10">
            <div className="flex items-center justify-between">
              <span className="flex items-center gap-2 text-sm font-semibold"><Sparkles className="h-3.5 w-3.5 text-ai" /> {m.symbol}</span>
              <ChangePill value={m.pct} />
            </div>
            <p className="mt-1.5 text-xs leading-relaxed text-fg/85">{m.summary}</p>
            <p className="mt-1 text-2xs text-muted">{timeAgo(m.end_t * 1000)}</p>
          </Link>
        ))}
        <div className="divide-y divide-line">
          {items.map((a) => <NewsItem key={a.id} a={a} compact />)}
        </div>
      </div>
    </Card>
  );
}

function Movers() {
  const { data } = useOverview();
  const [tab, setTab] = useState<"gainers" | "losers" | "active">("gainers");
  const rows = data?.[tab] ?? [];
  return (
    <Card>
      <CardHeader
        title="Market movers"
        action={<Segmented value={tab} onChange={setTab} options={[{ value: "gainers", label: "Gainers" }, { value: "losers", label: "Losers" }, { value: "active", label: "Active" }]} />}
      />
      <div className="grid gap-2 p-4 sm:grid-cols-2 lg:grid-cols-3">
        {rows.map((r) => (
          <Link key={r.symbol} to={`/stocks/${r.symbol}`} className="flex items-center gap-3 rounded-lg border border-line bg-panel2/30 p-3 transition-colors hover:border-faint/50">
            <StockLogo symbol={r.symbol} />
            <div className="min-w-0 flex-1">
              <div className="text-sm font-semibold">{r.symbol}</div>
              <div className="truncate text-2xs text-muted">{r.name}</div>
            </div>
            <div className="text-right">
              <LivePrice symbol={r.symbol} fallback={r as never} className="text-sm" />
              <div><LiveChange symbol={r.symbol} fallback={r as never} pill={false} className="text-xs" /></div>
            </div>
          </Link>
        ))}
      </div>
    </Card>
  );
}

export function DashboardPage() {
  return (
    <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_360px]">
      <div className="min-w-0 space-y-5">
        <EquityHero />
        <Card>
          <CardHeader title="Holdings" action={<Link to="/portfolio" className="flex items-center gap-1 text-xs text-muted hover:text-fg">Portfolio <ArrowRight className="h-3 w-3" /></Link>} />
          <Holdings limit={10} />
        </Card>
        <Movers />
      </div>
      <div className="space-y-5">
        <WatchlistCard />
        <AutomationsCard />
        <LiveWhyFeed />
      </div>
    </div>
  );
}
