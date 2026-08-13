# TDSC trusted-state-anchor characterization protocol

> Locked on 2026-07-30 before implementing or running P3.

## Scope and question

The end-to-end attack corrupts reward logs, not state sensors.  A trusted
state anchor therefore cannot remove that attack channel.  It can change the
state uncertainty under which a poisoned pending snapshot is admitted.  P3
asks:

1. how do trusted-anchor frequency and bounded measurement quality change
   sampled certificate coverage and the fraction of the poisoned pending
   update that can be retained;
2. how many trusted measurements are required over the locked 12 update
   checkpoints;
3. how much exact-model certificate computation is required; and
4. do the resulting final committed snapshots remain safe on new, physically
   deployed PyBullet states?

The experiment characterizes one trusted sensing contract.  It does not claim
that state anchors sanitize corrupted rewards or that an anchor has zero
hardware latency, energy, authentication, or monetary cost.

## Frozen learner and certificate inputs

- Learner seeds: `2040`, `2041`, and `2042`.
- Pending update: the locked final poisoned residual snapshot for each seed;
  no retraining, target reselection, or trace modification is allowed.
- Trusted certificate centers: the original 16 states drawn from
  `learner_seed + 5000`.
- Snapshot admission: the existing 21 fractions from trusted freeze
  `W=0` to the pending snapshot, exact Safe-Control-Gym CasADi dynamics,
  horizon 100, state-box guard `0.003`, and contiguous backtracking.
- The zero-uncertainty reconstruction must exactly reproduce locked commit
  fractions `0.55`, `0.40`, and `0.70` before any anchor result is accepted.

Only altitude `z` and pitch `theta` are placed on the anchor/untrusted-sensor
boundary.  The other four state channels remain trusted and uncorrupted.
This matches the two uncertainty dimensions already declared by the permanent
backup shield and avoids pretending to solve arbitrary full-state secure
estimation.

## Anchor schedule and quality

There are 12 update checkpoints, one after each 12-step adaptation batch.  An
anchor period `P` obtains a trusted measurement at checkpoints
`0, P, 2P, ...`.  The locked periods are:

- `P=1`: 12 anchor calls;
- `P=3`: 4 calls;
- `P=6`: 2 calls; and
- `P=12`: 1 call.

The final checkpoint is batch 11, so its anchor age is `0`, `2`, `5`, or `11`
update intervals.  Two bounded anchor qualities are locked:

- high quality: base error `(epsilon_z, epsilon_theta) =
  (0.001 m, 0.0005 rad)`;
- standard quality: `(0.005 m, 0.002 rad)`.

Between anchors, the justified uncertainty radius grows by
`(0.002 m, 0.001 rad)` per update interval.  Thus the final radius is

`base_error + final_anchor_age * growth`.

These values are a sensitivity grid, not measured specifications of a
particular sensor.  Infrastructure use is reported as calls and calls per
update checkpoint.  Hardware-specific anchor latency/energy remains an
explicit unmeasured cost; certificate latency is measured separately.

## Nested sampled plausible sets

For each certificate center and anchor condition, include the center and the
four `(+-z, +-theta)` corners at every locked condition radius no larger than
that condition in both coordinates.  This makes sampled plausible sets nested
across increasing uncertainty rather than replacing one corner shell with
another.

The trusted freeze snapshot first admits certificate centers for which every
sample remains inside the guarded box.  Contiguous backtracking then retains
the largest safe pending-snapshot fraction over every sample belonging to the
admitted centers.  If no center remains, or no nonzero fraction is safe, the
mechanism fails closed to freeze.  The reported quantities are:

- admitted certificate centers out of 16;
- sampled states per center;
- final retained update fraction and norm;
- whether the result is full freeze; and
- exact-model trajectory count and wall-clock certificate-audit latency.

Because the eight sampled sets are nested and use the same pending snapshot,
the locked implementation evaluates the largest 33-sample-per-center set once
per learner seed and derives every smaller condition from its indexed subset.
It reports that shared exact-model latency and the condition-specific
trajectory count separately.  The shared latency is the cost of this
characterization run, not a claim that every operational condition has the
same latency; condition-specific deployed implementations may exploit their
smaller sets.

These are sampled finite-horizon quantities, not continuous uncertainty-box
or invariant-set guarantees.

## Independent physical deployment

Deployment-state source seeds are `6050`, `6051`, and `6052`, disjoint from
all prior stages.  Draw 48 candidates per source seed.  For each learner seed,
use only the trusted freeze snapshot to form a baseline-safe pool at horizon
100 and guard `0.003`, then select eight deterministic order-spanning states.
Do not pre-admit states using an anchor-conditioned final snapshot.

On the same eight state/reset pairs within each learner seed, deploy:

- the poisoned raw final snapshot;
- always-freeze; and
- all eight anchor-conditioned committed snapshots.

Every rollout is 100 steps and stops at the first realized PyBullet state-box
violation.  Report pooled and per-seed violations, completion, reward,
actuator saturation, and physical action-interface error.  Poisoned raw
reward is truncated and is not a utility comparison.

## Validity and stop rules

The P3 characterization is valid only if:

1. zero-uncertainty recomputation exactly reproduces all three locked commit
   snapshots;
2. every learner seed has at least eight baseline-safe deployment states;
3. all ten mechanisms use identical paired state/reset keys;
4. maximum physical action-interface error is at most `1e-8` N; and
5. for each quality, admitted-center count and retained fraction are
   non-increasing as the anchor period grows over `1, 3, 6, 12`.

If sampled nesting fails to produce monotonic outcomes, stop and diagnose the
implementation.  If all non-reference anchor cells have identical coverage
and retention, retain the result as an uninformative sensitivity boundary and
do not claim that anchors improve availability.  Any physical violation is a
reported outcome, not a reason to remove a state or tune an error radius.

## Locked outcome

All validity checks passed.  Nine independently cached exact-model chunks
cover all 63 learner-seed/fraction cells without overlap, and
zero-uncertainty reconstruction exactly reproduces the three locked commit
snapshots.  All ten mechanisms use the same 24 new physical state/learner
blocks; maximum action-interface error and actuator saturation are zero.

Every anchor condition retains all 16 certificate centers.  For both high and
standard quality:

- periods 1, 3, and 6 retain fractions 0.55/0.40/0.70 for learner seeds
  2040/2041/2042;
- period 12 retains 0.50/0.40/0.65; and
- all committed snapshots have 0/24 physical violations, compared with
  23/24 for poisoned raw and 0/24 for freeze.

Thus lowering trusted calls from 12 to one reduces mean retained fraction
from 0.55 to 0.5167 but does not force full freeze.  The two quality levels
are not distinguishable at the locked 0.05 backtracking resolution.  The
shared exact-model sensitivity latency is 262.23/276.11/262.51 s across the
three seeds; individual condition trajectory counts span
168,000--1,108,800.

Every anchor-conditioned snapshot remains worse than freeze in all 24 paired
reward outcomes.  Mean deltas are -0.01950 for periods 1/3/6 and -0.01445 for
period 12.  This supports only a freshness-dependent certificate-availability
claim.  It does not show learning utility, reward-channel remediation, or a
measured sensor-platform cost.
