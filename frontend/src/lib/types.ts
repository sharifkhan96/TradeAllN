export type Quote = {
  symbol: string;
  price: number;
  prev_close: number;
  open: number;
  high: number;
  low: number;
  volume: number;
  change: number;
  change_pct: number;
  t?: number;
  ext_price?: number | null;
  ext_change_pct?: number | null;
  ext_session?: "pre" | "post" | null;
};

export type Stock = {
  symbol: string;
  name: string;
  exchange: string;
  sector: string;
  industry?: string;
  is_etf: boolean;
  quote: Quote | null;
};

export type StockDetail = Stock & {
  description: string;
  market_cap: number | null;
  pe_ratio: string | null;
  dividend_yield: string | null;
  beta: string;
  sector_etf: string;
  is_tradable: boolean;
  ceo: string;
  employees: number | null;
  website: string;
  hq: string;
  stats: { week52_high: number | null; week52_low: number | null; avg_volume: number | null };
  peers?: Stock[];
};

export type Bar = { t: number; o: number; h: number; l: number; c: number; v: number };

export type User = {
  id: number;
  email: string;
  display_name: string;
  name: string;
  timezone: string;
  ai_enabled: boolean;
  rules_paused: boolean;
};

export type Order = {
  id: string;
  symbol: string;
  name: string;
  side: "buy" | "sell";
  type: "market" | "limit" | "stop" | "stop_limit";
  time_in_force: "day" | "gtc";
  quantity: string;
  limit_price: string | null;
  stop_price: string | null;
  filled_qty: string;
  avg_fill_price: string | null;
  status: string;
  reject_reason: string;
  source: string;
  extended_hours: boolean;
  notional: string | null;
  created_at: string;
  filled_at: string | null;
};

export type Position = {
  symbol: string;
  name: string;
  sector: string;
  quantity: number;
  available: number;
  avg_cost: number;
  price: number;
  market_value: number;
  cost_basis: number;
  unrealized_pnl: number;
  unrealized_pct: number;
  day_pnl: number;
  day_pct: number;
  realized_pnl: number;
  weight: number;
};

export type Summary = {
  equity: number;
  cash: number;
  buying_power: number;
  reserved_cash: number;
  positions_value: number;
  day_pnl: number;
  day_pct: number;
  total_pnl: number;
  total_pct: number;
  unrealized_pnl: number;
  realized_pnl: number;
  starting_cash: number;
  positions_count: number;
};

export type News = {
  id: number;
  headline: string;
  summary: string;
  source: string;
  url: string;
  kind: string;
  published_at: string;
  sentiment: number;
  importance: number;
  sector: string;
  is_simulated: boolean;
  symbols: string[];
};

export type Explanation = {
  summary: string;
  category: string;
  confidence: "low" | "medium" | "high";
  method: "rules" | "llm";
  model?: string;
  citations: { relevance: string; article: News }[];
};

export type Move = {
  id: number | null;
  timeframe: string;
  start: string;
  end: string;
  start_t: number;
  end_t: number;
  start_price: number;
  end_price: number;
  pct_change: number;
  direction: "up" | "down" | "flat";
  z: number;
  market_pct: number | null;
  sector_pct: number | null;
  residual_pct: number | null;
  volume_ratio: number | null;
  explanation: Explanation | null;
};

export type Readable = { when: { logic: string; items: (string | Readable["when"])[] }; then: string; mode: string };

export type Rule = {
  id: number;
  name: string;
  source_text: string;
  spec: Record<string, unknown>;
  readable: Readable | null;
  status: "active" | "paused" | "triggered" | "expired" | "error";
  status_message: string;
  last_condition: boolean;
  last_evaluated_at: string | null;
  last_triggered_at: string | null;
  trigger_count: number;
  expires_at: string | null;
  created_at: string;
  executions?: { id: number; triggered_at: string; result: string; success: boolean; order_id: string | null }[];
};

export type Backtest = {
  supported: boolean;
  note: string | null;
  triggers: { date: string; price: number; return_since_pct: number }[];
  symbol?: string;
  series?: { date: string; close: number }[];
  days?: number;
};

export type RulePreview = {
  spec: Record<string, unknown>;
  readable: Readable;
  method: string;
  source_text: string;
  currently_true: boolean;
  backtest: Backtest;
};

export type OrderPreviewItem = {
  symbol: string;
  name?: string;
  side: "buy" | "sell";
  type: string;
  time_in_force: string;
  quantity?: number;
  price?: number;
  limit_price: number | null;
  stop_price: number | null;
  est_value: number;
  error?: string;
  warnings?: string[];
};

export type CommandPreview =
  | { kind: "orders"; items: OrderPreviewItem[]; warnings: string[]; totals: { buy: number; sell: number; buying_power_after: number }; executable: boolean }
  | { kind: "cancel"; orders: { id: string; symbol: string; side: string; type: string; quantity: number; limit_price: number | null; stop_price: number | null }[]; warnings: string[]; executable: boolean }
  | ({ kind: "rule"; executable: boolean } & RulePreview)
  | { kind: "navigate"; symbol: string; executable: false }
  | { kind: "answer"; answer: string; method: string; executable: false }
  | { kind: "message"; message: string; executable: false };

export type Command = {
  id: string;
  input: string;
  intent: string;
  method: string;
  preview: CommandPreview;
  status: string;
  result: { results?: { symbol?: string; ok: boolean; error?: string; status?: string; fill_price?: number }[] };
};

export type Insights = {
  symbol: string;
  unavailable?: boolean;
  analysts?: { buy: number; hold: number; sell: number; total: number; buy_pct: number | null; consensus: string };
  price_target?: { low: number | null; mean: number | null; median: number | null; high: number | null; current: number | null };
  earnings?: { date: string; estimate: number | null; actual: number | null; surprise_pct: number | null }[];
  next_earnings?: string | null;
  dividends?: { date: string; amount: number }[];
  ex_dividend_date?: string | null;
  dividend_rate?: number | null;
  fundamentals?: Record<string, number | null>;
};

export type Recurring = {
  id: number;
  symbol: string;
  name: string;
  amount: string;
  frequency: "daily" | "weekly" | "biweekly" | "monthly";
  next_run: string;
  active: boolean;
  last_run_at: string | null;
  last_result: string;
  total_invested: string;
};

export type MarketStatus = {
  status: string;
  simulated: boolean;
  label: string;
  now: string;
  provider: string;
  source: string;
  opens_at?: string;
  closes_at?: string;
};
