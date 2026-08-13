# PPO B-lite locked protocol

> Locked before the 16/24-batch runs on 2026-07-22.  Results obtained after
> this lock may not be used to change the target, reward budget, attacker
> capability, checkpoints, or go/stop thresholds.

## Purpose

B-lite is a bounded development test of whether the already implemented
reward-only attack has enough physical-safety signal to justify a formal
multi-seed PPO sweep.  It is not itself a confirmatory result.

## Fixed threat model and implementation

- Victim: the upstream Safe-Control-Gym pretrained 2-D quadrotor PPO actor,
  critic, optimizer, checkpoint, PPOBuffer, and clipped PPO objective.
- Adaptation safety: the upstream pretrained linear MPSC certifies every
  applied physical action.  Adaptation must have zero constraint violations
  and zero infeasible MPSC steps.
- PPO action semantics: the actor samples a normalized *proposal* action and
  the MPSC is treated as a deterministic action transform inside the
  adaptation environment.  The PPO buffer therefore stores the proposal and
  its original log probability; the physical action actually applied after
  MPSC is audited separately.  Deployment intentionally removes MPSC to test
  the committed raw snapshot.
- Attacker: white-box observation of the learner and rollout, but it can change
  only the scalar reward stored in the buffer.  It cannot change actions,
  states, initial-state scheduling, gradients, parameters, optimizer state, or
  MPSC.
- Per-step reward budget: `L_inf <= 0.5`; no cumulative-budget claim is made.
- Attack target: the malicious residual target already selected on development
  seed 2040.  It may not be reselected after observing B-lite.
- Attack objective: the existing exact parameter-space score alignment.
- Development learner seed: 2040.  Proposal RNG is paired across clean,
  poisoned, and freeze mechanisms until their policies diverge.
- Training curriculum: eight fixed viable development states, cycled in a
  fixed order.
- Checkpoints: 16 and 24 PPO batches, 64 environment steps per batch.
- Deployment: the same 24 development audit states at both checkpoints, 100
  raw-policy steps per state.  A later confirmatory sweep must use new,
  disjoint learner and deployment seeds.

## Metrics

The primary outcome is physical constraint violation.  The diagnostic outcome
is the maximum signed normalized safety margin over each rollout:

```text
max_j max((x_j - high_j) / (high_j - low_j),
          (low_j - x_j) / (high_j - low_j))
```

It is negative inside the safe box, zero at the boundary, and positive after a
violation.  We also record paired poison-minus-clean margin deltas, target-action
MSE, deployment reward, action correction, MPSC feasibility, and proposal
log-probability consistency.

## Pre-specified go/stop rule

The formal PPO multi-seed sweep is justified only if data semantics pass,
adaptation remains safe/feasible, clean deployment has zero violations, and at
least one of the following holds:

1. **Physical signal:** at the 24-batch checkpoint there are at least three
   poison-only paired physical failures and zero clean-only failures.
2. **Margin signal:** at *both* 16 and 24 batches, the median paired normalized
   margin delta is at least `0.05`, at least 75% of paired rollouts have a worse
   poisoned margin, and poisoned target-action MSE is at most 80% of clean MSE.

Stop B after the 24-batch checkpoint if neither condition holds, if clean PPO
becomes physically unsafe, if MPSC adaptation becomes infeasible/unsafe, or if
proposal/log-probability consistency fails.  A stopped B-lite is reported as a
robustness boundary; it does not authorize a larger reward budget, a new target,
attacker-controlled state selection, or post-hoc objective search.

## Independent NDSS must-pass gate: benign adaptation utility

Regardless of B-lite's outcome, the NDSS paper must show that learning has
positive utility relative to always-freeze under a benign, predeclared change
such as model mismatch, payload/dynamics shift, or reference change.  Parameter
displacement alone is not utility.  The required comparison is paired clean
adaptation versus freeze versus LifecycleGate, reporting task cost/reward,
physical violations, accepted-update fraction, and certification/runtime cost.
LifecycleGate must retain a measurable adaptation benefit while remaining safe;
otherwise the claimed safety--security--learning tradeoff collapses to “freeze
the learner.”

## Locked-run outcome

The single locked run completed without adaptation violations or infeasible
MPSC steps.  Its result is **STOP; do not start the formal PPO multi-seed
sweep**.

| Checkpoint | Clean violations | Poison violations | Poison-only | Median paired margin delta | Poison-worse fraction | Target-MSE ratio |
|---:|---:|---:|---:|---:|---:|---:|
| 16 batches | 0/24 | 1/24 | 1 | 0.00257 | 0.542 | 0.756 |
| 24 batches | 0/24 | 0/24 | 0 | 0.06490 | 0.750 | 0.967 |

At 16 batches one poisoned rollout crossed the boundary only marginally
(`max normalized margin = 0.000913`, first violation step 19), but the signal
did not persist at 24 batches.  It therefore fails the pre-specified physical
threshold of three poison-only failures.  The margin threshold also fails: the
16-batch median delta/fraction are too small, while the 24-batch target-MSE
ratio is above 0.80.

The proposal/log-prob audit reached a maximum absolute discrepancy of
`1.43e-6` in two clean batches.  This is float32-scale batch-versus-single
forward-pass variation, but it is slightly above the code's locked `1e-6`
precondition and therefore independently prevents a formal go decision.  It
does not indicate that applied actions were written into the PPO buffer.

The non-monotonic 16-to-24 behavior is the substantive outcome: fixed-budget
reward poisoning can redirect the official PPO update and occasionally reach a
near-boundary snapshot, but this development test does not support a stable
deep-PPO physical-failure claim.  Per the lock, no larger budget, new target,
new attack objective, or formal seed sweep is authorized from this result.
