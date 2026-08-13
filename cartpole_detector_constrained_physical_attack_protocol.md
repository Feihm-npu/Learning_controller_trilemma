# Detector-constrained physical-objective attack smoke protocol

> Locked on 2026-08-10 after R1 completed and before executing this attack.
> The only learner/evaluation pair is the already burned development pair
> `2070/9070`. No new seed namespace is authorized.

## Question

Can a bounded reward-only attacker retain the raw-release physical effect while
hard-satisfying the three frozen scalar-log checks that do not require a
trusted reward source?

This is not a retry of S1 or S2. S1/S2 optimized distance to a fixed harmful
parameter target and produced zero poison-only physical failures. The new
attacker has no parameter target in its objective. At every actual batch it
chooses the reward vector whose exact next learner snapshot best separates the
five-step and 120-step physical contracts on a fixed attacker-owned state set.

## Locked learner and evaluation

- Learner/evaluation seeds: `2070/9070` only.
- Two-parameter Gaussian residual REINFORCE, initialized at zero.
- 12 batches of 8 physical steps.
- `rho=0.005`, `sigma=0.8`, actor learning rate `1.0`, discount `0.97`,
  gradient cap `1.0`, reward-edit budget `2.0`, and the existing learner box.
- Existing 41-point CasADi action filter during adaptation.
- Existing V3 evaluation: 32 baseline-admitted candidate states, 24
  order-spanning states, five-step initial check, and 120-step physical
  deployment, paired with the locked clean 2070 snapshot.
- Resident five-step predictive authority is evaluated unchanged.

The attack may observe the current batch's actor features, exploration noise,
true scalar rewards, terminal flags, and current learner parameters. It may
write only the eight scalar rewards. It receives no future batch, evaluation
seed, evaluation state, or 9070 outcome during training.

## Frozen detector constraints

Load the already frozen seed-2070 calibration artifact by digest. Every logged
reward must satisfy

```
-5.888655463318784 <= logged_reward <= -0.01603442038059298
logged_reward <= 0
abs(reward_delta) <= 2
```

and each logged batch mean must lie inside

```
center = -0.4915801615623531
radius = 2.5533217417018235.
```

Thus known-sign, scalar-envelope, and batch-mean-envelope batch TPR are locked
to zero if implementation checks pass. Trusted recomputation is expected to
detect every nonzero edit and remains an explicit escape condition. No claim
is made against variance, temporal, transition-conditional, or learned
detectors.

If the pointwise box and batch-mean interval have no common feasible vector,
the batch uses the deterministic minimum-distance feasible projection if one
exists; otherwise the experiment stops as an integrity failure. Constraints
are never relaxed.

## Attacker-owned physical objective

Create a separate scoring environment with seed `6070`. Start from the 42
fixed states returned by the pre-existing `deployment_envelope()`, retain only
states on which zero-residual LQR is safe for 120 CasADi steps with guard
`0.0075`, and choose 14 deterministic order-spanning states. At least 12 must
remain. This set is fixed independently of evaluation seed 9070 and is never
changed in response to the smoke outcome.

For each completed learner batch, generate a deterministic candidate pool:

1. all `2^8=256` pointwise lower/upper box corners;
2. 768 uniform box samples from RNG seed `42070 + batch`;
3. the feasible projection of the zero edit;
4. the feasible projection of the original bounded-tanh edit; and
5. the feasible projection of the S2 desired edit with no exact-mean
   requirement beyond the frozen batch-mean envelope.

Every candidate is projected into the pointwise box and, only if needed, onto
the nearest boundary of the allowed batch-sum interval by deterministic scalar
bisection. Duplicate reward vectors may be removed without outcome inspection.

For each candidate, reconstruct the exact standardized REINFORCE gradient,
gradient cap, parameter clip, and effective next snapshot. Score all next
snapshots with vectorized CasADi dynamics on the 14 attacker-owned states.
Select the lexicographic maximum of:

1. whether at least 12 attacker states pass the five-step check;
2. number of five-step-accepted states that violate within 120 steps;
3. worst 120-step safety margin among five-step-accepted states;
4. aggregate early-violation score;
5. number of five-step-accepted states;
6. negative reward-edit L2 norm; and
7. negative original candidate index.

The last two fields make ties deterministic. The selected edit is applied to
the learner, and the process repeats on the next realized batch. This is a
12-batch closed-loop, receding physical-objective attack. It does not simulate
or peek at future batches and is not claimed to be a globally optimal
multi-batch solution.

## Integrity and reporting

For every batch report:

- candidate count and unique next-snapshot count;
- selected edit magnitude and number of changed rewards;
- sign, scalar-envelope, batch-mean, and budget violations;
- independently reconstructed learner reward, gradient, and next-parameter
  errors;
- public-state five-step acceptance, 120-step violations, worst margin, and
  early-violation score; and
- selection latency.

Report the final clean/poison/resident paired contract outcomes on 9070, plus
frozen-detector TPR/FPR. The 9070 state outcomes are used only after training
is complete.

## Hard gate and stop rule

The 2070 smoke passes only if:

1. every batch satisfies all frozen detector constraints and learner
   reconstruction errors are at most `1e-10`;
2. adaptation has zero physical constraint violations and all reward edits
   respect budget `2`;
3. at least one batch contains a nonzero edit;
4. known-sign, scalar-envelope, and batch-mean-envelope batch TPR are all zero;
5. at least 12 evaluation states pass the five-step poisoned-snapshot check;
6. poisoned raw release has at least one poison-only physical failure;
7. resident authority has zero physical failures and switches no later than
   each paired poisoned-release failure; and
8. pairing integrity holds.

If any integrity condition fails, diagnose the implementation without changing
the attack. If integrity passes but no poison-only failure occurs, close R2 as
insufficient physical effect. In either case do not run 2071/2072 or open a new
seed. A positive smoke permits only a separately locked confirmation decision;
it does not itself authorize new execution.

## Claim boundary

A positive result would show feasibility against three simple scalar-log
checks on one burned seed, not general stealth. A negative result would
strengthen the boundary that these constraints remove the demonstrated
physical effect. Trusted provenance/recomputation and resident authority remain
out-of-scope escape conditions rather than defenses the attack claims to
defeat.
