import { CalendarDays, ExternalLink, Users } from "lucide-react";
import { CartesianGrid, ResponsiveContainer, Scatter, ScatterChart, Tooltip, XAxis, YAxis, ZAxis } from "recharts";
import { useLiveQuote } from "@/components/Live";
import { Card, CardHeader, Skeleton, Stat } from "@/components/ui";
import { cn } from "@/lib/cn";
import { big, money, pct, shortDate } from "@/lib/format";
import type { Insights, StockDetail } from "@/lib/types";

export function ExtendedLine({ symbol, fallback }: { symbol: string; fallback?: StockDetail["quote"] }) {
  const q = useLiveQuote(symbol, fallback);
  if (!q.ext_price) return null;
  const session = fallback?.ext_session === "pre" ? "Pre-market" : "After hours";
  return (
    <div className="num mt-1 text-right text-xs text-muted">
      {session} <span className="text-fg">${q.ext_price.toFixed(2)}</span>{" "}
      <span className={cn((q.ext_change_pct ?? 0) >= 0 ? "text-up" : "text-down")}>{pct(q.ext_change_pct)}</span>
    </div>
  );
}

export function AnalystCard({ data, loading }: { data?: Insights; loading: boolean }) {
  const a = data?.analysts;
  const pt = data?.price_target;
  if (loading) return <Skeleton className="h-56" />;
  if (!a && !pt) return null;
  const bars = a
    ? [
        { label: "Buy", n: a.buy, tone: "bg-up" },
        { label: "Hold", n: a.hold, tone: "bg-warn" },
        { label: "Sell", n: a.sell, tone: "bg-down" },
      ]
    : [];
  return (
    <Card>
      <CardHeader title="Analyst ratings" subtitle={a ? `${a.total} analysts · consensus ${a.consensus || "n/a"}` : undefined} icon={<Users className="h-4 w-4" />} />
      <div className="space-y-5 p-5">
        {a && (
          <div className="flex items-center gap-5">
            <div className="text-center">
              <div className="num text-3xl font-semibold text-up">{a.buy_pct != null ? `${Math.round(a.buy_pct)}%` : "—"}</div>
              <div className="text-2xs text-muted">say Buy</div>
            </div>
            <div className="flex-1 space-y-2">
              {bars.map((b) => (
                <div key={b.label} className="flex items-center gap-2 text-xs">
                  <span className="w-9 text-muted">{b.label}</span>
                  <div className="h-2 flex-1 overflow-hidden rounded-full bg-panel2">
                    <div className={cn("h-full rounded-full", b.tone)} style={{ width: `${a.total ? (b.n / a.total) * 100 : 0}%` }} />
                  </div>
                  <span className="num w-6 text-right text-muted">{b.n}</span>
                </div>
              ))}
            </div>
          </div>
        )}
        {pt && pt.low != null && pt.high != null && pt.mean != null && (
          <div>
            <div className="mb-2 flex items-baseline justify-between">
              <span className="label">12-month price target</span>
              <span className="num text-sm">
                avg <b>{money(pt.mean)}</b>{" "}
                {pt.current ? <span className={cn("text-xs", pt.mean >= pt.current ? "text-up" : "text-down")}>({pct((pt.mean / pt.current - 1) * 100, 1)})</span> : null}
              </span>
            </div>
            <TargetBar low={pt.low} high={pt.high} mean={pt.mean} current={pt.current} />
          </div>
        )}
      </div>
    </Card>
  );
}

function TargetBar({ low, high, mean, current }: { low: number; high: number; mean: number; current: number | null }) {
  const lo = Math.min(low, current ?? low);
  const hi = Math.max(high, current ?? high);
  const pos = (v: number) => `${((v - lo) / (hi - lo || 1)) * 100}%`;
  return (
    <div>
      <div className="relative h-2 rounded-full bg-gradient-to-r from-down/50 via-warn/50 to-up/50">
        <span className="absolute top-1/2 h-4 w-1 -translate-x-1/2 -translate-y-1/2 rounded bg-fg" style={{ left: pos(mean) }} title="Average target" />
        {current != null && (
          <span className="absolute top-1/2 h-3 w-3 -translate-x-1/2 -translate-y-1/2 rounded-full border-2 border-panel bg-accent" style={{ left: pos(current) }} title="Current price" />
        )}
      </div>
      <div className="num mt-1.5 flex justify-between text-2xs text-muted">
        <span>Low {money(low)}</span>
        <span className="text-accent">● Now {current != null ? money(current) : "—"}</span>
        <span>High {money(high)}</span>
      </div>
    </div>
  );
}

export function EarningsCard({ data, loading }: { data?: Insights; loading: boolean }) {
  const rows = (data?.earnings ?? []).filter((e) => e.estimate != null || e.actual != null);
  if (loading) return <Skeleton className="h-56" />;
  if (!rows.length) return null;
  const pts = rows.flatMap((e, i) => [
    { x: i, y: e.estimate, kind: "Estimate", date: e.date },
    { x: i, y: e.actual, kind: "Actual", date: e.date, beat: e.actual != null && e.estimate != null && e.actual >= e.estimate },
  ]);
  const last = rows[rows.length - 1];
  return (
    <Card>
      <CardHeader
        title="Earnings (EPS)"
        icon={<CalendarDays className="h-4 w-4" />}
        subtitle={data?.next_earnings ? `Next report ${shortDate(data.next_earnings)}` : undefined}
        action={
          last?.surprise_pct != null ? (
            <span className={cn("num text-xs", last.surprise_pct >= 0 ? "text-up" : "text-down")}>last {pct(last.surprise_pct, 1)} surprise</span>
          ) : undefined
        }
      />
      <div className="h-44 px-3 pb-3 pt-2">
        <ResponsiveContainer>
          <ScatterChart margin={{ top: 8, right: 12, bottom: 0, left: 0 }}>
            <CartesianGrid vertical={false} stroke="rgb(var(--line))" strokeOpacity={0.5} />
            <XAxis
              type="number"
              dataKey="x"
              domain={[-0.5, rows.length - 0.5]}
              ticks={rows.map((_, i) => i)}
              tickFormatter={(i) => {
                const d = rows[i]?.date;
                return d ? `Q${Math.floor(new Date(d).getMonth() / 3) + 1} '${d.slice(2, 4)}` : "";
              }}
              tick={{ fill: "rgb(var(--faint))", fontSize: 10 }}
              axisLine={false}
              tickLine={false}
            />
            <YAxis type="number" dataKey="y" tick={{ fill: "rgb(var(--faint))", fontSize: 10 }} axisLine={false} tickLine={false} width={36} tickFormatter={(v) => `$${v}`} />
            <ZAxis range={[90, 90]} />
            <Tooltip
              cursor={false}
              contentStyle={{ background: "rgb(var(--panel))", border: "1px solid rgb(var(--line))", borderRadius: 8, fontSize: 12 }}
              formatter={(v: number, _n, p) => [`$${v?.toFixed(2)}`, (p.payload as { kind: string }).kind]}
              labelFormatter={() => ""}
            />
            <Scatter data={pts.filter((p) => p.kind === "Estimate" && p.y != null)} fill="rgb(var(--faint))" fillOpacity={0.5} />
            <Scatter data={pts.filter((p) => p.kind === "Actual" && p.y != null && p.beat)} fill="rgb(var(--up))" />
            <Scatter data={pts.filter((p) => p.kind === "Actual" && p.y != null && !p.beat)} fill="rgb(var(--down))" />
          </ScatterChart>
        </ResponsiveContainer>
      </div>
      <div className="flex gap-4 px-5 pb-4 text-2xs text-muted">
        <span className="flex items-center gap-1"><span className="h-2 w-2 rounded-full bg-faint/60" /> Expected</span>
        <span className="flex items-center gap-1"><span className="h-2 w-2 rounded-full bg-up" /> Beat</span>
        <span className="flex items-center gap-1"><span className="h-2 w-2 rounded-full bg-down" /> Missed</span>
      </div>
    </Card>
  );
}

export function CompanyCard({ stock, data }: { stock: StockDetail; data?: Insights }) {
  const f = data?.fundamentals ?? {};
  const facts = [
    stock.ceo && { l: "CEO", v: stock.ceo },
    stock.employees && { l: "Employees", v: stock.employees.toLocaleString() },
    stock.hq && { l: "Headquarters", v: stock.hq },
    stock.industry && { l: "Industry", v: stock.industry },
  ].filter(Boolean) as { l: string; v: string }[];
  return (
    <Card className="p-5">
      <div className="label mb-2">About</div>
      <p className="line-clamp-6 text-sm leading-relaxed text-muted">{stock.description || "No description available."}</p>
      {stock.website && (
        <a href={stock.website} target="_blank" rel="noopener noreferrer" className="mt-2 inline-flex items-center gap-1 text-xs text-accent hover:underline">
          {stock.website.replace(/^https?:\/\/(www\.)?/, "")} <ExternalLink className="h-3 w-3" />
        </a>
      )}
      {facts.length > 0 && (
        <div className="mt-4 grid grid-cols-2 gap-x-4 gap-y-3">
          {facts.map((x) => <Stat key={x.l} label={x.l} value={<span className="font-sans text-sm">{x.v}</span>} />)}
        </div>
      )}
      {Object.values(f).some((v) => v != null) && (
        <div className="mt-4 grid grid-cols-2 gap-x-4 gap-y-3 border-t border-line pt-4">
          {f.forward_pe != null && <Stat label="Forward P/E" value={f.forward_pe.toFixed(1)} />}
          {f.eps != null && <Stat label="EPS (TTM)" value={money(f.eps)} />}
          {f.revenue != null && <Stat label="Revenue (TTM)" value={`$${big(f.revenue)}`} />}
          {f.profit_margin != null && <Stat label="Profit margin" value={pct(f.profit_margin * 100, 1, false)} />}
          {f.revenue_growth != null && <Stat label="Revenue growth" value={<span className={f.revenue_growth >= 0 ? "text-up" : "text-down"}>{pct(f.revenue_growth * 100, 1)}</span>} />}
          {f.short_pct_float != null && <Stat label="Short interest" value={pct(f.short_pct_float * 100, 1, false)} />}
          {f.shares_outstanding != null && <Stat label="Shares out." value={big(f.shares_outstanding)} />}
          {f.expense_ratio != null && <Stat label="Expense ratio" value={pct(f.expense_ratio, 2, false)} />}
          {f.aum != null && <Stat label="Assets (AUM)" value={`$${big(f.aum)}`} />}
        </div>
      )}
    </Card>
  );
}

export function DividendsCard({ stock, data }: { stock: StockDetail; data?: Insights }) {
  const divs = data?.dividends ?? [];
  if (!divs.length && !(Number(stock.dividend_yield) > 0)) return null;
  return (
    <Card className="p-5">
      <div className="label mb-3">Dividends</div>
      <div className="grid grid-cols-3 gap-3">
        <Stat label="Yield" value={stock.dividend_yield ? `${Number(stock.dividend_yield).toFixed(2)}%` : "—"} />
        <Stat label="Annual rate" value={data?.dividend_rate ? money(data.dividend_rate) : "—"} />
        <Stat label="Ex-date" value={data?.ex_dividend_date ? shortDate(data.ex_dividend_date).replace(/, \d{4}/, "") : "—"} />
      </div>
      {divs.length > 0 && (
        <div className="mt-4 flex h-16 items-end gap-1.5">
          {divs.map((d) => {
            const max = Math.max(...divs.map((x) => x.amount));
            return (
              <div key={d.date} className="flex flex-1 flex-col items-center gap-1" title={`${shortDate(d.date)}: ${money(d.amount)}`}>
                <div className="w-full rounded-t bg-accent/70" style={{ height: `${(d.amount / max) * 48}px` }} />
                <span className="text-[9px] text-faint">{d.date.slice(2, 7)}</span>
              </div>
            );
          })}
        </div>
      )}
      <p className="mt-3 text-2xs text-faint">Dividends are paid into your cash automatically when you hold shares before the ex-date.</p>
    </Card>
  );
}
