import sys
from pathlib import Path

import pytest
from pydantic import ValidationError

from evallab.adapters.base import Citation
from evallab.adapters.rag_studio import RagStudioSystem
from evallab.config import load_settings
from evallab.datasets import load_dataset
from evallab.metrics import retrieval
from evallab.metrics.answer import summarize

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="module")
def settings():
    return load_settings(ROOT)


@pytest.fixture(scope="module")
def lumen(settings):
    return load_dataset("lumen@v1", settings)


@pytest.fixture(scope="module")
def studio(settings, lumen, tmp_path_factory):
    from app.answer.llm import FakeLLM

    s = settings.model_copy(update={"cache_dir": tmp_path_factory.mktemp("cache")})
    system = RagStudioSystem(s, embedder_kind="hash", llm=FakeLLM())
    system.prepare(lumen.corpus, system.config_schema()())
    return system


def _q(lumen, answerable=True):
    return next(c for c in lumen.cases if c.answerable == answerable)


def test_schema_rejects_unknown_model(studio):
    schema = studio.config_schema()
    assert schema().model == "claude-sonnet-5-5" and schema().prompt_variant == "default"
    with pytest.raises(ValidationError):
        schema(model="gpt-x")
    with pytest.raises(ValidationError):
        schema(prompt_variant="nope")
    with pytest.raises(ValidationError):
        schema(unknown_key=1)


def test_retrieval_only_trace(studio, lumen):
    t = studio.answer(_q(lumen).question, studio.config_schema()(), llm=False)
    assert t.status == "retrieval_only" and t.llm_calls == []
    assert [c.rank for c in t.retrieved] == list(range(1, len(t.retrieved) + 1)) and len(t.retrieved) == 8
    assert {c.document for c in t.retrieved} <= {p.name for p in lumen.corpus.files}


def test_llm_trace_mapping(studio, lumen):
    cfg = studio.config_schema()(min_similarity=0.0)
    t = studio.answer(_q(lumen).question, cfg, llm=True)
    # Studio's FakeLLM answers with its top passage citing c1, plus a sentence citing the non-existent c99,
    # which Studio's verifier drops — so the shown answer is "partial"
    assert t.status == "partial" and t.citations == [Citation(sentence_index=0, chunk_rank=1)]
    assert (t.raw_citation_count, t.raw_valid_citation_count) == (2, 1)
    assert len(t.llm_calls) == 1 and t.llm_calls[0].role == "system" and t.llm_calls[0].model == "claude-sonnet-5-5"
    assert t.system_detail["dropped_citations"] == 1 and t.system_detail["gate_passed"] is True


def test_gate_fail_maps_to_abstained_without_llm(studio, lumen):
    cfg = studio.config_schema()(min_similarity=0.99, retrieval_mode="vector")
    t = studio.answer(_q(lumen).question, cfg, llm=True)
    assert t.status == "abstained" and t.llm_calls == []
    assert studio.would_hit_cache(_q(lumen).question, cfg) is True


def test_would_hit_cache_follows_studio_cache(settings, lumen, tmp_path):
    from app.answer.llm import CachedLLM, FakeLLM

    s = settings.model_copy(update={"cache_dir": tmp_path})
    system = RagStudioSystem(s, embedder_kind="hash", llm=CachedLLM(FakeLLM(), tmp_path / "system"))
    cfg = system.config_schema()(min_similarity=0.0)
    system.prepare(lumen.corpus, cfg)
    q = _q(lumen).question
    assert system.would_hit_cache(q, cfg) is False
    first = system.answer(q, cfg, llm=True)
    assert first.llm_calls[0].cached is False
    assert system.would_hit_cache(q, cfg) is True
    assert system.answer(q, cfg, llm=True).llm_calls[0].cached is True
    assert system.would_hit_cache(q, system.config_schema()(min_similarity=0.0, prompt_variant="terse_cite_all")) is False


def test_version_reports_dirty(studio, monkeypatch):
    calls = {"rev-parse": "abc1234", "status": "", "diff": "diff text"}
    monkeypatch.setattr(studio, "_git", lambda *args: calls[args[0]])
    assert studio.version() == "rag-studio@abc1234"
    calls["status"] = " M app/x.py"
    v = studio.version()
    assert v.startswith("rag-studio@abc1234+dirty:") and len(v.split(":")[1]) == 8


@pytest.mark.slow
def test_metric_parity_with_studio(settings, lumen):
    """Eval Lab's retrieval metrics equal Studio's research/metrics.py on the same retrievals."""
    sys.path.insert(0, str((ROOT / settings.systems["rag_studio"]["path"]).resolve()))
    from research.metrics import summarize as studio_summarize

    system = RagStudioSystem(settings, embedder_kind="fastembed")
    questions = [c.model_dump() for c in lumen.cases]
    for mode in ("vector", "bm25", "hybrid"):
        cfg = system.config_schema()(retrieval_mode=mode)
        system.prepare(lumen.corpus, cfg)
        records, rows = [], []
        for case in lumen.cases:
            t = system.answer(case.question, cfg, llm=False)
            records.append({"qid": case.id, "status": "retrieval_only",
                            "retrieved": [{"document_name": c.document, "text": c.text} for c in t.retrieved]})
            m = retrieval.case_metrics(t, case, 8)
            rows.append({"case_id": case.id, "tag": case.tag, "answerable": case.answerable, "status": "ok",
                         "pass": m["hit"], "metrics": m, "latency_ms": 1, "cached": False,
                         "cost_spent_system": 0.0, "cost_spent_judge": 0.0,
                         "cost_nominal_system": 0.0, "cost_nominal_judge": 0.0})
        ours, theirs = summarize(rows, llm=False), studio_summarize(records, questions)
        assert ours["hit@k"] == pytest.approx(theirs["hit@8"], abs=1e-12), mode
        assert ours["mrr"] == pytest.approx(theirs["mrr"], abs=1e-12), mode
