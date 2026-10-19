import pytest

from evallab.adapters import get_system
from evallab.adapters.base import Citation, LLMCall, RetrievedChunk, Trace
from evallab.adapters.fake import FakeConfig, FakeSystem
from evallab.config import Settings


def _hits(system, questions, quality):
    cfg = FakeConfig(quality=quality)
    n = 0
    for q in questions:
        if not q["answerable"]:
            continue
        t = system.answer(q["question"], cfg, llm=False)
        evidence = {e["evidence"] for e in q["expected"]}
        n += any(c.text in evidence for c in t.retrieved)
    return n


def test_trace_roundtrip():
    t = Trace(
        retrieved=[RetrievedChunk(rank=1, document="a.md", text="x", score=0.5)],
        status="answered", sentences=["x."], citations=[Citation(sentence_index=0, chunk_rank=1)],
        raw_citation_count=2, raw_valid_citation_count=1,
        llm_calls=[LLMCall(model="m", role="system", input_tokens=3, output_tokens=4, cached=False, ms=9)],
        timings_ms={"retrieve": 1, "generate": 9}, system_detail={"k": "v"},
    )
    assert Trace.from_dict(t.to_dict()) == t


def test_fake_is_deterministic(fixture_corpus, fixture_questions):
    a, b = FakeSystem(), FakeSystem()
    cfg = FakeConfig()
    a.prepare(fixture_corpus, cfg)
    b.prepare(fixture_corpus, cfg)
    for q in fixture_questions:
        assert a.answer(q["question"], cfg, llm=True) == b.answer(q["question"], cfg, llm=True)


def test_fake_quality_changes_outcomes(fixture_corpus, fixture_questions):
    s = FakeSystem()
    s.prepare(fixture_corpus, FakeConfig())
    assert _hits(s, fixture_questions, 0.9) > _hits(s, fixture_questions, 0.3)


def test_fake_retrieval_only_has_no_llm_calls(fixture_corpus, fixture_questions):
    s = FakeSystem()
    s.prepare(fixture_corpus, FakeConfig())
    t = s.answer(fixture_questions[0]["question"], FakeConfig(), llm=False)
    assert t.status == "retrieval_only" and t.llm_calls == [] and len(t.retrieved) <= 8


def test_fake_answers_cite_rank_one_and_bill_tokens(fixture_corpus, fixture_questions):
    s = FakeSystem()
    s.prepare(fixture_corpus, FakeConfig(quality=1.0))
    t = s.answer(fixture_questions[0]["question"], FakeConfig(quality=1.0), llm=True)
    assert t.status == "answered" and t.citations == [Citation(sentence_index=0, chunk_rank=1)]
    assert t.llm_calls == [LLMCall(model="fake-model", role="system", input_tokens=1000, output_tokens=200, cached=False, ms=5)]


def test_fake_raise_on(fixture_corpus, fixture_questions):
    s = FakeSystem()
    q = fixture_questions[0]["question"]
    cfg = FakeConfig(raise_on=[q])
    s.prepare(fixture_corpus, cfg)
    with pytest.raises(RuntimeError):
        s.answer(q, cfg, llm=True)


def test_get_system_unknown_name(tmp_path):
    settings = Settings(root=tmp_path, budget_total_usd=1, judge_model="fake", judge_rubric_version="v1",
                        store_path=tmp_path / "s.db", cache_dir=tmp_path / "c", export_dir=tmp_path / "e", systems={})
    with pytest.raises(KeyError, match="fake"):
        get_system("nope", settings)
    assert get_system("fake", settings).name == "fake"
