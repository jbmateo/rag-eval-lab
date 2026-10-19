# Compare: rq1-retrieval:retrieval_mode=bm25 → rq1-retrieval:retrieval_mode=hybrid

Baseline `429bf0f0e4eb` (complete) · Candidate `db4ac97e819d` (complete)

## What changed

| setting | baseline | candidate |
|---|---|---|
| retrieval_mode | bm25 | hybrid |

System rag-studio@e97f4e8 → rag-studio@e97f4e8 · dataset lumen@v1 → lumen@v1 · judge none → none

## Summary

40 paired cases · McNemar p = 0.125 · minimum detectable change ≈ +14.0 pts

| metric | baseline | candidate | Δ | 95% CI | verdict |
|---|---|---|---|---|---|
| accuracy | 0.8750 | 0.9750 | 0.1000 | [0.0250, 0.2000] | better |
| mrr | 0.7021 | 0.7159 | 0.0138 | [-0.0885, 0.1184] | no detectable difference |
| latency_ms | 1.5000 | 6.8500 | 5.3500 | [4.9750, 5.7500] | worse |
| cost_per_case | 0.0000 | 0.0000 | 0.0000 | [0.0000, 0.0000] | no detectable difference |
| hit@k | 0.8750 | 0.9750 | | | |
| evidence_recall@k | 0.8292 | 0.9167 | | | |
| answer_rate | — | — | | | |
| abstention_precision | — | — | | | |
| abstention_recall | — | — | | | |
| citation_validity | — | — | | | |
| latency_p50_ms | 1 | 6 | | | |
| latency_p95_ms | 2 | 9 | | | |

## Cases

improved: 4 · regressed: 0 · stable pass: 35 · stable fail: 1 · not comparable: 0

| tag | n | improved | regressed | baseline acc | candidate acc |
|---|---|---|---|---|---|
| exact_term | 20 | 0 | 0 | 1.000 | 1.000 |
| natural | 20 | 4 | 0 | 0.750 | 0.950 |

### ▲ Improved (4)

- **q005** [natural] How long can I keep using an old API generation after a newer one arrives? — reason: `retrieval_gained`
  - baseline: (retrieval_only) · judge: —
  - candidate: (retrieval_only) · judge: —
- **q025** [natural] Which robot in the family is meant for cramped passages between shelving? — reason: `retrieval_gained`
  - baseline: (retrieval_only) · judge: —
  - candidate: (retrieval_only) · judge: —
- **q045** [natural] At what battery level does a robot go to recharge on its own initiative? — reason: `retrieval_gained`
  - baseline: (retrieval_only) · judge: —
  - candidate: (retrieval_only) · judge: —
- **q054** [natural] Why did responders not just reboot the failing service as soon as they understood what was wrong? — reason: `retrieval_gained`
  - baseline: (retrieval_only) · judge: —
  - candidate: (retrieval_only) · judge: —

<details><summary>Stable fail (1)</summary>

q013

</details>
