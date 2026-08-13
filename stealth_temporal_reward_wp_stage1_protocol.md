# Stealth temporal-reward WP: locked Stage-1/2 protocol

> Locked on 2026-08-03 before executing the S1 online smoke.  This lock covers
> implementation, offline verification, and burned learner/evaluation seeds
> `2070/9070`, `2071/9071`, and `2072/9072`.  It does not authorize or reserve a
> new confirmation namespace.

## S1 mechanism: exact sparse bounded reward permutation

For each completed eight-step REINFORCE batch with true reward vector `r`, the
attacker enumerates all `8!` permutations and retains exactly those satisfying

1. `max_i |r[perm[i]] - r[i]| <= 2`, and
2. at most four reward positions move.

Identity is always feasible.  For each feasible permutation, the attacker
reconstructs the learner's actual centered and standardized reward-to-go
gradient, applies the locked unit gradient-norm cap and learner parameter box,
and computes the next effective parameters.  It selects the first
lexicographically enumerated permutation minimizing Euclidean distance to the
fixed, pre-existing harmful snapshot

```
(-2.3625524160241205, -5.0).
```

This target was already recorded in
`safe_control_gym_cartpole_reward_direction_diagnostic.py` before this work
package.  It must not be changed in response to S1 results.

The attacker may inspect the completed batch and current learner parameters.
It may return only a reward-delta vector.  It cannot change features,
exploration noise, actions, states, terminal flags, learner gradients,
clipping, optimizer code, or parameters.

## Locked learner and contract configuration

- 12 batches, eight steps per batch;
- `rho=0.005`, Gaussian sigma `0.8`, learning rate `1.0`, discount `0.97`;
- gradient-norm cap `1.0` and the existing learner parameter box;
- 41-point CasADi adaptation filter;
- reward budget `2.0`;
- 32 candidate deployment states and 24 order-spanning states;
- five-step initial admission and 120-step deployment;
- baseline guard margin `0.0075`;
- the locked V3 clean snapshot for the matching learner seed is the paired
  clean comparator;
- clean release, poisoned permanent release, and resident predictive authority
  use the existing paired contract implementation.

## Required S1 invariants

For every batch:

- the logged and true reward multisets agree to `1e-12`;
- reward sum, mean, variance, sign counts, minimum, and maximum agree to
  `1e-12`;
- maximum absolute edit is at most `2 + 1e-12`;
- at most four positions move;
- the recorded selected candidate is the exact first argmin over the feasible
  set;
- replayed learner gradient and chosen next parameters match the core learner
  to `1e-10`.

The offline verification uses only the 96 already recorded clean batches from
seeds `2070--2072` and `2100--2104`.  It reports feasible-set size, whether a
non-identity candidate exists, target-distance improvement, selected move
count, perturbation magnitude, and wall-clock selection latency.  Offline
results do not authorize new seeds.

## Burned-seed execution order and stop rules

### S1-2070 smoke

Run only learner/evaluation pair `2070/9070`.  The smoke passes if:

- every required invariant and reward-budget check passes;
- adaptation has zero physical constraint violations;
- final target distance is strictly lower than the initial target distance;
- at least 12 paired states are initially accepted;
- poison-only raw-release discordance is at least one;
- resident authority has zero physical failures; and
- every poisoned raw-release failure has a switch no later than its failure.

If integrity or target progress fails, stop S1 and diagnose implementation.  If
integrity and progress pass but poison-only discordance is zero, close S1 for
insufficient deployment effect and execute S2 once on `2070/9070`.  Do not tune
the movement cap, target, batch count, budget, learner, or horizon.

### S1 burned extension

Only after the S1-2070 smoke passes, run `2071/9071` and `2072/9072` with the
identical mechanism.  Execute both regardless of the first extension outcome.
S1 passes the burned-seed gate if all integrity conditions hold, resident
authority has zero pooled failures with timely switching, and at least two of
the three burned learner seeds have at least one poison-only raw-release
failure.

If this gate fails, execute only the pre-declared S2 fallback.  No new seed may
be opened in either case until a later protocol freezes the route, detector
suite, confirmation seeds, metrics, and stop rules.
