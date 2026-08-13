# Burned-seed reward-ingestion end-to-end protocol

> Locked on 2026-08-10 after the V4 locked-trace boundary gate passed and
> before this end-to-end execution. The only learner/evaluation pair is the
> already used development pair `2070/9070`. This is a systems-linkage smoke,
> not untouched confirmation and not authorization to open a new seed.

## Goal

Connect the executable reward-ingestion trust placements to actual training
and physical rollout behavior on one already burned pair. The experiment asks
whether the same bounded reward write has different consequences when it is
accepted unsigned, rejected after trusted-origin verification, signed by a
compromised producer, or repaired from a trusted reward reference.

The prerequisite is
`results/cartpole_reward_ingestion_boundary_decision.csv` with
`locked_trace_gate_pass=True`. The prerequisite artifact and this protocol are
hashed into the output.

## Locked learner and control contract

- Learner/evaluation seeds: `2070/9070` only.
- Two-parameter residual REINFORCE and fixed target `(18,-5)`.
- 12 batches, 8 steps per batch, `rho=0.005`, `sigma=0.8`, learning rate
  `1.0`, discount `0.97`, gradient cap `1.0`, reward-edit budget `2.0`, and the
  existing learner parameter box.
- The same 41-point CasADi adaptation filter, 32 baseline-admitted candidate
  states, 24 order-spanning evaluation states, five-step admission monitor,
  and 120-step physical horizon.
- Common-state comparisons use the states accepted by the vulnerable poisoned
  snapshot under the five-step contract.

The clean and vulnerable poisoned runs must exactly reproduce the already
locked V3 final parameters. They are rerun to connect the ingestion modes to
the training implementation, not treated as new statistical evidence.

## End-to-end modes

| Mode | Training behavior | Expected update availability | Physical interpretation |
|---|---|---:|---|
| `clean_reference` | accept trusted rewards | 1 | non-attacked reference |
| `unsigned_postproducer_mutation` | accept bounded malicious rewards | 1 | vulnerable raw release and resident authority |
| `origin_bound_fail_closed` | every batch containing an invalid producer MAC is rejected atomically | 0 if all 12 batches contain edits | unchanged initial residual policy; raw release evaluated on the common vulnerable cohort |
| `compromised_producer_valid` | accept producer-authenticated malicious rewards | 1 | identical candidate to unsigned mutation; provenance cannot establish honest semantics |
| `trusted_reference_repair` | replace each mismatching reward with its trusted value before update | 1 | identical training path to the clean reference |

For `origin_bound_fail_closed`, the trainer uses the existing global
`freeze_updates` path because the locked 2070 attack edits every batch. The
attack is still computed and its budget/nonzero-batch integrity is checked,
but no rejected batch updates learner parameters. If any batch has no nonzero
edit, this equivalence is invalid and the experiment stops.

For `compromised_producer_valid` and `trusted_reference_repair`, the preceding
message-level experiment already checked signature placement and repair. This
run reuses the functionally identical poisoned and clean training paths; it
does not waste compute by rerunning duplicate trajectories under a new label.

## Measurements

Report per mode:

- accepted, rejected, and repaired reward records and batches;
- update availability and actor updates;
- maximum reward edit and adaptation constraint violations;
- final effective gain and bias;
- physical failures on the common vulnerable-accepted states;
- resident switches and failures for the vulnerable candidate; and
- mean physical reward as a descriptive outcome.

The fail-closed mode's zero update availability is an explicit availability
cost. It does not satisfy the paper's separate “benign adaptation utility vs.
freeze” requirement. Trusted-reference repair, if available, is the control
that preserves clean adaptation rather than freezing.

## Pass and stop rule

The systems bridge passes only if:

1. the prerequisite locked-trace gate is valid;
2. clean and poisoned final effective parameters match locked V3 values within
   `1e-10`;
3. all 12 poisoned 2070 batches contain a nonzero edit within the locked
   budget, making global freeze equivalent to batch-atomic origin rejection;
4. the origin-bound candidate remains exactly the initial zero residual;
5. the compromised-producer candidate exactly equals the vulnerable unsigned
   candidate;
6. trusted-reference repair exactly equals the clean candidate;
7. vulnerable raw release has at least one common-state physical failure,
   while resident authority has none and switches no later than each
   corresponding failure; and
8. origin-bound fail-closed and trusted-reference repair have no more physical
   failures than the clean reference on the same common cohort.

If any implementation-integrity condition fails, stop. If the bridge passes,
R1 is complete. No fresh seed is authorized: the next scientific decision is
whether the remaining detector-constrained attack WP merits its single
burned-seed smoke.

## Claim boundary

This smoke demonstrates executable trust-placement consequences on a known
pair. It does not add a fourth independent learner seed, establish exploit
acquisition, prove production-broker hardening, or show benign utility gains
over freeze.
