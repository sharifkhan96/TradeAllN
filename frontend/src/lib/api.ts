import { useAuth } from "@/stores/auth";

export class ApiError extends Error {
  constructor(public status: number, message: string, public data?: unknown) {
    super(message);
  }
}

const BASE = "/api/v1";
let refreshing: Promise<boolean> | null = null;

export async function refreshSession(): Promise<boolean> {
  refreshing ??= (async () => {
    try {
      const r = await fetch(`${BASE}/auth/refresh`, { method: "POST", credentials: "include" });
      if (!r.ok) {
        useAuth.getState().clear();
        return false;
      }
      const d = await r.json();
      useAuth.getState().setSession(d.access, d.user);
      return true;
    } catch {
      return false;
    } finally {
      setTimeout(() => (refreshing = null), 0);
    }
  })();
  return refreshing;
}

function messageFrom(data: unknown, status: number) {
  if (data && typeof data === "object") {
    const d = data as Record<string, unknown>;
    if (typeof d.detail === "string") return d.detail;
    const first = Object.entries(d)[0];
    if (first) {
      const [k, v] = first;
      const msg = Array.isArray(v) ? String(v[0]) : String(v);
      return k === "non_field_errors" ? msg : `${k}: ${msg}`;
    }
  }
  return status >= 500 ? "Server error. Please try again." : "Request failed.";
}

export async function api<T = unknown>(path: string, init: RequestInit & { json?: unknown } = {}, retry = true): Promise<T> {
  const { json, headers, ...rest } = init;
  const token = useAuth.getState().access;
  const r = await fetch(`${BASE}${path}`, {
    credentials: "include",
    ...rest,
    method: rest.method ?? (json !== undefined ? "POST" : "GET"),
    headers: {
      ...(json !== undefined ? { "Content-Type": "application/json" } : {}),
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...headers,
    },
    body: json !== undefined ? JSON.stringify(json) : rest.body,
  });
  if (r.status === 401 && retry && !path.startsWith("/auth/")) {
    if (await refreshSession()) return api<T>(path, init, false);
  }
  if (r.status === 204) return undefined as T;
  const data = await r.json().catch(() => null);
  if (!r.ok) throw new ApiError(r.status, messageFrom(data, r.status), data);
  return data as T;
}
