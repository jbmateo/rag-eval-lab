"use client";
import { useEffect, useRef } from "react";
import { StatusBadge } from "./StatusBadge";
import { evidenceMatches, ms, usd } from "@/lib/format";
import type { CaseRow, CompareCase, DatasetCase } from "@/lib/types";

function Side({ title, row, expected }: { title: string; row: CaseRow | null; expected: DatasetCase | null }) {
  if (!row) return <div className="text-sm text-muted">{title}: not in this run.</div>;
  if (row.status === "error" || !row.trace) {
    return <div className="space-y-1"><h3 className="font-semibold">{title}</h3><p className="text-sm text-critical">Errored: {row.error}</p></div>;
  }
  const t = row.trace;
  const ev = expected?.expected ?? [];
  const citedBy = (i: number) => t.citations.filter((c) => c.sentence_index === i);
  return (
    <div className="min-w-0 space-y-4">
      <div className="flex flex-wrap items-baseline gap-2">
        <h3 className="font-semibold">{title}</h3>
        <span className="text-sm">{row.pass === null ? "not scored" : row.pass ? "✓ pass" : "✗ fail"}</span>
        <span className="text-xs text-muted">answer status: {t.status}</span>
      </div>
      <div>
        <h4 className="mb-1 text-xs font-medium uppercase tracking-wide text-muted">Answer</h4>
        {t.sentences.length === 0 ? <p className="text-sm text-ink-2">({t.status === "abstained" ? "abstained — declined to answer" : "no answer text"})</p> : (
          <p className="text-sm leading-relaxed">
            {t.sentences.map((s, i) => (
              <span key={i}>{s}{citedBy(i).map((c, j) => (
                <sup key={j} className={`ml-0.5 rounded px-1 text-[10px] ${c.chunk_rank === null ? "bg-surface-2 text-critical" : "bg-surface-2 text-ink-2"}`}>
                  {c.chunk_rank === null ? "?" : c.chunk_rank}
                </sup>
              ))} </span>
            ))}
          </p>
        )}
      </div>
      {row.judge && (
        <div>
          <h4 className="mb-1 text-xs font-medium uppercase tracking-wide text-muted">Judge</h4>
          <p className="text-sm"><span className="font-medium">{row.judge.correct ? "Correct" : "Incorrect"}</span>
            {" · "}{row.judge.unsupported_claims} unsupported claim{row.judge.unsupported_claims === 1 ? "" : "s"}</p>
          <p className="text-sm text-ink-2">{row.judge.reason}</p>
        </div>
      )}
      <p className="num text-xs text-muted">
        latency {ms(row.latency_ms)}{row.cached ? " (cached)" : ""} · cost {usd(row.cost_nominal_system)} system + {usd(row.cost_nominal_judge)} judge
      </p>
      <div>
        <h4 className="mb-1 text-xs font-medium uppercase tracking-wide text-muted">Retrieved chunks</h4>
        <ol className="space-y-2">
          {t.retrieved.map((c) => {
            const hit = ev.some((e) => evidenceMatches(c.document, c.text, e));
            return (
              <li key={c.rank} className={`rounded-md border p-2 text-xs ${hit ? "border-[var(--good)] bg-surface-2" : "border-line"}`}>
                <div className="mb-1 flex items-center gap-2">
                  <span className="num rounded bg-surface-2 px-1.5 font-medium">#{c.rank}</span>
                  <span className="truncate text-ink-2">{c.document}</span>
                  {hit && <span className="ml-auto whitespace-nowrap font-medium text-good">✓ expected evidence</span>}
                </div>
                <p className="line-clamp-4 whitespace-pre-line text-ink-2">{c.text}</p>
              </li>
            );
          })}
        </ol>
      </div>
    </div>
  );
}

export function CaseDrawer({ entry, expected, baseRow, candRow, baseLabel, candLabel, onClose }: {
  entry: CompareCase; expected: DatasetCase | null; baseRow: CaseRow | null; candRow: CaseRow | null;
  baseLabel: string; candLabel: string; onClose: () => void;
}) {
  const closeRef = useRef<HTMLButtonElement>(null);
  useEffect(() => {
    closeRef.current?.focus();
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);
  return (
    <div className="fixed inset-0 z-50 flex justify-end bg-black/30" onClick={onClose}>
      <aside role="dialog" aria-modal="true" aria-label={`Case ${entry.case_id}`} onClick={(e) => e.stopPropagation()} style={{ overflowWrap: "anywhere" }}
        className="h-full w-full max-w-5xl overflow-y-auto border-l border-line bg-page p-5 shadow-xl">
        <div className="mb-4 flex items-start gap-3">
          <div className="min-w-0 flex-1 space-y-1">
            <div className="flex flex-wrap items-center gap-3"><StatusBadge status={entry.status} />
              <span className="num text-sm text-muted">{entry.case_id} · {entry.tag}{entry.reason ? ` · ${entry.reason.replaceAll("_", " ")}` : ""}</span></div>
            <h2 className="text-lg font-semibold">{entry.question}</h2>
          </div>
          <button ref={closeRef} onClick={onClose} className="rounded-md border border-line px-3 py-1.5 text-sm hover:bg-surface-2">Close</button>
        </div>
        <section className="mb-5 rounded-lg border border-line bg-surface p-3">
          <h3 className="mb-1 text-sm font-semibold">Expected evidence</h3>
          {!expected ? <p className="text-sm text-muted">Dataset case not available.</p>
            : expected.expected.length === 0 ? <p className="text-sm text-ink-2">None — the corpus does not answer this question; the right behaviour is to abstain.</p>
            : <ul className="space-y-1 text-sm">{expected.expected.map((e, i) => <li key={i}><span className="text-muted">[{e.document}]</span> {e.evidence}</li>)}</ul>}
        </section>
        <div className="grid gap-6 md:grid-cols-2">
          <Side title={`Baseline · ${baseLabel}`} row={baseRow} expected={expected} />
          <Side title={`Candidate · ${candLabel}`} row={candRow} expected={expected} />
        </div>
      </aside>
    </div>
  );
}
