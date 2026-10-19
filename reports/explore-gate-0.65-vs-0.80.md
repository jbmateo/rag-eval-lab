# Compare: gate-sweep-high:min_similarity=0.65 → gate-sweep-high:min_similarity=0.8

Baseline `dcb733ac9216` (complete) · Candidate `161961debcfa` (complete)

## What changed

| setting | baseline | candidate |
|---|---|---|
| min_similarity | 0.650 | 0.800 |

System rag-studio@e97f4e8 → rag-studio@e97f4e8 · dataset lumen@v1 → lumen@v1 · judge claude-haiku-5-5 → claude-haiku-5-5

## Summary

60 paired cases · McNemar p = 0.000 · minimum detectable change ≈ +16.8 pts

| metric | baseline | candidate | Δ | 95% CI | verdict |
|---|---|---|---|---|---|
| accuracy | 0.9167 | 0.7000 | -0.2167 | [-0.3333, -0.1167] | worse |
| mrr | 0.7159 | 0.7159 | 0.0000 | [0.0000, 0.0000] | no detectable difference |
| latency_ms | 6.0000 | 7.5000 | 1.5000 | [1.0000, 2.0000] | worse |
| cost_per_case | 0.0006 | 0.0004 | -0.0002 | [-0.0003, -0.0001] | better |
| hit@k | 0.9750 | 0.9750 | | | |
| evidence_recall@k | 0.9167 | 0.9167 | | | |
| answer_rate | 0.9750 | 0.5750 | | | |
| abstention_precision | 0.9524 | 0.5405 | | | |
| abstention_recall | 1.0000 | 1.0000 | | | |
| citation_validity | 1.0000 | 1.0000 | | | |
| latency_p50_ms | 5 | 9 | | | |
| latency_p95_ms | 7 | 19 | | | |

## Cases

improved: 0 · regressed: 13 · stable pass: 42 · stable fail: 5 · not comparable: 0

| tag | n | improved | regressed | baseline acc | candidate acc |
|---|---|---|---|---|---|
| exact_term | 20 | 0 | 1 | 0.950 | 0.900 |
| natural | 20 | 0 | 12 | 0.800 | 0.200 |
| unanswerable | 20 | 0 | 0 | 1.000 | 1.000 |

### ▼ Regressed (13)

- **q005** [natural] How long can I keep using an old API generation after a newer one arrives? — reason: `wrongly_abstained`
  - baseline: API version 2 became generally available on 2025-11-04, and version 1 remains supported until 2026-11-04. Version 1 is deprecated and will be switched off on 2026-11-04, which is twelve months after v2 became available. The general rule is that breaking changes are introduced only in a new major version, and the previous major version is supported for 12 months after the new one is released. · judge: The answer correctly states the general rule that the previous major version is supported for 12 months after the new one is released, which matches the gold evidence. The specific dates (2025-11-04 GA, 2026-11-04 end of support) are stated in the cited passages P1 and P2, so the answer's additional claims are supported.
  - candidate: (abstained) · judge: —
- **q008** [natural] How much advance warning does either side have to give when ending a job during the initial trial months? — reason: `wrongly_abstained`
  - baseline: The probation period for new employees is 6 months. During probation either side may end the employment with one month of notice. · judge: The answer correctly states that during probation either side may end employment with one month of notice, matching the gold evidence. The additional 6-month probation claim is directly stated in the cited passage P1.
  - candidate: (abstained) · judge: —
- **q011** [exact_term] From what moment does the 72 hour regulator notification clock start? — reason: `wrongly_abstained`
  - baseline: The 72 hour regulator notification clock starts at the moment the company becomes aware of a confirmed personal data breach. · judge: The answer correctly states the 72-hour regulator notification clock starts when the company becomes aware of a confirmed personal data breach, which matches the gold evidence and cited passage P1.
  - candidate: (abstained) · judge: —
- **q017** [natural] How long does an access credential stay usable after it is issued? — reason: `wrongly_abstained`
  - baseline: A bearer token issued through the Lumen Fleet API is valid for 3600 seconds after it is issued. · judge: The answer states the bearer token is valid for 3600 seconds after issuance, which matches the gold evidence and cited passage P1. It makes no additional unsupported claims.
  - candidate: (abstained) · judge: —
- **q018** [natural] For how long was work assignment halted for the Dutch deployment on that Saturday? — reason: `wrongly_abstained`
  - baseline: On Saturday 14 March 2026, the fleet dispatch service stopped assigning work to robots in the Rotterdam region for 1 hour and 53 minutes. The total duration from the first alert to restoration was 1 hour and 53 minutes. · judge: The answer correctly states the 1 hour and 53 minute duration for the Saturday 14 March 2026 halt in Rotterdam, matching the gold evidence and cited passages; both claims are directly stated in P1 and P2.
  - candidate: (abstained) · judge: —
- **q024** [natural] How fast must the most severe security holes be patched? — reason: `wrongly_abstained`
  - baseline: Critical vulnerabilities must be fixed within 7 days. · judge: The answer correctly states that critical vulnerabilities must be fixed within 7 days, which matches both the gold evidence and cited passage P1.
  - candidate: (abstained) · judge: —
- **q025** [natural] Which robot in the family is meant for cramped passages between shelving? — reason: `wrongly_abstained`
  - baseline: The LR7-S1 is the compact model of the LR7 family, intended for narrow aisles. The LR7-S1 fits through aisles as narrow as 900 mm, while the LR7-X2 requires at least 1,300 mm for turning. · judge: The answer correctly identifies the LR7-S1 as the compact model for narrow aisles, matching the gold evidence. The additional claims about 900 mm and 1,300 mm aisle widths are directly stated in the cited passage P1 and do not contradict the gold.
  - candidate: (abstained) · judge: —
- **q034** [natural] If my server is unreachable when an event notification is sent, how many times will the platform try again? — reason: `wrongly_abstained`
  - baseline: If delivery to your endpoint fails, the service retries up to 6 times with exponential backoff, starting at 30 seconds and doubling after each attempt. After the sixth failed attempt the event is dropped and the webhook is marked as degraded in the console. · judge: The answer correctly states the service retries up to 6 times with exponential backoff starting at 30 seconds, which matches the gold evidence. The additional claims about dropping the event and marking the webhook degraded are stated in cited passage P1.
  - candidate: (abstained) · judge: —
- **q040** [natural] How many days in a typical week can I do my job from my own house? — reason: `wrongly_abstained`
  - baseline: Employees whose role allows it may work from home up to 3 days per week. The days are agreed at team level, and teams are asked to keep at least one common office day each week. Roles that touch physical robots, such as the test hall and field service, are on site by default. · judge: The answer's core claim, that eligible employees may work from home up to 3 days per week, matches the gold evidence and the cited passage. The other two points (team-agreed days with a common office day, and on-site default for robot-touching roles) are directly stated in the cited passage P1, so they are supported and not unsupported claims.
  - candidate: (abstained) · judge: —
- **q042** [natural] What is the shortest allowed length for a login secret on corporate accounts? — reason: `wrongly_abstained`
  - baseline: Passwords for company accounts must be at least 14 characters long. · judge: The answer states that company account passwords must be at least 14 characters, which matches the gold evidence and is directly stated in cited passage P1. The question asks for the shortest allowed length, and the answer provides it.
  - candidate: (abstained) · judge: —
- **q054** [natural] Why did responders not just reboot the failing service as soon as they understood what was wrong? — reason: `wrongly_abstained`
  - baseline: At 03:12 the team decided against a simple restart. A restart would have restored service within minutes, but it would also have destroyed the evidence of the leak and risked a repeat within a few days. The incident commander chose to take a heap dump first and then perform a rollback. · judge: The answer correctly states the gold evidence: a restart would restore service quickly but would destroy evidence of the leak and risk repeat; the cited passage P1 supports the 03:12 decision, the incident commander's heap dump then rollback, and the risk of repeat within a few days. All claims are stated in the cited passage.
  - candidate: (abstained) · judge: —
- **q059** [natural] When will the first generation of the programming interface be shut off? — reason: `wrongly_abstained`
  - baseline: API version 1 is deprecated and will be switched off on 2026-11-04. Version 1 remains supported until 2026-11-04. · judge: The answer correctly states that API version 1 will be switched off on 2026-11-04, matching the gold evidence. Both listed claims are stated in the cited passages (P1 and the v3.2.0 release note on version 1 remaining supported until 2026-11-04).
  - candidate: (abstained) · judge: —
- **q060** [natural] How much better did robots get at re-finding their position in the test hall after the June 2026 patch? — reason: `wrongly_abstained`
  - baseline: The v3.4.1 patch, released 2026-06-09, improved relocalisation in large halls with few features, and the success rate in the test hall rose from 91 percent to 98 percent, a gain of 7 percentage points. Robots now request a reflective marker scan after two failed relocalisation attempts. · judge: The answer correctly states the success rate in the test hall rose from 91 to 98 percent, a 7 percentage point gain, which matches the gold evidence and cited passage P1. The reflective marker scan claim is also directly stated in P1 and the patch date and version are supported.
  - candidate: (abstained) · judge: —

<details><summary>Stable fail (5)</summary>

q013, q016, q020, q036, q044

</details>
