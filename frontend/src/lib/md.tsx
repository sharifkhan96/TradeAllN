import type { ReactNode } from "react";

/** Tiny markdown subset for assistant answers: **bold**, _italic_, `code`, bullets, paragraphs. */
function inline(text: string): ReactNode[] {
  const out: ReactNode[] = [];
  const re = /(\*\*[^*]+\*\*|_[^_]+_|`[^`]+`)/g;
  let last = 0;
  let m: RegExpExecArray | null;
  let i = 0;
  while ((m = re.exec(text))) {
    if (m.index > last) out.push(text.slice(last, m.index));
    const t = m[0];
    if (t.startsWith("**")) out.push(<strong key={i++} className="font-semibold text-fg">{t.slice(2, -2)}</strong>);
    else if (t.startsWith("`")) out.push(<code key={i++} className="rounded bg-panel2 px-1 font-mono text-xs">{t.slice(1, -1)}</code>);
    else out.push(<em key={i++} className="text-muted">{t.slice(1, -1)}</em>);
    last = m.index + t.length;
  }
  if (last < text.length) out.push(text.slice(last));
  return out;
}

export function Markdown({ text }: { text: string }) {
  const blocks = text.trim().split(/\n{2,}/);
  return (
    <div className="space-y-2.5 text-sm leading-relaxed text-fg/90">
      {blocks.map((b, i) => {
        const lines = b.split("\n");
        if (lines.every((l) => /^\s*[-*•]\s/.test(l))) {
          return (
            <ul key={i} className="space-y-1.5">
              {lines.map((l, j) => (
                <li key={j} className="flex gap-2">
                  <span className="mt-2 h-1 w-1 shrink-0 rounded-full bg-faint" />
                  <span>{inline(l.replace(/^\s*[-*•]\s/, ""))}</span>
                </li>
              ))}
            </ul>
          );
        }
        const head = lines.filter((l) => !/^\s*[-*•]\s/.test(l));
        const items = lines.filter((l) => /^\s*[-*•]\s/.test(l));
        return (
          <div key={i} className="space-y-1.5">
            {head.length > 0 && <p>{inline(head.join(" "))}</p>}
            {items.length > 0 && (
              <ul className="space-y-1.5">
                {items.map((l, j) => (
                  <li key={j} className="flex gap-2">
                    <span className="mt-2 h-1 w-1 shrink-0 rounded-full bg-faint" />
                    <span>{inline(l.replace(/^\s*[-*•]\s/, ""))}</span>
                  </li>
                ))}
              </ul>
            )}
          </div>
        );
      })}
    </div>
  );
}
