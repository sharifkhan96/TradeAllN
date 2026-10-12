import { useQueryClient } from "@tanstack/react-query";
import { CalendarClock } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";
import { Button, Input, Modal, Segmented } from "@/components/ui";
import { api } from "@/lib/api";

const FREQS = [
  { value: "daily", label: "Daily" },
  { value: "weekly", label: "Weekly" },
  { value: "biweekly", label: "2 weeks" },
  { value: "monthly", label: "Monthly" },
] as const;

export function RecurringModal({ symbol, open, onClose }: { symbol: string; open: boolean; onClose: () => void }) {
  const qc = useQueryClient();
  const [amount, setAmount] = useState("25");
  const [freq, setFreq] = useState<(typeof FREQS)[number]["value"]>("weekly");
  const [busy, setBusy] = useState(false);
  const save = async () => {
    setBusy(true);
    try {
      await api("/recurring", { json: { symbol, amount, frequency: freq } });
      qc.invalidateQueries({ queryKey: ["portfolio", "recurring"] });
      toast.success(`Recurring investment set: $${amount} of ${symbol} ${freq}`);
      onClose();
    } catch (e) {
      toast.error((e as Error).message);
    } finally {
      setBusy(false);
    }
  };
  return (
    <Modal open={open} onClose={onClose} title={<span className="flex items-center gap-2"><CalendarClock className="h-4 w-4 text-ai" /> Invest in {symbol} regularly</span>}>
      <div className="space-y-4 p-5">
        <label className="block">
          <span className="label">Amount each time</span>
          <Input className="num mt-1.5 text-base" prefix="$" value={amount} onChange={(e) => setAmount(e.target.value.replace(/[^\d.]/g, ""))} />
        </label>
        <div>
          <span className="label">How often</span>
          <Segmented className="mt-1.5 w-full [&>button]:flex-1" value={freq} onChange={setFreq} options={FREQS.map((f) => ({ value: f.value, label: f.label }))} />
        </div>
        <p className="text-xs text-muted">
          Buys ${amount || "0"} of {symbol} at market price on each scheduled trading day, using fractional shares. The first buy happens on the next trading
          day. Pause or cancel anytime from Portfolio.
        </p>
      </div>
      <div className="flex justify-end gap-2 border-t border-line px-5 py-3">
        <Button variant="ghost" onClick={onClose}>Cancel</Button>
        <Button variant="ai" onClick={save} loading={busy} disabled={!Number(amount)}>Start investing</Button>
      </div>
    </Modal>
  );
}
