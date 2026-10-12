import { Loader2, X } from "lucide-react";
import { forwardRef, useEffect, type ButtonHTMLAttributes, type HTMLAttributes, type InputHTMLAttributes, type ReactNode } from "react";
import { createPortal } from "react-dom";
import { cn } from "@/lib/cn";

type BtnVariant = "primary" | "secondary" | "ghost" | "up" | "down" | "ai" | "danger";
const btnVariants: Record<BtnVariant, string> = {
  primary: "bg-fg text-bg hover:bg-fg/90",
  secondary: "bg-panel2 text-fg border border-line hover:border-faint/60 hover:bg-panel2/80",
  ghost: "text-muted hover:text-fg hover:bg-panel2",
  up: "bg-up text-[#04130d] hover:brightness-110",
  down: "bg-down text-white hover:brightness-110",
  ai: "ai-gradient text-white hover:brightness-110 shadow-[0_6px_24px_-10px_rgb(var(--ai))]",
  danger: "text-down hover:bg-down/10 border border-down/30",
};
const btnSizes = { sm: "h-8 px-3 text-xs gap-1.5", md: "h-9 px-3.5 text-sm gap-2", lg: "h-11 px-5 text-sm gap-2", icon: "h-8 w-8 justify-center" };

export const Button = forwardRef<
  HTMLButtonElement,
  ButtonHTMLAttributes<HTMLButtonElement> & { variant?: BtnVariant; size?: keyof typeof btnSizes; loading?: boolean }
>(({ className, variant = "secondary", size = "md", loading, children, disabled, ...props }, ref) => (
  <button
    ref={ref}
    disabled={disabled || loading}
    className={cn(
      "focus-ring inline-flex shrink-0 items-center rounded-lg font-medium transition-all duration-150 active:scale-[0.98] disabled:pointer-events-none disabled:opacity-50",
      btnVariants[variant],
      btnSizes[size],
      className,
    )}
    {...props}
  >
    {loading && <Loader2 className="h-4 w-4 animate-spin" />}
    {children}
  </button>
));
Button.displayName = "Button";

export const Input = forwardRef<HTMLInputElement, InputHTMLAttributes<HTMLInputElement> & { prefix?: ReactNode; suffix?: ReactNode }>(
  ({ className, prefix, suffix, ...props }, ref) => (
    <div
      className={cn(
        "flex h-10 items-center gap-2 rounded-lg border border-line bg-panel2/60 px-3 transition-colors focus-within:border-accent/60 focus-within:bg-panel2",
        className,
      )}
    >
      {prefix && <span className="text-sm text-muted">{prefix}</span>}
      <input ref={ref} className="h-full w-full min-w-0 bg-transparent text-sm text-fg outline-none placeholder:text-faint" {...props} />
      {suffix && <span className="text-xs text-muted">{suffix}</span>}
    </div>
  ),
);
Input.displayName = "Input";

export function Card({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return <div className={cn("card", className)} {...props} />;
}

export function CardHeader({ title, subtitle, action, icon, className }: { title: ReactNode; subtitle?: ReactNode; action?: ReactNode; icon?: ReactNode; className?: string }) {
  return (
    <div className={cn("flex items-start justify-between gap-3 px-5 pt-4", className)}>
      <div className="flex min-w-0 items-center gap-2.5">
        {icon && <span className="text-muted">{icon}</span>}
        <div className="min-w-0">
          <h3 className="truncate text-sm font-semibold tracking-tight">{title}</h3>
          {subtitle && <p className="mt-0.5 truncate text-xs text-muted">{subtitle}</p>}
        </div>
      </div>
      {action}
    </div>
  );
}

const badgeTones = {
  neutral: "bg-panel2 text-muted border-line",
  up: "bg-up/10 text-up border-up/20",
  down: "bg-down/10 text-down border-down/20",
  ai: "bg-ai/10 text-ai border-ai/25",
  accent: "bg-accent/10 text-accent border-accent/25",
  warn: "bg-warn/10 text-warn border-warn/25",
};
export function Badge({ tone = "neutral", className, children }: { tone?: keyof typeof badgeTones; className?: string; children: ReactNode }) {
  return (
    <span className={cn("inline-flex items-center gap-1 rounded-md border px-1.5 py-0.5 text-2xs font-medium", badgeTones[tone], className)}>
      {children}
    </span>
  );
}

export function Segmented<T extends string>({ value, onChange, options, size = "sm", className }: {
  value: T;
  onChange: (v: T) => void;
  options: { value: T; label: ReactNode }[];
  size?: "sm" | "md";
  className?: string;
}) {
  return (
    <div className={cn("inline-flex rounded-lg border border-line bg-panel2/60 p-0.5", className)}>
      {options.map((o) => (
        <button
          key={o.value}
          onClick={() => onChange(o.value)}
          className={cn(
            "focus-ring rounded-md font-medium transition-all",
            size === "sm" ? "h-7 px-2.5 text-xs" : "h-8 px-3 text-sm",
            value === o.value ? "bg-panel text-fg shadow-sm ring-1 ring-line" : "text-muted hover:text-fg",
          )}
        >
          {o.label}
        </button>
      ))}
    </div>
  );
}

export function Skeleton({ className }: { className?: string }) {
  return <div className={cn("animate-pulse rounded-md bg-panel2", className)} />;
}

export function Spinner({ className }: { className?: string }) {
  return <Loader2 className={cn("h-4 w-4 animate-spin text-muted", className)} />;
}

export function Empty({ icon, title, hint, action }: { icon?: ReactNode; title: string; hint?: ReactNode; action?: ReactNode }) {
  return (
    <div className="flex flex-col items-center justify-center gap-2 px-6 py-10 text-center">
      {icon && <div className="mb-1 rounded-xl border border-line bg-panel2 p-3 text-muted">{icon}</div>}
      <p className="text-sm font-medium">{title}</p>
      {hint && <p className="max-w-sm text-xs text-muted">{hint}</p>}
      {action && <div className="mt-2">{action}</div>}
    </div>
  );
}

export function Switch({ checked, onChange, label }: { checked: boolean; onChange: (v: boolean) => void; label?: string }) {
  return (
    <button
      role="switch"
      aria-checked={checked}
      aria-label={label}
      onClick={() => onChange(!checked)}
      className={cn("focus-ring relative h-5 w-9 rounded-full transition-colors", checked ? "bg-up" : "bg-line")}
    >
      <span className={cn("absolute top-0.5 h-4 w-4 rounded-full bg-white shadow transition-all", checked ? "left-[18px]" : "left-0.5")} />
    </button>
  );
}

export function Modal({ open, onClose, children, className, title }: { open: boolean; onClose: () => void; children: ReactNode; className?: string; title?: ReactNode }) {
  useEffect(() => {
    if (!open) return;
    const k = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", k);
    return () => window.removeEventListener("keydown", k);
  }, [open, onClose]);
  if (!open) return null;
  return createPortal(
    <div className="fixed inset-0 z-50 flex items-start justify-center bg-black/50 p-4 pt-[10vh] backdrop-blur-sm" onMouseDown={onClose}>
      <div
        className={cn("card w-full max-w-lg animate-fadeIn shadow-pop", className)}
        onMouseDown={(e) => e.stopPropagation()}
        role="dialog"
      >
        {title && (
          <div className="flex items-center justify-between border-b border-line px-5 py-3.5">
            <h2 className="text-sm font-semibold">{title}</h2>
            <Button variant="ghost" size="icon" onClick={onClose} aria-label="Close">
              <X className="h-4 w-4" />
            </Button>
          </div>
        )}
        {children}
      </div>
    </div>,
    document.body,
  );
}

export function Drawer({ open, onClose, children, title, width = "max-w-md" }: { open: boolean; onClose: () => void; children: ReactNode; title: ReactNode; width?: string }) {
  useEffect(() => {
    if (!open) return;
    const k = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", k);
    return () => window.removeEventListener("keydown", k);
  }, [open, onClose]);
  return createPortal(
    <div className={cn("fixed inset-0 z-40 transition", open ? "pointer-events-auto" : "pointer-events-none")}>
      <div className={cn("absolute inset-0 bg-black/40 transition-opacity", open ? "opacity-100" : "opacity-0")} onClick={onClose} />
      <aside
        className={cn(
          "absolute right-0 top-0 flex h-full w-full flex-col border-l border-line bg-panel shadow-pop transition-transform duration-300",
          width,
          open ? "translate-x-0" : "translate-x-full",
        )}
      >
        <div className="flex items-center justify-between border-b border-line px-5 py-3.5">
          <div className="text-sm font-semibold">{title}</div>
          <Button variant="ghost" size="icon" onClick={onClose} aria-label="Close">
            <X className="h-4 w-4" />
          </Button>
        </div>
        <div className="min-h-0 flex-1 overflow-y-auto">{children}</div>
      </aside>
    </div>,
    document.body,
  );
}

export function Stat({ label, value, sub, className }: { label: ReactNode; value: ReactNode; sub?: ReactNode; className?: string }) {
  return (
    <div className={cn("min-w-0", className)}>
      <div className="label">{label}</div>
      <div className="num mt-1 truncate text-base font-semibold">{value}</div>
      {sub && <div className="num mt-0.5 text-xs">{sub}</div>}
    </div>
  );
}
