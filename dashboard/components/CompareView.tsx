"use client";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";
import { CaseDrawer } from "./CaseDrawer";
import { CaseList } from "./CaseList";
import { CompareSummary } from "./CompareSummary";
import { compareRuns } from "@/lib/compare";
import { fetchDataset, fetchExperiment, fetchRun } from "@/lib/client";
import { labelFor, slugify } from "@/lib/format";
import type { CompareReport, DatasetCase, RunFile } from "@/lib/types";

type Loaded = { report: CompareReport; base: RunFile; cand: RunFile; cases: Map<string, DatasetCase>; back: { slug: string; name: string } };

async function load(baseId: string, candId: string, expSlug: string | null): Promise<Loaded> {
  const [base, cand, exp] = await Promise.all([fetchRun(baseId), fetchRun(candId), expSlug ? fetchExperiment(expSlug) : null]);
  const report = compareRuns({ ...base.run, label: labelFor(exp, baseId, base.run.label) }, base.cases,
    { ...cand.run, label: labelFor(exp, candId, cand.run.label) }, cand.cases, true);
  const back = exp ? { slug: exp.slug, name: exp.name } : { slug: slugify(cand.run.experiment), name: cand.run.experiment };
  const [name, version] = cand.run.dataset.split("@");
  const cases = new Map<string, DatasetCase>();
  const ds = await fetchDataset(name);
  for (const c of ds?.versions[version] ?? []) cases.set(c.id, c);
  return { report, base, cand, cases, back };
}

export function CompareView() {
  const params = useSearchParams();
  const baseId = params.get("base"), candId = params.get("cand"), expSlug = params.get("exp");
  const [state, setState] = useState<Loaded | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [open, setOpen] = useState<string | null>(null);
  useEffect(() => {
    if (!baseId || !candId) return;
    load(baseId, candId, expSlug).then(setState, (e: Error) => setError(e.message));
  }, [baseId, candId, expSlug]);

  if (!baseId || !candId) return <p className="text-ink-2">Pick two runs on an experiment page to compare them.</p>;
  if (error) return <p role="alert" className="text-critical">Could not load the runs: {error}</p>;
  if (!state) return <p className="text-ink-2">Loading runs…</p>;
  const { report, base, cand, cases, back } = state;
  const opened = open ? report.cases.find((c) => c.case_id === open) ?? null : null;
  return (
    <div className="space-y-8">
      <div className="space-y-1">
        <Link href={`/experiments/${back.slug}/`} className="text-sm text-ink-2 hover:text-ink">← {back.name}</Link>
        <h1 className="text-2xl font-semibold tracking-tight">
          {report.base.label} <span className="text-muted">→</span> {report.cand.label}
        </h1>
        <p className="num text-sm text-muted">baseline {report.base.run_id} · candidate {report.cand.run_id}</p>
      </div>
      <CompareSummary report={report} />
      <CaseList report={report} onOpen={setOpen} />
      {opened && (
        <CaseDrawer entry={opened} expected={cases.get(opened.case_id) ?? null}
          baseRow={base.cases.find((c) => c.case_id === opened.case_id) ?? null}
          candRow={cand.cases.find((c) => c.case_id === opened.case_id) ?? null}
          baseLabel={report.base.label} candLabel={report.cand.label} onClose={() => setOpen(null)} />
      )}
    </div>
  );
}
