# RAG Evaluation Lab Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build `evallab`, a CLI + static dashboard that runs versioned, hypothesis-driven experiments against RAG systems through an adapter, scores retrieval and answers, and reports case-level regressions with honest statistics — with RAG Studio as the first system.

**Architecture:** A Python package (`evallab/`) owns datasets, experiment expansion, the runner (cache, cost gate, budget), metrics, an LLM judge, statistics, comparison and a SQLite store. Systems are reached only through the `RAGSystem` protocol; the RAG Studio adapter imports Studio's backend as an editable package. `evallab export` writes JSON that a statically exported Next.js dashboard reads; comparisons are recomputed in the browser by a TypeScript port held to byte-identical output.

**Tech Stack:** Python 3.12, anthropic, pydantic 2, pyyaml, typer, pytest · Next.js 15 (static export), React 19, Tailwind 4, Recharts, Playwright · SQLite.

**Spec:** `docs/design/2026-10-18-rag-eval-lab-design.md`

## Global Constraints

- Python ≥ 3.12; venv at `rag-eval-lab/.venv`, created with `python3.12 -m venv .venv`.
- RAG Studio backend installed editable from `../rag-studio/backend`; Eval Lab imports Studio only in `evallab/adapters/rag_studio.py` (and in one test, §Task 12).
- No numpy/scipy in `evallab` statistics; pure Python so `dashboard/lib/compare.ts` can match exactly.
- Models: system under test `claude-sonnet-5-5` / `claude-haiku-5-5`; judge `claude-haiku-5-5`. Exact IDs, no date suffixes.
- Pricing (USD per MTok, `pricing.yaml`, as of 2026-10-06): sonnet-5-5 in 2.00 / out 10.00; haiku-5-5 in 0.10 / out 0.50.
- Project budget hard cap `budget.total_usd = 1.00` in `evallab.toml`. Every paid run requires the user's explicit `y`; agents never pass `--yes` to a paid run.
- No test calls the real API. All tests run offline at $0.
- Never mention portfolios, interviewers or "showcasing" in any file or commit message.
- Specs live in `docs/design/`, plans in `docs/plans/`.
- Commit messages end with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
- Dashboard: colour-blind-safe palette; improved/regressed always icon + label, never colour alone; light and dark; usable at 375 px.

## Review Focus

1. **Interrupted run (Ctrl-C or crash mid-run)** → completed cases are kept, run is `partial`, `--resume` finishes it without re-billing or double-counting the ledger. *Test in Task 8.*
2. **Comparing a `partial` or `degraded` run** → `compare` refuses unless `--allow-incomplete`, and the report header says so when allowed. *Test in Task 10.*
3. **Empty denominators** (subset with no unanswerable cases, every answer unjudged, retrieval-only run) → metric is `None`, rendered as `—` in Markdown and dashboard, never `NaN`, `0`, or a crash. *Tests in Task 5 and Task 10.*
4. **Fully cached LLM run with no API key** → runs offline; only uncached calls require a key. *Test in Task 8.*
5. **Experiment or dataset reference that doesn't exist** (`lumen@v9`, unknown subset, unknown system) → one-line error naming what's missing and what exists, exit code 2, before any work. *Test in Task 4.*

---

## File Structure

```
rag-eval-lab/
├── pyproject.toml, Makefile, evallab.toml, pricing.yaml, .gitignore, .env.example
├── evallab/
│   ├── __init__.py
│   ├── config.py            evallab.toml + .env loading → Settings
│   ├── cli.py               Typer app; thin wrappers only
│   ├── adapters/{__init__,base,fake,rag_studio}.py
│   ├── datasets.py
│   ├── experiments.py
│   ├── pricing.py
│   ├── cache.py
│   ├── metrics/{__init__,retrieval,answer,judge}.py
│   ├── store.py
│   ├── runner.py
│   ├── stats.py
│   ├── compare.py
│   ├── spotcheck.py
│   └── export.py
├── tests/  (one test file per module, plus tests/fixtures/)
├── datasets/lumen/{manifest.yaml,v1.jsonl,corpus.lock}
├── experiments/*.yaml
├── cache/{system,judge}/
├── results/evallab.db
└── dashboard/  (Next.js)
```

---

### Task 1: RAG Studio prompt-variant and cache-key hooks (in `rag-studio`)

Work in `../rag-studio` on a new branch `feat/eval-hooks` created from `feat/v1`.

**Files:**
- Create: `rag-studio/backend/app/answer/prompts.py`
- Modify: `rag-studio/backend/app/config.py` (`PipelineConfig`), `app/answer/llm.py` (`LLM`, `ClaudeLLM`, `CachedLLM`, `FakeLLM`), `app/answer/service.py` (`answer_question_detailed`, `AnswerTrace`), `research/harness.py` (`_Spy.draft`)
- Test: `rag-studio/backend/tests/test_prompt_variants.py`

**Interfaces:**
- Produces:
  - `PROMPTS: dict[str, str]` with `"default"` = the current `SYSTEM_PROMPT` text unchanged, and `"terse_cite_all"` = default text + `"\n- Be terse: one short sentence per fact, and cite every sentence."`
  - `PipelineConfig.prompt_variant: str = "default"`
  - `LLM.draft(question, passages, model, system: str = PROMPTS["default"]) -> LLMOutcome`
  - `ANSWER_EFFORT = "medium"` constant in `llm.py`, used by `ClaudeLLM`
  - `AnswerTrace.stop_reasons: list[str]` (one per `draft` attempt)
  - `SYSTEM_PROMPT` stays importable as an alias of `PROMPTS["default"]`

- [ ] **Step 1: Write failing tests**
  - `test_default_prompt_unchanged`: `PROMPTS["default"] == SYSTEM_PROMPT`, and a `ClaudeLLM` with a fake client called via `answer_question_detailed` with default config sends `system == SYSTEM_PROMPT` and `output_config == {"effort": "medium", "format": {...ANSWER_SCHEMA}}` (byte-identical request to today).
  - `test_prompt_variant_is_sent`: config `prompt_variant="terse_cite_all"` → fake client receives `system == PROMPTS["terse_cite_all"]`.
  - `test_unknown_prompt_variant_raises`: `prompt_variant="nope"` → `ValueError` naming the known variants.
  - `test_cache_key_separates_prompts`: `CachedLLM` over a counting fake; same question/passages with two different `system` values → inner called twice; same `system` twice → once.
  - `test_cache_key_includes_effort_and_schema`: monkeypatching `ANSWER_EFFORT` to `"low"` produces a different cache file name than `"medium"`.
  - `test_trace_records_stop_reasons`: fake LLM returning `None` draft then a valid draft → `trace.stop_reasons == ["end_turn", "end_turn"]`.
- [ ] **Step 2: Run** `cd rag-studio/backend && .venv/bin/pytest tests/test_prompt_variants.py -q` → FAIL (import error on `app.answer.prompts`).
- [ ] **Step 3: Implement.** `answer_question_detailed` resolves `PROMPTS[cfg.prompt_variant]` (KeyError → `ValueError`) and passes `system=` to `llm.draft`. `CachedLLM` key adds `"system": system, "effort": ANSWER_EFFORT, "schema": ANSWER_SCHEMA` in place of the module constant. `FakeLLM.draft` and `research/harness.py::_Spy.draft` accept and forward `system`.
- [ ] **Step 4: Run** full suite `.venv/bin/pytest -q` → all pass (existing tests unchanged).
- [ ] **Step 5: Commit** on `feat/eval-hooks`: `feat(answer): prompt variants and complete LLM cache key for external evaluation`. Do not push or open a PR; ask the user.

> Note: existing Studio cache files become cache misses because the key changed. That is intended (old keys were incomplete) and costs nothing until a paid run.

---

### Task 2: Eval Lab scaffold, settings and CLI skeleton

**Files:**
- Create: `pyproject.toml`, `Makefile`, `evallab.toml`, `pricing.yaml`, `.gitignore`, `.env.example`, `evallab/__init__.py`, `evallab/config.py`, `evallab/cli.py`
- Test: `tests/test_config.py`

**Interfaces:**
- Produces:
  - `Settings` (pydantic): `root: Path`, `budget_total_usd: float`, `judge_model: str`, `judge_rubric_version: str`, `store_path: Path`, `cache_dir: Path`, `export_dir: Path`, `systems: dict[str, dict]`, `anthropic_api_key: str` (from env `ANTHROPIC_API_KEY`, else `.env` in root; never from `evallab.toml`)
  - `load_settings(root: Path | None = None) -> Settings` (root defaults to the nearest parent with `evallab.toml`)
  - `cli.app: typer.Typer`; console script `evallab = "evallab.cli:app"`
- `evallab.toml` values: `[budget] total_usd = 1.00`; `[judge] model = "claude-haiku-5-5"`, `rubric_version = "v1"`; `[paths] store = "results/evallab.db"`, `cache = "cache"`, `export = "dashboard/public/data"`; `[systems.rag_studio] path = "../rag-studio/backend"`, `embedder = "fastembed"`; `[ci] baseline_run = ""` (set in Task 18). `Settings.ci_baseline_run: str`; CLI `evallab ci-baseline` prints it (exit 2 if empty).
- `pyproject.toml`: `requires-python = ">=3.12"`; deps `anthropic>=1.15`, `pydantic>=2`, `pyyaml`, `typer`; optional `dev = ["pytest"]`; `[tool.pytest.ini_options] markers = ["slow"]`, `addopts = "-m 'not slow'"`.
- `Makefile` targets: `install` (venv, `pip install -e ../rag-studio/backend -e ".[dev]"`, `npm --prefix dashboard install` if present), `test`, `test-slow`, `dashboard`, `site`.
- `.gitignore`: `.venv/`, `.env`, `__pycache__/`, `dashboard/node_modules/`, `dashboard/.next/`, `dashboard/out/`. (`cache/` and `results/` are **committed**.)

- [ ] **Step 1: Failing tests** — `test_loads_defaults` (tmp root with the toml → `budget_total_usd == 1.0`, `judge_model == "claude-haiku-5-5"`, paths resolved relative to root); `test_api_key_from_env_over_dotenv`; `test_api_key_never_read_from_toml` (key in toml ignored).
- [ ] **Step 2: Run** `.venv/bin/pytest tests/test_config.py -q` → FAIL.
- [ ] **Step 3: Implement** `config.py`; `cli.py` with a `version` command only.
- [ ] **Step 4: Run** tests → PASS; `.venv/bin/evallab --help` lists `version`.
- [ ] **Step 5: Commit** `chore: scaffold evallab package, settings and CLI`.

---

### Task 3: Adapter protocol, Trace and FakeSystem

**Files:**
- Create: `evallab/adapters/__init__.py`, `evallab/adapters/base.py`, `evallab/adapters/fake.py`
- Test: `tests/test_adapters_fake.py`

**Interfaces:**
- Produces (in `base.py`), exactly as spec §4: `RetrievedChunk`, `Citation`, `LLMCall`, `Trace` dataclasses (all with `to_dict()` / `from_dict()`), `Corpus` (`name: str`, `path: Path`, `lock_hash: str`, `files: list[Path]`), and `RAGSystem` Protocol (`name`, `version()`, `config_schema()`, `prepare(corpus, config)`, `answer(question, config, llm: bool) -> Trace`).
- `RAGSystem` also has `would_hit_cache(question: str, config) -> bool` (used by the cost estimate); FakeSystem returns `False` unless constructed with `all_cached=True`.
- `get_system(name: str, settings: Settings) -> RAGSystem` in `adapters/__init__.py`; registry `{"fake": FakeSystem, "rag_studio": RagStudioSystem}` (the latter imported lazily). Unknown name → `KeyError` listing known names.
- `FakeSystem(all_cached: bool = False)`: config schema `FakeConfig(quality: float = 0.8, top_k: int = 8, model: str = "fake-model", fail_ids: list[str] = [], raise_on: list[str] = [])`. Deterministic: for a question, it hashes `(question, quality)` to decide whether the right evidence is retrieved and whether to answer; it retrieves real text from the corpus files. Answers cite rank 1. `LLMCall(model=config.model, role="system", input_tokens=1000, output_tokens=200, cached=False, ms=5)` per answered case. `raise_on` holds case questions for which `answer` raises `RuntimeError` (for error-path tests). `version()` returns `"fake@1"`.

- [ ] **Step 1: Failing tests** — `test_trace_roundtrip` (`Trace.from_dict(t.to_dict()) == t`); `test_fake_is_deterministic` (same inputs → equal traces); `test_fake_quality_changes_outcomes` (on a 20-question fixture, `quality=0.9` passes strictly more hits than `quality=0.3`); `test_fake_retrieval_only_has_no_llm_calls` (`llm=False` → `status == "retrieval_only"`, `llm_calls == []`); `test_get_system_unknown_name`.
- [ ] **Step 2: Run** → FAIL.
- [ ] **Step 3: Implement.** Add fixture corpus `tests/fixtures/corpus/` (3 short `.md` files) and `tests/fixtures/questions.jsonl` (20 cases: 14 answerable across tags `exact_term`/`paraphrase`, 6 `unanswerable`) with evidence copied verbatim from the fixture files.
- [ ] **Step 4: Run** → PASS.
- [ ] **Step 5: Commit** `feat: adapter protocol, Trace types and deterministic FakeSystem`.

---

### Task 4: Versioned datasets

**Files:**
- Create: `evallab/datasets.py`; CLI commands `dataset import|new|publish|validate|list`
- Test: `tests/test_datasets.py`

**Interfaces:**
- Consumes: `Corpus` (Task 3), `Settings` (Task 2).
- Produces:
  - `Case` (pydantic): `id: str`, `question: str`, `answerable: bool`, `tag: str`, `expected: list[Expected]`, `reference_answer: str | None = None`; `Expected(document: str, evidence: str)`
  - `Dataset`: `name`, `version`, `sha256`, `cases: list[Case]`, `corpus: Corpus`
  - `norm(text: str) -> str` — `" ".join(text.split()).casefold()`
  - `evidence_matches(chunk_document: str, chunk_text: str, e: Expected) -> bool` — spec §6 rule (document equal and whole-evidence or first-8-words containment)
  - `load_dataset(ref: str, settings) -> Dataset` where `ref` is `"name@version"`; verifies file sha256 and corpus lock; validates
  - `validate(cases, corpus) -> list[str]` — error messages; empty means valid
  - `import_dataset(name, source_jsonl, corpus_path, changes, settings) -> Dataset` — creates `datasets/<name>/` with `v1.jsonl`, `corpus.lock`, `manifest.yaml`
  - `new_draft(name, from_version, settings) -> Path` (writes `draft.jsonl`), `publish(name, changes, settings) -> Dataset` (validates draft, writes `v{n+1}.jsonl`, appends manifest, deletes draft)
  - `subset(ds: Dataset, spec: str) -> list[Case]` — `spec` is `"balanced-<n>"`: group by tag, order each group by mulberry32(seed=0) shuffle of ids sorted ascending (this task creates `evallab/stats.py` containing only `Mulberry32` as specified in Task 9; Task 9 adds the rest and the vector test), then round-robin across tags in sorted tag order until n. `n` > len → `ValueError`.
  - Exceptions: `DatasetError(Exception)` for every user-facing failure; CLI maps it to exit code 2.
- `corpus.lock` format: one line per file, `"<sha256>  <filename>"`, sorted by filename; `lock_hash` = sha256 of the lock file bytes.

- [ ] **Step 1: Failing tests**
  - `test_import_creates_v1` (fixture questions + corpus → manifest has `v1`, `cases: 20`, sha256 of `v1.jsonl`, `parent: null`)
  - `test_tampered_version_refused` (append a byte to `v1.jsonl` → `DatasetError` containing `"sha256 mismatch"`)
  - `test_corpus_change_refused` (edit a corpus file → `DatasetError` containing `"corpus lock"`)
  - `test_validate_catches` — four parametrized cases: duplicate id, unknown document, evidence not in document, unanswerable with expected → each yields one message naming the case id
  - `test_evidence_head_match` (evidence whose first 8 words are in the chunk but tail is not → True; other document → False)
  - `test_new_and_publish_v2` (draft edited, publish requires non-empty `changes`, manifest gains `v2` with `parent: v1`; `v1.jsonl` bytes unchanged)
  - `test_balanced_subset_stable` (`subset(ds, "balanced-10")` returns the same ids on two calls, tag counts differ by ≤ 1)
  - **Review Focus 5:** `test_unknown_version_message` (`load_dataset("lumen@v9")` → `DatasetError` whose message includes `"v9"` and `"available: v1"`); `test_cli_missing_dataset_exit_code` (Typer `CliRunner` → exit code 2, single-line stderr)
- [ ] **Step 2: Run** → FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** → PASS.
- [ ] **Step 5: Import the real dataset.** Run `evallab dataset import lumen --from ../rag-studio/backend/research/questions.jsonl --corpus ../rag-studio/backend/research/corpus --changes "Imported from rag-studio research/questions.jsonl @ <short sha of rag-studio feat/v1 HEAD>"`. Expected: `lumen@v1: 60 cases, valid`. If validation reports errors, stop and report them to the user — do not edit the questions.
- [ ] **Step 6: Commit** `feat: versioned datasets with hash and corpus lock; import lumen@v1`.

---

### Task 5: Metrics (retrieval, answer, pass rule)

**Files:**
- Create: `evallab/metrics/__init__.py`, `evallab/metrics/retrieval.py`, `evallab/metrics/answer.py`
- Test: `tests/test_metrics.py`

**Interfaces:**
- Consumes: `Trace` (Task 3), `Case`, `evidence_matches` (Task 4).
- Produces:
  - `retrieval.case_metrics(trace: Trace, case: Case, k: int) -> dict` → `{"hit": bool|None, "evidence_recall": float|None, "rr": float|None}` (all `None` for unanswerable)
  - `JudgeVerdict` dataclass (`correct: bool`, `unsupported_claims: int`, `reason: str`) — defined in `metrics/answer.py` and re-used by Task 6
  - `answer.case_metrics(trace, case, verdict: JudgeVerdict | None, judged: bool) -> dict` → `{"abstained", "answered", "citation_validity_raw", "citation_validity", "unjudged": bool}`
  - `answer.case_pass(trace, case, verdict, llm: bool, k: int) -> bool | None` — spec §6 pass rule; retrieval-only → `hit`; `None` when unjudged
  - `summarize(case_rows: list[dict], llm: bool) -> dict` — run aggregates: `n`, `n_errored`, `n_unjudged`, `accuracy`, `accuracy_definition` (`"pass_rule"` or `"hit@k"`), `hit@k`, `evidence_recall@k`, `mrr`, `answer_rate`, `abstention_precision`, `abstention_recall`, `citation_validity_raw`, `citation_validity`, `latency_p50_ms`, `latency_p95_ms`, `cost_spent`, `cost_nominal`, `cost_spent_system`, `cost_spent_judge`, `cost_per_case`, and `by_tag: {tag: {"n", "accuracy"}}`. Each `case_rows` item has keys `case`, `trace`, `status`, `pass`, `metrics`, `cost_spent`, `cost_nominal`, `latency_ms`, `cached`. Percentiles: nearest-rank on sorted uncached latencies.

- [ ] **Step 1: Failing tests** — hand-built traces:
  - `test_hit_recall_mrr` (two expected items, first match at rank 3, second absent → hit True, recall 0.5, rr 1/3)
  - `test_pass_rule_answerable` (answered + correct + 0 unsupported → True; 1 unsupported → False; abstained → False)
  - `test_pass_rule_unanswerable` (abstained → True; answered → False)
  - `test_unjudged_excluded_from_accuracy` (3 passes, 1 fail, 1 unjudged → accuracy 0.75, `n_unjudged == 1`)
  - `test_errored_excluded` (status `error` rows don't count)
  - `test_retrieval_only_accuracy_is_hit` (`accuracy_definition == "hit@k"`)
  - `test_latency_ignores_cached`
  - **Review Focus 3:** `test_empty_denominators_are_none` — subset with no unanswerable → `abstention_recall is None`; all unjudged → `accuracy is None`; retrieval-only → `answer_rate is None`. No `ZeroDivisionError`, no `nan`.
- [ ] **Step 2: Run** → FAIL. **Step 3: Implement.** **Step 4: Run** → PASS.
- [ ] **Step 5: Commit** `feat: retrieval and answer metrics with case pass rule`.

---

### Task 6: Pricing, cache and judge

**Files:**
- Create: `evallab/pricing.py`, `evallab/cache.py`, `evallab/metrics/judge.py`
- Test: `tests/test_pricing.py`, `tests/test_cache.py`, `tests/test_judge.py`

**Interfaces:**
- Produces:
  - `pricing.load(path) -> Pricing`; `Pricing.cost(model, input_tokens, output_tokens) -> float`; unknown model → `KeyError`. `pricing.yaml`: `as_of: 2026-10-06`, `models: {claude-sonnet-5-5: {input: 2.00, output: 10.00}, claude-haiku-5-5: {input: 0.10, output: 0.50}, fake-model: {input: 1.00, output: 1.00}}` (USD per MTok).
  - `cache.DiskCache(dir: Path)`: `key(payload: dict) -> str` (sha256 of `json.dumps(payload, sort_keys=True)`), `get(key) -> dict | None` (corrupt file → `None`), `put(key, value: dict)`.
  - `judge.RUBRIC_V1: str` — system prompt per spec §6 (judge the answer against gold evidence and cited passages; `correct` definition including the `partial` rule; count unsupported claims; ignore style).
  - `judge.Judge` Protocol: `judge(case: Case, trace: Trace, cited_texts: list[str]) -> tuple[JudgeVerdict | None, LLMCall]`
  - `judge.ClaudeJudge(api_key, cache: DiskCache, model, rubric_version, client=None)` — `messages.create(model=model, max_tokens=2000, system=RUBRIC_V1, messages=[...], output_config={"effort": "low", "format": {"type": "json_schema", "schema": transform_schema(VerdictModel)}})`; check `stop_reason` in `("refusal", "max_tokens")` → `None`; parse with pydantic, failure → `None`; cache key includes `model`, `rubric_version`, `RUBRIC_V1`, messages, schema; cached hit returns stored tokens with `cached=True`. Only successful verdicts are cached.
  - `judge.make_judge(settings, cache: DiskCache) -> Judge` — `FakeJudge()` when `settings.judge_model == "fake"`, else `ClaudeJudge`.
  - `judge.FakeJudge(rules: dict[str, JudgeVerdict | None] | None = None)` — default verdict: correct iff the answer's cited chunk matches expected evidence; `LLMCall(model="fake-model", role="judge", input_tokens=500, output_tokens=50, ...)`.

- [ ] **Step 1: Failing tests** — `test_cost_math` (`cost("claude-haiku-5-5", 1_000_000, 1_000_000) == 0.60`; sonnet → 12.00); `test_cache_roundtrip_and_corrupt`; `test_claude_judge_parses` (fake client returns valid JSON text → verdict); `test_claude_judge_refusal_is_none` (stop_reason `refusal` → `None`, not cached); `test_claude_judge_invalid_json_is_none`; `test_claude_judge_cache_hit_no_call` (second call: fake client call count unchanged, `LLMCall.cached is True`); `test_judge_request_shape` (assert `model`, `system`, `output_config["effort"] == "low"`).
- [ ] **Step 2: Run** → FAIL. **Step 3: Implement.** **Step 4: Run** → PASS.
- [ ] **Step 5: Commit** `feat: pricing, content-addressed cache and Haiku judge`.

---

### Task 7: Results store

**Files:**
- Create: `evallab/store.py`
- Test: `tests/test_store.py`

**Interfaces:**
- Produces: `Store(path: Path)` with tables exactly as spec §8 (`experiments`, `runs`, `case_results`, `ledger`; `PRIMARY KEY (run_id, case_id)` on `case_results`) and methods:
  - `upsert_experiment(name, yaml_text, git_sha, hypothesis)`
  - `create_run(run: RunRecord)`; `RunRecord` dataclass: `run_id, experiment, label, config: dict, system, system_version, dataset, dataset_sha, subset, judge_model, status, started_at, finished_at=None, summary: dict | None = None`
  - `get_run(run_id_or_prefix: str) -> RunRecord` (ambiguous prefix → `ValueError` listing matches); `find_run(experiment, label) -> RunRecord | None` (most recent by `started_at`); `list_runs(experiment=None) -> list[RunRecord]`
  - `put_case(run_id, row: dict)` (upsert), `case_rows(run_id) -> list[dict]`, `done_case_ids(run_id) -> set[str]`
  - `add_ledger(run_id, case_id, model, role, usd)`; `spent_total() -> float`
  - `finish_run(run_id, status, summary)`
- [ ] **Step 1: Failing tests** — `test_roundtrip_run_and_cases`; `test_prefix_lookup_ambiguous`; `test_put_case_is_upsert` (same case twice → one row); `test_spent_total_sums_ledger`; `test_reopen_persists`.
- [ ] **Step 2–4:** run → FAIL, implement, run → PASS.
- [ ] **Step 5: Commit** `feat: SQLite results store with spend ledger`.

---

### Task 8: Experiments and runner (identity, cost gate, budget, resume)

**Files:**
- Create: `evallab/experiments.py`, `evallab/runner.py`; CLI `run`, `budget`, `list`
- Test: `tests/test_experiments.py`, `tests/test_runner.py`

**Interfaces:**
- Consumes: everything above.
- Produces:
  - `Experiment` (pydantic): `name, description="", hypothesis: str | None, system, dataset, subset: str | None, llm: bool = False, judge: bool = False, base: dict = {}, grid: dict[str, list] | None, variants: list[dict] | None, repeats: int = 1, gate: GateSpec | None`; `GateSpec(max_regressed: int | None, min_accuracy_delta: float | None, max_cost_ratio: float | None)`. Exactly one of `grid`/`variants` may be set (neither → single run labelled `"base"`).
  - `load_experiment(path) -> tuple[Experiment, str]` (model + raw YAML text); `llm: true` without `hypothesis` → `ExperimentError`.
  - `expand(exp) -> list[tuple[str, dict]]` — `(label, config)`; grid labels are `"k=v,k=v"` in grid key order; variant labels from `label`.
  - `experiment_git_state(path) -> tuple[str, bool]` — `(commit sha, is_dirty)` via `git log -1 --format=%H -- <path>` and `git status --porcelain -- <path>`.
  - `run_id(dataset_sha, subset, lock_hash, system_version, judge_model, rubric_version, config, repeat) -> str` — first 12 hex of sha256 of sorted-key JSON.
  - `Estimate` dataclass per run: `label, run_id, cases, uncached_system, uncached_judge, usd, measured: bool`.
  - `PlannedRun` dataclass: `experiment: Experiment, label: str, run_id: str, config: BaseModel, dataset: Dataset, cases: list[Case], skip: bool` (`skip` = complete run exists and not `force`).
  - `repeats > 1` → `ExperimentError("repeats > 1 is not supported in v1")` (spec §14).
  - `plan_runs(exp_path, settings, store, force=False) -> list[PlannedRun]` (loads, validates against `system.config_schema()`, computes ids, skips complete runs unless `force`).
  - `estimate(planned, store, pricing) -> list[Estimate]` — per-call cost = mean of earlier ledger rows for same model+role (`measured=True`), else heuristic `input_tokens = chars/4`, `output_tokens = 1500` (`measured=False`). Cache hits are found by asking the adapter (`RagStudioSystem.would_hit_cache(question, config)` / FakeSystem always `False`); judge cache hits by computing the judge key.
  - `execute(planned_run, settings, store, system, judge, pricing, budget_remaining: float) -> RunRecord` — per case: `system.answer` → metrics → judge (if `judge` and answered) → `store.put_case` → ledger rows for uncached calls → before each next case, if `spent + next_estimate > budget_remaining`, stop with status `partial`. Catches `Exception` per case → status `error`. `KeyboardInterrupt` → mark `partial`, re-raise. Final status: `complete`, `partial`, or `degraded` (> 10% errored).
  - CLI: `evallab run <file> [--yes] [--dry-run] [--force] [--resume]`; `evallab budget`; `evallab list [--experiment]`. `run` prints the estimate table (columns: label, run_id, cases, uncached system, uncached judge, est. USD, measured) and `spent $X of $Y, remaining $Z`. Refuses (exit 2) if the sum of estimates > remaining, if the experiment file is dirty, or if any uncached call is needed and `anthropic_api_key` is empty.

- [ ] **Step 1: Failing tests** (all with FakeSystem + FakeJudge + tmp store/git repo)
  - `test_grid_expansion_labels` (`grid: {quality: [0.3, 0.9], top_k: [4]}` → labels `["quality=0.3,top_k=4", "quality=0.9,top_k=4"]`)
  - `test_invalid_config_rejected` (unknown key → error naming the key, before any case runs)
  - `test_llm_requires_hypothesis`; `test_dirty_experiment_refused`
  - `test_run_id_stable_and_sensitive` (same inputs → same id; change any config value → different id)
  - `test_complete_run_reused` (second `run` executes 0 cases; `--force` re-executes)
  - `test_budget_stop_marks_partial` (budget allows 3 cases' worth → 3 rows, status `partial`, ledger total ≤ budget)
  - `test_case_exception_is_error_and_degraded` (`raise_on` 3 of 20 → status `degraded`, 3 error rows)
  - **Review Focus 1:** `test_interrupt_then_resume` — FakeSystem raises `KeyboardInterrupt` on case 5; run is `partial` with 4 rows; `--resume` completes 20 rows; ledger has exactly one row per uncached call (no double counting).
  - **Review Focus 4:** `test_cached_run_needs_no_key` — pre-populate system + judge caches (`FakeSystem(all_cached=True)`), empty key → run succeeds; with one uncached case → refused with message containing `"ANTHROPIC_API_KEY"`.
  - `test_cli_dry_run_prints_estimate` (CliRunner; output contains run label and `remaining $1.00`; no rows written)
- [ ] **Step 2–4:** run → FAIL, implement, run → PASS.
- [ ] **Step 5: Commit** `feat: experiment expansion and runner with cost gate, budget cap and resume`.

---

### Task 9: Statistics

**Files:**
- Create/extend: `evallab/stats.py`; `tests/fixtures/stats_vectors.json`
- Test: `tests/test_stats.py`

**Interfaces:**
- Produces:
  - `class Mulberry32(seed: int)` with `next_u32() -> int` and `random() -> float` (`next_u32() / 2**32`). Algorithm (must match TS exactly):
    ```
    a = (a + 0x6D2B79F5) & 0xFFFFFFFF
    t = a
    t = imul(t ^ (t >> 15), t | 1) & 0xFFFFFFFF
    t ^= (t + imul(t ^ (t >> 7), t | 61)) & 0xFFFFFFFF
    return (t ^ (t >> 14)) & 0xFFFFFFFF
    ```
    where `imul(x, y) = (x * y) & 0xFFFFFFFF`.
  - `mcnemar_exact(b: int, c: int) -> float` — two-sided `min(1, 2 * Σ_{i=0}^{min(b,c)} C(b+c, i) / 2^(b+c))`; `b + c == 0` → `1.0`.
  - `paired_bootstrap_ci(base: list[float], cand: list[float], resamples=10_000, seed=0) -> tuple[float, float, float]` — `(mean_delta, lo, hi)`; each resample draws n indices with `floor(rng.random() * n)`; bounds at sorted indices `round(0.025*(B-1))`, `round(0.975*(B-1))`. Fewer than 2 pairs → `(delta, None, None)`.
  - `mde_paired(n: int, discordant: int) -> float | None` — `2.80 * sqrt(max(discordant/n, 1/n) / n)`; `n == 0` → `None`.
  - `verdict(lo, hi, higher_is_better=True) -> Literal["better", "worse", "no detectable difference"]`.
- [ ] **Step 1: Failing tests** — `test_mulberry32_vector` (seed 0: first five `next_u32()` equal the values in `stats_vectors.json`; generate them once with the reference algorithm in a scratch script and commit the fixture — the TS test in Task 15 reuses it); `test_mcnemar_known` (`(0, 0) → 1.0`; `(1, 5) → 0.21875`; `(0, 6) → 0.03125`); `test_bootstrap_reproducible_and_brackets` (same seed → identical tuple; `lo ≤ mean ≤ hi`); `test_mde` (`n=60, discordant=6 → ≈ 0.1143`).
- [ ] **Step 2–4:** run → FAIL, implement, run → PASS.
- [ ] **Step 5: Commit** `feat: seeded bootstrap, exact McNemar and MDE`.

---

### Task 10: Comparison report and gate

**Files:**
- Create: `evallab/compare.py`; CLI `compare`
- Test: `tests/test_compare.py`; fixture `tests/fixtures/compare_pair.json` (two runs' case rows) and `tests/fixtures/compare_expected.json`

**Interfaces:**
- Consumes: `Store` (Task 7), `stats` (Task 9), `summarize` (Task 5).
- Produces:
  - `compare_runs(base: RunRecord, base_rows, cand: RunRecord, cand_rows, allow_incomplete=False) -> dict` — JSON-serializable report: `base`, `cand` (id, label, status), `config_diff: {key: [base, cand]}`, `versions`, `warnings: list[str]`, `summary: {metric: {base, cand, delta, lo, hi, verdict}}` for `accuracy`, `mrr`, `latency_p50_ms`, `cost_per_case` (+ plain base/cand for the other §6 metrics), `mcnemar_p`, `mde`, `counts: {improved, regressed, stable_pass, stable_fail, not_comparable}`, `by_tag`, `cases: [{case_id, tag, question, status, reason, base: {...}, cand: {...}}]` sorted regressed → improved → stable_fail → stable_pass, then by id.
  - Reason precedence (first that applies): `retrieval_lost`, `retrieval_gained`, `wrongly_abstained`, `hallucinated`, `judge_incorrect`, `judge_correct`, `unsupported_claims`; else `null`.
  - `render_markdown(report) -> str` — sections per spec §9; `None` renders as `—`.
  - `check_gate(report, gate: GateSpec) -> list[str]` — failed checks as messages; `max_cost_ratio` compares `cost_per_case`.
  - Metric deltas for latency and cost use `higher_is_better=False`.
  - Base/cand must be paired on shared case ids; different dataset versions → warning `"datasets differ (lumen@v1 vs lumen@v2): comparing N shared cases"`.
  - CLI: `evallab compare BASE CAND [--format md|json] [--out PATH] [--gate] [--allow-incomplete]`; `BASE`/`CAND` are id prefixes or `experiment:label`. `--gate` uses the candidate experiment's `gate`, overridable by `--max-regressed`, `--min-accuracy-delta`, `--max-cost-ratio`; exit 1 on failure.
- [ ] **Step 1: Failing tests**
  - `test_classification_and_reasons` (fixture: case A hit lost → `regressed/retrieval_lost`; case B abstained on unanswerable then answered → `regressed/hallucinated`; case C fail→pass via judge → `improved/judge_correct`)
  - `test_report_matches_fixture` (`compare_runs` on `compare_pair.json` equals `compare_expected.json` exactly — this file is the cross-language contract used in Task 15)
  - `test_dataset_mismatch_warns_and_uses_shared`
  - `test_gate_failures` (`max_regressed: 0` with 2 regressed → one message containing `"regressed 2 > 0"`; CLI exit code 1)
  - **Review Focus 2:** `test_incomplete_run_refused` (partial candidate → `ValueError` mentioning `--allow-incomplete`; with the flag → report `warnings` contains `"candidate run is partial"`)
  - **Review Focus 3:** `test_markdown_renders_none_as_dash` (retrieval-only pair → no `"nan"`/`"None"` in the Markdown)
- [ ] **Step 2–4:** run → FAIL, implement, run → PASS. Generate `compare_expected.json` from the implementation only after hand-checking the counts and reasons in it against the fixture.
- [ ] **Step 5: Commit** `feat: case-level regression report with statistics and gate`.

---

### Task 11: End-to-end on the fake system

**Files:**
- Create: `tests/test_e2e_fake.py`, `tests/fixtures/experiments/fake-sweep.yaml`

- [ ] **Step 1: Write test** `test_run_compare_export_e2e`: in a tmp git repo, import the fixture dataset, commit a `fake-sweep.yaml` (`system: fake`, `grid: {quality: [0.4, 0.9]}`, `llm: true`, `judge: true`, hypothesis set), `evallab run --yes` via CliRunner with budget 1.00 and the tmp `evallab.toml` setting `[judge] model = "fake"`, then `evallab compare fake-sweep:quality=0.4 fake-sweep:quality=0.9 --format json` → `counts.improved > 0`, and `evallab export` writes `index.json` listing both runs. (`export` arrives in Task 14 — mark that final assertion `pytest.skip` until then and remove the skip in Task 14.)
- [ ] **Step 2: Run** → PASS for run + compare (any failure here is a bug in Tasks 3–10; fix it there).
- [ ] **Step 3: Commit** `test: end-to-end run and compare on the fake system`.

---

### Task 12: RAG Studio adapter

**Files:**
- Create: `evallab/adapters/rag_studio.py`
- Test: `tests/test_rag_studio_adapter.py`

**Interfaces:**
- Consumes: Task 1's Studio API (`PipelineConfig.prompt_variant`, `PROMPTS`, `LLM.draft(..., system=)`, `CachedLLM`, `ClaudeLLM`, `answer_question_detailed`, `AnswerTrace.stop_reasons`), Studio's `retrieve`, `make_embedder`, `connect`, `init_db`, `create_document`, `ingest_document`.
- Produces: `RagStudioSystem(settings, embedder_kind: str | None = None, llm=None)` implementing `RAGSystem`:
  - `config_schema()` → `StudioConfig` mirroring `PipelineConfig` field-for-field with `Literal` constraints (`retrieval_mode`, `model in {"claude-sonnet-5-5", "claude-haiku-5-5"}`, `prompt_variant in PROMPTS`).
  - `version()` → `"rag-studio@<short sha>"`, plus `"+dirty:<sha256(git diff HEAD -- app)[:8]>"` when `git status --porcelain -- app` is non-empty (run in Studio's backend dir).
  - `prepare` → ingest corpus into a temp SQLite DB per `chunk_chars` (in-process cache keyed by `(chunk_chars, embedder_kind)`), raising if any document isn't `ready`.
  - `answer(question, config, llm)` → `llm=False`: `retrieve(...)` only, `status="retrieval_only"`. `llm=True`: `answer_question_detailed` with `CachedLLM(ClaudeLLM(api_key), settings.cache_dir / "system")` (or the injected `llm`); map statuses (`not_found`/`insufficient_evidence` → `abstained`); `citations` from response citations mapped to retrieved ranks (`chunk_id` not retrieved → `chunk_rank=None`); `raw_citation_count` / `raw_valid_citation_count` from `trace.raw_sentences` and `trace.valid_labels`; a single `LLMCall(role="system")` carrying the trace's total tokens (Studio may retry a draft once), `cached` = every attempt was a cache hit, `ms` = generate timing; none when the gate failed; `timings_ms` from the response.
  - `would_hit_cache(question, config) -> bool` — runs retrieval, builds the passages exactly as Studio does, and checks whether the `CachedLLM` key file exists; gate-fails (no LLM call) count as hits.
- [ ] **Step 1: Failing tests** (Studio `hash` embedder, Studio `FakeLLM`, real lumen corpus)
  - `test_schema_rejects_unknown_model`
  - `test_retrieval_only_trace` (one lumen question → 8 chunks with ranks 1..8, `llm_calls == []`)
  - `test_llm_trace_mapping` (Studio `FakeLLM` → `status == "answered"`, one citation to rank 1, `raw_citation_count == 2`, `raw_valid_citation_count == 1` — FakeLLM cites `c1` and `c99`)
  - `test_unanswerable_maps_to_abstained`
  - `test_version_reports_dirty` (monkeypatch the git helper)
  - `@pytest.mark.slow test_metric_parity_with_studio` — the one allowed import of `research.metrics`: for each RQ1 variant (`vector`, `bm25`, `hybrid`) with fastembed, run Eval Lab retrieval-only on lumen@v1 and also build Studio-format records from the same traces; assert Eval Lab `hit@k` and `mrr` equal `research.metrics.summarize(...)` values to 1e-12.
- [ ] **Step 2–4:** run → FAIL, implement, run `make test` and `make test-slow` → PASS.
- [ ] **Step 5: Commit** `feat: RAG Studio adapter`.

---

### Task 13: Judge spot check

**Files:**
- Create: `evallab/spotcheck.py`; CLI `spotcheck sample|score`
- Test: `tests/test_spotcheck.py`

**Interfaces:**
- Produces:
  - `sample(store, run_ids: list[str], n=30, seed=0) -> list[dict]` — judged cases stratified evenly by each run's `config["model"]`, via `Mulberry32`; writes `spotcheck/<date>-<runs>.csv` with columns `run_id, model, case_id, question, answer, evidence, judge_correct, judge_unsupported, human_correct, human_unsupported` (human columns empty).
  - `score(csv_path) -> dict` — `{"n", "agreement", "kappa", "by_model": {model: {"n", "agreement", "kappa"}}}` on `correct`; rows with empty human labels skipped; κ `None` when undefined.
- [ ] **Step 1: Failing tests** — `test_sample_is_stratified` (two models → 15/15); `test_kappa_known` (2×2 table `[[10, 2], [3, 15]]` → κ ≈ 0.6575); `test_unlabelled_rows_skipped`.
- [ ] **Step 2–4:** run → FAIL, implement, run → PASS.
- [ ] **Step 5: Commit** `feat: judge spot-check sampling and Cohen's kappa`.

---

### Task 14: Export for the dashboard

**Files:**
- Create: `evallab/export.py`; CLI `export`
- Test: `tests/test_export.py`

**Interfaces:**
- Produces: `export_all(store, settings, out_dir) -> list[Path]` writing:
  - `index.json`: `{"generated_at", "budget": {"total", "spent"}, "experiments": [{"name", "description", "hypothesis", "runs": [run_id...], "status", "best_accuracy", "spent"}]}`
  - `experiments/<name>.json`: experiment YAML text, git sha, and `runs: [{run_id, label, config, status, summary}]`
  - `runs/<run_id>.json`: run record + `cases` (all case rows with traces, judge verdicts, metrics)
  - `datasets/<name>.json`: manifest + cases of every version
  - File names use `run_id` and experiment `name` slugified to `[a-z0-9-]`; JSON written with `sort_keys=True`, `indent=0`.
- [ ] **Step 1: Failing tests** — `test_export_files_and_shapes` (fake e2e store → all four kinds exist and parse; `index.json.budget.spent` equals `store.spent_total()`); `test_slugified_names` (experiment named `"My Sweep/2"` → `experiments/my-sweep-2.json`). Remove the skip in Task 11's final assertion.
- [ ] **Step 2–4:** run → FAIL, implement, run full suite → PASS.
- [ ] **Step 5: Commit** `feat: JSON export for the static dashboard`.

---

### Task 15: Dashboard scaffold, data layer and compare port

**Files:**
- Create: `dashboard/` via `npx create-next-app@15.5.28 dashboard --ts --tailwind --eslint --app --no-src-dir --import-alias "@/*"`; then `dashboard/next.config.ts` (`output: "export"`, `images.unoptimized: true`, `trailingSlash: true`), `dashboard/lib/types.ts`, `dashboard/lib/data.ts`, `dashboard/lib/stats.ts`, `dashboard/lib/compare.ts`, `dashboard/tests/compare.test.ts` (Vitest)
- Install: `recharts`, dev `vitest`, `@playwright/test`

**Interfaces:**
- Consumes: export JSON shapes (Task 14); `tests/fixtures/stats_vectors.json`, `compare_pair.json`, `compare_expected.json` (Tasks 9–10).
- Produces:
  - `types.ts`: TS types mirroring the export JSON and the compare report.
  - `data.ts`: build-time loaders `getIndex()`, `getExperiment(name)`, `getDataset(name)` reading `public/data` with `fs`; client fetchers `fetchRun(runId)` from `/data/runs/<id>.json`.
  - `stats.ts`: `Mulberry32`, `mcnemarExact`, `pairedBootstrapCi`, `mdePaired`, `verdict` — same semantics as Task 9.
  - `compare.ts`: `compareRuns(base, baseRows, cand, candRows, allowIncomplete)` — same output as Task 10's `compare_runs`.
- [ ] **Step 1: Failing tests** — `mulberry32 matches python vectors`; `compareRuns matches python fixture` (deep-equal to `compare_expected.json`; compare floats by exact equality — both sides do identical IEEE operations in the same order).
- [ ] **Step 2: Run** `npx vitest run` → FAIL.
- [ ] **Step 3: Implement.** Keep `sum` order identical to Python (left-to-right over cases sorted by id).
- [ ] **Step 4: Run** → PASS; `npm run build` succeeds with an empty `public/data/index.json` fixture.
- [ ] **Step 5: Commit** `feat(dashboard): static Next.js scaffold, data layer and compare port`.

---

### Task 16: Dashboard pages

**Files:**
- Create: `dashboard/app/layout.tsx`, `app/page.tsx` (experiments), `app/experiments/[name]/page.tsx`, `app/compare/page.tsx` (client, reads `?base=&cand=` under `<Suspense>`), `app/datasets/[name]/page.tsx`, `components/{BudgetBar,RunsTable,CostAccuracyScatter,MetricBars,TagHeatmap,CompareSummary,CaseList,CaseDrawer,StatusBadge}.tsx`, `app/globals.css` (colour tokens, light + dark)
- Use `generateStaticParams` from `getIndex()` for dynamic routes.

**Requirements (spec §10):**
- Experiments page: one card per experiment (hypothesis, run count, status, best accuracy, spent); header `BudgetBar` shows `"$0.43 of $1.00 spent"`.
- Experiment page: `RunsTable` shows only config keys that vary across runs, then accuracy ± CI (CI from `summary`), hit@8, abstention P/R, p50/p95, cost per case, errors; sortable. `CostAccuracyScatter` with CI error bars and the Pareto front (max accuracy for ≤ cost) drawn as a line. `MetricBars` for accuracy, latency, cost. `TagHeatmap` of pass rate by tag × run. Two-run checkbox selection → link to `/compare/?base=…&cand=…`. Accuracy axis label shows `accuracy_definition`.
- Compare page: `CompareSummary` (config diff, Δ, CI, verdict badge, McNemar p, MDE, warnings); `CaseList` with filters (status, tag, reason); `CaseDrawer` side by side: expected evidence; retrieved chunks with evidence matches highlighted and rank badges; answer with citations; status; judge verdict and reason.
- Datasets page: versions and changelog; case browser by tag with per-run pass marks.
- `StatusBadge`: improved = ▲ "Improved", regressed = ▼ "Regressed", stable = ● "Stable pass" / "Stable fail" — icon + text always; palette from the dataviz skill's colour-blind-safe defaults.
- `None` values render `—`.

- [ ] **Step 1:** Export the fake e2e store into `dashboard/public/data` (`evallab export` against a store produced by `fake-sweep.yaml`) as the dev fixture.
- [ ] **Step 2:** Build pages and components.
- [ ] **Step 3: Verify in the browser preview** (`make dashboard`): each page renders without console errors in light and dark; at 375 px nothing scrolls horizontally; selecting two runs opens a compare view whose counts match `evallab compare` on the same pair.
- [ ] **Step 4:** `npm run build && npx tsc --noEmit && npm run lint` → clean.
- [ ] **Step 5: Commit** `feat(dashboard): experiments, experiment, compare and dataset pages`.

---

### Task 17: Playwright smoke test and CI

**Files:**
- Create: `dashboard/playwright.config.ts` (serves `out/` with `npx serve out -l 4173`), `dashboard/e2e/smoke.spec.ts`, `.github/workflows/ci.yml`

- [ ] **Step 1: Write** `smoke.spec.ts`, projects `desktop` (1280×800) and `mobile` (375×812): home shows ≥ 1 experiment card → open it → runs table has ≥ 2 rows → tick two runs → Compare → summary shows a verdict badge → open first case → drawer shows "Expected evidence" and both answers. Assert `document.documentElement.scrollWidth <= innerWidth` on mobile.
- [ ] **Step 2: Run** `npm run build && npx playwright test` → PASS.
- [ ] **Step 3: Write** `ci.yml`: job `python` (checkout this repo and `jbmateo/rag-studio` at the `feat/eval-hooks` ref into `../rag-studio` — needs a `RAG_STUDIO_TOKEN` secret since the repo is private; setup-python 3.12; `make install`; `make test`; `evallab run experiments/rq1-retrieval.yaml --yes` (free, retrieval-only; Studio checked out at the ref under test, so its version — and the run id — change when Studio changes) then `evallab compare $(evallab ci-baseline) rq1-retrieval:retrieval_mode=hybrid --gate --max-regressed 0`); job `dashboard` (setup-node 20; `npm ci`; `npx vitest run`; build; Playwright). Tell the user they must add the secret; don't push.
- [ ] **Step 4:** Validate the workflow syntax with `npx --yes @action-validator/cli .github/workflows/ci.yml` (or report if unavailable).
- [ ] **Step 5: Commit** `ci: tests, retrieval gate and dashboard smoke test`.

---

### Task 18: Free experiments ($0)

**Files:**
- Create: `experiments/rq1-retrieval.yaml`, `experiments/retrieval-sweep.yaml`, `experiments/gate-validation.yaml`
- Modify: `results/evallab.db`, `cache/`, `dashboard/public/data/`

**Requirements:**
- `rq1-retrieval.yaml`: `system: rag_studio`, `dataset: lumen@v1`, `llm: false`, `grid: {retrieval_mode: [vector, bm25, hybrid]}`, `hypothesis` = Studio's pre-registered H1 text copied verbatim from `rag-studio/backend/research/` (find it in the pre-registration commit `8c829e1`).
- `retrieval-sweep.yaml`: `llm: false`, `grid: {chunk_chars: [1000, 2000, 4000], top_k: [4, 8, 12]}`, `description: exploratory`.
- `gate-validation.yaml`: `llm: false`, `variants: [{label: baseline}, {label: aggressive, top_k: 3, chunk_chars: 4000}]`, `hypothesis: "The gate flags the aggressive config: at least one regressed case and a negative accuracy delta."`, `gate: {max_regressed: 0}`.

- [ ] **Step 1:** Commit the three experiment files (pre-registration: before running).
- [ ] **Step 2:** Run each with `evallab run <file> --yes` (allowed: estimate is $0; abort if the table shows any cost). Expected: `complete`, `spent $0.00`.
- [ ] **Step 3:** `evallab compare gate-validation:baseline gate-validation:aggressive --gate` → exit 1 with regressed cases listed. Save the Markdown to `reports/gate-validation.md`. If the gate does **not** fire, report that to the user as a finding — do not tune the config until it does.
- [ ] **Step 4:** Compare RQ1 hybrid vs vector and hybrid vs bm25; save to `reports/`. Check the hit@8 / MRR against `rag-studio/backend/research/results/rq1/summary.json` and note any difference (chunker changed after that run; a difference is expected and must be explained, not hidden).
- [ ] **Step 5:** Set `[ci] baseline_run` in `evallab.toml` to the `rq1-retrieval:retrieval_mode=hybrid` run id. `evallab export`; commit `evallab.toml`, `results/`, `cache/`, `reports/`, `dashboard/public/data/` as `research: free retrieval experiments and gate validation`.

---

### Task 19: Paid experiments (user-gated, ≤ $1.00 total)

**This task is executed together with the user. Every run is a separate turn: show the estimate table, ask "Run this for ~$X? (spent $Y of $1.00)", and only after an explicit yes run it — the user types `y` at the prompt or explicitly approves `--yes` for that one run.** Stop at any point the user declines; later steps are skipped and recorded as not run.

**Files:**
- Create: `experiments/probe.yaml`, `baseline.yaml`, `prompt-sweep.yaml`, `chunk-sweep.yaml`, `gate-sweep.yaml`, `verify-ablation.yaml`, `model-sweep.yaml` — contents per spec §7.1 and §13; H2–H4 hypotheses copied verbatim from Studio's pre-registration (amendments noted in FINDINGS).
- `probe.yaml`: `subset: balanced-3`, `grid: {model: [claude-haiku-5-5, claude-sonnet-5-5]}`, `llm: true`, `judge: true`, hypothesis `"Calibration only: measures tokens per case; no claim."`

- [ ] **Step 0:** Confirm `ANTHROPIC_API_KEY` is available (copy from `rag-studio/backend/.env` into `rag-eval-lab/.env` only with the user's permission). Commit all paid experiment files **except** `model-sweep.yaml`'s `subset`, which is set after step 1.
- [ ] **Step 1 (probe, ~$0.05):** run; report measured cost per case per model.
- [ ] **Step 2 (baseline):** run; report.
- [ ] **Step 3 (prompt-sweep), Step 4 (chunk-sweep), Step 5 (gate-sweep), Step 6 (verify-ablation, expected $0):** one at a time, each with its own approval.
- [ ] **Step 7 (model-sweep):** compute `n = floor(remaining / measured_sonnet_cost_per_case)`, clamp to ≤ 60; if `n < 20`, skip H5 and record why. Otherwise set `subset: balanced-<n>`, commit, show estimate, ask, run.
- [ ] **Step 8:** `evallab spotcheck sample` on the model-sweep (or baseline if H5 skipped) runs → give the CSV to the user to hand-label; after they finish, `evallab spotcheck score` → record κ.
- [ ] **Step 9:** compares for each hypothesis into `reports/`; `evallab export`; commit `research: paid experiments (spent $X of $1.00)`.

---

### Task 20: FINDINGS, README and screenshots

**Files:**
- Create: `FINDINGS.md`, `README.md`, `docs/screenshots/*.png`

- [ ] **Step 1: FINDINGS.md** — per hypothesis H1–H6: statement as registered (with commit sha), setup (experiment file, dataset version, system version, n, subset), results table with CIs and MDE, verdict, what changed because of it. Sections: judge reliability (κ overall and per model), gate validation walkthrough, limitations (n = 60, Haiku judge self-preference, H5 subset size, single corpus, chunker change since Studio's RQ1), actual total spend. Steps not run are listed as not run, with the reason.
- [ ] **Step 2: README.md** — what it is and why (systematic improvement over demos), architecture diagram (adapter → runner → store → export → dashboard), quickstart (`make install`, `make test`, `evallab dataset validate lumen@v1`, `evallab run experiments/rq1-retrieval.yaml`, `evallab compare …`, `make dashboard`), how to add an adapter (the `RAGSystem` protocol in 15 lines), screenshots, link to RAG Studio. No portfolio/interview wording.
- [ ] **Step 3:** Screenshots via the browser preview: experiments page, experiment scatter, compare view with drawer open (desktop), and one mobile.
- [ ] **Step 4:** Final checks: `make test`, `make test-slow`, dashboard build + Playwright all pass; `grep -rniE "portfolio|interview" --exclude-dir=node_modules .` returns nothing.
- [ ] **Step 5: Commit** `docs: findings, README and screenshots`. Ask the user before creating a GitHub repo or pushing.
