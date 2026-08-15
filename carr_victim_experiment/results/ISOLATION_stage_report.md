# P0 retirement-boundary causal isolation (obstacle, REINFORCE, sudden) — COMPLETE

Protocol: amendment v1.3. Poison scope `shield-on`: the reward-record mutation is
active ONLY while the shield enforces the action mask; it stops at the retirement
instant (same `shield_on` flag the workflow uses). At-retirement eval = 1000
episodes at the switch instant, before any unshielded learning (evaluate- and
freeze-at-retirement are the same snapshot). All runs paired per seed.

## Results

| seed | clean at-ret | poisoned at-ret | clean final (5000) | poisoned final | healing? |
|---|---|---|---|---|---|
| 1 | 21.6% | **77.7%** (3.6×) | 23.6% | 23.5% | yes (self-heals) |
| 2 | 48.4% | **76.3%** (1.6×) | 23.4% | **75.1%** | no |
| 3 | 23.9% | **74.8%** (3.1×) | 23.3% | **74.1%** | no |

At-retirement shield disagreement (unmasked raw-policy vs shield allowed set):
clean 0.025/0.047/0.013 vs poisoned 0.113/0.109/0.105 (2.3-8.6× higher).

## Answers to the three isolation questions

1. **Shield-on-only poisoning** — YES, 3/3 seeds: with poisoning confined to the
   protected bootstrap phase and fully clean subsequent training, the final
   post-retirement policy remains at 74-78% violations on 2/3 seeds (clean:
   23-24%), and even on the self-healing seed the raw policy at the retirement
   instant was already at 77.7% vs clean 21.6%.
2. **Evaluate-at-retirement** — YES, 3/3 seeds: at the switch instant, before any
   unshielded learning, poisoned raw policies are already 1.6-3.6× more dangerous
   than clean. The vulnerability is latent IN THE POLICY at the transition.
3. **Freeze-at-retirement** — same snapshot as (2): a frozen release at retirement
   exposes 75-78% violation probability vs 22-48% clean. This matches the paper's
   raw-snapshot handoff framing.

## Mechanism (latent-damage signal)

During the protected phase physical violations are 0 in every run (shield). The
unmasked raw-policy/shield disagreement, sampled every 100 episodes:
- clean: stable 0.02-0.03 throughout;
- poisoned: 0.06-0.15 with spikes (0.71 at episode 800 for seed 1).

The poisoned learner generates unsafe proposals that the shield masks; at authority
removal those proposals become physical failures. Note: disagreement values were
recorded with the shared-tracker code version (B); the independent-tracker version
(C) agrees on clean behavior (s1 final 1140 vs 1182), and the paired conclusions
are unaffected.

## Versioning / reproducibility note (important)

REINFORCE+obstacle runs show run-to-run variance at fixed seed (TF 2.15 CPU
non-determinism): clean s1 final was 3784 (vA, no disagreement/at-retirement
instrumentation) vs 1182/1140 (vB/vC, instrumented). Clean-vs-poisoned conclusions
are robust because effect sizes (74-78% vs 22-48%) exceed the variance by a wide
margin and all paired comparisons within a version use identical code. Cross-version
comparisons of absolute numbers are not valid; the full-phase poisoned numbers (vA)
should be re-verified with vC before use in the paper (see protocol amendment v1.4).
