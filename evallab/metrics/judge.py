"""LLM judge: one structured verdict per answered case.

Follows RAG Studio's pattern: messages.create with a JSON-schema output, then check stop_reason and
validate ourselves. A refused, truncated or unparseable reply is None (counted as unjudged), never a guess.
"""
import time
from typing import Protocol

import anthropic
from anthropic import transform_schema
from pydantic import BaseModel, Field, ValidationError

from evallab.adapters.base import LLMCall, RetrievedChunk, Trace
from evallab.cache import DiskCache
from evallab.datasets import Case, evidence_matches
from evallab.metrics.answer import JudgeVerdict

RUBRIC_V1 = """You grade an answer produced by a question-answering system that must answer only from retrieved passages.
You are given the question, the system's answer, the gold evidence (what a correct answer must be based on), an optional reference answer, and the passages the answer cited.

Decide:
- correct: true if the answer states what the gold evidence says in reply to the question. If the answer says it is only a partial answer, it is correct only if what it does state is right AND the part it says is missing is genuinely absent from the gold evidence. Wrong numbers, names or conditions make it incorrect. Ignore style and length.
- unsupported_claims: the number of factual claims in the answer that are not stated in, or directly entailed by, the cited passages.
- reason: one or two sentences explaining the verdict."""


RUBRIC_V2 = RUBRIC_V1 + """
Each cited passage starts with a header naming its document and section, exactly as the system saw it; facts stated in that header (such as a release version or section title) count as stated in the passage."""

RUBRICS = {"v1": RUBRIC_V1, "v2": RUBRIC_V2}


def rubric_for(version: str) -> str:
    if version not in RUBRICS:
        raise ValueError(f"Unknown judge rubric_version {version!r}; known: {', '.join(sorted(RUBRICS))}")
    return RUBRICS[version]


class VerdictModel(BaseModel):
    correct: bool
    unsupported_claims: int = Field(ge=0)
    reason: str


VERDICT_SCHEMA = transform_schema(VerdictModel)


class Judge(Protocol):
    model: str

    def judge(self, case: Case, trace: Trace, cited: list[RetrievedChunk]) -> tuple[JudgeVerdict | None, LLMCall]: ...

    def would_hit(self, case: Case, trace: Trace, cited: list[RetrievedChunk]) -> bool: ...


def build_message(case: Case, trace: Trace, cited: list[RetrievedChunk], rubric_version: str) -> str:
    """v1 is the original rendering (kept byte for byte so its cache stays valid). v2 adds each passage's
    document and section header — what the answering model saw — and what a partial answer says is missing."""
    v2 = rubric_version != "v1"
    answer = "\n".join(f"{i}. {s}" for i, s in enumerate(trace.sentences, start=1)) or "(no sentences)"
    evidence = "\n".join(f"- [{e.document}] {e.evidence}" for e in case.expected)
    header = (lambda i, c: f"[P{i}] ({c.document} — {c.location})" if c.location else f"[P{i}] ({c.document})") if v2 \
        else (lambda i, c: f"[P{i}]")
    passages = "\n\n".join(f"{header(i, c)}\n{c.text}" for i, c in enumerate(cited, start=1)) or "(none)"
    parts = [f"Question: {case.question}", f"Answer status: {trace.status}", f"Answer:\n{answer}"]
    if v2 and trace.status == "partial" and trace.system_detail.get("missing"):
        parts.append(f"What the answer says is missing: {trace.system_detail['missing']}")
    parts.append(f"Gold evidence:\n{evidence}")
    if case.reference_answer:
        parts.append(f"Reference answer: {case.reference_answer}")
    parts.append(f"Cited passages:\n\n{passages}")
    return "\n\n".join(parts)


class ClaudeJudge:
    needs_api_key = True

    def __init__(self, api_key: str, cache: DiskCache, model: str, rubric_version: str, client=None):
        self._client = client
        self.api_key = api_key
        self.cache, self.model, self.rubric_version = cache, model, rubric_version
        self.rubric = rubric_for(rubric_version)

    @property
    def client(self):
        if self._client is None:
            self._client = anthropic.Anthropic(api_key=self.api_key, timeout=60, max_retries=2)
        return self._client

    def _key(self, message: str) -> str:
        return self.cache.key({"model": self.model, "rubric_version": self.rubric_version, "system": self.rubric,
                               "message": message, "schema": VERDICT_SCHEMA, "effort": "low"})

    def would_hit(self, case: Case, trace: Trace, cited: list[RetrievedChunk]) -> bool:
        return self.cache.has(self._key(build_message(case, trace, cited, self.rubric_version)))

    def judge(self, case: Case, trace: Trace, cited: list[RetrievedChunk]) -> tuple[JudgeVerdict | None, LLMCall]:
        message = build_message(case, trace, cited, self.rubric_version)
        key = self._key(message)
        hit = self.cache.get(key)
        if hit is not None:
            return (JudgeVerdict(**hit["verdict"]),
                    LLMCall(self.model, "judge", hit["input_tokens"], hit["output_tokens"], True, 0))
        t0 = time.perf_counter()
        resp = self.client.messages.create(
            model=self.model, max_tokens=2000, system=self.rubric,
            messages=[{"role": "user", "content": message}],
            output_config={"effort": "low", "format": {"type": "json_schema", "schema": VERDICT_SCHEMA}},
        )
        call = LLMCall(self.model, "judge", resp.usage.input_tokens, resp.usage.output_tokens, False,
                       round((time.perf_counter() - t0) * 1000))
        if (resp.stop_reason or "") in ("refusal", "max_tokens"):
            return None, call
        text = next((b.text for b in resp.content if getattr(b, "type", None) == "text"), "")
        try:
            parsed = VerdictModel.model_validate_json(text)
        except (ValidationError, ValueError):
            return None, call
        verdict = JudgeVerdict(parsed.correct, parsed.unsupported_claims, parsed.reason)
        self.cache.put(key, {"verdict": parsed.model_dump(), "input_tokens": call.input_tokens,
                             "output_tokens": call.output_tokens})
        return verdict, call


class FakeJudge:
    """Correct iff a cited chunk holds expected evidence; no unsupported claims. For tests and demos."""

    model = "fake-model"
    needs_api_key = False

    def __init__(self, rules: dict[str, JudgeVerdict | None] | None = None):
        self.rules = rules or {}

    def would_hit(self, case, trace, cited) -> bool:
        return False

    def judge(self, case: Case, trace: Trace, cited: list[RetrievedChunk]) -> tuple[JudgeVerdict | None, LLMCall]:
        call = LLMCall(self.model, "judge", 500, 50, False, 1)
        if case.id in self.rules:
            return self.rules[case.id], call
        by_rank = {c.rank: c for c in trace.retrieved}
        cited = [by_rank[c.chunk_rank] for c in trace.citations if c.chunk_rank in by_rank]
        correct = any(evidence_matches(c.document, c.text, e) for c in cited for e in case.expected)
        return JudgeVerdict(correct, 0, "fake"), call


def make_judge(settings, cache: DiskCache) -> Judge:
    if settings.judge_model == "fake":
        return FakeJudge()
    return ClaudeJudge(settings.anthropic_api_key, cache, settings.judge_model, settings.judge_rubric_version)
