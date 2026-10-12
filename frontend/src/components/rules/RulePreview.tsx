import { AlertTriangle, CheckCircle2, Clock, Zap } from "lucide-react";
import { Line, LineChart, ReferenceDot, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { Badge } from "@/components/ui";
import { cn } from "@/lib/cn";
import { money, pct, shortDate } from "@/lib/format";
import type { Backtest, Readable } from "@/lib/types";

function When({ node, depth = 0 }: { node: Readable["when"]; depth?: number }) {
  const joiner = node.logic === "any" ? "OR" : node.logic === "not" ? "NOT" : "AND";
  return (
    <div className={cn("space-y-1.5", depth > 0 && "rounded-lg border border-dashed border-line p-2")}>
      {node.items.map((it, i) => (
        <div key={i} className="flex items-start gap-2">
          {i > 0 || node.logic === "not" ? (
            <span className="mt-0.5 w-9 shrink-0 text-right font-mono text-2xs font-semibold text-ai">{joiner}</span>
          ) : (
            <span className="w-9 shrink-0" />
          )}
          {typeof it === "string" ? (
            <span className="rounded-md border border-line bg-panel2 px-2 py-1 text-xs text-fg/90">{it}</span>
          ) : (
            <When node={it} depth={depth + 1} />
          )}
        </div>
      ))}
    </div>
  );
}

export function ReadableRule({ readable, compact }: { readable: Readable; compact?: boolean }) {
  return (
    <div className={cn("space-y-3", compact && "space-y-2")}>
      <div>
        <div className="label mb-1.5 flex items-center gap-1.5">
          <Clock className="h-3 w-3" /> When
        </div>
        <When node={readable.when} />
      </div>
      <div>
        <div className="label mb-1.5 flex items-center gap-1.5">
          <Zap className="h-3 w-3" /> Then
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <span className="rounded-md border border-ai/30 bg-ai/10 px-2 py-1 text-xs font-medium text-ai">{readable.then}</span>
          <span className="text-2xs text-muted">{readable.mode}</span>
        </div>
      </div>
    </div>
  );
}

export function BacktestView({ bt }: { bt: Backtest }) {
  if (!bt.supported) return <p className="text-xs text-muted">{bt.note}</p>;
  const series = bt.series ?? [];
  const triggers = bt.triggers;
  return (
    <div>
      <div className="mb-2 flex items-center justify-between">
        <div className="label">Would have triggered (last {bt.days} sessions)</div>
        <Badge tone={triggers.length ? "ai" : "neutral"}>{triggers.length} time{triggers.length === 1 ? "" : "s"}</Badge>
      </div>
      {series.length > 1 && (
        <div className="h-28">
          <ResponsiveContainer>
            <LineChart data={series} margin={{ top: 6, right: 6, bottom: 0, left: 0 }}>
              <XAxis dataKey="date" hide />
              <YAxis domain={["auto", "auto"]} hide />
              <Tooltip
                contentStyle={{ background: "rgb(var(--panel))", border: "1px solid rgb(var(--line))", borderRadius: 8, fontSize: 12 }}
                labelFormatter={(d) => shortDate(String(d))}
                formatter={(v: number) => [money(v), bt.symbol]}
              />
              <Line type="monotone" dataKey="close" stroke="rgb(var(--accent))" strokeWidth={1.5} dot={false} isAnimationActive={false} />
              {triggers.map((t) => (
                <ReferenceDot key={t.date} x={t.date} y={t.price} r={4} fill="rgb(var(--ai))" stroke="rgb(var(--panel))" strokeWidth={2} />
              ))}
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}
      {triggers.length > 0 && (
        <div className="mt-2 flex flex-wrap gap-1.5">
          {triggers.slice(-6).map((t) => (
            <span key={t.date} className="num rounded-md bg-panel2 px-1.5 py-0.5 text-2xs text-muted">
              {shortDate(t.date)} · {money(t.price)} · <span className={t.return_since_pct >= 0 ? "text-up" : "text-down"}>{pct(t.return_since_pct, 1)} since</span>
            </span>
          ))}
        </div>
      )}
      {bt.note && <p className="mt-2 text-2xs text-faint">{bt.note}</p>}
    </div>
  );
}

export function RulePreviewCard({ readable, backtest, currentlyTrue, method }: { readable: Readable; backtest: Backtest; currentlyTrue: boolean; method: string }) {
  return (
    <div className="space-y-4">
      <div className="flex items-center gap-2">
        <Badge tone={method === "llm" ? "ai" : "neutral"}>{method === "llm" ? "Understood by AI" : method === "builder" ? "Rule builder" : "Instant parse"}</Badge>
        <span className="text-2xs text-muted">Checked every second by a deterministic engine. No AI runs when it fires.</span>
      </div>
      <ReadableRule readable={readable} />
      {currentlyTrue ? (
        <div className="flex items-start gap-2 rounded-lg border border-warn/30 bg-warn/10 p-2.5 text-xs text-warn">
          <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" />
          This condition is true right now, so the rule will fire as soon as you activate it.
        </div>
      ) : (
        <div className="flex items-center gap-2 text-xs text-muted">
          <CheckCircle2 className="h-3.5 w-3.5 text-up" /> Condition is not met yet. It will fire when it becomes true.
        </div>
      )}
      <div className="rounded-lg border border-line bg-panel2/40 p-3">
        <BacktestView bt={backtest} />
      </div>
    </div>
  );
}
