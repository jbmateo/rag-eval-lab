import { StatusBadge } from "./StatusBadge";
import { ms, num, pct, signedPts, usd, value } from "@/lib/format";
import type { CompareReport, MetricDelta } from "@/lib/types";

const ROWS: { key: keyof CompareReport["summary"]; label: string; fmt: (v: number | null) => string; delta: (v: number | null) => string }[] = [
  { key: "accuracy", label: "Accuracy", fmt: pct, delta: signedPts },
  { key: "mrr", label: "MRR", fmt: (v) => num(v, 3), delta: (v) => (v === null ? "—" : `${v >= 0 ? "+" : ""}${v.toFixed(3)}`) },
  { key: "latency_ms", label: "Mean latency (uncached)", fmt: ms, delta: (v) => (v === null ? "—" : `${v >= 0 ? "+" : ""}${Math.round(v)} ms`) },
  { key: "cost_per_case", label: "Cost per case", fmt: (v) => usd(v), delta: (v) => (v === null ? "—" : `${v >= 0 ? "+" : "−"}${usd(Math.abs(v))}`) },
];

function Ci({ m, fmt }: { m: MetricDelta; fmt: (v: number | null) => string }) {
  return m.lo === null ? <span className="text-muted">—</span> : <span>[{fmt(m.lo)}, {fmt(m.hi)}]</span>;
}

export function CompareSummary({ report: r }: { report: CompareReport }) {
  const diff = Object.entries(r.config_diff);
  const acc = r.summary.accuracy;
  return (
    <section className="space-y-4">
      {r.warnings.map((w) => (
        <p key={w} role="status" className="rounded-md border border-line bg-surface-2 px-3 py-2 text-sm"><span aria-hidden>⚠ </span>{w}</p>
      ))}
      <div className="grid gap-4 md:grid-cols-[1fr_2fr]">
        <div className="min-w-0 rounded-lg border border-line bg-surface p-4">
          <h2 className="mb-2 font-semibold">What changed</h2>
          {diff.length === 0 ? <p className="text-sm text-ink-2">Same settings — only the system or dataset version differs.</p> : (
            <table className="num w-full text-sm">
              <tbody>
                {diff.map(([k, [b, c]]) => (
                  <tr key={k}><th className="py-1 pr-3 text-left font-medium">{k}</th><td className="py-1 text-ink-2">{value(b)}</td>
                    <td className="px-2 text-muted">→</td><td className="py-1">{value(c)}</td></tr>
                ))}
              </tbody>
            </table>
          )}
          <p className="mt-3 text-xs text-muted">
            system {r.versions.base.system_version} → {r.versions.cand.system_version}<br />
            dataset {r.versions.base.dataset} → {r.versions.cand.dataset} · judge {r.versions.cand.judge_model}
          </p>
        </div>
        <div className="min-w-0 rounded-lg border border-line bg-surface p-4">
          <div className="mb-3 flex flex-wrap items-baseline gap-3">
            <h2 className="font-semibold">Verdict</h2>
            <StatusBadge status={acc.verdict} />
            <span className="num text-sm text-ink-2">
              {r.n_compared} paired cases · McNemar p = {num(r.mcnemar_p, 3)} · smallest change this sample can detect ≈ {pct(r.mde, 0)}
            </span>
          </div>
          <div className="overflow-x-auto">
            <table className="num w-full text-sm">
              <thead className="text-left text-muted">
                <tr><th className="py-1 pr-3 font-medium">metric</th><th className="pr-3 font-medium">baseline</th><th className="pr-3 font-medium">candidate</th>
                  <th className="pr-3 font-medium">Δ</th><th className="pr-3 font-medium">95% CI</th><th className="font-medium">verdict</th></tr>
              </thead>
              <tbody>
                {ROWS.map(({ key, label, fmt, delta }) => {
                  const m = r.summary[key];
                  return (
                    <tr key={key} className="border-t border-line">
                      <th className="py-1.5 pr-3 text-left font-medium">{label}</th>
                      <td className="whitespace-nowrap pr-3">{fmt(m.base)}</td><td className="whitespace-nowrap pr-3">{fmt(m.cand)}</td>
                      <td className="whitespace-nowrap pr-3">{delta(m.delta)}</td><td className="whitespace-nowrap pr-3"><Ci m={m} fmt={delta} /></td>
                      <td><StatusBadge status={m.verdict} /></td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </section>
  );
}
