# Carr et al. AAAI'23 Victim Experiment — Locked Protocol (v1)

**Status**: locked 2026-08-14 (before any experiment run). Amendments require a new version block.

## Amendment v1.1 (2026-08-14, after clean fidelity gate passed)

- Fidelity gate PASSED on obstacle/REINFORCE (seed 1, 5000 eps): shield 0/0,
  smooth 326/675, sudden 3277/3784, no-shield 3798/3784 — paper Tab. 1 ordering
  reproduced (shield < smooth ≪ sudden ≤ no-shield).
- Clean seed 2/3 (sudden): 1015/1127 and 1981/2471 → seed variance is large;
  paired same-seed comparisons are the primary analysis (McNemar exact on eval
  episode traces).
- V1 bias / V2 risk at δ=2 did NOT raise post-removal violations (mixed /
  slightly protective — absorbed by the value baseline and return normalization).
- V3 contrast at δ=2 raised post-removal violations on the transfer-sensitive
  seed (s2: 1127 → 3762, first-violation episode 6 → 0; disagreement 0.013 →
  0.105) and saturates where clean is already at ceiling (s1 75.7% → 75.7%).
- **Budget escalation added**: V3 contrast at δ=10 (per-record L∞ bound still
  ≪ terminal rewards ±1100; per-step rewards are ±1). Runs locked: seeds 1-3,
  sudden, 5000 eps.
- New metric captured: per-episode during-training violation episodes
  (`during_violation_episodes` in summary JSON) — the shielded phase
  (episodes 0..999) has 0 violations by shield construction (winning-region
  mask) and is verified empirically in the shield-retained condition (0/5000).

## Amendment v1.2 (2026-08-15, PPO battery)

- PPO (vendored tf-agents PPO, action masking) trained for 10^5 env steps,
  shield switched off at env-step 10^5 (`--switch-episode 4000` in the code's
  step units = train_step_counter/25, matching "shield for the first 1000
  episodes" of the REINFORCE protocol); eval 5000 episodes as before.
- PPO paired results (sudden, obstacle, contrast δ=2): seed 1 2448→2449
  (p=1.0), seed 2 1178→2439 (p=2.6e-149), seed 3 1142→1139 (p=0.96). Attack
  effect confined to transfer-sensitive seeds; consistent with REINFORCE seed 2
  (1127→3762, p≈0) and REINFORCE δ=10 seeds 2-3 (p≈0 / 8.4e-138).

## Amendment v1.3 (2026-08-15, retirement-boundary causal isolation — expert P0)

Motivation: the previous poisoned runs poisoned the ENTIRE training (including the
post-retirement unshielded phase), so they support "poisoned update provenance
undermines a shield-retirement learning workflow" but not yet the cleaner claim
"latent damage is created inside the protected phase and only becomes physical at
authority removal". Three isolation experiments, all produced by one run each:

1. **Shield-on-only poisoning**: `--poison-scope shield-on` — the reward-record
   mutation is active ONLY while the shield enforces the action mask (bootstrap
   phase); it stops exactly at the retirement instant (checked against the same
   `shield_on` flag that the workflow uses). Subsequent training is clean.
2. **Evaluate-at-retirement**: at the switch instant, before any unshielded
   learning, the current raw policy is evaluated (`at_retirement_eps=1000`
   episodes) → `at_retirement_stats`.
3. **Freeze-at-retirement**: the same snapshot; if at-retirement poisoned policy is
   already significantly worse than clean, the vulnerability is latent in the
   policy before any post-retirement learning (identical mechanism for evaluation).

New instrumentation per run: `disagreement_curve` (unmasked raw-policy/shield
disagreement during training, sampled every eval_interval — the latent-damage
signal: unsafe proposals masked by the shield while physical violations stay 0),
`poison_stats` (budget usage: mutated records, total delta, raw reward
min/mean/std), `at_retirement_stats`.

Runs locked: obstacle, sudden, REINFORCE 5000 eps: clean s1-3 + shield-on-only
contrast δ=2 s1-3 (paired). At-retirement eval = 1000 episodes (same loop as final
eval; the final 5000-episode eval is unchanged).

## Amendment v1.4 (2026-08-15, after P0 completed)

- **P0 results**: shield-on-only poisoning → 3/3 seeds dangerous at retirement
  (77.7/76.3/74.8% vs clean 21.6/48.4/23.9%); 2/3 seeds fail to self-heal after
  4000 clean post-retirement episodes (75.1/74.1% vs 23.4/23.3%); 1/3 (s1)
  self-heals (23.5%). At-retirement disagreement 2.3-8.6× higher under poisoning.
- **Reproducibility finding**: TF 2.15 CPU non-determinism gives run-to-run
  variance at fixed seed for REINFORCE+obstacle (clean s1 final: 3784 in the
  pre-instrumentation code version vs 1182/1140 in instrumented versions). All
  paired comparisons are within-version; cross-version absolute numbers must not
  be mixed. Full-phase poisoned runs (vA) to be re-verified with the current code
  version (vC) before paper use.
- **Instrumentation change**: eval env now uses an INDEPENDENT belief tracker
  (upstream shared one tracker between learn/eval envs; the unmasked disagreement
  probe executes raw-policy actions that corrupt a shared belief). See patches.md.

## 1. Objective

Demonstrate the paper's novel security intersection on an **independently proposed,
third-party shield-retirement lifecycle** (Carr et al., "Safe Reinforcement Learning via
Shielding under Partial Observability", AAAI 2023):

> Under reward-only update-log poisoning (bounded L∞ per-record mutation; no other plane
> writable), an assurance lifecycle that bootstraps a learner behind a runtime shield and
> later retires the shield's authority can leave the *protected phase* observationally safe
> while the *released raw policy* exhibits a large, latent post-removal safety failure —
> whereas the clean baseline transfers safely.

This turns the current paper's self-defined "resident vs raw release" contract into a
demonstration on a real, published workflow with public code.

## 2. Victim workflow (unchanged from upstream)

- Official code: `stevencarrau/safe_RL_POMDPs` (Zenodo DOI 10.5281/zenodo.7320140, commit
  vendored 2026-08-14) + `stevencarrau/shield_rl_gridworlds` (POMDP package `gridstorm`).
- Lifecycle (paper §4.3, Fig. 4, Tab. 1): train REINFORCE behind the Storm-computed
  belief-support shield for the first **1000 episodes**, then either
  - **HARD** (sudden): shield off from episode 1000 on;
  - **SOFT** (smooth): shield applied with probability `1 - decay`, `decay += 5e-3*α`
    per post-switch step (`α` = agent Adam learning rate; repo default 3e-2);
  - **retained**: shield stays on; **no-shield**: trained and run without shield.
- Training budget: 5000 episodes, ≤100 steps each (paper Tab. 1 protocol, REINFORCE).
- Eval: 5000 episodes with the *final* policy; violations counted as episodes ending in a
  `traps` (unsafe) state ("After" column); "During" = violations inside training episodes.
- Domains (first milestone): `obstacle (N=6)` — static traps, sparse reward, goal +1000,
  matches paper's hyperparameter domain. Secondary: `avoid (N=6, RADIUS=3)`, `rocks (N=6)`.
- Learners: REINFORCE first (paper's headline Tab. 1), then PPO and discrete SAC
  (paper §5: "these observations hold for other RL algorithms"), budgets 10^5 steps.

## 3. Attack (the ONLY change)

**Attack surface**: the reward records in the learner's update-data plane. The attacker may
write `r' = r + ξ` per record with `|ξ| ≤ δ` (L∞-bounded). Everything else — state,
observation, action, shield, environment dynamics, network parameters, optimizer, eval —
is untouched and identical between clean and poisoned runs.

**Knowledge**: attacker knows the public environment model (map, dynamics) and reads the
logged reward records (including the logged observation), matching a training-data
attacker on the update plane.

Attack variants (all bounded per-record, applied only during the training phase;
eval and violation counters see true rewards):
- **V0 / clean**: ξ = 0 (baseline).
- **V1 / constant bias**: ξ = δ on every record. State-free control; expected to be weak
  under return normalization.
- **V2 / risk-seeking**: ξ = δ if the logged state is *risk-adjacent* (one step from a
  trap under some action; static per-state flag from the public model), else 0.
- **V3 / contrast**: ξ = +δ on risk-adjacent records, −δ on safe records. Stronger
  steering toward danger corridors while remaining within the per-record bound.

Budgets: δ ∈ {1.0, 2.0} (per-step baseline reward is 0; goal/trap magnitudes ±1000 are
untouched, so the attack is a *latent* distortion, not a goal flip).

## 4. Seeds & pairing

Independent training seeds 1..3 (TF + NumPy + Storm simulator seed all derived from the
seed). Clean and poisoned runs use the *same* seed → paired comparison. No retraining,
no selection on results; all seeds reported.

## 5. Metrics (per seed, per condition)

- violations during training (protected phase) — expectation: 0 with shield in all
  conditions (attack must not change this);
- violations after removal across 5000 eval episodes + violation *probability* per episode;
- time-to-first-violation (episode index in eval);
- (aux) eval reward curves every 100 episodes (training progress), policy/shield
  disagreement rate on eval traces (fraction of steps where the unmasked policy argmax is
  outside the shielded set).

## 6. Stop rules / fidelity gate

1. **Environment gate**: the official pipeline must run on this Mac (stormpy 1.11.3 +
   TF 2.16 + TF-Agents 0.19, Python 3.10.12) with the vendored code and ≤1 documented
   patch per concern (seed plumbing, reward hook, metric capture). If the stack cannot run,
   stop and report, do not silently reimplement.
2. **Fidelity gate**: before poisoning, the clean baseline must qualitatively reproduce
   paper Tab. 1 ordering on the chosen domain: Shield ≈ 0/0 < Smooth ≪ Sudden < No-shield,
   with no-shield and sudden clearly non-zero. If not, investigate and lock config changes
   before any poisoned run.
3. **Poison runs**: V2/V3 must keep "during" violations at 0 (shield effectiveness intact);
   the headline result is clean-post-removal ≈ low vs poisoned-post-removal ≫ low in the
   HARD condition (and, if visible, a smaller effect in SOFT). Absence after all variants
   and seeds → negative result, reported as such (per audit §13 this is the go/no-go).

## 7. Outputs

`results/` per run: JSON summary (violations during/after, first-violation, per-episode
violation trace, seed/config provenance), aggregate CSV across seeds/conditions, figures
(during/after bars, per-episode violation curves), `patches.md` diff log vs upstream.

## 8. Compute notes (this machine)

MacBook (macOS 14.4.1, Apple Silicon), pyenv Python 3.10.12 venv, CPU-only TF 2.16.2,
stormpy 1.11.3 arm64 wheel. REINFORCE 5000-episode runs are the expected bottleneck;
timing smoke (200 episodes) gates the schedule.
