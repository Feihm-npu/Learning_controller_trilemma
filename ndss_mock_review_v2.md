# NDSS 2027 mock review v2 — post U1/U2/U3 (refreshed, adversarial)

> Generated 2026-08-12. A 4-lens adversarial re-review of the paper after the
> U1/U2/U3 uplifts were integrated, run to check whether they close the v1
> top-3 objections and whether the new content overclaims. Grounded in the
> actual text + result CSVs. This file records the review verdict AND the
> corrections applied in response. See `ndss_mock_review_v1.md` for the first
> pass.

## Headline verdict

Consensus recommendation: **borderline / weak-accept**. The four lenses agreed on
a uniform and important point: **the three uplifts each advance a v1 objection but
none fully closes it, and — as first written — all three overclaimed.** The
objection-closure grid came back `partially / partially / partially`. The review
found no data or soundness defect; every issue was honesty/scoping of the *new*
paragraphs. This is precisely the failure mode the project's discipline exists to
catch, so the findings were treated as blocking and corrected before finalizing.

## What the review found, and what was done (all corrections applied)

### U1 — "second learner family" overstated → corrected

- **Finding (high):** the "advantage actor--critic" is verified to be
  REINFORCE-with-a-2-parameter-linear-baseline: identical Monte-Carlo
  return (`reward_to_go`), identical residual actor and score function, no
  bootstrapping/TD. The reward-log attack channel is unchanged. Calling it a
  distinct "on-policy learner family" overstates a within-family robustness
  result; R3's ask (off-policy DDPG/SAC, a *different* channel) is explicitly out
  of scope.
- **Corrected:** the paragraph now reads "A learned value baseline does not blunt
  the attack," states the shared MC return/actor/channel, and calls it "a
  robustness check within the Monte-Carlo policy-gradient family, not a distinct
  learner family." The conclusion and the sec5 limitation were updated to match
  (no more "two learner families" / "residual REINFORCE only").

### U2 — "widens / freeze frontier / genuinely non-singleton" overstated → corrected

- **Findings:** (a) "persists and widens" and "connects to the analytic freeze
  frontier" are a **single-seed artifact** — per seed the poisoned count is
  non-monotone in rho (2210: 13/13/10 *decreases*; 2212: 15/14/15 flat; only
  2211: 13/17/36 drives the pooled 41→44→61); the kernel never empties
  (cert_admitted constant), so the freeze frontier is never reached. (b)
  "genuinely non-singleton" was **not measured** — the code uses the tautology
  `nonsingleton := rho>0.005` rather than the protocol's promised distinct-state
  count. (c) U2 injects **observation FDI**, i.e. a *stronger* attacker than the
  reward-log-only core, which must be scoped against the paper's own threat
  model; and rho enters only the **adaptation-time** kernel, not the release
  certificate.
- **Corrected:** the paragraph now scopes U2 as the general-model observation-FDI
  regime and a "strictly stronger attacker," reports the physical box half-width
  (±2.3° at rho=0.04) instead of "genuinely non-singleton," names the
  adaptation-time kernel as the non-singleton object, includes the rho=0.005
  reference (41 vs 5), states the per-seed count is non-monotone, and claims only
  **persistence** (not a trend, not the freeze frontier). The
  protocol/implementation deviation on the non-singleton measure is disclosed in
  `u2_joint_channel_protocol.md`.

### U3 — "effective defense / no clean cost" overstated → corrected

- **Findings:** (a) defended 0/126 merely **equals** the always-freeze baseline
  the paper already reports as 0 failures — the genuine delta is *selectivity*
  (0 clean batches frozen), not a safety gain. (b) The detector is co-designed
  with the attack's sign signature (freeze if any logged reward > 0; the tanh
  poison must push rewards positive) and is **evadable** by a sign-respecting
  attacker — and the paper's own moment-preserving/sparse variants (sign-valid)
  independently cause no harm, which is *why* the gate looks safe. (c) Under
  attack the defended learner freezes ~every batch (updates 0/0/1 of 12):
  **availability collapses to freeze**; "no clean cost" holds only for the clean
  condition.
- **Corrected:** the paragraph is retitled "In-loop restatement of the check,"
  states its safety only matches always-freeze, that the added value is
  selectivity, that availability collapses to freeze under attack, that it
  catches only the sign-violating effective attack and is evaded by sign-valid
  edits (which cause no harm here), and that it is an in-loop restatement of the
  detectability boundary rather than a defense against a sign-valid adaptive
  attacker. The within-snapshot p-value caveat was added.

### Cross-cutting fixes

- Added a note that the uplift cohorts use the full 42-state envelope
  (126 = 3×42) without the initial-acceptance filter, so their absolute rates are
  not directly comparable to the filtered 120-pair hero cohort.
- **Added CSV-locking audit tests** (`test_uplift_experiment_numbers_locked`) so
  the uplift numbers and honest-scoping phrases are pinned to their result CSVs
  exactly like the main results — closing the "unguarded new claims" gap. Suite
  now 74/74.
- Reconciled the U2/U3 protocol artifact lists with the files actually produced.

## Residual honest scope after corrections

- U1: a learned baseline does not blunt the attack (within-family robustness);
  cross-family generality (off-policy/PPO) remains a boundary.
- U2: the contract separation persists under a non-singleton *adaptation* plausible
  set and a strictly stronger observation-FDI attacker; no monotone-trend or
  freeze-frontier claim.
- U3: an in-loop known-sign gate is a selective restatement of the detectability
  boundary (matches always-freeze safety, frozen clean-availability), not a
  defense against a sign-valid adaptive attacker.

These are all genuine, if modest, supporting results — kept in the evaluation with
honest scoping rather than promoted to the abstract/contributions, which would
re-introduce overclaim. The paper's headline (the resident-vs-release contract
separation) and its main C2 cross-system evidence are unchanged.
