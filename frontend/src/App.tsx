import { useEffect, type ReactNode } from "react";
import { Navigate, Route, Routes, useLocation } from "react-router-dom";
import { Toaster } from "sonner";
import { AppShell } from "@/components/layout/AppShell";
import { Spinner } from "@/components/ui";
import { refreshSession } from "@/lib/api";
import { DashboardPage } from "@/pages/Dashboard";
import { DiscoverPage } from "@/pages/Discover";
import { LeaderboardPage } from "@/pages/Leaderboard";
import { LoginPage } from "@/pages/Login";
import { MarketsPage } from "@/pages/Markets";
import { OrdersPage } from "@/pages/Orders";
import { PortfolioPage } from "@/pages/Portfolio";
import { RulesPage } from "@/pages/Rules";
import { SettingsPage } from "@/pages/Settings";
import { StockPage } from "@/pages/Stock";
import { useAuth } from "@/stores/auth";
import { connectLive } from "@/stores/live";
import { useUI } from "@/stores/ui";

function RequireAuth({ children }: { children: ReactNode }) {
  const { user, ready } = useAuth();
  const loc = useLocation();
  if (!ready)
    return (
      <div className="grid h-full place-items-center">
        <Spinner className="h-6 w-6" />
      </div>
    );
  if (!user) return <Navigate to="/login" state={{ from: loc.pathname }} replace />;
  return <>{children}</>;
}

export function App() {
  const access = useAuth((s) => s.access);
  const theme = useUI((s) => s.theme);

  useEffect(() => {
    refreshSession().finally(() => useAuth.getState().setReady());
    // refresh the short-lived access token before it expires
    const id = setInterval(() => useAuth.getState().access && refreshSession(), 10 * 60 * 1000);
    return () => clearInterval(id);
  }, []);

  useEffect(() => {
    connectLive(access);
  }, [access]);

  return (
    <>
      <Routes>
        <Route path="/login" element={<LoginPage mode="login" />} />
        <Route path="/register" element={<LoginPage mode="register" />} />
        <Route
          element={
            <RequireAuth>
              <AppShell />
            </RequireAuth>
          }
        >
          <Route index element={<DashboardPage />} />
          <Route path="discover" element={<DiscoverPage />} />
          <Route path="markets" element={<MarketsPage />} />
          <Route path="stocks/:symbol" element={<StockPage />} />
          <Route path="portfolio" element={<PortfolioPage />} />
          <Route path="orders" element={<OrdersPage />} />
          <Route path="rules" element={<RulesPage />} />
          <Route path="leaderboard" element={<LeaderboardPage />} />
          <Route path="settings" element={<SettingsPage />} />
        </Route>
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
      <Toaster
        theme={theme}
        position="bottom-right"
        toastOptions={{
          style: { background: "rgb(var(--panel))", border: "1px solid rgb(var(--line))", color: "rgb(var(--fg))" },
        }}
      />
    </>
  );
}
