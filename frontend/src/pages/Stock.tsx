import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Bell, CandlestickChart, LineChart, ScanSearch, Sparkles, Star, Workflow, X } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { toast } from "sonner";
import { PriceChart, type ChartStyle } from "@/components/chart/PriceChart";
import { ExplanationCard, NewsItem, StoryTimeline } from "@/components/explain/Explain";
import { Flash, LiveChange, StockLogo, useLiveQuote } from "@/components/Live";
import { OrderTicket } from "@/components/trading/OrderTicket";
import { Badge, Button, Card, CardHeader, Empty, Segmented, Skeleton, Spinner, Stat } from "@/components/ui";
import { api } from "@/lib/api";
import { cn } from "@/lib/cn";
import { big, countdown, money, pct, price, qty, tone } from "@/lib/format";
import { useAIStatus, useBars, useInsights, useMarketStatus, useMoves, useNews, usePositions, useStock, useWatchlists } from "@/lib/queries";
import { AnalystCard, CompanyCard, DividendsCard, EarningsCard, ExtendedLine } from "@/components/stock/Research";
import type { Explanation, Move } from "@/lib/types";
import { useLive } from "@/stores/live";
import { useUI } from "@/stores/ui";

const RANGES = ["LIVE", "1D", "5D", "1M", "6M", "1Y", "2Y"] as const;
type Range = (typeof RANGES)[number];

type RangeResult = { move: Move; segments: Move[]; ai_used: boolean; timeframe: string };

export function StockPage() {
  const { symbol = "" } = useParams();
  const sym = symbol.toUpperCase();
  const [range, setRange] = useState<Range>("1D");
  const [style, setStyle] = useState<ChartStyle>("area");
  const [selected, setSelected] = useState<Move | null>(null);
  const [selecting, setSelecting] = useState(false);
  const [rangeResult, setRangeResult] = useState<RangeResult | null>(null);
  const qc = useQueryClient();
  const { data: stock, isLoading, error: stockError } = useStock(sym);
  const { data: insights, isLoading: insightsLoading } = useInsights(sym, !!stock);
  const ready = !!stock;
  const { data: bars, isFetching: barsLoading } = useBars(sym, range, ready);
  const { data: movesData, isFetching: movesLoading } = useMoves(sym, range, ready);
  const { data: news } = useNews(sym, ready);
  const { data: positions } = usePositions();
  const { data: ai } = useAIStatus();
  const { data: market } = useMarketStatus();
  const live = useLiveQuote(sym, stock?.quote);
  const allLiveNews = useLive((s) => s.news);
  const liveNews = useMemo(
    () => allLiveNews.filter((n) => n.symbols.includes(sym) || (stock?.sector && n.sector === stock.sector) || n.kind === "macro"),
    [allLiveNews, sym, stock?.sector],
  );
  const pos = positions?.find((p) => p.symbol === sym);
  const moves = movesData?.moves ?? [];

  useEffect(() => {
    setSelected(null);
    setRangeResult(null);
    setSelecting(false);
    setStyle(["LIVE", "1D", "5D"].includes(range) ? "area" : "candles");
  }, [sym, range]);

  // default selection: the most recent move that has a news story behind it
  useEffect(() => {
    if (selected || !moves.length) return;
    const withNews = [...moves].reverse().find((m) => m.direction !== "flat" && (m.explanation?.citations.length ?? 0) > 0);
    setSelected(withNews ?? moves[moves.length - 1]);
  }, [moves, selected]);

  const deep = useMutation({
    mutationFn: (id: number) => api<Move & { ai_available: boolean }>(`/moves/${id}/deep`, { method: "POST" }),
    onSuccess: (m) => {
      setSelected((s) => (s ? { ...s, explanation: m.explanation } : s));
      qc.invalidateQueries({ queryKey: ["moves", sym, range] });
      if (m.explanation?.method !== "llm") toast("AI isn't configured, so this uses the rules engine. Set ANTHROPIC_API_KEY to enable Claude.");
    },
    onError: (e) => toast.error((e as Error).message),
  });

  const explainRange = useMutation({
    mutationFn: ({ start, end }: { start: number; end: number }) => {
      const tf = movesData?.timeframe ?? bars?.timeframe ?? "5m";
      const iso = (t: number) => new Date(t * 1000).toISOString();
      return api<RangeResult>(`/stocks/${sym}/explain?timeframe=${tf}&start=${iso(start)}&end=${iso(end + 1)}`);
    },
    onSuccess: (r) => {
      setRangeResult(r);
      setSelecting(false);
    },
    onError: (e) => toast.error((e as Error).message),
  });

  const first = bars?.bars[0];
  const rangeChange = first && Number.isFinite(live.price) ? (live.price / first.o - 1) * 100 : null;

  if (isLoading && !stock)
    return (
      <div className="grid h-[60vh] place-items-center">
        <div className="flex flex-col items-center gap-3 text-sm text-muted">
          <StockLogo symbol={sym} className="h-14 w-14 rounded-2xl" />
          <div className="flex items-center gap-2">
            <Spinner /> Loading real market data for <b className="text-fg">{sym}</b>…
          </div>
          <p className="text-xs text-faint">First visit to a ticker fetches its history, profile and news. This takes a few seconds.</p>
        </div>
      </div>
    );
  if (!stock)
    return (
      <Empty
        title={stockError ? (stockError as Error).message : `No US-listed stock called ${sym}`}
        hint="Search any US stock or ETF with ⌘K."
      />
    );

  return (
    <div className="space-y-5">
      {/* header */}
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div className="flex items-center gap-3.5">
          <StockLogo symbol={sym} className="h-12 w-12 rounded-xl text-xs" />
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-2xl font-semibold tracking-tight">{sym}</h1>
              {stock && <Badge>{stock.exchange}</Badge>}
              {stock?.sector && <Badge>{stock.sector}</Badge>}
              {stock?.is_etf && <Badge tone="accent">ETF</Badge>}
            </div>
            <div className="text-sm text-muted">{stock?.name ?? <Skeleton className="h-4 w-40" />}</div>
          </div>
        </div>
        <div className="flex items-end gap-5">
          <div className="text-right">
            <div className="text-3xl font-semibold tracking-tight">
              <Flash value={live.price} className="num">${price(live.price)}</Flash>
            </div>
            <div className="mt-1 flex items-center justify-end gap-2 text-sm">
              <LiveChange symbol={sym} fallback={stock?.quote} />
              <span className="text-xs text-muted">today</span>
              {rangeChange != null && range !== "1D" && range !== "LIVE" && (
                <span className={cn("num text-xs", tone(rangeChange))}>
                  {pct(rangeChange)} <span className="text-muted">{range}</span>
                </span>
              )}
            </div>
            <ExtendedLine symbol={sym} fallback={stock?.quote} />
          </div>
          <div className="flex gap-2">
            <WatchToggle symbol={sym} />
            <Button size="sm" onClick={() => useUI.getState().openPalette(`alert me when ${sym} goes above ${Math.ceil(live.price * 1.05)}`)}>
              <Bell className="h-3.5 w-3.5" /> Alert
            </Button>
            <Button size="sm" variant="ai" onClick={() => useUI.getState().openPalette(`if ${sym} drops 5% today buy $1000`)}>
              <Workflow className="h-3.5 w-3.5" /> Automate
            </Button>
          </div>
        </div>
      </div>

      <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_340px]">
        <div className="min-w-0 space-y-5">
          {/* chart */}
          <Card className="overflow-hidden">
            <div className="flex flex-wrap items-center justify-between gap-2 border-b border-line px-3 py-2.5">
              <Segmented
                value={range}
                onChange={setRange}
                options={RANGES.map((r) => ({
                  value: r,
                  label: r === "LIVE" ? <span className="flex items-center gap-1.5"><span className="h-1.5 w-1.5 animate-pulseDot rounded-full bg-down" />Live</span> : r,
                }))}
              />
              <div className="flex items-center gap-2">
                {(barsLoading || movesLoading) && <Spinner />}
                <Button
                  size="sm"
                  variant={selecting ? "ai" : "secondary"}
                  onClick={() => {
                    setSelecting((v) => !v);
                    setRangeResult(null);
                  }}
                  title="Drag across the chart to explain any period"
                >
                  <ScanSearch className="h-3.5 w-3.5" /> {selecting ? "Selecting…" : "Explain a range"}
                </Button>
                <Segmented
                  value={style}
                  onChange={setStyle}
                  options={[
                    { value: "area", label: <LineChart className="h-3.5 w-3.5" /> },
                    { value: "candles", label: <CandlestickChart className="h-3.5 w-3.5" /> },
                  ]}
                />
              </div>
            </div>
            {bars && bars.bars.length > 1 ? (
              <PriceChart
                className="h-[420px]"
                bars={bars.bars}
                timeframe={bars.timeframe}
                symbol={sym}
                style={style}
                live={range === "LIVE" || range === "1D"}
                moves={rangeResult ? [] : moves}
                selectedMove={rangeResult ? null : selected}
                onSelectMove={(m) => {
                  setSelected(m);
                  setRangeResult(null);
                }}
                selecting={selecting}
                onSelectRange={(a, b) => explainRange.mutate({ start: a, end: b })}
                highlight={rangeResult ? { start_t: rangeResult.move.start_t, end_t: rangeResult.move.end_t } : null}
              />
            ) : (
              <div className="grid h-[420px] place-items-center">
                {range === "LIVE" ? (
                  <p className="max-w-sm text-center text-sm text-muted">
                    {market && market.status !== "open"
                      ? `The market is closed. The live second-by-second view resumes when it opens${market.opens_at ? ` (${countdown(market.opens_at)})` : ""}.`
                      : "Collecting live ticks…"}
                  </p>
                ) : (
                  <Spinner className="h-6 w-6" />
                )}
              </div>
            )}
            <div className="flex items-center gap-4 border-t border-line px-4 py-2 text-2xs text-muted">
              <span className="flex items-center gap-1.5"><span className="h-2 w-2 rounded-full bg-up" /> news-driven rise</span>
              <span className="flex items-center gap-1.5"><span className="h-2 w-2 rounded-full bg-down" /> news-driven fall</span>
              <span className="hidden sm:inline">Click any part of the chart to see why it moved · times in ET</span>
              {market && <span className="ml-auto hidden md:inline">{market.source}</span>}
            </div>
          </Card>

          {/* why */}
          <Card className="ai-border p-5">
            <div className="mb-3 flex items-center gap-2">
              <Sparkles className="h-4 w-4 text-ai" />
              <h3 className="text-sm font-semibold">Why did it move?</h3>
              {rangeResult && (
                <button onClick={() => setRangeResult(null)} className="ml-auto flex items-center gap-1 text-xs text-muted hover:text-fg">
                  <X className="h-3 w-3" /> Clear range
                </button>
              )}
            </div>
            {explainRange.isPending ? (
              <div className="flex items-center gap-2 py-6 text-sm text-muted"><Spinner className="text-ai" /> Explaining the selected range…</div>
            ) : rangeResult ? (
              <div className="space-y-4">
                <ExplanationCard move={rangeResult.move} explanation={rangeResult.move.explanation} title="Selected range" />
                {rangeResult.segments.length > 1 && (
                  <div>
                    <div className="label mb-2">Inside this range</div>
                    <StoryTimeline moves={rangeResult.segments} selected={null} onSelect={(m) => setRangeResult({ ...rangeResult, move: m })} />
                  </div>
                )}
              </div>
            ) : selected ? (
              <ExplanationCard
                move={selected}
                explanation={selected.explanation as Explanation | null}
                aiAvailable={ai?.ai_enabled}
                onDeep={selected.id ? () => deep.mutate(selected.id!) : undefined}
                deepLoading={deep.isPending}
              />
            ) : (
              <p className="py-4 text-sm text-muted">Select a part of the chart.</p>
            )}
          </Card>

          <div className="grid gap-5 lg:grid-cols-2">
            <AnalystCard data={insights} loading={insightsLoading} />
            <EarningsCard data={insights} loading={insightsLoading} />
          </div>

          <div className="grid gap-5 lg:grid-cols-2">
            <Card>
              <CardHeader title={`The story · ${range}`} subtitle={`${moves.length} moves detected`} />
              <div className="max-h-[420px] overflow-y-auto p-3">
                {moves.length ? (
                  <StoryTimeline moves={moves} selected={selected} onSelect={(m) => { setSelected(m); setRangeResult(null); }} />
                ) : (
                  <Empty title="No moves yet" />
                )}
              </div>
            </Card>
            <Card>
              <CardHeader title="News" subtitle="Company, sector and macro" />
              <div className="max-h-[420px] divide-y divide-line overflow-y-auto px-5 pb-2">
                {[...liveNews, ...(news ?? [])].slice(0, 25).map((a) => <NewsItem key={a.id} a={a} />)}
                {!news?.length && <Empty title="No news" />}
              </div>
            </Card>
          </div>
        </div>

        {/* right column */}
        <div className="space-y-5">
          <OrderTicket symbol={sym} quote={stock?.quote} />
          {pos && (
            <Card className="p-4">
              <div className="label mb-3">Your position</div>
              <div className="grid grid-cols-2 gap-4">
                <Stat label="Shares" value={qty(pos.quantity)} />
                <Stat label="Market value" value={money(pos.market_value)} />
                <Stat label="Avg cost" value={money(pos.avg_cost)} />
                <Stat label="Portfolio weight" value={`${pos.weight.toFixed(1)}%`} />
                <Stat label="Today" value={<span className={tone(pos.day_pnl)}>{money(pos.day_pnl, { sign: true })}</span>} />
                <Stat label="Total return" value={<span className={tone(pos.unrealized_pnl)}>{money(pos.unrealized_pnl, { sign: true })}</span>} sub={<span className={tone(pos.unrealized_pct)}>{pct(pos.unrealized_pct)}</span>} />
              </div>
            </Card>
          )}
          <Card className="p-4">
            <div className="label mb-3">Key stats</div>
            {stock ? (
              <div className="grid grid-cols-2 gap-x-4 gap-y-3.5">
                <Stat label="Open" value={price(stock.quote?.open)} />
                <Stat label="Prev close" value={price(stock.quote?.prev_close)} />
                <Stat label="Day range" value={<span className="text-sm">{price(stock.quote?.low)} – {price(stock.quote?.high)}</span>} />
                <Stat label="52-wk range" value={<span className="text-sm">{price(stock.stats.week52_low)} – {price(stock.stats.week52_high)}</span>} />
                <Stat label="Market cap" value={stock.market_cap ? `$${big(stock.market_cap)}` : "—"} />
                <Stat label="P/E" value={stock.pe_ratio ?? "—"} />
                <Stat label="Avg volume" value={big(stock.stats.avg_volume)} />
                <Stat label="Beta" value={Number(stock.beta).toFixed(2)} />
              </div>
            ) : (
              <Skeleton className="h-40" />
            )}
          </Card>
          {stock && <CompanyCard stock={stock} data={insights} />}
          {stock && <DividendsCard stock={stock} data={insights} />}
          {stock && stock.peers && stock.peers.length > 0 && (
            <Card className="p-4">
              {(
                <>
                  <div className="label mb-2">People also own</div>
                  <div className="space-y-1">
                    {stock.peers.map((p) => (
                      <Link key={p.symbol} to={`/stocks/${p.symbol}`} className="flex items-center gap-2.5 rounded-lg px-1.5 py-1.5 hover:bg-panel2">
                        <StockLogo symbol={p.symbol} className="h-7 w-7" />
                        <span className="text-sm font-medium">{p.symbol}</span>
                        <span className="flex-1 truncate text-xs text-muted">{p.name}</span>
                        <LiveChange symbol={p.symbol} fallback={p.quote} />
                      </Link>
                    ))}
                  </div>
                </>
              )}
            </Card>
          )}
          <Upcoming symbol={sym} />
        </div>
      </div>
    </div>
  );
}

function WatchToggle({ symbol }: { symbol: string }) {
  const { data: wls } = useWatchlists();
  const qc = useQueryClient();
  const wl = wls?.[0];
  const on = !!wl?.items.some((i) => i.symbol === symbol);
  const toggle = async () => {
    if (!wl) return;
    if (on) await api(`/watchlists/${wl.id}/items/${symbol}`, { method: "DELETE" });
    else await api(`/watchlists/${wl.id}/items`, { json: { symbol } });
    qc.invalidateQueries({ queryKey: ["watchlists"] });
    toast(on ? `Removed ${symbol} from ${wl.name}` : `Added ${symbol} to ${wl.name}`);
  };
  return (
    <Button size="sm" onClick={toggle} title={on ? "Remove from watchlist" : "Add to watchlist"}>
      <Star className={cn("h-3.5 w-3.5", on && "fill-warn text-warn")} /> {on ? "Watching" : "Watch"}
    </Button>
  );
}

function Upcoming({ symbol }: { symbol: string }) {
  const { data } = useQuery({
    queryKey: ["calendar", symbol],
    queryFn: () => api<{ id: number; symbol: string | null; kind: string; ts: string; title: string; payload: { upcoming?: boolean } }[]>(`/calendar?symbol=${symbol}`),
    staleTime: 60000,
  });
  const { data: past } = useQuery({
    queryKey: ["earnings-history", symbol],
    queryFn: () => api<{ headline: string; published_at: string; kind: string }[]>(`/news?symbol=${symbol}&limit=100`),
    staleTime: 60000,
  });
  const events = useMemo(() => (data ?? []).filter((e) => e.payload?.upcoming).slice(0, 4), [data]);
  const earningsCount = (past ?? []).filter((n) => n.kind === "earnings").length;
  if (!events.length) return null;
  return (
    <Card className="p-4">
      <div className="label mb-3">Upcoming catalysts</div>
      <div className="space-y-2.5">
        {events.map((e) => (
          <div key={e.id} className="flex items-center gap-3">
            <div className="w-12 shrink-0 rounded-lg border border-line bg-panel2 py-1 text-center">
              <div className="text-[10px] uppercase text-muted">{new Date(e.ts).toLocaleDateString("en-US", { month: "short" })}</div>
              <div className="num text-sm font-semibold">{new Date(e.ts).getDate()}</div>
            </div>
            <div className="min-w-0">
              <div className="truncate text-sm">{e.title}</div>
              <div className="text-2xs text-muted">{e.symbol ? "Company event" : "Market-wide"}</div>
            </div>
          </div>
        ))}
      </div>
      {earningsCount > 0 && <p className="mt-3 text-2xs text-faint">{earningsCount} past earnings reports are in the news history.</p>}
    </Card>
  );
}

