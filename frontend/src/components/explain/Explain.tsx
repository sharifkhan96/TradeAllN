import { BarChart2, Building2, FileText, Globe2, Landmark, Megaphone, MinusCircle, Newspaper, Sparkles, TrendingDown, TrendingUp, Users } from "lucide-react";
import type { ReactNode } from "react";
import { Badge, Button } from "@/components/ui";
import { cn } from "@/lib/cn";
import { etTime, pct, timeAgo } from "@/lib/format";
import type { Explanation, Move, News } from "@/lib/types";

export const CATEGORY: Record<string, { label: string; icon: ReactNode }> = {
  company_news: { label: "Company news", icon: <Building2 className="h-3 w-3" /> },
  earnings: { label: "Earnings", icon: <BarChart2 className="h-3 w-3" /> },
  analyst: { label: "Analyst action", icon: <Users className="h-3 w-3" /> },
  filing: { label: "SEC filing", icon: <FileText className="h-3 w-3" /> },
  sector: { label: "Sector move", icon: <Megaphone className="h-3 w-3" /> },
  market_wide: { label: "Market-wide", icon: <Globe2 className="h-3 w-3" /> },
  macro: { label: "Macro data", icon: <Landmark className="h-3 w-3" /> },
  no_clear_catalyst: { label: "No clear catalyst", icon: <MinusCircle className="h-3 w-3" /> },
  quiet: { label: "Quiet", icon: <MinusCircle className="h-3 w-3" /> },
};

export function NewsItem({ a, compact }: { a: News; compact?: boolean }) {
  const tone = a.sentiment > 0.15 ? "up" : a.sentiment < -0.15 ? "down" : "neutral";
  return (
    <div className={cn("group flex gap-3", compact ? "py-2" : "py-3")}>
      <div className={cn("mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full", tone === "up" ? "bg-up" : tone === "down" ? "bg-down" : "bg-faint")} />
      <div className="min-w-0 flex-1">
        {a.url ? (
          <a
            href={a.url}
            target="_blank"
            rel="noopener noreferrer"
            className={cn("leading-snug text-fg/90 decoration-faint underline-offset-2 hover:text-fg hover:underline", compact ? "text-xs" : "text-sm")}
          >
            {a.headline}
          </a>
        ) : (
          <p className={cn("leading-snug text-fg/90", compact ? "text-xs" : "text-sm")}>{a.headline}</p>
        )}
        <div className="mt-1 flex flex-wrap items-center gap-x-2 gap-y-1 text-2xs text-muted">
          <span>{a.source}</span>
          <span>·</span>
          <span title={etTime(a.published_at)}>{timeAgo(a.published_at)}</span>
          {a.symbols.slice(0, 3).map((s) => (
            <span key={s} className="rounded bg-panel2 px-1 font-mono text-[10px] text-fg/70">{s}</span>
          ))}
          {a.kind !== "news" && <span className="capitalize text-faint">{a.kind.replace("_", " ")}</span>}
          {a.is_simulated && <span className="text-faint">· simulated</span>}
        </div>
      </div>
    </div>
  );
}

export function ExplanationCard({
  move, explanation, onDeep, deepLoading, aiAvailable, title,
}: {
  move: Pick<Move, "direction" | "pct_change" | "start_t" | "end_t" | "market_pct" | "sector_pct" | "residual_pct" | "volume_ratio">;
  explanation: Explanation | null;
  onDeep?: () => void;
  deepLoading?: boolean;
  aiAvailable?: boolean;
  title?: string;
}) {
  const cat = explanation ? CATEGORY[explanation.category] ?? CATEGORY.no_clear_catalyst : null;
  const Icon = move.direction === "up" ? TrendingUp : move.direction === "down" ? TrendingDown : MinusCircle;
  return (
    <div className="animate-fadeIn">
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-center gap-2.5">
          <div className={cn("grid h-8 w-8 place-items-center rounded-lg", move.direction === "up" ? "bg-up/10 text-up" : move.direction === "down" ? "bg-down/10 text-down" : "bg-panel2 text-muted")}>
            <Icon className="h-4 w-4" />
          </div>
          <div>
            <div className="text-sm font-semibold">
              {title ?? (move.direction === "flat" ? "Held steady" : move.direction === "up" ? "Went up" : "Went down")}{" "}
              <span className={cn("num", move.pct_change > 0 ? "text-up" : move.pct_change < 0 ? "text-down" : "text-muted")}>{pct(move.pct_change)}</span>
            </div>
            <div className="text-2xs text-muted">
              {etTime(move.start_t)} → {etTime(move.end_t)} ET
            </div>
          </div>
        </div>
        {explanation && (
          <div className="flex flex-col items-end gap-1">
            <Badge tone="ai">{cat?.icon} {cat?.label}</Badge>
            <span className="text-2xs text-muted">{explanation.confidence} confidence</span>
          </div>
        )}
      </div>

      {explanation ? (
        <p className="mt-3 text-sm leading-relaxed text-fg/90">{explanation.summary}</p>
      ) : (
        <p className="mt-3 text-sm text-muted">No explanation yet.</p>
      )}

      <div className="mt-3 grid grid-cols-3 gap-2">
        <Mini label="Market (SPY)" value={move.market_pct} />
        <Mini label="Sector" value={move.sector_pct} />
        <Mini label="Stock-specific" value={move.residual_pct} />
      </div>

      {explanation && explanation.citations.length > 0 && (
        <div className="mt-3">
          <div className="label mb-1 flex items-center gap-1.5"><Newspaper className="h-3 w-3" /> Sources</div>
          <div className="divide-y divide-line">
            {explanation.citations.map((c) => (
              <div key={c.article.id} className="relative">
                {c.relevance === "primary" && <span className="absolute -left-2 top-3 h-4 w-0.5 rounded bg-ai" />}
                <NewsItem a={c.article} compact />
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="mt-3 flex items-center justify-between gap-2 border-t border-line pt-3">
        <span className="text-2xs text-faint">
          {explanation?.method === "llm" ? `Written by ${explanation.model || "Claude"} from timed news` : "Matched from news timing and market moves"} · not a guaranteed cause
        </span>
        {onDeep && explanation?.method !== "llm" && (
          <Button size="sm" variant="ai" onClick={onDeep} loading={deepLoading} disabled={aiAvailable === false} title={aiAvailable === false ? "Set ANTHROPIC_API_KEY to enable" : undefined}>
            <Sparkles className="h-3.5 w-3.5" /> Deeper AI analysis
          </Button>
        )}
      </div>
    </div>
  );
}

function Mini({ label, value }: { label: string; value: number | null }) {
  return (
    <div className="rounded-lg bg-panel2/60 px-2.5 py-2">
      <div className="text-2xs text-muted">{label}</div>
      <div className={cn("num text-sm font-medium", value == null ? "text-faint" : value > 0 ? "text-up" : value < 0 ? "text-down" : "text-muted")}>
        {value == null ? "—" : pct(value)}
      </div>
    </div>
  );
}

export function StoryTimeline({ moves, selected, onSelect }: { moves: Move[]; selected: Move | null; onSelect: (m: Move) => void }) {
  return (
    <ol className="relative space-y-1 before:absolute before:bottom-3 before:left-[11px] before:top-3 before:w-px before:bg-line">
      {[...moves].reverse().map((m) => {
        const isSel = selected?.start_t === m.start_t && selected?.end_t === m.end_t;
        const cat = m.explanation ? CATEGORY[m.explanation.category] : null;
        return (
          <li key={`${m.start_t}-${m.end_t}`}>
            <button
              onClick={() => onSelect(m)}
              className={cn("relative flex w-full gap-3 rounded-lg p-2 text-left transition-colors", isSel ? "bg-ai/10 ring-1 ring-ai/30" : "hover:bg-panel2/70")}
            >
              <span
                className={cn(
                  "relative z-10 mt-0.5 grid h-[22px] w-[22px] shrink-0 place-items-center rounded-full border-2 border-panel text-white",
                  m.direction === "up" ? "bg-up" : m.direction === "down" ? "bg-down" : "bg-faint",
                )}
              >
                {m.direction === "up" ? <TrendingUp className="h-3 w-3" /> : m.direction === "down" ? <TrendingDown className="h-3 w-3" /> : <MinusCircle className="h-3 w-3" />}
              </span>
              <span className="min-w-0 flex-1">
                <span className="flex items-center justify-between gap-2">
                  <span className="text-2xs text-muted">{etTime(m.start_t)}</span>
                  <span className={cn("num text-xs font-semibold", m.pct_change > 0 ? "text-up" : m.pct_change < 0 ? "text-down" : "text-muted")}>{pct(m.pct_change)}</span>
                </span>
                <span className="mt-0.5 line-clamp-2 block text-xs leading-snug text-fg/85">{m.explanation?.summary ?? "…"}</span>
                {cat && m.explanation && m.explanation.citations.length > 0 && (
                  <span className="mt-1 inline-flex items-center gap-1 text-2xs text-ai">{cat.icon} {cat.label}</span>
                )}
              </span>
            </button>
          </li>
        );
      })}
    </ol>
  );
}
