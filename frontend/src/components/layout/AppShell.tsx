import {
  Activity, BarChart3, Bot, BriefcaseBusiness, Command, Compass, LayoutDashboard, ListOrdered, LogOut, Moon,
  Search, Settings, Sparkles, Sun, Trophy, Workflow,
} from "lucide-react";
import { useEffect, useState, type ReactNode } from "react";
import { NavLink, Outlet, useNavigate } from "react-router-dom";
import { AskPanel } from "@/components/AskPanel";
import { CommandPalette } from "@/components/CommandPalette";
import { ChangePill, useLiveQuote } from "@/components/Live";
import { Button } from "@/components/ui";
import { api } from "@/lib/api";
import { cn } from "@/lib/cn";
import { countdown, price } from "@/lib/format";
import { useMarketStatus, useOverview, usePositions, useWatchlists } from "@/lib/queries";
import { useAuth } from "@/stores/auth";
import { useLive } from "@/stores/live";
import { useUI } from "@/stores/ui";
import { LiveEvents } from "./LiveEvents";

const NAV = [
  { to: "/", label: "Dashboard", icon: LayoutDashboard, end: true },
  { to: "/discover", label: "Discover", icon: Compass },
  { to: "/markets", label: "Markets", icon: BarChart3 },
  { to: "/portfolio", label: "Portfolio", icon: BriefcaseBusiness },
  { to: "/orders", label: "Orders", icon: ListOrdered },
  { to: "/rules", label: "Automations", icon: Workflow },
  { to: "/leaderboard", label: "Leaderboard", icon: Trophy },
];

export function Logo({ className }: { className?: string }) {
  return (
    <div className={cn("flex items-center gap-2.5", className)}>
      <img src="/logo.svg" alt="" className="h-8 w-8" />
      <span className="text-[15px] font-semibold tracking-tight">
        TradeAll<span className="text-ai">N</span>
      </span>
    </div>
  );
}

function Sidebar() {
  const user = useAuth((s) => s.user);
  const { theme, toggleTheme } = useUI();
  const navigate = useNavigate();
  const logout = async () => {
    await api("/auth/logout", { method: "POST" }).catch(() => undefined);
    useAuth.getState().clear();
    navigate("/login");
  };
  return (
    <aside className="hidden w-[232px] shrink-0 flex-col border-r border-line bg-panel/60 lg:flex">
      <div className="px-5 pb-4 pt-5">
        <Logo />
      </div>
      <nav className="flex-1 space-y-0.5 px-3">
        {NAV.map(({ to, label, icon: Icon, end }) => (
          <NavLink
            key={to}
            to={to}
            end={end}
            className={({ isActive }) =>
              cn(
                "group flex h-9 items-center gap-3 rounded-lg px-3 text-sm font-medium transition-colors",
                isActive ? "bg-panel2 text-fg ring-1 ring-line" : "text-muted hover:bg-panel2/60 hover:text-fg",
              )
            }
          >
            <Icon className="h-4 w-4" />
            {label}
          </NavLink>
        ))}
        <button
          onClick={() => useUI.getState().setAsk(true)}
          className="mt-3 flex h-9 w-full items-center gap-3 rounded-lg px-3 text-sm font-medium text-ai transition-colors hover:bg-ai/10"
        >
          <Sparkles className="h-4 w-4" /> Ask your portfolio
        </button>
      </nav>
      <DataSource />
      <div className="space-y-1 border-t border-line p-3">
        <NavLink
          to="/settings"
          className={({ isActive }) =>
            cn("flex h-9 items-center gap-3 rounded-lg px-3 text-sm font-medium", isActive ? "bg-panel2 text-fg" : "text-muted hover:bg-panel2/60 hover:text-fg")
          }
        >
          <Settings className="h-4 w-4" /> Settings
        </NavLink>
        <button onClick={toggleTheme} className="flex h-9 w-full items-center gap-3 rounded-lg px-3 text-sm font-medium text-muted hover:bg-panel2/60 hover:text-fg">
          {theme === "dark" ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
          {theme === "dark" ? "Light mode" : "Dark mode"}
        </button>
        <div className="mt-2 flex items-center gap-2.5 rounded-lg px-2 py-2">
          <div className="ai-gradient grid h-8 w-8 place-items-center rounded-full text-xs font-semibold text-white">
            {(user?.name ?? "?").slice(0, 1).toUpperCase()}
          </div>
          <div className="min-w-0 flex-1">
            <div className="truncate text-sm font-medium">{user?.name}</div>
            <div className="truncate text-2xs text-muted">Paper account</div>
          </div>
          <Button variant="ghost" size="icon" onClick={logout} title="Log out" aria-label="Log out">
            <LogOut className="h-4 w-4" />
          </Button>
        </div>
      </div>
    </aside>
  );
}

function DataSource() {
  const { data } = useMarketStatus();
  if (!data) return null;
  return (
    <div className="px-5 pb-3 text-2xs leading-relaxed text-faint">
      {data.simulated ? "Simulated prices and news" : <>Prices: {data.source}{data.source === "Yahoo Finance" && " (may be delayed)"}<br />News: Yahoo, Google News, SEC EDGAR</>}
    </div>
  );
}

function TapeItem({ symbol, fallback }: { symbol: string; fallback: { price: number; change_pct: number } }) {
  const q = useLiveQuote(symbol, fallback);
  return (
    <NavLink to={`/stocks/${symbol}`} className="flex items-center gap-2 px-4 text-xs hover:text-fg">
      <span className="font-semibold text-fg/90">{symbol}</span>
      <span className="num text-muted">{price(q.price)}</span>
      <span className={cn("num", q.change_pct >= 0 ? "text-up" : "text-down")}>
        {q.change_pct >= 0 ? "▲" : "▼"} {Math.abs(q.change_pct).toFixed(2)}%
      </span>
    </NavLink>
  );
}

function TickerTape() {
  const { data } = useOverview();
  const rows = [...(data?.indices ?? []), ...(data?.heatmap ?? []).slice(0, 18)];
  if (!rows.length) return <div className="h-9 border-b border-line" />;
  return (
    <div className="relative h-9 overflow-hidden border-b border-line bg-panel/40">
      <div className="flex h-full w-max animate-marquee items-center hover:[animation-play-state:paused]">
        {[...rows, ...rows].map((r, i) => (
          <TapeItem key={`${r.symbol}-${i}`} symbol={r.symbol} fallback={r} />
        ))}
      </div>
      <div className="pointer-events-none absolute inset-y-0 left-0 w-12 bg-gradient-to-r from-bg to-transparent" />
      <div className="pointer-events-none absolute inset-y-0 right-0 w-12 bg-gradient-to-l from-bg to-transparent" />
    </div>
  );
}

function MarketPill() {
  const { data } = useMarketStatus();
  const connected = useLive((s) => s.connected);
  const open = data?.status === "open";
  const [, force] = useState(0);
  useEffect(() => {
    const id = setInterval(() => force((x) => x + 1), 30000);
    return () => clearInterval(id);
  }, []);
  return (
    <div
      className="hidden items-center gap-2 rounded-full border border-line bg-panel px-3 py-1 text-xs text-muted md:flex"
      title={`${data?.label ?? ""} · data: ${data?.source ?? ""}`}
    >
      <span className={cn("h-1.5 w-1.5 rounded-full", open ? "animate-pulseDot bg-up" : "bg-faint")} />
      <span className="font-medium text-fg/90">{open ? "Market open" : data?.label ?? "…"}</span>
      {data?.simulated && <span className="text-faint">· simulated</span>}
      {!data?.simulated && data?.opens_at && <span className="text-faint">· opens {countdown(data.opens_at)}</span>}
      {!data?.simulated && data?.closes_at && <span className="text-faint">· closes {countdown(data.closes_at)}</span>}
      <span className={cn("ml-1 flex items-center gap-1", connected ? "text-up" : "text-warn")}>
        <Activity className="h-3 w-3" /> {connected ? "Live" : "Connecting"}
      </span>
    </div>
  );
}

function SpyMini() {
  const q = useLiveQuote("SPY");
  return (
    <div className="hidden items-center gap-2 text-xs xl:flex">
      <span className="text-muted">S&P 500</span>
      <ChangePill value={q.change_pct} />
    </div>
  );
}

function Topbar() {
  const openPalette = useUI((s) => s.openPalette);
  return (
    <header className="flex h-14 shrink-0 items-center gap-3 border-b border-line px-4 lg:px-6">
      <Logo className="lg:hidden" />
      <button
        onClick={() => openPalette()}
        className="focus-ring group flex h-9 max-w-xl flex-1 items-center gap-2.5 rounded-lg border border-line bg-panel px-3 text-left text-sm text-faint transition-colors hover:border-ai/40"
      >
        <Search className="h-4 w-4" />
        <span className="flex-1 truncate">
          Search, trade or ask — <span className="text-muted">“buy $500 of Apple”</span>,{" "}
          <span className="hidden text-muted sm:inline">“if NVDA drops 5% buy 10”</span>
        </span>
        <kbd className="hidden items-center gap-0.5 rounded border border-line bg-panel2 px-1.5 py-0.5 font-mono text-2xs text-muted sm:flex">
          <Command className="h-3 w-3" />K
        </kbd>
      </button>
      <div className="ml-auto flex items-center gap-3">
        <SpyMini />
        <MarketPill />
        <Button variant="ai" size="sm" onClick={() => useUI.getState().setAsk(true)} className="hidden sm:inline-flex">
          <Bot className="h-4 w-4" /> Ask
        </Button>
      </div>
    </header>
  );
}

function MobileNav() {
  return (
    <nav className="fixed inset-x-0 bottom-0 z-30 flex h-14 items-center justify-around border-t border-line bg-panel/95 backdrop-blur lg:hidden">
      {NAV.slice(0, 5).map(({ to, icon: Icon, label, end }) => (
        <NavLink key={to} to={to} end={end} className={({ isActive }) => cn("flex flex-col items-center gap-0.5 text-2xs", isActive ? "text-fg" : "text-muted")}>
          <Icon className="h-4 w-4" />
          {label}
        </NavLink>
      ))}
    </nav>
  );
}

function WatchedSync() {
  // Keep a set of symbols the user cares about, so live toasts only fire for those.
  const { data: pos } = usePositions();
  const { data: wls } = useWatchlists();
  useEffect(() => {
    const s = [...(pos ?? []).map((p) => p.symbol), ...(wls ?? []).flatMap((w) => w.items.map((i) => i.symbol))];
    useLive.getState().setWatched(s);
  }, [pos, wls]);
  return null;
}

export function AppShell({ children }: { children?: ReactNode }) {
  const openPalette = useUI((s) => s.openPalette);
  useEffect(() => {
    const k = (e: KeyboardEvent) => {
      const typing = ["INPUT", "TEXTAREA"].includes((e.target as HTMLElement)?.tagName);
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        openPalette();
      } else if (e.key === "/" && !typing) {
        e.preventDefault();
        openPalette();
      }
    };
    window.addEventListener("keydown", k);
    return () => window.removeEventListener("keydown", k);
  }, [openPalette]);
  return (
    <div className="flex h-full">
      <Sidebar />
      <div className="flex min-w-0 flex-1 flex-col">
        <Topbar />
        <TickerTape />
        <main className="min-h-0 flex-1 overflow-y-auto pb-16 lg:pb-0">
          <div className="mx-auto w-full max-w-[1440px] p-4 lg:p-6">{children ?? <Outlet />}</div>
        </main>
      </div>
      <MobileNav />
      <CommandPalette />
      <AskPanel />
      <LiveEvents />
      <WatchedSync />
    </div>
  );
}

