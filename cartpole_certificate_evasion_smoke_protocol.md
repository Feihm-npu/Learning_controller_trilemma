# Gate-aware cartpole certificate-evasion target smoke

> Specified before execution on 2026-07-31.  
> Status at lock: retrospective-mechanism smoke using locked training outputs.

## Question

Does an explicit attacker objective that requires passage of the five-step
reverse-switch gate select the same target policy used by the already locked
reward-only attack, and does the learned snapshot retain both gate passage and
delayed physical failure?

This smoke does not relabel the original target search as preregistered or
claim that its reward perturbations solved a joint continuous gate-evasion
optimization.  It checks whether the locked attack is a valid realization of
an independently specified gate-aware target objective.

## Attacker target set and objective

- Candidate effective residual parameters:
  - gain in `{-18, 0, 18}`;
  - bias in `{-5, 0, 5}`.
- Initial states: the 42 deterministic deployment-envelope states.
- Admission constraint: zero CasADi state-box violations and non-positive
  maximum margin for five steps on all 42 states.
- Lexicographic attack objective among admitted targets:
  1. maximize the number of states violating by 120 steps;
  2. maximize the worst 120-step state-box margin;
  3. maximize the sum of post-gate remaining horizon at first violation.

## Locked evidence

- Learned snapshot and attack target:
  `results/safe_control_gym_reinforce_reward_poisoning.csv`.
- Physical rollouts:
  `results/safe_control_gym_reinforce_reward_poisoning_rollouts.csv`.
- Resident-authority comparison:
  `results/cartpole_predictive_simplex_smoke_summary.csv`.

## Positive criterion

The smoke is positive only if:

1. the explicit gate-aware objective selects the locked attack target;
2. the locked learned snapshot passes the five-step gate on all 42 states;
3. it has at least one delayed CasADi and physical violation by 120 steps; and
4. the paired resident predictive-Simplex smoke has zero physical violations.

