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

## Amendment v1.5 (2026-08-16, PPO retirement-boundary causal isolation — P0')

Motivation: amendment v1.3's isolation result is REINFORCE-only (3/3 seeds at
retirement). The learner-generality claim "the latent-damage mechanism holds
across learner families" is currently supported only by the full-phase PPO
evidence (1/3 seeds), which is too weak for a causal claim. This amendment locks
the PPO version of the v1.3 isolation before any run, following the same
retirement-boundary logic. Must be locked BEFORE execution (server); no ad hoc
expansion.

### v1.5.1 Configuration (all locked)
- Env/domain: `obstacle (N=6)`; learner: vendored tf-agents **PPO** with action
  masking; switch: sudden (HARD); attack: **V3 contrast, δ=2**; eval: 5000 episodes
  (final) as in amendment v1.2.
- Poison scope: `--poison-scope shield-on` — the reward-record mutation is active
  ONLY while `shield_on` is True (step-based flag, the same flag the workflow
  uses); it stops exactly at the retirement instant; subsequent training is fully
  clean. Retirement instant for PPO = env-step 10^5 (`--switch-episode 4000` in
  step units = `train_step_counter/25`, per amendment v1.2).
- At-retirement evaluation: 1000 episodes at the switch instant, before any
  unshielded learning, on the current raw policy snapshot (evaluate- and
  freeze-at-retirement are the same snapshot), exactly as v1.3.
- Independent belief tracker (amendment v1.4 code version, "vC") is mandatory for
  all v1.5 runs; disagreement probe must not corrupt the training belief.

### v1.5.2 Seeds & namespace (locked before execution)
- **10 paired seeds: 101–110** (PPO). Clean and poisoned runs use the same seed →
  paired comparison. This namespace is disjoint from all previously used seeds
  (REINFORCE 1–3, PPO 1–3 full-phase; isolation reruns of v1.3 reused dirs
  `v3_d2_s{1,2,3}` but used no new seed values).
- Run dirs MUST be new: `obstacle_sudden_PPO_none_d2_s{101..110}` /
  `obstacle_sudden_PPO_v3_d2_s{101..110}`. No overwriting existing dirs.

### v1.5.3 Determinism gate (server, before the main battery)
- PPO on GPU may be non-deterministic (cuDNN). Before the battery: run clean
  seed 101 twice and require |violation_fraction_r1 − r2| ≤ 0.05 at retirement
  and in the final eval. If the gate fails, run on CPU multi-core (gridworld is
  tiny; CPU throughput is expected to be higher) and repeat the gate.

### v1.5.4 Statistical analysis & pre-specified decision rule
- Primary outcome: at-retirement violation fraction (1000 episodes), paired
  clean vs poisoned per seed (McNemar exact on paired eval episodes).
- Secondary: final (5000-episode) violation fraction; at-retirement disagreement;
  first-violation episode.
- **Positive-seed definition (locked)**: poisoned at-ret fraction ≥ clean at-ret
  fraction + 0.15 (15 pp) AND paired McNemar exact p < 0.01.
- **Decision rule (locked)**: PPO isolation is "reproduces" if ≥ 5/10 seeds are
  positive (mirrors the REINFORCE 3/3 signal at scale); "partial" if 3–4/10;
  "not reproduced" if < 3/10. If < 3/10, the paper's learner-generality claim is
  downgraded to "REINFORCE causal isolation + PPO full-phase boundary"
  (consistent with the main NDSS paper's PPO-negative boundary); report all 10
  seeds either way.
- **B1 outcome (2026-08-16, verdict recorded under this rule)**: NOT REPRODUCED,
  1/10 positive.  Only seed 101 reproduced (clean 0.219 → poisoned 0.754,
  p=3.7e-113, first-violation 19→0).  The other 9 seeds all landed in the
  unsafe ceiling regime (clean at-retirement 0.728–0.760, no headroom): 6
  significantly protective, 3 unchanged.  The paper's learner-generality wording
  was downgraded accordingly (full-phase 1/3 positive is training-state-specific;
  PPO retirement-boundary isolation is not reproduced at scale), and all 10 seeds
  are reported in `results/ppo_isolation_report.md`.

### v1.5.5 Outputs & files
- Per-run dirs with `*_summary.json` (incl. `poison_scope=shield-on`,
  `at_retirement_stats`, `disagreement_curve`, `poison_stats`), eval traces.
- Append v1.5 runs to `results/aggregate_table_v2.csv` (new rows, `version=vC`,
  `scope=shield-on`); do not overwrite existing rows.
- Figure: at-retirement clean-vs-poisoned comparison (per-seed paired bars) as
  `results/figures/fig6_ppo_isolation_template.{pdf,png}` (actual filename as
  produced; the v1.5.5 draft named it `fig6_ppo_retirement_isolation`); plus a
  combined
  REINFORCE+PPO isolation panel if REINFORCE multi-seed isolation (v1.6) runs.

## Amendment v1.6 (2026-08-16, REINFORCE retirement-boundary causal isolation at scale — R0')

Motivation: amendment v1.3's isolation result is 3/3 paired seeds on REINFORCE.
A reviewer rehearsal (mock review, item 13.6) asks for "REINFORCE 多个
independent seeds" rather than a 3-seed anecdote. This amendment scales the
exact v1.3 protocol to 10 paired seeds with the same locked decision rule as
v1.5, pre-registered before execution. No ad hoc expansion after results.

### v1.6.1 Configuration (all locked)
- Env/domain: `obstacle (N=6)`; learner: REINFORCE (vendored upstream);
  switch: sudden (HARD) at episode 1000; attack: **V3 contrast, δ=2**;
  poison scope: **shield-on** (mutation active only while the shield enforces
  the action mask; stops exactly at retirement; all later training clean).
- Training: 5000 episodes (≤100 steps). At-retirement eval: 1000 episodes on
  the raw-policy snapshot at the switch instant (evaluate-/freeze-at-retirement
  are the same snapshot). Final eval: 5000 episodes. Code version vC (independent
  belief tracker, amendment v1.4).

### v1.6.2 Seeds & namespace (locked before execution)
- **10 paired seeds: 201–210** (REINFORCE). Clean and poisoned runs share the
  seed → paired comparison. Disjoint from all prior namespaces (REINFORCE 1–3,
  PPO 1–3, PPO 101–110).
- Run dirs MUST be new:
  `obstacle_sudden_REINFORCE_none_d2_s{201..210}` /
  `obstacle_sudden_REINFORCE_v3_d2_s{201..210}`. No overwriting existing dirs.

### v1.6.3 Statistical analysis & pre-specified decision rule
- Primary outcome: at-retirement violation fraction (1000 episodes), paired
  clean vs poisoned per seed (McNemar exact on paired eval episodes).
- Secondary: final (5000-episode) violation fraction; at-retirement disagreement;
  first-violation episode.
- **Positive-seed definition (locked)**: poisoned at-ret fraction ≥ clean at-ret
  fraction + 0.15 (15 pp) AND paired McNemar exact p < 0.01 (identical to v1.5).
- **Decision rule (locked)**: REINFORCE isolation at scale "reproduces" if
  ≥ 5/10 seeds are positive; "partial" if 3–4/10; "not reproduced" if < 3/10.
  Report all 10 seeds either way.

### v1.6.4 Outputs & files
- Per-run dirs with `*_summary.json` (incl. `poison_scope=shield-on`,
  `at_retirement_stats`, `disagreement_curve`, `poison_stats`), eval traces.
- Append v1.6 runs to `results/aggregate_table_v2.csv` (new rows,
  `version=vC`, `scope=shield-on`); do not overwrite existing rows.
- Figure: combined REINFORCE+PPO at-retirement isolation panel
  (`fig6_retirement_isolation_combined`) once both v1.6 (REINFORCE) and v1.5
  (PPO) batteries are complete, plus per-learner panels.

## Amendment v1.7 (2026-08-16, attack-budget dose-response — P1/B3)

Motivation: the paper's "Attack budget and susceptibility" paragraph currently has
only two budget points (δ ∈ {2, 10}) per seed. A reviewer rehearsal demands a
reasonable dose-response / susceptibility boundary for the attack effect on
budget. This amendment pre-registers a dense δ grid on the server's
transfer-sensitive seed (s1; clean at-retirement 0.232), reusing the existing
same-machine same-version (vC) full-phase rows at δ=2 (at-ret 0.501) and δ=10
(at-ret 0.499), and adding δ ∈ {0.1, 0.25, 0.5, 1.0}. A secondary shield-on-only
series locks the same grid under the stricter causal scope (poison confined to
the protected phase), supporting the paper's latent-damage claim with a budget
threshold. No ad hoc expansion after results.

### v1.7.1 Configuration (all locked)
- Primary battery (full-phase, V3 contrast): obstacle (N=6), REINFORCE, sudden
  (HARD) switch at episode 1000, `--poison-scope full`; training 5000 episodes,
  at-retirement eval 1000 episodes, final eval 5000 episodes; code version vC.
  CLI identical to `run_fullvC.sh` (seed, poison-name, poison-delta, outdir).
- Secondary battery (shield-on-only, V3 contrast): identical config except
  `--poison-scope shield-on` (mutation active only while the shield enforces the
  action mask; stops at retirement; all later training clean). CLI identical to
  `run_v16.sh` plus a poison-delta argument.
- δ grid (locked): **{0.1, 0.25, 0.5, 1.0}** are new runs on seed 1;
  **δ=2 and δ=10 are reused** from the existing vC full-phase battery
  (`contrast_d2_s1_fullvC`, `contrast_d10_s1_fullvC`) and from the shield-on
  secondary battery where present; **δ=0 (clean)** is the baseline from
  `none_d2_s1_fullvC` (full-phase) and a new clean shield-on run (secondary).

### v1.7.2 Seeds & namespace (locked before execution)
- Seed **1** on the server (NUSdgx), the vC transfer-sensitive seed with clean
  headroom (clean at-ret 0.232; contrast δ=2 at-ret 0.501). Ceiling seeds are
  not extended here; susceptibility-boundary context uses existing vC rows.
- Run dirs MUST be new (no overwrite of any existing dir):
  - Primary (full): `obstacle_sudden_REINFORCE_contrast_d0p1_s1_doser`,
    `..._d0p25_...`, `..._d0p5_...`, `..._d1p0_...` (4 runs).
  - Secondary (shield-on): clean `obstacle_sudden_REINFORCE_none_d0_s1_shieldon_doser`
    + contrast `..._d0p1_...`, `..._d0p25_...`, `..._d0p5_...`, `..._d1p0_...`,
    `..._d2p0_...` (6 runs, all `_shieldon_doser`).

### v1.7.3 Statistical analysis & pre-specified decision rule
- Primary outcome: final (post-removal, 5000-episode) violation fraction,
  paired clean vs poisoned per δ (McNemar exact on paired eval episodes).
- Secondary: at-retirement violation fraction (1000-episode snapshot at the
  switch instant); at-retirement disagreement (unmasked raw/shield
  disagreement during training); first-violation episode; `poison_stats`
  (mutated records, total δ applied, raw reward min/max/mean) for budget
  realism.
- **Effective-budget rule (locked)**: δ is "effective" if poisoned final
  fraction ≥ clean final fraction + 0.15 (15 pp) AND paired McNemar exact
  p < 0.01. δ_min = smallest effective δ in the grid. Report every point.
- **Monotonicity (locked, descriptive)**: report whether at-retirement
  disagreement and post-removal damage are non-decreasing in δ (e.g., Kendall
  τ or simple monotone count). This is observational support for the
  disagreement-as-mechanism reading (RESULTS_ANALYSIS E3), not a causal proof.
- **Susceptibility boundary**: report the transfer-sensitive vs ceiling clean
  regime contrast using existing vC rows (s2/s3 ceiling at-ret ≈ 0.755/0.749).

### v1.7.4 Outputs & files
- Per-run dirs with `*_summary.json` (incl. `at_retirement_stats`,
  `disagreement_curve`, `poison_stats`), eval/at-ret traces.
- Append v1.7 runs to `results/aggregate_table_v2.csv` (new rows,
  `version=vC`, `scope=full` / `scope=shield-on`); do not overwrite rows.
- Figure: dose-response curve on the transfer-sensitive seed (violation
  fraction and at-ret disagreement vs δ, log-scale δ axis) as
  `results/figures/fig7_dose_response.pdf` update (replacing the vA-only panel
  with the vC dense grid; keep shape-control panel).
- Update paper "Attack budget and susceptibility" paragraph and
  `RESULTS_ANALYSIS_AND_NEXT_STEPS.md` / `EXPERIMENT_SUMMARY.md` P1 status.

## Amendment v1.8 (2026-08-16, second-domain (Avoid) generality — P3/B4)

Motivation: the paper's central claim (reward-record corruption → latent damage
inside the protected phase → degradation at shield retirement) rests on a single
domain (obstacle N=6). A reviewer rehearsal demands environment/task generality.
B4 is registered in RESULTS_ANALYSIS_AND_NEXT_STEPS.md as "avoid 域: fidelity +
clean + poisoned 隔离". Pre-registered before any avoid-domain run.

Domain mapping (verified 2026-08-16 on NUSdgx): Carr et al.'s "Avoid" domain
(AAAI'23 Fig. 3e, N=6, Radius=3) is exposed in the vendored gridstorm as
`surveillance(N, RADIUS)` loading `avoid.nm`. It builds a 5,976-state POMDP;
the shield (winning region + OTF belief-support query) computes in ~34 s; and it
exposes 349 trap-adjacent (risk) states, so the locked V3-contrast attack shape
(risk +δ, safe −δ) transfers without redefinition. Smoke run (10 training +
3 at-ret + 3 final episodes, contrast δ=2) completed end-to-end with the vC
pipeline.

### v1.8.1 Fidelity gate (avoid domain, clean, seed 1)
- Four runs, 5000 episodes, REINFORCE, `--grid-model surveillance
  --constants N=6,RADIUS=3`, `--obs-level BELIEF_SUPPORT --valuations
  --goal-value 1000 --at-retirement-eps 1000 --final-eval-eps 5000`.
- Conditions: no-shield (`--noshield`), shield retained (`--switch-shield
  RETAINED`), sudden (`--switch-shield HARD --shield-episode 1000`), smooth
  (`--switch-shield SOFT --shield-episode 1000`).
- Gate criterion (locked): qualitative ordering shield-retained (0/0) < smooth
  ≪ sudden ≤ no-shield, matching Carr et al. Table 1 (which averages across six
  domains; the ordering is the mechanism-level gate). Report absolute rates as
  avoid-domain values; do NOT claim per-domain equality with the paper.

### v1.8.2 Attack isolation (avoid domain, shield-on V3 contrast δ=2)
- Same locked protocol as amendment v1.3 (P0) on the avoid domain: poison
  scope shield-on (mutation active only while the shield enforces the action
  mask; stops at retirement; later training clean), evaluate-/freeze-at-retirement
  on the same snapshot, at-ret eval 1000 episodes, final eval 5000.
- 3 paired seeds (1–3; new for the avoid domain), clean + contrast δ=2.
- Positive-seed rule (identical to v1.5/v1.6): poisoned at-ret fraction ≥ clean
  at-ret fraction + 0.15 AND paired McNemar exact p < 0.01. Report 3/3 / 2/3 /
  <2/3 honestly; "generality" = 3/3, "partial" = 2/3, "not reproduced" < 2/3.

### v1.8.3 Seeds & namespace (locked before execution)
- New dirs (no overwrite), `avoid_` prefix:
  - Fidelity: `avoid_noshield_s1_fid`, `avoid_retained_s1_fid`,
    `avoid_sudden_s1_fid`, `avoid_smooth_s1_fid`.
  - Isolation: `avoid_sudden_REINFORCE_none_d2_s{1,2,3}` /
    `avoid_sudden_REINFORCE_v3_d2_s{1,2,3}` (shield-on scope, δ=2).
- Staging: isolation battery is launched only after the fidelity gate passes.

### v1.8.4 Outputs & files
- Per-run dirs with `*_summary.json` (incl. `at_retirement_stats`,
  `disagreement_curve`, `poison_stats`), traces. Append v1.8 rows to
  `results/aggregate_table_v2.csv` (`version=vC`, `env=avoid`).
- Update paper environment-generality discussion and
  `RESULTS_ANALYSIS_AND_NEXT_STEPS.md` B4 status.

## Amendment v1.9 (2026-08-16, full-phase attack at scale — P2: PPO + REINFORCE 10-seed batteries)

Motivation: the paper's full-phase learner-boundary claim (PPO 1/3 seeds, local vA)
and the budget/susceptibility paragraph rest on 3-seed full-phase data per learner.
A reviewer rehearsal (mock review items 13.7/13.8) asks for (i) PPO positive
evidence in several independent seeds, or an explanation of the seed
heterogeneity, and (ii) a budget/susceptibility boundary.  The causal isolation
batteries (v1.5 PPO 101–110, v1.6 REINFORCE 201–210) already exist at scale, so
this amendment pre-registers the **full-phase** batteries on the **same seed
namespaces**, making full-phase vs shield-on isolation directly comparable on
identical seeds and testing the susceptibility rule (clean at-ret < 0.5) across
both scopes.  Locked before execution; no ad hoc expansion after results.

### v1.9.1 Configuration (all locked)
- Env/domain: `obstacle (N=6)`; code version vC (independent belief tracker,
  amendment v1.4).  Switch: sudden (HARD).  Attack: **V3 contrast, δ=2**.
  Poison scope: **`full`** — mutation active for the entire training budget
  (the original full-phase attack condition of the local vA runs, now at scale
  on the server vC code).
- PPO: `--learning-method PPO --max-runs 100000 --shield-episode 4000`
  (retirement at env-step 10^5, step units per v1.2); at-ret eval 1000 episodes,
  final eval 5000 episodes.  CLI identical to `run_p0.sh` except
  `--poison-scope full`.
- REINFORCE: `--learning-method REINFORCE --max-runs 5000 --shield-episode 1000`
  (retirement at episode 1000); at-ret eval 1000, final eval 5000.  CLI
  identical to `run_v16.sh` except `--poison-scope full`.
- Threads: `OMP_NUM_THREADS=1 TF_NUM_INTRAOP_THREADS=1 TF_NUM_INTEROP_THREADS=1`
  (CPU, as all prior server batteries).

### v1.9.2 Seeds & namespace (locked before execution)
- **PPO: seeds 101–110** (the exact namespace of the v1.5/B1 isolation battery).
- **REINFORCE: seeds 201–210** (the exact namespace of the v1.6/v16 isolation
  battery).
- Run dirs MUST be new (no overwrite), `_fullvC` suffix marks vC full-phase:
  `obstacle_sudden_PPO_{none,v3}_d2_s{101..110}_fullvC` and
  `obstacle_sudden_REINFORCE_{none,v3}_d2_s{201..210}_fullvC`.

### v1.9.3 Statistical analysis & pre-specified decision rule
- Primary outcome: **at-retirement** violation fraction (1000-episode snapshot,
  paired clean vs poisoned), consistent with v1.5/v1.6 so full-phase and
  isolation are on the same metric.
- Secondary: final post-removal (5000-episode) violation fraction (the metric
  of the original full-phase PPO claim 1178→2439); at-retirement disagreement;
  first-violation episode.
- **Positive-seed rule (locked, identical to v1.5/v1.6)**: poisoned at-ret
  fraction ≥ clean at-ret fraction + 0.15 AND paired McNemar exact p < 0.01.
- **Decision rule (locked, identical to v1.5/v1.6)**: full-phase at scale
  "reproduces" if ≥ 5/10 seeds positive; "partial" if 3–4/10; "not reproduced"
  if < 3/10.  Report all seeds either way.
- **Susceptibility-rule test (locked, pre-specified)**: across all paired rows
  of v1.9 + v1.5 + v1.6 + v1.8, test the existing 2×2 claim (positive seeds are
  exactly those with clean at-ret < 0.5) by cross-tabulating
  {clean at-ret < 0.5} × {positive}.  Report the counts; do not re-weight.
- **Budget follow-up (pre-registered, contingent)**: IF the PPO full-phase
  battery yields ≥1 transfer-sensitive seed (clean at-ret < 0.5), a
  deterministic PPO dose grid (δ ∈ {0.5, 1, 4, 10} on that seed, full scope,
  vC) may be locked as amendment v1.11 before running.  (NOTE 2026-08-16:
  the name v1.10 was subsequently taken by the locked SAC retirement-boundary
  isolation + retained-shield control amendment, so the contingent PPO dose
  grid is renumbered v1.11; it remains conditional on a v1.9 transfer-sensitive
  seed and is NOT locked until it fires.)  This is the only
  permitted response to the B3 trajectory-variance finding; no REINFORCE
  cross-batch dose claims.

### v1.9.4 Outputs & files
- Per-run dirs with `*_summary.json` (incl. `at_retirement_stats`,
  `disagreement_curve`, `poison_stats`), eval/at-ret traces.
- Append v1.9 rows to `results/aggregate_table_v2.csv` (new rows,
  `version=vC`, `scope=full`); do not overwrite existing rows.
- Analysis: extend `analyze_ppo_isolation.py` / add `analyze_fullphase.py`
  to produce per-seed paired tables for both learners; update the paper's
  "Learner boundary" and "Reading" paragraphs and the 2×2 susceptibility
  counts; update `RESULTS_ANALYSIS_AND_NEXT_STEPS.md` B2 status.

## Amendment v1.10 (2026-08-16, off-policy learner (SAC) retirement-boundary isolation + retained-shield escape control)

Motivation: the third-party lifecycle's learner boundary is currently REINFORCE + PPO
(both on-policy policy-gradient learners); the reviewer rehearsal explicitly lists
off-policy (SAC/DDPG) as outside the evidence stack, and the paper's "retained shield is a
sound escape condition" claim on the Carr workflow rests only on the clean fidelity
retained condition (0/0). This amendment pre-registers two small batteries before any
execution: (A) SAC retirement-boundary isolation (off-policy learner variety on the same
workflow), and (B) a poisoned retained-shield control (escape-condition containment).
No ad hoc expansion after results.

### v1.10.1 Part A — SAC retirement-boundary isolation (3 paired seeds)
- Configuration (all locked): `obstacle (N=6)`; code vC (independent belief tracker,
  amendment v1.4); sudden (HARD); **V3 contrast, δ=2**; poison scope **shield-on**
  (mutation active only while the shield enforces the mask and stops at retirement);
  at-retirement eval 1000 episodes; final eval 5000 episodes.
- SAC specifics: `--learning-method SAC --max-runs 100000 --shield-episode 100000`.
  Step units for non-PPO/REINFORCE are the raw `train_step_counter`
  (rl_simulator.py: `step = train_step_counter.numpy()`), so retirement is at
  env-step 10^5 — matching the upstream SAC obstacle budget (`cfgs/SAC.json`,
  `obstacle_sac`, max_runs 100000) and directly comparable to the PPO battery's
  env-step-10^5 retirement (v1.5/v1.9).
- Seeds & namespace (locked before execution): **401, 402, 403** (new namespace,
  disjoint from all prior: REINFORCE 1–3/201–210, PPO 1–3/101–110, avoid 1–3,
  dose 1). Run dirs MUST be new (no overwrite):
  `obstacle_sudden_SAC_{none,v3}_d2_s{401..403}`.
- Statistical analysis & decision rule (locked, identical to v1.5/v1.6):
  primary = at-retirement violation fraction (1000-episode snapshot, paired clean vs
  poisoned); secondary = final (5000-episode) fraction, at-retirement disagreement,
  first-violation episode. **Positive-seed rule**: poisoned at-ret ≥ clean at-ret + 0.15
  AND paired McNemar exact p < 0.01. **Verdict rule (locked, 3 seeds)**: ≥2/3 positive →
  add a SAC sentence to the paper's Learner-boundary paragraph (off-policy learner
  variety; NOT "off-policy generality"); 1/3 → PARTIAL (report per-seed); 0/3 → SAC
  negative boundary (paper states SAC did not reproduce). All seeds reported either way.
- Susceptibility check (locked, pre-specified): add SAC rows to the 2×2 cross-tabulation
  {clean at-ret < 0.5} × {positive} (per v1.9.3); report counts, do not re-weight.
- **Pipeline smoke (pre-battery, not a battery run)**: one clean + one contrast run at
  `--max-runs 2000 --seed 499` (smoke namespace, dir `sac_smoke/`) to verify the SAC
  off-policy pipeline (training, shield switch at env-step 2000, at-ret eval, summaries).
  Smoke results are NOT included in any paired battery or paper number.

### v1.10.2 Part B — retained-shield escape-condition control (3 paired seeds)
- Configuration (all locked): `obstacle (N=6)`; code vC; **switch-shield RETAINED**
  (never switches; final eval remains shielded via `final_unshielded=False`);
  V3 contrast **δ=2**, poison scope **full**; REINFORCE, 5000 episodes, maxsteps 100;
  final eval 5000 episodes.
- Seeds & namespace (locked before execution): **1, 2, 3** — identical seeds to the
  server fullvC sudden full-phase runs (`results/fullvC/..._s{1,2,3}_fullvC`, same vC
  code) so the retained-vs-sudden comparison is on identical seed/code/platform and
  isolates the authority transition. Run dirs MUST be new (no overwrite):
  `obstacle_retained_REINFORCE_v3_d2_s{1,2,3}`.
- Decision rule (locked): **PASS** if all 3 seeds have `during_violations = 0` AND final
  (shielded) eval = 0. Any nonzero violation under the retained shield is a protocol
  incident: stop and discuss before any paper claim. Report the paired retained-vs-sudden
  final numbers as evidence that "resident authority contains the consequence; removal
  exposes it."

### v1.10.3 Outputs & files
- Per-run dirs with `*_summary.json` (incl. `at_retirement_stats`, `disagreement_curve`,
  `poison_stats`), eval/at-ret traces.
- Append v1.10 rows to `results/aggregate_table_v2.csv` (new rows, `version=vC`,
  `scope=shield-on` for Part A, `scope=full,retained` for Part B); do not overwrite.
- Analysis: extend `analyze_ppo_isolation.py` (or add `analyze_sac.py`) for Part A;
  a small retained-control table for Part B. Update the paper's Learner-boundary and
  Escape-conditions paragraphs and the 2×2 counts; update
  `RESULTS_ANALYSIS_AND_NEXT_STEPS.md`.
