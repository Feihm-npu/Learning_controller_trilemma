# TDSC certificate coverage and model-mismatch protocol

> Locked on 2026-07-30 before running the coverage audit.

## Question

How often does the finite-horizon CasADi certificate agree with independent
PyBullet deployment on states that were **not** pre-admitted by that
certificate?  The primary risks are:

1. false acceptance: CasADi certifies a snapshot/state pair that violates the
   realized PyBullet state box within the same horizon;
2. false rejection: CasADi rejects a pair that remains physically safe;
3. vacuity: zero false acceptance obtained only by certifying almost no
   states.

This audit characterizes a sampled finite-horizon certificate.  It cannot
establish continuous-state invariance.

## Frozen inputs

- Benchmark: Safe-Control-Gym 2-D quadrotor with the physical thrust
  interface and state box already used by the locked reward-poisoning audit.
- Snapshots: reconstruct from the final per-batch weights in
  `results/safe_control_gym_quadrotor_reinforce_reward_poisoning_sweep_traces.csv`
  and the locked commit fractions in
  `results/safe_control_gym_quadrotor_reinforce_reward_poisoning_sweep.csv`;
  assert every reconstructed norm against the corresponding locked summary.
  The summary stores norms rather than weight components, so both original
  artifacts are required.  Do not retrain or reselect snapshots.
- Learner seeds: 2040, 2041, 2042.
- Mechanisms per learner seed: clean REINFORCE, poisoned action-only,
  poisoned commit gate, and always-freeze.
- Coverage-state source seeds: 4050, 4051, 4052.  These are disjoint from
  training, certificate, calibration, deployment, PPO, and benign-utility
  seeds used so far.
- Draw 48 states per coverage seed from the already declared interior
  quadrotor distribution, for 144 states total.  Do not apply CasADi
  admission or spread selection.
- Horizons: 20, 50, and 100 control steps.
- Guard margins: 0, 0.001, 0.003, 0.005, and 0.01 in physical state units.
- The primary pre-existing certificate configuration is horizon 100,
  guard 0.003.  The other grid cells are characterization, not a
  post-hoc selector.

## Paired execution

For every learner seed, mechanism, and coverage state:

1. propagate the raw snapshot with the exact Safe-Control-Gym CasADi
   discrete model and clipped physical actions;
2. run the same raw snapshot from the same state in independent PyBullet;
3. record first violation, maximum margin, executed steps, reward, and maximum
   action-interface error;
4. derive safe/unsafe labels for all locked horizons;
5. for every guard margin, compare CasADi certification against the PyBullet
   state-box outcome at the same horizon.

PyBullet safety uses the realized state box.  Requested actions are clipped to
the declared physical action box before execution.  Input saturation and
interface mismatch are reported separately rather than conflated with state
failure.

## Metrics

Each mechanism/horizon/guard cell reports:

- evaluated snapshot-state pairs;
- certificate coverage and rejection rate;
- PyBullet safe rate;
- true acceptance, false acceptance, true rejection, and false rejection;
- false-acceptance rate among certified pairs;
- false-rejection rate among rejected pairs;
- worst PyBullet normalized state margin among certified pairs;
- maximum physical action-interface error.

Per learner-seed rows and pooled rows must both be retained.  Raw paired rows
are the source of truth.

## Hard gate and interpretation

The existing sampled-certificate soundness claim passes only if the primary
configuration:

1. has zero false acceptances over all certified snapshot/state pairs;
2. has maximum action-interface error at most `1e-8` N; and
3. certifies at least 25% of state pairs for every clean, commit, and freeze
   mechanism (poisoned action-only may legitimately have lower coverage).

If any condition fails:

- stop calling the current commit certificate sound under PyBullet model
  mismatch;
- retain the attack and runtime-filter evidence, but describe commit as a
  sampled admission heuristic until a robust mismatch margin or reachable-set
  certificate is specified and locked before execution and passes a new audit;
- do not remove failing states, choose another grid cell, or enlarge the guard
  after observing this audit.

False rejection has no pass threshold; it is an availability cost and must be
reported.  A successful primary cell does not authorize an invariant-set
claim.

## Locked outcome

The primary `H=100`, guard `0.003` configuration passed:

- 1728 snapshot/state pairs were evaluated without certificate pre-admission;
- 1293 pairs were certified and none was a false acceptance;
- pooled clean/commit/freeze coverage was
  `0.9861/0.9444/1.0000`, above the locked 25% floor;
- the poisoned action-only snapshot had coverage `0.0625`, correctly rejecting
  almost all of its physically unsafe pairs;
- maximum physical action-interface error and actuator saturation were both
  zero.

Across the 432 pairs per mechanism, PyBullet violations within 100 steps were
clean `6`, poisoned action-only `403`, commit `21`, and freeze `0`.  At the
primary configuration, false rejections were clean `0`, poisoned action-only
`2`, commit `3`, and freeze `0` (5/435 rejected pairs in total).  Thus the
certificate rejected every observed unsafe pair while conservatively
rejecting five safe pairs.

The characterization grid also exposes why the guard is part of the
certificate contract.  With guard zero, the poisoned action-only snapshot had
1, 2, and 1 false acceptances at horizons 20, 50, and 100.  Every locked
positive guard (`0.001`--`0.01`) removed observed false acceptance, with
increasing false rejection at larger guards.  The primary guard `0.003` was
the pre-existing commit configuration and was declared before this audit; it
was not selected from this grid.

Total vectorized CasADi and PyBullet runtimes were `70.95 s` and `181.33 s`.
This result supports the sampled guarded certificate on the audited
distribution and horizon only; it remains insufficient for a continuous-state
invariance claim.
