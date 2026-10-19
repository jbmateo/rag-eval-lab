"""A deterministic stand-in system for tests: word-overlap retrieval whose quality is a config knob.

Each question gets a fixed pseudo-random draw u in [0, 1) from its text. When u > quality the best
chunk is withheld, so raising quality can only add hits. The system abstains when nothing it
retrieves shares at least two content words with the question.
"""
import hashlib
import re

from pydantic import BaseModel

from evallab.adapters.base import Citation, Corpus, LLMCall, RetrievedChunk, Trace

STOPWORDS = {"what", "which", "does", "with", "that", "from", "this", "when", "where", "long", "many", "much",
             "must", "take", "every", "after", "before", "within", "time", "they", "their", "there", "into"}
MIN_OVERLAP = 2


class FakeConfig(BaseModel, extra="forbid"):
    quality: float = 0.8
    top_k: int = 8
    model: str = "fake-model"
    raise_on: list[str] = []


def _words(text: str) -> set[str]:
    return {w for w in re.findall(r"[a-z0-9][a-z0-9.\-:]*[a-z0-9]|[a-z0-9]", text.lower()) if len(w) >= 4} - STOPWORDS


def _draw(question: str) -> float:
    return int(hashlib.sha256(question.encode()).hexdigest()[:8], 16) / 2**32


class FakeSystem:
    name = "fake"
    needs_api_key = False

    def __init__(self, all_cached: bool = False):
        self.all_cached = all_cached
        self.chunks: list[tuple[str, str]] = []

    def version(self) -> str:
        return "fake@1"

    def config_schema(self) -> type[BaseModel]:
        return FakeConfig

    def prepare(self, corpus: Corpus, config: BaseModel) -> None:
        self.chunks = []
        for path in corpus.files:
            for line in path.read_text().splitlines():
                line = line.strip()
                if line and not line.startswith("#"):
                    self.chunks.append((path.name, line))

    def would_hit_cache(self, question: str, config: BaseModel) -> bool:
        return self.all_cached

    def answer(self, question: str, config: FakeConfig, llm: bool) -> Trace:
        if question in config.raise_on:
            raise RuntimeError(f"fake failure for {question!r}")
        q = _words(question)
        scored = sorted(
            ((len(q & _words(text)), doc, text) for doc, text in self.chunks),
            key=lambda s: (-s[0], s[1], s[2]),
        )
        if _draw(question) > config.quality:
            scored = scored[1:]
        top = scored[: config.top_k]
        retrieved = [RetrievedChunk(rank=i, document=doc, text=text, score=float(s))
                     for i, (s, doc, text) in enumerate(top, start=1)]
        if not llm:
            return Trace(retrieved=retrieved, status="retrieval_only", timings_ms={"retrieve": 1})
        call = LLMCall(model=config.model, role="system", input_tokens=1000, output_tokens=200,
                       cached=self.all_cached, ms=5)
        timings = {"retrieve": 1, "generate": 5}
        if not top or top[0][0] < MIN_OVERLAP:
            return Trace(retrieved=retrieved, status="abstained", llm_calls=[call], timings_ms=timings)
        return Trace(
            retrieved=retrieved, status="answered", sentences=[top[0][2]],
            citations=[Citation(sentence_index=0, chunk_rank=1)],
            raw_citation_count=1, raw_valid_citation_count=1, llm_calls=[call], timings_ms=timings,
        )
