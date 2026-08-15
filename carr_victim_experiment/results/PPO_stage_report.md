# PPO stage results (obstacle N=6, official pipeline, 10^5 training steps)

Protocol: protocol.md (amendment v1.1). PPO via the vendored tf-agents PPO agent with
action masking; shield switch at env-step 10^5 (shield_episode=4000 in step units;
≈ "first 1000 episodes" of the REINFORCE protocol). Eval: 5000 episodes.

| seed | poison | δ | during | after | frac | first | disagreement |
|---|---|---|---|---|---|---|---|
| 1 | clean | — | 858 | 2448 | 0.490 | 2 | 0.0470 |
| 1 | contrast | 2 | 835 | 2449 | 0.490 | 0 | 0.0470 |
| 2 | clean | — | 404 | 1178 | 0.236 | 6 | 0.0252 |
| 2 | contrast | 2 | 918 | 2439 | 0.488 | 0 | 0.0472 |
| 3 | clean | — | 511 | 1142 | 0.228 | 0 | 0.0129 |
| 3 | contrast | 2 | 298 | 1139 | 0.228 | 5 | 0.0250 |

Paired tests (McNemar exact, paired eval episodes): s1 p=1.00 (no effect),
s2 p=2.6e-149 (↑2.1×), s3 p=0.96 (no effect).

Reading: the attack effect is confined to transfer-sensitive seeds. On seed 2 —
where the clean policy transfers safety to the released raw policy (23.6%) — the
contrast attack at δ=2 raises post-removal violations ~2.1× (1178 → 2439;
first-violation episode 6 → 0; shield disagreement 0.025 → 0.047). Seeds whose clean
post-removal behavior is already poor (s1: 49%) or whose released policy is not
transfer-sensitive to this attack shape (s3) show no effect. This mirrors the
REINFORCE pattern with a more stable learner and is the honest multi-seed boundary:
the vulnerability is real (paired, p≈1e-149) but seed-dependent, and the attack is
not a trivial "corrupt rewards" effect (bias/risk variants do not raise violations).
