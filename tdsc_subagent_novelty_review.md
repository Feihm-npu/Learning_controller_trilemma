> ⚠️ **前一投稿场地的历史文档（2026-08-19 标注）。** 本文件针对 NDSS/TDSC 撰写，
> 与当前 USENIX Security 2027 的稿件状态、页面预算与结论均不一致。
> **当前状态请读 [`usenix_direction_audit_0819.md`](usenix_direction_audit_0819.md)。**
> 保留仅为历史记录。

# TDSC simulated novelty review

> Review date: 2026-07-31  
> Review design: three independent simulated reviewers, followed by a
> cross-review meta-analysis  
> Decision: **NOVELTY HARD GATE FAIL — hold submission and revise**

## Executive decision

No single prior work was found that jointly covers all four elements of the
paper:

1. an online controller/policy update;
2. a physical safety certificate or runtime-assurance architecture;
3. malicious corruption of the online update-data channel; and
4. admission of a raw updated snapshot intended to leave runtime authority.

The paper therefore is **not directly duplicated**.  However, the current
positioning is not submission-safe.  The reviewers independently reconstructed
most of the paper's broad story from established components, and the
prior-art adversary found a particularly dangerous omitted neighbor:

- Damare et al., *A Barrier Certificate-Based Simplex Architecture for Systems
  With Approximate and Hybrid Dynamics*, IEEE Access 2025
  ([official record](https://researchconnect.stonybrook.edu/en/publications/a-barrier-certificate-based-simplex-architecture-for-systems-with-2/),
  [DOI](https://doi.org/10.1109/ACCESS.2025.3599459)).

Damare et al. already combine a barrier-certificate Simplex architecture, an
RL neural controller, poisoned-controller experiments, an online adaptation
module, and forward/reverse switching.  The important remaining distinction is
temporal and contractual: their poisoning occurs in the controller's earlier
training, their online retraining uses trusted baseline-controller data, and
the decision module remains resident after reverse switching.  This paper
instead corrupts the **online reward-log channel** and studies whether the
updated **raw snapshot can permanently leave that runtime authority**.

That distinction is real, but the current manuscript neither cites this
closest work nor turns the distinction into a sufficiently non-obvious theorem
or direct empirical comparison.  The appropriate current decision is therefore
**hold TDSC submission**, not abandon the project.

## Reviewer scorecard

| Reviewer lens | Novelty | Significance | Recommendation | Main concern |
|---|---:|---:|---|---|
| Runtime assurance / safe control | 3/5 | 3/5 | Major revision / borderline weak reject | Broad lifecycle claim is already occupied by Simplex, MPSC, shield-removal, and across-update certification |
| CPS security / poisoning | 2/5 | 3/5 | Weak reject / reject-and-resubmit | Known poisoning plus known safe-update/runtime-assurance primitives; formal and empirical threat models do not fully meet |
| Adversarial prior-art search | 3.5/10 | — | Hard-gate fail | Damare 2025 and Neural Simplex cover most of the architecture; several direct policy-repair works are omitted |

Meta-review:

- **Current novelty:** approximately 2/5.
- **Fatal single-paper overlap:** no.
- **Combinatorial obviousness risk:** high.
- **Related-work completeness:** unacceptable for submission.
- **Best remaining venue:** TDSC, after controlled revision; the review does
  not justify returning to NDSS.

## Consensus: what is and is not new

### Claims that are not safe as primary novelty

- Online controller upgrades need safety assurance.
- An update can invalidate an old policy certificate.
- Runtime action filtering and raw-policy safety are different objects.
- A baseline controller, rollback, freeze, forward/reverse switching, or
  shield removal can manage an unsafe learned controller.
- Policy parameters or actions can be projected into a safe feasible set.
- Runtime data can repair an unsafe learned policy.
- Reward poisoning can steer an online learner.
- A finite-horizon simulation or sampled check can support a switch-back
  decision.
- A finite cover plus Lipschitz/model-error margins can lift sampled checks.

### Defensible residual contribution

The strongest defensible paper is a security/dependability characterization of
this specific transition:

> A learner adapts online while a runtime authority protects the plant; an
> attacker corrupts the learner's online update log without directly writing
> actions, gradients, parameters, or optimizer state; the resulting raw
> snapshot is later considered for permanent release from that authority.

The paper's distinctive package is then:

- adversarial update-data integrity;
- attacked-history plausible-state semantics;
- physical closed-loop certificate inheritance;
- the distinction between resident runtime authority and permanent raw release;
- delayed physical failure despite safe protected adaptation;
- a common cost audit of commit, freeze, permanent shield, MPSC, and trusted
  anchors;
- explicit negative boundaries for PPO generality and benign utility.

This is a narrower and more credible claim than inventing “certificate
lifecycle security,” online update certification, or raw-policy release as
general problems.

## Closest-work matrix

| Work | Online update | Malicious online update data | Physical certificate / RTA | Raw policy leaves runtime authority | Exact delta of this paper |
|---|---:|---:|---:|---:|---|
| Seto et al., Simplex 1998 | controller upgrades | no | yes | no | attacks the update-data channel and distinguishes permanent raw release |
| Phan et al., Neural Simplex 2020 | yes; online retraining | no | yes | no; monitor remains | poisoned adaptation log and admission outside resident DM |
| Zhou et al., Runtime-Safety-Guided Policy Repair 2020 | yes; policy repair | no | safety-controller-guided | seeks to reduce switching, but not adversarial release | attacker-aware history and deployment contract |
| Chow et al., Safe Policy Learning 2021 | yes; parameter/action projection | no | Lyapunov/CMDP constraints | policy is trained to be near-safe | adversarial histories and physical raw-snapshot release |
| Didier et al., Adaptive MPSC 2021 | certificate/model adapts | no | yes | no; MPSC remains online | corrupted learner update rather than trusted set-membership identification |
| Carr et al., shield removal 2023 | learned policy changes | no | shield under partial observability | yes, empirically | adversarial data and explicit admission semantics |
| Hsu et al., Sim-to-Lab-to-Real 2023 | protected learning | no | PAC-Bayes deployment bounds | yes | deterministic/adversarial plausible-state certificate rather than distributional bound |
| Lu et al., Repair with Preservation 2024 | policy repair | no | formal verification of preserved regions | updated policy is verified | malicious update histories and runtime-authority contract |
| Yu et al., neural control/certificate repair 2025 | policy and certificate retraining | no | runtime monitoring/certificate | repaired controller | poisoning and permanent-release admission |
| **Damare et al., Bb-Simplex 2025** | **yes; online retraining** | **poisoned controller, but trusted online retraining** | **barrier Simplex** | **no; DM remains resident** | **poison is in the online log and target is permanent raw release** |
| Mirzaeedodangeh et al., L4DC 2026 | iterative policy updates | not update-log poisoning | adversarially robust conformal guarantees | policy update changes guarantee | CPS plausible-state kernel and malicious learner data |

Additional relevant lines include certified continual learning, adaptive reward
poisoning, CRABS, Simplex-Drive, neural policy/certificate repair, and recent
RTA certificates for adapting controllers.

## The three strongest rejection arguments

### 1. The formal novelty is too close to definitions and standard machinery

The future-history theorem says that a sound certificate for an updated
controller must hold over the future histories covered by that certificate,
while the certified parameter set is defined by that membership.  The
halfspace result is a linear inequality rewrite.  The conditional continuous
lift is a standard cover-and-margin argument once the joint cover,
Lipschitz constants, and model-error bound are supplied.  Plausible-set
monotonicity follows from set inclusion under universal constraints.

These statements can be useful specification boundaries, but they cannot bear
the paper's main novelty claim as currently written.

### 2. The closest adaptive-Simplex and policy-repair literature is missing

The current related work cites Simplex, MPSC, Carr, Brunke, and certified
continual learning, but omits work that is closer to the full architecture:

- Damare 2025 barrier-based Simplex;
- Neural Simplex;
- runtime-safety-guided policy repair;
- repair with preservation;
- neural control and certificate repair;
- safe policy parameter/action projection;
- protected learning followed by certified unshielded deployment;
- recent guarantees transferred across policy updates.

An expert reviewer can reasonably interpret these omissions as evidence that
the claimed gap was defined without confronting the nearest systems.

### 3. The most distinctive formal threat model is not closed by the main experiment

The formalism derives much of its distinctiveness from observation FDI,
attacked-history ambiguity, and the plausible-state set
\(X_{\mathcal A}(h)\).  The primary end-to-end attack changes reward logs while
states and observations remain trusted.  In that experiment the plausible
state set is essentially a singleton, so the implemented commit check is much
closer to finite-state, finite-horizon post-training verification.

The manuscript must either:

- add an experiment in which observation ambiguity and reward-log corruption
  jointly affect the learner and snapshot admission; or
- narrow the main paper to reward-log integrity and present severe-sensor
  ambiguity as a formal extension rather than empirically validated core.

## Strongest author rebuttal

The credible rebuttal is not that the individual ingredients are new:

> Simplex and MPSC certify a composition that retains runtime authority;
> Neural Simplex and Damare retrain under baseline control but retain their
> decision module and do not corrupt the online retraining channel; policy
> repair and safe policy projection assume trusted update evidence; Carr
> studies shield removal empirically; Hsu provides a PAC-Bayes deployment
> guarantee under a non-malicious data model; adaptive reward-poisoning work
> does not analyze inheritance of a physical CPS certificate.  This paper
> isolates and evaluates the gap formed when an attacker corrupts the online
> update log during protected adaptation and the resulting raw snapshot is
> intended to leave runtime authority.  Its contribution is the
> attacker-aware certification target and deployment-contract
> characterization, not a new shield, poison primitive, or general
> verification algorithm.

This rebuttal establishes a real delta.  It will not be persuasive until it is
reflected in the title/abstract/introduction/contributions/related work and
tested against the closest reverse-switch baseline.

## Required revision before TDSC submission

### P0 — novelty blockers

1. **Perform claim surgery.**
   Replace “The unresolved object is the lifecycle” and “We define certificate
   lifecycle security” with a narrower claim about adversarial online
   update-log corruption and permanent raw-snapshot release.

2. **Add the omitted closest work and an explicit delta table.**
   At minimum discuss Damare 2025, Neural Simplex, Zhou's runtime-guided policy
   repair, Lu's repair with preservation, Yu's policy/certificate repair,
   Chow's safe policy projection, Hsu's protected-to-unprotected deployment,
   and Mirzaeedodangeh's across-update guarantees.

3. **Run a direct Neural-Simplex/Damare-style contract comparison.**
   Compare resident reverse switching with finite snapshot commit, permanent
   shield, and freeze under the same poisoned online updates.  The key measured
   distinction must be whether the monitor remains resident after control is
   returned, rather than merely whether a controller is switched back in.

4. **Resolve the formal–empirical threat-model split.**
   Either add a joint observation-ambiguity/update-log experiment or demote the
   severe-sensor formalism from the empirically supported core.

### P1 — strongly recommended

5. Add fresh confirmatory learner seeds that exclude the quadrotor development
   seed, plus a normalized poison-budget sweep and simple poisoning baselines.
6. Add at least one security defense baseline for the reward/log channel, even
   if it is a simple integrity or anomaly-detection mechanism.
7. Present the necessary theorem as a semantic specification boundary, not a
   deep technical result.  If stronger theory is pursued, target an
   attacker-aware information/availability lower bound or certificate binding
   to the snapshot, evidence, threat contract, and reachable-history cover.

## Investment decision

The work should **not be abandoned**: no exact prior-art duplication was found,
and the accumulated two-system evidence, contract/cost audit, negative results,
and reproducibility package remain valuable.

The rational next investment is one bounded novelty-repair cycle:

1. complete the related-work and claim rewrite;
2. implement the closest resident reverse-switch baseline;
3. make a go/no-go decision based on whether permanent raw release exposes a
   measurable failure that the resident-authority contract masks.

If that comparison produces a clear, reproducible separation, continue to
TDSC.  If the distinction collapses to terminology or a known poisoning
composition, stop adding experiments and reposition as a narrower
security-measurement/systematization paper.

## Meta-review verdict

**Current paper:** weak reject on novelty; do not submit.  
**After P0 claim/related-work revision only:** still borderline.  
**After a positive direct adaptive-Simplex contract comparison:** credible
TDSC submission.  
**NDSS:** still not recommended under the current negative PPO and benign
utility boundaries.

