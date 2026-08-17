# P0 retirement-boundary causal isolation (obstacle, REINFORCE, sudden) — provenance-corrected

Protocol: amendment v1.3. Poison scope `shield-on`: the reward-record mutation is
active ONLY while the shield enforces the action mask; it stops at the retirement
instant (same `shield_on` flag the workflow uses). At-retirement eval = 1000
episodes at the switch instant, before any unshielded learning (evaluate- and
freeze-at-retirement are the same snapshot). The table uses only complete
clean/poisoned training pairs.

## Results

| seed | clean at-ret | poisoned at-ret | clean final (5000) | poisoned final | healing? |
|---|---|---|---|---|---|
| 1 | 21.6% | **77.7%** (3.6×) | 23.6% | 23.5% | yes (self-heals) |
| 2 | 48.4% | **76.3%** (1.6×) | 23.4% | **75.1%** | no |
| 3 (fresh pair) | 24.1% | 24.2% (unchanged) | 74.7% | 22.8% | protective final |

At-retirement shield disagreement (unmasked raw-policy vs shield allowed set):
clean 0.025/0.047/0.013 vs poisoned 0.113/0.109/0.025.

## Answers to the three isolation questions

1. **Shield-on-only poisoning** — two of three provenance-complete pairs are
   positive at retirement; the fresh third pair is unchanged despite low clean
   disagreement.  One positive effect persists after fully clean subsequent
   learning.
2. **Evaluate-at-retirement** — the two positive raw policies are already
   1.6-3.6× more dangerous before unshielded learning.  These runs establish
   latent policy damage at the transition; the fresh pair establishes
   within-opportunity-region non-reproduction.
3. **Freeze-at-retirement** — the same snapshots support the raw-release
   comparison, with two positive effects and one null effect.

## Mechanism (latent-damage signal)

During the protected phase physical violations are 0 in every run.  In the two
positive local pairs, clean retirement disagreement is 0.025/0.047 and poisoned
disagreement is 0.113/0.109.  The fresh non-positive pair is also low at
retirement (0.013 clean and 0.025 poisoned).

The poisoned learner generates unsafe proposals that the shield masks; at authority
removal those proposals become physical failures in the positive runs.  The
fresh pair separates this masked-proposal mechanism from reliable attack success.

## Versioning / reproducibility note (important)

REINFORCE+obstacle runs show run-to-run variance at fixed configured seed under
TF 2.15 CPU execution.  The experimental unit is therefore an independently
trained clean/poisoned pair under one locked configuration.  Cross-version or
cross-host absolute values are not paired evidence.  The main table excludes the
local configured-seed-3 poisoned realization because its clean endpoint lacks
valid provenance and substitutes the complete fresh pair for both endpoints.
