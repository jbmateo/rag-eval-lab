import { describe, expect, it } from "vitest";
import { chunkSeries, modelComparison, retrievalByTag, spendByExperiment, sweepGrid, thresholdCurve, verdictCounts } from "../lib/overview";
import type { ExperimentFile, Run } from "../lib/types";

const run = (id: string, experiment: string, config: Record<string, unknown>, summary: Record<string, unknown>): Run => ({
  run_id: id, experiment, label: Object.entries(config).map(([k, v]) => `${k}=${v}`).join(","), config: config as Run["config"],
  system: "rag_studio", system_version: "v", dataset: "lumen@v1", dataset_sha: "s", subset: null, judge_model: "j",
  status: "complete", started_at: "", finished_at: null, summary: summary as Run["summary"],
});
const exp = (name: string, runs: Run[]): ExperimentFile => ({ name, slug: name, yaml: "", git_sha: "", hypothesis: null, description: "", llm: true, gate: null, runs });

describe("overview data", () => {
  it("modelComparison pairs accuracy with its CI and cost", () => {
    const e = exp("model-sweep", [
      run("s", "model-sweep", { model: "claude-sonnet-5-5" }, { accuracy: 0.883, accuracy_ci: [0.8, 0.95], cost_per_case: 0.0109 }),
      run("h", "baseline", { model: "claude-haiku-5-5" }, { accuracy: 0.917, accuracy_ci: [0.833, 0.983], cost_per_case: 0.00062 }),
    ]);
    expect(modelComparison(e)).toEqual([
      { model: "claude-sonnet-5-5", accuracy: 0.883, ci: [0.8, 0.95], costPerCase: 0.0109 },
      { model: "claude-haiku-5-5", accuracy: 0.917, ci: [0.833, 0.983], costPerCase: 0.00062 },
    ]);
    expect(modelComparison(null)).toEqual([]);
  });

  it("thresholdCurve merges sweeps, sorts by threshold and drops duplicates", () => {
    const low = exp("gate-sweep", [0.45, 0.25, 0.35].map((t) => run(`l${t}`, "gate-sweep", { min_similarity: t }, { answer_rate: 1, abstention_recall: 1, accuracy: 0.9 })));
    const high = exp("gate-sweep-high", [run("h7", "x", { min_similarity: 0.7 }, { answer_rate: 0.8, abstention_recall: 1, accuracy: 0.8 }),
      run("l0.35", "gate-sweep", { min_similarity: 0.35 }, { answer_rate: 1, abstention_recall: 1, accuracy: 0.9 })]);
    expect(thresholdCurve(low, high).map((p) => p.threshold)).toEqual([0.25, 0.35, 0.45, 0.7]);
    expect(thresholdCurve(low, high)[3]).toEqual({ threshold: 0.7, answerRate: 0.8, refusalRecall: 1, accuracy: 0.8 });
  });

  it("chunkSeries sorts by chunk size", () => {
    const e = exp("chunk-sweep", [4000, 1000].map((c) => run(`c${c}`, "chunk-sweep", { chunk_chars: c },
      { "hit@k": c / 4000, answer_rate: 0.95, accuracy: 0.9, cost_per_case: c / 1e6 })));
    expect(chunkSeries(e)).toEqual([
      { chunk: 1000, hit: 0.25, answerRate: 0.95, accuracy: 0.9, costPerCase: 0.001 },
      { chunk: 4000, hit: 1, answerRate: 0.95, accuracy: 0.9, costPerCase: 0.004 },
    ]);
  });

  it("retrievalByTag reads per-tag hit rates by mode, answerable tags only", () => {
    const tag = (e: number, n: number) => ({ by_tag: { exact_term: { n: 20, accuracy: e }, natural: { n: 20, accuracy: n }, unanswerable: { n: 0, accuracy: null } } });
    const e = exp("rq1-retrieval", [run("v", "rq1", { retrieval_mode: "vector" }, tag(0.95, 0.95)),
      run("b", "rq1", { retrieval_mode: "bm25" }, tag(1, 0.75)), run("h", "rq1", { retrieval_mode: "hybrid" }, tag(1, 0.95))]);
    expect(retrievalByTag(e)).toEqual([
      { tag: "exact_term", vector: 0.95, bm25: 1, hybrid: 1 },
      { tag: "natural", vector: 0.95, bm25: 0.75, hybrid: 0.95 },
    ]);
  });

  it("sweepGrid lays hit@k out by chunk size × top_k", () => {
    const e = exp("retrieval-sweep", [[1000, 4], [1000, 8], [2000, 4]].map(([c, k]) =>
      run(`${c}-${k}`, "rs", { chunk_chars: c, top_k: k }, { "hit@k": c / 10000 + k / 100 })));
    const g = sweepGrid(e);
    expect(g.chunks).toEqual([1000, 2000]);
    expect(g.topKs).toEqual([4, 8]);
    expect(g.value(1000, 8)).toBeCloseTo(0.18);
    expect(g.value(2000, 8)).toBeNull();
  });

  it("spendByExperiment counts each run once, under the experiment that created it", () => {
    const shared = run("b", "baseline", {}, { cost_spent: 0.04 });
    const exps = [exp("baseline", [shared]), exp("prompt-sweep", [shared, run("p", "prompt-sweep", {}, { cost_spent: 0.042 })]),
      exp("free", [run("f", "free", {}, { cost_spent: 0 })])];
    expect(spendByExperiment(exps)).toEqual([{ experiment: "prompt-sweep", spent: 0.042 }, { experiment: "baseline", spent: 0.04 }]);
  });

  it("verdictCounts groups held and rejected", () => {
    expect(verdictCounts([{ verdict: "rejected" }, { verdict: "holds" }, { verdict: "holds (within noise)" }]))
      .toEqual({ held: 2, rejected: 1 });
  });
});
