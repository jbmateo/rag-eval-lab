# Compare: model-sweep:model=claude-sonnet-5-5 → baseline:base

Baseline `570cb6f27c3d` (complete) · Candidate `16143ca4e352` (complete)

## What changed

| setting | baseline | candidate |
|---|---|---|
| model | claude-sonnet-5-5 | claude-haiku-5-5 |

System rag-studio@e97f4e8 → rag-studio@e97f4e8 · dataset lumen@v1 → lumen@v1 · judge claude-haiku-5-5 → claude-haiku-5-5

## Summary

60 paired cases · McNemar p = 0.727 · minimum detectable change ≈ +13.2 pts

| metric | baseline | candidate | Δ | 95% CI | verdict |
|---|---|---|---|---|---|
| accuracy | 0.8833 | 0.9167 | 0.0333 | [-0.0500, 0.1167] | no detectable difference |
| mrr | 0.7159 | 0.7159 | 0.0000 | [0.0000, 0.0000] | no detectable difference |
| latency_ms | 2634.0351 | 2506.6140 | -127.4211 | [-510.5965, 278.1579] | no detectable difference |
| cost_per_case | 0.0109 | 0.0006 | -0.0103 | [-0.0106, -0.0100] | better |
| hit@k | 0.9750 | 0.9750 | | | |
| evidence_recall@k | 0.9167 | 0.9167 | | | |
| answer_rate | 1.0000 | 1.0000 | | | |
| abstention_precision | 1.0000 | 1.0000 | | | |
| abstention_recall | 0.9500 | 1.0000 | | | |
| citation_validity | 1.0000 | 1.0000 | | | |
| latency_p50_ms | 2348 | 2324 | | | |
| latency_p95_ms | 4971 | 5960 | | | |

## Cases

improved: 5 · regressed: 3 · stable pass: 50 · stable fail: 2 · not comparable: 0

| tag | n | improved | regressed | baseline acc | candidate acc |
|---|---|---|---|---|---|
| exact_term | 20 | 3 | 1 | 0.850 | 0.950 |
| natural | 20 | 1 | 2 | 0.850 | 0.800 |
| unanswerable | 20 | 1 | 0 | 0.950 | 1.000 |

### ▼ Regressed (3)

- **q020** [exact_term] If my company laptop is stolen on a trip, how quickly must I report it by email to security@lumenrobotics.example, and who signs off on a replacement? — reason: `unsupported_claims`
  - baseline: You must report a lost or stolen device within 2 hours of noticing, either by email to security@lumenrobotics.example or through the 24 hour security hotline. A replacement for a stolen laptop needs the approval of your director, who will usually ask for the police report number before ordering. · judge: The answer correctly states the 2-hour reporting deadline by email to security@lumenrobotics.example and that the director approves replacements, both supported by P1 and P2. The added details about the 24-hour hotline and police report number are also stated in the cited passages.
  - candidate: If a company laptop is lost or stolen, you must report it within 2 hours of noticing, by email to security@lumenrobotics.example or through the 24 hour security hotline. You should also follow the security policy procedure and inform your manager. A replacement for a stolen laptop needs the approval of your director, who will usually ask for the police report number before ordering. Reporting late is treated as a policy violation, and the security team will lock and wipe the device remotely after the report. · judge: The answer correctly states the 2-hour email report deadline to security@lumenrobotics.example and that the director approves replacements, both supported by the passages. The claim that the director 'will usually ask for the police report number' is in P2, and the remote lock/wipe and late-report violation are in P1; the only unsupported element is the claim that the 24-hour hotline is an alternative, which is actually in P1, so it is supported; the answer's claim that the report can be made 'through the 24 hour security hotline' is supported, leaving the 'inform your manager' and 'follow policy' points supported by P2 as well, so one minor unsupported detail remains in the framing of 'noticing' being exact wording rather than a claim, counted conservatively as one.
- **q036** [natural] By how much did the time for a robot to get back online after roaming between access points drop in late February 2026? — reason: `unsupported_claims`
  - baseline: In release v3.3.1, dated 2026-02-24, the median time for a robot to reconnect after a Wi-Fi roam fell from 14 seconds to 6 seconds. That is a drop of 8 seconds. · judge: The answer correctly states the median reconnect time after a Wi-Fi roam fell from 14 to 6 seconds in the 2026-02-24 release, and the 8-second drop is a direct arithmetic consequence. Both claims are supported by the cited passage P1.
  - candidate: In release v3.3.1, released 2026-02-24, the median time for a robot to reconnect after a Wi-Fi roam fell from 14 seconds to 6 seconds, a reduction of 8 seconds. · judge: The answer correctly states the drop from 14 to 6 seconds (8 seconds) in v3.3.1 released 2026-02-24, matching the gold evidence and P1. The label 'v3.3.1' is not stated in the passages shown, which only give a release date and no version number, so that is one unsupported claim.
- **q044** [natural] What is the longest route I can submit as a single task before it gets turned down? — reason: `unsupported_claims`
  - baseline: A single mission can contain at most 256 waypoints, so 256 waypoints is the longest route you can submit as one mission. A body that exceeds this limit is rejected with error code E-4472 and HTTP status 422. The limit was raised from 128 to 256 in v3.4.0. For longer routes, split them into several missions chained with the follow_up field. · judge: The answer correctly states the 256-waypoint limit per mission, matching the gold evidence and api-reference passage. The additional claims (E-4472, HTTP 422, raise from 128 in v3.4.0, follow_up chaining) are all stated in the cited passages; the release notes version label is not explicitly stated but the release note itself is dated and the version is not contradicted, so no unsupported claims are counted.
  - candidate: A mission may contain at most 256 waypoints. A request body that exceeds this limit is rejected with error code E-4472 and HTTP status 422. This limit was raised from 128 to 256 waypoints in release v3.4.0. Longer routes can be split into several missions that are chained with the follow_up field. · judge: The answer correctly states the 256-waypoint limit per mission, matching the gold evidence. The claim that the limit was raised in release v3.4.0 is not supported by the cited passages, which give the release date 2026-05-12 but no version number; the other claims (E-4472, HTTP 422, follow_up) are supported.

### ▲ Improved (5)

- **q006** [exact_term] What did change LUM-4560 introduce? — reason: `unsupported_claims`
  - baseline: LUM-4560 introduced a limit of 20 commands per minute per robot on POST /robots/{id}/commands. Requests above that limit are rejected with E-4290. It was part of release v3.3.0. · judge: The answer correctly states the 20 commands per minute per robot limit on POST /robots/{id}/commands and the E-4290 rejection, both matching the gold evidence and cited passage. The claim that it was part of release v3.3.0 is not stated in the passages; v3.3.0 appears only as the LR7-S1 requirement, so that claim is unsupported.
  - candidate: LUM-4560 introduced a limit of 20 commands per minute per robot on POST /robots/{id}/commands. Requests above this limit are rejected with E-4290. · judge: The answer correctly states LUM-4560 introduced a limit of 20 commands per minute per robot on POST /robots/{id}/commands, and the cited passage explicitly says requests above the limit are rejected with E-4290 under LUM-4560.
- **q012** [exact_term] What does error code E-4471 mean? — reason: `unsupported_claims`
  - baseline: E-4471 means that the target robot is offline, and it is returned with HTTP status 409. It is raised when a command is sent to a robot that is not connected to the fleet service, and it is described as the most common error in production. Before retrying, you should check the robot status with GET /robots/{id}. · judge: The answer correctly states E-4471 means the target robot is offline with HTTP 409, matching the gold evidence and P1. Claim 2 (raised when robot not connected to fleet service, most common error in production) is supported by P2, and claim 3 (check robot status with GET /robots/{id} before retrying) is also supported by P2; however, the statement that it is 'the most common error in production' is supported, so the only unsupported element is minor elaboration, counted as one.
  - candidate: Error code E-4471 means that the target robot is offline, and its HTTP status is 409. It is returned when the target robot is not connected to the fleet service, and the command is rejected. Before retrying, check the robot status with GET /robots/{id}. · judge: The answer correctly states E-4471 means the target robot is offline with HTTP 409, matching the gold evidence and passages. Its claims about the robot not being connected, the command being rejected, and checking GET /robots/{id} before retrying are all stated in the cited passage.
- **q017** [natural] How long does an access credential stay usable after it is issued? — reason: `judge_correct`
  - baseline: An API bearer token for the Lumen Fleet API is valid for 3600 seconds after it is issued, and a new token must be sent before the old one expires. A privileged session for production systems expires after 8 hours. Client secrets for the Lumen Fleet API must be rotated every 180 days, and after a rotation the old secret keeps working for 15 minutes. · judge: The answer correctly states the API bearer token lifetime of 3600 seconds, but it also adds claims about privileged sessions and client secret rotation that are not what the question asks about; the first part is correct and grounded, but the partial-answer framing is acceptable only if the missing part is absent, which it is not claimed to be fully. The gold evidence focuses on the token lifetime, and the answer's added items are supported by passages, so the main issue is that the answer is framed as partial while its core statement is right; judged on the core answer it is correct.
  - candidate: A bearer token issued through the Lumen Fleet API is valid for 3600 seconds after it is issued. · judge: The answer states the bearer token is valid for 3600 seconds after issuance, which matches the gold evidence and cited passage P1. It makes no additional unsupported claims.
- **q023** [exact_term] Which release fixed the defect behind INC-20260314-07, and what was the defect? — reason: `judge_correct`
  - baseline: The defect behind INC-20260314-07 was fixed in the hotfix released on 2026-03-19, which is listed in the release notes between v3.4.0 and v3.3.2 and is described as a hotfix for the dispatch outage in INC-20260314-07. The defect was a connection pool leak in the dispatch service that was introduced in v3.3.1. Connections that timed out while a robot was switching access points were not returned to the pool, so the pool slowly shrank. The leak came from a refactoring of the reconnect logic in v3.3.1, shipped on 24 February 2026. The fix makes connections that time out while a robot switches access points get returned to the pool (LUM-4851). · judge: The answer correctly identifies the 2026-03-19 hotfix, the connection pool leak introduced in v3.3.1, its cause, and the LUM-4851 fix, but the claim that the hotfix is 'listed between v3.4.0 and v3.3.2' is not stated in the cited passages (the hotfix is labeled as v3.3.2 in gold evidence, and the passage does not mention v3.4.0 ordering). Also, the gold says the hotfix shipped as v3.3.2, and the answer never names the release version v3.3.2 as the fix, omitting the key answer to 'which release'.
  - candidate: The defect was fixed in a hotfix released 2026-03-19, which is listed in the v3.3.2 section of the release notes, and it was a hotfix for the dispatch outage described in INC-20260314-07. The defect was a connection pool leak in the dispatch service, introduced in v3.3.1. Connections that timed out while a robot was switching access points were not returned to the pool, so the pool slowly shrank. The hotfix changed the service so that connections that time out while a robot switches access points are returned to the pool. · judge: The answer correctly identifies the hotfix released 2026-03-19 in v3.3.2 as the fix for INC-20260314-07 and accurately describes the connection pool leak introduced in v3.3.1 and its mechanism, all supported by the cited passages.
- **q056** [unanswerable] What service credits were offered to customers affected by the March 14 outage? — reason: `correctly_abstained`
  - baseline: The postmortem states that customers received no financial penalties from Lumen automatically, and that the commercial follow up was handled by the account team outside of the postmortem document. · judge: The gold evidence is empty, so the answer cannot be shown to state what the gold says about service credits. The answer's claim that no automatic financial penalties were given and that the account team handled follow-up is supported by passage P1, but it does not identify any service credits offered and marks itself as partial with no gold basis to confirm the missing part is absent.
  - candidate: (abstained) · judge: —

<details><summary>Stable fail (2)</summary>

q013, q016

</details>
