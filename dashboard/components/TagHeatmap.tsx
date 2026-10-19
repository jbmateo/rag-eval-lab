import { pct } from "@/lib/format";
import type { Run } from "@/lib/types";

const STEPS = ["--seq-1", "--seq-2", "--seq-3", "--seq-4", "--seq-5", "--seq-6", "--seq-7"];

function cell(v: number | null) {
  if (v === null) return { background: "var(--surface-2)", color: "var(--muted)" };
  const i = Math.min(STEPS.length - 1, Math.floor(v * STEPS.length));
  return { background: `var(${STEPS[i]})`, color: i >= 3 ? "#ffffff" : "#0b0b0b" };
}

export function TagHeatmap({ runs }: { runs: Run[] }) {
  const tags = [...new Set(runs.flatMap((r) => Object.keys(r.summary?.by_tag ?? {})))].sort();
  return (
    <figure className="min-w-0 rounded-lg border border-line bg-surface p-4">
      <figcaption className="mb-1 font-semibold">Pass rate by question type</figcaption>
      <p className="mb-3 text-sm text-ink-2">Which kinds of question each run gets right. Darker is higher.</p>
      <div className="overflow-x-auto">
        <table className="num w-full border-separate text-sm" style={{ borderSpacing: 2 }}>
          <thead>
            <tr>
              <th className="px-2 py-1 text-left font-medium text-muted">run</th>
              {tags.map((t) => <th key={t} className="px-2 py-1 text-left font-medium text-muted">{t}</th>)}
            </tr>
          </thead>
          <tbody>
            {runs.map((r) => (
              <tr key={r.run_id}>
                <th className="whitespace-nowrap px-2 py-1 text-left font-medium">{r.label}</th>
                {tags.map((t) => {
                  const b = r.summary?.by_tag?.[t];
                  const v = b ? b.accuracy : null;
                  return (
                    <td key={t} className="rounded px-2 py-1" style={cell(v)} title={`${r.label} · ${t}: ${pct(v)} of ${b?.n ?? 0} cases`}>
                      {pct(v, 0)}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </figure>
  );
}
