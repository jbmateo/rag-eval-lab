# Compare: baseline:base → prompt-sweep:prompt_variant=terse_cite_all

Baseline `16143ca4e352` (complete) · Candidate `a2929ae19eee` (complete)

## What changed

| setting | baseline | candidate |
|---|---|---|
| prompt_variant | default | terse_cite_all |

System rag-studio@e97f4e8 → rag-studio@e97f4e8 · dataset lumen@v1 → lumen@v1 · judge claude-haiku-5-5 → claude-haiku-5-5

## Summary

60 paired cases · McNemar p = 1.000 · minimum detectable change ≈ +8.1 pts

| metric | baseline | candidate | Δ | 95% CI | verdict |
|---|---|---|---|---|---|
| accuracy | 0.9167 | 0.9333 | 0.0167 | [-0.0333, 0.0833] | no detectable difference |
| mrr | 0.7159 | 0.7159 | 0.0000 | [0.0000, 0.0000] | no detectable difference |
| latency_ms | 2506.6140 | 2101.6316 | -404.9825 | [-707.9649, -127.4035] | better |
| cost_per_case | 0.0006 | 0.0006 | -0.0000 | [-0.0000, -0.0000] | better |
| hit@k | 0.9750 | 0.9750 | | | |
| evidence_recall@k | 0.9167 | 0.9167 | | | |
| answer_rate | 1.0000 | 1.0000 | | | |
| abstention_precision | 1.0000 | 1.0000 | | | |
| abstention_recall | 1.0000 | 1.0000 | | | |
| citation_validity | 1.0000 | 1.0000 | | | |
| latency_p50_ms | 2324 | 1880 | | | |
| latency_p95_ms | 5960 | 2966 | | | |

## Cases

improved: 2 · regressed: 1 · stable pass: 54 · stable fail: 3 · not comparable: 0

| tag | n | improved | regressed | baseline acc | candidate acc |
|---|---|---|---|---|---|
| exact_term | 20 | 1 | 1 | 0.950 | 0.950 |
| natural | 20 | 1 | 0 | 0.800 | 0.850 |
| unanswerable | 20 | 0 | 0 | 1.000 | 1.000 |

### ▼ Regressed (1)

- **q012** [exact_term] What does error code E-4471 mean? — reason: `judge_incorrect`
  - baseline: Error code E-4471 means that the target robot is offline, and its HTTP status is 409. It is returned when the target robot is not connected to the fleet service, and the command is rejected. Before retrying, check the robot status with GET /robots/{id}. · judge: The answer correctly states E-4471 means the target robot is offline with HTTP 409, matching the gold evidence and passages. Its claims about the robot not being connected, the command being rejected, and checking GET /robots/{id} before retrying are all stated in the cited passage.
  - candidate: E-4471 means that the target robot is offline. The HTTP status for E-4471 is 409. A command is rejected with E-4471 when the target robot is not connected to the fleet service. · judge: Claim 1 (target robot is offline) is supported by P1 and partly matches the gold's implication, but claim 3 correctly describes the rejection condition, and claim 2 (HTTP 409) is correct; however, the answer's claim that E-4471 means the robot is offline is stated in P1 as well, so the answer's content is accurate. Overall the answer states what the cited passages say, so it is correct.

### ▲ Improved (2)

- **q020** [exact_term] If my company laptop is stolen on a trip, how quickly must I report it by email to security@lumenrobotics.example, and who signs off on a replacement? — reason: `unsupported_claims`
  - baseline: If a company laptop is lost or stolen, you must report it within 2 hours of noticing, by email to security@lumenrobotics.example or through the 24 hour security hotline. You should also follow the security policy procedure and inform your manager. A replacement for a stolen laptop needs the approval of your director, who will usually ask for the police report number before ordering. Reporting late is treated as a policy violation, and the security team will lock and wipe the device remotely after the report. · judge: The answer correctly states the 2-hour email report deadline to security@lumenrobotics.example and that the director approves replacements, both supported by the passages. The claim that the director 'will usually ask for the police report number' is in P2, and the remote lock/wipe and late-report violation are in P1; the only unsupported element is the claim that the 24-hour hotline is an alternative, which is actually in P1, so it is supported; the answer's claim that the report can be made 'through the 24 hour security hotline' is supported, leaving the 'inform your manager' and 'follow policy' points supported by P2 as well, so one minor unsupported detail remains in the framing of 'noticing' being exact wording rather than a claim, counted conservatively as one.
  - candidate: A lost or stolen device must be reported within 2 hours of noticing it, by email to security@lumenrobotics.example or through the 24 hour security hotline. A replacement for a stolen laptop needs the approval of your director. You must also inform your manager if a device is lost or stolen. · judge: The answer correctly states the 2-hour email reporting requirement to security@lumenrobotics.example and that the director approves a stolen laptop replacement, both supported by the cited passages. The additional claims about the 24-hour hotline and informing the manager are also stated in P1 and P2 respectively, so no unsupported claims remain.
- **q036** [natural] By how much did the time for a robot to get back online after roaming between access points drop in late February 2026? — reason: `unsupported_claims`
  - baseline: In release v3.3.1, released 2026-02-24, the median time for a robot to reconnect after a Wi-Fi roam fell from 14 seconds to 6 seconds, a reduction of 8 seconds. · judge: The answer correctly states the drop from 14 to 6 seconds (8 seconds) in v3.3.1 released 2026-02-24, matching the gold evidence and P1. The label 'v3.3.1' is not stated in the passages shown, which only give a release date and no version number, so that is one unsupported claim.
  - candidate: The median time for a robot to reconnect after a Wi-Fi roam fell from 14 seconds to 6 seconds in the v3.3.1 release. That is a drop of 8 seconds. · judge: The answer correctly states the median reconnect time fell from 14 to 6 seconds, as in cited passage P1 and the gold evidence, and the 8-second drop is the direct arithmetic difference. The release is v3.3.1 dated 2026-02-24, though the cited passage does not name the version explicitly; the release date is late February, which matches the question.

<details><summary>Stable fail (3)</summary>

q013, q016, q044

</details>
