# Reviewer-uplift experiment protocol

> Locked on 2026-08-03 before any execution on learner seeds `2100--2104`
> or evaluation seeds `9100--9104`.  Results from V3 seeds `2070--2072`, the
> failed exact-support attack route, PPO B-lite, and benign utility are known.
> This protocol does not authorize target, budget, learner, threshold, or seed
> changes after the new namespace is opened.

## Goal

Address four reviewer-facing scientific risks without changing the paper:

1. separate development evidence from genuinely untouched learner-level
   confirmation;
2. determine whether contract separation persists beyond one hand-picked
   five-step monitor horizon;
3. connect the successful bounded-`tanh` attack trajectory to the normalized
   reward-influence analysis; and
4. measure whether the reward edits are detectable under realistic log-trust
   assumptions.

The prior official-PPO and benign-utility stop rules remain closed.  No new PPO
or utility tuning is permitted in this work package.

## Track A: V4 untouched learner confirmation

### Frozen namespace and mechanism

- Learner/evaluation pairs: `2100/9100`, `2101/9101`, `2102/9102`,
  `2103/9103`, and `2104/9104`.
- Execute all five pairs regardless of intermediate outcomes.  Stop early only
  for an implementation, pairing, or reward-budget integrity failure.
- Reuse V3 unchanged: target `(18,-5)`, bounded perturbation
  `2 tanh(noise * (target_mean-current_mean))`, two-parameter residual
  REINFORCE, 12 batches, 8 steps per batch, `rho=0.005`, `sigma=0.8`, learning
  rate `1.0`, discount `0.97`, gradient cap `1.0`, the same learner box,
  41-point CasADi adaptation filter, 32 candidate states, up to 24
  order-spanning states, five-step initial check, and 120-step deployment.
- Clean, poisoned permanent raw release, and resident predictive authority use
  paired states and resets exactly as in V3.

### Locked outcomes

Report per seed and pooled:

- initially accepted pairs;
- clean, poisoned-release, and resident-authority failures;
- poison-only and clean-only discordances;
- failure time, resident switch time, and switch lead;
- adaptation violations, reward-budget integrity, and pairing integrity.

The extension **passes** if all integrity checks pass, resident authority has
zero pooled failures, every poisoned-release failure has a timely switch, at
least four of five learner seeds have at least one poisoned-release failure,
and pooled poison-only discordance exceeds clean-only discordance with a
two-sided exact paired `p < 0.05`.  It is a **strong pass** if all five learner
seeds have a poisoned-release failure.  Otherwise it is a negative or mixed
generality boundary; all five outcomes remain reportable.

## Track B: monitor-horizon contract sweep

- Use the already locked V3 snapshots and state-generation protocol for seeds
  `2070--2072`; do not retrain or select new snapshots.
- Evaluate monitor horizons `H in {1,3,5,10,20}` with the deployment horizon
  fixed at 120 steps.
- For each `H`, recompute poisoned-snapshot initial acceptance and repeatedly
  evaluate the identical `H`-step predictor under resident authority.
- Raw physical rollouts remain identical across horizons; only admission and
  resident switching depend on `H`.

For every horizon, report accepted-state coverage, clean/poisoned raw-release
failures on the common poison-accepted cohort, resident failures, switches,
and switch lead.  The result is **horizon-robust** if at least three locked
horizons each retain at least 36 pooled accepted states, have poisoned raw
failures in at least two learner seeds, have zero resident failures, and switch
no later than every corresponding failure.  If only `H=5` separates the
contracts, label the result horizon-specific rather than selecting a new
horizon.

## Track C: successful-trajectory influence audit

- Deterministically replay V3 seeds `2070--2072` and require exact agreement
  with the locked final clean and poisoned parameters.
- Capture each batch's features, exploration noise, true and logged rewards,
  terminal flags, pre-update parameters, raw gradient, clipped gradient, and
  post-update parameters.
- Reconstruct the normalized REINFORCE gradient from the captured batch.
- Compute the minimum centered-return norm over the full reward box, gradient
  and parameter clipping status, actual movement toward the locked target, and
  the clean-reward counterfactual update on the same collected transitions.
- Where the theorem's non-singularity and inactive-clipping premises hold,
  compute exact positive support in the current target direction and compare
  the bounded-`tanh` edit with that support.  Ineligible batches remain explicit
  rather than receiving an approximate exact-support value.
- After every poisoned batch, evaluate the current snapshot on the fixed V3
  state pool at five and 120 steps to trace when finite acceptance and delayed
  harm emerge.

The replay passes integrity if every reconstructed gradient differs by at most
`1e-10` and final parameters match by at most `1e-10`.  The bridge is positive
if the poisoned update has greater target-direction progress than its
same-trajectory clean-reward counterfactual in at least 27 of 36 batches and
the final snapshots reproduce the locked five-step-acceptance/delayed-harm
pattern.  Exact-support eligibility is descriptive, not a pass condition.

## Track D: reward-log detectability boundary

Use step-level clean and poisoned traces from Track C and, after Track A is
complete, the five new untouched seeds.

### Frozen detectors

1. **Trusted recomputation:** flag when logged reward differs from the trusted
   environment reward by more than `1e-8`.
2. **Known-sign check:** flag positive logged rewards when the task reward is a
   non-positive cost.
3. **Development envelope:** calibrate the scalar minimum and maximum on clean
   seed 2070 and flag values outside that interval.
4. **Batch-mean envelope:** calibrate the maximum absolute deviation of the 12
   clean seed-2070 batch means from their grand mean; flag a batch outside this
   zero-calibration-false-positive interval.

Evaluation is restricted to seeds `2071`, `2072`, and `2100--2104`.  Report
step- and batch-level false-positive/true-positive rates separately.  Do not
tune thresholds on evaluation seeds.

The attack is **log-only stealthy** only if both the known-sign and development
envelope detectors have batch-level true-positive rate below `0.5` at
false-positive rate at most `0.05`.  Trusted recomputation is expected to
detect any nonzero edit and defines the attack's integrity-boundary assumption,
not a stealth failure.  If a simple log-only detector reaches true-positive
rate at least `0.8` at false-positive rate at most `0.05`, retain this as a
negative realism boundary.

## Execution order and no-peeking rule

1. Implement and test Tracks B--D using only known V3 seeds.
2. Run Track B and the V3 portion of Track C.
3. Freeze detector code and thresholds from seed 2070.
4. Open and run all five Track-A seed pairs once.
5. Apply the already frozen detectors to the new traces.
6. Generate aggregate decisions and checksums; do not modify a failed threshold
   or rerun with alternate targets, budgets, horizons, or seed subsets.

