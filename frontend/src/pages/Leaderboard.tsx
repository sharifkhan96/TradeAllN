import { Crown, Trophy } from "lucide-react";
import { Badge, Card, Skeleton } from "@/components/ui";
import { cn } from "@/lib/cn";
import { money, pct, tone } from "@/lib/format";
import { useLeaderboard } from "@/lib/queries";

export function LeaderboardPage() {
  const { data, isLoading } = useLeaderboard();
  const top = (data ?? []).slice(0, 3);
  return (
    <div className="space-y-5">
      <div>
        <h1 className="flex items-center gap-2 text-xl font-semibold tracking-tight"><Trophy className="h-5 w-5 text-warn" /> Leaderboard</h1>
        <p className="text-sm text-muted">Ranked by all-time return on each paper account.</p>
      </div>
      <div className="grid gap-3 md:grid-cols-3">
        {top.map((r, i) => (
          <Card key={r.rank} className={cn("relative overflow-hidden p-5", i === 0 && "ai-border")}>
            {i === 0 && <Crown className="absolute right-4 top-4 h-5 w-5 text-warn" />}
            <div className="label">#{r.rank}</div>
            <div className="mt-1 text-lg font-semibold">{r.name} {r.is_you && <Badge tone="ai">You</Badge>}</div>
            <div className={cn("num mt-2 text-2xl font-semibold", tone(r.return_pct))}>{pct(r.return_pct)}</div>
            <div className="num mt-1 text-xs text-muted">{money(r.equity)} equity</div>
          </Card>
        ))}
      </div>
      <Card className="overflow-x-auto">
        <table className="w-full min-w-[520px] text-sm">
          <thead>
            <tr>{["Rank", "Trader", "Equity", "Today", "All-time", "Positions"].map((h, i) => <th key={h} className={cn("label px-5 pb-2 pt-4 text-left font-medium", i > 1 && "text-right")}>{h}</th>)}</tr>
          </thead>
          <tbody>
            {isLoading && <tr><td colSpan={6} className="p-4"><Skeleton className="h-24" /></td></tr>}
            {(data ?? []).map((r) => (
              <tr key={r.rank} className={cn("border-t border-line/70", r.is_you && "bg-ai/5")}>
                <td className="num px-5 py-3 text-muted">{r.rank}</td>
                <td className="px-5 font-medium">{r.name} {r.is_you && <Badge tone="ai">You</Badge>}</td>
                <td className="num px-5 text-right">{money(r.equity)}</td>
                <td className={cn("num px-5 text-right", tone(r.day_pct))}>{pct(r.day_pct)}</td>
                <td className={cn("num px-5 text-right font-semibold", tone(r.return_pct))}>{pct(r.return_pct)}</td>
                <td className="num px-5 text-right text-muted">{r.positions}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </Card>
    </div>
  );
}
