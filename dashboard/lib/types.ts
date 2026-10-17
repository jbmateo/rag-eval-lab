// Shapes written by `evallab export` (evallab/export.py) and the compare report (evallab/compare.py).

export type Json = null | boolean | number | string | Json[] | { [k: string]: Json };

export interface RetrievedChunk { rank: number; document: string; text: string; score: number }
export interface Citation { sentence_index: number; chunk_rank: number | null }
export interface LLMCall { model: string; role: "system" | "judge"; input_tokens: number; output_tokens: number; cached: boolean; ms: number }
export interface Trace {
  retrieved: RetrievedChunk[];
  status: "answered" | "partial" | "abstained" | "retrieval_only";
  sentences: string[];
  citations: Citation[];
  raw_citation_count: number;
  raw_valid_citation_count: number;
  llm_calls: LLMCall[];
  timings_ms: Record<string, number>;
  system_detail: Record<string, Json>;
}
export interface JudgeVerdict { correct: boolean; unsupported_claims: number; reason: string }

export interface CaseRow {
  case_id: string;
  tag: string;
  answerable: boolean;
  status: "ok" | "error";
  pass: boolean | null;
  question?: string | null;
  metrics: Record<string, number | boolean | null | undefined>;
  trace: Trace | null;
  judge: JudgeVerdict | null;
  error: string | null;
  latency_ms: number | null;
  cached: boolean;
  cost_spent_system: number;
  cost_spent_judge: number;
  cost_nominal_system: number;
  cost_nominal_judge: number;
}

export type Summary = Record<string, Json> & {
  accuracy?: number | null;
  accuracy_definition?: string;
  accuracy_ci?: [number | null, number | null];
  by_tag?: Record<string, { n: number; accuracy: number | null }>;
};

export interface Run {
  run_id: string;
  experiment: string;
  label: string;
  config: Record<string, Json>;
  system: string;
  system_version: string;
  dataset: string;
  dataset_sha: string;
  subset: string | null;
  judge_model: string;
  status: string;
  started_at: string;
  finished_at: string | null;
  summary: Summary | null;
}

export interface RunFile { run: Run; cases: CaseRow[] }

export interface ExperimentIndexEntry {
  name: string; slug: string; description: string; hypothesis: string | null; llm: boolean;
  runs: string[]; status: string; best_accuracy: number | null; spent: number;
}
export interface Index {
  generated_at: string;
  budget: { total: number; spent: number };
  experiments: ExperimentIndexEntry[];
  datasets: string[];
}
export interface ExperimentFile {
  name: string; slug: string; yaml: string; git_sha: string; hypothesis: string | null; description: string;
  llm: boolean; gate: Record<string, number | null> | null; runs: Run[];
}
export interface DatasetCase {
  id: string; question: string; answerable: boolean; tag: string;
  expected: { document: string; evidence: string }[]; reference_answer: string | null;
}
export interface DatasetFile {
  name: string;
  manifest: { name: string; versions: { version: string; cases: number; created: string; parent: string | null; changes: string }[] };
  versions: Record<string, DatasetCase[]>;
}

export interface MetricDelta {
  n: number; base: number | null; cand: number | null; delta: number | null;
  lo: number | null; hi: number | null; verdict: string;
}
export interface CaseSnapshot {
  status: string; pass: boolean | null; answer_status: string | null; sentences: string[];
  judge: JudgeVerdict | null; error: string | null;
}
export type CaseStatus = "regressed" | "improved" | "stable_fail" | "stable_pass" | "not_comparable";
export interface CompareCase {
  case_id: string; tag: string; answerable: boolean; question: string | null;
  status: CaseStatus; reason: string | null; base: CaseSnapshot | null; cand: CaseSnapshot | null;
}
export interface CompareReport {
  base: Pick<Run, "run_id" | "experiment" | "label" | "status">;
  cand: Pick<Run, "run_id" | "experiment" | "label" | "status">;
  config_diff: Record<string, [Json, Json]>;
  versions: Record<"base" | "cand", { system_version: string | null; dataset: string | null; judge_model: string | null }>;
  warnings: string[];
  n_compared: number;
  summary: Record<"accuracy" | "mrr" | "latency_ms" | "cost_per_case", MetricDelta>;
  other: Record<string, { base: Json; cand: Json }>;
  mcnemar_p: number;
  mde: number | null;
  counts: Record<"improved" | "regressed" | "stable_pass" | "stable_fail" | "not_comparable", number>;
  errored_after_pass: number;
  by_tag: Record<string, { n: number; improved: number; regressed: number; base_accuracy: number | null; cand_accuracy: number | null }>;
  cases: CompareCase[];
}
