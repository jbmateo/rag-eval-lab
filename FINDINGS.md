# Findings

Every result below comes from a committed experiment file, the versioned dataset `lumen@v1` (60 questions:
20 `exact_term`, 20 `natural`, 20 `unanswerable`) and a recorded system version. Hypotheses were committed before
their runs; the experiment file's commit is stored with each run. Comparisons are paired over the same cases, with
95% paired bootstrap intervals (10,000 resamples, seed 0) and an exact McNemar test. Reports for each comparison are
in [`reports/`](reports/); the dashboard shows every run case by case.

**System under test:** RAG Studio `rag-studio@e97f4e8` (branch `feat/eval-hooks`: default pipeline unchanged; adds
prompt variants and a complete answer-cache key). Hybrid retrieval, 2,000-character chunks, top 8, similarity gate
0.35, citation verification on, unless a row says otherwise.
**Judge:** `claude-haiku-5-5`, rubric `v1`, effort `low`, one verdict per answered case.
**Accuracy** is the share of cases that pass: an answerable question passes if it is answered, the judge rules it
correct and finds no unsupported claim; an unanswerable question passes if the system abstains. Retrieval-only
experiments use hit@8 over the 40 answerable questions instead.

**Total API spend: $0.85 of a $1.00 budget.**

## Summary

| | Question | Verdict |
|---|---|---|
| H1 | Does hybrid retrieval beat vector-only on exact terms by ≥ 10 points? | **Rejected** (+5 pts) — reproduces RAG Studio's own result exactly |
| H2′ | Does raising the similarity gate trade answers for refusals? | **Rejected** — the gate never fires at 0.25–0.45 |
| H3′ | Does citation verification remove unsupported claims? | **Rejected** — nothing to remove at the default chunk size |
| H4 | Do small chunks retrieve better and large chunks answer more? | **Rejected** — both gaps have the wrong sign or are zero |
| H5 | Is Haiku within 5 points of Sonnet at ≤ 10% of the cost? | **Holds** — +3.3 pts at 5.7% of the cost; no detectable difference |
| H6 | Does a terse, cite-everything prompt reduce unsupported claims? | **Holds as registered**, but the change is within noise |
| Gate | Does the regression gate catch a plausible bad change? | **Yes** — 5 regressed cases, exit 1 |
| Explore | Can a higher similarity threshold help at all? | **No** — it only blocks answerable questions |

The most useful result is not on this list: **the judge is the noisiest part of the measurement** (see
[Judge reliability](#judge-reliability)).

## H1 — hybrid vs single-mode retrieval (retrieval only, $0)

Registered in rag-studio commit `8c829e1`: *on `exact_term` questions, hybrid hit@8 is at least 10 points above
vector-only; on `natural`, hybrid is within 5 points of vector; overall, hybrid is at least as high as the better
single mode.*

| hit@8 | vector | bm25 | hybrid |
|---|---|---|---|
| exact_term (n=20) | 0.95 | 1.00 | 1.00 |
| natural (n=20) | 0.95 | 0.75 | 0.95 |
| overall (n=40) | 0.950 | 0.875 | 0.975 |

The `exact_term` gain is +5 points, half the predicted 10, so **H1 is rejected**; the other two clauses hold. These
are exactly the numbers RAG Studio's own harness committed (`research/results/rq1/summary.json`), which is the
check that Eval Lab's port of the metrics is faithful (a slow test also asserts this). Vector-only versus hybrid:
2 cases improved, 1 regressed ([report](reports/rq1-vector-vs-hybrid.md)).

**What changed because of it:** nothing in RAG Studio — hybrid still has the best overall hit@8 and costs nothing
extra — but the claim "hybrid fixes exact terms" is off the table for this corpus: vector search already finds 19 of 20.

## Gate validation — does the gate catch a bad change? (retrieval only, $0)

A plausible cost-saving change: fewer, bigger chunks (`top_k` 3, 4,000 characters). Registered claim: the gate
flags it.

| | baseline | aggressive | Δ | 95% CI |
|---|---|---|---|---|
| hit@k (n=40) | 0.975 | 0.875 | −10.0 pts | [−22.5, 0.0] |
| evidence recall | 0.917 | 0.804 | | |

`evallab compare --gate` exits 1 with **5 regressed cases** (all `retrieval_lost`) against 1 improved
([report](reports/gate-validation.md)). The claim holds. Note the interval: at n = 40 the statistics alone would
call this "no detectable difference" (McNemar p = 0.22, smallest detectable change ≈ 17 pts). The gate's
"no regressed cases" rule is deliberately stricter than the statistics — it is a tripwire that sends a person to
read the regressed cases, not a significance test.

## H2′ — the similarity gate ($0)

Registered as H2 in rag-studio `8c829e1`, sweep reduced from nine thresholds (0.20–0.60) to three (0.25, 0.35, 0.45)
for budget, stated before running: *raising `min_similarity` from 0.25 to 0.45 does not raise the answer rate and
does raise refusal recall; some threshold reaches answer rate ≥ 80% with refusal recall ≥ 70%.*

| min_similarity | answer rate (answerable) | refusal recall (unanswerable) | cases gated |
|---|---|---|---|
| 0.25 | 100% | 100% | 0 / 60 |
| 0.35 | 100% | 100% | 0 / 60 |
| 0.45 | 100% | 100% | 0 / 60 |

Refusal recall does not rise, so **H2′ is rejected** (the other clauses hold trivially). The cause: with RAG
Studio's embedder every question's best match scores between 0.60 and 0.82 — unanswerable questions included — so a
threshold below 0.60 never gates anything. All three runs sent identical requests, which is why they cost $0. All
abstention here comes from the model, which declined every unanswerable question.

### Exploratory follow-up: higher thresholds ($0, not pre-registered)

Written after seeing the similarity distribution above, so it carries no pass/fail claim.

| min_similarity | answerable blocked | unanswerable blocked | refusal recall | accuracy |
|---|---|---|---|---|
| 0.35 | 0 / 40 | 0 / 20 | 100% | 91.7% |
| 0.65 | 1 / 40 | 1 / 20 | 100% | 91.7% |
| 0.70 | 8 / 40 | 2 / 20 | 100% | 81.7% |
| 0.75 | 15 / 40 | 3 / 20 | 100% | 71.7% |
| 0.80 | 17 / 40 | 3 / 20 | 100% | 70.0% |

Raising the threshold only blocks answerable questions. It can never block more than 3 unanswerable ones, because
in hybrid mode the gate also passes any question with a strong keyword match, and 17 of the 20 unanswerable
questions have one. **What changed because of it:** for this corpus and model the similarity gate is not a useful
guardrail; the model's own abstention is. A gate keyed on keyword-match quality, not embedding similarity, is the
next thing worth testing.

## H3′ — citation verification ($0)

Registered as H3 in rag-studio `8c829e1`, measured per answer (this judge counts unsupported claims per answer, not
per sentence): *raw citation validity with verification off is below 98%, and the share of answered cases with an
unsupported claim falls by at least 3 points with verification on.*

| | verification off | verification on |
|---|---|---|
| raw citation validity (before verification) | 100% | 100% |
| answered cases with ≥ 1 unsupported claim | 5 / 40 | 5 / 40 |

At the default chunk size Haiku cited only passages that exist, so verification had nothing to remove and both
arms produced identical answers. **H3′ is rejected.** Verification did act in the chunk-size runs (3 citations
dropped at 1,000 characters, 6 at 4,000; raw validity 97.4% and 95.1%), so it is not dead code — just idle on the
default configuration.

## H4 — chunk size (Haiku, $0.10)

Registered in rag-studio `8c829e1`: *chunk size 1,000 has hit@8 at least 5 points above 4,000, while 4,000 has an
answer rate at least 5 points above 1,000.*

| chunk_chars | hit@8 | answer rate | accuracy | cost per case |
|---|---|---|---|---|
| 1,000 | 95.0% | 95.0% | 91.7% | $0.00042 |
| 2,000 | 97.5% | 100% | 91.7% | $0.00062 |
| 4,000 | 100% | 95.0% | 91.7% | $0.00099 |

The retrieval gap has the opposite sign (−5 pts) and the answer-rate gap is zero, so **H4 is rejected on both
clauses.** Accuracy is the same at every size — yet between 1,000 and 4,000 characters **10 cases flip, 5 each
way**, which is exactly what a single headline number hides and the case-level comparison shows; cost per case grows with chunk size (more input tokens). On this
corpus, the default of 2,000 is the best answer rate at a middle cost, and 1,000 is the cheapest option with the
same accuracy ([report](reports/h4-chunk-4000-vs-1000.md)).

## H5 — Sonnet vs Haiku ($0.63)

Registered before the Sonnet run: *Haiku accuracy is within 5 points of Sonnet at no more than 10% of the system
cost per case.* The probe measured Sonnet at ~$0.011 a case, so the full dataset fit the budget.

| | claude-sonnet-5-5 | claude-haiku-5-5 | Δ (Haiku − Sonnet) |
|---|---|---|---|
| accuracy (n=60) | 88.3% [80.0, 95.0] | 91.7% [83.3, 98.3] | +3.3 pts [−5.0, +11.7] |
| refusal recall | 95% | 100% | |
| cost per case (system) | $0.0109 | $0.00062 | 5.7% of Sonnet |
| latency p50 / p95 | 2.35 s / 4.97 s | 2.32 s / 5.96 s | |

McNemar p = 0.73 (5 improved, 3 regressed); the smallest change this sample can detect is about 13 points.
Haiku is within 5 points — it scored higher — at 5.7% of the cost, so **H5 holds**, and the right reading is that the
two models are indistinguishable on this task at n = 60 while Haiku costs 18× less
([report](reports/h5-sonnet-vs-haiku.md)). **What changed because of it:** Haiku is the sensible default answering
model for RAG Studio on this kind of corpus.

## H6 — a terse, cite-everything prompt (Haiku, $0.04)

Registered before running: *with `terse_cite_all`, the share of answered cases with an unsupported claim is at
least 5 points lower than with the default prompt, and the answer rate is not more than 5 points lower.*

| | default | terse_cite_all | Δ |
|---|---|---|---|
| answered cases with ≥ 1 unsupported claim (n=40) | 12.5% | 7.5% | −5.0 pts [−12.5, 0.0] |
| answer rate | 100% | 100% | 0 |
| accuracy (n=60) | 91.7% | 93.3% | +1.7 pts |

Both clauses hold, exactly at the threshold, so **H6 holds as registered** — but the interval reaches zero and the
difference is two cases, which the judge noise described below could produce on its own. Treat it as a lead to
re-test on a larger dataset, not a result ([report](reports/h6-prompt.md)).

## Judge reliability

Comparing near-identical answers across runs shows the judge's `unsupported_claims` count is inconsistent. In H5,
two of the three "regressions" are answers that are almost word for word the same as the passing ones, failed
because the judge counted a release version label as unsupported in one run and accepted it in the other (q036,
q044); a third verdict's reasoning contradicts itself (q020: "…so it is supported … counted conservatively as one").
Because a case fails on a single unsupported claim, this noise moves accuracy case by case.

A hand-labelled spot check is prepared: 30 judged answers, 15 from each model, in
[`spotcheck/2026-10-18-570cb6-16143c.csv`](spotcheck/2026-10-18-570cb6-16143c.csv). **Agreement and Cohen's κ are
pending the hand labels** and will be added here. Until then, every accuracy difference smaller than a few cases
should be read as within judge noise. Next steps, in order of cost: score the spot check; re-judge at higher effort
(cached answers make this judge-only); require two consistent verdicts before a case fails.

## Limitations

- **Small dataset.** n = 60 (40 answerable). The smallest detectable change is 8–17 points depending on the
  comparison; most differences here are below it.
- **One corpus.** All results are for the six-document Lumen Robotics corpus; the similarity-gate finding in
  particular depends on its embedder and vocabulary.
- **Haiku judges Haiku.** The judge may favour answers in its own style. The spot check is stratified by model to
  measure this; until it is scored, H5 should be read with that caveat.
- **Restated hypotheses.** H2′ and H3′ were adapted from RAG Studio's pre-registered H2 and H3 (smaller sweep,
  per-answer measure) before running; H4 was run with Haiku rather than Sonnet answering.
- **Single runs.** No repeats; answer variance between identical runs is not measured.

## Spend

| experiment | spent |
|---|---|
| probe (3 cases × 2 models) | $0.035 |
| baseline | $0.044 |
| prompt-sweep | $0.042 |
| chunk-sweep | $0.101 |
| model-sweep (Sonnet, 60 cases) | $0.631 |
| gate-sweep, verify-ablation, gate-sweep-high, all retrieval-only experiments | $0.000 |
| **total** | **$0.853** |

Every LLM call is cached by content and the cache is committed, so all of the above re-runs for $0.
