# Normalized reward-influence geometry smoke

> Specified before execution on 2026-07-31.  
> Status at lock: theorem/implementation consistency smoke.

## Question

For one real Safe-Control-Gym cartpole REINFORCE batch, does the normalized
reward-influence model exactly reconstruct the artifact update, and does the
SOCP support computation upper-bound bounded-reward attacks on every
halfspace of a concrete parameter gate?

## Frozen configuration

- Seed `2040`.
- One clean adaptation batch of eight physical steps.
- Existing learner settings: `rho=0.005`, `sigma=0.8`, actor learning rate
  `1.0`, discount `0.97`, reward budget `2.0`, gradient norm limit `1.0`.
- Gate coordinates: effective residual gain/bias.
- Gate: `parameter_constraints` at the zero cartpole state, future span
  `0.03`, 41-point CasADi action kernel, and zero guard.
- Support solver: CLARABEL with the existing SCS fallback and 40 bisection
  iterations.

## Validity checks

1. The reconstructed normalized gradient matches the artifact gradient to
   absolute error at most `1e-10`.
2. Clean gradient clipping and parameter clipping are inactive.
3. The centered-return norm is bounded away from zero throughout the reward
   box.
4. For every row with a reachable non-negative support, the SOCP witness
   respects the reward budget and its reconstructed halfspace value agrees
   with the reported support within `1e-4`.
5. If no non-negative influence is reachable for a row, the implementation
   reports zero only as a conservative upper bound and does not label it an
   exact witness.

The smoke is positive if all validity checks pass.  Whether the one-batch
reward set crosses the gate is a measured result, not a pass requirement.
