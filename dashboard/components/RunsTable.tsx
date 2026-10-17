"use client";
import { useMemo, useState } from "react";
import { StatusBadge } from "./StatusBadge";
import { ms, pct, usd, value, varyingKeys } from "@/lib/format";
import type { Run } from "@/lib/types";

type Col = { key: string; label: string; get: (r: Run) => number | string | null; render: (r: Run) => React.ReactNode };

const s = (r: Run, k: string) => (r.summary?.[k] ?? null) as number | null;

export function RunsTable({ runs, selected, onToggle, accLabel }:
  { runs: Run[]; selected: string[]; onToggle: (id: string) => void; accLabel: string }) {
  const keys = useMemo(() => varyingKeys(runs.map((r) => r.config)), [runs]);
  const [sort, setSort] = useState<{ key: string; desc: boolean }>({ key: "accuracy", desc: true });
  const cols: Col[] = [
    ...keys.map((k) => ({ key: `cfg:${k}`, label: k, get: (r: Run) => value(r.config[k]), render: (r: Run) => value(r.config[k]) })),
    { key: "accuracy", label: accLabel, get: (r) => s(r, "accuracy"), render: (r) => {
      const ci = r.summary?.accuracy_ci;
      return <span>{pct(s(r, "accuracy"))}{ci && ci[0] !== null && <span className="text-muted"> [{pct(ci[0], 0)}–{pct(ci[1], 0)}]</span>}</span>;
    } },
    { key: "hit@k", label: "hit@k", get: (r) => s(r, "hit@k"), render: (r) => pct(s(r, "hit@k")) },
    { key: "mrr", label: "MRR", get: (r) => s(r, "mrr"), render: (r) => pct(s(r, "mrr")) },
    { key: "abstention_precision", label: "abstain P", get: (r) => s(r, "abstention_precision"), render: (r) => pct(s(r, "abstention_precision")) },
    { key: "abstention_recall", label: "abstain R", get: (r) => s(r, "abstention_recall"), render: (r) => pct(s(r, "abstention_recall")) },
    { key: "latency_p50_ms", label: "p50", get: (r) => s(r, "latency_p50_ms"), render: (r) => ms(s(r, "latency_p50_ms")) },
    { key: "latency_p95_ms", label: "p95", get: (r) => s(r, "latency_p95_ms"), render: (r) => ms(s(r, "latency_p95_ms")) },
    { key: "cost_per_case", label: "cost/case", get: (r) => s(r, "cost_per_case"), render: (r) => usd(s(r, "cost_per_case")) },
    { key: "n_errored", label: "errors", get: (r) => s(r, "n_errored"), render: (r) => value(s(r, "n_errored")) },
  ];
  const col = cols.find((c) => c.key === sort.key) ?? cols[0];
  const rows = [...runs].sort((a, b) => {
    const x = col.get(a), y = col.get(b);
    if (x === y) return 0;
    if (x === null) return 1;
    if (y === null) return -1;
    return (x < y ? -1 : 1) * (sort.desc ? -1 : 1);
  });
  return (
    <div className="overflow-x-auto rounded-lg border border-line bg-surface">
      <table className="w-full text-sm">
        <thead className="text-left text-muted">
          <tr className="border-b border-line">
            <th className="px-3 py-2"><span className="sr-only">Select</span></th>
            <th className="px-3 py-2 font-medium">run</th>
            {cols.map((c) => (
              <th key={c.key} className="px-3 py-2 font-medium" aria-sort={sort.key === c.key ? (sort.desc ? "descending" : "ascending") : "none"}>
                <button className="whitespace-nowrap hover:text-ink" onClick={() => setSort({ key: c.key, desc: sort.key === c.key ? !sort.desc : true })}>
                  {c.label}{sort.key === c.key ? (sort.desc ? " ↓" : " ↑") : ""}
                </button>
              </th>
            ))}
            <th className="px-3 py-2 font-medium">status</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.run_id} className="border-b border-line last:border-0 hover:bg-surface-2">
              <td className="px-3 py-2">
                <input type="checkbox" aria-label={`Select run ${r.label}`} checked={selected.includes(r.run_id)}
                  onChange={() => onToggle(r.run_id)} className="size-4 accent-[var(--series-1)]" />
              </td>
              <td className="px-3 py-2"><div className="font-medium">{r.label}</div><div className="num text-xs text-muted">{r.run_id}</div></td>
              {cols.map((c) => <td key={c.key} className="num whitespace-nowrap px-3 py-2">{c.render(r)}</td>)}
              <td className="px-3 py-2"><StatusBadge status={r.status} /></td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
