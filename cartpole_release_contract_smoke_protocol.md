# Cartpole resident-authority versus permanent-release smoke

> Specified before execution on 2026-07-31.  
> Status at lock: engineering smoke, not confirmatory evidence.

## Question

Can the locked reward-poisoned cartpole snapshot pass a short-horizon
reverse-switch check while producing different physical outcomes solely
because the runtime authority is either retained or permanently removed?

## Frozen inputs

- Snapshot: the `poisoned_action_only_snapshot` pending parameters in
  `results/safe_control_gym_reinforce_reward_poisoning.csv`.
- Learner/environment seed: `2040`.
- Initial states: the 42 deterministic states returned by
  `safe_control_gym_delayed_trigger_attack.deployment_envelope()`.
- Reverse-switch evidence: the exact Safe-Control-Gym CasADi model, five
  steps, singleton initial state, and zero guard.
- Physical deployment: Safe-Control-Gym PyBullet cartpole for 120 steps.
- Resident authority: at every physical step, test the raw residual-LQR action
  against the singleton-state one-step CasADi safe-action kernel on the
  existing 41-point action grid.  Execute the raw action when it lies in the
  kernel interval; otherwise execute the nearest certified grid action.  If
  the kernel is empty, execute the clipped trusted LQR action and record a
  rejection.  The implementation specializes the existing plausible-box
  kernel at `rho=0` to its one unique state instead of evaluating 17 duplicate
  corners; this changes computation only, not the kernel.
- Permanent release: execute the identical raw residual-LQR snapshot without
  the resident authority.

## Outcomes

For each state and contract, record:

- whether the five-step reverse-switch check accepts;
- its maximum model margin and its first predicted violation over 120 steps;
- physical first violation and completed steps;
- resident-authority interventions and empty-kernel fallbacks;
- mean physical reward.

## Go/no-go rule

The contract-gap smoke is positive only if:

1. at least one state is accepted by the five-step check and later violates
   under permanent raw release;
2. the identical accepted state and snapshot have no observed physical
   violation with the authority resident; and
3. the resident authority actually intervenes before or at the time needed to
   prevent that violation.

The result establishes a reproducible contract separation for this finite
smoke.  It does not prove an invariant resident controller and does not yet
establish a gate-aware reward-poisoning attack.
