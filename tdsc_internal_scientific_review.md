# TDSC internal scientific review

> Review date: 2026-07-30  
> Status: **Superseded on 2026-07-31 by the novelty review and
> certificate-evasion pivot.**  The empirical checks below remain useful, but
> the venue and novelty decision no longer governs the manuscript.  See
> `tdsc_subagent_novelty_review.md` and
> `tdsc_certificate_evasion_pivot_results.md`.  
> Decision: **PASS for internal/coauthor scientific review; retain TDSC as the
> submission target.** This is not a recommendation to return to the NDSS
> research track.

## Bottom line

The paper now has a defensible TDSC-shaped contribution: it characterizes the
certificate object that an adversarial online update must preserve, supplies a
conditional finite-abstraction lift, demonstrates a reward-log-only lifecycle
failure on two physical-control benchmarks, and compares snapshot admission
against freeze and permanent runtime protection with explicit coverage and
availability costs.

The result is deliberately narrower than the original NDSS ambition. It does
not establish learner-family universality, continuous-state invariance, or
benign adaptation utility. Those negative boundaries are visible in the
abstract, introduction, evaluation, related work, and conclusion.

## Blocking findings resolved in this review

1. **Missing closest predecessors.** Simplex, linear/adaptive MPSC, shielding
   under full and partial observability, online barrier learning, and prior
   policy/reward poisoning are now discussed. The paper no longer implies
   that rollback, backup switching, shield removal, or reward poisoning is
   itself new.
2. **Incorrect quadrotor test label.** The stored value was a one-sided exact
   binomial result but the manuscript called it two-sided. Code, locked CSV,
   manuscript, and project records now use the correct two-sided value:
   `6.776263578034403e-21`.
3. **Pseudoreplication risk.** Rollout blocks that share a learned snapshot are
   not described as independent learner replicates. Exact tests, Wilson
   intervals, and paired-block bootstrap intervals are explicitly conditional
   on the three locked learner snapshots; the cross-learner statement is the
   directional consistency over 3/3 seeds.
4. **Reward comparability.** Rewards from violating raw snapshots can cover
   shorter episodes after failure. Main-table and frontier captions now mark
   those values as descriptive rather than utility comparisons.
5. **Unsupported preregistration wording.** The protocols were locked before
   execution but were not externally registered. The manuscript and artifact
   records now say “pre-specified” or “specified and locked before execution.”
6. **Formal type mismatch.** The learning-freeze definition now distinguishes
   an updated action leaving the action kernel from a parameter leaving the
   certified parameter set.
7. **Venue-format abstract.** The abstract is now 188 words and contains no
   mathematical expressions. The compiled manuscript is 15 double-column
   pages.

## Claim closure

| Claim | Evidence | Review status |
|---|---|---|
| Action certification does not automatically certify an updated raw policy. | Necessary current/future-history conditions, explicit deployment contracts, analytic and parameter-gate counterexamples. | Closed within the stated certificate semantics. |
| A finite parameter gate can imply continuous lifecycle membership only under additional assumptions. | Joint history/state/disturbance cover plus explicit Lipschitz, discretization, and model-error margin. | Mathematically closed as conditional sufficiency; no cover-construction claim. |
| Reward-log-only corruption can create delayed raw-snapshot failure. | Cartpole `38/188` vs `1/188`; quadrotor `68/72` vs `0/72`; disjoint state pools and 3/3 quadrotor learner seeds. | Strong for the declared residual-REINFORCE family. |
| Snapshot admission and permanent runtime protection are distinct sound escape contracts. | Commit/freeze/shield/MPSC all `0/24` on a common paired audit, with coverage, intervention, reward, and latency costs. | Closed empirically for the locked sampled finite-horizon setting. |
| Trusted state anchors reduce information uncertainty but do not repair reward-log corruption. | Nested freshness/quality grid and physical paired audit. | Closed for the declared altitude/pitch anchor model. |
| Safe admitted updates are useful. | Benign actuator-shift gate fails against freeze. | Explicitly unsupported; retained as a negative boundary. |

## Residual reviewer risks

### High: perceived incremental novelty

The future-history necessary condition is direct once certificate soundness is
defined, and Simplex already addresses safe online upgrades through permanent
runtime authority. The defense is the combination of adversarial raw-snapshot
admission semantics, the explicit conditional lift, reward-log-only physical
evidence, and a unified contract/cost comparison. Claiming a new shield,
rollback architecture, or universal impossibility would make this risk
blocking again.

### High: no positive benign utility

LifecycleGate accepts updates but does not beat freeze in the locked benign
smoke. This prevents an NDSS-level “safety-security-learning” success claim.
For TDSC, the paper is framed as security/dependability characterization and
negative evidence, not as a useful adaptive-control algorithm.

### Medium: limited learner and seed population

The positive physical attack is limited to low-dimensional residual
REINFORCE, and there are three learner seeds. The official PPO gate is
negative. Conditional block-level statistics and the learner-family boundary
must remain visible.

### Medium: sampled certificates and simulation

Commit and utility gates use finite state sets and finite horizons. The
coverage audit finds no false acceptance at the locked positive guard but does
not prove invariance. PyBullet is independent of the CasADi certificate model
but is not hardware.

### Medium: timing interpretation

Reported times are single-process host wall-clock measurements, not WCET.
Offline commit and online filters implement different contracts, so latency
numbers are not interchangeable.

### Low: manuscript length and cost

The current 15-page manuscript is below the IEEE Computer Society maximum of
18 formatted pages for a Transactions submission, but exceeds the 12-page
regular-paper baseline that triggers mandatory overlength charges after final
layout. This is a cost/editing issue rather than a scientific blocker.

## Reviewer attack rehearsal

- **“This is just Simplex.”** Simplex retains a runtime authority; this paper
  asks what evidence is required before an adversarially trained raw snapshot
  leaves that authority, and measures the cost of keeping the authority.
- **“The theorem is tautological.”** The necessary boundary is intentionally
  semantic. The stronger technical result is the explicit margin sufficient
  lift; its cover and regularity assumptions are stated rather than hidden.
- **“The p-values use 72 independent learners.”** They do not. The manuscript
  identifies paired state-block tests as conditional on three snapshots and
  reports 3/3 seed consistency separately.
- **“Zero failures prove the gate safe.”** The paper says sampled
  finite-horizon evidence and reports coverage/model-mismatch limits.
- **“Why learn if freeze is better?”** The paper does not claim useful
  learning. The failed benign gate is a principal negative boundary and a
  reason to target TDSC rather than NDSS.

## Recommended next sequence

1. Freeze scientific claims and experiments. More attack tuning would violate
   the locked negative gates and has poor expected return.
2. Obtain a coauthor/external read focused on novelty relative to Simplex,
   shielding removal, and adaptive MPSC.
3. If avoiding overlength charges matters, move expository frontiers and
   secondary plots to supplement while preserving the two-system attack,
   unified paired frontier, coverage audit, and negative gates in the main
   paper.
4. Complete submission-only metadata, authorship, disclosure, and the current
   TDSC portal checklist after the scientific text is frozen.
