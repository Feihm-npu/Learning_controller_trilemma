# Reward-ingestion boundary experiment protocol

> Locked on 2026-08-10 before executing the reward-ingestion boundary harness.
> The experiment uses only the already opened V4 traces for learner seeds
> `2100--2104`. It does not authorize a new learner/evaluation seed, attack
> target, reward budget, detector threshold, or physical rollout.

## Question

Can the paper's split-trust precondition be represented as an executable,
least-privilege learning-data interface, and do origin integrity and trust
placement have the effects claimed by the threat model?

This work package evaluates the capability and integrity boundary after a
reward-writer credential has been compromised. It does not demonstrate how
that credential is acquired and does not model host root compromise.

## Locked input

- Step source: `results/cartpole_v4_untouched_confirmation_steps.csv`.
- Locked outcomes: `results/cartpole_v4_untouched_confirmation_training.csv`
  and `results/cartpole_v4_untouched_confirmation_aggregate.csv`.
- Detector calibration:
  `results/cartpole_reward_detectability_calibration.csv`.
- Every input digest is recorded in the decision output.
- All five V4 learner seeds and both clean and poisoned mechanisms are replayed;
  no seed or failed batch may be removed.

The trace exposes the exact learner-consumed transition projection: normalized
actor features, exploration noise, terminal flag, and scalar reward. It does
not contain the full environment state/action record. Consequently, the
experiment calls equality with the locked trusted reward a **trusted-reference
check**, not a new end-to-end demonstration that reward was recomputed from a
complete transition.

## Executable capability boundary

The ingestion service mints an authenticated capability for principal
`reward-writer` with one permitted patch path: `reward`. The capability binds
the principal, allowed path, run, and expiry. The service verifies the
capability before applying a patch.

The positive test patches `reward`. Locked negative tests attempt to patch:

1. `feature_gain_coordinate`;
2. `feature_bias_coordinate`;
3. `exploration_noise`;
4. `done`;
5. `run_id`;
6. `batch`;
7. `step`;
8. `trainer.params`;
9. `optimizer.state`;
10. `release.decision`; and
11. `certificate.state`.

A capability whose allowed-path claim is modified after minting is an
additional negative test. The boundary passes only if every legitimate reward
patch is authorized and every forbidden-path or forged-capability request is
denied.

This is a message-level capability experiment, not an operating-system or
container escape experiment. The scientific claim is that the modeled write
set is implementable and auditable, not that this Python harness is a hardened
production broker.

## Integrity modes

For every poisoned V4 record, construct an origin envelope that binds
`run_id`, `batch`, `step`, both feature coordinates, exploration noise,
terminal flag, reward, and the digest of the preceding envelope. A signed run
manifest binds the expected record count and final chain digest. Canonical
serialization and HMAC-SHA256 provide a deterministic stand-in for origin
authentication. The reward-writer never receives the trusted-producer key.

Value integrity and sequence completeness are tested separately. For every
seed, the untouched trusted chain must verify, while each of the following
locked probes must be detected: mutation of one reward, omission of an
interior record, reordering of adjacent records, replay of one record, and
truncation of the final record. The signed manifest is required because a
forward chain alone cannot reveal tail truncation.

| Mode | Producer/writer placement | Ingestion action | Locked expectation |
|---|---|---|---|
| `unsigned_postproducer_mutation` | trusted producer, compromised downstream writer | accept the authorized reward patch without origin verification | all poisoned batches accepted; exact poisoned-policy replay |
| `origin_bound_fail_closed` | trusted producer, compromised downstream writer | verify the producer MAC after mutation; reject the entire batch if any record is invalid | every nonzero-mutated poisoned batch rejected; no claim of exact end-to-end policy |
| `compromised_producer_valid` | producer itself compromised | producer signs the malicious reward; accept if the MAC is valid | all poisoned batches accepted; exact poisoned-policy replay |
| `trusted_reference_repair` | trusted reference remains outside the compromised writer | replace a mismatching submitted reward with the locked trusted reward | every nonzero edit repaired; exact same-trajectory true-reward counterfactual replay |
| `known_sign_fail_closed` | no origin trust; task-specific semantic invariant | reject a batch containing a positive reward | reproduce the frozen detector's batch decisions |
| `scalar_envelope_fail_closed` | no origin trust; frozen development envelope | reject a batch with a reward outside the frozen scalar range | reproduce the frozen detector's batch decisions |

Batch-atomic rejection is locked before execution. Partial batches are not sent
to the learner. For rejected batches, the offline audit leaves the learner
parameters unchanged and continues over the remaining locked trace only to
measure availability and parameter displacement. Because later features were
collected under another policy, this counterfactual is explicitly off-policy
and is not physical-effect evidence.

## Replay and measurements

For clean and poisoned streams, reconstruct each REINFORCE update from the
locked features, exploration noise, reward, and terminal flag, including the
locked gradient cap and parameter box. Report:

- maximum final effective-parameter error against the V4 training artifact;
- accepted, rejected, repaired, and origin-invalid records and batches;
- detection of mutation, omission, reorder, replay, and tail-truncation
  probes;
- authorized and denied capability operations;
- forged-capability denial;
- verification latency as an implementation measurement, not a performance
  claim;
- final effective parameters for every integrity mode; and
- availability as accepted batches divided by 12.

The aggregate V4 physical result is linked to a mode only when that mode exactly
reconstructs the locked poisoned snapshot. New physical safety claims for
fail-closed or repaired modes require a later end-to-end run.

## Pass and stop rules

The locked-trace gate passes only if:

1. clean and unsigned-poison replay each have maximum final effective-parameter
   error at most `1e-10`;
2. `compromised_producer_valid` also exactly reconstructs the poisoned policy;
3. all reward patches pass the scoped capability check;
4. all forbidden paths and the forged capability are denied;
5. origin-bound verification rejects every batch containing a nonzero
   post-producer mutation;
6. trusted-reference repair observes and repairs every nonzero edit;
7. every locked sequence-completeness probe is detected while every untouched
   trusted chain verifies;
8. known-sign and scalar-envelope batch decisions equal the frozen detector
   decisions; and
9. input and protocol digests are emitted.

If replay error exceeds `1e-10`, capability isolation fails, or detector
decisions disagree, stop and repair the harness without running any physical
experiment. If the gate passes, the only authorized next experiment is an
end-to-end run on the already burned `2070/9070` pair. No fresh seed namespace
is opened by this protocol.

## Claims this experiment cannot support

- exploitation of a real historian, broker, or KPI producer;
- resilience to host root compromise or key theft from the trusted producer;
- stealth against the frozen scalar checks;
- trusted recomputation from full state/action data;
- physical safety of a fail-closed or repair policy without the gated
  end-to-end run.
