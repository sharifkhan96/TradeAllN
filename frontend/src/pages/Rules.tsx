import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Pause, Play, SlidersHorizontal, Sparkles, Trash2, Workflow } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";
import { ReadableRule, RulePreviewCard } from "@/components/rules/RulePreview";
import { Badge, Button, Card, Drawer, Empty, Input, Segmented, Skeleton, Spinner } from "@/components/ui";
import { api } from "@/lib/api";
import { cn } from "@/lib/cn";
import { etTime, timeAgo } from "@/lib/format";
import { useCompileRule, useRules } from "@/lib/queries";
import type { Rule, RulePreview } from "@/lib/types";

const EXAMPLES = [
  "if NVDA drops 5% today buy $2000",
  "alert me when AAPL goes above 240",
  "if TSLA rises 4% today sell half",
  "when MSFT's 50-day average crosses above its 200-day, buy 10 shares",
  "if my AMZN position is down 10%, sell all of it",
  "if XOM falls below 100 and RSI is under 30 buy 20",
];

const STATUS_TONE = { active: "up", paused: "neutral", triggered: "ai", expired: "warn", error: "down" } as const;

function Builder({ onPreview }: { onPreview: (p: RulePreview) => void }) {
  const [symbol, setSymbol] = useState("AAPL");
  const [metric, setMetric] = useState<"price" | "pct_change" | "rsi">("pct_change");
  const [op, setOp] = useState("<=");
  const [value, setValue] = useState("-3");
  const [action, setAction] = useState<"buy_notional" | "buy_qty" | "sell_pct" | "notify">("buy_notional");
  const [amount, setAmount] = useState("1000");
  const [busy, setBusy] = useState(false);
  const preview = async () => {
    setBusy(true);
    const sym = symbol.toUpperCase();
    const act: Record<string, unknown> = { type: action, symbol: action === "notify" ? null : sym };
    if (action === "buy_notional") act.amount = Number(amount);
    if (action === "buy_qty") act.quantity = Number(amount);
    if (action === "sell_pct") act.pct = Number(amount);
    if (action === "notify") act.message = `${sym} condition met`;
    const clause: Record<string, unknown> = { metric, symbol: sym, op, value: Number(value) };
    if (metric === "rsi") clause.period = 14;
    try {
      onPreview(
        await api<RulePreview>("/rules/preview", {
          json: { spec: { name: `${sym} ${metric.replace("_", " ")} ${op} ${value}`, condition: { logic: "all", clauses: [clause] }, action: act, mode: "once" } },
        }),
      );
    } catch (e) {
      toast.error((e as Error).message);
    } finally {
      setBusy(false);
    }
  };
  const sel = "h-10 rounded-lg border border-line bg-panel2/60 px-2.5 text-sm outline-none focus:border-accent/60";
  return (
    <div className="grid items-end gap-3 md:grid-cols-[repeat(6,minmax(0,1fr))_auto]">
      <label><span className="label">Symbol</span><Input className="mt-1.5" value={symbol} onChange={(e) => setSymbol(e.target.value)} /></label>
      <label><span className="label">Metric</span>
        <select className={cn(sel, "mt-1.5 w-full")} value={metric} onChange={(e) => setMetric(e.target.value as typeof metric)}>
          <option value="pct_change">% change today</option><option value="price">Price</option><option value="rsi">RSI (14, daily)</option>
        </select>
      </label>
      <label><span className="label">Is</span>
        <select className={cn(sel, "mt-1.5 w-full")} value={op} onChange={(e) => setOp(e.target.value)}>
          <option value="<=">≤ at or below</option><option value=">=">≥ at or above</option><option value="crosses_above">crosses above</option><option value="crosses_below">crosses below</option>
        </select>
      </label>
      <label><span className="label">Value</span><Input className="num mt-1.5" value={value} onChange={(e) => setValue(e.target.value)} /></label>
      <label><span className="label">Then</span>
        <select className={cn(sel, "mt-1.5 w-full")} value={action} onChange={(e) => setAction(e.target.value as typeof action)}>
          <option value="buy_notional">Buy $ amount</option><option value="buy_qty">Buy shares</option><option value="sell_pct">Sell % of position</option><option value="notify">Notify me</option>
        </select>
      </label>
      <label className={cn(action === "notify" && "invisible")}><span className="label">{action === "buy_notional" ? "Dollars" : action === "sell_pct" ? "Percent" : "Shares"}</span><Input className="num mt-1.5" value={amount} onChange={(e) => setAmount(e.target.value)} /></label>
      <Button onClick={preview} loading={busy}>Preview</Button>
    </div>
  );
}

function RuleDetail({ id, onClose }: { id: number | null; onClose: () => void }) {
  const { data } = useQuery({ queryKey: ["rule", id], queryFn: () => api<Rule>(`/rules/${id}`), enabled: id != null });
  return (
    <Drawer open={id != null} onClose={onClose} title={data?.name ?? "Automation"} width="max-w-lg">
      {data ? (
        <div className="space-y-5 p-5">
          {data.source_text && <p className="rounded-lg bg-panel2/60 p-3 text-sm italic text-muted">“{data.source_text}”</p>}
          {data.readable && <ReadableRule readable={data.readable} />}
          <div className="grid grid-cols-2 gap-3 text-xs">
            <div><div className="label">Status</div><Badge tone={STATUS_TONE[data.status]} className="mt-1">{data.status}</Badge></div>
            <div><div className="label">Condition now</div><div className="mt-1">{data.last_condition ? "true" : "false"}</div></div>
            <div><div className="label">Last checked</div><div className="mt-1">{data.last_evaluated_at ? timeAgo(data.last_evaluated_at) : "never"}</div></div>
            <div><div className="label">Expires</div><div className="mt-1">{data.expires_at ? etTime(data.expires_at) : "—"}</div></div>
          </div>
          {data.status_message && <p className="text-xs text-muted">{data.status_message}</p>}
          <div>
            <div className="label mb-2">History</div>
            {data.executions?.length ? (
              <div className="space-y-2">
                {data.executions.map((e) => (
                  <div key={e.id} className="rounded-lg border border-line p-3 text-sm">
                    <div className="flex justify-between text-2xs text-muted"><span>{etTime(e.triggered_at)}</span><Badge tone={e.success ? "up" : "down"}>{e.success ? "ok" : "failed"}</Badge></div>
                    <p className="mt-1">{e.result}</p>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-sm text-muted">Hasn't triggered yet.</p>
            )}
          </div>
        </div>
      ) : (
        <div className="p-5"><Spinner /></div>
      )}
    </Drawer>
  );
}

export function RulesPage() {
  const { data: rules, isLoading } = useRules();
  const compile = useCompileRule();
  const qc = useQueryClient();
  const [text, setText] = useState("");
  const [mode, setMode] = useState<"ai" | "builder">("ai");
  const [preview, setPreview] = useState<RulePreview | null>(null);
  const [detail, setDetail] = useState<number | null>(null);

  const activate = useMutation({
    mutationFn: () => api<Rule>("/rules", { json: { spec: preview!.spec, source_text: preview!.source_text } }),
    onSuccess: (r) => {
      toast.success("Automation activated", { description: r.readable?.then });
      setPreview(null);
      setText("");
      qc.invalidateQueries({ queryKey: ["rules"] });
    },
    onError: (e) => toast.error((e as Error).message),
  });

  const act = async (r: Rule, action: "pause" | "resume" | "delete") => {
    try {
      if (action === "delete") await api(`/rules/${r.id}`, { method: "DELETE" });
      else await api(`/rules/${r.id}/${action}`, { method: "POST" });
      qc.invalidateQueries({ queryKey: ["rules"] });
    } catch (e) {
      toast.error((e as Error).message);
    }
  };

  const run = async (t: string) => {
    setText(t);
    setPreview(null);
    try {
      setPreview(await compile.mutateAsync(t));
    } catch {
      /* shown below */
    }
  };

  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-xl font-semibold tracking-tight">Automations</h1>
        <p className="text-sm text-muted">Describe conditions in plain English. A deterministic engine checks them every second and acts for you.</p>
      </div>

      <Card className="ai-border p-5">
        <div className="mb-4 flex items-center justify-between">
          <div className="flex items-center gap-2 text-sm font-semibold"><Sparkles className="h-4 w-4 text-ai" /> New automation</div>
          <Segmented value={mode} onChange={setMode} options={[{ value: "ai", label: <span className="flex items-center gap-1"><Sparkles className="h-3 w-3" /> Describe</span> }, { value: "builder", label: <span className="flex items-center gap-1"><SlidersHorizontal className="h-3 w-3" /> Builder</span> }]} />
        </div>
        {mode === "ai" ? (
          <>
            <form
              onSubmit={(e) => {
                e.preventDefault();
                run(text);
              }}
              className="flex gap-2"
            >
              <Input className="h-12 flex-1 text-base" value={text} onChange={(e) => setText(e.target.value)} placeholder="If NVDA drops 5% today and RSI is below 30, buy $2,000…" />
              <Button type="submit" variant="ai" size="lg" loading={compile.isPending}>Preview</Button>
            </form>
            <div className="mt-3 flex flex-wrap gap-1.5">
              {EXAMPLES.map((ex) => (
                <button key={ex} onClick={() => run(ex)} className="rounded-full border border-line px-2.5 py-1 text-xs text-muted transition-colors hover:border-ai/40 hover:text-fg">
                  {ex}
                </button>
              ))}
            </div>
            {compile.error && <p className="mt-3 rounded-lg border border-down/30 bg-down/10 px-3 py-2 text-sm text-down">{(compile.error as Error).message}</p>}
          </>
        ) : (
          <Builder onPreview={setPreview} />
        )}
        {preview && (
          <div className="mt-5 animate-fadeIn border-t border-line pt-5">
            <RulePreviewCard readable={preview.readable} backtest={preview.backtest} currentlyTrue={preview.currently_true} method={preview.method} />
            <div className="mt-4 flex justify-end gap-2">
              <Button variant="ghost" onClick={() => setPreview(null)}>Discard</Button>
              <Button variant="ai" onClick={() => activate.mutate()} loading={activate.isPending}>Activate automation</Button>
            </div>
          </div>
        )}
      </Card>

      <div className="grid gap-4 md:grid-cols-2">
        {isLoading && [0, 1].map((i) => <Skeleton key={i} className="h-40" />)}
        {(rules ?? []).map((r) => (
          <Card key={r.id} className="flex flex-col p-4 transition-colors hover:border-faint/50">
            <div className="flex items-start justify-between gap-3">
              <button onClick={() => setDetail(r.id)} className="min-w-0 text-left">
                <div className="truncate text-sm font-semibold">{r.name}</div>
                <div className="mt-0.5 text-2xs text-muted">
                  {r.trigger_count ? `Fired ${r.trigger_count}× · last ${timeAgo(r.last_triggered_at!)}` : "Not fired yet"} ·{" "}
                  {r.last_evaluated_at ? `checked ${timeAgo(r.last_evaluated_at)}` : "waiting for the engine"}
                </div>
              </button>
              <Badge tone={STATUS_TONE[r.status]}>
                {r.status === "active" && <span className="h-1.5 w-1.5 animate-pulseDot rounded-full bg-up" />}
                {r.status}
              </Badge>
            </div>
            <div className="mt-3 flex-1">{r.readable && <ReadableRule readable={r.readable} compact />}</div>
            {r.status_message && <p className="mt-2 truncate text-2xs text-muted" title={r.status_message}>{r.status_message}</p>}
            <div className="mt-3 flex justify-end gap-1 border-t border-line pt-3">
              {r.status === "active" ? (
                <Button size="sm" variant="ghost" onClick={() => act(r, "pause")}><Pause className="h-3.5 w-3.5" /> Pause</Button>
              ) : (
                <Button size="sm" variant="ghost" onClick={() => act(r, "resume")}><Play className="h-3.5 w-3.5" /> {r.status === "paused" ? "Resume" : "Re-arm"}</Button>
              )}
              <Button size="sm" variant="ghost" onClick={() => act(r, "delete")} className="hover:text-down"><Trash2 className="h-3.5 w-3.5" /></Button>
            </div>
          </Card>
        ))}
      </div>
      {!isLoading && !rules?.length && <Empty icon={<Workflow className="h-5 w-5" />} title="No automations yet" hint="Describe one above, e.g. “alert me when AAPL goes above 240”." />}
      <RuleDetail id={detail} onClose={() => setDetail(null)} />
    </div>
  );
}
