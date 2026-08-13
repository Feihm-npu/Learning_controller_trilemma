# NDSS 2027 submission TODO (owner: authors / user decisions)

> Created 2026-08-10. The science is frozen and audit-green (73/73 tests,
> 234-file SHA-256 manifest, body ≤13 pp). What remains is submission-operational
> metadata and optional uplift decisions. See `ndss_mock_review_v1.md` for the
> full referee rehearsal and `ndss_submission_status.md` for the claim contract.

## A. Submission-operational — required before portal upload

- [x] **Target cycle: NDSS 2027 Fall** (deadline **2026-08-19**). Author priority:
      quality over speed — the paper is already submission-shaped and audit-green,
      so no rushed changes; keep the Summer 2028-equivalent cycle as fallback only
      if a quality concern surfaces before the deadline.
- [ ] **Double-blind check.** `\author{}` is empty and "Anonymous submission for
      review" is set (good). Do a final self-de-anonymization sweep: no author
      names, affiliations, funding, repo URLs, or self-citations in first person.
      *(author)*
- [x] **Generative-AI disclosure — drafted** (per your stated use: Anthropic
      Claude Opus 4.8 for prose polishing, OpenAI GPT-5.6 Sol for code review).
      Ready statement in §E.1; paste into the portal's GenAI field at submission.
      One residual author check: confirm it covers the *full* extent of AI use
      (NDSS wants disclosure proportional to use) — extend if any AI-generated
      code/prose beyond polishing/review entered the submission. *(author — paste
      + confirm completeness)*
- [x] **Template compliance — VERIFIED (no changes needed).** NDSS 2027 requires
      the IEEEtran-based `bare_conf_NDSS2027.tex` template; the paper uses exactly
      that (`\documentclass[conference]{IEEEtran}`, bundled `IEEEtran.cls` V1.8b —
      the version NDSS distributes), US-letter two-column, Times 10pt/11pt, NDSS
      block at the bottom of the first column, `\author{}` empty and "Anonymous
      submission for review" set. Venue string ("Seoul, 22--26 March 2027") is
      correct. Body 13 pp, well within both the 13-excl-refs and 18-incl-all caps.
      **IEEEtran.cls byte-identity VERIFIED:** NDSS 2027 ships no custom class (the
      official `bare_conf_NDSS2027.tex` just requires "IEEEtran.cls V1.8b or
      later"); the bundled copy is byte-identical to canonical CTAN IEEEtran.cls
      V1.8b (281,957 bytes, SHA-256 `da751920a317ed31...`). No change needed.
- [ ] **BADControl reference completion.** Entry `burbano_badcontrol_2026` has
      authors + venue (USENIX Security 2026) + URL; fill pages/DOI once the
      proceedings are final. *(author)*
- [ ] **Responsible disclosure.** Ethics section states no specific fielded
      system/vendor is known to require notification; confirm this is accurate
      for the final author set. *(author)*
- [ ] **Author/affiliation + acknowledgments** for camera-ready only (keep
      anonymized for review). *(author)*

## B. Optional scientific uplifts — need a pre-registered protocol + a NEW seed
namespace and an execution-locked stop rule (do NOT run ad hoc)

- [x] **U1 (DONE — integrated): second positive learner family.** Advantage
      actor--critic (learned per-state value critic) under a locked protocol
      (`u1_second_learner_family_protocol.md`). Canary 2200 passed the locked
      gate; confirmation 2201/2202 pooled to poisoned `40/126` vs clean `2/126`,
      commit/freeze `0/126`, 3/3 seeds, two-sided exact `p=7.28e-12`. Integrated
      into the evaluation, limitations, claim contract, and reproducibility
      manifest. Widens generality across two on-policy families; PPO stays
      negative. *(off-policy DDPG/SAC, which alters the attack channel via a TD
      target, remains a separate future item)*
- [x] **U2 (DONE — integrated): joint observation-FDI + reward-log.** Locked
      rho grid (`u2_joint_channel_protocol.md`), 3 untouched seeds 2210--2212.
      At non-singleton rho 0.02/0.04 poisoned raw release fails 44/126 and
      61/126 vs clean 4/126 and 3/126, commit/freeze 0/126 at every radius; the
      separation persists and widens with rho. Closes the singleton-artifact
      concern. Integrated into evaluation, claim contract, and manifest.
- [x] **U3 (DONE — integrated): in-loop reward-integrity defense.** Frozen
      known-sign check as an in-loop batch gate (`u3_inloop_defense_protocol.md`),
      3 untouched seeds 2220--2222: poisoned raw-release failures 39/126 → 0/126,
      clean unchanged (2/126), 0 clean batches frozen, paired exact p=3.6e-12.
      Establishes a cheap downstream containment defense. Integrated into
      evaluation, claim contract, and manifest.

## C. Optional writing polish — page-budget permitting (body at 13 pp)

- [ ] Add the quadrotor `68/72` cross-system result to the **abstract** (strongest
      generality signal, currently only in intro/eval). Requires trimming a
      sentence to stay ≤200 words and page-neutral.
- [ ] Add a compact **delta table** vs Simplex / Neural-Simplex / Damare /
      BADControl / policy-repair (novelty-review recommendation). Requires
      reclaiming ~0.3 pp elsewhere.
- [ ] One half-sentence in the intro distinguishing the two cartpole experiments
      (fixed-target-`tanh` linear residual for 27/120 vs residual-REINFORCE for
      38/188) so the two numbers are not conflated.
- [ ] Optional fragment-preserving language polish (nature-polishing /
      paper-prose-tightening). Deferred by default: the audit test hard-codes ~30
      exact required fragments and the body is at the page limit, so an automated
      pass must be run with fragment/page guards. *(user approval to proceed)*

## D. Do NOT reopen (locked negative gates — reopening post hoc breaks the
discipline that makes the negatives credible)

- Official-PPO multi-seed unsafe-policy sweep (failed pre-specified gate).
- Benign-utility formal multi-seed run (failed pre-specified gate).
- Exact-support SOCP attack-optimizer route (retained as a batch-audit theorem
  and a failed optimizer boundary only).

## E. Ready-to-use statements & camera-ready templates

### E.1 Generative-AI disclosure (per author-stated use)

> **Use of Generative AI.** In preparing this work the authors used
> generative-AI assistants in two roles: a large language model (Anthropic Claude
> Opus 4.8) for language polishing of the manuscript prose, and a large language
> model (OpenAI GPT-5.6 Sol) for code review of the experiment and analysis
> scripts. All research questions, the threat model, the experimental protocols
> and pre-specified stop rules, the scientific claims and proofs, and all reported
> results were designed, executed, and verified by the authors, who take full
> responsibility for the content. No generative model was used to fabricate data
> or results; every reported number is produced by the authors' code and is
> reproducible from the released artifact.

Placement: paste into the portal's GenAI-disclosure field; it is anonymity-safe
(tool names do not identify authors). NDSS requires disclosure *proportional to
use*, so if AI assistance in the final workflow went beyond polishing and code
review (e.g., generating or scaffolding any code or prose that made it into the
submission), extend the two-role list accordingly before submitting.

### E.2 Camera-ready author block (replace the empty `\author{}`; keep empty for review)

```latex
\author{\IEEEauthorblockN{First Author\IEEEauthorrefmark{1}, Second Author\IEEEauthorrefmark{2}}
\IEEEauthorblockA{\IEEEauthorrefmark{1}Affiliation One, City, Country\\ Email: a@x.edu}
\IEEEauthorblockA{\IEEEauthorrefmark{2}Affiliation Two, City, Country\\ Email: b@y.edu}}
```

### E.3 Camera-ready NDSS pubid block (replace the "Anonymous submission" block)

```latex
\IEEEpubid{\parbox{\columnwidth}{
    Network and Distributed System Security (NDSS) Symposium 2027\\
    22--26 March 2027, Seoul, Republic of Korea\\
    ISBN <assigned>\\
    https://dx.doi.org/10.14722/ndss.2027.<24XXXX for Fall / 23XXXX for Summer>\\
    www.ndss-symposium.org
}\hspace{\columnsep}\makebox[\columnwidth]{}}
```

Use `24XXXX` for the Fall cycle DOI, `23XXXX` for Summer; the exact number and
ISBN are assigned on acceptance. Do **not** apply E.2/E.3 to the review
submission — it must stay anonymous.
