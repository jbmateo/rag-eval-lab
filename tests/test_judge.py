import json
from types import SimpleNamespace

from evallab.adapters.base import Citation, RetrievedChunk, Trace
from evallab.cache import DiskCache
from evallab.datasets import Case, Expected
from evallab.metrics.answer import JudgeVerdict
from evallab.metrics.judge import RUBRIC_V1, ClaudeJudge, FakeJudge, make_judge

CASE = Case(id="q1", question="How long is the battery?", answerable=True, tag="t",
            expected=[Expected(document="a.md", evidence="The battery lasts 38 minutes.")])
TRACE = Trace(retrieved=[RetrievedChunk(1, "a.md", "The battery lasts 38 minutes.", 1.0),
                         RetrievedChunk(2, "b.md", "Unrelated.", 0.5)],
              status="answered", sentences=["It lasts 38 minutes."], citations=[Citation(0, 1)])


class FakeClient:
    def __init__(self, text, stop="end_turn"):
        self.calls = []
        self.text, self.stop = text, stop
        self.messages = SimpleNamespace(create=self._create)

    def _create(self, **kw):
        self.calls.append(kw)
        blocks = [SimpleNamespace(type="text", text=self.text)] if self.text is not None else []
        return SimpleNamespace(content=blocks, stop_reason=self.stop,
                               usage=SimpleNamespace(input_tokens=700, output_tokens=60))


VALID = json.dumps({"correct": True, "unsupported_claims": 0, "reason": "matches"})


def judge(tmp_path, client):
    return ClaudeJudge("k", DiskCache(tmp_path), "claude-haiku-5-5", "v1", client=client)


def test_claude_judge_parses(tmp_path):
    verdict, call = judge(tmp_path, FakeClient(VALID)).judge(CASE, TRACE, [TRACE.retrieved[0]])
    assert verdict == JudgeVerdict(True, 0, "matches")
    assert (call.model, call.role, call.input_tokens, call.output_tokens, call.cached) == ("claude-haiku-5-5", "judge", 700, 60, False)


def test_judge_request_shape(tmp_path):
    client = FakeClient(VALID)
    judge(tmp_path, client).judge(CASE, TRACE, [TRACE.retrieved[0]])
    kw = client.calls[0]
    assert kw["model"] == "claude-haiku-5-5" and kw["system"] == RUBRIC_V1
    assert kw["output_config"]["effort"] == "low" and kw["output_config"]["format"]["type"] == "json_schema"
    content = kw["messages"][0]["content"]
    assert "How long is the battery?" in content and "It lasts 38 minutes." in content
    assert "The battery lasts 38 minutes." in content


def test_claude_judge_refusal_is_none(tmp_path):
    j = judge(tmp_path, FakeClient(None, "refusal"))
    verdict, call = j.judge(CASE, TRACE, [])
    assert verdict is None and call.input_tokens == 700
    assert list(tmp_path.iterdir()) == []


def test_claude_judge_invalid_json_is_none(tmp_path):
    assert judge(tmp_path, FakeClient("{not json")).judge(CASE, TRACE, [])[0] is None
    assert judge(tmp_path, FakeClient('{"correct": "maybe"}')).judge(CASE, TRACE, [])[0] is None


def test_claude_judge_cache_hit_no_call(tmp_path):
    client = FakeClient(VALID)
    j = judge(tmp_path, client)
    j.judge(CASE, TRACE, [TRACE.retrieved[0]])
    verdict, call = j.judge(CASE, TRACE, [TRACE.retrieved[0]])
    assert len(client.calls) == 1 and call.cached is True and verdict.correct
    assert j.would_hit(CASE, TRACE, [TRACE.retrieved[0]]) and not j.would_hit(CASE, TRACE, [TRACE.retrieved[1]])


def test_fake_judge_uses_cited_evidence():
    v, call = FakeJudge().judge(CASE, TRACE, [])
    assert v.correct and call.role == "judge" and call.model == "fake-model"
    wrong = Trace(retrieved=TRACE.retrieved, status="answered", sentences=["x"], citations=[Citation(0, 2)])
    assert FakeJudge().judge(CASE, wrong, [])[0].correct is False


def test_make_judge(tmp_path, make_settings):
    assert isinstance(make_judge(make_settings(tmp_path), DiskCache(tmp_path)), FakeJudge)
    s = make_settings(tmp_path, judge_model="claude-haiku-5-5", anthropic_api_key="k")
    assert isinstance(make_judge(s, DiskCache(tmp_path)), ClaudeJudge)


V1_MESSAGE = ("Question: How long is the battery?\n\nAnswer status: answered\n\nAnswer:\n1. It lasts 38 minutes.\n\n"
              "Gold evidence:\n- [a.md] The battery lasts 38 minutes.\n\nCited passages:\n\n[P1]\nThe battery lasts 38 minutes.")


def test_v1_message_unchanged():
    """Committed judge caches stay valid: rubric v1 renders exactly as before."""
    from evallab.metrics.judge import build_message
    assert build_message(CASE, TRACE, [TRACE.retrieved[0]], "v1") == V1_MESSAGE


def test_v2_message_shows_document_section_and_missing():
    """Review #4: v2 shows the judge each passage's document and section, and what a partial answer says is missing."""
    from evallab.metrics.judge import RUBRIC_V2, build_message, rubric_for
    chunk = RetrievedChunk(1, "release-notes.md", "Median reconnect time fell from 14 s to 6 s.", 1.0, "## v3.3.1")
    partial = Trace(retrieved=[chunk], status="partial", sentences=["It fell by 8 s."], citations=[Citation(0, 1)],
                    system_detail={"missing": "The date is not stated."})
    msg = build_message(CASE, partial, [chunk], "v2")
    assert "[P1] (release-notes.md — ## v3.3.1)" in msg and "The date is not stated." in msg
    assert rubric_for("v2") == RUBRIC_V2 and "header" in RUBRIC_V2
    import pytest
    with pytest.raises(ValueError):
        rubric_for("v9")
