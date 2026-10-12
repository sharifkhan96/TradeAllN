import { Compass, Flame, TrendingDown, TrendingUp, Users } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";
import { ChangePill, LiveChange, LivePrice, StockLogo } from "@/components/Live";
import { Card, CardHeader, Empty, Segmented, Skeleton } from "@/components/ui";
import { cn } from "@/lib/cn";
import { big, price } from "@/lib/format";
import { useDiscover, useOverview, type Collection, type ScreenRow } from "@/lib/queries";

function MoverRow({ r }: { r: ScreenRow }) {
  return (
    <Link to={`/stocks/${r.symbol}`} className="flex items-center gap-3 rounded-lg px-3 py-2.5 transition-colors hover:bg-panel2/60">
      <StockLogo symbol={r.symbol} />
      <div className="min-w-0 flex-1">
        <div className="text-sm font-semibold">{r.symbol}</div>
        <div className="truncate text-2xs text-muted">{r.name}</div>
      </div>
      <div className="hidden text-right text-2xs text-muted sm:block">
        {r.market_cap ? `$${big(r.market_cap)}` : ""}
        <div>Vol {big(r.volume)}</div>
      </div>
      <div className="w-24 text-right">
        <div className="num text-sm">{price(r.price)}</div>
        <ChangePill value={r.change_pct} className="mt-0.5" />
      </div>
    </Link>
  );
}

function CollectionCard({ c, open, onToggle }: { c: Collection; open: boolean; onToggle: () => void }) {
  return (
    <Card className={cn("overflow-hidden transition-colors", open && "ring-1 ring-ai/30")}>
      <button onClick={onToggle} className="flex w-full items-center gap-3 p-4 text-left hover:bg-panel2/40">
        <span className="grid h-10 w-10 place-items-center rounded-xl bg-panel2 text-xl">{c.emoji}</span>
        <div className="min-w-0 flex-1">
          <div className="text-sm font-semibold">{c.name}</div>
          <div className="mt-1 flex -space-x-1.5">
            {c.items.slice(0, 6).map((i) => (
              <StockLogo key={i.symbol} symbol={i.symbol} className="h-5 w-5 rounded-full p-0.5 ring-2 ring-panel" />
            ))}
            {c.items.length > 6 && <span className="pl-3 text-2xs text-muted">+{c.items.length - 6}</span>}
          </div>
        </div>
        {c.avg_change_pct != null && <ChangePill value={c.avg_change_pct} />}
      </button>
      {open && (
        <div className="border-t border-line p-2">
          {c.items.map((i) => (
            <Link key={i.symbol} to={`/stocks/${i.symbol}`} className="flex items-center gap-3 rounded-lg px-3 py-2 hover:bg-panel2/60">
              <StockLogo symbol={i.symbol} className="h-7 w-7" />
              <div className="min-w-0 flex-1">
                <div className="text-sm font-medium">{i.symbol}</div>
                <div className="truncate text-2xs text-muted">{i.name}</div>
              </div>
              <LivePrice symbol={i.symbol} fallback={i.quote} className="text-sm" />
              <LiveChange symbol={i.symbol} fallback={i.quote} />
            </Link>
          ))}
        </div>
      )}
    </Card>
  );
}

export function DiscoverPage() {
  const { data, isLoading } = useDiscover();
  const { data: overview } = useOverview();
  const [tab, setTab] = useState<"gainers" | "losers" | "active">("gainers");
  const [open, setOpen] = useState<string | null>("magnificent-7");
  const rows = data?.[tab] ?? [];
  return (
    <div className="space-y-5">
      <div>
        <h1 className="flex items-center gap-2 text-xl font-semibold tracking-tight"><Compass className="h-5 w-5 text-ai" /> Discover</h1>
        <p className="text-sm text-muted">Real market movers across all US stocks, popular lists and what other traders hold.</p>
      </div>
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        {(overview?.indices ?? []).map((r) => (
          <Link key={r.symbol} to={`/stocks/${r.symbol}`}>
            <Card className="flex items-center justify-between p-4 transition-colors hover:border-faint/50">
              <div>
                <div className="text-xs text-muted">{{ SPY: "S&P 500", QQQ: "Nasdaq 100", DIA: "Dow Jones", IWM: "Russell 2000" }[r.symbol] ?? r.symbol}</div>
                <LivePrice symbol={r.symbol} fallback={r as never} className="mt-1 block text-lg font-semibold" />
              </div>
              <LiveChange symbol={r.symbol} fallback={r as never} />
            </Card>
          </Link>
        ))}
      </div>
      <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_380px]">
        <Card>
          <CardHeader
            title="Top movers"
            subtitle="All US-listed stocks · from Yahoo Finance"
            icon={tab === "losers" ? <TrendingDown className="h-4 w-4" /> : tab === "active" ? <Flame className="h-4 w-4" /> : <TrendingUp className="h-4 w-4" />}
            action={
              <Segmented
                value={tab}
                onChange={setTab}
                options={[
                  { value: "gainers", label: "Gainers" },
                  { value: "losers", label: "Losers" },
                  { value: "active", label: "Most active" },
                ]}
              />
            }
          />
          <div className="p-2">
            {isLoading && Array.from({ length: 6 }).map((_, i) => <Skeleton key={i} className="m-2 h-12" />)}
            {rows.map((r) => <MoverRow key={r.symbol} r={r} />)}
            {!isLoading && !rows.length && <Empty title="No movers right now" hint="Screeners refresh during market hours." />}
          </div>
        </Card>
        <div className="space-y-5">
          <Card>
            <CardHeader title="Popular on TradeAllN" icon={<Users className="h-4 w-4" />} subtitle="Most held by traders here" />
            <div className="p-2">
              {(data?.popular ?? []).map((p, i) => (
                <Link key={p.symbol} to={`/stocks/${p.symbol}`} className="flex items-center gap-3 rounded-lg px-3 py-2 hover:bg-panel2/60">
                  <span className="num w-4 text-xs text-faint">{i + 1}</span>
                  <StockLogo symbol={p.symbol} className="h-7 w-7" />
                  <div className="min-w-0 flex-1">
                    <div className="text-sm font-medium">{p.symbol}</div>
                    <div className="truncate text-2xs text-muted">{p.holders} trader{p.holders === 1 ? "" : "s"}</div>
                  </div>
                  <LiveChange symbol={p.symbol} />
                </Link>
              ))}
            </div>
          </Card>
        </div>
      </div>
      <div>
        <h2 className="mb-3 text-sm font-semibold">Lists</h2>
        <div className="grid items-start gap-4 md:grid-cols-2 xl:grid-cols-3">
          {(data?.collections ?? []).map((c) => (
            <CollectionCard key={c.slug} c={c} open={open === c.slug} onToggle={() => setOpen(open === c.slug ? null : c.slug)} />
          ))}
          {isLoading && [0, 1, 2].map((i) => <Skeleton key={i} className="h-20" />)}
        </div>
      </div>
      <p className="text-center text-2xs text-faint">Market data from Yahoo Finance; may be delayed. Lists are for discovery, not recommendations.</p>
    </div>
  );
}
