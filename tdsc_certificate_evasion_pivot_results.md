# Certificate-evasion pivot: formal audit and smoke results

> Date: 2026-07-31  
> Decision: **PASS the pre-specified multi-seed contract hard gate; enter
> manuscript claim surgery.**  
> Paper status: the contract result is now stable enough to replace the old
> broad lifecycle-novelty story, subject to the clipping and retrospective
> attack-design limits below.

## Bottom line

The proposed novelty pivot survived its first go/no-go, with one important
mathematical correction and one informative failed defense:

1. The existing learners standardize advantages, so bounded rewards do **not**
   induce the affine parameter zonotope originally hypothesized.
2. Before gradient and parameter clipping, the exact object is a normalized
   reward-influence set: a centered reward-to-go zonotope is mapped to the unit
   sphere and then through the policy score matrix.
3. A real cartpole batch exactly matches this model, and positive halfspace
   support can be computed by second-order-cone feasibility and bisection.
4. An explicit gate-aware target objective selects the already locked attack
   target.  The learned snapshot passes a five-step reverse-switch check on
   42/42 states but fails after permanent release on 13/42 in both CasADi and
   PyBullet.
5. Retaining only a one-step action kernel is insufficient: it still fails on
   10/42 states.
6. Retaining a repeated five-step predictive Simplex decision module prevents
   every observed failure, switching exactly on the 13 states that fail after
   permanent release.

This is the desired closest-work separation:

> Reverse switching is safe because runtime authority remains resident.  The
> same finite evidence is not a sound certificate for permanently removing
> that authority.

## 1. Correct reward-to-update geometry

For a fixed batch with score rows \(S\), reward-to-go operator \(H\), and
centering matrix \(C\), define

\[
y(\delta)=CH(r+\delta), \qquad \|\delta\|_\infty\le\epsilon.
\]

The artifact standardizes centered advantages.  When their standard deviation
is nonzero, the unclipped gradient is

\[
g(\delta)
=
\frac{1}{\sqrt{T}}S^\top
\frac{y(\delta)}{\|y(\delta)\|_2}.
\]

Thus the attack set is not
\(\theta_{\mathrm{clean}}+B[-\epsilon,\epsilon]^T\).  It is the image of an
affine reward zonotope under normalization and the score map:

\[
\mathcal U_\epsilon(\theta)
=
\left\{
\theta+\frac{\alpha}{\sqrt T}S^\top
\frac{CH(r+\delta)}{\|CH(r+\delta)\|_2}
:
\|\delta\|_\infty\le\epsilon
\right\},
\]

subject to inactive gradient and parameter clipping.

For a gate-coordinate map \(P\) and halfspace \(a^\top P\theta\le b\), let

\[
q=\frac{\alpha}{\sqrt T}SP^\top a.
\]

The positive support is obtained by maximizing

\[
\frac{q^\top y}{\|y\|_2}.
\]

For a fixed candidate value \(t\ge0\), reachability of support at least \(t\)
is the second-order-cone feasibility problem

\[
\|\delta\|_\infty\le\epsilon,\qquad
t\|CH(r+\delta)\|_2
\le
q^\top CH(r+\delta).
\]

Bisection therefore gives the exact positive support.  If no non-negative
support is reachable, zero remains a sound conservative upper bound but is
not labeled as an attainable witness.

Implementation:

- `reward_certificate_geometry.py`
- `test_reward_certificate_geometry.py`
- `safe_control_gym_cartpole_reward_geometry_smoke.py`

## 2. Real-batch geometry smoke

Locked smoke:

- seed 2040;
- eight real Safe-Control-Gym adaptation steps;
- reward budget 2.0;
- 22 halfspaces from the center-state finite parameter gate.

Outcome:

| Check | Result |
|---|---:|
| Gradient reconstruction error | \(2.78\times10^{-17}\) |
| Clean gradient norm | 0.196789 |
| Gradient clipping active | no |
| Parameter clipping active | no |
| Minimum centered-return norm over reward box | 7.993864 |
| Maximum exact witness/support error | \(1.07\times10^{-9}\) |
| Minimum robust halfspace margin for this batch | 4.598004 |
| Halfspaces crossed by one batch | 0/22 |
| Smoke decision | pass |

The last result is a useful negative boundary: the first reward-poisonable
batch cannot by itself leave this local parameter gate.  The physical attack
arises through accumulated updates, not a fabricated one-step crossing.

Primary outputs:

- `results/cartpole_reward_geometry_smoke_rows.csv`
- `results/cartpole_reward_geometry_smoke_decision.csv`

## 3. Gate-aware target smoke

The independent gate-aware target objective was:

1. require zero five-step CasADi violations and non-positive maximum margin on
   all 42 deployment states;
2. among accepted targets, maximize 120-step violating states, worst margin,
   and post-gate failure score.

Over the locked \(3\times3\) effective-parameter target grid, it selected

\[
(k,b)=(18,-5),
\]

exactly matching the target recorded before this novelty pivot in the locked
reward-poisoning artifact.

The actual learned reward-only snapshot is

\[
(k,b)=(-2.362552416,-5).
\]

It produces:

| Outcome | Count |
|---|---:|
| Five-step reverse-switch acceptance | 42/42 |
| 120-step CasADi violations | 13/42 |
| 120-step PyBullet violations | 13/42 |
| Predictive-resident physical violations | 0/42 |

This is retrospective mechanism validation, not a new confirmatory attack:
the original reward poison did not explicitly solve the newly written
gate-aware objective.  The result establishes that its locked target and
learned snapshot satisfy that objective.

Primary outputs:

- `results/cartpole_certificate_evasion_target_candidates.csv`
- `results/cartpole_certificate_evasion_smoke_decision.csv`

## 4. Resident-authority comparison

### Failed one-step resident mechanism

The first resident implementation retained a one-step singleton-state action
kernel.  It was not a recoverability certificate:

| Contract | Accepted | Physical violations | Interventions | Empty kernels |
|---|---:|---:|---:|---:|
| Permanent release | 42/42 | 13/42 | 0 | 0 |
| One-step resident kernel | 42/42 | 10/42 | 53 | 27 |

This negative result is retained.  It prevents an overbroad claim that any
resident action filter is a valid escape condition.

Outputs:

- `results/cartpole_release_contract_smoke_rollouts.csv`
- `results/cartpole_release_contract_smoke_summary.csv`

### Successful predictive Simplex mechanism

The corrected resident contract repeated the same five-step raw-policy
prediction at every physical step.  When the prediction first included a
state-box violation, it switched to trusted LQR for the remainder of the
rollout.

| Contract | Initially accepted | Physical violations | Forward switches | Median switch/failure step |
|---|---:|---:|---:|---:|
| Permanent release | 42/42 | 13/42 | 0 | failure 10 |
| Resident predictive authority | 42/42 | 0/42 | 13 | switch 6 |

Pair-level audit:

- every release-failure state triggered a resident forward switch;
- every switch occurred no later than the paired release failure;
- no resident switch occurred on the other 29 states;
- the resident contract used 988 LQR-controlled steps after switching.

Outputs:

- `results/cartpole_predictive_simplex_smoke_rollouts.csv`
- `results/cartpole_predictive_simplex_smoke_summary.csv`

## 5. Novelty consequence

The new defensible claim is no longer that controller updates, reverse
switching, or certificate lifecycle are generally new.  It is:

> A reward-only attacker can steer protected online adaptation toward a target
> that passes a finite reverse-switch contract yet fails after permanent
> authority removal.  Repeating the same decision rule under resident
> predictive authority converts those latent failures into timely forward
> switches.  Therefore reverse-switch evidence is contract-bound and cannot be
> transferred to permanent raw release.

The normalized reward-influence analysis supplies an attack-specific bridge
between corruptible rewards and certificate halfspaces.  The contract smoke
supplies the direct Neural-Simplex/Damare comparison requested by the novelty
review.

## 6. Multi-seed contract hard gate

The confirmatory audit fixed the five-step reverse-switch horizon developed on
seed 2040, reconstructed the already locked poisoned snapshots for learner
seeds 2040--2042, and evaluated disjoint state pools generated with seeds
8040--8042.  Each learner seed contributed 24 order-spanning states selected
from 32 baseline-admitted candidates.  No horizon or guard was tuned per seed.

One state for learner seed 2041 was rejected by the initial five-step check,
leaving 71 accepted state--snapshot pairs:

| Contract | Accepted pairs | Physical failures | Interventions / switches |
|---|---:|---:|---:|
| Permanent raw release | 71 | 19 | 0 |
| One-step resident action kernel | 71 | 14 | 79 interventions; 41 empty kernels |
| Five-step resident predictive authority | 71 | 0 | 19 forward switches |

The permanent-release failures occur in every learner seed: 6/24, 3/23, and
10/24.  Resident predictive authority switches on exactly those 19 paired
states and prevents every observed failure.  Each switch occurs four physical
steps before the corresponding raw-release failure.  On the two learner seeds
not used to develop the horizon, permanent release fails on 13 states and the
resident mechanism fails on none.

This passes the locked hard gate:

- permanent release fails in all 3/3 learner seeds;
- resident predictive authority has 0/71 failures;
- all 19 raw-release failures have a timely paired switch;
- all 216 mechanism rows have unique and complete pairing keys.

Primary outputs:

- `cartpole_multiseed_release_contract_protocol.md`
- `results/cartpole_multiseed_release_contract_rows.csv`
- `results/cartpole_multiseed_release_contract_summary.csv`
- `results/cartpole_multiseed_release_contract_decision.csv`

The result is confirmatory for the deployment-contract separation, not for the
attack target itself.  The five-step horizon is development-fixed rather than
pristine, and the predictive monitor is a minimal repeated finite-horizon
decision module rather than a complete Neural Simplex or barrier-based Simplex
implementation.

## 7. Remaining theory and attack-design gates

### P0: theory scope under clipping

The exact support theorem currently covers batches for which advantage
normalization is active and gradient/parameter clipping are inactive.

- Some cartpole batches trigger gradient clipping.
- Every locked quadrotor REINFORCE batch reaches the gradient norm cap.

The manuscript must either derive the radial-clipping branch or scope the
exact theorem to unclipped batches and treat clipped learners empirically.  It
must not call the current result an exact characterization of the entire
multi-batch quadrotor attack.

### P1: fresh gate-aware training — locked smoke failed

The locked attack is consistent with the independently specified gate-aware
objective, but was not originally optimized under that constraint.  A stronger
follow-up would:

1. choose the gate-aware target before training on fresh seeds;
2. use the normalized reward-influence solver or its clipped extension to
   choose reward perturbations batch by batch; and
3. test gate passage and permanent-release failure on held-out states.

This was attempted after the multi-seed contract audit passed.  The protocol
fixed target `(18,-5)`, a batchwise exact normalized-influence support solver,
learner seed `2060`, and held-out evaluation seed `9060` before execution.
The development result was:

- `0/12` nonzero reward witnesses and maximum reward edit `0`;
- `24/24` five-step-accepted held-out states;
- `0/24` clean and `0/24` poisoned raw-release failures;
- no resident failures, but no release failures to prevent.

The first batch had no reachable non-negative projection toward the fixed
target.  In batches 1--11, the reward box contained a centered-return
singularity, so the exact theorem did not authorize a witness and the locked
zero fallback applied.  Per protocol, learner seeds `2061` and `2062` were not
executed.

A post-stop diagnostic on the burned seed found positive exact support toward
the prior harmful snapshot, but a full exploratory V2 obtained only one
nonzero batch and still `0/24` raw-release failures.  This establishes a
boundary: the exact unclipped support result is useful for batch auditing, but
the present positive-support construction is not a general multi-batch attack
optimizer across normalization singularities.

### P2: prospective fixed-target bounded attack — hard gate passed

A separate V3 protocol retained the original bounded `tanh` reward-shaping
rule rather than relabeling SOCP as a general optimizer.  Before opening a new
seed namespace, it fixed target `(18,-5)`, all learner settings, the five-step
check, held-out state generation, and sequential decision rule.

Development seed `2070` passed with 11/24 poisoned raw-release failures,
0/24 clean failures, and 0/24 resident predictive authority failures.  This authorized
unchanged execution on `2071` and `2072`.  The pooled result is:

- all 72/72 state--snapshot pairs pass the initial five-step check;
- poisoned raw release fails on 23/72 across 3/3 seeds;
- paired clean release fails on 2/72;
- resident predictive authority fails on 0/72;
- all 23 poisoned failures have a timely paired switch;
- discordance is 21 poison-only versus 0 clean-only
  (two-sided exact `p=9.5367431640625e-7`);
- protected adaptation, reward-budget, and pairing checks all pass.

This resolves the prospective-evidence risk for the fixed target and attacker.
It does not establish joint gate optimality of the `tanh` rule.  The failed
SOCP route remains a mandatory theorem/optimizer boundary.

## Research decision

The deployment-contract separation reproduced beyond the development seed and
is ready to anchor the manuscript:

> Reverse-switch evidence is valid only while the corresponding runtime
> authority remains resident; it cannot by itself authorize permanent raw
> release after adversarial online adaptation.

Claim surgery should now:

1. lead with protected adaptation followed by permanent authority removal,
   rather than claim certificate lifecycle or reverse switching as generally
   new;
2. compare directly against resident Simplex-style authority and retain the
   failed one-step filter;
3. present normalized reward-influence support as an exact, attack-specific
   result only for unclipped batches;
4. present V3 as prospective fixed-target evidence while labeling the
   five-step horizon and target as development-fixed, the `tanh` rule as
   heuristic, and the exact-support route as a failed optimizer boundary; and
5. keep the PPO and benign-adaptation failures as mandatory negative
   boundaries.
