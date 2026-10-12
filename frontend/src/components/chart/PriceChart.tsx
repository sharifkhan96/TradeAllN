import {
  ColorType, CrosshairMode, createChart, type IChartApi, type ISeriesApi, type SeriesMarker, type Time, type UTCTimestamp,
} from "lightweight-charts";
import { useEffect, useMemo, useRef, useState } from "react";
import { cn } from "@/lib/cn";
import type { Bar, Move } from "@/lib/types";
import { onLive } from "@/stores/live";
import { useUI } from "@/stores/ui";

// The chart library renders UTC; shift timestamps so axes read in US Eastern time.
const etOffsetCache = new Map<number, number>();
function etOffset(t: number) {
  const hour = Math.floor(t / 3600);
  let o = etOffsetCache.get(hour);
  if (o === undefined) {
    const d = new Date(t * 1000);
    const et = new Date(d.toLocaleString("en-US", { timeZone: "America/New_York" }));
    const utc = new Date(d.toLocaleString("en-US", { timeZone: "UTC" }));
    o = Math.round((et.getTime() - utc.getTime()) / 1000);
    etOffsetCache.set(hour, o);
  }
  return o;
}
const toChart = (t: number) => (t + etOffset(t)) as UTCTimestamp;
const fromChart = (t: number) => t - etOffset(t);

function cssColor(name: string, alpha = 1) {
  const raw = getComputedStyle(document.documentElement).getPropertyValue(`--${name}`).trim();
  const [r, g, b] = raw.split(/\s+/).map(Number);
  return alpha === 1 ? `rgb(${r}, ${g}, ${b})` : `rgba(${r}, ${g}, ${b}, ${alpha})`;
}

export type ChartStyle = "area" | "candles";

type Props = {
  bars: Bar[];
  timeframe: string;
  symbol: string;
  style: ChartStyle;
  live?: boolean;
  moves?: Move[];
  selectedMove?: Move | null;
  onSelectMove?: (m: Move) => void;
  selecting?: boolean;
  onSelectRange?: (startT: number, endT: number) => void;
  highlight?: { start_t: number; end_t: number } | null;
  className?: string;
};

export function PriceChart({
  bars, timeframe, symbol, style, live, moves = [], selectedMove, onSelectMove, selecting, onSelectRange, highlight, className,
}: Props) {
  const wrap = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const seriesRef = useRef<ISeriesApi<"Candlestick"> | ISeriesApi<"Area"> | null>(null);
  const volRef = useRef<ISeriesApi<"Histogram"> | null>(null);
  const lastBar = useRef<Bar | null>(null);
  const theme = useUI((s) => s.theme);
  const [overlay, setOverlay] = useState<{ left: number; width: number; tone: string } | null>(null);
  const [drag, setDrag] = useState<{ x0: number; x1: number } | null>(null);
  const movesRef = useRef(moves);
  movesRef.current = moves;
  const onSelectRef = useRef(onSelectMove);
  onSelectRef.current = onSelectMove;

  // create chart once per style/theme
  useEffect(() => {
    if (!wrap.current) return;
    const chart = createChart(wrap.current, {
      autoSize: true,
      layout: {
        background: { type: ColorType.Solid, color: "transparent" },
        textColor: cssColor("muted"),
        fontFamily: "JetBrains Mono, ui-monospace, monospace",
        fontSize: 11,
      },
      grid: { vertLines: { color: cssColor("line", 0.35) }, horzLines: { color: cssColor("line", 0.35) } },
      rightPriceScale: { borderColor: cssColor("line"), scaleMargins: { top: 0.1, bottom: 0.22 } },
      timeScale: { borderColor: cssColor("line"), timeVisible: true, secondsVisible: timeframe === "1s", rightOffset: 4 },
      crosshair: {
        mode: CrosshairMode.Normal,
        vertLine: { color: cssColor("faint"), labelBackgroundColor: cssColor("panel-2") },
        horzLine: { color: cssColor("faint"), labelBackgroundColor: cssColor("panel-2") },
      },
      handleScale: { axisPressedMouseMove: true },
    });
    const up = cssColor("up");
    const down = cssColor("down");
    const series =
      style === "candles"
        ? chart.addCandlestickSeries({ upColor: up, downColor: down, wickUpColor: up, wickDownColor: down, borderVisible: false })
        : chart.addAreaSeries({
            lineColor: cssColor("accent"),
            topColor: cssColor("accent", 0.28),
            bottomColor: cssColor("accent", 0.0),
            lineWidth: 2,
            priceLineVisible: true,
          });
    const vol = chart.addHistogramSeries({ priceFormat: { type: "volume" }, priceScaleId: "vol", lastValueVisible: false, priceLineVisible: false });
    chart.priceScale("vol").applyOptions({ scaleMargins: { top: 0.84, bottom: 0 } });
    chart.subscribeClick((p) => {
      if (!p.time || !onSelectRef.current) return;
      const t = fromChart(p.time as number);
      const hit = movesRef.current.find((m) => t >= m.start_t && t <= m.end_t);
      if (hit) onSelectRef.current(hit);
    });
    chartRef.current = chart;
    seriesRef.current = series;
    volRef.current = vol;
    return () => {
      chart.remove();
      chartRef.current = null;
      seriesRef.current = null;
      volRef.current = null;
    };
  }, [style, theme, timeframe]);

  // data
  useEffect(() => {
    const s = seriesRef.current;
    const v = volRef.current;
    if (!s || !v) return;
    const up = cssColor("up", 0.35);
    const down = cssColor("down", 0.35);
    if (style === "candles") {
      (s as ISeriesApi<"Candlestick">).setData(bars.map((b) => ({ time: toChart(b.t), open: b.o, high: b.h, low: b.l, close: b.c })));
    } else {
      (s as ISeriesApi<"Area">).setData(bars.map((b) => ({ time: toChart(b.t), value: b.c })));
    }
    v.setData(bars.map((b) => ({ time: toChart(b.t), value: b.v, color: b.c >= b.o ? up : down })));
    lastBar.current = bars.length ? { ...bars[bars.length - 1] } : null;
    chartRef.current?.timeScale().fitContent();
  }, [bars, style, theme, timeframe]);

  // live updates: extend the last bar (or open a new one) from the quote stream
  useEffect(() => {
    if (!live) return;
    const bucket = timeframe === "1s" ? 1 : timeframe === "1m" ? 60 : timeframe === "5m" ? 300 : timeframe === "1h" ? 3600 : 0;
    if (!bucket) return;
    return onLive((msg) => {
      if (msg.type !== "quotes") return;
      const q = (msg.q as Record<string, [number, number, number]>)[symbol];
      const s = seriesRef.current;
      if (!q || !s) return;
      const t = msg.t as number;
      const price = q[0];
      const bt = t - (t % bucket);
      let b = lastBar.current;
      if (!b || bt > b.t) b = { t: bt, o: b?.c ?? price, h: price, l: price, c: price, v: 0 };
      else if (bt < b.t) return;
      b = { ...b, h: Math.max(b.h, price), l: Math.min(b.l, price), c: price };
      lastBar.current = b;
      if (style === "candles") (s as ISeriesApi<"Candlestick">).update({ time: toChart(b.t), open: b.o, high: b.h, low: b.l, close: b.c });
      else (s as ISeriesApi<"Area">).update({ time: toChart(b.t), value: b.c });
    });
  }, [live, symbol, timeframe, style]);

  // move markers
  const markers = useMemo<SeriesMarker<Time>[]>(() => {
    if (!bars.length) return [];
    const times = bars.map((b) => b.t);
    const snap = (t: number) => {
      let lo = 0;
      let hi = times.length - 1;
      while (lo < hi) {
        const mid = (lo + hi + 1) >> 1;
        if (times[mid] <= t) lo = mid;
        else hi = mid - 1;
      }
      return times[lo];
    };
    return moves
      .filter((m) => m.direction !== "flat" && m.explanation && m.explanation.category !== "no_clear_catalyst" && m.explanation.category !== "quiet")
      .map((m) => {
        const isSel = selectedMove && selectedMove.start_t === m.start_t && selectedMove.end_t === m.end_t;
        const news = (m.explanation?.citations.length ?? 0) > 0;
        return {
          time: toChart(snap(m.end_t)),
          position: m.direction === "up" ? "aboveBar" : "belowBar",
          color: isSel ? cssColor("ai") : m.direction === "up" ? cssColor("up") : cssColor("down"),
          shape: news ? "circle" : m.direction === "up" ? "arrowDown" : "arrowUp",
          size: isSel ? 1.6 : 1,
          text: news ? `${m.pct_change > 0 ? "+" : ""}${m.pct_change.toFixed(1)}%` : "",
        } as SeriesMarker<Time>;
      })
      .sort((a, b) => (a.time as number) - (b.time as number));
  }, [moves, bars, selectedMove]);

  useEffect(() => {
    seriesRef.current?.setMarkers(markers);
  }, [markers, style, theme, timeframe]);

  // highlight band for the selected move / explained range
  const band = highlight ?? (selectedMove ? { start_t: selectedMove.start_t, end_t: selectedMove.end_t } : null);
  useEffect(() => {
    const chart = chartRef.current;
    if (!chart || !band) {
      setOverlay(null);
      return;
    }
    const update = () => {
      const ts = chart.timeScale();
      const a = ts.timeToCoordinate(toChart(snapTo(bars, band.start_t)));
      const b = ts.timeToCoordinate(toChart(snapTo(bars, band.end_t)));
      if (a == null || b == null) return setOverlay(null);
      const tone = selectedMove?.direction === "down" ? "down" : selectedMove?.direction === "up" ? "up" : "ai";
      setOverlay({ left: Math.min(a, b), width: Math.max(2, Math.abs(b - a)), tone });
    };
    update();
    chart.timeScale().subscribeVisibleLogicalRangeChange(update);
    return () => chart.timeScale().unsubscribeVisibleLogicalRangeChange(update);
  }, [band?.start_t, band?.end_t, bars, style, theme, timeframe, selectedMove]);

  // drag-to-explain
  const onPointerDown = (e: React.PointerEvent) => {
    if (!selecting) return;
    const x = e.clientX - (wrap.current?.getBoundingClientRect().left ?? 0);
    (e.target as HTMLElement).setPointerCapture(e.pointerId);
    setDrag({ x0: x, x1: x });
  };
  const onPointerMove = (e: React.PointerEvent) => {
    if (!drag) return;
    const x = e.clientX - (wrap.current?.getBoundingClientRect().left ?? 0);
    setDrag({ ...drag, x1: x });
  };
  const onPointerUp = () => {
    if (!drag || !chartRef.current) return;
    const ts = chartRef.current.timeScale();
    const [a, b] = [Math.min(drag.x0, drag.x1), Math.max(drag.x0, drag.x1)];
    setDrag(null);
    if (b - a < 8) return;
    const t0 = ts.coordinateToTime(a);
    const t1 = ts.coordinateToTime(b);
    if (t0 && t1) onSelectRange?.(fromChart(t0 as number), fromChart(t1 as number));
  };

  return (
    <div className={cn("relative", className)}>
      <div ref={wrap} className="absolute inset-0" />
      {overlay && (
        <div
          className={cn(
            "pointer-events-none absolute bottom-6 top-0 border-x",
            overlay.tone === "up" && "border-up/40 bg-up/[0.07]",
            overlay.tone === "down" && "border-down/40 bg-down/[0.07]",
            overlay.tone === "ai" && "border-ai/50 bg-ai/[0.08]",
          )}
          style={{ left: overlay.left, width: overlay.width }}
        />
      )}
      {selecting && (
        <div
          className="absolute inset-0 bottom-6 cursor-crosshair"
          onPointerDown={onPointerDown}
          onPointerMove={onPointerMove}
          onPointerUp={onPointerUp}
        >
          {drag && (
            <div
              className="absolute bottom-0 top-0 border-x border-ai/70 bg-ai/15"
              style={{ left: Math.min(drag.x0, drag.x1), width: Math.abs(drag.x1 - drag.x0) }}
            />
          )}
          {!drag && (
            <div className="pointer-events-none absolute left-1/2 top-3 -translate-x-1/2 rounded-full border border-ai/40 bg-panel/90 px-3 py-1 text-xs text-ai shadow-pop">
              Drag across the chart to explain that range
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function snapTo(bars: Bar[], t: number) {
  if (!bars.length) return t;
  let best = bars[0].t;
  for (const b of bars) {
    if (b.t <= t) best = b.t;
    else break;
  }
  return best;
}
