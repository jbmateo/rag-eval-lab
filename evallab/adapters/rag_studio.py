"""Adapter for RAG Studio (../rag-studio/backend, installed editable). The only module that imports it."""
import atexit
import hashlib
import shutil
import subprocess
import tempfile
import uuid
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, field_validator

from app.answer.llm import CachedLLM, ClaudeLLM
from app.answer.prompts import PROMPTS
from app.answer.schema import Passage
from app.answer.service import answer_question_detailed
from app.config import PipelineConfig
from app.db import connect, init_db
from app.embeddings import make_embedder
from app.ingest.pipeline import ingest_document
from app.retrieval import retrieve
from app.store import create_document

from evallab.adapters.base import Citation, Corpus, LLMCall, RetrievedChunk, Trace
from evallab.config import Settings

ABSTAINED = ("not_found", "insufficient_evidence")


class StudioConfig(BaseModel):
    """Mirrors app.config.PipelineConfig field for field."""

    model_config = ConfigDict(extra="forbid")

    retrieval_mode: Literal["vector", "bm25", "hybrid"] = "hybrid"
    min_similarity: float = 0.35
    verify_citations: bool = True
    chunk_chars: int = 2000
    top_k: int = 8
    model: Literal["claude-sonnet-5-5", "claude-haiku-5-5"] = "claude-sonnet-5-5"
    prompt_variant: str = "default"

    @field_validator("prompt_variant")
    @classmethod
    def _known_prompt(cls, v: str) -> str:
        if v not in PROMPTS:
            raise ValueError(f"unknown prompt_variant {v!r}; known: {sorted(PROMPTS)}")
        return v


class _Spy:
    """Records whether each draft attempt was served from the cache."""

    def __init__(self, inner):
        self.inner, self.cached = inner, []

    def draft(self, question, passages, model, **kw):
        out = self.inner.draft(question, passages, model, **kw)
        self.cached.append(bool(out.cached))
        return out


class RagStudioSystem:
    name = "rag_studio"
    needs_api_key = True

    def __init__(self, settings: Settings, embedder_kind: str | None = None, llm=None):
        cfg = settings.systems.get("rag_studio", {})
        self.backend = (settings.root / cfg.get("path", "../rag-studio/backend")).resolve()
        self.embedder_kind = embedder_kind or cfg.get("embedder", "fastembed")
        self.embedder = make_embedder(self.embedder_kind)
        self._llm = llm
        self._settings = settings
        self._dbs: dict[tuple[int, str], tuple] = {}

    @property
    def llm(self):
        if self._llm is None:
            self._llm = CachedLLM(ClaudeLLM(self._settings.anthropic_api_key), self._settings.cache_dir / "system")
        return self._llm

    # identity -------------------------------------------------------------------------------------
    def _git(self, *args: str) -> str:
        return subprocess.run(["git", *args], cwd=self.backend, capture_output=True, text=True).stdout.strip()

    def version(self) -> str:
        v = f"rag-studio@{self._git('rev-parse', '--short', 'HEAD')}"
        if self._git("status", "--porcelain", "--", "app"):
            v += "+dirty:" + hashlib.sha256(self._git("diff", "HEAD", "--", "app").encode()).hexdigest()[:8]
        return v

    def config_schema(self) -> type[BaseModel]:
        return StudioConfig

    # corpus ---------------------------------------------------------------------------------------
    def prepare(self, corpus: Corpus, config: StudioConfig) -> None:
        key = (config.chunk_chars, corpus.lock_hash)
        if key not in self._dbs:
            tmp = Path(tempfile.mkdtemp(prefix="evallab-studio-"))
            atexit.register(shutil.rmtree, tmp, ignore_errors=True)
            conn = connect(tmp / "corpus.db")
            init_db(conn)
            user_id = uuid.uuid4().hex
            conn.execute("INSERT INTO users(id, email, password_hash) VALUES (?,?,?)",
                         (user_id, f"evallab-{config.chunk_chars}@example.test", "x"))
            conn.commit()
            pipeline = PipelineConfig(chunk_chars=config.chunk_chars)
            for path in corpus.files:
                doc = create_document(conn, user_id, name=path.name, source_type=path.suffix[1:], source_url=None,
                                      file_path=str(path), size_bytes=path.stat().st_size)
                ingest_document(conn, self.embedder, pipeline, doc.id)
                row = conn.execute("SELECT status, error FROM documents WHERE id=?", (doc.id,)).fetchone()
                if row["status"] != "ready":
                    raise RuntimeError(f"RAG Studio could not ingest {path.name}: {row['error']}")
            self._dbs[key] = (conn, user_id)

    def _db(self, config: StudioConfig):
        for (chunk_chars, _), db in self._dbs.items():
            if chunk_chars == config.chunk_chars:
                return db
        raise RuntimeError("prepare() must be called with this chunk_chars before answer()")

    # answering ------------------------------------------------------------------------------------
    def would_hit_cache(self, question: str, config: StudioConfig) -> bool:
        conn, user_id = self._db(config)
        cfg = PipelineConfig(**config.model_dump())
        result = retrieve(conn, self.embedder, cfg, user_id, question, None)
        if not result.gate_passed:
            return True  # no LLM call is made
        llm = self.llm
        if not hasattr(llm, "has"):
            return False
        passages = [Passage(label=f"c{i}", document_name=rc.chunk.document_name, location=rc.chunk.location,
                            text=rc.chunk.text) for i, rc in enumerate(result.chunks, start=1)]
        return llm.has(question, passages, cfg.model, system=PROMPTS[cfg.prompt_variant])

    def answer(self, question: str, config: StudioConfig, llm: bool) -> Trace:
        conn, user_id = self._db(config)
        cfg = PipelineConfig(**config.model_dump())
        if not llm:
            import time

            t0 = time.perf_counter()
            result = retrieve(conn, self.embedder, cfg, user_id, question, None)
            ms = round((time.perf_counter() - t0) * 1000)
            return Trace(retrieved=_chunks(result.chunks), status="retrieval_only", timings_ms={"retrieve": ms},
                         system_detail=_detail(result))
        spy = _Spy(self.llm)
        resp, trace = answer_question_detailed(conn, self.embedder, spy, cfg, user_id, question, None)
        retrieved = _chunks(trace.retrieval.chunks)
        rank_by_chunk = {rc.chunk.id: i for i, rc in enumerate(trace.retrieval.chunks, start=1)}
        chunk_by_n = {c.n: c.chunk_id for c in resp.citations}
        citations = [Citation(sentence_index=i, chunk_rank=rank_by_chunk.get(chunk_by_n.get(n)))
                     for i, s in enumerate(resp.sentences) for n in s.citations]
        labels = set(trace.valid_labels)
        raw = [lb for s in trace.raw_sentences for lb in s.citations]
        calls = []
        if spy.cached:
            calls.append(LLMCall(model=cfg.model, role="system", input_tokens=trace.input_tokens,
                                 output_tokens=trace.output_tokens, cached=all(spy.cached),
                                 ms=resp.timings_ms.generate))
        detail = _detail(trace.retrieval) | {"dropped_citations": resp.dropped_citations,
                                             "stop_reasons": trace.stop_reasons, "missing": resp.missing,
                                             "studio_status": resp.status}
        return Trace(
            retrieved=retrieved,
            status="abstained" if resp.status in ABSTAINED else resp.status,
            sentences=[s.text for s in resp.sentences], citations=citations,
            raw_citation_count=len(raw), raw_valid_citation_count=sum(1 for lb in raw if lb in labels),
            llm_calls=calls, timings_ms=resp.timings_ms.model_dump(), system_detail=detail,
        )


def _chunks(rcs) -> list[RetrievedChunk]:
    return [RetrievedChunk(rank=i, document=rc.chunk.document_name, text=rc.chunk.text, score=rc.score)
            for i, rc in enumerate(rcs, start=1)]


def _detail(result) -> dict:
    return {"gate_passed": result.gate_passed, "max_similarity": result.max_similarity,
            "strong_term_hit": result.strong_term_hit}
