"use client";
import { useMemo, useState } from "react";
import { StatusBadge } from "./StatusBadge";
import type { CompareReport } from "@/lib/types";

const STATUSES = ["regressed", "improved", "stable_fail", "stable_pass", "not_comparable"] as const;

export function CaseList({ report, onOpen }: { report: CompareReport; onOpen: (id: string) => void }) {
  const [status, setStatus] = useState<string>("changed");
  const [tag, setTag] = useState("all");
  const [reason, setReason] = useState("all");
  const tags = useMemo(() => [...new Set(report.cases.map((c) => c.tag))].sort(), [report]);
  const reasons = useMemo(() => [...new Set(report.cases.map((c) => c.reason).filter(Boolean) as string[])].sort(), [report]);
  const shown = report.cases.filter((c) =>
    (status === "all" || (status === "changed" ? c.status === "regressed" || c.status === "improved" : c.status === status))
    && (tag === "all" || c.tag === tag) && (reason === "all" || c.reason === reason));
  const select = "rounded-md border border-line bg-surface px-2 py-1.5 text-sm";
  return (
    <section className="space-y-3">
      <div className="flex flex-wrap items-center gap-3">
        <h2 className="text-lg font-semibold">Cases</h2>
        <div className="flex flex-wrap gap-x-4 gap-y-1 text-sm">
          {STATUSES.map((s) => <span key={s} className="inline-flex gap-1.5"><StatusBadge status={s} /><span className="num">{report.counts[s]}</span></span>)}
        </div>
      </div>
      <div className="flex flex-wrap gap-2">
        <label className="sr-only" htmlFor="f-status">Status</label>
        <select id="f-status" className={select} value={status} onChange={(e) => setStatus(e.target.value)}>
          <option value="changed">Changed (regressed + improved)</option><option value="all">All cases</option>
          {STATUSES.map((s) => <option key={s} value={s}>{s.replace("_", " ")}</option>)}
        </select>
        <label className="sr-only" htmlFor="f-tag">Tag</label>
        <select id="f-tag" className={select} value={tag} onChange={(e) => setTag(e.target.value)}>
          <option value="all">All tags</option>{tags.map((t) => <option key={t}>{t}</option>)}
        </select>
        <label className="sr-only" htmlFor="f-reason">Reason</label>
        <select id="f-reason" className={select} value={reason} onChange={(e) => setReason(e.target.value)}>
          <option value="all">All reasons</option>{reasons.map((r) => <option key={r}>{r}</option>)}
        </select>
      </div>
      {shown.length === 0 ? <p className="rounded-lg border border-line bg-surface p-4 text-sm text-ink-2">No cases match these filters.</p> : (
        <ul className="divide-y divide-[var(--border)] rounded-lg border border-line bg-surface">
          {shown.map((c) => (
            <li key={c.case_id}>
              <button onClick={() => onOpen(c.case_id)} className="flex w-full flex-wrap items-center gap-x-4 gap-y-1 px-4 py-3 text-left hover:bg-surface-2">
                <span className="w-32 shrink-0"><StatusBadge status={c.status} /></span>
                <span className="num w-12 shrink-0 text-sm text-muted">{c.case_id}</span>
                <span className="min-w-0 flex-1 text-sm">{c.question ?? "(question unavailable)"}</span>
                <span className="text-xs text-muted">{c.tag}{c.reason ? ` · ${c.reason.replaceAll("_", " ")}` : ""}</span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
