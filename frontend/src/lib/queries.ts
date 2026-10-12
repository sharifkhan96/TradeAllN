import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "./api";
import type {
  Bar, Command, MarketStatus, Move, News, Order, Position, Rule, RulePreview, Stock, StockDetail, Summary,
} from "./types";

export const qk = {
  summary: ["portfolio", "summary"],
  positions: ["portfolio", "positions"],
  history: ["portfolio", "history"],
  analytics: ["portfolio", "analytics"],
  orders: (status?: string) => ["orders", status ?? "all"],
  rules: ["rules"],
  watchlists: ["watchlists"],
};

export const useSummary = () =>
  useQuery({ queryKey: qk.summary, queryFn: () => api<Summary>("/portfolio/summary"), refetchInterval: 5000 });
export const usePositions = () =>
  useQuery({ queryKey: qk.positions, queryFn: () => api<Position[]>("/portfolio/positions"), refetchInterval: 5000 });
export const useHistory = () =>
  useQuery({
    queryKey: qk.history,
    queryFn: () => api<{ date: string; equity: number; benchmark?: number | null }[]>("/portfolio/history"),
    refetchInterval: 30000,
  });
export type Analytics = {
  total_return_pct: number;
  benchmark_return_pct: number | null;
  volatility_pct: number;
  sharpe: number | null;
  max_drawdown_pct: number;
  win_rate_pct: number | null;
  closed_trades: number;
  best_trade: number | null;
  worst_trade: number | null;
  sector_allocation: { sector: string; value: number }[];
  top_weight_pct: number;
};
export const useAnalytics = () =>
  useQuery({ queryKey: qk.analytics, queryFn: () => api<Analytics>("/portfolio/analytics"), refetchInterval: 30000 });

export const useOrders = (status?: string) =>
  useQuery({
    queryKey: qk.orders(status),
    queryFn: () => api<Order[]>(`/orders${status ? `?status=${status}` : ""}`),
    refetchInterval: 10000,
  });

export const useStocks = (search = "") =>
  useQuery({
    queryKey: ["stocks", search],
    queryFn: () => api<Stock[]>(`/stocks?search=${encodeURIComponent(search)}&limit=${search ? 8 : 100}`),
    placeholderData: keepPreviousData,
    staleTime: 10000,
  });

export const useStock = (symbol: string) =>
  useQuery({ queryKey: ["stock", symbol], queryFn: () => api<StockDetail>(`/stocks/${symbol}`), staleTime: 30000, retry: false });

export const useBars = (symbol: string, range: string, enabled = true) =>
  useQuery({
    enabled,
    queryKey: ["bars", symbol, range],
    queryFn: () => api<{ timeframe: string; bars: Bar[] }>(`/stocks/${symbol}/bars?range=${range}`),
    placeholderData: keepPreviousData,
    staleTime: range === "LIVE" ? 0 : 30000,
  });

export const useMoves = (symbol: string, range: string, enabled = true) =>
  useQuery({
    enabled,
    queryKey: ["moves", symbol, range],
    queryFn: () => api<{ timeframe: string; moves: Move[] }>(`/stocks/${symbol}/moves?range=${range}`),
    staleTime: 60000,
    refetchInterval: range === "LIVE" ? 15000 : range === "1D" ? 60000 : false,
  });

export const useNews = (symbol?: string, enabled = true) =>
  useQuery({
    enabled,
    queryKey: ["news", symbol ?? "all"],
    queryFn: () => api<News[]>(`/news${symbol ? `?symbol=${symbol}&limit=30` : "?limit=30"}`),
    refetchInterval: 60000,
  });

export const useMarketStatus = () =>
  useQuery({ queryKey: ["market-status"], queryFn: () => api<MarketStatus>("/market/status"), refetchInterval: 60000 });

export type OverviewRow = { symbol: string; name: string; price: number; change_pct: number; volume: number; sector?: string };
export const useOverview = () =>
  useQuery({
    queryKey: ["overview"],
    queryFn: () =>
      api<{
        status: MarketStatus;
        indices: OverviewRow[];
        sectors: OverviewRow[];
        gainers: OverviewRow[];
        losers: OverviewRow[];
        active: OverviewRow[];
        heatmap: OverviewRow[];
      }>("/market/overview"),
    refetchInterval: 10000,
  });

export const useRules = () => useQuery({ queryKey: qk.rules, queryFn: () => api<Rule[]>("/rules"), refetchInterval: 10000 });

export type Watchlist = { id: number; name: string; items: { symbol: string; name: string; quote: Stock["quote"] }[] };
export const useWatchlists = () => useQuery({ queryKey: qk.watchlists, queryFn: () => api<Watchlist[]>("/watchlists") });

export const useCalendar = () =>
  useQuery({
    queryKey: ["calendar"],
    queryFn: () => api<{ id: number; symbol: string | null; kind: string; ts: string; title: string; payload: Record<string, unknown> }[]>("/calendar"),
    staleTime: 60000,
  });

export const useLeaderboard = () =>
  useQuery({
    queryKey: ["leaderboard"],
    queryFn: () =>
      api<{ rank: number; name: string; is_you: boolean; equity: number; return_pct: number; day_pct: number; positions: number }[]>(
        "/leaderboard",
      ),
    refetchInterval: 15000,
  });

export const useAIStatus = () =>
  useQuery({
    queryKey: ["ai-status"],
    queryFn: () => api<{ ai_enabled: boolean; user_ai_enabled: boolean; model: string | null }>("/assistant/status"),
    staleTime: 60000,
  });

export function useInvalidateTrading() {
  const qc = useQueryClient();
  return () => {
    qc.invalidateQueries({ queryKey: ["portfolio"] });
    qc.invalidateQueries({ queryKey: ["orders"] });
    qc.invalidateQueries({ queryKey: ["accounts"] });
  };
}

export const useParseCommand = () =>
  useMutation({ mutationFn: (text: string) => api<Command>("/assistant/parse", { json: { text } }) });

export const useCompileRule = () =>
  useMutation({ mutationFn: (text: string) => api<RulePreview>("/rules/compile", { json: { text } }) });

export const useInsights = (symbol: string, enabled = true) =>
  useQuery({
    queryKey: ["insights", symbol],
    queryFn: () => api<import("./types").Insights>(`/stocks/${symbol}/insights`),
    staleTime: 10 * 60 * 1000,
    enabled,
  });

export const useRecurring = () =>
  useQuery({ queryKey: ["portfolio", "recurring"], queryFn: () => api<import("./types").Recurring[]>("/recurring") });

export const useDividends = () =>
  useQuery({
    queryKey: ["portfolio", "dividends"],
    queryFn: () => api<{ symbol: string; ex_date: string; per_share: string; quantity: string; amount: string; paid_at: string }[]>("/dividends"),
  });

export const useLedger = () =>
  useQuery({
    queryKey: ["portfolio", "ledger"],
    queryFn: () => api<{ id: number; type: string; amount: string; balance_after: string; reference: string; created_at: string }[]>("/ledger"),
  });

export type ScreenRow = { symbol: string; name: string; price: number; change_pct: number; volume: number; market_cap?: number };
export type Collection = {
  slug: string;
  name: string;
  emoji: string;
  avg_change_pct: number | null;
  items: { symbol: string; name: string; quote: import("./types").Quote | null }[];
};
export const useDiscover = () =>
  useQuery({
    queryKey: ["discover"],
    queryFn: () =>
      api<{ gainers: ScreenRow[]; losers: ScreenRow[]; active: ScreenRow[]; popular: { symbol: string; name: string; holders: number }[]; collections: Collection[] }>(
        "/discover",
      ),
    refetchInterval: 60000,
  });

export type ClosedTrade = {
  symbol: string;
  name: string;
  sector: string;
  opened_at: string | null;
  closed_at: string;
  quantity: number;
  entry: number | null;
  exit: number;
  pnl: number;
  return_pct: number;
  held_days: number;
};
export type Performance = {
  period: string;
  summary: {
    closed_trades: number;
    wins: number;
    losses: number;
    breakeven: number;
    win_rate_pct: number | null;
    net_pnl: number;
    gross_profit: number;
    gross_loss: number;
    profit_factor: number | null;
    avg_win: number | null;
    avg_loss: number | null;
    payoff_ratio: number | null;
    expectancy: number | null;
    avg_return_pct: number | null;
    largest_win: ClosedTrade | null;
    largest_loss: ClosedTrade | null;
    avg_hold_days_win: number | null;
    avg_hold_days_loss: number | null;
    fees: number;
    max_win_streak: number;
    max_loss_streak: number;
    current: { kind: "win" | "loss" | null; length: number };
  };
  activity: { orders: number; filled: number; cancelled: number; rejected: number; by_source: Record<string, number>; buy_volume: number };
  open_positions: { count: number; winners: number; losers: number; unrealized_pnl: number; best: { symbol: string; unrealized_pct: number } | null; worst: { symbol: string; unrealized_pct: number } | null };
  by_symbol: { symbol: string; name: string; pnl: number; trades: number; wins: number }[];
  by_sector: { sector: string; pnl: number }[];
  monthly: { month: string; pnl: number; trades: number; wins: number }[];
  distribution: { bucket: string; count: number; positive: boolean }[];
  cumulative: { date: string; pnl: number }[];
  recent: ClosedTrade[];
  risk: {
    days: number;
    sortino?: number | null;
    best_day?: { date: string; pct: number };
    worst_day?: { date: string; pct: number };
    positive_days_pct?: number;
    beta?: number;
    alpha_annual_pct?: number;
    correlation?: number | null;
    cagr_pct?: number | null;
    calmar?: number | null;
  };
};
export const usePerformance = (period: string) =>
  useQuery({
    queryKey: ["portfolio", "performance", period],
    queryFn: () => api<Performance>(`/portfolio/performance?period=${period}`),
    placeholderData: keepPreviousData,
    refetchInterval: 60000,
  });
