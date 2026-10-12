import { CalendarDays } from "lucide-react";
import { Link } from "react-router-dom";
import { ChangePill, LiveChange, LivePrice, StockLogo } from "@/components/Live";
import { Card, CardHeader, Skeleton } from "@/components/ui";
import { cn } from "@/lib/cn";
import { pct } from "@/lib/format";
import { useCalendar, useOverview, type OverviewRow } from "@/lib/queries";
import { useLive } from "@/stores/live";

function heatColor(c: number) {
  const a = Math.min(1, Math.abs(c) / 3);
  return c >= 0 ? `rgb(var(--up) / ${0.12 + a * 0.6})` : `rgb(var(--down) / ${0.12 + a * 0.6})`;
}

function Heatmap({ rows }: { rows: OverviewRow[] }) {
  const quotes = useLive((s) => s.quotes);
  const bySector = rows.reduce<Record<string, OverviewRow[]>>((acc, r) => {
    (acc[r.sector ?? "Other"] ??= []).push(r);
    return acc;
  }, {});
  return (
    <div className="grid gap-3 p-4 sm:grid-cols-2 xl:grid-cols-4">
      {Object.entries(bySector).map(([sector, items]) => (
        <div key={sector}>
          <div className="label mb-1.5">{sector}</div>
          <div className="grid grid-cols-3 gap-1">
            {items.map((r) => {
              const c = quotes[r.symbol]?.c ?? r.change_pct;
              return (
                <Link
                  key={r.symbol}
                  to={`/stocks/${r.symbol}`}
                  className="rounded-md px-2 py-2.5 text-center transition-transform hover:scale-[1.03]"
                  style={{ background: heatColor(c) }}
                >
                  <div className="text-xs font-semibold">{r.symbol}</div>
                  <div className="num text-2xs opacity-90">{pct(c)}</div>
                </Link>
              );
            })}
          </div>
        </div>
      ))}
    </div>
  );
}

export function MarketsPage() {
  const { data } = useOverview();
  const { data: cal } = useCalendar();
  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-xl font-semibold tracking-tight">Markets</h1>
        <p className="text-sm text-muted">{data?.status.label ?? "…"}</p>
      </div>
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        {(data?.indices ?? []).map((r) => (
          <Link key={r.symbol} to={`/stocks/${r.symbol}`}>
            <Card className="p-4 transition-colors hover:border-faint/50">
              <div className="flex items-center justify-between">
                <span className="text-sm font-semibold">{r.symbol}</span>
                <LiveChange symbol={r.symbol} fallback={r as never} />
              </div>
              <div className="mt-0.5 truncate text-2xs text-muted">{r.name}</div>
              <LivePrice symbol={r.symbol} fallback={r as never} className="mt-2 block text-xl font-semibold" />
            </Card>
          </Link>
        ))}
        {!data && [0, 1, 2, 3].map((i) => <Skeleton key={i} className="h-24" />)}
      </div>
      <Card>
        <CardHeader title="Heatmap" subtitle="Today's change, live" />
        {data ? <Heatmap rows={data.heatmap} /> : <Skeleton className="m-4 h-48" />}
      </Card>
      <div className="grid gap-5 lg:grid-cols-3">
        <Card>
          <CardHeader title="Sectors" />
          <div className="space-y-2 p-5">
            {[...(data?.sectors ?? [])].sort((a, b) => b.change_pct - a.change_pct).map((s) => {
              const w = Math.min(100, Math.abs(s.change_pct) * 30);
              return (
                <Link key={s.symbol} to={`/stocks/${s.symbol}`} className="flex items-center gap-3 text-sm">
                  <span className="w-40 truncate">{s.sector}</span>
                  <div className="relative h-2 flex-1 rounded-full bg-panel2">
                    <div
                      className={cn("absolute top-0 h-2 rounded-full", s.change_pct >= 0 ? "left-1/2 bg-up" : "right-1/2 bg-down")}
                      style={{ width: `${w / 2}%` }}
                    />
                  </div>
                  <ChangePill value={s.change_pct} />
                </Link>
              );
            })}
          </div>
        </Card>
        {(["gainers", "losers"] as const).map((k) => (
          <Card key={k}>
            <CardHeader title={k === "gainers" ? "Top gainers" : "Top losers"} />
            <div className="p-2">
              {(data?.[k] ?? []).map((r) => (
                <Link key={r.symbol} to={`/stocks/${r.symbol}`} className="flex items-center gap-3 rounded-lg px-3 py-2 hover:bg-panel2/60">
                  <StockLogo symbol={r.symbol} className="h-7 w-7" />
                  <div className="min-w-0 flex-1">
                    <div className="text-sm font-semibold">{r.symbol}</div>
                    <div className="truncate text-2xs text-muted">{r.name}</div>
                  </div>
                  <LiveChange symbol={r.symbol} fallback={r as never} />
                </Link>
              ))}
            </div>
          </Card>
        ))}
      </div>
      <Card>
        <CardHeader title="Catalyst calendar" icon={<CalendarDays className="h-4 w-4" />} subtitle="Earnings and macro releases, next 30 days" />
        <div className="grid gap-2 p-4 sm:grid-cols-2 lg:grid-cols-3">
          {(cal ?? []).filter((e) => (e.payload as { upcoming?: boolean }).upcoming).slice(0, 18).map((e) => (
            <div key={e.id} className="flex items-center gap-3 rounded-lg border border-line p-2.5">
              <div className="w-11 shrink-0 rounded-md bg-panel2 py-1 text-center">
                <div className="text-[10px] uppercase text-muted">{new Date(e.ts).toLocaleDateString("en-US", { month: "short" })}</div>
                <div className="num text-sm font-semibold">{new Date(e.ts).getDate()}</div>
              </div>
              <div className="min-w-0">
                <div className="truncate text-sm">{e.title}</div>
                <div className="text-2xs text-muted">{e.symbol ?? "Macro"} · {e.kind.toUpperCase()}</div>
              </div>
            </div>
          ))}
        </div>
      </Card>
    </div>
  );
}
