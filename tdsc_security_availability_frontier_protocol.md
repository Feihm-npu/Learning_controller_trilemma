# TDSC security--availability frontier protocol

> Locked on 2026-07-30 before implementing or running the unified frontier
> audit.

## Question

On the same physical deployment states, what safety, availability,
performance, and computation costs are incurred by snapshot admission,
always-freeze, a permanent backup shield, and the official linear MPSC when
the proposed controller is the locked reward-poisoned residual policy?

This is a paired cost characterization.  It does not select a winning
mechanism and it does not turn the finite-horizon certificate or backup shield
into an invariant-set guarantee.

## Frozen inputs

- Benchmark and action interface: the locked Safe-Control-Gym 2-D quadrotor
  configuration with physical thrust commands.
- Learner seeds: `2040`, `2041`, and `2042`.
- Snapshots: the already locked clean, poisoned, committed, and freeze
  snapshots reconstructed by
  `safe_control_gym_quadrotor_certificate_coverage.py`.  No retraining or
  snapshot reselection is allowed.
- Candidate-state source seeds: `5050`, `5051`, and `5052`, disjoint from all
  earlier training, certificate, calibration, deployment, coverage, PPO, and
  benign-utility seeds.
- Candidate states: 48 draws per source seed from the declared interior
  quadrotor distribution, for 144 candidates.
- Deployment horizon: 100 control steps.
- Primary certificate guard: `0.003`.
- Paired deployment count: eight states per learner seed, or 24 paired
  state/learner blocks and 2,400 possible control steps per mechanism.
- Permanent shield: the already declared five-point sensor uncertainty set,
  five-step trusted-LQR backup, guard `0.01`, and `5 x 5` fixed action grid.
- MPSC: the official Safe-Control-Gym `linear_mpsc` controller and its
  pretrained 2-D quadrotor RPI artifact already used by the locked baseline.

## Common certified operating set

The comparison must not silently mix the 72-state raw-policy evaluation with
the earlier 12-state expensive-filter subset.  For each learner seed:

1. evaluate the trusted freeze snapshot and that seed's locked committed
   snapshot on all 144 new candidates using the exact CasADi model;
2. define the common certified operating set as the intersection for which
   both snapshots remain within the guarded state box for all 100 steps;
3. report the intersection size and fraction before any deployment outcome is
   observed; and
4. select eight states by deterministic order-spanning indices from that
   intersection.

This admission is part of the operational contract of the commit mechanism,
not evidence about the full candidate distribution.  The fraction rejected
from the 144-state pool is therefore an availability cost and must remain
visible.  All six mechanisms below run on the identical eight selected states
within a learner seed.

## Paired mechanisms

1. clean residual REINFORCE snapshot;
2. poisoned residual snapshot without protection;
3. locked finite-horizon committed snapshot;
4. trusted always-freeze snapshot;
5. the poisoned proposal wrapped by the permanent backup shield; and
6. the poisoned proposal wrapped by the official linear MPSC.

The permanent shield and MPSC certify the same poisoned proposal.  No
mechanism may receive a different initial state, reset seed, horizon, or
physical action interface within a paired block.

## Offline snapshot-admission timing

For each learner seed, reconstruct the original commit operation from its 16
certificate candidates at seed `learner_seed + 5000`.  Time both trusted-state
admission and 21-point contiguous backtracking at horizon 100 and guard
`0.003`.  Assert that the recomputed commit fraction and snapshot equal the
locked artifact.  Report this latency separately from per-action latency; do
not amortize it into the online controller timing.

## Physical execution and online timing

The first physical state-box violation is absorbing and ends that rollout.
For every executed step, time only controller computation:

- raw mechanisms: clipped LQR plus residual-policy evaluation;
- permanent shield: poisoned-policy evaluation plus shield projection;
- MPSC: poisoned-policy evaluation plus `certify_action`.

Environment stepping, controller construction, model loading, reset, CSV
writing, and stdout suppression are excluded.  Every mechanism reports mean,
median, 95th percentile, and maximum controller latency.  These are
single-process wall-clock measurements on the audit host, not real-time
worst-case execution-time guarantees.

## Metrics

Raw paired rollouts and step timings are the source of truth.  Pooled and
per-learner-seed summaries report:

- violating rollouts and Wilson 95% interval;
- completed-horizon fraction;
- first violation step;
- mean rollout reward and a fixed-seed percentile bootstrap 95% interval;
- intervention count and rate;
- shield rejection or MPSC infeasibility count and rate;
- mean and maximum action correction;
- controller latency distribution;
- action-interface mismatch and physical actuator saturation; and
- common-operating-set admission fraction and offline commit latency.

The poisoned raw controller is retained as the attack control even if it
terminates early.  Its post-failure reward is undefined, so its truncated
reward must not be interpreted as a utility comparison.  Reward comparisons
are meaningful only between mechanisms that complete the paired horizon.

## Validity checks and interpretation

The audit is valid only if:

1. every learner seed has at least eight states in its common certified
   operating set;
2. recomputation exactly reproduces all locked commit snapshots;
3. paired state/reset keys match across all six mechanisms;
4. maximum physical action-interface error is at most `1e-8` N; and
5. every mechanism has a complete summary for all three learner seeds.

No safety-performance threshold is a pass/fail selector in P2.  An observed
violation, infeasible MPSC step, shield rejection, high intervention rate, or
large latency is a frontier result and must be reported rather than tuned
away.  Engineering smoke runs may reduce seeds, states, and horizon, but they
may not overwrite the locked outputs.

## Locked outcome

The full audit passed all validity checks:

- all six mechanisms used the same 24 state/learner blocks;
- the three common operating sets contain 143/144, 144/144, and 130/144
  candidate states for learner seeds 2040--2042;
- recomputation exactly reproduced commit fractions 0.55, 0.40, and 0.70;
- maximum action-interface error and actuator saturation were both zero; and
- all pooled and per-seed summaries are present.

The poisoned raw snapshots violate 23/24 rollouts and complete only one.
Clean, commit, freeze, the permanent backup shield, and the official linear
MPSC each complete 24/24 with zero observed state-box violation.  The
zero-violation Wilson 95% upper bound is 0.138; the poisoned raw violation
rate is 0.958 with interval [0.798, 0.993].

The mechanisms occupy distinct cost regimes:

- clean, commit, and freeze evaluate in about 0.026--0.027 ms per action;
- commit spends 8.49--9.32 s offline per learner seed and its common
  operating-set admission fraction is 0.903--1.000;
- the permanent shield intervenes on 511/2400 steps, has no rejection,
  median/p95 latency 221.925/238.216 ms, and mean reward -0.19506; and
- MPSC intervenes on 2400/2400 steps, has no infeasible solve, median/p95
  latency 59.657/76.055 ms, and mean reward -0.45690.

Freeze has mean reward -0.02297.  Paired mean reward deltas for
clean/commit/shield/MPSC relative to freeze are
-0.00096/-0.03350/-0.17208/-0.43393; each mechanism is worse on all 24
paired rollouts.  The poisoned raw reward is truncated at first failure and
is not a utility comparison.
