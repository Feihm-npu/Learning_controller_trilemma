# Reward-ingestion realism and detector-constrained attack WP results

> Finalized 2026-08-10. R1 passed both locked-trace and burned-seed gates. R2
> passed integrity/detectability gates but failed its held-out physical-effect
> gate and is closed without new seeds.

## Executive decision

- **R1 executable split-trust boundary: pass.** The modeled reward-only write
  set is implementable as an authenticated capability. Correctly placed origin
  binding rejects downstream mutation; a compromised producer can authenticate
  malicious semantics; trusted-reference repair preserves clean updates;
  resident authority contains the physical consequence.
- **R2 detector-constrained physical attack: negative.** The attack evaded all
  three frozen scalar-log checks and optimized a direct physical objective on
  an attacker-owned state set, but caused `0/24` failures on held-out 9070.
- **No new namespace.** Do not run 2071/2072 or retune the R2 candidate search.
  The paper retains no stealth claim.
- **Unresolved NDSS debt.** These experiments do not repair the failed benign
  adaptation utility versus freeze result.

## R1-A: locked V4 trace gate

Protocol:
`cartpole_reward_ingestion_boundary_protocol.md`.

Harness:
`safe_control_gym_cartpole_reward_ingestion_boundary.py`.

Across all five already opened V4 seeds:

- clean replay maximum final-parameter error: `0`;
- unsigned poisoned replay maximum error: `0`;
- compromised-producer authenticated replay maximum error: `0`;
- all `480` legitimate reward patches authorized;
- all attempts to patch eleven forbidden paths denied;
- all five forged-capability probes denied;
- all untouched origin chains verified;
- reward mutation, interior omission, adjacent reorder, record replay, and tail
  truncation were detected for every seed;
- origin binding rejected all 12 poisoned batches per seed;
- trusted-reference checking repaired all 96 edits per seed; and
- known-sign and scalar-envelope batch decisions exactly matched the frozen
  detector.

The unsigned and compromised-producer modes exactly link to the locked V4
physical result: poisoned raw release `27/120`, resident authority `0/120`.
Fail-closed and repair policies were not assigned new physical claims from
off-policy trace replay.

The signed run manifest is essential: a forward hash chain detects interior
deletion/reordering but cannot by itself reveal removal of the final record.

## R1-B: burned 2070/9070 end-to-end bridge

Protocol:
`cartpole_reward_ingestion_end_to_end_protocol.md`.

Harness:
`safe_control_gym_cartpole_reward_ingestion_end_to_end.py`.

The clean and poisoned training paths exactly reproduced the locked V3
parameters and physical rows. On the same 24 vulnerable-accepted states:

| Trust placement / authority | Update availability | Raw failures | Resident failures |
|---|---:|---:|---:|
| Clean reference | 1.0 | 0/24 | -- |
| Unsigned downstream mutation | 1.0 | 11/24 | 0/24 |
| Compromised producer signs malicious reward | 1.0 | 11/24 | 0/24 |
| Trusted-origin failure, batch-atomic reject | 0.0 | 0/24 | -- |
| Trusted-reference repair | 1.0 | 0/24 | -- |

All 11 vulnerable failures had timely resident switches. The result clarifies
the architectural alternatives:

- correct upstream origin integrity removes post-producer mutation but may
  freeze all learning when recovery is unavailable;
- signing by a compromised producer proves provenance, not semantic honesty;
- a trusted reference can preserve adaptation availability when reward is
  recomputable; and
- resident authority still contains downstream physical harm if upstream
  integrity fails.

This is one known seed used to connect the systems boundary to training and
physical behavior, not new generality evidence.

## R2: detector-constrained physical-objective smoke

Protocol:
`cartpole_detector_constrained_physical_attack_protocol.md`.

Harness:
`safe_control_gym_cartpole_detector_constrained_physical_attack.py`.

The attack evaluated `12,324` deterministic feasible reward vectors across 12
batches. Each candidate update was scored directly for five-step acceptance
and 120-step harm on 14 attacker-owned states that were independent of 9070.
The final effective snapshot was `(-7.24688,-0.73229)`.

Integrity results:

- all 12 batches passed the sign, scalar-envelope, batch-mean-envelope, and
  `L_inf <= 2` constraints;
- every batch changed all eight scalar rewards;
- learner reward-delta, raw-gradient, and next-parameter reconstruction errors
  were all exactly `0`;
- adaptation constraint violations: `0`;
- known-sign batch TPR: `0` at frozen FPR `0`;
- scalar-envelope batch TPR: `0` at frozen FPR `0.0357`;
- batch-mean-envelope TPR: `0` at frozen FPR `0.0357`;
- trusted-recomputation TPR: `1` at FPR `0`.

Optimization behavior separated on its own scoring set: batch 0 reached `1/14`
long-horizon failures, batches 1--11 reached `2/14`, while every selected
snapshot retained `14/14` five-step acceptance. Median per-batch selection
latency was `39.59 s` using 17 independent CasADi workers.

Held-out evaluation did not transfer:

- poisoned five-step acceptance: `24/24`;
- clean raw failures: `0/24`;
- poisoned raw failures: `0/24`;
- poison-only discordance: `0`;
- resident failures: `0/24`.

Therefore the smoke is a valid negative result, not an implementation failure.
It shows that evading the frozen scalar checks is feasible, but the tested
physical-objective construction did not retain the paper's harmful-release
effect. Optimizer-set harm without held-out transfer must not be reported as a
successful attack.

## Engineering audit

The end-to-end R1 script first failed before environment creation because the
local `.venv-safe-control` lacked PyTorch; the unchanged run succeeded under
the project's system interpreter, which contained the locked dependencies.

R2's initial monolithic CasADi evaluation and a shared-function threading
microbenchmark were stopped before any learner batch decision or result was
produced. Microbenchmarks showed near-linear cost (`0.62 s` for one candidate,
`32.12 s` for 64) and that a shared CVODES function is not thread-safe. The
final implementation uses independent environment/controller/CVODES objects
per worker, preserves the complete candidate set and original candidate order,
and completed without numerical errors. These were execution-engine fixes,
not outcome-driven changes to the attack.

## Scientific interpretation

R1 materially improves threat-model realism and makes log completeness
assumptions testable. It supports a narrow conditional security claim:
post-compromise reward-only writes are consequential when origin/reference
integrity is absent, and downstream authority placement determines whether
those writes become physical harm.

R2 does not upgrade the paper to a stealth-attack claim. Together with S1/S2,
it suggests a consistent boundary on 2070: detector-compatible reward edits
can move the two-parameter learner and even overfit a public physical surrogate,
but the demonstrated delayed harm has not survived the detector constraints on
held-out deployment states. Any further attack route would be a new work
package requiring a new hypothesis, not another variant or seed expansion.
