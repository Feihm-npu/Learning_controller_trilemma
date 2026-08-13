# Threat-model realism and reviewer-facing claim contract

> Locked presentation review, 2026-08-05. This work package changes no attack,
> learner, state pool, threshold, or result. It makes the already evaluated
> integrity precondition and escape conditions explicit.

## One-sentence threat model

After a reward-ingestion principal in an asynchronous learning-data plane is
compromised, a white-box attacker may make a bounded write to each scalar
reward record consumed by the updater, but cannot write the authenticated
runtime state/action path, learner code, gradients, parameters, optimizer,
certificate, release rule, or held-out deployment-state selection.

The security result is conditional on this foothold. The artifact does not
demonstrate compromise of a historian, broker, replay service, or reward
producer.

## Operational interpretation

The split is plausible when protected commissioning or edge retraining uses a
high-integrity runtime selector while an asynchronous updater consumes data
from a historian, telemetry broker, replay writer, or external KPI service.
The candidate can later be exported to a lower-latency controller or fleet
target without the training-time predictor. NIST SP 800-82 Rev. 3 describes
zoned OT architectures and data-management assets; MITRE ATT&CK for ICS
identifies the data historian as an asset that exchanges ICS and business
data. These references motivate the architecture, not the acquisition step:

- NIST SP 800-82 Rev. 3: `https://doi.org/10.6028/NIST.SP.800-82r3`
- MITRE Data Historian A0006: `https://attack.mitre.org/assets/A0006/`

## Integrity-control matrix

| Control | What it assumes | Effect on this attack | What it does not prove |
|---|---|---|---|
| Origin-bound, append-only reward record | Trusted producer signs reward with transition, action, identity, and time | Rejects post-producer mutation before learning | A compromised producer can sign a malicious value |
| Trusted recomputation | Reward is deterministic from authenticated transitions and the recomputer is trusted | Blocks every evaluated edit; measured batch TPR/FPR `1/0` | Not available for irreducibly external labels/KPIs |
| Known-sign check | Task guarantees nonpositive reward | Detects `90.5%` of poisoned batches at `0` FPR | Task-specific and incomplete |
| Scalar development envelope | Clean scalar range transfers | Detects `91.7%` at `3.6%` FPR | Distribution-dependent |
| Batch-mean envelope | Batch means transfer | Only `1.2%` TPR at `3.6%` FPR | Generic aggregate monitoring is weak here |
| Commit admission | Candidate can be checked on a declared set/horizon | Rejects or shrinks unsafe snapshot updates | Does not establish reward provenance |
| Resident predictive authority | Predictor/baseline remains online | `0/120` V4 failures with 27 timely switches | Detects consequence, not corruption |

## Reviewer-objection audit

| Likely objection | Direct answer now visible in paper |
|---|---|
| “Why can the attacker edit reward but not the controller?” | It compromises one least-privilege learning-data principal; Table 1 enumerates every attacker write boundary. |
| “Why not authenticate the log?” | Do so when possible. Origin-bound provenance removes the modeled post-producer mutation and is an explicit upstream escape condition. |
| “Why not recompute reward?” | If reward is deterministic from authenticated transitions, recomputation completely blocks the evaluated channel. The paper reports this negative boundary rather than assuming it away. |
| “Is the attack stealthy?” | No. Two frozen scalar checks exceed `0.90` batch TPR, and the abstract, threat model, evaluation, limitations, and conclusion all say so. |
| “Is permanent release artificial?” | It represents an intentional commissioning/export/promotion handoff made to avoid permanent compute, intervention, or backup-service dependence. The paper compares those costs. |
| “Does the attack defeat Simplex/MPSC?” | No. Resident predictive authority and permanent MPSC are escape conditions; the flaw is transferring their evidence to a different raw-release contract. |
| “Is this only a safety bug?” | The physical consequence is produced by an adversarial, bounded update-data write crossing a declared integrity boundary. The novelty is the security consequence of assurance-contract transfer, not reward poisoning or runtime assurance alone. |

## Reviewer-facing order

The first-pass narrative is now:

1. Title and abstract state the split-trust precondition.
2. Figure 1 shows the lower-integrity learning-data plane and high-integrity
   runtime-assurance plane.
3. The threat model enumerates attacker writes and explains intentional
   permanent release.
4. The evaluation leads with untouched V4 contract separation and labels it
   conditional on reward-record access.
5. Theory and cross-system evidence characterize consequences inside that
   boundary.
6. The integrity table reports which upstream controls remove the attack.
7. Limitations and conclusion repeat that this is neither a service exploit
   nor a stealth claim.

## Locked wording

Allowed:

- “conditional attack under a compromised reward-ingestion interface”;
- “finite reverse-switch evidence is contract-bound”;
- “origin integrity or trusted recomputation removes the upstream attack
  precondition”;
- “resident authority contains the downstream physical consequence.”

Disallowed:

- “stealthy reward poisoning”;
- “bypasses authenticated logs”;
- “compromises an industrial historian”;
- “defeats Simplex, shielding, or MPSC”;
- “proves raw release unsafe in general.”
