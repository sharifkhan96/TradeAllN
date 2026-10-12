import { useQueryClient } from "@tanstack/react-query";
import { Command as Cmdk } from "cmdk";
import { ArrowRight, Check, CornerDownLeft, Search, Sparkles, X, XCircle, Zap } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { createPortal } from "react-dom";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { ChangePill, StockLogo } from "@/components/Live";
import { RulePreviewCard } from "@/components/rules/RulePreview";
import { Badge, Button, Spinner } from "@/components/ui";
import { api } from "@/lib/api";
import { cn } from "@/lib/cn";
import { money, price, qty } from "@/lib/format";
import { Markdown } from "@/lib/md";
import { useParseCommand, useStocks } from "@/lib/queries";
import type { Command } from "@/lib/types";
import { useUI } from "@/stores/ui";

const EXAMPLES = [
  { text: "buy $500 of apple", hint: "Dollar-amount market order" },
  { text: "sell half my nvidia", hint: "Uses your position size" },
  { text: "buy 5 msft at 400 gtc", hint: "Limit order, good till cancelled" },
  { text: "if tesla drops 3% today buy $1000", hint: "Creates an automation" },
  { text: "alert me when AAPL goes above 240", hint: "Price alert" },
  { text: "why is my portfolio down today?", hint: "Ask about your portfolio" },
  { text: "close all my tech positions", hint: "Basket order (AI)" },
  { text: "put a stop loss 8% below all my positions", hint: "Protective stops (AI)" },
];

function OrdersPreview({ cmd }: { cmd: Extract<Command["preview"], { kind: "orders" }> }) {
  return (
    <div className="space-y-2">
      {cmd.items.map((it, i) => (
        <div key={i} className={cn("flex items-center gap-3 rounded-lg border p-3", it.error ? "border-down/30 bg-down/5" : "border-line bg-panel2/40")}>
          <StockLogo symbol={it.symbol} />
          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-2 text-sm">
              <Badge tone={it.side === "buy" ? "up" : "down"}>{it.side.toUpperCase()}</Badge>
              <span className="font-semibold">{it.quantity != null ? qty(it.quantity) : "—"} {it.symbol}</span>
              <span className="text-xs text-muted">
                {it.type.replace("_", " ")}
                {it.limit_price ? ` @ ${money(it.limit_price)}` : ""}
                {it.stop_price ? ` stop ${money(it.stop_price)}` : ""} · {it.time_in_force.toUpperCase()}
              </span>
            </div>
            {it.error ? (
              <div className="mt-1 text-xs text-down">{it.error}</div>
            ) : (
              <div className="mt-0.5 truncate text-xs text-muted">
                {it.name} · last {price(it.price)}
                {it.warnings?.map((w) => (
                  <span key={w} className="ml-2 text-warn">⚠ {w}</span>
                ))}
              </div>
            )}
          </div>
          <div className="num text-right text-sm font-medium">{it.error ? "" : `≈ ${money(it.est_value)}`}</div>
        </div>
      ))}
      {cmd.warnings.map((w) => (
        <div key={w} className="text-xs text-warn">⚠ {w}</div>
      ))}
      <div className="num flex justify-between px-1 pt-1 text-xs text-muted">
        <span>{cmd.totals.buy > 0 && <>Buying ≈ <span className="text-fg">{money(cmd.totals.buy)}</span></>}{cmd.totals.sell > 0 && <> Selling ≈ <span className="text-fg">{money(cmd.totals.sell)}</span></>}</span>
        <span>Buying power after ≈ <span className="text-fg">{money(cmd.totals.buying_power_after)}</span></span>
      </div>
    </div>
  );
}

function Result({ cmd, onDone }: { cmd: Command; onDone: () => void }) {
  const qc = useQueryClient();
  const navigate = useNavigate();
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState<Command | null>(null);
  const p = cmd.preview;

  useEffect(() => {
    if (p.kind === "navigate") {
      navigate(`/stocks/${p.symbol}`);
      onDone();
    }
  }, [p, navigate, onDone]);

  const confirm = async () => {
    setBusy(true);
    try {
      const r = await api<Command>(`/assistant/confirm/${cmd.id}`, { method: "POST" });
      setDone(r);
      qc.invalidateQueries({ queryKey: ["portfolio"] });
      qc.invalidateQueries({ queryKey: ["orders"] });
      qc.invalidateQueries({ queryKey: ["rules"] });
      const ok = r.result.results?.filter((x) => x.ok).length ?? 0;
      if (p.kind === "rule") toast.success("Automation activated", { description: p.readable.then });
      else if (ok) toast.success(p.kind === "cancel" ? `Cancelled ${ok} order${ok > 1 ? "s" : ""}` : `Placed ${ok} order${ok > 1 ? "s" : ""}`);
    } catch (e) {
      toast.error((e as Error).message);
    } finally {
      setBusy(false);
    }
  };
  const reject = () => {
    api(`/assistant/reject/${cmd.id}`, { method: "POST" }).catch(() => undefined);
    onDone();
  };

  const header = (
    <div className="mb-3 flex items-center justify-between">
      <div className="flex min-w-0 items-center gap-2 text-sm">
        <span className="truncate text-muted">“{cmd.input}”</span>
      </div>
      <Badge tone={cmd.method === "llm" ? "ai" : "neutral"}>
        {cmd.method === "llm" ? <><Sparkles className="h-3 w-3" /> AI</> : <><Zap className="h-3 w-3" /> Instant</>}
      </Badge>
    </div>
  );

  if (done) {
    const results = done.result.results ?? [];
    return (
      <div className="p-4">
        {header}
        <div className="space-y-1.5">
          {results.map((r, i) => (
            <div key={i} className="flex items-center gap-2 text-sm">
              {r.ok ? <Check className="h-4 w-4 text-up" /> : <XCircle className="h-4 w-4 text-down" />}
              <span className="font-medium">{r.symbol ?? "Automation"}</span>
              <span className="text-muted">
                {r.ok ? (r.status === "filled" ? `filled${r.fill_price ? ` @ ${money(r.fill_price)}` : ""}` : r.status ?? "done") : r.error}
              </span>
            </div>
          ))}
        </div>
        <div className="mt-4 flex justify-end">
          <Button variant="primary" size="sm" onClick={onDone}>Done</Button>
        </div>
      </div>
    );
  }

  return (
    <div className="max-h-[65vh] overflow-y-auto p-4">
      {header}
      {p.kind === "orders" && <OrdersPreview cmd={p} />}
      {p.kind === "cancel" && (
        <div className="space-y-1.5">
          {p.orders.map((o) => (
            <div key={o.id} className="flex items-center gap-2 rounded-lg border border-line bg-panel2/40 px-3 py-2 text-sm">
              <Badge tone={o.side === "buy" ? "up" : "down"}>{o.side.toUpperCase()}</Badge>
              {qty(o.quantity)} {o.symbol} <span className="text-xs text-muted">{o.type}{o.limit_price ? ` @ ${money(o.limit_price)}` : ""}</span>
            </div>
          ))}
          {p.warnings.map((w) => <p key={w} className="text-xs text-muted">{w}</p>)}
        </div>
      )}
      {p.kind === "rule" && <RulePreviewCard readable={p.readable} backtest={p.backtest} currentlyTrue={p.currently_true} method={p.method} />}
      {p.kind === "answer" && (
        <div className="rounded-lg border border-line bg-panel2/30 p-3.5">
          <Markdown text={p.answer} />
          {p.method === "rules" && <p className="mt-3 text-2xs text-faint">Answered without AI. Add an Anthropic API key for open-ended questions.</p>}
        </div>
      )}
      {p.kind === "message" && <p className="rounded-lg border border-line bg-panel2/30 p-3.5 text-sm text-muted">{p.message}</p>}

      {p.executable && (
        <div className="mt-4 flex items-center justify-between gap-3 border-t border-line pt-3">
          <p className="text-2xs text-faint">Paper trading with virtual money. Nothing executes until you confirm.</p>
          <div className="flex gap-2">
            <Button variant="ghost" size="sm" onClick={reject}>Cancel</Button>
            <Button
              size="sm"
              loading={busy}
              onClick={confirm}
              variant={p.kind === "rule" ? "ai" : p.kind === "cancel" ? "danger" : p.kind === "orders" && p.items.every((i) => i.side === "sell") ? "down" : "up"}
            >
              {p.kind === "rule" ? "Activate automation" : p.kind === "cancel" ? "Cancel orders" : "Confirm"}
              <CornerDownLeft className="h-3.5 w-3.5 opacity-70" />
            </Button>
          </div>
        </div>
      )}
      {!p.executable && p.kind !== "navigate" && (
        <div className="mt-4 flex justify-end">
          <Button size="sm" variant="ghost" onClick={onDone}>Close</Button>
        </div>
      )}
    </div>
  );
}

export function CommandPalette() {
  const { paletteOpen, paletteText, closePalette } = useUI();
  const [text, setText] = useState("");
  const [cmd, setCmd] = useState<Command | null>(null);
  const parse = useParseCommand();
  const navigate = useNavigate();
  const term = text.trim();
  const looksLikeCommand = /\s/.test(term) || /^(buy|sell|if|when|alert|why|what|how|cancel|close)/i.test(term);
  const { data: stocks } = useStocks(term.length >= 1 && term.length < 20 ? term.split(" ").pop() ?? "" : "");

  useEffect(() => {
    if (paletteOpen) {
      setText(paletteText);
      setCmd(null);
      parse.reset();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [paletteOpen]);

  useEffect(() => {
    if (!paletteOpen) return;
    const k = (e: KeyboardEvent) => e.key === "Escape" && closePalette();
    window.addEventListener("keydown", k);
    return () => window.removeEventListener("keydown", k);
  }, [paletteOpen, closePalette]);

  const run = async (t: string) => {
    if (!t.trim()) return;
    setText(t);
    try {
      setCmd(await parse.mutateAsync(t));
    } catch {
      /* error rendered below */
    }
  };

  const runItem = term ? (

                <Cmdk.Item
                  value={`run:${term}`}
                  onSelect={() => run(term)}
                  className="flex cursor-pointer items-center gap-3 rounded-lg px-3 py-2.5 text-sm data-[selected=true]:bg-ai/10"
                >
                  <div className="ai-gradient grid h-8 w-8 place-items-center rounded-lg text-white"><Sparkles className="h-4 w-4" /></div>
                  <div className="min-w-0 flex-1">
                    <div className="truncate font-medium">{term}</div>
                    <div className="text-xs text-muted">Run as an order, automation or question</div>
                  </div>
                  <CornerDownLeft className="h-4 w-4 text-muted" />
                </Cmdk.Item>
              
  ) : null;

  const matches = useMemo(() => (term ? (stocks ?? []).slice(0, 6) : []), [stocks, term]);

  if (!paletteOpen) return null;
  return createPortal(
    <div className="fixed inset-0 z-50 flex items-start justify-center bg-black/55 p-4 pt-[9vh] backdrop-blur-sm" onMouseDown={closePalette}>
      <div className="ai-border w-full max-w-2xl animate-fadeIn overflow-hidden rounded-2xl shadow-pop" onMouseDown={(e) => e.stopPropagation()}>
        {cmd ? (
          <Result cmd={cmd} onDone={closePalette} />
        ) : (
          <Cmdk shouldFilter={false} loop className="flex flex-col">
            <div className="flex items-center gap-3 border-b border-line px-4">
              {parse.isPending ? <Spinner className="text-ai" /> : <Sparkles className="h-4 w-4 text-ai" />}
              <Cmdk.Input
                autoFocus
                value={text}
                onValueChange={(v) => {
                  setText(v);
                  parse.reset();
                }}
                placeholder="Trade, automate, search or ask…"
                className="h-14 flex-1 bg-transparent text-[15px] outline-none placeholder:text-faint"
              />
              <button onClick={closePalette} className="text-muted hover:text-fg" aria-label="Close">
                <X className="h-4 w-4" />
              </button>
            </div>
            {parse.error && <div className="border-b border-line bg-down/5 px-4 py-3 text-sm text-down">{(parse.error as Error).message}</div>}
            <Cmdk.List className="max-h-[56vh] overflow-y-auto p-2">
              {looksLikeCommand && runItem}
              {matches.length > 0 && (
                <Cmdk.Group heading="Stocks" className="[&_[cmdk-group-heading]]:label [&_[cmdk-group-heading]]:px-3 [&_[cmdk-group-heading]]:py-2">
                  {matches.map((s) => (
                    <Cmdk.Item
                      key={s.symbol}
                      value={`stock:${s.symbol}`}
                      onSelect={() => {
                        navigate(`/stocks/${s.symbol}`);
                        closePalette();
                      }}
                      className="flex cursor-pointer items-center gap-3 rounded-lg px-3 py-2 text-sm data-[selected=true]:bg-panel2"
                    >
                      <StockLogo symbol={s.symbol} />
                      <div className="min-w-0 flex-1">
                        <div className="flex items-center gap-1.5 font-semibold">
                          {s.symbol}
                          <span className="text-2xs font-normal text-faint">{s.exchange}</span>
                          {s.is_etf && <Badge tone="accent">ETF</Badge>}
                        </div>
                        <div className="truncate text-xs text-muted">{s.name}</div>
                      </div>
                      {s.quote && <span className="num text-sm">{price(s.quote.price)}</span>}
                      {s.quote && <ChangePill value={s.quote.change_pct} />}
                      <ArrowRight className="h-4 w-4 text-faint" />
                    </Cmdk.Item>
                  ))}
                </Cmdk.Group>
              )}
              {!looksLikeCommand && runItem}
              {!term && (
                <Cmdk.Group heading="Try" className="[&_[cmdk-group-heading]]:label [&_[cmdk-group-heading]]:px-3 [&_[cmdk-group-heading]]:py-2">
                  {EXAMPLES.map((ex) => (
                    <Cmdk.Item
                      key={ex.text}
                      value={`ex:${ex.text}`}
                      onSelect={() => run(ex.text)}
                      className="flex cursor-pointer items-center gap-3 rounded-lg px-3 py-2 text-sm data-[selected=true]:bg-panel2"
                    >
                      <Search className="h-4 w-4 text-faint" />
                      <span className="flex-1">{ex.text}</span>
                      <span className="text-xs text-muted">{ex.hint}</span>
                    </Cmdk.Item>
                  ))}
                </Cmdk.Group>
              )}
            </Cmdk.List>
            <div className="flex items-center justify-between border-t border-line px-4 py-2 text-2xs text-faint">
              <span>↑↓ navigate · ↵ run · esc close</span>
              <span>Orders always need your confirmation</span>
            </div>
          </Cmdk>
        )}
      </div>
    </div>,
    document.body,
  );
}
