# NDSS 2027 research-track status

> Updated 2026-08-05. This is the active decision sheet; older TDSC planning
> documents are historical evidence, not the current claim contract.

## Current decision

**Proceed with the NDSS research track, but only under the narrowed
resident-authority versus permanent-release claim.**

After V3 development fixed the target and attacker and the detector was frozen,
the V4 confirmation ran five untouched learner/evaluation pairs once.  Among
120 initially five-step-accepted pairs, poisoned permanent release caused 27
physical failures across all five seeds, paired clean caused 2, and resident
predictive authority caused 0.  All 27 failures had timely switches;
discordance was 25 poison-only versus 0 clean-only.  Horizons 3, 5, and 10 all
meet the locked contract-separation condition.  An independent older-snapshot audit
retains the one-step negative control: 14/71 failures and 41 empty kernels,
versus 0/71 under resident predictive authority.

The exact theoretical object is the normalized image of a centered
reward-to-go box.  Conic homogenization removes the zero-vector degeneracy,
and a second SOC denominator branch covers global Euclidean gradient clipping.
Coordinatewise parameter clipping remains excluded.  The V3 implementation
audit verifies 22/36 poisoned batches; this is a batch support theorem, not a
multi-batch attack optimizer.

## Claim-to-evidence contract

| Claim | Evidence | Allowed strength |
|---|---|---|
| Conditional on a compromised reward-ingestion principal, reward-only update-log poisoning can survive protected adaptation and later harm raw release. | Real PyBullet rewards/transitions; bounded reward edits; no writes to runtime state/action, code, parameters, optimizer, certificate, or held-out states; multi-seed paired deployment. | Main empirical security claim; no service-exploit or stealth claim. |
| The attack is not specific to REINFORCE's batch-mean baseline. | Learned-baseline advantage variant sharing the same Monte-Carlo return, actor, and reward-log channel (`u1_second_learner_family_protocol.md`), untouched seeds 2200--2202: poisoned raw `40/126`, clean `2/126`, commit/freeze `0/126`; 38 vs 0 discordant, two-sided exact `p=7.28e-12` (within-snapshot). | Robustness WITHIN the Monte-Carlo policy-gradient family, **not** a distinct learner family; off-policy/bootstrapped learners and official PPO remain the generality boundary. |
| The separation is not an artifact of a singleton plausible state. | U2 general-model observation-FDI (a strictly stronger attacker than reward-log-only) + reward-log, locked rho grid, seeds 2210--2212 (`u2_joint_channel_protocol.md`): at non-singleton rho `0.02`/`0.04` poisoned raw fails `44/126`/`61/126` vs clean `4/126`/`3/126`, commit/freeze `0/126` (singleton `0.005`: `41` vs `5`). Non-singleton object is the adaptation-time kernel; per-seed count is non-monotone in rho. | Separation PERSISTS under a non-singleton adaptation set; **not** a monotone trend and **not** the freeze frontier (kernel does not empty on this grid). |
| An in-loop known-sign gate restates the detectability boundary as a selective mechanism. | U3 in-loop known-sign gate, seeds 2220--2222 (`u3_inloop_defense_protocol.md`): poisoned raw `39/126` undefended vs `0/126` defended, 0 clean batches frozen, ~all batches frozen under attack; paired `p=3.6e-12` (within-snapshot). | Safety only **matches** always-freeze; added value is selectivity. Catches only the sign-violating effective attack; sign-respecting variants evade it but cause no harm here. **Not** a defense vs a sign-valid adaptive attacker. |
| Finite reverse-switch evidence is valid only while its runtime authority remains resident. | Five untouched V4 seeds: poisoned raw release `27/120`, paired clean `2/120`, resident predictive authority `0/120`; all 27 timely switches; `H=3/5/10` separate. | Main contract-separation claim, explicitly finite-horizon and sampled-state. |
| One-step action safety is insufficient for this release contract. | `14/71` one-step resident failures and 41 empty-kernel cases. | Negative mechanism result, not a universal impossibility theorem. |
| A bounded reward box has exact positive normalized influence support under global gradient clipping. | Homogenized SOC unit tests pass; V3 `22/36` verified batches, including 18 old singular and 20 old gradient-bound-excluded cases; maximum witness error `3.67e-5`. | Exact one-batch result; coordinatewise parameter clipping and multi-batch construction excluded. |
| The effective attack is stealthy to task-aware reward-log checks. | Known-sign detector TPR/FPR `0.905/0`; scalar envelope `0.917/0.036`; trusted recomputation `1/0`; stealth variants cause `0/24` release failures. | Explicitly unsupported negative realism boundary. |
| The method works against official PPO or improves benign adaptation over freeze. | PPO B-lite and benign-utility smokes did not pass. | Negative boundary only. |

## Submission-format state

- Active source: `paper_latex/bare_conf_NDSS2027.tex`.
- Active PDF: `paper_latex/bare_conf_NDSS2027.pdf`.
- Official IEEE conference mode, anonymous review marking, and no keyword
  block are locked by tests.
- PDF is 14 pages total on US Letter; References begin on page 14, so the main
  text remains within the 13-page limit.
- The latest build has no overfull boxes, undefined citations, or undefined
  references.

## Remaining scientific debt

### Completed hard gate: prospective attack construction

The exact-support V1 route failed as recorded below, but the separately locked
V3 fixed-target bounded-`tanh` attacker passed in a sequential namespace with
one development/canary seed and two untouched confirmation seeds:

- per-seed poisoned failures `11/24`, `5/24`, and `7/24`;
- clean failures `0/24`, `0/24`, and `2/24`;
- resident predictive authority failures `0/72`;
- 21 poison-only, 0 clean-only, exact paired
  `p=9.5367431640625e-7`;
- zero protected-adaptation violations, 12/12 nonzero poison batches per seed,
  budget and pairing checks all valid.

This removes the retrospective-evidence hard gate for the fixed target and
attacker. It does not make the bounded `tanh` rule a joint gate optimizer.

The later V4 untouched block adds five new learner/evaluation pairs with no
changes: per-seed poisoned failures `5/24`, `4/24`, `7/24`, `2/24`, and `9/24`;
clean totals `2/120`; resident failures `0/120`; 25 poison-only versus zero
clean-only, exact paired `p=5.960464477539063e-8`.

### Retained negative boundary: exact-support attack construction

The original exact-support prospective development smoke failed on learner seed
`2060`: 0/12 nonzero reward witnesses, 0/24 raw-release failures, and no
execution of untouched seeds `2061/2062`. The nominal target direction had no
non-negative influence in batch 0; the remaining 11 reward boxes crossed the
standardization singularity, outside the theorem's scope. A post-stop V2
diagnostic toward the prior harmful snapshot produced one nonzero witness but
still 0/24 failures.  After the theory extension, a second post-stop run on the
same burned seed produced 9/12 nonzero witnesses but again 0/24 failures.
Therefore exact support remains a batch audit theorem, not a general
multi-batch attack optimizer.

### Completed P0: clipped batch-support boundary

The radial global-gradient-clipping branch and normalization-zero
homogenization are derived and validated.  Do not broaden this result across
coordinatewise parameter clipping or into multi-batch optimality.  Ten V3
batches cannot globally exclude parameter clipping, including nine observed
activations; four additional cone directions lack a witness above the
implementation normalization tolerance.

### Completed U1: second learner family (advantage actor--critic)

Executed under a specified-and-locked protocol (`u1_second_learner_family_protocol.md`)
that fixed the family, threat model, hyperparameters, seed namespace, and stop rule
before execution.  The bounded reward-log channel is identical to C2; only the
learner update rule changes (learned per-state value critic instead of the
constant batch-mean baseline).  Canary seed 2200 passed the locked gate
(poisoned `13/42`, clean `1/42`, commit/freeze `0/42`), authorizing untouched
seeds 2201/2202.  Pooled over three seeds: poisoned raw release `40/126`, paired
clean `2/126`, commit/freeze `0/126`, all 3/3 seeds failing, 38 poison-only vs 0
clean-only, two-sided exact `p=7.28e-12`.  This widens C2 across two on-policy
learner families; official PPO remains negative and off-policy DDPG/SAC (which
would alter the attack channel through a TD target) remains out of scope.

### Completed U2: non-singleton plausible set (joint observation-FDI + reward-log)

Executed under a locked protocol (`u2_joint_channel_protocol.md`) that fixed a
rho grid `{0.005, 0.02, 0.04}` before execution and reports every radius. Raising
the observation-FDI radius makes the attacked-history plausible box genuinely
non-singleton, so the certificate ranges over multiple physical states. Canary
2210 passed; confirmation 2211/2212 reproduce. Pooled over three seeds the
contract separation persists and widens with rho: poisoned raw release fails
`41/126` (rho 0.005), `44/126` (0.02), `61/126` (0.04) versus clean `5/126`,
`4/126`, `3/126`, while commit and freeze stay `0/126` at every radius. This
answers the reviewer concern that the empirical plausible set was effectively a
singleton.

### Completed U3: in-loop reward-integrity defense

Executed under a locked protocol (`u3_inloop_defense_protocol.md`). The frozen
known-sign check is placed inside the update loop as a batch gate. Canary 2220
passed; confirmation 2221/2222 reproduce. Pooled over three seeds it reduces
poisoned raw-release failures from `39/126` to `0/126`, leaves clean learning
unchanged (`2/126`), freezes zero clean batches, and freezes 35 of 36 poisoned
batches (paired two-sided exact `p=3.6e-12`). A cheap in-loop task-aware check is
an effective downstream containment defense, complementing upstream
provenance/recomputation and resident containment.

### P1: resident-authority baseline depth

The current resident predictive authority is deliberately minimal. It
supports the authority-contract comparison but is not a new Neural
Simplex/Bb-Simplex architecture and does not replace a full invariant-set or
recoverability implementation.

## Reviewer-facing presentation state

- Evaluation now opens with the prospective contract-separation audit.
- The hero table leads with the untouched 120-pair V4 confirmation, then
  reports the 72-pair development/sequential V3 cohort and the independent
  71-state audit as separate evidence blocks.
- Section titles follow the security spine: assurance-contract failure modes,
  contract-aware update analysis, and deployment contracts/escape conditions.
- The paper uses four canonical contract labels: permanent raw release,
  resident predictive authority, one-step resident kernel, and commit
  admission.
- The successful bounded-`tanh` physical attack and failed exact-support SOCP
  attack route are explicitly separated; SOCP remains a batch-audit tool.
- The abstract states the compromised reward-ingestion precondition before
  the result; Fig. 1 separates the asynchronous learning-data plane from the
  high-integrity runtime-assurance plane.
- The threat-model write-boundary table enumerates every attacker-visible
  object, and the evaluation integrity matrix distinguishes provenance,
  recomputation, semantics-dependent detection, commit admission, and
  resident containment.
- Section surgery removes the full trusted-anchor table and repetitive
  shield-removal discussion from the main paper while retaining their locked
  artifact rows and negative boundaries.  The V4 hero table, clipped theory,
  unified frontier, and model-mismatch table remain in the main text.

### Completed P1: security realism

The paper now models a split-trust deployment explicitly.  A compromised
reward-ingestion principal has bounded scalar-write authority in the
asynchronous learning-data plane, while the runtime state/action path, updater
code, parameters, optimizer, certificate, release rule, and held-out states
remain outside attacker write authority.  The benchmark begins after this
foothold and does not claim a historian/service exploit.  Protected
commissioning followed by snapshot export or promotion explains intentional
authority removal.  The text distinguishes origin-bound provenance, trusted
recomputation, semantics-dependent anomaly detection, commit admission, and
resident containment; the frozen detector results remain visible as a
negative stealth boundary.

## Next decision

Attack-evidence development is closed. The next work should improve security
realism and final submission polish, not consume another learner-seed
namespace.  The normalization-singularity and global-gradient-clipping theory
extension is complete as an exact one-batch audit.  Its remaining gap is not
another conic derivation: it is the causal bridge from batch-local support to
multi-batch deployment harm, especially when coordinatewise parameter
clipping can activate.  The burned-seed post-stop diagnostic did not close
that bridge, so no new untouched seeds should be opened for this route without
a materially new construction and a preregistered stop rule.
