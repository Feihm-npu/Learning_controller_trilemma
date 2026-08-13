# Stealth temporal-reward WP: locked S2 fallback protocol

> Locked on 2026-08-03 after S1-2070 produced no raw-release effect and before
> executing S2.  S1's integrity and target-progress checks passed, but its
> poison-only discordance was zero.  This file resolves the already declared S2
> projection algorithm; it does not alter S1 or authorize a new seed.

## Desired edit and projection

Use the same pre-existing fixed effective target as S1,
`(-2.3625524160241205, -5.0)`.  For each completed eight-step batch, form the
same target-directed desired edit used by the bounded-`tanh` family:

```
desired_i = 2 tanh(noise_i * (target_mean_i-current_mean_i))
```

with temperature `1.0`.  Let `r` be the true reward vector and use the already
frozen clean-seed-2070 scalar envelope

```
L = -5.888655463318784
U = -0.01603442038059298.
```

Choose the unique Euclidean projection of `desired` onto

```
max(-2, L-r_i) <= delta_i <= min(2, U-r_i)
sum_i delta_i = 0.
```

Compute it by deterministic scalar bisection of
`delta_i = clip(desired_i-lambda, lower_i, upper_i)` for 100 iterations.  The
identity edit is feasible for the locked S2-2070 smoke; infeasibility is an
integrity failure, not permission to relax the constraints.

## Locked execution and invariants

All learner, contract, target, batch, budget, horizon, state, and comparator
settings remain those in `stealth_temporal_reward_wp_stage1_protocol.md`.
Run only `2070/9070` first.

Every batch must satisfy, to `1e-10`:

- reward budget and frozen scalar envelope;
- no positive logged reward;
- zero-sum reward edit and equality of logged/true batch means;
- agreement between the independently reconstructed projected edit and the
  edit consumed by the learner;
- learner raw gradient and next-parameter agreement.

The S2-2070 smoke uses the S1 smoke deployment gate: strict target-distance
progress, at least 12 poison-accepted paired states, at least one poison-only
raw-release failure, zero resident failures, timely switching, zero adaptation
violations, reward-budget integrity, and pairing integrity.

If the S2-2070 smoke has no poison-only failure, close this work package without
running S2 on `2071/2072` or opening new seeds.  If it passes, execute both
burned extension seeds unchanged and require raw-release effect in at least two
of the three burned seeds before any new confirmation protocol is considered.
