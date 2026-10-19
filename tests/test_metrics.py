import math

from evallab.adapters.base import Citation, RetrievedChunk, Trace
from evallab.datasets import Case, Expected
from evallab.metrics import answer, retrieval
from evallab.metrics.answer import JudgeVerdict, case_pass, summarize

E1 = Expected(document="a.md", evidence="alpha beta gamma delta")
E2 = Expected(document="b.md", evidence="omega psi chi phi")
ANS = Case(id="q1", question="q?", answerable=True, tag="t1", expected=[E1, E2])
UNANS = Case(id="q2", question="u?", answerable=False, tag="unanswerable", expected=[])
OK = JudgeVerdict(correct=True, unsupported_claims=0, reason="")


def chunks(*specs):
    return [RetrievedChunk(rank=i, document=d, text=t, score=1.0) for i, (d, t) in enumerate(specs, start=1)]


def trace(status="answered", retrieved=None, **kw):
    return Trace(retrieved=retrieved or chunks(("a.md", "alpha beta gamma delta")), status=status, **kw)


def row(case, passed, *, status="ok", metrics=None, latency=100, cached=False, cost=(0.0, 0.0, 0.0, 0.0)):
    return {"case_id": case.id, "tag": case.tag, "answerable": case.answerable, "status": status, "pass": passed,
            "metrics": metrics or {}, "latency_ms": latency, "cached": cached,
            "cost_spent_system": cost[0], "cost_spent_judge": cost[1],
            "cost_nominal_system": cost[2], "cost_nominal_judge": cost[3]}


def test_hit_recall_mrr():
    t = trace(retrieved=chunks(("x.md", "nothing"), ("a.md", "zzz"), ("a.md", "say alpha beta gamma delta!")))
    m = retrieval.case_metrics(t, ANS, k=8)
    assert m == {"hit": True, "evidence_recall": 0.5, "rr": 1 / 3}
    assert retrieval.case_metrics(t, ANS, k=2) == {"hit": False, "evidence_recall": 0.0, "rr": 0.0}
    assert retrieval.case_metrics(t, UNANS, k=8) == {"hit": None, "evidence_recall": None, "rr": None}


def test_pass_rule_answerable():
    assert case_pass(trace(), ANS, OK, llm=True, k=8) is True
    assert case_pass(trace(), ANS, JudgeVerdict(True, 1, ""), llm=True, k=8) is False
    assert case_pass(trace(), ANS, JudgeVerdict(False, 0, ""), llm=True, k=8) is False
    assert case_pass(trace("abstained"), ANS, None, llm=True, k=8) is False
    assert case_pass(trace("partial"), ANS, OK, llm=True, k=8) is True
    assert case_pass(trace(), ANS, None, llm=True, k=8) is None   # unjudged


def test_pass_rule_unanswerable():
    assert case_pass(trace("abstained"), UNANS, None, llm=True, k=8) is True
    assert case_pass(trace("answered"), UNANS, OK, llm=True, k=8) is False


def test_retrieval_only_pass_is_hit():
    t = trace("retrieval_only")
    assert case_pass(t, ANS, None, llm=False, k=8) is True
    assert case_pass(t, UNANS, None, llm=False, k=8) is None


def test_answer_case_metrics():
    t = trace(citations=[Citation(0, 1), Citation(0, None)], raw_citation_count=3, raw_valid_citation_count=2)
    m = answer.case_metrics(t, ANS, None, judged=True)
    assert m == {"abstained": False, "answered": True, "citation_validity_raw": 2 / 3,
                 "citation_validity": 0.5, "unjudged": True}
    assert answer.case_metrics(trace("abstained"), UNANS, None, judged=True)["unjudged"] is False


def test_unjudged_excluded_from_accuracy():
    rows = [row(ANS, True), row(ANS, True), row(ANS, True), row(ANS, False),
            row(ANS, None, metrics={"unjudged": True})]
    s = summarize(rows, llm=True)
    assert s["accuracy"] == 0.75 and s["n_unjudged"] == 1 and s["accuracy_definition"] == "pass_rule"


def test_errored_excluded():
    s = summarize([row(ANS, True), row(ANS, None, status="error")], llm=True)
    assert s["accuracy"] == 1.0 and s["n_errored"] == 1 and s["n"] == 2


def test_retrieval_only_accuracy_is_hit():
    rows = [row(ANS, True, metrics={"hit": True, "evidence_recall": 1.0, "rr": 1.0}),
            row(ANS, False, metrics={"hit": False, "evidence_recall": 0.0, "rr": 0.0}),
            row(UNANS, None, metrics={"hit": None, "evidence_recall": None, "rr": None})]
    s = summarize(rows, llm=False)
    assert s["accuracy_definition"] == "hit@k" and s["accuracy"] == 0.5 and s["hit@k"] == 0.5 and s["mrr"] == 0.5


def test_latency_ignores_cached():
    rows = [row(ANS, True, latency=v) for v in (10, 20, 30, 40)] + [row(ANS, True, latency=9999, cached=True)]
    s = summarize(rows, llm=True)
    assert s["latency_p50_ms"] == 20 and s["latency_p95_ms"] == 40


def test_abstention_precision_recall():
    rows = [row(UNANS, True, metrics={"abstained": True, "answered": False}),
            row(UNANS, False, metrics={"abstained": False, "answered": True}),
            row(ANS, False, metrics={"abstained": True, "answered": False}),
            row(ANS, True, metrics={"abstained": False, "answered": True})]
    s = summarize(rows, llm=True)
    assert s["abstention_precision"] == 0.5 and s["abstention_recall"] == 0.5 and s["answer_rate"] == 0.5


def test_costs_split_and_per_case():
    rows = [row(ANS, True, cost=(0.01, 0.002, 0.02, 0.004)), row(ANS, True, cost=(0.0, 0.0, 0.02, 0.004))]
    s = summarize(rows, llm=True)
    assert math.isclose(s["cost_spent"], 0.012) and math.isclose(s["cost_nominal"], 0.048)
    assert math.isclose(s["cost_spent_system"], 0.01) and math.isclose(s["cost_spent_judge"], 0.002)
    assert math.isclose(s["cost_per_case"], 0.02)


def test_by_tag():
    rows = [row(ANS, True), row(ANS, False), row(UNANS, True)]
    assert summarize(rows, llm=True)["by_tag"] == {"t1": {"n": 2, "accuracy": 0.5},
                                                   "unanswerable": {"n": 1, "accuracy": 1.0}}


def test_empty_denominators_are_none():
    only_answerable = [row(ANS, True, metrics={"abstained": False, "answered": True})]
    s = summarize(only_answerable, llm=True)
    assert s["abstention_recall"] is None and s["abstention_precision"] is None
    all_unjudged = [row(ANS, None, metrics={"unjudged": True})]
    assert summarize(all_unjudged, llm=True)["accuracy"] is None
    r = summarize([row(ANS, True, metrics={"hit": True, "evidence_recall": 1.0, "rr": 1.0})], llm=False)
    assert r["answer_rate"] is None and r["citation_validity"] is None
    empty = summarize([], llm=True)
    assert empty["accuracy"] is None and empty["latency_p50_ms"] is None and empty["cost_per_case"] is None
    for v in [*s.values(), *empty.values()]:
        assert not (isinstance(v, float) and math.isnan(v))
