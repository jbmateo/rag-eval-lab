// Port of evallab/compare.py::compare_runs. Must produce JSON identical to the Python version
// (pinned by tests/compare.test.ts against tests/fixtures/compare_expected.json).
import { fsumLtr, mcnemarExact, mdePaired, pairedBootstrapCi, verdict } from "./stats";
import type { CaseRow, CaseSnapshot, CompareCase, CompareReport, Json, MetricDelta, Run } from "./types";

const STATUS_ORDER = ["regressed", "improved", "stable_fail", "stable_pass", "not_comparable"] as const;
const INCOMPLETE = ["partial", "running", "degraded"];
const OTHER_METRICS = ["hit@k", "evidence_recall@k", "answer_rate", "abstention_precision", "abstention_recall",
  "citation_validity", "latency_p50_ms", "latency_p95_ms"];

type RunLike = Pick<Run, "run_id" | "status" | "config" | "dataset"> & Partial<Run>;

const has = (v: unknown) => v !== undefined && v !== null;
const orNull = <T,>(v: T | undefined): T | null => (v === undefined ? null : v);

function stable(v: unknown): string {
  if (Array.isArray(v)) return `[${v.map(stable).join(",")}]`;
  if (v && typeof v === "object") {
    return `{${Object.keys(v).sort().map((k) => `${JSON.stringify(k)}:${stable((v as Record<string, unknown>)[k])}`).join(",")}}`;
  }
  return JSON.stringify(v === undefined ? null : v);
}

function mean(values: number[]): number | null {
  return values.length ? fsumLtr(values) / values.length : null;
}

function reason(b: CaseRow, c: CaseRow, answerable: boolean): string | null {
  const bm = b.metrics, cm = c.metrics;
  if (has(bm.hit) && has(cm.hit) && bm.hit !== cm.hit) return cm.hit ? "retrieval_gained" : "retrieval_lost";
  if (has(bm.abstained) && has(cm.abstained) && bm.abstained !== cm.abstained) {
    if (answerable) return cm.abstained ? "wrongly_abstained" : "stopped_abstaining";
    return cm.abstained ? "correctly_abstained" : "hallucinated";
  }
  const bj = b.judge, cj = c.judge;
  if (bj && cj) {
    if (bj.correct !== cj.correct) return cj.correct ? "judge_correct" : "judge_incorrect";
    if (bj.unsupported_claims !== cj.unsupported_claims) return "unsupported_claims";
  }
  return null;
}

function snapshot(row: CaseRow | undefined): CaseSnapshot | null {
  if (!row) return null;
  const trace = row.trace;
  return {
    status: row.status, pass: row.pass, answer_status: trace ? trace.status : null,
    sentences: trace?.sentences ?? [], judge: orNull(row.judge), error: orNull(row.error),
  };
}

function metric(baseVals: number[], candVals: number[], higherIsBetter = true): MetricDelta {
  const [delta, lo, hi] = pairedBootstrapCi(baseVals, candVals);
  return { n: baseVals.length, base: mean(baseVals), cand: mean(candVals), delta, lo, hi, verdict: verdict(lo, hi, higherIsBetter) };
}

const runView = (r: RunLike) => ({
  run_id: r.run_id, experiment: orNull(r.experiment), label: orNull(r.label), status: r.status,
}) as CompareReport["base"];

export function compareRuns(base: RunLike, baseRows: CaseRow[], cand: RunLike, candRows: CaseRow[],
  allowIncomplete = false): CompareReport {
  const warnings: string[] = [];
  for (const [role, run] of [["baseline", base], ["candidate", cand]] as const) {
    if (INCOMPLETE.includes(run.status)) {
      if (!allowIncomplete) {
        throw new Error(`The ${role} run ${run.run_id} is ${run.status}; pass --allow-incomplete to compare anyway`);
      }
      warnings.push(`${role} run is ${run.status}`);
    }
  }
  const bBy = new Map(baseRows.map((r) => [r.case_id, r]));
  const cBy = new Map(candRows.map((r) => [r.case_id, r]));
  const ids = [...new Set([...bBy.keys(), ...cBy.keys()])].sort();
  const shared = ids.filter((i) => bBy.has(i) && cBy.has(i));
  if (base.dataset !== cand.dataset) {
    warnings.unshift(`datasets differ (${base.dataset} vs ${cand.dataset}): comparing ${shared.length} shared cases`);
  }

  const cases: CompareCase[] = [];
  const pairs: [CaseRow, CaseRow][] = [];
  for (const cid of ids) {
    const b = bBy.get(cid), c = cBy.get(cid);
    const ref = (b ?? c)!;
    const entry: CompareCase = {
      case_id: cid, tag: ref.tag, answerable: ref.answerable, question: orNull(ref.question),
      status: "not_comparable", reason: null, base: snapshot(b), cand: snapshot(c),
    };
    const ok = !!b && !!c && b.status === "ok" && c.status === "ok";
    if (ok && b!.pass !== null && c!.pass !== null) {
      pairs.push([b!, c!]);
      if (b!.pass && c!.pass) entry.status = "stable_pass";
      else if (!b!.pass && !c!.pass) entry.status = "stable_fail";
      else {
        entry.status = c!.pass ? "improved" : "regressed";
        entry.reason = reason(b!, c!, ref.answerable);
      }
    } else if (ok && b!.pass === null && c!.pass === null) {
      continue;
    }
    cases.push(entry);
  }
  cases.sort((x, y) => STATUS_ORDER.indexOf(x.status) - STATUS_ORDER.indexOf(y.status)
    || (x.case_id < y.case_id ? -1 : x.case_id > y.case_id ? 1 : 0));

  const erroredAfterPass = shared.filter((cid) => bBy.get(cid)!.status === "ok" && bBy.get(cid)!.pass
    && cBy.get(cid)!.status === "error").length;
  const count = (s: string) => cases.filter((e) => e.status === s).length;
  const counts = { improved: count("improved"), regressed: count("regressed"), stable_pass: count("stable_pass"),
    stable_fail: count("stable_fail"), not_comparable: count("not_comparable") };
  const num = (v: unknown) => Number(v);
  const rr = pairs.filter(([b, c]) => has(b.metrics.rr) && has(c.metrics.rr));
  const lat = pairs.filter(([b, c]) => !b.cached && !c.cached && b.latency_ms !== null && c.latency_ms !== null);
  const summary = {
    accuracy: metric(pairs.map(([b]) => num(b.pass)), pairs.map(([, c]) => num(c.pass))),
    mrr: metric(rr.map(([b]) => num(b.metrics.rr)), rr.map(([, c]) => num(c.metrics.rr))),
    latency_ms: metric(lat.map(([b]) => num(b.latency_ms)), lat.map(([, c]) => num(c.latency_ms)), false),
    cost_per_case: metric(pairs.map(([b]) => b.cost_nominal_system), pairs.map(([, c]) => c.cost_nominal_system), false),
  };
  const byTag: CompareReport["by_tag"] = {};
  for (const tag of [...new Set(pairs.map(([b]) => b.tag))].sort()) {
    const tp = pairs.filter(([b]) => b.tag === tag);
    byTag[tag] = {
      n: tp.length,
      improved: tp.filter(([b, c]) => !b.pass && c.pass).length,
      regressed: tp.filter(([b, c]) => b.pass && !c.pass).length,
      base_accuracy: mean(tp.map(([b]) => num(b.pass))),
      cand_accuracy: mean(tp.map(([, c]) => num(c.pass))),
    };
  }
  const keys = [...new Set([...Object.keys(base.config), ...Object.keys(cand.config)])].sort();
  const configDiff: Record<string, [Json, Json]> = {};
  for (const k of keys) {
    const bv = orNull(base.config[k]), cv = orNull(cand.config[k]);
    if (stable(bv) !== stable(cv)) configDiff[k] = [bv, cv];
  }
  const bs = (base.summary ?? {}) as Record<string, Json>, cs = (cand.summary ?? {}) as Record<string, Json>;
  const versions = (r: RunLike) => ({
    system_version: orNull(r.system_version), dataset: orNull(r.dataset), judge_model: orNull(r.judge_model),
  });
  return {
    base: runView(base), cand: runView(cand), config_diff: configDiff,
    versions: { base: versions(base), cand: versions(cand) },
    warnings, n_compared: pairs.length, summary,
    other: Object.fromEntries(OTHER_METRICS.map((m) => [m, { base: orNull(bs[m]), cand: orNull(cs[m]) }])),
    mcnemar_p: mcnemarExact(counts.improved, counts.regressed),
    mde: mdePaired(pairs.length, counts.improved + counts.regressed),
    counts, errored_after_pass: erroredAfterPass, by_tag: byTag, cases,
  };
}
