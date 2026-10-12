import { useMutation } from "@tanstack/react-query";
import { ArrowUp, Bot, Sparkles } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { Badge, Drawer, Spinner } from "@/components/ui";
import { api } from "@/lib/api";
import { cn } from "@/lib/cn";
import { Markdown } from "@/lib/md";
import { useAIStatus } from "@/lib/queries";
import { useUI } from "@/stores/ui";

type Turn = { role: "user" | "assistant"; text: string; method?: string };

const SUGGESTIONS = [
  "Why is my portfolio down today?",
  "How exposed am I to tech?",
  "What's my win rate?",
  "Which holding moved the most today and why?",
];

export function AskPanel() {
  const { askOpen, setAsk } = useUI();
  const [turns, setTurns] = useState<Turn[]>([]);
  const [text, setText] = useState("");
  const end = useRef<HTMLDivElement>(null);
  const { data: ai } = useAIStatus();
  const ask = useMutation({
    mutationFn: (question: string) => api<{ answer: string; method: string }>("/assistant/ask", { json: { question } }),
    onSuccess: (r) => setTurns((t) => [...t, { role: "assistant", text: r.answer, method: r.method }]),
    onError: (e) => setTurns((t) => [...t, { role: "assistant", text: (e as Error).message, method: "error" }]),
  });
  useEffect(() => {
    end.current?.scrollIntoView({ behavior: "smooth" });
  }, [turns, ask.isPending]);

  const send = (q: string) => {
    if (!q.trim() || ask.isPending) return;
    setTurns((t) => [...t, { role: "user", text: q.trim() }]);
    setText("");
    ask.mutate(q.trim());
  };

  return (
    <Drawer
      open={askOpen}
      onClose={() => setAsk(false)}
      width="max-w-lg"
      title={
        <span className="flex items-center gap-2">
          <Sparkles className="h-4 w-4 text-ai" /> Ask your portfolio
          {ai && <Badge tone={ai.ai_enabled ? "ai" : "neutral"}>{ai.ai_enabled ? "Claude" : "Rules mode"}</Badge>}
        </span>
      }
    >
      <div className="flex h-full flex-col">
        <div className="flex-1 space-y-4 p-5">
          {turns.length === 0 && (
            <div className="pt-6 text-center">
              <div className="ai-gradient mx-auto grid h-12 w-12 place-items-center rounded-2xl text-white shadow-[0_10px_30px_-10px_rgb(var(--ai))]">
                <Bot className="h-6 w-6" />
              </div>
              <h3 className="mt-4 text-base font-semibold">What do you want to know?</h3>
              <p className="mx-auto mt-1 max-w-xs text-sm text-muted">
                Answers come from your holdings, trades and the news behind each price move. It can't place trades.
              </p>
              <div className="mt-6 grid gap-2">
                {SUGGESTIONS.map((s) => (
                  <button key={s} onClick={() => send(s)} className="rounded-lg border border-line bg-panel2/40 px-3 py-2.5 text-left text-sm text-fg/90 transition-colors hover:border-ai/40 hover:bg-ai/5">
                    {s}
                  </button>
                ))}
              </div>
            </div>
          )}
          {turns.map((t, i) =>
            t.role === "user" ? (
              <div key={i} className="ml-auto max-w-[85%] rounded-2xl rounded-br-md bg-panel2 px-3.5 py-2.5 text-sm">{t.text}</div>
            ) : (
              <div key={i} className="flex gap-3">
                <div className="ai-gradient mt-0.5 grid h-7 w-7 shrink-0 place-items-center rounded-lg text-white"><Sparkles className="h-3.5 w-3.5" /></div>
                <div className={cn("min-w-0 flex-1", t.method === "error" && "text-down")}>
                  {t.method === "error" ? <p className="text-sm">{t.text}</p> : <Markdown text={t.text} />}
                </div>
              </div>
            ),
          )}
          {ask.isPending && (
            <div className="flex items-center gap-2 text-sm text-muted">
              <Spinner className="text-ai" /> Looking at your portfolio…
            </div>
          )}
          <div ref={end} />
        </div>
        <form
          className="sticky bottom-0 border-t border-line bg-panel p-3"
          onSubmit={(e) => {
            e.preventDefault();
            send(text);
          }}
        >
          <div className="flex items-center gap-2 rounded-xl border border-line bg-panel2/50 px-3 focus-within:border-ai/50">
            <input
              value={text}
              onChange={(e) => setText(e.target.value)}
              placeholder="Ask about your portfolio…"
              className="h-11 flex-1 bg-transparent text-sm outline-none placeholder:text-faint"
            />
            <button type="submit" disabled={!text.trim() || ask.isPending} className="ai-gradient grid h-7 w-7 place-items-center rounded-lg text-white disabled:opacity-40">
              <ArrowUp className="h-4 w-4" />
            </button>
          </div>
        </form>
      </div>
    </Drawer>
  );
}
