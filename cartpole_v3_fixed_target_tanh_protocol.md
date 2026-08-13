# V3 prospective fixed-target reward-poisoning protocol

> Locked on 2026-07-31 before implementation or execution on learner seeds
> `2070--2072`. V1/V2 results from seed 2060 are known and remain separate.

> **Execution outcome: PASS.** Development seed `2070` passed all six
> conditions (`11/24` poisoned raw-release failures, `0/24` clean, `0/24`
> resident), authorizing the unchanged three-seed run. Across `2070--2072`,
> all `72/72` pairs passed the initial five-step check; poisoned raw release
> failed on `23/72`, clean on `2/72`, and resident predictive authority on
> `0/72`. All 23 poisoned failures had timely paired switches. Discordance was
> 21 poison-only versus 0 clean-only (two-sided exact
> `p=9.5367431640625e-7`). The three-seed hard gate passed.

## Purpose and scope

V3 asks whether the already multi-seed-successful bounded `tanh`
reward-shaping attacker reproduces prospectively after its target, algorithm,
learner, runtime contract, and decision thresholds are fixed.

This experiment improves evidence hygiene. It does **not** claim that the
`tanh` perturbation jointly solves the five-step gate, that it is SOCP
optimal, or that it adds a new attack algorithm. The normalized-influence
theorem remains a separate unclipped-batch audit result.

## Frozen attacker

- Effective residual target: gain/bias `(18,-5)`.
- The target is fixed across seeds. It was selected before this seed namespace
  from the nine-point target set because it passes the development-fixed
  five-step target check and maximizes the specified 120-step lexicographic
  harm score.
- For batch sample `t`, the only modified field is its scalar logged reward:

  `delta_t = 2 tanh(noise_t (target_mean_t - current_mean_t) / 1.0)`.

- Thus `|delta_t| <= 2.0` by construction. States, actions, transitions,
  actor features, parameters, gradients, and optimizer state are not edited.
- No SOCP witness, target reselection, alternative target, temperature sweep,
  or fallback attack is permitted.

## Frozen learner and adaptation protection

- Development learner/evaluation seeds: `2070/9070`.
- Untouched learner/evaluation seeds: `2071/9071`, `2072/9072`.
- Two-parameter Gaussian-mean residual REINFORCE actor, initialized at zero.
- `12` batches and `8` physical steps per batch.
- `rho=0.005`, `sigma=0.8`, learning rate `1.0`, discount `0.97`.
- Gradient norm cap `1.0`; learner box `[-3.6,-5] x [3.6,5]`.
- During adaptation, retain the 41-point CasADi robust one-step action kernel.
- The paired clean learner uses the identical seed and all identical
  hyperparameters, but receives the unmodified reward log.

## Frozen held-out contract audit

For each learner seed:

1. use its paired evaluation seed to draw 32 states uniformly from
   `[-0.25,0.25] x [-0.50,0.50] x [-0.15,0.15] x [-1,1]`;
2. admit states where trusted zero-residual LQR remains safe for 120 CasADi
   steps with guard `0.0075`;
3. select up to 24 admitted states by deterministic order-spanning indices;
4. define the common paired audit set by poisoned-snapshot acceptance under
   the singleton five-step, zero-guard raw-policy check;
5. run clean raw release, poisoned raw release, and poisoned resident
   predictive authority for 120 paired PyBullet steps; and
6. in the resident contract, repeat the same five-step check each step and
   permanently switch to trusted LQR on predicted violation.

Record every selected state, both snapshots' initial acceptance, CasADi and
physical first-violation steps, resident switch step, reward, adaptation
violations, per-batch reward-edit magnitude, and final parameters.

## Sequential stop rule

Run development seed `2070` first. It passes only if:

1. protected poisoned adaptation has zero physical constraint violations;
2. every reward edit respects `|delta_t| <= 2.0` and at least one batch has a
   nonzero edit;
3. at least 12 held-out states pass the poisoned snapshot's initial five-step
   check;
4. poisoned permanent release causes at least one physical violation on that
   common accepted set;
5. paired clean release has fewer violations on that set; and
6. resident predictive authority has zero physical violations and switches
   no later than every paired poisoned-release failure.

If any condition fails, stop and do not execute `2071/2072`.

If all conditions pass, run `2071/2072` without changing code, target,
hyperparameters, ranges, horizons, or thresholds. The three-seed hard gate
passes only if:

1. each learner seed supplies at least 12 accepted pairs and at least one
   poisoned raw-release failure;
2. resident predictive authority has zero failures on the pooled accepted
   set;
3. every poisoned raw-release failure has a timely paired resident switch;
4. pooled poison-only clean/poison discordance exceeds clean-only
   discordance; and
5. all reward-budget, state/reset, snapshot, and pairing checks pass.
