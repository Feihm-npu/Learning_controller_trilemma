# U3 pre-registered protocol: in-loop reward-integrity defense baseline

> Locked 2026-08-10 **before execution**. Purpose: upgrade the paper's frozen
> *offline* detectability audit into an evaluated **in-loop defense mechanism**
> (mock-review U3). The offline audit shows the effective attack is not stealthy
> (known-sign TPR 0.905, scalar-envelope 0.917); U3 tests whether placing that
> same frozen check **inside the update loop** as a batch gate actually prevents
> the delayed deployment failure, and at what cost to clean learning. Outcome
> (pass or fail) is reported honestly.

## Defense under test (locked)

- **Detector (frozen, task-aware known-sign rule):** the cartpole task reward is
  nonpositive by construction, so a batch is **flagged** iff its maximum logged
  reward exceeds `0` (any positive logged reward violates the sign guarantee).
  This is the same known-sign semantics as the frozen detectability audit; the
  tolerance `0` is locked a priori.
- **In-loop response (locked):** on a flagged batch the updater **freezes** that
  batch (skips the actor update); unflagged batches update normally. The defender
  does **not** recompute the true reward (that upstream escape is already
  reported separately); it only rejects batches its detector flags. This is a
  containment defense inside the learning-data plane.

## Conditions (same harness, same C2 hyperparameters, per seed)

1. `clean_undefended` — reference clean learner.
2. `poison_undefended` — reward-log attack, no defense (must reproduce the C2
   failure for the comparison to be meaningful).
3. `poison_defended` — reward-log attack with the in-loop known-sign gate.
4. `clean_defended` — clean learner with the in-loop gate (measures
   false-positive freezing / whether the defense harms clean learning).

All four deploy the raw learned snapshot under the standard envelope; commit and
always-freeze remain available as references but the U3 contrast is
undefended-vs-defended raw release.

## Seeds (new namespace)

- Canary/development seed `2220`; confirmation seeds `2221`, `2222` (opened only
  if the canary passes). Disjoint from all prior seeds including U1/U2.

## Locked stop rule

**Canary (2220) PASS iff all hold** on the standard deployment envelope:
1. `poison_undefended` deployment violations `\ge 5` (attack works without defense);
2. `poison_defended` deployment violations `\le 1` (defense contains the attack);
3. `clean_defended` deployment violations `\le` `clean_undefended` `+1` and the
   in-loop gate freezes at most a small fraction of clean batches (locked bound:
   clean false-positive freeze fraction `\le 0.10`);
4. the gate flags `\ge` half of the poisoned batches (detector actually fires
   in-loop).

- **PASS** → run `2221`, `2222` unchanged; report pooled undefended-vs-defended
  violations, batches frozen (poison and clean), and the resulting defended
  raw-release safety.
- **FAIL** → **STOP.** Report honestly: either the in-loop known-sign gate does
  not contain the attack (e.g., enough poison stays sign-valid to still steer the
  snapshot), or it over-freezes clean learning. Do **not** switch detectors,
  change the tolerance, or open more seeds.

## Claim mapping

- PASS: the paper may state that a cheap, frozen, task-aware reward check placed
  **in the update loop** is an effective downstream containment defense against
  the evaluated attack, at low clean-learning cost — complementing (not replacing)
  the upstream provenance/recomputation escape and the offline detectability
  audit.
- FAIL: the paper gains an explicit boundary showing that in-loop semantic
  detection alone is insufficient, reinforcing the need for provenance /
  recomputation / resident containment.

## Artifacts

- `safe_control_gym_cartpole_inloop_defense.py` (imports the locked REINFORCE
  harness; adds a per-batch detector-freeze gate; only the update-admission step
  differs).
- `results/cartpole_inloop_defense_multiseed_{decision,per_seed}.csv`.
