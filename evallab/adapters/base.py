"""The boundary between Eval Lab and a system under test. Everything Eval Lab scores comes from a Trace."""
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Literal, Protocol

from pydantic import BaseModel

Status = Literal["answered", "partial", "abstained", "retrieval_only"]


@dataclass(frozen=True)
class RetrievedChunk:
    rank: int
    document: str
    text: str
    score: float
    location: str = ""  # section heading / page the system showed its model alongside the text


@dataclass(frozen=True)
class Citation:
    sentence_index: int
    chunk_rank: int | None  # None: the citation points at nothing that was retrieved


@dataclass(frozen=True)
class LLMCall:
    model: str
    role: Literal["system", "judge"]
    input_tokens: int
    output_tokens: int
    cached: bool
    ms: int


@dataclass
class Trace:
    retrieved: list[RetrievedChunk]
    status: Status
    sentences: list[str] = field(default_factory=list)
    citations: list[Citation] = field(default_factory=list)
    raw_citation_count: int = 0
    raw_valid_citation_count: int = 0
    llm_calls: list[LLMCall] = field(default_factory=list)
    timings_ms: dict[str, int] = field(default_factory=dict)
    system_detail: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "Trace":
        return cls(
            retrieved=[RetrievedChunk(**c) for c in d["retrieved"]],
            status=d["status"],
            sentences=list(d["sentences"]),
            citations=[Citation(**c) for c in d["citations"]],
            raw_citation_count=d["raw_citation_count"],
            raw_valid_citation_count=d["raw_valid_citation_count"],
            llm_calls=[LLMCall(**c) for c in d["llm_calls"]],
            timings_ms=dict(d["timings_ms"]),
            system_detail=dict(d["system_detail"]),
        )


@dataclass(frozen=True)
class Corpus:
    name: str
    path: Path
    lock_hash: str
    files: list[Path]


class RAGSystem(Protocol):
    name: str

    def version(self) -> str: ...

    def config_schema(self) -> type[BaseModel]: ...

    def prepare(self, corpus: Corpus, config: BaseModel) -> None: ...

    def answer(self, question: str, config: BaseModel, llm: bool) -> Trace: ...

    def would_hit_cache(self, question: str, config: BaseModel) -> bool: ...
