const usd = new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" });
const usd0 = new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 0 });
const compact = new Intl.NumberFormat("en-US", { notation: "compact", maximumFractionDigits: 2 });

export const n = (v: unknown): number => (typeof v === "number" ? v : v == null || v === "" ? NaN : Number(v));

export function money(v: unknown, opts: { sign?: boolean; whole?: boolean } = {}) {
  const x = n(v);
  if (!Number.isFinite(x)) return "—";
  const s = (opts.whole ? usd0 : usd).format(Math.abs(x));
  if (opts.sign) return `${x >= 0 ? "+" : "−"}${s}`;
  return x < 0 ? `−${s}` : s;
}

export function price(v: unknown) {
  const x = n(v);
  if (!Number.isFinite(x)) return "—";
  return x.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

export function pct(v: unknown, digits = 2, sign = true) {
  const x = n(v);
  if (!Number.isFinite(x)) return "—";
  return `${sign && x > 0 ? "+" : x < 0 ? "−" : ""}${Math.abs(x).toFixed(digits)}%`;
}

export const big = (v: unknown) => {
  const x = n(v);
  return Number.isFinite(x) ? compact.format(x) : "—";
};

export const qty = (v: unknown) => {
  const x = n(v);
  return Number.isFinite(x) ? x.toLocaleString("en-US", { maximumFractionDigits: 6 }) : "—";
};

export const tone = (v: unknown) => {
  const x = n(v);
  return !Number.isFinite(x) || x === 0 ? "text-muted" : x > 0 ? "text-up" : "text-down";
};

export function timeAgo(iso: string | number | Date) {
  const t = new Date(iso).getTime();
  const s = Math.round((Date.now() - t) / 1000);
  if (s < 0) return "upcoming";
  if (s < 45) return "just now";
  if (s < 3600) return `${Math.round(s / 60)}m ago`;
  if (s < 86400) return `${Math.round(s / 3600)}h ago`;
  if (s < 86400 * 7) return `${Math.round(s / 86400)}d ago`;
  return new Date(t).toLocaleDateString("en-US", { month: "short", day: "numeric" });
}

export const etTime = (iso: string | number) =>
  new Date(typeof iso === "number" ? iso * 1000 : iso).toLocaleString("en-US", {
    timeZone: "America/New_York",
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });

/** "in 2h 14m" / "Mon 9:30 AM" style countdown to an ISO time. */
export function countdown(iso: string) {
  const ms = new Date(iso).getTime() - Date.now();
  if (ms <= 0) return "now";
  const m = Math.round(ms / 60000);
  if (m < 60) return `in ${m}m`;
  const h = Math.floor(m / 60);
  if (h < 24) return `in ${h}h ${m % 60}m`;
  return new Date(iso).toLocaleString("en-US", { timeZone: "America/New_York", weekday: "short", hour: "numeric", minute: "2-digit" }) + " ET";
}

export const shortDate = (iso: string) =>
  new Date(iso).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
