# RAG Evaluation Lab — Design Spec

Date: 2026-10-18 · Status: draft for review · Companion to [RAG Studio](../../../rag-studio)

## 1. Purpose

An evaluation and regression-testing tool for retrieval-augmented generation systems. It is a research
tool for improving an AI system **systematically**: changes are stated as hypotheses up front, measured on a versioned dataset, compared case by case with honest
statistics, and gated against regressions, instead of being judged from a few good-looking demos.

RAG Studio is the first system under test. Eval Lab is general: it talks to systems only through an
adapter interface (§4).

**Success criteria**

1. Picking any two runs in the dashboard shows immediately which cases
   improved or regressed, why, and what each change cost.
2. Every number in `FINDINGS.md` is reproducible from a committed experiment file, dataset version
   and system version.
3. The whole project's API spend stays within **$1.00** (§8).

**MVP features**

- Versioned evaluation dataset in JSONL (§5)
- Comparison of chunk sizes, retrieval strategies, prompts and models (§7)
- Automated retrieval and answer evaluation (§6)
- Dashboard comparing accuracy, latency and estimated cost (§10)
- Saved experiment configurations and results (§7, §8)
- Regression report identifying improved and regressed cases (§9)

## 2. Decisions

| Topic | Decision |
|---|---|
| Relation to RAG Studio | General tool with an adapter boundary; Studio is the first adapter, imported as a Python package (editable install) |
| Studio's `research/` harness | Frozen. Its RQ1 results and pre-registered hypotheses stay where they are. Eval Lab imports its question set as dataset `lumen@v1` and restates RQ1–RQ4 as Eval Lab experiments |
| Dashboard | Next.js static site fed by JSON exported from the results store — no API server; deployable for free |
| Models compared | `claude-sonnet-5-5` vs `claude-haiku-5-5` |
| Judge | `claude-haiku-5-5` for every run (budget), calibrated by a hand-labelled spot check |
| Spend | Cost-gated, cache-first, offline defaults; $1.00 project-wide hard cap |

## 3. Repository layout

```
rag-eval-lab/
├── evallab/
│   ├── cli.py               `evallab` entry point (Typer)
│   ├── adapters/
│   │   ├── base.py          RAGSystem protocol, Trace and related dataclasses
│   │   ├── rag_studio.py    RAG Studio adapter
│   │   └── fake.py          deterministic, config-sensitive system for tests
│   ├── datasets.py          load, hash-verify, validate, create and publish versions
│   ├── experiments.py       YAML → concrete run configs
│   ├── runner.py            executes runs: cache, cost gate, budget, resume
│   ├── cache.py             content-addressed disk cache for LLM calls
│   ├── pricing.py           reads pricing.yaml, token → USD
│   ├── metrics/
│   │   ├── retrieval.py     hit@k, evidence recall@k, MRR
│   │   ├── answer.py        abstention, citation validity, case pass rule
│   │   └── judge.py         LLM judge (structured output) + FakeJudge
│   ├── stats.py             McNemar exact test, paired bootstrap CI, minimum detectable effect
│   ├── compare.py           regression report (Markdown + JSON) and gate
│   ├── spotcheck.py         sample judged cases for hand labelling; Cohen's κ
│   ├── store.py             SQLite results store
│   └── export.py            store → dashboard/public/data/*.json
├── dashboard/               Next.js 15 static export
├── datasets/lumen/          manifest.yaml, v1.jsonl, corpus.lock
├── experiments/             *.yaml
├── tests/                   pytest
├── cache/                   LLM + judge cache (committed, so re-runs are free for anyone)
├── results/evallab.db       committed results
├── pricing.yaml
├── evallab.toml             paths, budget, defaults
├── .github/workflows/ci.yml
├── Makefile
├── README.md
├── FINDINGS.md
└── docs/design/, docs/plans/
```

Stack: Python ≥ 3.11, `anthropic`, `pydantic`, `pyyaml`, `typer`, `numpy`, `scipy` (McNemar via
binomial), `pytest`. RAG Studio's backend is installed with `pip install -e ../rag-studio/backend`.
Dashboard: Next.js 15, React 19, Tailwind 4, Recharts, Playwright (same as RAG Studio plus Recharts).

## 4. Adapter interface

```python
class RAGSystem(Protocol):
    name: str
    def version(self) -> str: ...                      # e.g. "rag-studio@f858310+dirty:<hash>"
    def config_schema(self) -> type[BaseModel]: ...    # pydantic model of accepted settings
    def prepare(self, corpus: Corpus, config: BaseModel) -> None: ...   # ingest; cached per ingest-relevant keys
    def answer(self, question: str, config: BaseModel, llm: bool) -> Trace: ...
```

```python
@dataclass
class RetrievedChunk:  rank: int; document: str; text: str; score: float
@dataclass
class Citation:        sentence_index: int; chunk_rank: int | None   # None = cites nothing retrieved
@dataclass
class LLMCall:         model: str; role: str; input_tokens: int; output_tokens: int; cached: bool; ms: int
@dataclass
class Trace:
    retrieved: list[RetrievedChunk]
    status: Literal["answered", "partial", "abstained", "retrieval_only"]
    sentences: list[str]
    citations: list[Citation]
    raw_citation_count: int            # before any verification step
    raw_valid_citation_count: int
    llm_calls: list[LLMCall]
    timings_ms: dict[str, int]         # e.g. {"retrieve": 41, "generate": 2310}
    system_detail: dict                # adapter-specific extras, stored but never scored
```

`version()` must change whenever the system's code changes; a dirty working tree appends a hash of
the diff. Eval Lab never imports anything from a system except through its adapter, and computes
every metric from `Trace` plus the dataset.

### 4.1 RAG Studio adapter

- Config schema mirrors Studio's `PipelineConfig`: `retrieval_mode`, `min_similarity`,
  `verify_citations`, `chunk_chars`, `top_k`, `model`, plus the new `prompt_variant`.
- `prepare` ingests the corpus into a throwaway SQLite DB per `chunk_chars` (same approach as Studio's
  `research/harness.py`), using fastembed by default or Studio's `hash` embedder in tests.
- `answer` calls `answer_question_detailed` and maps the response:
  `not_found` and `insufficient_evidence` → `abstained`; `answered` and `partial` → as is.
  Studio's LLM is wrapped in its `CachedLLM`, pointed at `rag-eval-lab/cache/system/`.

### 4.2 Required RAG Studio changes (separate branch in the rag-studio repo)

1. **Prompt variants.** Add `prompt_variant: str = "default"` to `PipelineConfig`, and
   `app/answer/prompts.py` with a `PROMPTS: dict[str, str]` registry (`default` = today's
   `SYSTEM_PROMPT`, unchanged). `LLM.draft` receives the system prompt; `CachedLLM`'s key uses the
   prompt actually sent rather than the module constant, otherwise variants would collide in the cache.
2. **Cache key completeness.** Add the output schema and `effort` to `CachedLLM`'s key.
3. **Expose the raw draft.** `answer_question_detailed`'s trace already carries `raw_sentences`;
   confirm it is enough to compute raw citation validity, and add the per-call `stop_reason`.
4. No behaviour change for Studio users: default config produces byte-identical requests.

## 5. Versioned dataset

```
datasets/lumen/
├── manifest.yaml
├── v1.jsonl
└── corpus.lock        # sha256 per corpus file
```

```yaml
name: lumen
corpus: {path: ../rag-studio/backend/research/corpus, lock: corpus.lock}
versions:
  - version: v1
    file: v1.jsonl
    sha256: <hex>
    cases: 60
    created: 2026-10-18
    parent: null
    changes: "Imported from rag-studio research/questions.jsonl @ f858310"
```

Case schema (a superset of Studio's, so v1 imports unchanged):

```json
{"id": "q002", "question": "...", "answerable": true, "tag": "exact_term",
 "expected": [{"document": "api-reference.md", "evidence": "If a robot has less than 15 percent ..."}],
 "reference_answer": null}
```

Rules:

- **Published versions are immutable.** Loading recomputes sha256 and refuses to run on mismatch.
  New versions: `evallab dataset new lumen --from v1` creates an editable draft;
  `evallab dataset publish lumen` validates, hashes, requires a `--changes` message and appends to
  the manifest.
- **Case IDs persist across versions** only when the meaning is unchanged; otherwise a new ID.
- **Corpus lock:** every run records the lock hash; a mismatch with the files on disk aborts the run.
- **Validation on load:** unique IDs; every `expected.document` exists in the corpus; every `evidence`
  string occurs in that document after the same normalization used for chunk matching; unanswerable
  cases have empty `expected`; `tag` is non-empty.
- References use `name@version`, e.g. `lumen@v1`.

## 6. Metrics

All metrics are computed per case, then aggregated per run. Evidence matching: normalized substring
containment of the evidence in the chunk text (lower-case, whitespace collapsed, same as Studio).

**Retrieval** (answerable cases; free):

- `hit@k` — any expected evidence in the top k (k = config `top_k`, default 8)
- `evidence_recall@k` — share of the case's expected evidence items found in the top k
- `mrr` — 1 / rank of the first chunk containing any expected evidence; 0 if none

**Answer** (LLM runs):

- `abstained` — `Trace.status == "abstained"`
- Run-level: `answer_rate` (answered or partial, over answerable cases), `abstention_precision`
  and `abstention_recall` (over unanswerable cases)
- `citation_validity_raw` — `raw_valid_citation_count / raw_citation_count`
- `citation_validity` — share of shown citations whose `chunk_rank` is not None
- Judge verdict (answered and partial cases only): one call per case.
  - Input: question, answer sentences, gold evidence, `reference_answer` if present, and the text
    of the chunks the answer cites.
  - Output (structured, pydantic-validated): `{correct: bool, unsupported_claims: int, reason: str}`.
    `correct` means the answer states what the evidence says in reply to the question; for a
    `partial` answer, correct only if what it does state is right **and** the missing part is truly
    absent from the gold evidence.
  - Refusal, truncation or invalid output → `unjudged`; reported as a count, excluded from
    accuracy's denominator, never guessed.

**Case pass rule** (drives accuracy and the regression report):

- answerable → pass iff status is `answered` or `partial`, judge `correct`, and `unsupported_claims == 0`
- unanswerable → pass iff `abstained`
- `accuracy` = passed / (cases − errored − unjudged)
- Retrieval-only runs (`llm: false`): `accuracy` is defined as `hit@k` over answerable cases, and
  every report and chart labels which definition is in use.

**Operating metrics**

- Latency p50 / p95, per stage and end to end, computed only from LLM calls that were not cache
  hits; cached cases are flagged and excluded from latency. Retrieval latency is always measured.
- Cost from `LLMCall` tokens × `pricing.yaml`: `cost_nominal` (as if nothing were cached) and
  `cost_spent` (actual), each split into `system` and `judge`; plus `cost_per_case`.

**Judge reliability**

- Judge model and rubric version are part of the run identity.
- `evallab spotcheck <run>...` samples 30 judged cases stratified by the run's model under test,
  writes a CSV for hand labelling, and once labelled reports judge-vs-human agreement and Cohen's κ.
- Known risk, stated in FINDINGS: a Haiku judge may favour Haiku answers. κ is reported per model.

## 7. Experiments

```yaml
name: model-sweep
description: Is Haiku good enough for grounded, abstaining answers?
hypothesis: >
  H5 — claude-haiku-5-5 accuracy is within 5 points of claude-sonnet-5-5 at ≤ 10% of the cost per case.
system: rag_studio
dataset: lumen@v1
subset: balanced-30        # optional; named, seeded, tag-stratified subset recorded in the run
llm: true
judge: true
base: {retrieval_mode: hybrid, chunk_chars: 2000, top_k: 8, min_similarity: 0.35,
       verify_citations: true, prompt_variant: default}
grid:
  model: [claude-sonnet-5-5, claude-haiku-5-5]
repeats: 1
gate: {max_regressed: 0, min_accuracy_delta: -0.02, max_cost_ratio: 1.2}
```

- `grid` is a cartesian product over `base`; alternatively `variants:` is an explicit list of
  `{label, ...overrides}`. Each run gets a label (from `variants`, or generated from grid values).
- Every concrete config is validated against the adapter's `config_schema()` before anything runs.
- **Pre-registration:** an experiment with `llm: true` must have `hypothesis`. The runner records the
  git commit of the experiment file; it refuses to run if the file has uncommitted changes, so the
  hypothesis provably predates the results.
- `subset` names are resolved by `datasets.py` with a fixed seed and stored with the run.
- `repeats > 1` bypasses the cache on purpose to measure answer variance (not used within budget).

### 7.1 Planned experiments

| File | Hypothesis | Varies | Model | Cost |
|---|---|---|---|---|
| `rq1-retrieval.yaml` | H1 (Studio RQ1): hybrid beats best single mode by ≥ 10 pts hit@8 on `exact_term` | retrieval_mode | — | $0 |
| `retrieval-sweep.yaml` | exploratory, no LLM | chunk_chars, top_k | — | $0 |
| `gate-validation.yaml` | validates the gate itself: a plausible "optimization" that breaks cases must be caught | a deliberately bad config (e.g. `top_k: 3`, `chunk_chars: 4000`) vs baseline | — | $0 |
| `baseline.yaml` | — (baseline used by every LLM sweep) | — | haiku | ~$0.06–0.10 |
| `prompt-sweep.yaml` | H6: a "cite every claim, be terse" prompt reduces unsupported claims without lowering answer rate | prompt_variant | haiku | ~$0.06–0.10 |
| `chunk-sweep.yaml` | H4 (Studio RQ4) restated | chunk_chars 1000 / 4000 | haiku | ~$0.12–0.20 |
| `gate-sweep.yaml` | H2 (Studio RQ2) restated, reduced to 0.25 / 0.35 / 0.45 | min_similarity | haiku | ~$0.05–0.10 |
| `verify-ablation.yaml` | H3 (Studio RQ3) restated | verify_citations | haiku | $0 (cached drafts) |
| `model-sweep.yaml` | H5 (above) | model | both | remainder |

Exact hypothesis wording for H1–H4 is copied from Studio's pre-registered text; any change is recorded
as an amendment in FINDINGS.

## 8. Runner, cache, cost and storage

**Run identity.** `run_id` = first 12 hex chars of sha256 over (dataset version sha, subset, corpus
lock hash, system version, judge model + rubric version, full validated config, repeat index).
An existing complete run with the same id is reused unless `--force`.

**Flow for `evallab run <file>`:**
1. Load and verify the dataset and corpus lock; load the experiment; expand; validate configs.
2. For each run: count cases needing an uncached LLM call (cache lookups are exact, so this is known
   before spending).
3. Estimate cost per uncached call from the mean measured tokens of earlier calls with the same model
   and role; if none exist, from `count_tokens`-free heuristics (input chars / 4, output = 1,500 tokens
   to allow for thinking) — the estimate is flagged "unmeasured" in that case.
4. Print a table: run label, cases, uncached system calls, uncached judge calls, estimated USD,
   plus project spend so far and remaining budget.
5. Refuse if the estimate exceeds the remaining budget. Otherwise ask `y/N` (`--yes` to skip,
   `--dry-run` to stop here).
6. `prepare`, then run cases sequentially; record each case result immediately (so runs can resume).
7. After every uncached call, add its actual cost to the project ledger; if the **next** call's
   estimate would exceed the cap, stop and mark the run `partial`. `evallab run --resume` continues.

**Cache.** Directory `cache/system/` (Studio's `CachedLLM` format) and `cache/judge/` (sha256 of
model, rubric version, system prompt, messages and output schema). Committed to git so anyone can
reproduce all results at $0.

**Budget.** `evallab.toml`: `budget.total_usd = 1.00`. The ledger is the sum of `cost_spent` over all
runs in the store. `evallab budget` prints spent / remaining. Raising the cap is an explicit edit to
`evallab.toml`.

**Errors.** SDK retries handle transient API errors. A case still failing is stored with
`status = error` and excluded from metrics; a run with > 10% errored cases is marked `degraded`.
Missing API key with an LLM experiment → refuse before estimating, with a clear message. Retrieval-only
experiments never need a key.

**SQLite store (`results/evallab.db`):**

- `experiments(name, yaml, git_sha, hypothesis, created_at)`
- `runs(run_id, experiment, label, config_json, system, system_version, dataset, dataset_sha, subset,
  judge_model, status[complete|partial|degraded], started_at, finished_at, summary_json)`
- `case_results(run_id, case_id, status[ok|error], pass, metrics_json, trace_json, judge_json,
  cost_spent, cost_nominal, latency_ms, cached)`
- `ledger(ts, run_id, case_id, model, role, usd)`

## 9. Regression report

`evallab compare <baseline> <candidate> [--format md|json] [--out path] [--gate]`. Runs are addressed
by id prefix or `experiment:label`.

- **Pairing:** cases matched by id; if dataset versions differ, use the shared ids and print a
  warning first. Cases errored in either run are listed as not comparable.
- **Status:** improved (fail → pass), regressed (pass → fail), stable pass, stable fail.
- **Reason** for each flip, first that applies: `retrieval_lost` / `retrieval_gained` (hit@k changed),
  `wrongly_abstained` / `hallucinated` (abstention changed on answerable / unanswerable),
  `judge_incorrect` / `judge_correct`, `unsupported_claims`.
- **Statistics:**
  - McNemar exact test (two-sided binomial on the discordant pairs) for pass/fail.
  - Paired bootstrap 95% CI (10,000 resamples, seed 0) for Δ accuracy, Δ MRR, Δ p50 latency,
    Δ cost per case.
  - Verdict "better" / "worse" only when the CI excludes 0; otherwise "no detectable difference".
  - Minimum detectable effect at the current n (80% power, α = 0.05) is printed, so it is clear
    how large a change this dataset can resolve.
- **Contents:** config diff (only differing keys), versions, judge; summary table with
  baseline → candidate, Δ, CI; counts by status and by tag; regressed cases first (question, reason,
  both answers, judge reasons), then improved, then a collapsed stable-fail list.
- **Gate:** with `--gate`, exit code 1 if any `gate` threshold (from the experiment or CLI flags) is
  violated, and the failed checks are listed.

## 10. Dashboard

Static Next.js export. `evallab export` writes `dashboard/public/data/`:
`index.json` (experiments, runs, budget), `experiments/<name>.json` (runs + summaries),
`runs/<run_id>.json` (case results with traces), `datasets/<name>.json`.

Comparisons are computed in the browser from two run files. `dashboard/lib/compare.ts` reimplements
`compare.py`'s classification, reasons and statistics with a seeded PRNG; a shared fixture test
requires identical output from both.

Pages:

1. `/` — experiment cards: hypothesis, runs, status, best accuracy, spend; header shows project budget.
2. `/experiments/[name]` — runs table (varying keys as columns; accuracy ± CI, hit@8, abstention P/R,
   p50/p95, cost per case, errors; sortable); cost-vs-accuracy scatter with CI bars and the Pareto
   front highlighted; grouped bars for accuracy, latency, cost; tag × run pass-rate heatmap; select two
   runs → Compare.
3. `/compare?base=&cand=` — the §9 report; filters by status, tag, reason; case drawer with question,
   expected evidence, and both runs side by side (retrieved chunks with evidence highlighted and rank
   badges, answer with citations, status, judge verdict and reason).
4. `/datasets/[name]` — versions and changelog; case browser by tag with per-run pass marks.

Design: neutral data-tool look; colour-blind-safe palette; improved/regressed always paired with an
icon and label, never colour alone; light and dark; responsive down to 375 px. `make dashboard`
exports and runs `next dev`; `make site` builds the static site.

## 11. Testing

All tests run offline at $0.

- **Unit:** dataset hashing (tampered file fails), validation (missing document, evidence not in
  document, duplicate id, unanswerable with evidence); experiment expansion, schema rejection,
  hypothesis required, dirty experiment file refused; retrieval and answer metrics and the pass rule on
  hand-built traces; McNemar and bootstrap against known values and seed reproducibility; pricing,
  estimates, ledger, budget stop → `partial`, resume.
- **End-to-end (fake adapter + FakeJudge):** run → store → compare → export with known improved and
  regressed cases; gate exit codes.
- **RAG Studio adapter integration:** retrieval-only run on the real corpus with the `hash` embedder;
  a check that Eval Lab's RQ1 hit@8 / MRR reproduce Studio's committed `research/results/rq1/summary.json`
  when run with fastembed (marked slow).
- **Parity:** `compare.py` and `compare.ts` produce identical JSON on a fixture.
- **Dashboard:** Playwright smoke test on the static build — experiments → experiment → compare →
  case drawer — at desktop and mobile widths.
- **CI** (`.github/workflows/ci.yml`): pytest (fast set), dashboard build + Playwright, and
  `evallab run experiments/rq1-retrieval.yaml` + `evallab compare --gate` against the committed baseline.

## 12. Deliverables

- `FINDINGS.md`: per hypothesis — statement (as registered), setup (experiment file, dataset, system
  version, n), results with CIs, verdict, and what was changed because of it; a judge-reliability
  section (κ); a gate-validation walkthrough; a limitations section (n = 60, Haiku judge, subset size
  for H5, single corpus); actual total spend.
- `README.md`: what and why, architecture diagram, quickstart (`make install`, `make test`,
  `evallab run`, `make dashboard`), screenshots, hosted dashboard link, link to RAG Studio.

## 13. Budget plan

Hard cap $1.00 for the whole project. Every step below is a separate `evallab run` with its own
estimate and confirmation; the order is the priority order.

| # | Step | Estimate |
|---|---|---|
| 0 | Calibration probe: 3 cases × (haiku, sonnet), measures real tokens incl. thinking | ~$0.05 |
| 1 | `baseline.yaml` (haiku, 60 cases, haiku judge) | ~$0.06–0.10 |
| 2 | `prompt-sweep.yaml` | ~$0.06–0.10 |
| 3 | `chunk-sweep.yaml` | ~$0.12–0.20 |
| 4 | `gate-sweep.yaml` | ~$0.05–0.10 |
| 5 | `verify-ablation.yaml` | $0 |
| 6 | `model-sweep.yaml` on a balanced subset; n = remaining budget ÷ measured sonnet cost per case, min 20, max 60 | remainder |

If step 0 shows fewer than 20 Sonnet cases fit, H5 is not run and FINDINGS says so. Retrieval-only
experiments (H1, retrieval sweep, gate validation) are free and run first.

## 14. Out of scope (v1)

A second real system adapter (the fake adapter proves the interface); HTTP adapter; launching runs
from the dashboard; auth; LLM-generated datasets; Batch API; multiple judges; longitudinal trends
across many commits (v1 is pairwise compare + gate); answer-variance studies (`repeats > 1`).
