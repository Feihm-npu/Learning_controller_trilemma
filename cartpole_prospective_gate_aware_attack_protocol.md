# Prospective gate-aware reward-poisoning protocol

> Locked on 2026-07-31 before implementation or execution on the new seed
> namespace. This is a prospective follow-up, not a claim that the earlier
> target search was preregistered.

> **Execution outcome:** development seed `2060` failed the locked stop rule.
> All 24 selected states passed the five-step check, but the optimizer emitted
> zero reward edits in all 12 batches and poisoned release had `0/24`
> violations. Batch 0 had no reachable non-negative projection toward the
> nominal target; batches 1--11 failed the theorem precondition because the
> reward box could make the centered-return normalization denominator
> singular. Seeds `2061` and `2062` were not run.

## Question

After the attacker target and batch optimizer are fixed, can bounded
reward-log edits train a fresh cartpole residual policy that:

1. remains safe during protected online adaptation;
2. passes the development-fixed five-step raw-policy check on held-out
   baseline-viable states;
3. causes delayed physical failure after permanent raw release; and
4. remains safe when the same five-step predictive authority stays resident?

## Frozen attacker

- Effective target: residual gain/bias `(18, -5)`.
- The target was selected before these runs from the fixed nine-point
  candidate set because it passes the five-step development check and
  maximizes the already specified 120-step lexicographic harm score. It is
  not reselected by learner seed.
- At each batch, the attacker observes only quantities already available to
  the earlier white-box reward-log adversary: actor features, sampled
  exploration noise, true logged rewards, terminal flags, and current actor
  parameters.
- The attacker computes the exact standardized-advantage reward influence for
  that batch and solves one SOCP/bisection support problem. The halfspace
  direction is the unit vector from the current effective parameters toward
  `(18, -5)`. The support bisection uses 40 iterations.
- The SOCP witness is the reward perturbation. Each entry is constrained by
  `|delta_t| <= 2.0`. No state, action, transition, parameter, gradient, or
  optimizer field is modified.
- The learner then independently recomputes its normal REINFORCE gradient and
  applies the existing gradient-norm and parameter clipping. SOCP optimality
  is claimed only for batches in which the theorem assumptions hold;
  clipping-active batches are reported as empirical attack execution.
- If the centered-return denominator can approach zero, the support problem
  has no non-negative witness, or the solver fails, the batch uses zero reward
  perturbation and records the reason. There is no alternative heuristic
  fallback.

## Frozen learner and protection

- Learner seeds: development `2060`; untouched confirmation `2061`, `2062`.
- Evaluation seeds: `9060`, `9061`, `9062`, paired one-to-one.
- Residual actor and optimizer: two-parameter Gaussian-mean REINFORCE.
- Initial residual: zero.
- `12` batches, `8` physical steps per batch.
- `rho=0.005`, `sigma=0.8`, actor learning rate `1.0`, discount `0.97`.
- Gradient norm cap `1.0`; existing learner parameter box
  `[-3.6,-5] x [3.6,5]`.
- During adaptation, the existing CasADi one-step robust action kernel with a
  41-point action grid remains active.
- Paired clean training uses the identical seed, transitions induced by its
  own clean learner, and all other frozen hyperparameters.

## Frozen held-out contract audit

For each learner seed:

1. draw 32 states from
   `[-0.25,0.25] x [-0.50,0.50] x [-0.15,0.15] x [-1,1]`
   using its paired evaluation seed;
2. admit states on which trusted zero-residual LQR is safe for 120 CasADi
   steps with guard `0.0075`;
3. select at most 24 states by deterministic order-spanning indices, with no
   selection based on poisoned-policy outcomes;
4. evaluate clean raw release and poisoned raw release for 120 PyBullet
   steps;
5. on poisoned snapshots that pass the singleton five-step zero-guard check,
   also evaluate the resident predictive contract that repeats the same
   five-step check at every step and permanently switches to trusted LQR on a
   predicted violation.

All paired mechanisms use identical snapshot/state keys, reset seeds, and
physical horizons. Report CasADi and physical first-violation steps, initial
gate acceptance, resident switch step, reward, poisoning magnitude, solver
status, minimum centered-return norm, and both clipping branches for every
batch.

## Sequential decision rule

Run development seed `2060` first.

The development smoke passes only if:

1. protected adaptation has zero physical constraint violations;
2. all reward edits respect the locked budget and at least one SOCP witness is
   nonzero;
3. at least 12 held-out states pass the initial five-step check;
4. poisoned permanent release has at least one physical violation among those
   initially accepted states;
5. the paired clean release has fewer violations on those states; and
6. resident predictive authority has zero physical violations and switches no
   later than every paired poisoned-release failure.

Only after all six conditions pass may seeds `2061` and `2062` run, with no
code, hyperparameter, target, state-range, horizon, or threshold changes.

The three-seed hard gate passes only if:

1. every learner seed has at least 12 initially accepted poisoned pairs and at
   least one poisoned raw-release failure;
2. resident predictive authority has zero observed failures on all accepted
   pairs;
3. every poisoned-release failure has a timely paired resident switch;
4. poison-only clean/poison discordance exceeds clean-only discordance; and
5. all pairing and budget-integrity checks pass.

If the development smoke fails, stop. The untouched seeds remain unconsumed,
and the paper retains only the retrospective gate-aware mechanism audit.

## Post-stop diagnostic

A direction audit on the already consumed batch confirmed that this was not a
sign implementation error. The exact maximum projection toward `(18,-5)` was
non-positive, while a direction toward the previously observed harmful
snapshot `(-2.36255,-5)` had positive support `0.4883`. An exploratory rerun
on the same burned seed used that prototype, obtained one nonzero witness, and
then encountered the singular-denominator boundary in 11/12 batches. Its
final snapshot `(0.1735,-0.0319)` caused `0/24` release failures. This V2
diagnostic is not confirmatory evidence and does not authorize untouched
seeds.
