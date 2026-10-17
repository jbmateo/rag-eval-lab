"use client";
import Link from "next/link";
import { useMemo, useState } from "react";
import { CostAccuracyScatter } from "./CostAccuracyScatter";
import { MetricBars } from "./MetricBars";
import { RunsTable } from "./RunsTable";
import { TagHeatmap } from "./TagHeatmap";
import type { ExperimentFile } from "@/lib/types";

export function ExperimentView({ exp }: { exp: ExperimentFile }) {
  const [selected, setSelected] = useState<string[]>([]);
  const toggle = (id: string) =>
    setSelected((s) => (s.includes(id) ? s.filter((x) => x !== id) : [...s.slice(-1), id]));
  const accLabel = exp.runs[0]?.summary?.accuracy_definition === "hit@k" ? "hit@k" : "accuracy";
  const anyCost = useMemo(() => exp.runs.some((r) => Number(r.summary?.cost_per_case ?? 0) > 0), [exp.runs]);
  return (
    <div className="space-y-8">
      <section className="max-w-3xl space-y-2">
        <Link href="/" className="text-sm text-ink-2 hover:text-ink">← Experiments</Link>
        <h1 className="text-2xl font-semibold tracking-tight">{exp.name}</h1>
        {exp.hypothesis && <p><span className="font-medium">Hypothesis: </span>{exp.hypothesis}</p>}
        {exp.description && <p className="text-ink-2">{exp.description}</p>}
        <p className="text-sm text-muted">
          {exp.runs.length} runs · experiment file at commit <code className="num">{exp.git_sha.slice(0, 7)}</code> ·
          {" "}{accLabel === "hit@k" ? "retrieval only — accuracy is hit@k over answerable cases" : "accuracy = share of cases passing the pass rule"}
        </p>
      </section>

      <section className="space-y-3">
        <div className="flex flex-wrap items-center gap-3">
          <h2 className="text-lg font-semibold">Runs</h2>
          <span className="text-sm text-ink-2">Tick two runs to compare them case by case.</span>
          {selected.length === 2 ? (
            <Link href={`/compare/?base=${selected[0]}&cand=${selected[1]}`}
              className="ml-auto rounded-md bg-series-1 px-3 py-1.5 text-sm font-medium text-white">
              Compare {selected.length} runs →
            </Link>
          ) : (
            <span className="ml-auto rounded-md border border-line px-3 py-1.5 text-sm text-muted">Select {2 - selected.length} more</span>
          )}
        </div>
        <RunsTable runs={exp.runs} selected={selected} onToggle={toggle} accLabel={accLabel} />
      </section>

      <section className="grid gap-6 lg:grid-cols-2">
        {anyCost ? (
          <CostAccuracyScatter runs={exp.runs} accLabel={accLabel} />
        ) : (
          <div className="rounded-lg border border-line bg-surface p-4 text-sm text-ink-2">
            <h3 className="mb-1 font-semibold text-ink">Cost vs {accLabel}</h3>
            These runs made no LLM calls, so they cost nothing; compare them on {accLabel} and latency instead.
          </div>
        )}
        <TagHeatmap runs={exp.runs} />
      </section>
      <MetricBars runs={exp.runs} accLabel={accLabel} />
    </div>
  );
}
