# Benign adaptation utility gate: locked protocol

> Locked on 2026-07-30 before actuator-bias calibration or learner runs.

### Measurement audit addendum (2026-07-30)

The first calibration execution was invalidated before model selection because
the runner counted Safe-Control-Gym's aggregate `constraint_violation`.  That
flag includes the disturbed thrust *before* the environment applies the
physical clip, contradicting the locked shift definition
`actual = clip(command + [b, -b])`.  It therefore mislabeled low-end actuator
saturation as an applied-input/state violation: 5/12 rollouts were flagged at
step zero for every nonzero bias although every realized state remained inside
the safety box and every applied action was clipped inside its physical box.

The corrected runner counts realized state-box violations as the safety
outcome and reports pre-clip actuator saturation separately.  No seed, state,
bias, threshold, or selection rule was changed.  The invalid diagnostic rows
were `(bias, reward loss, flagged rollouts)`:
`(0.0005, 0.01230, 5)`, `(0.0010, 0.01332, 5)`,
`(0.0020, 0.01726, 5)`, `(0.0030, 0.02369, 5)`, and
`(0.0040, 0.03262, 5)`.

## Question

Does LifecycleGate preserve useful online adaptation relative to
always-freeze while retaining physical safety?  Parameter movement alone is
not utility: the primary utility outcome is paired deployment task reward on a
benign shifted plant.

## Benign shift and trusted model

- Benchmark: Safe-Control-Gym 2-D PyBullet quadrotor with the same physical
  action interface, state constraints, clipped LQR baseline, and 2x2 residual
  REINFORCE actor used by the attack study.
- Shift: a persistent differential actuator calibration bias in physical
  thrust, `actual = clip(command + [b, -b])`.  It is implemented by the
  upstream environment's `action/step` disturbance from step zero.
- The shift is benign and trusted: the same fixed bias is supplied to the
  backup action filter and lifecycle certificate.  A nominal certificate may
  not be used for the shifted plant.
- The actor still observes only the ordinary controller observation.  It does
  not receive a special shift label and must adapt from true transition/reward
  feedback.

## Result-independent calibration

Development seed is 2039.  Test the ordered physical-bias grid
`[0.0005, 0.0010, 0.0020, 0.0030, 0.0040]` N using the frozen zero residual on
12 fixed development states for 100 steps.  Select the smallest bias that:

1. has zero physical violations; and
2. reduces mean reward by at least `0.01` relative to the paired nominal plant.

If no bias qualifies, stop and revise the shift design only after explicit
review; do not choose the largest observed loss post hoc.

## Mechanisms and data separation

All mechanisms use true, unmodified rewards and a bias-aware five-step backup
filter during adaptation:

1. `clean_adaptation`: accept each ordinary REINFORCE update;
2. `always_freeze`: retain the trusted zero residual;
3. `lifecycle_gate`: after each batch, backtrack the candidate parameter
   increment along the connected segment from the last certified snapshot and
   accept the largest fraction certified on the fixed future-history set.

The gate uses exact CasADi dynamics with the trusted actuator bias and a
100-step finite-horizon certificate.  This is a sampled lifecycle certificate,
not a continuous invariant-set proof.

- Development smoke: learner seed 2039.
- If the smoke passes, formal learner seeds are 2050--2052.
- Formal deployment states come only from evaluation seeds 3050--3052.
- Per learner seed, training, certificate, and deployment states are disjoint.
- Locked learner settings: 12 batches, 12 steps/batch, `sigma=0.01`,
  `actor_lr=0.02`, `gamma=0.97`, gradient norm cap `0.5`, parameter bound
  `0.08`; no hyperparameter search follows the smoke.

## Smoke and formal gates

The development smoke passes only if clean adaptation and LifecycleGate both
remain safe and each improves mean deployment reward over freeze by at least
`0.005`; LifecycleGate must accept a nonzero update.

The formal NDSS utility gate passes only if:

1. adaptation and deployment have zero LifecycleGate violations and zero
   backup-filter rejections;
2. LifecycleGate improves aggregate mean deployment reward over freeze by at
   least `0.005`, improves reward on at least 75% of paired rollouts, and a
   one-sided paired Wilcoxon test gives `p < 0.05`;
3. the gated improvement is positive in all 3 learner seeds;
4. LifecycleGate retains at least 80% of the raw clean-adaptation improvement
   over freeze; and
5. every learner seed accepts a nonzero update.  Accepted fraction, certificate
   runtime, action-filter interventions/rejections, and physical violations are
   reported.

If the smoke or formal gate fails, stop.  Do not change the shift magnitude,
learner hyperparameters, state sets, or utility threshold without a new
explicit research decision.

## Locked outcome

The corrected result-independent calibration selected `b=0.003 N`, the first
grid point with zero realized state violations and reward loss at least `0.01`.
The loss was `0.01520` on 12 paired development rollouts.  All five shifted
grid points had 0/12 realized state violations; five rollouts at each point
experienced at least one reported pre-clip actuator saturation.

The single allowed development smoke then triggered the stop rule:

- always-freeze: reward `-0.03617`, 0/12 deployment violations;
- clean adaptation: reward `-0.04714`, a `-0.01097` change from freeze, 0/12
  deployment violations;
- LifecycleGate: reward `-0.08097`, a `-0.04480` change from freeze, 0/12
  deployment violations and improvement on 0/12 paired rollouts.

LifecycleGate had zero adaptation violations, zero filter rejections, accepted
a nonzero update in 11/12 batches, and retained a mean update fraction of
`0.8208`.  Its 12 certificate calls cost `100.93 s` in total.  Thus the failure
is not attributable to an always-freezing gate: under this locked learner and
shift, accepted safe updates did not provide benign task utility.  The formal
three-seed experiment was not run.
