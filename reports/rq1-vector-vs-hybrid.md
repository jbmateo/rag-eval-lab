# Compare: rq1-retrieval:retrieval_mode=vector → rq1-retrieval:retrieval_mode=hybrid

Baseline `85619097d2ac` (complete) · Candidate `db4ac97e819d` (complete)

## What changed

| setting | baseline | candidate |
|---|---|---|
| retrieval_mode | vector | hybrid |

System rag-studio@e97f4e8 → rag-studio@e97f4e8 · dataset lumen@v1 → lumen@v1 · judge none → none

## Summary

40 paired cases · McNemar p = 1.000 · minimum detectable change ≈ +12.1 pts

| metric | baseline | candidate | Δ | 95% CI | verdict |
|---|---|---|---|---|---|
| accuracy | 0.9500 | 0.9750 | 0.0250 | [-0.0500, 0.1250] | no detectable difference |
| mrr | 0.6863 | 0.7159 | 0.0296 | [-0.0500, 0.1125] | no detectable difference |
| latency_ms | 5.3750 | 6.8500 | 1.4750 | [1.2500, 1.7000] | worse |
| cost_per_case | 0.0000 | 0.0000 | 0.0000 | [0.0000, 0.0000] | no detectable difference |
| hit@k | 0.9500 | 0.9750 | | | |
| evidence_recall@k | 0.8958 | 0.9167 | | | |
| answer_rate | — | — | | | |
| abstention_precision | — | — | | | |
| abstention_recall | — | — | | | |
| citation_validity | — | — | | | |
| latency_p50_ms | 5 | 6 | | | |
| latency_p95_ms | 7 | 9 | | | |

## Cases

improved: 2 · regressed: 1 · stable pass: 37 · stable fail: 0 · not comparable: 0

| tag | n | improved | regressed | baseline acc | candidate acc |
|---|---|---|---|---|---|
| exact_term | 20 | 1 | 0 | 0.950 | 1.000 |
| natural | 20 | 1 | 1 | 0.950 | 0.950 |

### ▼ Regressed (1)

- **q013** [natural] What is the recommended safeguard against problems that build up slowly over days? — reason: `retrieval_lost`
  - baseline: (retrieval_only) · judge: —
  - candidate: (retrieval_only) · judge: —

### ▲ Improved (2)

- **q011** [exact_term] From what moment does the 72 hour regulator notification clock start? — reason: `retrieval_gained`
  - baseline: (retrieval_only) · judge: —
  - candidate: (retrieval_only) · judge: —
- **q017** [natural] How long does an access credential stay usable after it is issued? — reason: `retrieval_gained`
  - baseline: (retrieval_only) · judge: —
  - candidate: (retrieval_only) · judge: —
