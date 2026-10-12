import { useQueryClient } from "@tanstack/react-query";
import { ListOrdered } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";
import { toast } from "sonner";
import { StockLogo } from "@/components/Live";
import { Badge, Button, Card, Empty, Segmented, Skeleton } from "@/components/ui";
import { api } from "@/lib/api";
import { cn } from "@/lib/cn";
import { etTime, money, qty } from "@/lib/format";
import { useOrders } from "@/lib/queries";

const STATUS_TONE: Record<string, "up" | "down" | "ai" | "neutral" | "warn" | "accent"> = {
  filled: "up", open: "accent", partially_filled: "accent", cancelled: "neutral", rejected: "down", expired: "warn",
};

export function OrdersPage() {
  const [tab, setTab] = useState<"open" | "filled" | "cancelled,rejected,expired" | "">("open");
  const { data, isLoading } = useOrders(tab || undefined);
  const qc = useQueryClient();
  const cancel = async (id: string) => {
    try {
      await api(`/orders/${id}`, { method: "DELETE" });
      qc.invalidateQueries({ queryKey: ["orders"] });
      qc.invalidateQueries({ queryKey: ["portfolio"] });
      toast("Order cancelled");
    } catch (e) {
      toast.error((e as Error).message);
    }
  };
  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold tracking-tight">Orders</h1>
          <p className="text-sm text-muted">Manual, assistant and automation orders in one place.</p>
        </div>
        <Segmented
          value={tab}
          onChange={setTab}
          options={[
            { value: "open", label: "Open" },
            { value: "filled", label: "Filled" },
            { value: "cancelled,rejected,expired", label: "Closed" },
            { value: "", label: "All" },
          ]}
        />
      </div>
      <Card className="overflow-x-auto">
        <table className="w-full min-w-[760px] text-sm">
          <thead>
            <tr>
              {["Symbol", "Side", "Type", "Qty", "Limit / Stop", "Fill", "Source", "Status", "Placed", ""].map((h) => (
                <th key={h} className="label px-4 pb-2 pt-4 text-left font-medium">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {isLoading && Array.from({ length: 3 }).map((_, i) => <tr key={i}><td colSpan={10} className="p-3"><Skeleton className="h-8" /></td></tr>)}
            {(data ?? []).map((o) => (
              <tr key={o.id} className="border-t border-line/70 hover:bg-panel2/40">
                <td className="px-4 py-2.5">
                  <Link to={`/stocks/${o.symbol}`} className="flex items-center gap-2.5">
                    <StockLogo symbol={o.symbol} className="h-7 w-7" />
                    <span className="font-semibold">{o.symbol}</span>
                  </Link>
                </td>
                <td className="px-4"><Badge tone={o.side === "buy" ? "up" : "down"}>{o.side.toUpperCase()}</Badge></td>
                <td className="px-4 capitalize text-muted">{o.type.replace("_", " ")} · {o.time_in_force.toUpperCase()}</td>
                <td className="num px-4">{qty(o.quantity)}</td>
                <td className="num px-4 text-muted">
                  {o.limit_price ? money(o.limit_price) : "—"}
                  {o.stop_price ? ` / ${money(o.stop_price)}` : ""}
                </td>
                <td className="num px-4">{o.avg_fill_price ? money(o.avg_fill_price) : "—"}</td>
                <td className="px-4"><Badge tone={o.source === "rule" ? "ai" : o.source === "assistant" ? "accent" : "neutral"}>{o.source}</Badge></td>
                <td className="px-4">
                  <Badge tone={STATUS_TONE[o.status] ?? "neutral"}>{o.status.replace("_", " ")}</Badge>
                  {o.reject_reason && <div className="mt-0.5 max-w-[200px] truncate text-2xs text-muted" title={o.reject_reason}>{o.reject_reason}</div>}
                </td>
                <td className="px-4 text-xs text-muted">{etTime(o.created_at)}</td>
                <td className={cn("px-4 text-right")}>
                  {["open", "partially_filled"].includes(o.status) && <Button size="sm" variant="danger" onClick={() => cancel(o.id)}>Cancel</Button>}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {!isLoading && !data?.length && <Empty icon={<ListOrdered className="h-5 w-5" />} title="No orders here" hint="Limit and stop orders wait here until the price reaches them." />}
      </Card>
    </div>
  );
}
