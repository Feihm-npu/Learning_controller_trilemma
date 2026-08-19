#!/usr/bin/env python3
"""Executable reward-ingestion capability and integrity boundary audit.

The audit consumes only the locked V4 step traces.  HMAC keys are fixed test
fixtures: HMAC is used to exercise trust placement, not to benchmark key
management or claim production cryptographic hardening.
"""

from __future__ import annotations

import base64
import csv
import hashlib
import hmac
import json
import time
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Iterable

import numpy as np

import safe_control_gym_reinforce_reward_poisoning as reinforce
import safe_control_gym_reward_log_detectability as detector


ROOT = Path(__file__).resolve().parent
RESULTS = ROOT / "results"
STEP_SOURCE = RESULTS / "cartpole_v4_untouched_confirmation_steps.csv"
TRAINING_SOURCE = RESULTS / "cartpole_v4_untouched_confirmation_training.csv"
AGGREGATE_SOURCE = RESULTS / "cartpole_v4_untouched_confirmation_aggregate.csv"
CALIBRATION_SOURCE = RESULTS / "cartpole_reward_detectability_calibration.csv"
PROTOCOL = ROOT / "cartpole_reward_ingestion_boundary_protocol.md"
OUTPUT_PREFIX = RESULTS / "cartpole_reward_ingestion_boundary"

LEARNER_SEEDS = (2100, 2101, 2102, 2103, 2104)
BATCHES = 12
BATCH_STEPS = 8
SIGMA = 0.8
GAMMA = 0.97
ACTOR_LR = 1.0
GRADIENT_CAP = 1.0
REPLAY_TOLERANCE = 1e-10
EDIT_TOLERANCE = 1e-12
ZERO_DIGEST = "0" * 64
CAPABILITY_EXPIRY_EPOCH = 4_102_444_800

PRODUCER_KEY = hashlib.sha256(
    b"reward-ingestion-boundary/trusted-producer/test-fixture/v1"
).digest()
BROKER_KEY = hashlib.sha256(
    b"reward-ingestion-boundary/capability-broker/test-fixture/v1"
).digest()

FORBIDDEN_PATHS = (
    "feature_gain_coordinate",
    "feature_bias_coordinate",
    "exploration_noise",
    "done",
    "run_id",
    "batch",
    "step",
    "trainer.params",
    "optimizer.state",
    "release.decision",
    "certificate.state",
)

MODES = (
    "unsigned_postproducer_mutation",
    "origin_bound_fail_closed",
    "compromised_producer_valid",
    "trusted_reference_repair",
    "known_sign_fail_closed",
    "scalar_envelope_fail_closed",
)


@dataclass(frozen=True)
class Event:
    run_id: str
    batch: int
    step: int
    feature_gain_coordinate: str
    feature_bias_coordinate: str
    exploration_noise: str
    done: str
    reward: str
    previous_digest: str


@dataclass(frozen=True)
class SignedEnvelope:
    event: Event
    origin_mac: str


@dataclass(frozen=True)
class RunManifest:
    run_id: str
    expected_records: int
    final_digest: str
    origin_mac: str


@dataclass(frozen=True)
class CapabilityClaims:
    principal: str
    run_id: str
    allowed_paths: tuple[str, ...]
    expires_epoch: int


@dataclass(frozen=True)
class SignedCapability:
    claims: CapabilityClaims
    broker_mac: str


@dataclass(frozen=True)
class PatchResult:
    authorized: bool
    reason: str
    envelope: SignedEnvelope


@dataclass
class ReplayRow:
    learner_seed: int
    stream: str
    batches_replayed: int
    final_gain: float
    final_bias: float
    locked_final_gain: float
    locked_final_bias: float
    final_effective_parameter_error: float
    exact_replay: bool


@dataclass
class CapabilityRow:
    learner_seed: int
    principal: str
    requested_path: str
    forged_claim: bool
    attempts: int
    authorized: int
    denied: int
    expected_authorized: bool
    expectation_met: bool


@dataclass
class CompletenessRow:
    learner_seed: int
    probe: str
    expected_valid: bool
    observed_valid: bool
    detected: bool
    reason: str


@dataclass
class IntegrityModeRow:
    learner_seed: int
    mode: str
    records: int
    nonzero_edits: int
    authorized_reward_patches: int
    integrity_flagged_records: int
    accepted_records: int
    rejected_records: int
    repaired_records: int
    accepted_batches: int
    rejected_batches: int
    availability: float
    verification_operations: int
    verification_elapsed_ns: int
    final_gain: float
    final_bias: float
    poisoned_parameter_error: float
    exact_poisoned_snapshot_match: bool
    offline_counterfactual_only: bool
    locked_physical_link_valid: bool
    linked_poisoned_release_violations: int | None
    linked_resident_predictive_violations: int | None


@dataclass
class DetectorAgreementRow:
    learner_seed: int
    detector: str
    batches: int
    independently_flagged_batches: int
    frozen_detector_flagged_batches: int
    exact_batch_decision_match: bool


@dataclass
class BoundaryDecision:
    learner_seeds: int
    step_source_sha256: str
    training_source_sha256: str
    aggregate_source_sha256: str
    calibration_source_sha256: str
    protocol_sha256: str
    harness_sha256: str
    max_clean_replay_error: float
    max_unsigned_poison_replay_error: float
    max_compromised_producer_replay_error: float
    exact_replay_pass: bool
    reward_capability_pass: bool
    forbidden_path_denial_pass: bool
    forged_capability_denial_pass: bool
    origin_bound_rejection_pass: bool
    trusted_reference_repair_pass: bool
    sequence_completeness_pass: bool
    detector_agreement_pass: bool
    linked_v4_poisoned_release_violations: int
    linked_v4_resident_predictive_violations: int
    no_new_seed_namespace_opened: bool
    locked_trace_gate_pass: bool
    next_authorized_stage: str


def canonical(value: object) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("utf-8")


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def keyed_mac(key: bytes, value: object) -> str:
    return hmac.new(key, canonical(value), hashlib.sha256).hexdigest()


def event_payload(event: Event) -> dict[str, object]:
    return asdict(event)


def envelope_digest(envelope: SignedEnvelope) -> str:
    return hashlib.sha256(
        canonical(
            {
                "event": event_payload(envelope.event),
                "origin_mac": envelope.origin_mac,
            }
        )
    ).hexdigest()


def sign_event(event: Event) -> SignedEnvelope:
    return SignedEnvelope(event, keyed_mac(PRODUCER_KEY, event_payload(event)))


def verify_event(envelope: SignedEnvelope) -> bool:
    expected = keyed_mac(PRODUCER_KEY, event_payload(envelope.event))
    return hmac.compare_digest(expected, envelope.origin_mac)


def manifest_payload(manifest: RunManifest) -> dict[str, object]:
    return {
        "run_id": manifest.run_id,
        "expected_records": manifest.expected_records,
        "final_digest": manifest.final_digest,
    }


def sign_manifest(run_id: str, expected_records: int, final_digest: str) -> RunManifest:
    unsigned = RunManifest(run_id, expected_records, final_digest, "")
    return replace(unsigned, origin_mac=keyed_mac(PRODUCER_KEY, manifest_payload(unsigned)))


def verify_manifest(manifest: RunManifest) -> bool:
    expected = keyed_mac(PRODUCER_KEY, manifest_payload(manifest))
    return hmac.compare_digest(expected, manifest.origin_mac)


def capability_payload(claims: CapabilityClaims) -> dict[str, object]:
    return {
        "principal": claims.principal,
        "run_id": claims.run_id,
        "allowed_paths": list(claims.allowed_paths),
        "expires_epoch": claims.expires_epoch,
    }


def mint_reward_capability(run_id: str) -> SignedCapability:
    claims = CapabilityClaims(
        principal="reward-writer",
        run_id=run_id,
        allowed_paths=("reward",),
        expires_epoch=CAPABILITY_EXPIRY_EPOCH,
    )
    return SignedCapability(claims, keyed_mac(BROKER_KEY, capability_payload(claims)))


def verify_capability(
    capability: SignedCapability, *, run_id: str, path: str, now_epoch: int
) -> tuple[bool, str]:
    expected = keyed_mac(BROKER_KEY, capability_payload(capability.claims))
    if not hmac.compare_digest(expected, capability.broker_mac):
        return False, "invalid_capability_mac"
    if capability.claims.principal != "reward-writer":
        return False, "wrong_principal"
    if capability.claims.run_id != run_id:
        return False, "wrong_run"
    if now_epoch > capability.claims.expires_epoch:
        return False, "expired"
    if path not in capability.claims.allowed_paths:
        return False, "path_not_allowed"
    return True, "authorized"


def patch_envelope(
    envelope: SignedEnvelope,
    *,
    path: str,
    value: str,
    capability: SignedCapability,
    now_epoch: int,
) -> PatchResult:
    authorized, reason = verify_capability(
        capability,
        run_id=envelope.event.run_id,
        path=path,
        now_epoch=now_epoch,
    )
    if not authorized:
        return PatchResult(False, reason, envelope)
    if path not in Event.__dataclass_fields__:
        return PatchResult(False, "unknown_event_path", envelope)
    patched = replace(envelope.event, **{path: value})
    return PatchResult(True, reason, SignedEnvelope(patched, envelope.origin_mac))


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as source:
        return list(csv.DictReader(source))


def write_rows(path: Path, rows: Iterable[object]) -> None:
    dictionaries = [asdict(row) for row in rows]
    if not dictionaries:
        raise RuntimeError(f"refusing to write empty result: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=list(dictionaries[0]))
        writer.writeheader()
        writer.writerows(dictionaries)


def selected_rows(
    rows: list[dict[str, str]], seed: int, mechanism: str
) -> list[dict[str, str]]:
    selected = [
        row
        for row in rows
        if int(row["learner_seed"]) == seed and row["mechanism"] == mechanism
    ]
    selected.sort(key=lambda row: (int(row["batch"]), int(row["step"])))
    if len(selected) != BATCHES * BATCH_STEPS:
        raise RuntimeError(
            f"expected {BATCHES * BATCH_STEPS} {mechanism} rows for {seed}, "
            f"got {len(selected)}"
        )
    return selected


def run_id(seed: int) -> str:
    return f"v4-reward-stream-{seed}"


def build_chain(
    rows: list[dict[str, str]], seed: int, *, reward_column: str
) -> tuple[list[SignedEnvelope], RunManifest]:
    previous = ZERO_DIGEST
    envelopes: list[SignedEnvelope] = []
    for row in rows:
        event = Event(
            run_id=run_id(seed),
            batch=int(row["batch"]),
            step=int(row["step"]),
            feature_gain_coordinate=row["feature_gain_coordinate"],
            feature_bias_coordinate=row["feature_bias_coordinate"],
            exploration_noise=row["exploration_noise"],
            done=row["done"],
            reward=row[reward_column],
            previous_digest=previous,
        )
        envelope = sign_event(event)
        envelopes.append(envelope)
        previous = envelope_digest(envelope)
    return envelopes, sign_manifest(run_id(seed), len(envelopes), previous)


def verify_chain(
    envelopes: list[SignedEnvelope], manifest: RunManifest
) -> tuple[bool, str]:
    if not verify_manifest(manifest):
        return False, "invalid_manifest_mac"
    if len(envelopes) != manifest.expected_records:
        return False, "record_count_mismatch"
    previous = ZERO_DIGEST
    seen: set[tuple[int, int]] = set()
    for index, envelope in enumerate(envelopes):
        event = envelope.event
        if event.run_id != manifest.run_id:
            return False, "run_id_mismatch"
        expected_key = (index // BATCH_STEPS, index % BATCH_STEPS)
        key = (event.batch, event.step)
        if key != expected_key:
            return False, "sequence_mismatch"
        if key in seen:
            return False, "replayed_record"
        seen.add(key)
        if event.previous_digest != previous:
            return False, "chain_mismatch"
        if not verify_event(envelope):
            return False, "invalid_event_mac"
        previous = envelope_digest(envelope)
    if previous != manifest.final_digest:
        return False, "final_digest_mismatch"
    return True, "valid"


def completeness_probes(
    seed: int, envelopes: list[SignedEnvelope], manifest: RunManifest
) -> list[CompletenessRow]:
    probes: list[tuple[str, list[SignedEnvelope], bool]] = [
        ("untouched", list(envelopes), True),
    ]
    mutation = list(envelopes)
    mutation[17] = replace(
        mutation[17], event=replace(mutation[17].event, reward="123.0")
    )
    probes.append(("reward_mutation", mutation, False))
    omission = list(envelopes)
    del omission[17]
    probes.append(("interior_omission", omission, False))
    reordered = list(envelopes)
    reordered[17], reordered[18] = reordered[18], reordered[17]
    probes.append(("adjacent_reorder", reordered, False))
    replayed = list(envelopes)
    replayed.insert(18, replayed[17])
    probes.append(("record_replay", replayed, False))
    probes.append(("tail_truncation", list(envelopes[:-1]), False))

    output: list[CompletenessRow] = []
    for probe, candidate, expected_valid in probes:
        observed_valid, reason = verify_chain(candidate, manifest)
        output.append(
            CompletenessRow(
                learner_seed=seed,
                probe=probe,
                expected_valid=expected_valid,
                observed_valid=observed_valid,
                detected=observed_valid == expected_valid,
                reason=reason,
            )
        )
    return output


def grouped_batches(rows: list[dict[str, str]]) -> list[list[dict[str, str]]]:
    return [
        [row for row in rows if int(row["batch"]) == batch]
        for batch in range(BATCHES)
    ]


def apply_update(current: np.ndarray, rows: list[dict[str, str]], rewards: list[str]) -> np.ndarray:
    features = np.asarray(
        [
            [float(row["feature_gain_coordinate"]), float(row["feature_bias_coordinate"])]
            for row in rows
        ],
        dtype=float,
    )
    noise = np.asarray([float(row["exploration_noise"]) for row in rows], dtype=float)
    dones = np.asarray([float(row["done"]) for row in rows], dtype=float)
    reward_values = np.asarray([float(value) for value in rewards], dtype=float)
    gradient = reinforce.reinforce_gradient(
        features,
        noise,
        reward_values,
        dones,
        sigma=SIGMA,
        gamma=GAMMA,
    )
    norm = float(np.linalg.norm(gradient))
    if norm > GRADIENT_CAP:
        gradient *= GRADIENT_CAP / norm
    return np.minimum(
        np.maximum(current + ACTOR_LR * gradient, reinforce.LEARNER_LOW),
        reinforce.LEARNER_HIGH,
    )


def replay(rows: list[dict[str, str]], reward_column: str) -> np.ndarray:
    current = np.zeros(2, dtype=float)
    for batch_rows in grouped_batches(rows):
        current = apply_update(current, batch_rows, [row[reward_column] for row in batch_rows])
    return reinforce.to_effective_params(current)


def locked_params(training: list[dict[str, str]], seed: int, mechanism: str) -> np.ndarray:
    matches = [
        row
        for row in training
        if int(row["learner_seed"]) == seed and row["mechanism"] == mechanism
    ]
    if len(matches) != 1:
        raise RuntimeError(f"missing locked training row for {seed}/{mechanism}")
    return np.asarray(
        [float(matches[0]["final_gain"]), float(matches[0]["final_bias"])],
        dtype=float,
    )


def capability_audit(
    seed: int, poison_rows: list[dict[str, str]], envelopes: list[SignedEnvelope]
) -> list[CapabilityRow]:
    capability = mint_reward_capability(run_id(seed))
    now_epoch = int(time.time())
    positive = [
        patch_envelope(
            envelope,
            path="reward",
            value=row["logged_reward"],
            capability=capability,
            now_epoch=now_epoch,
        )
        for envelope, row in zip(envelopes, poison_rows)
    ]
    output = [
        CapabilityRow(
            learner_seed=seed,
            principal="reward-writer",
            requested_path="reward",
            forged_claim=False,
            attempts=len(positive),
            authorized=sum(result.authorized for result in positive),
            denied=sum(not result.authorized for result in positive),
            expected_authorized=True,
            expectation_met=all(result.authorized for result in positive),
        )
    ]
    first = envelopes[0]
    for path in FORBIDDEN_PATHS:
        result = patch_envelope(
            first,
            path=path,
            value="forbidden-write",
            capability=capability,
            now_epoch=now_epoch,
        )
        output.append(
            CapabilityRow(
                learner_seed=seed,
                principal="reward-writer",
                requested_path=path,
                forged_claim=False,
                attempts=1,
                authorized=int(result.authorized),
                denied=int(not result.authorized),
                expected_authorized=False,
                expectation_met=not result.authorized,
            )
        )
    forged = replace(
        capability,
        claims=replace(
            capability.claims,
            allowed_paths=capability.claims.allowed_paths + ("trainer.params",),
        ),
    )
    forged_result = patch_envelope(
        first,
        path="trainer.params",
        value="forged-write",
        capability=forged,
        now_epoch=now_epoch,
    )
    output.append(
        CapabilityRow(
            learner_seed=seed,
            principal="reward-writer",
            requested_path="trainer.params",
            forged_claim=True,
            attempts=1,
            authorized=int(forged_result.authorized),
            denied=int(not forged_result.authorized),
            expected_authorized=False,
            expectation_met=not forged_result.authorized,
        )
    )
    return output


def detector_agreement(
    seed: int,
    poison_rows: list[dict[str, str]],
    calibration: detector.CalibrationRow,
) -> tuple[list[DetectorAgreementRow], dict[str, set[int]]]:
    flagged: dict[str, set[int]] = {}
    output: list[DetectorAgreementRow] = []
    independent_checks = {
        "known_sign": lambda value: value > calibration.positive_reward_threshold,
        "scalar_envelope": lambda value: bool(
            value < calibration.scalar_reward_min - calibration.envelope_tolerance
            or value > calibration.scalar_reward_max + calibration.envelope_tolerance
        ),
    }
    for name, check in independent_checks.items():
        independent = {
            batch
            for batch, batch_rows in enumerate(grouped_batches(poison_rows))
            if any(check(float(row["logged_reward"])) for row in batch_rows)
        }
        frozen = {
            batch
            for batch, batch_rows in enumerate(grouped_batches(poison_rows))
            if any(detector.step_flag(name, row, calibration) for row in batch_rows)
        }
        flagged[name] = independent
        output.append(
            DetectorAgreementRow(
                learner_seed=seed,
                detector=name,
                batches=BATCHES,
                independently_flagged_batches=len(independent),
                frozen_detector_flagged_batches=len(frozen),
                exact_batch_decision_match=independent == frozen,
            )
        )
    return output, flagged


def process_mode(
    seed: int,
    poison_rows: list[dict[str, str]],
    true_chain: list[SignedEnvelope],
    mode: str,
    capability: SignedCapability,
    flagged_batches: dict[str, set[int]],
    locked_poison: np.ndarray,
    aggregate: dict[str, str],
) -> IntegrityModeRow:
    if mode not in MODES:
        raise ValueError(mode)
    now_epoch = int(time.time())
    patches = [
        patch_envelope(
            envelope,
            path="reward",
            value=row["logged_reward"],
            capability=capability,
            now_epoch=now_epoch,
        )
        for envelope, row in zip(true_chain, poison_rows)
    ]
    if not all(result.authorized for result in patches):
        raise RuntimeError(f"authorized reward patch failed for seed {seed}")
    submitted = [result.envelope for result in patches]

    malicious_chain: list[SignedEnvelope] | None = None
    if mode == "compromised_producer_valid":
        malicious_chain, malicious_manifest = build_chain(
            poison_rows, seed, reward_column="logged_reward"
        )
        chain_valid, reason = verify_chain(malicious_chain, malicious_manifest)
        if not chain_valid:
            raise RuntimeError(f"malicious producer chain unexpectedly invalid: {reason}")

    current = np.zeros(2, dtype=float)
    accepted_batches = 0
    rejected_batches = 0
    accepted_records = 0
    rejected_records = 0
    repaired_records = 0
    flagged_records = 0
    verification_operations = 0
    verification_elapsed_ns = 0
    nonzero_edits = sum(
        abs(float(row["logged_reward"]) - float(row["true_reward"])) > EDIT_TOLERANCE
        for row in poison_rows
    )

    for batch in range(BATCHES):
        start = batch * BATCH_STEPS
        stop = start + BATCH_STEPS
        batch_rows = poison_rows[start:stop]
        batch_submitted = submitted[start:stop]
        batch_accepted = True
        rewards = [envelope.event.reward for envelope in batch_submitted]

        if mode == "origin_bound_fail_closed":
            before = time.perf_counter_ns()
            validity = [verify_event(envelope) for envelope in batch_submitted]
            verification_elapsed_ns += time.perf_counter_ns() - before
            verification_operations += len(validity)
            flagged_records += sum(not value for value in validity)
            batch_accepted = all(validity)
        elif mode == "compromised_producer_valid":
            assert malicious_chain is not None
            batch_malicious = malicious_chain[start:stop]
            before = time.perf_counter_ns()
            validity = [verify_event(envelope) for envelope in batch_malicious]
            verification_elapsed_ns += time.perf_counter_ns() - before
            verification_operations += len(validity)
            flagged_records += sum(not value for value in validity)
            batch_accepted = all(validity)
            rewards = [envelope.event.reward for envelope in batch_malicious]
        elif mode == "trusted_reference_repair":
            rewards = []
            for row, envelope in zip(batch_rows, batch_submitted):
                submitted_reward = float(envelope.event.reward)
                trusted_reward = float(row["true_reward"])
                mismatch = abs(submitted_reward - trusted_reward) > EDIT_TOLERANCE
                flagged_records += int(mismatch)
                repaired_records += int(mismatch)
                rewards.append(row["true_reward"] if mismatch else envelope.event.reward)
        elif mode == "known_sign_fail_closed":
            flagged_records += sum(float(value) > 0.0 for value in rewards)
            batch_accepted = batch not in flagged_batches["known_sign"]
        elif mode == "scalar_envelope_fail_closed":
            calibration = detector.load_calibration()
            flagged_records += sum(
                float(value) < calibration.scalar_reward_min - calibration.envelope_tolerance
                or float(value) > calibration.scalar_reward_max + calibration.envelope_tolerance
                for value in rewards
            )
            batch_accepted = batch not in flagged_batches["scalar_envelope"]
        elif mode == "unsigned_postproducer_mutation":
            pass

        if batch_accepted:
            current = apply_update(current, batch_rows, rewards)
            accepted_batches += 1
            accepted_records += len(batch_rows)
        else:
            rejected_batches += 1
            rejected_records += len(batch_rows)

    effective = reinforce.to_effective_params(current)
    poison_error = float(np.linalg.norm(effective - locked_poison))
    exact_match = poison_error <= REPLAY_TOLERANCE
    physical_link = bool(
        exact_match
        and mode
        in ("unsigned_postproducer_mutation", "compromised_producer_valid")
    )
    return IntegrityModeRow(
        learner_seed=seed,
        mode=mode,
        records=len(poison_rows),
        nonzero_edits=nonzero_edits,
        authorized_reward_patches=sum(result.authorized for result in patches),
        integrity_flagged_records=flagged_records,
        accepted_records=accepted_records,
        rejected_records=rejected_records,
        repaired_records=repaired_records,
        accepted_batches=accepted_batches,
        rejected_batches=rejected_batches,
        availability=accepted_batches / BATCHES,
        verification_operations=verification_operations,
        verification_elapsed_ns=verification_elapsed_ns,
        final_gain=float(effective[0]),
        final_bias=float(effective[1]),
        poisoned_parameter_error=poison_error,
        exact_poisoned_snapshot_match=exact_match,
        offline_counterfactual_only=mode
        in (
            "origin_bound_fail_closed",
            "trusted_reference_repair",
            "known_sign_fail_closed",
            "scalar_envelope_fail_closed",
        ),
        locked_physical_link_valid=physical_link,
        linked_poisoned_release_violations=(
            int(aggregate["poisoned_release_violations"]) if physical_link else None
        ),
        linked_resident_predictive_violations=(
            int(aggregate["resident_predictive_violations"]) if physical_link else None
        ),
    )


def output_path(suffix: str) -> Path:
    return Path(f"{OUTPUT_PREFIX}_{suffix}.csv")


def main() -> None:
    steps = read_rows(STEP_SOURCE)
    training = read_rows(TRAINING_SOURCE)
    aggregate_rows = read_rows(AGGREGATE_SOURCE)
    if len(aggregate_rows) != 1:
        raise RuntimeError("expected one locked V4 aggregate row")
    aggregate = aggregate_rows[0]
    calibration = detector.load_calibration()

    replay_rows: list[ReplayRow] = []
    capability_rows: list[CapabilityRow] = []
    completeness_rows: list[CompletenessRow] = []
    integrity_rows: list[IntegrityModeRow] = []
    detector_rows: list[DetectorAgreementRow] = []

    for seed in LEARNER_SEEDS:
        clean_rows = selected_rows(steps, seed, "clean")
        poison_rows = selected_rows(steps, seed, "fixed_target_tanh")
        clean_effective = replay(clean_rows, "logged_reward")
        poison_effective = replay(poison_rows, "logged_reward")
        clean_locked = locked_params(training, seed, "clean")
        poison_locked = locked_params(training, seed, "fixed_target_tanh")
        for stream, effective, locked in (
            ("clean", clean_effective, clean_locked),
            ("poisoned", poison_effective, poison_locked),
        ):
            error = float(np.linalg.norm(effective - locked))
            replay_rows.append(
                ReplayRow(
                    learner_seed=seed,
                    stream=stream,
                    batches_replayed=BATCHES,
                    final_gain=float(effective[0]),
                    final_bias=float(effective[1]),
                    locked_final_gain=float(locked[0]),
                    locked_final_bias=float(locked[1]),
                    final_effective_parameter_error=error,
                    exact_replay=error <= REPLAY_TOLERANCE,
                )
            )

        true_chain, manifest = build_chain(poison_rows, seed, reward_column="true_reward")
        capability_rows.extend(capability_audit(seed, poison_rows, true_chain))
        completeness_rows.extend(completeness_probes(seed, true_chain, manifest))
        seed_detector_rows, flagged = detector_agreement(seed, poison_rows, calibration)
        detector_rows.extend(seed_detector_rows)
        capability = mint_reward_capability(run_id(seed))
        for mode in MODES:
            integrity_rows.append(
                process_mode(
                    seed,
                    poison_rows,
                    true_chain,
                    mode,
                    capability,
                    flagged,
                    poison_locked,
                    aggregate,
                )
            )

    clean_errors = [
        row.final_effective_parameter_error for row in replay_rows if row.stream == "clean"
    ]
    unsigned_errors = [
        row.poisoned_parameter_error
        for row in integrity_rows
        if row.mode == "unsigned_postproducer_mutation"
    ]
    compromised_errors = [
        row.poisoned_parameter_error
        for row in integrity_rows
        if row.mode == "compromised_producer_valid"
    ]
    reward_capability_pass = all(
        row.expectation_met
        for row in capability_rows
        if row.requested_path == "reward" and not row.forged_claim
    )
    forbidden_pass = all(
        row.expectation_met
        for row in capability_rows
        if row.requested_path in FORBIDDEN_PATHS and not row.forged_claim
    )
    forged_pass = all(
        row.expectation_met for row in capability_rows if row.forged_claim
    )
    origin_pass = all(
        row.rejected_batches
        == sum(
            any(
                abs(float(step["logged_reward"]) - float(step["true_reward"]))
                > EDIT_TOLERANCE
                for step in grouped_batches(
                    selected_rows(steps, row.learner_seed, "fixed_target_tanh")
                )[batch]
            )
            for batch in range(BATCHES)
        )
        for row in integrity_rows
        if row.mode == "origin_bound_fail_closed"
    )
    repair_pass = all(
        row.repaired_records == row.nonzero_edits and row.accepted_batches == BATCHES
        for row in integrity_rows
        if row.mode == "trusted_reference_repair"
    )
    completeness_pass = all(row.detected for row in completeness_rows)
    detector_pass = all(row.exact_batch_decision_match for row in detector_rows)
    exact_replay_pass = bool(
        max(clean_errors) <= REPLAY_TOLERANCE
        and max(unsigned_errors) <= REPLAY_TOLERANCE
        and max(compromised_errors) <= REPLAY_TOLERANCE
    )
    gate_pass = bool(
        exact_replay_pass
        and reward_capability_pass
        and forbidden_pass
        and forged_pass
        and origin_pass
        and repair_pass
        and completeness_pass
        and detector_pass
    )
    decision = BoundaryDecision(
        learner_seeds=len(LEARNER_SEEDS),
        step_source_sha256=digest(STEP_SOURCE),
        training_source_sha256=digest(TRAINING_SOURCE),
        aggregate_source_sha256=digest(AGGREGATE_SOURCE),
        calibration_source_sha256=digest(CALIBRATION_SOURCE),
        protocol_sha256=digest(PROTOCOL),
        harness_sha256=digest(Path(__file__)),
        max_clean_replay_error=max(clean_errors),
        max_unsigned_poison_replay_error=max(unsigned_errors),
        max_compromised_producer_replay_error=max(compromised_errors),
        exact_replay_pass=exact_replay_pass,
        reward_capability_pass=reward_capability_pass,
        forbidden_path_denial_pass=forbidden_pass,
        forged_capability_denial_pass=forged_pass,
        origin_bound_rejection_pass=origin_pass,
        trusted_reference_repair_pass=repair_pass,
        sequence_completeness_pass=completeness_pass,
        detector_agreement_pass=detector_pass,
        linked_v4_poisoned_release_violations=int(
            aggregate["poisoned_release_violations"]
        ),
        linked_v4_resident_predictive_violations=int(
            aggregate["resident_predictive_violations"]
        ),
        no_new_seed_namespace_opened=True,
        locked_trace_gate_pass=gate_pass,
        next_authorized_stage=(
            "burned_2070_9070_end_to_end" if gate_pass else "stop_and_repair_harness"
        ),
    )

    write_rows(output_path("replay"), replay_rows)
    write_rows(output_path("capabilities"), capability_rows)
    write_rows(output_path("completeness"), completeness_rows)
    write_rows(output_path("integrity_modes"), integrity_rows)
    write_rows(output_path("detector_agreement"), detector_rows)
    write_rows(output_path("decision"), [decision])
    print(decision)


if __name__ == "__main__":
    main()
