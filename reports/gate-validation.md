# Compare: rq1-retrieval:retrieval_mode=hybrid → gate-validation:aggressive

Baseline `db4ac97e819d` (complete) · Candidate `360332995d46` (complete)

## What changed

| setting | baseline | candidate |
|---|---|---|
| chunk_chars | 2000 | 4000 |
| top_k | 8 | 3 |

System rag-studio@e97f4e8 → rag-studio@e97f4e8 · dataset lumen@v1 → lumen@v1 · judge none → none

## Summary

40 paired cases · McNemar p = 0.219 · minimum detectable change ≈ +17.1 pts

| metric | baseline | candidate | Δ | 95% CI | verdict |
|---|---|---|---|---|---|
| accuracy | 0.9750 | 0.8750 | -0.1000 | [-0.2250, 0.0000] | no detectable difference |
| mrr | 0.7159 | 0.7125 | -0.0034 | [-0.1033, 0.1018] | no detectable difference |
| latency_ms | 6.8500 | 7.4000 | 0.5500 | [0.2750, 0.8500] | worse |
| cost_per_case | 0.0000 | 0.0000 | 0.0000 | [0.0000, 0.0000] | no detectable difference |
| hit@k | 0.9750 | 0.8750 | | | |
| evidence_recall@k | 0.9167 | 0.8042 | | | |
| answer_rate | — | — | | | |
| abstention_precision | — | — | | | |
| abstention_recall | — | — | | | |
| citation_validity | — | — | | | |
| latency_p50_ms | 6 | 7 | | | |
| latency_p95_ms | 9 | 11 | | | |

## Cases

improved: 1 · regressed: 5 · stable pass: 34 · stable fail: 0 · not comparable: 0

| tag | n | improved | regressed | baseline acc | candidate acc |
|---|---|---|---|---|---|
| exact_term | 20 | 0 | 0 | 1.000 | 1.000 |
| natural | 20 | 1 | 5 | 0.950 | 0.750 |

### ▼ Regressed (5)

- **q017** [natural] How long does an access credential stay usable after it is issued? — reason: `retrieval_lost`
  - baseline: (retrieval_only) · judge: —
  - candidate: (retrieval_only) · judge: —
- **q036** [natural] By how much did the time for a robot to get back online after roaming between access points drop in late February 2026? — reason: `retrieval_lost`
  - baseline: (retrieval_only) · judge: —
  - candidate: (retrieval_only) · judge: —
- **q040** [natural] How many days in a typical week can I do my job from my own house? — reason: `retrieval_lost`
  - baseline: (retrieval_only) · judge: —
  - candidate: (retrieval_only) · judge: —
- **q045** [natural] At what battery level does a robot go to recharge on its own initiative? — reason: `retrieval_lost`
  - baseline: (retrieval_only) · judge: —
  - candidate: (retrieval_only) · judge: —
- **q052** [natural] Are employees made to change their logins on a calendar basis? — reason: `retrieval_lost`
  - baseline: (retrieval_only) · judge: —
  - candidate: (retrieval_only) · judge: —

### ▲ Improved (1)

- **q013** [natural] What is the recommended safeguard against problems that build up slowly over days? — reason: `retrieval_gained`
  - baseline: (retrieval_only) · judge: —
  - candidate: (retrieval_only) · judge: —
