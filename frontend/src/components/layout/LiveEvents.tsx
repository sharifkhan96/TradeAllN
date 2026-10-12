import { useQueryClient } from "@tanstack/react-query";
import { useEffect } from "react";
import { toast } from "sonner";
import { money, pct, qty } from "@/lib/format";
import type { Order } from "@/lib/types";
import { onLive, useLive, type LiveMove } from "@/stores/live";

/** Turns WebSocket events into toasts and cache invalidations. */
export function LiveEvents() {
  const qc = useQueryClient();
  useEffect(
    () =>
      onLive((msg) => {
        if (msg.type === "order_update") {
          const o = msg.order as Order;
          qc.invalidateQueries({ queryKey: ["portfolio"] });
          qc.invalidateQueries({ queryKey: ["orders"] });
          if (msg.filled) {
            toast.success(`${o.side === "buy" ? "Bought" : "Sold"} ${qty(o.filled_qty)} ${o.symbol} @ ${money(o.avg_fill_price)}`, {
              description: o.source === "rule" ? "Executed by an automation" : o.source === "assistant" ? "Placed by the assistant" : undefined,
            });
          } else if (o.status === "rejected") {
            toast.error(`${o.symbol} order rejected`, { description: o.reject_reason });
          } else if (o.status === "expired") {
            toast(`${o.symbol} order expired`);
          }
        } else if (msg.type === "rule_triggered") {
          qc.invalidateQueries({ queryKey: ["rules"] });
          const rule = msg.rule as { name: string };
          (msg.success ? toast.success : toast.error)(`Automation: ${rule.name}`, { description: String(msg.message) });
        } else if (msg.type === "dividend") {
          qc.invalidateQueries({ queryKey: ["portfolio"] });
          toast.success(`Dividend received: ${money(msg.amount)} from ${msg.symbol}`);
        } else if (msg.type === "recurring_run") {
          qc.invalidateQueries({ queryKey: ["portfolio"] });
          toast(`Recurring investment · ${msg.symbol}`, { description: String(msg.message) });
        } else if (msg.type === "move_explained") {
          const m = msg as unknown as LiveMove;
          if (!useLive.getState().watched.has(m.symbol)) return;
          toast(`Why ${m.symbol} just moved ${pct(m.pct)}`, {
            description: m.summary,
            action: { label: "View", onClick: () => (window.location.href = `/stocks/${m.symbol}`) },
            duration: 9000,
          });
        }
      }),
    [qc],
  );
  return null;
}
