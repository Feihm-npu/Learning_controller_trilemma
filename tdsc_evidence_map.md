> ⚠️ **前一投稿场地的历史文档（2026-08-19 标注）。** 本文件针对 NDSS/TDSC 撰写，
> 与当前 USENIX Security 2027 的稿件状态、页面预算与结论均不一致。
> **当前状态请读 [`usenix_direction_audit_0819.md`](usenix_direction_audit_0819.md)。**
> 保留仅为历史记录。

# TDSC evidence map and claim lock

> **HISTORICAL (superseded 2026-08-05).** This is the TDSC-era result-to-claim
> contract. The project has since returned to **NDSS 2027**; the authoritative
> current claim contract is `ndss_submission_status.md`, which adds the headline
> resident-authority-vs-permanent-release separation (V4 `27/120` vs `2/120` vs
> `0/120`) not listed below. The C1--C6 numbers here remain factually correct and
> the BANNED-claims list below still holds, but this file no longer governs the
> paper's target venue or headline. Read it as history.
>
> Started 2026-07-30 after the pre-specified NDSS benign-utility gate
> failed.  This document is the result-to-claim contract for the journal
> rewrite.  A paper claim may not exceed the evidence listed here.

## Journal thesis

Safety certification for an online-adaptive cyber-physical controller is a
lifecycle property, not a property of one filtered action or one policy
snapshot.  Strategic corruption of update data can preserve safe adaptation
actions while moving the deployable raw policy outside its certificate.
Sound operation therefore requires explicit update admission, rollback, or
trusted re-anchoring.  These escape conditions have measurable coverage,
intervention, performance, and learning-availability costs.

The journal contribution is a systematic characterization of this lifecycle
boundary.  It is not a claim that all online learning is unsafe, that all
deep-RL learners are vulnerable, or that the current LifecycleGate has
demonstrated benign adaptation utility.

## Claim-to-evidence map

| ID | Claim allowed in the paper | Evidence | Status |
|---|---|---|---|
| C1 | Action certification does not imply update certification; sound lifecycle certification requires the updated action map to remain in the certified kernel over reachable attacked histories.  A finite abstraction is sufficient only when a joint reachable history/state/disturbance cover and an explicit discretization, policy-variation, and model-error margin are justified. | Current-history lemma, action-filter counterexample, future-history necessary theorem, linear-policy halfspace proposition, margin-robust finite-abstraction sufficiency theorem, plausible-set monotonicity proposition, analytic freeze frontier. | Necessary condition plus a conditional sufficient lift; neither is a complete controller-synthesis theorem. |
| C2 | A reward-log-only attacker can turn safe adaptation into unsafe delayed deployment for a canonical online learner without writing actions, gradients, parameters, or optimizer state. | Cartpole residual REINFORCE: clean 1/188, poisoned 38/188, commit/freeze 0/188; 37 poison-only vs 0 clean-only, two-sided exact paired `p=1.455e-11`. Quadrotor residual REINFORCE: clean 0/72, poisoned 68/72, commit/freeze 0/72; 68 poison-only vs 0 clean-only, two-sided exact paired `p=6.776e-21`; failures in 3/3 learner seeds. | Strong for the declared low-dimensional residual-REINFORCE family on two CPS benchmarks. |
| C3 | Finite-horizon snapshot admission and permanently-online safety mechanisms are distinct escape conditions. | Quadrotor commit gate 0/72 with nonzero retained fractions 0.55/0.40/0.70. Independent unadmitted-state audit at the pre-existing `H=100`, guard `0.003` configuration: 0 false acceptances among 1293 certified/1728 evaluated snapshot-state pairs; clean/commit/freeze coverage 0.986/0.944/1.000 and 5 false rejections. Unified independent-state frontier: poisoned raw 23/24 violations; commit/freeze/permanent shield/official MPSC all 0/24 on identical paired blocks. | Supported on the audited distribution and finite horizons; not a continuous invariant-set guarantee. |
| C4 | Strong runtime protection can eliminate observed physical failures while imposing substantial availability/performance cost. | Unified frontier: permanent shield intervenes on 511/2400 steps, reward `-0.19506`, median/p95 online latency `221.925/238.216 ms`; official MPSC intervenes on 2400/2400, reward `-0.45690`, median/p95 `59.657/76.055 ms`; both 0/24 violations. Commit has reward `-0.05647`, common-set coverage 0.903--1.000, offline certificate latency 8.49--9.32 s/seed, and raw-policy online latency about 0.026 ms. | Supported for the locked unified quadrotor audit; timing is host wall-clock, not WCET. |
| C5 | Parameter movement or certificate acceptance is not evidence of useful learning. | Benign actuator-bias smoke: freeze/clean/gate rewards `-0.03617/-0.04714/-0.08097`; all 0/12 deployment violations. Gate accepts nonzero updates in 11/12 batches with mean fraction `0.8208`, yet improves 0/12 paired rollouts; 12 certificate calls cost `100.93 s`. | Supported negative boundary from one pre-specified development seed; no formal utility sweep was run. |
| C6 | The fixed-budget unsafe-policy effect does not presently generalize to official PPO. | PPO B-lite: 16 batches clean 0/24, poisoned 1/24; 24 batches both 0/24. Neither locked physical nor two-checkpoint margin gate passed. Pretrained PPO is 0/72; a separately constructed normalized malicious target is 72/72 unsafe. | Supported negative boundary; do not claim a successful deep-PPO physical attack. |

## Claims explicitly forbidden

1. LifecycleGate has proved benign adaptation utility over always-freeze.
2. The reward-only attack causes stable physical failures in official PPO.
3. A sampled CasADi finite-horizon certificate is a continuous-state
   invariant-set proof.
4. The official MPSC is ineffective; it is effective but costly in this
   audit.
5. Nonzero accepted update fraction is synonymous with learning utility.
6. The work establishes a universal safety--security--learning impossibility
   theorem for every learner, attacker, and trusted-sensing architecture.
7. Pre-clip actuator saturation is a realized physical-input violation after
   clipping.  It must be reported separately.

## Evidence hierarchy

### Primary evidence

- Locked three-learner-seed quadrotor residual-REINFORCE audit.
- Locked three-seed cartpole residual-REINFORCE audit.
- Official linear-MPSC cost audit.
- Analytic lifecycle condition and freeze frontier.

### Boundary evidence

- Official PPO B-lite stop.
- Pre-specified benign-utility stop.
- One-step gate failure versus finite-horizon commit gate.
- Sampled-certificate coverage and admission limitations.

### Expository evidence

- One-dimensional, linear-tank, nonlinear-tank, and parameter-polytope
  examples.
- Short Safe-Control-Gym attacked-observation cartpole sweep.

Expository evidence explains the mechanism but may not replace the primary
end-to-end learner results.

## TDSC manuscript structure

1. Introduction: certification is stateful across updates; summarize positive
   evidence and negative boundaries together.
2. System and threat model: distinguish sensor/observation FDI, reward-log
   poisoning, runtime action filtering, snapshot admission, and trusted
   anchors.
3. Certificate lifecycle semantics: unsafe action, stale policy, uncertified
   update, forced freeze, and utility loss.
4. Necessary lifecycle conditions and finite abstractions.
5. Attack and gate constructions: reward-only REINFORCE attack, commit gate,
   permanent filter, and MPSC escape condition.
6. Evaluation methodology: result-independent calibration, disjoint data,
   paired outcomes, action-interface audit, and sampled-certificate boundary.
7. Positive results: cartpole and quadrotor multi-seed evidence.
8. Cost and boundary results: runtime shields, PPO, benign utility, and
   measurement audit.
9. Related work, limitations, and operational guidance.

## Remaining TDSC work packages

### P0 — manuscript truthfulness and reproducibility

- **Completed:** the obsolete conference abstract/evaluation has been replaced
  by the journal thesis, all locked positive results, and both negative gates.
- **Completed:** the manuscript has five CSV-generated tables and one analytic
  table; every generated result row carries an existing raw
  `source_file`/`source_files` link.  The old 12-rollout shield/MPSC rows were
  removed from the end-to-end table so runtime mechanisms are compared only
  on the unified 24-block audit.
- **Completed:** `tdsc_reproducibility_manifest.md` records exact commands,
  environment versions, the upstream revision, seed namespaces, and SHA-256
  checksums for 121 locked files.
- **Retained:** the invalid pre-clip calibration diagnostic remains in
  `benign_utility_protocol.md` and is explicitly excluded from confirmatory
  outcomes.

### P1 — certificate coverage and soundness boundary

- **Completed:** on 144 disjoint, unadmitted states and all 12 locked
  snapshots, the primary `H=100`, guard `0.003` cell certifies 1293/1728 pairs
  with zero false acceptance; clean/commit/freeze coverage is
  0.986/0.944/1.000 and false rejection is 5/435 rejected pairs.
- **Boundary retained:** the unguarded poisoned snapshot has 1/2/1 false
  acceptances at horizons 20/50/100.  Positive guard margins remove observed
  false acceptance but increase rejection.
- Continue to describe the result as sampled finite-horizon evidence, not an
  invariant guarantee.

### P2 — security and availability frontiers

- **Completed:** all six mechanisms were evaluated on 24 identical paired
  state/learner blocks selected from a new 144-state candidate pool per
  learner seed.  Poisoned raw violates 23/24; every protected mechanism and
  clean completes 24/24 without observed violation.
- **Completed:** pooled and per-seed CSVs include Wilson safety intervals,
  paired-block bootstrap reward intervals conditional on the locked snapshots,
  intervention, correction,
  rejection/infeasibility, and controller latency.
- **Completed:** offline commit reconstruction exactly reproduces fractions
  0.55/0.40/0.70 and is timed separately at 8.49--9.32 s/seed.  Common
  operating-set coverage is 0.993/1.000/0.903.
- **Boundary retained:** every completing adaptive/protective mechanism has
  lower paired reward than freeze on all 24 blocks; the runtime mechanisms
  impose large per-step computation and intervention costs.

### P3 — trusted-anchor characterization

- **Completed:** a locked grid varies anchor period 1/3/6/12 and two bounded
  qualities over the final poisoned snapshot.  Trusted calls are 12/4/2/1
  per 12 update checkpoints; only z/theta are placed on this boundary.
- **Completed:** every condition retains 16/16 certificate centers and has
  0/24 violations on new paired physical states, versus poisoned raw 23/24.
  Period 12 reduces retained fractions from 0.55/0.40/0.70 to
  0.50/0.40/0.65; periods 1/3/6 do not.
- **Boundary retained:** high and standard quality are indistinguishable at
  0.05 fraction resolution; every anchor-conditioned snapshot is worse than
  freeze on all 24 paired reward outcomes.  State anchors do not sanitize
  reward corruption.
- Anchor calls, uncertainty bounds, sampled-set size, exact-model audit
  latency, and the absence of hardware latency/energy measurements are
  explicit; the anchor is not modeled as a free oracle.

### P4 — theory strengthening

- **Completed:** the fixed-controller certificate is expressed through
  Lipschitz obligations over current state, action, disturbance, and successor
  state.  The composition assumptions now explicitly include a joint
  reachable history/state/disturbance cover, policy regularity, uniform model
  error, and model/certificate Lipschitz constants.
- **Completed:** the margin-robust finite-abstraction theorem tightens each
  sampled obligation by an explicit sum of state discretization, policy
  variation, disturbance discretization, and model-error terms; under the
  stated assumptions it is sufficient for continuous future-history
  lifecycle membership.
- **Completed:** plausible-set inclusion implies reverse kernel inclusion and
  certified-parameter-set inclusion on a fixed history domain.  This gives a
  monotone freeze frontier for nested ambiguity and explains when a trusted
  anchor can weakly enlarge feasibility.
- **Boundary retained:** the experimental sampled certificates do not prove
  the theorem's joint-cover or uniform-error premises; the empirical guard
  and coverage audit are not promoted to a continuous invariant proof.

### P5 — submission gate

- **Completed:** P0--P4 are complete and their empirical/theoretical
  boundaries remain explicit.
- **Completed:** all five generated tables are source-linked; runtime
  mechanisms are compared only on the common 24-block protocol.
- **Completed:** the official-PPO and benign-utility negative results remain
  visible in the abstract, introduction, evaluation, limitations, and
  conclusion.
- **Completed:** automated submission audits check provenance, generated
  inputs/figures, the old mixed protocol, forbidden positive phrasing,
  statistical-reporting locks, the TDSC abstract constraint, and all locked
  checksums.  The full suite passes 34/34.
- **Completed:** the 15-page journal PDF compiles without overfull boxes,
  undefined references, or undefined citations, and its key result pages have
  been visually inspected.

**Decision:** the TDSC draft passes the defined P5 gate and is ready for
internal scientific review.  This is not yet a claim that editorial metadata,
author declarations, or the final journal submission package are complete.

### P6 — internal scientific red team

- **Completed:** closest-prior-work positioning now explicitly covers
  Simplex online upgrades, linear/adaptive MPSC, shielding and shield removal,
  online barrier learning, and prior policy/reward poisoning.  Novelty is not
  attributed to rollback, permanent switching, shielding, or reward poisoning.
- **Completed:** the quadrotor paired exact test was corrected from a
  mislabeled one-sided value to the two-sided value `6.776e-21`; code, locked
  artifact, prose, and regression tests agree.
- **Completed:** rollout-level tests, Wilson intervals, and paired-block
  bootstraps are scoped as conditional on three locked learner snapshots, not
  inference over 72 independent learners.
- **Completed:** failed-episode rewards, sampled-certificate claims, internal
  protocol locking, and the action-kernel/parameter-set type distinction were
  corrected or clarified.
- **Completed:** the TDSC abstract is 188 words with no mathematical
  expressions.  The 15-page PDF compiles without overfull boxes, undefined
  references, or undefined citations.

**Decision:** the scientific package passes internal red-team review for TDSC
and should now be frozen for coauthor/external novelty review.  NDSS remains
unsupported because official-PPO generality and benign utility both failed
their pre-specified gates.
