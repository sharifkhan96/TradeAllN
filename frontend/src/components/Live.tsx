import { useEffect, useId, useRef, useState } from "react";
import { cn } from "@/lib/cn";
import { pct, price as fmtPrice, tone } from "@/lib/format";
import type { Quote } from "@/lib/types";
import { useLive } from "@/stores/live";

/** Latest price/change for a symbol: live WebSocket value, falling back to the REST quote. */
export function useLiveQuote(symbol: string, fallback?: Partial<Pick<Quote, "price" | "change_pct" | "ext_price" | "ext_change_pct">> | null) {
  const live = useLive((s) => s.quotes[symbol]);
  return {
    price: live?.p ?? fallback?.price ?? NaN,
    change_pct: live?.c ?? fallback?.change_pct ?? NaN,
    volume: live?.v,
    ext_price: live ? live.x ?? null : fallback?.ext_price ?? null,
    ext_change_pct: live ? live.xc ?? null : fallback?.ext_change_pct ?? null,
  };
}

/** A number that flashes green/red when it changes. */
export function Flash({ value, children, className }: { value: number; children: React.ReactNode; className?: string }) {
  const prev = useRef(value);
  const [dir, setDir] = useState<"up" | "down" | null>(null);
  const [key, setKey] = useState(0);
  useEffect(() => {
    if (Number.isFinite(prev.current) && Number.isFinite(value) && value !== prev.current) {
      setDir(value > prev.current ? "up" : "down");
      setKey((k) => k + 1);
    }
    prev.current = value;
  }, [value]);
  return (
    <span key={key} className={cn("rounded px-0.5 -mx-0.5", dir === "up" && "animate-flashUp", dir === "down" && "animate-flashDown", className)}>
      {children}
    </span>
  );
}

export function LivePrice({ symbol, fallback, className }: { symbol: string; fallback?: Quote | null; className?: string }) {
  const q = useLiveQuote(symbol, fallback);
  return (
    <Flash value={q.price} className={cn("num", className)}>
      {fmtPrice(q.price)}
    </Flash>
  );
}

export function ChangePill({ value, className }: { value: number; className?: string }) {
  return (
    <span
      className={cn(
        "num inline-flex min-w-[64px] justify-end rounded-md px-1.5 py-0.5 text-xs font-medium",
        value > 0 ? "bg-up/10 text-up" : value < 0 ? "bg-down/10 text-down" : "bg-panel2 text-muted",
        className,
      )}
    >
      {pct(value)}
    </span>
  );
}

export function LiveChange({ symbol, fallback, pill = true, className }: { symbol: string; fallback?: Quote | null; pill?: boolean; className?: string }) {
  const q = useLiveQuote(symbol, fallback);
  return pill ? <ChangePill value={q.change_pct} className={className} /> : <span className={cn("num", tone(q.change_pct), className)}>{pct(q.change_pct)}</span>;
}

export function Sparkline({ data, className, positive }: { data: number[]; className?: string; positive?: boolean }) {
  const id = `sg-${useId().replace(/:/g, "")}`;
  if (data.length < 2) return <div className={className} />;
  const min = Math.min(...data);
  const max = Math.max(...data);
  const span = max - min || 1;
  const w = 100;
  const h = 32;
  const pts = data.map((v, i) => `${(i / (data.length - 1)) * w},${h - ((v - min) / span) * (h - 4) - 2}`).join(" ");
  const up = positive ?? data[data.length - 1] >= data[0];
  const color = up ? "rgb(var(--up))" : "rgb(var(--down))";
  return (
    <svg viewBox={`0 0 ${w} ${h}`} preserveAspectRatio="none" className={className}>
      <defs>
        <linearGradient id={id} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor={color} stopOpacity="0.25" />
          <stop offset="1" stopColor={color} stopOpacity="0" />
        </linearGradient>
      </defs>
      <polygon points={`0,${h} ${pts} ${w},${h}`} fill={`url(#${id})`} />
      <polyline points={pts} fill="none" stroke={color} strokeWidth="1.5" vectorEffect="non-scaling-stroke" />
    </svg>
  );
}

const failedLogos = new Set<string>();

export function StockLogo({ symbol, className }: { symbol: string; className?: string }) {
  const [failed, setFailed] = useState(failedLogos.has(symbol));
  if (!failed)
    return (
      <div className={cn("grid h-8 w-8 shrink-0 place-items-center overflow-hidden rounded-lg bg-white ring-1 ring-line", className)}>
        <img
          src={`/api/v1/logos/${encodeURIComponent(symbol)}`}
          alt=""
          loading="lazy"
          className="h-full w-full object-cover"
          onError={() => {
            failedLogos.add(symbol);
            setFailed(true);
          }}
        />
      </div>
    );
  // Fallback: deterministic monogram tile.
  let h = 0;
  for (const ch of symbol) h = (h * 31 + ch.charCodeAt(0)) % 360;
  return (
    <div
      className={cn("grid h-8 w-8 shrink-0 place-items-center rounded-lg text-2xs font-bold text-white", className)}
      style={{ background: `linear-gradient(135deg, hsl(${h} 55% 42%), hsl(${(h + 40) % 360} 60% 30%))` }}
    >
      {symbol.slice(0, 4)}
    </div>
  );
}
