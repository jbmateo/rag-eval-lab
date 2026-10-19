// Shapes the exported experiment files into the series the overview page charts.
import type { ExperimentFile, Run } from "./types";

type Exp = ExperimentFile | null | undefined;

const num = (r: Run, key: string): number | null => {
  const v = r.summary?.[key];
  return typeof v === "number" ? v : null;
};
const cfg = (r: Run, key: string) => r.config[key] as number | string;

export function modelComparison(exp: Exp) {
  return (exp?.runs ?? []).map((r) => ({
    model: String(cfg(r, "model")),
    accuracy: num(r, "accuracy"),
    ci: (r.summary?.accuracy_ci ?? [null, null]) as [number | null, number | null],
    costPerCase: num(r, "cost_per_case"),
  }));
}

export function thresholdCurve(...exps: Exp[]) {
  const seen = new Map<number, { threshold: number; answerRate: number | null; refusalRecall: number | null; accuracy: number | null }>();
  for (const e of exps) for (const r of e?.runs ?? []) {
    const t = Number(cfg(r, "min_similarity"));
    if (!seen.has(t)) seen.set(t, { threshold: t, answerRate: num(r, "answer_rate"), refusalRecall: num(r, "abstention_recall"), accuracy: num(r, "accuracy") });
  }
  return [...seen.values()].sort((a, b) => a.threshold - b.threshold);
}

export function chunkSeries(exp: Exp) {
  return (exp?.runs ?? []).map((r) => ({
    chunk: Number(cfg(r, "chunk_chars")), hit: num(r, "hit@k"), answerRate: num(r, "answer_rate"),
    accuracy: num(r, "accuracy"), costPerCase: num(r, "cost_per_case"),
  })).sort((a, b) => a.chunk - b.chunk);
}

const MODES = ["vector", "bm25", "hybrid"] as const;

export function retrievalByTag(exp: Exp) {
  const runs = new Map((exp?.runs ?? []).map((r) => [String(cfg(r, "retrieval_mode")), r]));
  const tags = [...new Set([...runs.values()].flatMap((r) => Object.entries(r.summary?.by_tag ?? {})
    .filter(([, v]) => v.accuracy !== null && v.n > 0).map(([t]) => t)))].sort();
  return tags.map((tag) => ({
    tag, ...Object.fromEntries(MODES.map((m) => [m, runs.get(m)?.summary?.by_tag?.[tag]?.accuracy ?? null])),
  })) as { tag: string; vector: number | null; bm25: number | null; hybrid: number | null }[];
}

export function sweepGrid(exp: Exp) {
  const runs = exp?.runs ?? [];
  const chunks = [...new Set(runs.map((r) => Number(cfg(r, "chunk_chars"))))].sort((a, b) => a - b);
  const topKs = [...new Set(runs.map((r) => Number(cfg(r, "top_k"))))].sort((a, b) => a - b);
  const at = new Map(runs.map((r) => [`${cfg(r, "chunk_chars")}:${cfg(r, "top_k")}`, num(r, "hit@k")]));
  return { chunks, topKs, value: (chunk: number, topK: number) => at.get(`${chunk}:${topK}`) ?? null };
}

/** Each run's spend counted once, under the experiment that created it (shared runs appear in several). */
export function spendByExperiment(exps: ExperimentFile[]) {
  const runs = new Map(exps.flatMap((e) => e.runs).map((r) => [r.run_id, r]));
  const by = new Map<string, number>();
  for (const r of runs.values()) by.set(r.experiment, (by.get(r.experiment) ?? 0) + (num(r, "cost_spent") ?? 0));
  return [...by].filter(([, v]) => v > 0).map(([experiment, spent]) => ({ experiment, spent })).sort((a, b) => b.spent - a.spent);
}

export function verdictCounts(findings: { verdict: string }[]) {
  const held = findings.filter((f) => f.verdict.startsWith("holds")).length;
  return { held, rejected: findings.filter((f) => f.verdict.startsWith("rejected")).length };
}
