# Multi-seed cartpole release-contract audit

> Locked on 2026-07-31 before implementation or execution.  
> Scope: confirmatory contract audit with a development-fixed monitor horizon.

## Question

Across all three locked cartpole reward-poisoned learner snapshots, does the
same finite reverse-switch evidence remain safe only when predictive runtime
authority is retained, while permanent raw release exposes delayed failure?

## Frozen inputs

- Learner seeds: `2040`, `2041`, and `2042`.
- Snapshots: the locked `poisoned_action_only_snapshot` pending gain/bias in
  `results/safe_control_gym_reinforce_reward_poisoning_sweep.csv`.  There is no
  retraining or snapshot reselection.
- Fresh evaluation seeds: `8040`, `8041`, and `8042`, paired one-to-one with
  learner seeds.
- Candidate states: 32 uniform draws per evaluation seed from
  `[-0.25,0.25] x [-0.50,0.50] x [-0.15,0.15] x [-1,1]`.
- Baseline admission: trusted zero-residual LQR is safe for 120 CasADi steps
  with guard `0.0075`.
- Paired state count: 24 per learner seed, selected by deterministic
  order-spanning indices from the baseline-admitted list.
- Initial reverse-switch evidence: five CasADi steps, singleton state, zero
  guard.  Horizon five was fixed by the preceding seed-2040 engineering smoke
  and is not retuned here.
- Physical horizon: 120 PyBullet steps.

## Paired contracts

1. `permanent_release`: the poisoned raw residual-LQR snapshot executes after
   initial five-step acceptance with no later authority.
2. `resident_one_step_kernel`: the singleton one-step CasADi action kernel
   remains online, with a 41-point action grid and LQR fallback on an empty
   kernel.  This mechanism is retained after its seed-2040 failure.
3. `resident_predictive_simplex`: while the poisoned controller has authority,
   the five-step raw-policy check is repeated at every physical step.  A
   predicted violation causes an immediate, permanent switch to trusted LQR.

All three contracts receive the identical learner snapshot, physical state,
environment seed, initial acceptance result, and horizon within a paired
block.

## Recorded outcomes

- candidate, baseline-admitted, selected, and initially accepted states;
- CasADi 120-step first violation;
- PyBullet first violation;
- one-step interventions and empty kernels;
- predictive forward-switch step and subsequent baseline-control steps;
- mean reward.

The one-step mechanism is diagnostic and has no required success threshold.

## Hard-gate decision

The audit passes only if:

1. every learner seed supplies 24 paired states;
2. every learner seed has at least one initially accepted permanent-release
   physical failure;
3. the resident predictive authority has zero observed physical violations on
   all initially accepted paired states;
4. every permanent-release failure has a paired predictive forward switch no
   later than its release failure step; and
5. row keys, snapshots, initial acceptance, and state/reset fields match
   across all three contracts.

Seed 2040 remains the development learner.  Results for seeds 2041 and 2042
must also be reported separately as the untouched learner confirmation.
