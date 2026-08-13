# Stealth temporal-reward work package — brainstorming draft

> Status: **DRAFT / NOT PRE-REGISTERED** (2026-08-03).  No new learner or
> evaluation seed has been opened.  All quantitative screening below uses the
> already burned V3/V4 traces.  This file may change until a separate protocol
> is explicitly frozen.

## Why open this work package

The V4 extension strongly reproduced lifecycle contract separation, but the
frozen reward-log audit rejected a stealth claim: known-sign and scalar-range
checks achieved over 90% batch-level TPR.  The new question is therefore not
whether a larger reward perturbation can cause more failures.  It is:

> Can an attacker alter temporal credit assignment while preserving the
> reward statistics visible to an unauthenticated log auditor, and can resident
> deployment authority still contain the resulting snapshot?

Trusted reward recomputation remains an explicit hard boundary.  No nonzero
reward-only attack is expected to evade a trusted transition-linked reward
anchor.

## Candidate mechanisms

### S1 (preferred novelty route): sparse bounded reward permutation

After an eight-step batch is collected and before the learner update, choose a
permutation matrix `P` and log `P r` rather than `r`.  The attacker may inspect
the completed batch but cannot change actions, states, terminal flags,
gradients, optimizer code, or parameters.

Proposed frozen feasible set:

- `max_i |(P r)_i-r_i| <= 2`;
- at most four of eight reward positions move;
- identity is always feasible;
- choose the exact best feasible permutation under the learner's actual
  normalized, gradient-capped, parameter-clipped next-update rule;
- use the already documented pre-WP harmful target
  `(-2.3625524160241205, -5.0)`, rather than choosing a target from new runs.

For every feasible `P`, the attack exactly preserves the batch reward
multiset.  Consequently it preserves sign counts, minimum, maximum, every
quantile, mean, variance, histogram, and every permutation-invariant detector.
It changes the REINFORCE update because the discounted return operator is
order-sensitive and generally does not commute with `P`.

Because the batch has only eight rewards, all `8! = 40,320` permutations can be
enumerated.  The chosen update is therefore exact over the declared finite
attack set and does not require the inactive-clipping or non-singularity
premises that blocked the previous continuous support certificate.

### S2 (power fallback): moment-preserving projected shaping

Start with target-directed bounded `tanh` shaping and project its reward edit
onto

```
|delta_i| <= 2
L <= r_i + delta_i <= U
sum_i delta_i = 0,
```

where `[L,U]` is frozen using old clean traces.  This enforces non-positive,
in-envelope logged rewards and exactly preserves the true batch mean.  It does
not preserve the full multiset and is therefore less novel and less stealthy
than S1, but it retains substantially more local gradient influence.

### Baselines / ablations

- Original bounded-`tanh` V3 attack (effective but detectable).
- Sign/range-clipped `tanh` without mean preservation.
- S1 with at most two moved rewards (one-swap sparse limit).
- S1 with all eight positions movable (permutation power upper bound).
- Clean learner and freeze baseline.

## Existing-trace capacity screen

The screen used 96 clean or poisoned batches from learner seeds 2070--2072 and
2100--2104.  It did not run a new environment seed.

- Every one of 96 batches has a non-identity budget-feasible permutation.
- Full permutations improve the negative-bias update objective in 96/96
  batches; median improvement is 0.0815 in effective-gradient coordinates on
  clean trajectories.
- Restricting the permutation to at most four moved positions retains an
  average improvement of 0.1061 versus 0.1187 with all positions movable
  (about 89% of the full-permutation capacity).
- A single swap improves the same objective in 96/96 clean batches; its median
  improvement is 0.0522.
- On poisoned trajectories, exact permutation remains beneficial in 96/96
  batches, with median `L_inf` edit 0.192 and no sign violation.
- Projecting the existing `tanh` edit to the clean sign/range envelope removes
  all sign and scalar-envelope batch flags in this retrospective screen while
  retaining positive negative-bias influence in 90/96 batches.
- Adding exact mean preservation retains positive influence in 88/96 batches;
  the projection problem is feasible in 96/96 batches.

The important negative signal is cumulative strength.  On fixed clean
trajectories, a four-position permutation reaches only about `-1.7` median
bias after 12 batches when aimed at the prior harmful snapshot.  Mean-preserving
projected shaping reaches about `-3.0` median bias.  S1 is therefore a
high-novelty/high-failure-risk route; S2 is the lower-novelty power fallback.

## Threat-model split

The work package should distinguish three observation levels.

1. **Marginal reward log:** sign, range, moments, quantiles, histogram, KS,
   Wasserstein, MMD, and cross-batch change-point checks.  S1 is structurally
   indistinguishable for within-batch permutation-invariant checks.
2. **Ordered but unauthenticated log:** lag-one correlation, total variation,
   run lengths, spectral features, and clean-trained feature/reward residuals.
   These are the meaningful empirical stealth tests for S1.
3. **Trusted transition-linked anchor:** authenticated environment reward or
   trusted recomputation.  Any non-identity S1/S2 edit is detectable; this is a
   system assumption and intended boundary, not an attack failure.

The attacker needs outer-loop access to a completed reward batch before the
batch learner updates.  It does not need to modify the learner or physical
trajectory.  This assumption must remain explicit.

## Proposed staged execution and stop rules

### Stage 0 — capacity and collision screen

- Existing-trace capacity screen: complete, positive for both S1 and S2.
- Complete a dedicated novelty review before making a novelty claim.  Current
  search found adaptive reward poisoning, outer-loop dynamic poisoning, and
  homogeneity-based stealth detection, but no direct use of bounded within-
  batch reward permutation to preserve the exact reward multiset while
  attacking temporal credit assignment.

### Stage 1 — implementation-only gate

- Implement S1 exact enumeration and S2 box-plus-mean projection behind the
  existing `reward_poisoner` interface.
- Unit-test exact multiset preservation, move count, reward budget, sign/range,
  mean preservation, exact argmax agreement against brute force, and no direct
  parameter/gradient writes.
- Benchmark per-batch attack latency.
- Do not run new seeds.

### Stage 2 — burned-seed online smoke

- Run seed 2070/9070 first, then 2071/9071 and 2072/9072 only if the first smoke
  has nonzero target progress and all integrity checks pass.
- Keep 12 batches, eight steps, the existing learner, action filter, state
  generation, H=5 admission, and 120-step deployment fixed.
- Prefer S1-k4 if it produces at least one poison-only raw-release failure with
  zero resident failures and exact log invariants.
- If S1-k4 has no raw-release effect, run S2 once as the pre-declared fallback;
  do not tune `k`, batch count, reward budget, target, or horizon in response.
- Stop the WP if neither route produces a raw-release effect on at least two of
  the three burned seeds.

### Stage 3 — detector freeze

- Calibrate the enlarged log-only detector suite exclusively on already
  available clean traces.
- Freeze thresholds, code hashes, attack route, target, seeds, and all success
  criteria before opening a new namespace.
- A proposed stealth hard gate is: no frozen log-only detector has batch-level
  TPR >= 0.5 at FPR <= 0.05, while trusted recomputation is reported separately.

### Stage 4 — untouched confirmation

- Reserve a fresh five-seed learner/evaluation namespace only after Stage 3.
- Execute all five pairs once.
- Reuse the V4 efficacy gate: failures in at least four of five learner seeds,
  pooled poison-only discordance greater than clean-only with two-sided exact
  `p < 0.05`, zero resident failures, timely switching, and full integrity.
- Require both efficacy and the frozen log-only stealth gate.  Otherwise report
  an effectiveness--observability frontier rather than selecting a new route.

## Decision tree and sunk-cost control

- **S1 succeeds:** strongest outcome.  The contribution becomes temporal
  credit-assignment poisoning that is exactly invisible to marginal reward
  audits, plus the resident-authority mitigation.
- **Only S2 succeeds:** useful but more incremental.  Frame it as a constrained
  effectiveness--detectability frontier, not perfect stealth.
- **Neither succeeds:** stop.  Retain the already established conclusion that
  the effective V3/V4 attack is detectable without a trusted reward anchor.

The next authorized action should be Stage 1 plus the single burned-seed S1-k4
smoke.  New seed reservation and protocol freezing should wait for that result.
