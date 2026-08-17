# Carr third-party lifecycle experiment — summary (updated 2026-08-17)

## Headline
Bounded reward-record poisoning (contrast variant, L∞ per-record δ=2/10, only the
training reward log is writable) can impair post-removal safety transfer on the
third-party Carr et al. AAAI'23 lifecycle.  Provenance-complete causal-isolation
pairs show both positive and non-positive outcomes at the authority transition:

**Shield-on-only poisoning** (mutation stops exactly at retirement; subsequent
learning fully clean), obstacle/REINFORCE/sudden, paired runs:

| seed | clean at-retirement | poisoned at-retirement | clean final | poisoned final |
|---|---|---|---|---|
| 1 | 21.6% | 77.7% (3.6×) | 23.6% | 23.5% (self-heals) |
| 2 | 48.4% | 76.3% (1.6×) | 23.4% | 75.1% (no healing) |
| 3 (fresh pair) | 24.1% | 24.2% (unchanged) | 74.7% | 22.8% (protective final) |

- Two of three provenance-complete pairs are already more dangerous at the
  retirement instant (1000-episode evaluate/freeze snapshot), establishing
  latent policy damage before unshielded learning in those runs.
- One positive pair remains worse after 4000 fully clean post-retirement
  episodes; the other recovers.  The fresh third pair is unchanged at retirement
  despite low clean disagreement and becomes protective at the final endpoint.
- In the two positive local pairs, disagreement rises from 2.5%/4.7% clean to
  11.3%/10.9% poisoned while physical violations remain zero.  The fresh
  non-positive pair is also low-disagreement (1.3% clean, 2.5% poisoned), so
  low disagreement marks opportunity rather than success.

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
Protected execution is violation-free in every run.  In the positive pairs,
policy damage is present at retirement before unshielded learning.  Across the
larger batteries, the outcome depends on the realized retirement state rather
than nominal seed identity.  Bias/risk controls separate the contrast shape from
generic reward degradation.

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
- V3 contrast (risk-adjacent +δ, safe −δ) impairs post-removal safety transfer in
  the local realization indexed by seed 2 in both learners:
  - REINFORCE: 1127 → 3762 (δ=2, 3.3×), 1127 → 3766 (δ=10); McNemar exact p≈0;
    first-violation episode 6 → 0; shield-disagreement 0.013 → 0.105.
  - PPO: 1178 → 2439 (δ=2, 2.1×); first-violation 6 → 0.
- Seed 1 (clean baseline already poor post-removal: REINFORCE 76%, PPO 49%) shows no
  attack effect; seed 3 REINFORCE δ=2 no effect, δ=10 +50%.
- V1 bias / V2 risk: no attack effect (V2 is protective under some conditions,
  consistent with value-baseline and return-normalization absorption).

## 4. Interpretation
The protected phase (episodes 0-999, shield active) is violation-free in every run
(shield construction + retained-shield control 0/5000).  Positive pairs contain
latent policy damage at the transition; non-positive low-disagreement pairs show
that available headroom does not determine exploit success.  Carr et al.'s
workflow supplies the third-party lifecycle instance, and the PPO, SAC, and
REINFORCE batteries characterize conditional exploitability across learners and
training realizations.

## 5. Files
- aggregate_table.csv, figures/fig1-3 (baseline bars; per-seed clean-vs-poisoned with
  first-violation labels; cumulative violation curves)
- REINFORCE_stage_report.md; per-run dirs with summary.json + eval_trace.npy
