import { useQueryClient } from "@tanstack/react-query";
import { CalendarClock, Moon } from "lucide-react";
import { useMemo, useState } from "react";
import { toast } from "sonner";
import { useLiveQuote } from "@/components/Live";
import { RecurringModal } from "@/components/trading/RecurringModal";
import { Button, Card, Input, Segmented, Switch } from "@/components/ui";
import { api } from "@/lib/api";
import { cn } from "@/lib/cn";
import { countdown, money, qty as fmtQty } from "@/lib/format";
import { useMarketStatus, usePositions, useSummary } from "@/lib/queries";
import type { Order, Quote } from "@/lib/types";

type Side = "buy" | "sell";
type Type = "market" | "limit" | "stop" | "stop_limit";

export function OrderTicket({ symbol, quote }: { symbol: string; quote?: Quote | null }) {
  const qc = useQueryClient();
  const live = useLiveQuote(symbol, quote);
  const { data: summary } = useSummary();
  const { data: positions } = usePositions();
  const { data: market } = useMarketStatus();
  const pos = positions?.find((p) => p.symbol === symbol);
  const [side, setSide] = useState<Side>("buy");
  const [type, setType] = useState<Type>("market");
  const [mode, setMode] = useState<"dollars" | "shares">("dollars");
  const [amount, setAmount] = useState("");
  const [limit, setLimit] = useState("");
  const [stop, setStop] = useState("");
  const [tif, setTif] = useState<"day" | "gtc">("day");
  const [extended, setExtended] = useState(false);
  const [review, setReview] = useState(false);
  const [busy, setBusy] = useState(false);
  const [recurring, setRecurring] = useState(false);

  const extendedSession = market && ["pre_market", "after_hours"].includes(market.status);
  const refPrice =
    type === "limit" || type === "stop_limit" ? Number(limit) || live.price : type === "stop" ? Number(stop) || live.price : extended && live.ext_price ? live.ext_price : live.price;
  const shares = useMemo(() => {
    const a = Number(amount);
    if (!a || !refPrice) return 0;
    const raw = mode === "shares" ? a : a / refPrice;
    return Math.floor(raw * 1e6) / 1e6; // fractional shares, 6 dp
  }, [amount, mode, refPrice]);
  const est = mode === "dollars" ? Number(amount) || 0 : shares * refPrice;
  const maxSell = pos?.available ?? 0;
  const over = side === "buy" ? est > (summary?.buying_power ?? 0) : shares > maxSell + 1e-9;
  const needsWhole = type === "stop" || type === "stop_limit";

  const submit = async () => {
    setBusy(true);
    try {
      const body: Record<string, unknown> = {
        symbol,
        side,
        type,
        limit_price: type === "limit" || type === "stop_limit" ? Number(limit) : null,
        stop_price: type === "stop" || type === "stop_limit" ? Number(stop) : null,
        time_in_force: tif,
        extended_hours: type === "limit" && extended,
        client_order_id: crypto.randomUUID(),
      };
      if (mode === "dollars" && side === "buy") body.notional = Number(amount).toFixed(2);
      else body.quantity = mode === "shares" ? Number(amount) : shares;
      const o = await api<Order>("/orders", { json: body });
      qc.invalidateQueries({ queryKey: ["portfolio"] });
      qc.invalidateQueries({ queryKey: ["orders"] });
      if (o.status === "open")
        toast(`Order placed: ${side} ${fmtQty(o.quantity)} ${symbol}`, {
          description: market?.status !== "open" && !o.extended_hours ? "Queued for the market open" : `${type.replace("_", " ")} · waiting for price`,
        });
      setAmount("");
      setReview(false);
    } catch (e) {
      toast.error((e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <Card className="overflow-hidden">
      <div className="grid grid-cols-2 border-b border-line">
        {(["buy", "sell"] as Side[]).map((s) => (
          <button
            key={s}
            onClick={() => {
              setSide(s);
              setReview(false);
              if (s === "sell") setMode("shares");
            }}
            className={cn(
              "h-11 text-sm font-semibold capitalize transition-colors",
              side === s ? (s === "buy" ? "bg-up/10 text-up shadow-[inset_0_-2px_0_rgb(var(--up))]" : "bg-down/10 text-down shadow-[inset_0_-2px_0_rgb(var(--down))]") : "text-muted hover:text-fg",
            )}
          >
            {s} {symbol}
          </button>
        ))}
      </div>
      <div className="space-y-3.5 p-4">
        <Segmented
          value={type}
          onChange={(v) => {
            setType(v);
            setReview(false);
            if (v === "stop" || v === "stop_limit") setMode("shares");
          }}
          className="w-full [&>button]:flex-1"
          options={[
            { value: "market", label: "Market" },
            { value: "limit", label: "Limit" },
            { value: "stop", label: "Stop" },
            { value: "stop_limit", label: "Stop limit" },
          ]}
        />
        <div>
          <div className="mb-1.5 flex items-center justify-between">
            <span className="label">{mode === "shares" ? "Shares" : "Amount"}</span>
            {!needsWhole && (
              <Segmented
                value={mode}
                onChange={(m) => {
                  setMode(m);
                  setAmount("");
                }}
                options={[
                  { value: "dollars", label: "$" },
                  { value: "shares", label: "Shares" },
                ]}
              />
            )}
          </div>
          <Input
            inputMode="decimal"
            value={amount}
            onChange={(e) => setAmount(e.target.value.replace(/[^\d.]/g, ""))}
            placeholder={mode === "dollars" ? "0.00" : "0"}
            prefix={mode === "dollars" ? "$" : undefined}
            suffix={
              <button
                type="button"
                onClick={() => {
                  if (side === "sell") {
                    setMode("shares");
                    setAmount(String(maxSell));
                  } else {
                    setMode("dollars");
                    setAmount(String(Math.floor((summary?.buying_power ?? 0) * 0.99 * 100) / 100));
                  }
                }}
                className="font-medium text-muted hover:text-fg"
              >
                MAX
              </button>
            }
            className="num text-base"
          />
          {side === "buy" && mode === "dollars" && (
            <div className="mt-2 flex gap-1.5">
              {[10, 50, 100, 500].map((v) => (
                <button key={v} onClick={() => setAmount(String(v))} className="num flex-1 rounded-md border border-line py-1 text-xs text-muted hover:border-faint/60 hover:text-fg">
                  ${v}
                </button>
              ))}
            </div>
          )}
        </div>
        {(type === "stop" || type === "stop_limit") && (
          <label className="block">
            <span className="label">Stop price</span>
            <Input className="num mt-1.5" prefix="$" value={stop} onChange={(e) => setStop(e.target.value.replace(/[^\d.]/g, ""))} placeholder={live.price.toFixed(2)} />
          </label>
        )}
        {(type === "limit" || type === "stop_limit") && (
          <label className="block">
            <span className="label">Limit price</span>
            <Input className="num mt-1.5" prefix="$" value={limit} onChange={(e) => setLimit(e.target.value.replace(/[^\d.]/g, ""))} placeholder={live.price.toFixed(2)} />
          </label>
        )}
        {type !== "market" && (
          <div className="flex items-center justify-between">
            <span className="label">Time in force</span>
            <Segmented value={tif} onChange={setTif} options={[{ value: "day", label: "Day" }, { value: "gtc", label: "GTC" }]} />
          </div>
        )}
        {type === "limit" && (
          <div className="flex items-center justify-between gap-3 rounded-lg border border-line px-3 py-2">
            <div>
              <div className="flex items-center gap-1.5 text-sm font-medium"><Moon className="h-3.5 w-3.5 text-ai" /> Extended hours</div>
              <div className="text-2xs text-muted">Allow fills 4:00–9:30 AM and 4:00–8:00 PM ET</div>
            </div>
            <Switch checked={extended} onChange={setExtended} label="Extended hours" />
          </div>
        )}
        <div className="num space-y-1.5 rounded-lg bg-panel2/50 p-3 text-xs">
          <Row label={extended && live.ext_price ? "Extended-hours price" : "Market price"} value={money(extended && live.ext_price ? live.ext_price : live.price)} />
          <Row label="Est. shares" value={fmtQty(shares)} />
          <Row label={side === "buy" ? "Estimated cost" : "Estimated proceeds"} value={money(est)} strong />
          <Row
            label={side === "buy" ? "Buying power" : "Shares available"}
            value={side === "buy" ? money(summary?.buying_power) : fmtQty(maxSell)}
            className={over ? "text-down" : undefined}
          />
        </div>
        {market && market.status !== "open" && !(extended && type === "limit" && extendedSession) && (
          <p className="rounded-lg border border-warn/25 bg-warn/10 px-3 py-2 text-xs text-warn">
            The market is closed. Your order will be queued and fills from the open
            {market.opens_at ? ` (${countdown(market.opens_at)})` : ""}.{type === "market" && extendedSession ? " Use a limit order with extended hours to trade now." : ""}
          </p>
        )}
        {review ? (
          <div className="space-y-2">
            <p className="text-center text-xs text-muted">
              {side === "buy" ? "Buy" : "Sell"} <b className="text-fg">{mode === "dollars" && side === "buy" ? money(est) + " of " : fmtQty(shares) + " "}{symbol}</b> at{" "}
              {type === "market" ? "market" : type.replace("_", " ")}
              {extended && type === "limit" ? " · extended hours" : ""}
            </p>
            <div className="grid grid-cols-2 gap-2">
              <Button variant="secondary" onClick={() => setReview(false)} className="justify-center">Edit</Button>
              <Button variant={side === "buy" ? "up" : "down"} onClick={submit} loading={busy} className="justify-center">
                Submit order
              </Button>
            </div>
          </div>
        ) : (
          <Button
            variant={side === "buy" ? "up" : "down"}
            size="lg"
            className="w-full justify-center"
            disabled={!shares || over || ((type === "limit" || type === "stop_limit") && !Number(limit)) || ((type === "stop" || type === "stop_limit") && !Number(stop))}
            onClick={() => setReview(true)}
          >
            Review {side} order
          </Button>
        )}
        {side === "buy" && (
          <button onClick={() => setRecurring(true)} className="flex w-full items-center justify-center gap-1.5 text-xs font-medium text-ai hover:underline">
            <CalendarClock className="h-3.5 w-3.5" /> Invest in {symbol} regularly
          </button>
        )}
        {pos && (
          <p className="text-center text-2xs text-muted">
            You own {fmtQty(pos.quantity)} shares · avg {money(pos.avg_cost)}
          </p>
        )}
      </div>
      <RecurringModal symbol={symbol} open={recurring} onClose={() => setRecurring(false)} />
    </Card>
  );
}

function Row({ label, value, strong, className }: { label: string; value: string; strong?: boolean; className?: string }) {
  return (
    <div className={cn("flex justify-between", className)}>
      <span className="font-sans text-muted">{label}</span>
      <span className={cn(strong && "font-semibold text-fg")}>{value}</span>
    </div>
  );
}
