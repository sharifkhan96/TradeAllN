import { useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { toast } from "sonner";
import { Badge, Button, Card, CardHeader, Input, Modal, Switch } from "@/components/ui";
import { api } from "@/lib/api";
import { useAIStatus } from "@/lib/queries";
import type { User } from "@/lib/types";
import { useAuth } from "@/stores/auth";
import { useUI } from "@/stores/ui";

export function SettingsPage() {
  const user = useAuth((s) => s.user)!;
  const { theme, toggleTheme } = useUI();
  const { data: ai } = useAIStatus();
  const qc = useQueryClient();
  const [name, setName] = useState(user.display_name);
  const [confirmReset, setConfirmReset] = useState(false);

  const patch = async (body: Partial<User>) => {
    try {
      const u = await api<User>("/auth/me", { method: "PATCH", json: body });
      useAuth.getState().setUser(u);
      toast.success("Saved");
    } catch (e) {
      toast.error((e as Error).message);
    }
  };
  const reset = async () => {
    await api("/accounts/reset", { method: "POST" });
    qc.invalidateQueries();
    setConfirmReset(false);
    toast.success("Paper account reset to its starting cash");
  };

  return (
    <div className="mx-auto max-w-3xl space-y-5">
      <h1 className="text-xl font-semibold tracking-tight">Settings</h1>
      <Card>
        <CardHeader title="Profile" />
        <div className="flex items-end gap-3 p-5">
          <label className="flex-1"><span className="label">Display name</span><Input className="mt-1.5" value={name} onChange={(e) => setName(e.target.value)} /></label>
          <Button onClick={() => patch({ display_name: name })}>Save</Button>
        </div>
        <div className="px-5 pb-5 text-sm text-muted">Signed in as {user.email}</div>
      </Card>
      <Card>
        <CardHeader title="AI & automations" />
        <div className="divide-y divide-line">
          <Row
            title={<>AI features {ai && <Badge tone={ai.ai_enabled ? "ai" : "neutral"}>{ai.ai_enabled ? ai.model : "server key not set"}</Badge>}</>}
            hint="Natural-language orders and rules, deeper move explanations and portfolio Q&A use Claude. Without it, the instant parser and rules engine still work."
            control={<Switch checked={user.ai_enabled} onChange={(v) => patch({ ai_enabled: v })} label="AI features" />}
          />
          <Row
            title="Pause all automations"
            hint="A kill switch: rules stay saved but nothing fires while this is on."
            control={<Switch checked={user.rules_paused} onChange={(v) => patch({ rules_paused: v })} label="Pause automations" />}
          />
        </div>
      </Card>
      <Card>
        <CardHeader title="Appearance" />
        <Row title="Dark mode" hint="Easier on the eyes for long sessions." control={<Switch checked={theme === "dark"} onChange={toggleTheme} label="Dark mode" />} />
      </Card>
      <Card>
        <CardHeader title="Paper account" />
        <Row
          title="Reset account"
          hint="Cancels open orders, closes all positions and restores your starting cash. This can't be undone."
          control={<Button variant="danger" size="sm" onClick={() => setConfirmReset(true)}>Reset</Button>}
        />
      </Card>
      <p className="text-center text-2xs text-faint">TradeAllN is a paper-trading platform: real market data, virtual money. Prices come from Yahoo Finance and may be delayed. Nothing here is investment advice.</p>
      <Modal open={confirmReset} onClose={() => setConfirmReset(false)} title="Reset paper account?">
        <div className="p-5 text-sm text-muted">All positions, open orders and history snapshots will be cleared.</div>
        <div className="flex justify-end gap-2 border-t border-line px-5 py-3">
          <Button variant="ghost" onClick={() => setConfirmReset(false)}>Cancel</Button>
          <Button variant="down" onClick={reset}>Reset account</Button>
        </div>
      </Modal>
    </div>
  );
}

function Row({ title, hint, control }: { title: React.ReactNode; hint: string; control: React.ReactNode }) {
  return (
    <div className="flex items-center justify-between gap-6 px-5 py-4">
      <div>
        <div className="flex items-center gap-2 text-sm font-medium">{title}</div>
        <div className="mt-0.5 text-xs text-muted">{hint}</div>
      </div>
      {control}
    </div>
  );
}
