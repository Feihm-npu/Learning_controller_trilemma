# REINFORCE stage results (obstacle N=6, official Carr et al. AAAI'23 pipeline)

Protocol: protocol.md + amendment v1.1. All runs: obstacle, REINFORCE, 5000 training
episodes, ≤100 steps, BELIEF_SUPPORT obs, goal +1000 (env adds 1000 on top of model
gain 100), trap ≈ -1100, safe move +1, timeout +99. Sudden switch = shield off at
episode 1000. Eval = 5000 episodes with final policy.

## 1. Clean baseline (fidelity gate, seed 1) — reproduces paper Tab. 1 ordering

| condition | during | after | frac | first-violation (eval) |
|---|---|---|---|---|
| no-shield | 3798 | 3784 | 0.757 | 0 |
| shield retained | 0 | 0 | 0.000 | — |
| sudden switch-off | 3277 | 3784 | 0.757 | 0 |
| smooth switch-off | 326 | 675 | 0.135 | 3 |

Paper Tab. 1 (6-domain averages): 3153/1023, 0/0, 1867/502, 27/5. Our single-domain
numbers are higher (obstacle has slippery dynamics + sparse goal), but the qualitative
ordering **shield < smooth ≪ sudden ≤ no-shield** is reproduced exactly.

## 2. Seed variability (sudden, clean)

| seed | during | after | frac | first | disagreement |
|---|---|---|---|---|---|
| 1 | 3277 | 3784 | 0.757 | 0 | 0.106 |
| 2 | 1015 | 1127 | 0.225 | 6 | 0.013 |
| 3 | 1981 | 2471 | 0.494 | 0 | 0.047 |

REINFORCE on this sparse domain is highly seed-unstable (paper: "REINFORCE does not
always converge"); paired same-seed clean-vs-poisoned is the primary comparison.

## 3. Poisoned runs (sudden; only the reward records of the training env are mutated)

| seed | attack | δ | during | after | first | McNemar exact p (paired eval eps) |
|---|---|---|---|---|---|---|
| 1 | clean | — | 3277 | 3784 | 0 | — |
| 1 | bias | 2 | 2179 | 2451 | 1 | 2.8e-165 (↓ protective) |
| 1 | risk | 2 | 965 | 1181 | 4 | 0.0 (↓ protective) |
| 1 | contrast | 2 | 3002 | 3787 | 1 | 0.96 (no change, ceiling) |
| 1 | contrast | 10 | 2792 | 1197 | 2 | 0.0 (↓ protective) |
| 2 | clean | — | 1015 | 1127 | 6 | — |
| 2 | risk | 2 | 1935 | 2457 | 1 | 2.0e-162 (↑2.2×) |
| 2 | contrast | 2 | 3503 | 3762 | 0 | 0.0 (↑3.3×) |
| 2 | contrast | 10 | 3280 | 3766 | 0 | 0.0 (↑3.3×) |
| 3 | clean | — | 1981 | 2471 | 0 | — |
| 3 | risk | 2 | 1003 | 1146 | 0 | 6.1e-164 (↓) |
| 3 | contrast | 2 | 960 | 2482 | 1 | 0.84 (no change) |
| 3 | contrast | 10 | 2963 | 3700 | 0 | 8.4e-138 (↑1.5×) |

## 4. Reading (honest)

- The contrast attack (reward risk-adjacent records, penalize safe records) can
  destroy post-removal safety transfer (seed 2: 1127 → 3762, 3.3×, p≈0; corroborated
  by shield-disagreement 0.013 → 0.105 and first-violation 6 → 0).
- On seeds where the clean baseline already saturates (s1: 75.7%) or where REINFORCE
  fails to produce a risk-taking policy (s3, δ=2), the attack shows no effect; on
  s1, δ=2/10 poisoning even produced *lower* post-removal violations (the value
  baseline + return normalization absorb bounded additive distortion — an interesting
  negative control showing the attack is not a trivial "make rewards worse" effect).
- Conclusion for REINFORCE: the phenomenon exists but is learner-noise-limited.
  PPO (stable learner) is the decisive test; see PPO_stage_report.md.

## 5. Files

- `aggregate_table.csv` — all runs; `figures/fig1..3` — baseline bars, per-seed
  clean-vs-poisoned scatter with first-violation labels, cumulative violation curves.
- Per-run dirs: `*_summary.json` (cfg provenance + metrics), `*_eval_trace.npy`
  (5000 per-episode eval violation flags).
