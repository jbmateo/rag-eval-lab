"""Retrieval metrics for one case: hit@k, evidence recall@k, reciprocal rank."""
from evallab.adapters.base import Trace
from evallab.datasets import Case, evidence_matches


def case_metrics(trace: Trace, case: Case, k: int) -> dict:
    if not case.answerable:
        return {"hit": None, "evidence_recall": None, "rr": None}
    top = trace.retrieved[:k]
    found = [any(evidence_matches(c.document, c.text, e) for c in top) for e in case.expected]
    first = next((c.rank for c in top if any(evidence_matches(c.document, c.text, e) for e in case.expected)), None)
    return {
        "hit": any(found),
        "evidence_recall": sum(found) / len(found) if found else 0.0,
        "rr": 1 / first if first else 0.0,
    }
