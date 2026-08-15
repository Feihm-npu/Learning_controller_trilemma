# Carr victim experiment — summary (FINAL, 2026-08-15)

## Headline
Bounded reward-record poisoning (contrast variant, L∞ per-record δ=2/10, only the
training reward log is writable) destroys post-removal safety transfer on the
third-party Carr et al. AAAI'23 lifecycle, and the causal isolation (amendment
v1.3) shows the damage is LATENT IN THE POLICY BEFORE the authority transition:

**Shield-on-only poisoning** (mutation stops exactly at retirement; subsequent
learning fully clean), obstacle/REINFORCE/sudden, paired seeds:

| seed | clean at-retirement | poisoned at-retirement | clean final | poisoned final |
|---|---|---|---|---|
| 1 | 21.6% | 77.7% (3.6×) | 23.6% | 23.5% (self-heals) |
| 2 | 48.4% | 76.3% (1.6×) | 23.4% | 75.1% (no healing) |
| 3 | 23.9% | 74.8% (3.1×) | 23.3% | 74.1% (no healing) |

- 3/3 seeds: the raw policy is already significantly more dangerous AT the
  retirement instant (evaluate/freeze-at-retirement; 1000-episode eval) — the
  vulnerability is created inside the protected phase and masked by the shield.
- 2/3 seeds: even 4000 episodes of fully-clean post-retirement learning cannot
  repair the damage; 1/3 (s1) self-heals — a susceptibility/repair heterogeneity.
- Mechanism signal: unmasked raw-policy/shield disagreement during the protected
  phase stays 2-3% for clean but rises to 6-15% (peak 71%) under poisoning, while
  physical violations remain 0 — the shielded operation masks unsafe proposals
  that become physical failures at authority removal.

Original full-phase and REINFORCE/PPO results:
- REINFORCE seed 2: post-removal violations 1127 → 3762 (δ=2) / 3766 (δ=10);
  McNemar exact p≈0; first-violation episode 6 → 0; shield-disagreement 0.013 → 0.105.
- PPO seed 2: 1178 → 2439 (δ=2); p=2.6e-149; first-violation 6 → 0; disagreement
  0.025 → 0.047.
- REINFORCE δ=10 also raises seed 3: 2471 → 3700 (p=8.4e-138).
- Negative boundaries (honest): seeds with poor clean transfer (REINFORCE s1 75.7%,
  PPO s1 49%) show no attack effect; V1 bias and V2 risk variants do not raise
  violations (V2 even protective — absorbed by value baseline + return
  normalization); PPO s3 unchanged at δ=2.

## Interpretation for the paper
Protected phase (shield active) is violation-free in every run. The damage is latent
and materializes only after the authority transition — on the exact lifecycle the
paper targets (shield bootstrap → retirement), with two learner families. The
per-seed boundary is the honest multi-seed result: the vulnerability is real,
paired and significant, but not universal; the attack is not a trivial reward
degradation (bias/risk controls).

## 1. What was built
Official Carr et al. AAAI'23 pipeline (safe_RL_POMDPs + gridstorm) vendored and patched
minimally (seeds, reward-poison hook, metrics) — see ../patches.md. Runs on this Mac
(Apple Silicon, TF 2.15.1 + tf-agents 0.19 + stormpy 1.11.3, Python 3.10.12 venv).

## 2. Fidelity gate (obstacle, REINFORCE, 5000 eps, seed 1) — PASSED
| condition | during | after |
|---|---|---|
| no-shield | 3798 | 3784 |
| shield retained | 0 | 0 |
| sudden | 3277 | 3784 |
| smooth | 326 | 675 |
Ordering reproduces paper Tab. 1 (shield < smooth ≪ sudden ≤ no-shield).

## 3. Attack (reward-record mutation only, |ξ|≤δ, L∞ per record; sudden retirement)
- V3 contrast (risk-adjacent +δ, safe −δ) destroys post-removal safety transfer on the
  transfer-sensitive seed 2 in BOTH learners:
  - REINFORCE: 1127 → 3762 (δ=2, 3.3×), 1127 → 3766 (δ=10); McNemar exact p≈0;
    first-violation episode 6 → 0; shield-disagreement 0.013 → 0.105.
  - PPO: 1178 → 2439 (δ=2, 2.1×); first-violation 6 → 0.
- Seed 1 (clean baseline already poor post-removal: REINFORCE 76%, PPO 49%) shows no
  attack effect; seed 3 REINFORCE δ=2 no effect, δ=10 +50%.
- V1 bias / V2 risk: no attack effect (V2 even protective — absorbed by value
  baseline/return normalization; honest negative control).

## 4. Interpretation
The protected phase (episodes 0-999, shield active) is violation-free in every run
(shield construction + retained-shield control 0/5000). The attack's damage is latent:
it shows only after the authority transition, on seeds where clean learning transfers
safety to the released policy. This is exactly the paper's "assurance inheritance
across an authority transition under compromised update provenance" claim, now on a
third-party lifecycle (Carr et al. workflow) with a modern learner (PPO) and
REINFORCE.

## 5. Files
- aggregate_table.csv, figures/fig1-3 (baseline bars; per-seed clean-vs-poisoned with
  first-violation labels; cumulative violation curves)
- REINFORCE_stage_report.md; per-run dirs with summary.json + eval_trace.npy
