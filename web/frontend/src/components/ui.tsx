import type { ReactNode } from "react";

export function Spinner({ className = "" }: { className?: string }) {
  return (
    <span
      className={`inline-block h-5 w-5 animate-spin rounded-full border-2 border-brand/30 border-t-brand ${className}`}
      aria-hidden
    />
  );
}

type Tone = "info" | "success" | "danger" | "muted";

const TONES: Record<Tone, string> = {
  info: "bg-brand-soft text-brand-strong border-brand/20",
  success: "bg-brand-soft text-brand-strong border-brand/30",
  danger: "bg-danger-soft text-danger border-danger/20",
  muted: "bg-surface-soft text-ink-soft border-line",
};

export function LiveBanner({
  tone = "info",
  icon,
  children,
}: {
  tone?: Tone;
  icon?: ReactNode;
  children: ReactNode;
}) {
  return (
    <div className={`flex items-start gap-3 rounded-2xl border px-5 py-4 text-lg leading-relaxed ${TONES[tone]}`}>
      {icon ? <span className="text-2xl leading-none">{icon}</span> : null}
      <div className="flex-1">{children}</div>
    </div>
  );
}

export function Badge({ children, tone = "muted" }: { children: ReactNode; tone?: Tone }) {
  return (
    <span className={`inline-flex items-center gap-1 rounded-full border px-3 py-1 text-sm font-semibold ${TONES[tone]}`}>
      {children}
    </span>
  );
}
