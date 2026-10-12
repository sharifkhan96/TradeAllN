import { create } from "zustand";
import type { News } from "@/lib/types";

export type LiveQuote = { p: number; c: number; v: number; t: number; x?: number | null; xc?: number | null };
export type LiveMove = {
  symbol: string;
  pct: number;
  start_t: number;
  end_t: number;
  summary: string;
  category: string;
  article: News;
};
type Msg = { type: string; [k: string]: unknown };
type Listener = (m: Msg) => void;

type LiveState = {
  connected: boolean;
  quotes: Record<string, LiveQuote>;
  news: News[];
  liveMoves: LiveMove[];
  watched: Set<string>;
  setWatched: (s: string[]) => void;
};

export const useLive = create<LiveState>((set) => ({
  connected: false,
  quotes: {},
  news: [],
  liveMoves: [],
  watched: new Set(),
  setWatched: (s) => set({ watched: new Set(s) }),
}));

const listeners = new Set<Listener>();
export const onLive = (fn: Listener) => {
  listeners.add(fn);
  return () => void listeners.delete(fn);
};

let ws: WebSocket | null = null;
let currentToken: string | null = null;
let retry = 0;
let timer: ReturnType<typeof setTimeout> | undefined;

function handle(msg: Msg) {
  if (msg.type === "quotes") {
    const t = msg.t as number;
    const q = msg.q as Record<string, [number, number, number, number | null, number | null]>;
    const next: Record<string, LiveQuote> = {};
    for (const [s, [p, c, v, x, xc]] of Object.entries(q)) next[s] = { p, c, v, t, x, xc };
    useLive.setState((st) => ({ quotes: { ...st.quotes, ...next } }));
  } else if (msg.type === "news") {
    useLive.setState((st) => ({ news: [msg.article as News, ...st.news].slice(0, 50) }));
  } else if (msg.type === "move_explained") {
    useLive.setState((st) => ({ liveMoves: [msg as unknown as LiveMove, ...st.liveMoves].slice(0, 30) }));
  }
  listeners.forEach((fn) => fn(msg));
}

export function connectLive(token: string | null) {
  if (token === currentToken && ws && ws.readyState <= 1) return;
  currentToken = token;
  clearTimeout(timer);
  if (ws) {
    ws.onclose = null;
    ws.close();
    ws = null;
  }
  if (!token) {
    useLive.setState({ connected: false });
    return;
  }
  const proto = location.protocol === "https:" ? "wss" : "ws";
  ws = new WebSocket(`${proto}://${location.host}/ws/?token=${encodeURIComponent(token)}`);
  ws.onopen = () => {
    retry = 0;
    useLive.setState({ connected: true });
  };
  ws.onmessage = (e) => {
    try {
      handle(JSON.parse(e.data));
    } catch {
      /* ignore malformed frames */
    }
  };
  ws.onclose = () => {
    useLive.setState({ connected: false });
    ws = null;
    retry = Math.min(retry + 1, 6);
    const tok = currentToken;
    currentToken = null; // let the retry reconnect
    timer = setTimeout(() => connectLive(tok), 500 * 2 ** retry);
  };
}
