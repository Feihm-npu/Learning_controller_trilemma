# NDSS 2027 pre-submission mock review (v1)

> Generated 2026-08-10 as a pre-submission referee simulation for
> `paper_latex/bare_conf_NDSS2027.tex`, title *"Protected While Learning,
> Unsafe When Released: Reward Poisoning Across Runtime-Assurance Contracts"*.
> Calibrated to NDSS / top-tier systems-security norms (the target venue), not
> to a Nature-family journal, per the review request. Structure follows the
> `nature-reviewer` skill (3 reviewers + cross-synthesis + risk list). Grounded
> only in the current manuscript, `ndss_submission_status.md`, and the repo
> review history. This is a self-assessment aid, not an editorial decision.

## Review setup

- **Input scope:** full compiled manuscript (14→15 pp, body ends p.13; Ethics +
  references p.14–15), all nine section files, claim contract
  `ndss_submission_status.md`, reproducibility manifest, audit suite (74/74).
- **Assessment boundary:** simulation-only evidence (Safe-Control-Gym /
  PyBullet); no hardware, no real OT system. Reviewer cannot re-run experiments;
  numbers taken as reported and cross-checked against locked CSVs by the audit
  test.
- **Shared claim summary:** Under a split-trust deployment where an attacker can
  write only bounded scalar rewards consumed by a policy-gradient updater
  (runtime state/action/params/certificate trusted), *finite reverse-switch
  evidence collected while a decision module is resident does not transfer to
  permanent raw-policy release*. Headline: V4 five untouched cartpole seeds →
  poisoned raw release 27/120, clean 2/120, resident predictive authority
  0/120; one-step kernel 14/71. Cross-system quadrotor reward-log attack 68/72
  vs 0/72. Plus a normalized reward-influence (SOC) batch-audit theorem, a
  unified commit/freeze/shield/MPSC cost frontier, a CasADi–PyBullet coverage
  audit (1293/1728, 0 false accept), and explicit PPO-transfer / benign-utility
  / detectability negative boundaries.
- **Visible evidence base:** two CPS systems, multi-seed paired deployment,
  locked-before-execution protocols, source-linked auto-generated tables,
  SHA-256 artifact manifest.
- **Missing materials affecting confidence:** no hardware; single learner
  family for the positive physical attack (low-dim residual REINFORCE); three
  learner seeds per system; sampled finite-horizon certificates only.

---

## Reviewer 1 — emphasis: runtime assurance / safe control & formal claims

- **Overall assessment:** Solid, unusually disciplined contribution with a real
  and previously-unarticulated delta (contract transfer of finite reverse-switch
  evidence), but the formal core is deliberately light and the strongest result
  is a *measurement/characterization*, not a new synthesis or impossibility
  theorem. Borderline-accept to weak-accept for a research track if the
  writing-level issues are fixed.
- **Who would care & why:** the RTA/Simplex, safe-RL, and CPS-security
  communities that build "protected adaptation then deploy" pipelines; the
  result names a failure mode (evidence-contract transfer) they are currently
  positioned to make.
- **Major strengths:** (1) clean separation of *resident predictive authority*
  vs *permanent raw release* vs *one-step resident kernel* vs *commit
  admission*, with the one-step kernel retained as a negative control (14/71) —
  this is what makes "residence alone is insufficient" credible rather than
  rhetorical; (2) the normalized reward-influence / conic-homogenization
  analysis is a genuine, correct technical nugget with exact witness error
  reported; (3) honesty — the PPO and benign-utility negatives are in the
  abstract.
- **Major concerns:** (a) the future-history necessary condition is close to a
  definitional unrolling once certificate soundness is defined; the paper should
  keep presenting it as a *specification boundary*, not oversell it as deep
  theory (it already largely does). (b) The exact-support theorem covers only
  unclipped / global-gradient-clipped batches; coordinatewise parameter clipping
  is excluded and the quadrotor attack is empirical — the causal bridge from
  batch-local support to multi-batch deployment harm is not closed and the paper
  says so, but a reviewer will still dock novelty for it.
- **Technical failings to address before the case is established:** none that are
  *blocking* given the stated scoping; the lift's joint-cover / Lipschitz /
  model-error premises must remain visibly unproven (they are).
- **Assessment against criteria:** originality medium-high (the contract-transfer
  framing is new even though every ingredient is known); soundness high *within
  the sampled finite-horizon scope*; significance medium-high for the subfield.
- **Recommendation posture:** weak accept / minor-to-major revision.

## Reviewer 2 — emphasis: CPS / ML security, threat model, attack realism

- **Overall assessment:** The security framing is now careful and defensible, but
  the paper's single largest risk is a reviewer asking *"is the split-trust
  reward-ingestion attacker realistic enough to carry an NDSS paper, given the
  attack is non-stealthy and fully removed by trusted recomputation?"* The paper
  pre-empts this well, but the honesty is double-edged.
- **Who would care & why:** OT/ICS security, poisoning/backdoor researchers,
  runtime-assurance builders.
- **Major strengths:** (1) explicit least-privilege write-boundary table; (2) the
  integrity matrix distinguishing provenance / recomputation / semantic
  detection / commit / resident containment is exactly the taxonomy a security
  reviewer wants; (3) BADControl and the RL/control-backdoor line are now cited
  and cleanly distinguished (unconditional-after-release, certificate-relative,
  vs trigger-conditioned physical backdoor).
- **Major concerns:** (a) **Detectability vs significance tension.** Trusted
  recomputation is TPR/FPR 1/0 and two simple task-aware checks exceed 0.90 TPR;
  a hostile reviewer reads this as "the interesting attack is easy to stop, so
  the security contribution is the *observation*, not the *threat*." The paper
  must (and mostly does) sell the *contract-transfer* insight, not the poison, as
  the contribution — the abstract/intro framing is the deciding factor.
  (b) **Formal-vs-empirical threat-model gap** (raised in the internal novelty
  review): the general model has observation-FDI plausible sets
  `X_A(h)`, but the end-to-end attack keeps state/observation trusted, so the
  headline experiment's plausible set is effectively a singleton. The paper now
  scopes this correctly (reward-log channel is the empirical core; severe-sensor
  ambiguity is formal extension), but a reviewer may still want *one* joint
  observation-ambiguity + reward-log experiment.
- **Technical failings to address:** none blocking; ensure the abstract leads
  with the contract insight (it does) and not with "reward poisoning."
- **Assessment against criteria:** originality medium; soundness high; realism
  medium-high *conditional on the stated foothold*, which is the crux.
- **Recommendation posture:** borderline; leans accept if the PC values
  measurement/systematization papers, leans weak-reject if it demands a novel
  *offensive* capability.

## Reviewer 3 — emphasis: empirical rigor, statistics, reproducibility, generality

- **Overall assessment:** Among the most reproducible CPS-security submissions a
  reviewer will see (locked protocols, source-linked tables, SHA-256 manifest,
  74/74 audit). The rigor bar is high; the generality of the *positive physical
  attack* is the honest soft spot.
- **Who would care & why:** artifact-evaluation-minded reviewers; anyone who has
  been burned by non-reproducible poisoning results.
- **Major strengths:** paired designs, disjoint state pools, seed namespacing,
  result-independent calibration, and negative gates that were honored rather
  than tuned away.
- **Major concerns:** (a) **Statistical scope** — the contract-separation exact
  p-values (5.96e-8, 9.54e-7) are within-snapshot discordance tests; pairs
  sharing a learner seed are not independent replicates. *This is now caveated in
  both intro and evaluation* (good); keep the cross-seed 5/5 (3/3) reproduction
  as the generality statement, not the p-value. (b) **Learner generality** — the
  physical attack is established only for low-dim residual REINFORCE; official
  PPO does not stably fail. This is disclosed, but limits the "canonical online
  learner" claim; a reviewer may want a second learner family (e.g., DDPG/SAC
  residual) even if PPO stays negative. (c) **Sampled certificate** — coverage
  audit is strong (0 false accept at the locked guard) but explicitly not a
  continuous-invariant proof; fine as scoped.
- **Technical failings to address:** none blocking for the reported scope.
- **Assessment against criteria:** soundness high; generality medium;
  reproducibility very high.
- **Recommendation posture:** accept-leaning on rigor, conditional on the
  generality caveats staying visible (they do).

---

## Cross-review synthesis

- **Consensus strengths:** (1) a real, sharply-scoped contribution — evidence
  collected under resident authority does not certify raw release — backed by a
  clean four-contract taxonomy and a retained negative control; (2) exemplary
  reproducibility and honesty (negatives in the abstract); (3) a correct,
  self-contained conic reward-influence result; (4) now-adequate related-work
  positioning including BADControl and the backdoor line.
- **Consensus technical risks (all *presentation/scoping*, not data):**
  (i) novelty is combinatorial — every ingredient exists; the paper wins or
  loses on whether the contract-transfer insight reads as non-obvious;
  (ii) the effective attack is non-stealthy and fully blocked upstream by trusted
  recomputation, so significance rests on the *observation*, not the exploit;
  (iii) positive physical attack is single-learner-family; (iv) formal severe-
  sensor model is broader than the empirical reward-log core.
- **Where emphasis differs:** R1 weighs formal depth (light-but-honest); R2
  weighs threat realism (the crux); R3 weighs generality (the soft spot). None
  finds a *data* flaw.
- **Significance readout:** a credible measurement/systematization + focused
  attack+contract paper. Its ceiling at NDSS depends on the PC's appetite for
  characterization papers over novel offensive capability.
- **Most important pre-submission actions:** all are writing/framing except the
  optional generality experiment (see split below).

---

## Fixable by writing (do before submission — no new experiments)

1. **Lead every summary with the contract-transfer insight, not "reward
   poisoning."** Abstract/intro already do; make the title-to-contribution line
   airtight so R2's "easy-to-stop attack" reading is pre-empted.
2. **Keep the snapshot-conditional p-value caveat visible** (done: intro +
   evaluation) — this defuses R3's strongest rigor objection.
3. **State the single-learner-family scope as a deliberate boundary** in the
   contributions list, not only in limitations (partly done).
4. **One or two sentences making the formal-vs-empirical scoping explicit in the
   threat model** ("severe-sensor plausible sets are the general model; the
   end-to-end attack instantiates the reward-log channel with trusted state").
   The text already implies this; make it a labeled sentence.
5. **Optional abstract addition:** the quadrotor 68/72 cross-system result is the
   strongest generality signal and is currently absent from the abstract. Add it
   *only* if a sentence can be trimmed to stay ≤200 words and page-neutral.
6. **Consider a compact "delta table"** vs Simplex / Neural Simplex / Damare /
   BADControl / policy-repair (the novelty review recommended it). Space is the
   constraint (body at 13 pp); would require trimming elsewhere.

## Needs a new (pre-registered) experiment — USER DECISION required

These would raise the ceiling but each opens a new seed namespace and must have
a locked stop rule *before* execution (consistent with project discipline). None
is required for a defensible submission; each is an uplift bet.

- **U1 — second positive learner family** (e.g., residual DDPG/SAC) to widen the
  "canonical online learner" claim beyond REINFORCE while keeping PPO negative.
  Directly answers R3(b). Highest expected reviewer value.
- **U2 — joint observation-FDI + reward-log experiment** so the empirical result
  exercises a non-singleton plausible set `X_A(h)`, closing R2(b) /
  the internal novelty review's item 4.
- **U3 — a reward-channel security-defense baseline** (integrity/anomaly detector
  in the loop) evaluated as a mechanism, not only as the frozen detectability
  audit.

> Repeatedly cautioned in the repo: do **not** reopen the PPO sweep, the
> benign-utility formal run, or the exact-support attack route — those failed
> pre-specified gates and reopening them post hoc would violate the discipline
> that makes the negatives credible.

---

## Round 2 — adversarial reject rehearsal (does the post-edit paper survive?)

The strongest reject a hostile NDSS PC member would write, and the paper's
current defense:

1. **"This is Simplex/Neural-Simplex/Damare with a poisoned log — combinatorial,
   not novel."** *Defense (holds):* the delta is the *contract* — prior RTA keeps
   the monitor resident; this paper asks what finite evidence licenses *removing*
   it, and shows reverse-switch evidence does not transfer. The one-step-kernel
   negative control (14/71) proves the distinction is recoverability, not
   terminology. Related work now states each delta. *Residual risk:* a PC that
   equates "no new mechanism" with "no novelty" can still weak-reject; mitigated
   but not eliminable by writing. A compact delta table would help (page-limited).

2. **"The attack is non-stealthy and trusted recomputation kills it (1/0), so
   there is no threat."** *Defense (holds if framed right):* the contribution is
   the assurance-contract gap and its defense taxonomy, not a stealthy exploit;
   the paper explicitly positions recomputation/provenance as the correct
   upstream fix and measures the containment cost of the alternatives. *Residual
   risk:* real. This is the crux objection; the abstract/intro framing must keep
   the insight, not the poison, in front. Currently acceptable.

3. **"p-values overstate independence."** *Defense (now holds):* both intro and
   evaluation carry the within-snapshot / not-independent-replicate caveat, and
   generality is carried by 5/5 and 3/3 seed reproduction. This objection is
   largely closed by the v1 edits.

4. **"Only one learner family physically fails; PPO doesn't."** *Defense
   (partial):* disclosed in abstract, contributions, limitations. *Residual
   risk:* a determined reviewer wants a second *positive* family (→ U1). This is
   the one place a new experiment materially raises the ceiling.

5. **"Sampled certificate ≠ invariance; simulation ≠ hardware."** *Defense
   (holds):* explicitly scoped as sampled finite-horizon with a coverage/guard
   audit; no invariance claimed. Standard, accepted boundary.

**Round-2 verdict:** No *data* or *soundness* defect surfaces on a second pass.
The paper is a defensible, honest, highly-reproducible submission whose accept
probability is bounded above by (a) the PC's taste for characterization vs novel
offense and (b) whether objections 1–2 are neutralized by framing. Convergence:
round-2 finds no new blocker beyond round-1's; the writing fixes are in place;
the only ceiling-raiser is optional experiment U1. **Recommend: submit to a
cycle whose reviewing values systematization + focused attack, and treat U1 as
the one high-value uplift if a cycle is skipped.**
