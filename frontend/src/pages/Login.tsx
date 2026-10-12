import { ArrowRight, Bot, LineChart, ShieldCheck, Workflow } from "lucide-react";
import { useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { Logo } from "@/components/layout/AppShell";
import { Button, Input } from "@/components/ui";
import { api } from "@/lib/api";
import type { User } from "@/lib/types";
import { useAuth } from "@/stores/auth";

const FEATURES = [
  { icon: LineChart, title: "Know why it moved", text: "Every stretch of every chart is tied to the news, filings and macro events behind it." },
  { icon: Bot, title: "Trade in plain English", text: "“Sell half my Tesla”. You always review and confirm first." },
  { icon: Workflow, title: "Automate with words", text: "“If NVDA drops 5% and RSI < 30, buy $2,000”, backtested before you activate it." },
];

export function LoginPage({ mode }: { mode: "login" | "register" }) {
  const navigate = useNavigate();
  const loc = useLocation();
  const [email, setEmail] = useState(mode === "login" && import.meta.env.DEV ? "demo@tradeall.app" : "");
  const [password, setPassword] = useState(mode === "login" && import.meta.env.DEV ? "demo-trader-2026" : "");
  const [name, setName] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      const body = mode === "login" ? { email, password } : { email, password, display_name: name };
      const r = await api<{ access: string; user: User }>(`/auth/${mode}`, { json: body });
      useAuth.getState().setSession(r.access, r.user);
      navigate((loc.state as { from?: string })?.from ?? "/", { replace: true });
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="grid min-h-full lg:grid-cols-[1.1fr_1fr]">
      <div className="relative hidden overflow-hidden border-r border-line bg-panel lg:block">
        <div className="absolute inset-0 opacity-60 [background:radial-gradient(60%_50%_at_20%_10%,rgb(var(--ai)/0.25),transparent),radial-gradient(50%_40%_at_90%_90%,rgb(var(--up)/0.18),transparent)]" />
        <svg className="absolute inset-x-0 bottom-0 h-1/2 w-full opacity-70" viewBox="0 0 600 200" preserveAspectRatio="none">
          <defs>
            <linearGradient id="hero" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0" stopColor="rgb(var(--up))" stopOpacity="0.35" />
              <stop offset="1" stopColor="rgb(var(--up))" stopOpacity="0" />
            </linearGradient>
          </defs>
          <path d="M0 170 L40 160 L80 165 L120 140 L160 150 L200 120 L240 128 L280 96 L320 104 L360 70 L400 82 L440 52 L480 60 L520 34 L560 40 L600 18 L600 200 L0 200Z" fill="url(#hero)" />
          <path d="M0 170 L40 160 L80 165 L120 140 L160 150 L200 120 L240 128 L280 96 L320 104 L360 70 L400 82 L440 52 L480 60 L520 34 L560 40 L600 18" fill="none" stroke="rgb(var(--up))" strokeWidth="2" />
          {[[200, 120], [360, 70], [520, 34]].map(([x, y]) => (
            <circle key={x} cx={x} cy={y} r="5" fill="rgb(var(--ai))" stroke="rgb(var(--panel))" strokeWidth="3" />
          ))}
        </svg>
        <div className="relative flex h-full flex-col p-12">
          <Logo />
          <div className="mt-auto mb-40 max-w-md">
            <h1 className="text-4xl font-semibold leading-tight tracking-tight">
              Every price move,
              <br />
              <span className="bg-gradient-to-r from-ai to-accent bg-clip-text text-transparent">explained.</span>
            </h1>
            <p className="mt-4 text-muted">Paper-trade US stocks with real market prices and real news. See why things move and trade in plain English.</p>
            <div className="mt-8 space-y-5">
              {FEATURES.map(({ icon: Icon, title, text }) => (
                <div key={title} className="flex gap-3">
                  <div className="grid h-9 w-9 shrink-0 place-items-center rounded-lg border border-line bg-panel2 text-ai">
                    <Icon className="h-4 w-4" />
                  </div>
                  <div>
                    <div className="text-sm font-semibold">{title}</div>
                    <div className="text-sm text-muted">{text}</div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
      <div className="flex items-center justify-center p-6">
        <form onSubmit={submit} className="w-full max-w-sm">
          <Logo className="mb-10 lg:hidden" />
          <h2 className="text-2xl font-semibold tracking-tight">{mode === "login" ? "Welcome back" : "Create your account"}</h2>
          <p className="mt-1.5 text-sm text-muted">
            {mode === "login" ? "Sign in to your paper trading account." : "Start with $100,000 in virtual cash."}
          </p>
          <div className="mt-8 space-y-3">
            {mode === "register" && (
              <label className="block">
                <span className="label">Display name</span>
                <Input className="mt-1.5" value={name} onChange={(e) => setName(e.target.value)} placeholder="Alex Trader" />
              </label>
            )}
            <label className="block">
              <span className="label">Email</span>
              <Input className="mt-1.5" type="email" required value={email} onChange={(e) => setEmail(e.target.value)} autoComplete="email" />
            </label>
            <label className="block">
              <span className="label">Password</span>
              <Input
                className="mt-1.5"
                type="password"
                required
                minLength={8}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                autoComplete={mode === "login" ? "current-password" : "new-password"}
              />
            </label>
          </div>
          {error && <p className="mt-3 rounded-lg border border-down/30 bg-down/10 px-3 py-2 text-sm text-down">{error}</p>}
          <Button type="submit" variant="primary" size="lg" loading={busy} className="mt-6 w-full justify-center">
            {mode === "login" ? "Sign in" : "Create account"} <ArrowRight className="h-4 w-4" />
          </Button>
          {mode === "login" && import.meta.env.DEV && (
            <p className="mt-3 text-center text-xs text-faint">The demo account is pre-filled with a portfolio and automations.</p>
          )}
          <p className="mt-6 text-center text-sm text-muted">
            {mode === "login" ? "New here? " : "Already have an account? "}
            <Link to={mode === "login" ? "/register" : "/login"} className="font-medium text-fg hover:underline">
              {mode === "login" ? "Create an account" : "Sign in"}
            </Link>
          </p>
          <p className="mt-10 flex items-center justify-center gap-1.5 text-2xs text-faint">
            <ShieldCheck className="h-3 w-3" /> Paper trading with virtual money. Not investment advice.
          </p>
        </form>
      </div>
    </div>
  );
}
