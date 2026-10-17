"""Answer metrics, the case pass rule, and run-level aggregation.

Aggregation works on flat case rows (as stored), so it never needs the trace:
  case_id, tag, answerable, status ("ok" | "error"), pass (bool | None), metrics (dict),
  latency_ms, cached, cost_spent_system, cost_spent_judge, cost_nominal_system, cost_nominal_judge.
"""
import math
from dataclasses import dataclass

from evallab.adapters.base import Trace
from evallab.datasets import Case
from evallab.metrics import retrieval


@dataclass(frozen=True)
class JudgeVerdict:
    correct: bool
    unsupported_claims: int
    reason: str


def _ratio(num: float, den: float) -> float | None:
    return num / den if den else None


def _mean(values: list) -> float | None:
    values = [v for v in values if v is not None]
    return sum(values) / len(values) if values else None


def case_metrics(trace: Trace, case: Case, verdict: JudgeVerdict | None, judged: bool) -> dict:
    answered = trace.status in ("answered", "partial")
    valid_shown = sum(1 for c in trace.citations if c.chunk_rank is not None)
    return {
        "abstained": trace.status == "abstained",
        "answered": answered,
        "citation_validity_raw": _ratio(trace.raw_valid_citation_count, trace.raw_citation_count),
        "citation_validity": _ratio(valid_shown, len(trace.citations)),
        "unjudged": answered and judged and verdict is None,
    }


def case_pass(trace: Trace, case: Case, verdict: JudgeVerdict | None, llm: bool, k: int) -> bool | None:
    if not llm:
        return retrieval.case_metrics(trace, case, k)["hit"]
    if not case.answerable:
        return trace.status == "abstained"
    if trace.status not in ("answered", "partial"):
        return False
    if verdict is None:
        return None
    return verdict.correct and verdict.unsupported_claims == 0


def _percentile(values: list[float], p: float) -> float | None:
    if not values:
        return None
    s = sorted(values)
    return s[max(0, math.ceil(p * len(s)) - 1)]


def summarize(case_rows: list[dict], llm: bool) -> dict:
    ok = [r for r in case_rows if r["status"] == "ok"]
    answerable = [r for r in ok if r["answerable"]]
    unanswerable = [r for r in ok if not r["answerable"]]
    m = lambda r, key: r["metrics"].get(key)
    passes = [r["pass"] for r in ok if r["pass"] is not None]

    abstained = [r for r in ok if m(r, "abstained")]
    correct_abstentions = sum(1 for r in abstained if not r["answerable"])
    raw_cites = [m(r, "citation_validity_raw") for r in ok]

    by_tag: dict[str, dict] = {}
    for tag in sorted({r["tag"] for r in ok}):
        tagged = [r["pass"] for r in ok if r["tag"] == tag and r["pass"] is not None]
        by_tag[tag] = {"n": len(tagged), "accuracy": _mean(tagged)}

    latencies = [r["latency_ms"] for r in ok if not r["cached"] and r["latency_ms"] is not None]
    spent_sys = sum(r["cost_spent_system"] for r in case_rows)
    spent_judge = sum(r["cost_spent_judge"] for r in case_rows)
    nominal_sys = sum(r["cost_nominal_system"] for r in case_rows)
    nominal_judge = sum(r["cost_nominal_judge"] for r in case_rows)
    return {
        "n": len(case_rows),
        "n_errored": len(case_rows) - len(ok),
        "n_unjudged": sum(1 for r in ok if m(r, "unjudged")),
        "accuracy": _mean(passes),
        "accuracy_definition": "pass_rule" if llm else "hit@k",
        "hit@k": _mean([m(r, "hit") for r in answerable]),
        "evidence_recall@k": _mean([m(r, "evidence_recall") for r in answerable]),
        "mrr": _mean([m(r, "rr") for r in answerable]),
        "answer_rate": _mean([float(m(r, "answered")) for r in answerable if m(r, "answered") is not None]) if llm else None,
        "abstention_precision": _ratio(correct_abstentions, len(abstained)) if llm else None,
        "abstention_recall": _ratio(correct_abstentions, len(unanswerable)) if llm and unanswerable else None,
        "citation_validity_raw": _mean(raw_cites) if llm else None,
        "citation_validity": _mean([m(r, "citation_validity") for r in ok]) if llm else None,
        "latency_p50_ms": _percentile(latencies, 0.5),
        "latency_p95_ms": _percentile(latencies, 0.95),
        "cost_spent": spent_sys + spent_judge,
        "cost_nominal": nominal_sys + nominal_judge,
        "cost_spent_system": spent_sys,
        "cost_spent_judge": spent_judge,
        "cost_per_case": _ratio(nominal_sys, len(ok)),
        "by_tag": by_tag,
    }
