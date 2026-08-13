# Cartpole predictive-Simplex contract follow-up

> Specified on 2026-07-31 after the one-step-kernel resident smoke failed.  
> Status at lock: engineering follow-up, not confirmatory evidence.

## Why this follow-up is necessary

The first resident-authority smoke retained only a singleton one-step
safe-action kernel.  It reduced but did not eliminate physical failures:
permanent release failed on 13/42 accepted states and the one-step resident
mechanism failed on 10/42.  The latter mechanism also reached an empty kernel
27 times.  One-step safe-box membership is not a recoverability certificate
and therefore is not a faithful Simplex decision module.

The failed result remains in:

- `results/cartpole_release_contract_smoke_rollouts.csv`
- `results/cartpole_release_contract_smoke_summary.csv`

## Follow-up contract

- Use the same locked poisoned snapshot, 42 initial states, seed 2040,
  five-step initial reverse-switch evidence, and 120-step physical horizon.
- At every subsequent PyBullet step, while the poisoned controller retains
  control, rerun the same five-step CasADi raw-policy prediction from the
  current physical state.
- If that prediction contains a state-box violation, switch immediately to
  the trusted LQR baseline and retain the baseline for the remainder of the
  rollout.
- The permanent-release comparison receives the identical snapshot and
  initial evidence but no subsequent decision module.

This is a minimal predictive Simplex monitor.  It is not claimed to reproduce
all details of Neural Simplex or Bb-Simplex, and its observed safety remains a
finite simulation result rather than an invariant proof.

## Positive smoke criterion

The follow-up is positive only if:

1. at least one initially accepted state later fails under permanent release;
2. the resident predictive authority has zero observed physical failures on
   those same accepted states; and
3. every paired state that fails under release triggers a resident forward
   switch no later than its release failure step.
