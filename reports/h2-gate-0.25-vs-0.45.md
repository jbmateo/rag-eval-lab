# Compare: gate-sweep:min_similarity=0.25 → gate-sweep:min_similarity=0.45

Baseline `accd11b1d02e` (complete) · Candidate `9e5473331e2c` (complete)

## What changed

| setting | baseline | candidate |
|---|---|---|
| min_similarity | 0.250 | 0.450 |

System rag-studio@e97f4e8 → rag-studio@e97f4e8 · dataset lumen@v1 → lumen@v1 · judge claude-haiku-5-5 → claude-haiku-5-5

## Summary

60 paired cases · McNemar p = 1.000 · minimum detectable change ≈ +4.7 pts

| metric | baseline | candidate | Δ | 95% CI | verdict |
|---|---|---|---|---|---|
| accuracy | 0.9167 | 0.9167 | 0.0000 | [0.0000, 0.0000] | no detectable difference |
| mrr | 0.7159 | 0.7159 | 0.0000 | [0.0000, 0.0000] | no detectable difference |
| latency_ms | — | — | — | — | no detectable difference |
| cost_per_case | 0.0006 | 0.0006 | 0.0000 | [0.0000, 0.0000] | no detectable difference |
| hit@k | 0.9750 | 0.9750 | | | |
| evidence_recall@k | 0.9167 | 0.9167 | | | |
| answer_rate | 1.0000 | 1.0000 | | | |
| abstention_precision | 1.0000 | 1.0000 | | | |
| abstention_recall | 1.0000 | 1.0000 | | | |
| citation_validity | 1.0000 | 1.0000 | | | |
| latency_p50_ms | — | — | | | |
| latency_p95_ms | — | — | | | |

## Cases

improved: 0 · regressed: 0 · stable pass: 55 · stable fail: 5 · not comparable: 0

| tag | n | improved | regressed | baseline acc | candidate acc |
|---|---|---|---|---|---|
| exact_term | 20 | 0 | 0 | 0.950 | 0.950 |
| natural | 20 | 0 | 0 | 0.800 | 0.800 |
| unanswerable | 20 | 0 | 0 | 1.000 | 1.000 |

<details><summary>Stable fail (5)</summary>

q013, q016, q020, q036, q044

</details>
