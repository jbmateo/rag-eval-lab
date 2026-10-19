const STYLES: Record<string, { icon: string; label: string; cls: string }> = {
  improved: { icon: "▲", label: "Improved", cls: "text-good" },
  regressed: { icon: "▼", label: "Regressed", cls: "text-critical" },
  stable_pass: { icon: "●", label: "Stable pass", cls: "text-ink-2" },
  stable_fail: { icon: "○", label: "Stable fail", cls: "text-ink-2" },
  not_comparable: { icon: "–", label: "Not comparable", cls: "text-muted" },
  better: { icon: "▲", label: "Better", cls: "text-good" },
  worse: { icon: "▼", label: "Worse", cls: "text-critical" },
  "no detectable difference": { icon: "≈", label: "No detectable difference", cls: "text-ink-2" },
  complete: { icon: "✓", label: "Complete", cls: "text-good" },
  partial: { icon: "◐", label: "Partial", cls: "text-critical" },
  degraded: { icon: "!", label: "Degraded", cls: "text-critical" },
  running: { icon: "…", label: "Running", cls: "text-ink-2" },
};

export function StatusBadge({ status }: { status: string }) {
  const s = STYLES[status] ?? { icon: "", label: status, cls: "text-ink-2" };
  return (
    <span className={`inline-flex items-center gap-1 whitespace-nowrap text-sm font-medium ${s.cls}`}>
      <span aria-hidden>{s.icon}</span>{s.label}
    </span>
  );
}
