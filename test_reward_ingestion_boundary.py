from __future__ import annotations

import csv
import hashlib
from pathlib import Path


ROOT = Path(__file__).resolve().parent
RESULTS = ROOT / "results"


def rows(name: str) -> list[dict[str, str]]:
    with (RESULTS / name).open(newline="") as source:
        return list(csv.DictReader(source))


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_reward_ingestion_locked_trace_gate_passes_exactly() -> None:
    decision = rows("cartpole_reward_ingestion_boundary_decision.csv")
    assert len(decision) == 1
    row = decision[0]
    assert row["locked_trace_gate_pass"] == "True"
    assert row["no_new_seed_namespace_opened"] == "True"
    assert row["next_authorized_stage"] == "burned_2070_9070_end_to_end"
    assert float(row["max_clean_replay_error"]) <= 1e-10
    assert float(row["max_unsigned_poison_replay_error"]) <= 1e-10
    assert float(row["max_compromised_producer_replay_error"]) <= 1e-10
    assert row["protocol_sha256"] == digest(
        ROOT / "cartpole_reward_ingestion_boundary_protocol.md"
    )
    assert row["harness_sha256"] == digest(
        ROOT / "safe_control_gym_cartpole_reward_ingestion_boundary.py"
    )


def test_reward_writer_capability_is_reward_only() -> None:
    capability = rows("cartpole_reward_ingestion_boundary_capabilities.csv")
    assert len(capability) == 65
    reward_rows = [
        row
        for row in capability
        if row["requested_path"] == "reward" and row["forged_claim"] == "False"
    ]
    assert len(reward_rows) == 5
    assert all(int(row["attempts"]) == 96 for row in reward_rows)
    assert all(int(row["authorized"]) == 96 for row in reward_rows)
    assert all(row["expectation_met"] == "True" for row in capability)
    forged = [row for row in capability if row["forged_claim"] == "True"]
    assert len(forged) == 5
    assert all(int(row["denied"]) == 1 for row in forged)


def test_origin_binding_and_sequence_completeness_have_distinct_controls() -> None:
    modes = rows("cartpole_reward_ingestion_boundary_integrity_modes.csv")
    assert len(modes) == 30
    origin = [row for row in modes if row["mode"] == "origin_bound_fail_closed"]
    compromised = [
        row for row in modes if row["mode"] == "compromised_producer_valid"
    ]
    repaired = [row for row in modes if row["mode"] == "trusted_reference_repair"]
    assert all(int(row["rejected_batches"]) == 12 for row in origin)
    assert all(int(row["integrity_flagged_records"]) == 96 for row in origin)
    assert all(row["exact_poisoned_snapshot_match"] == "True" for row in compromised)
    assert all(int(row["repaired_records"]) == 96 for row in repaired)

    completeness = rows("cartpole_reward_ingestion_boundary_completeness.csv")
    assert len(completeness) == 30
    assert {row["probe"] for row in completeness} == {
        "untouched",
        "reward_mutation",
        "interior_omission",
        "adjacent_reorder",
        "record_replay",
        "tail_truncation",
    }
    assert all(row["detected"] == "True" for row in completeness)
    assert all(
        row["observed_valid"] == ("True" if row["probe"] == "untouched" else "False")
        for row in completeness
    )


def test_semantic_controls_match_the_frozen_detector_without_tuning() -> None:
    agreement = rows("cartpole_reward_ingestion_boundary_detector_agreement.csv")
    assert len(agreement) == 10
    assert {row["detector"] for row in agreement} == {
        "known_sign",
        "scalar_envelope",
    }
    assert all(row["exact_batch_decision_match"] == "True" for row in agreement)
    decision = rows("cartpole_reward_ingestion_boundary_decision.csv")[0]
    assert decision["detector_agreement_pass"] == "True"
    assert int(decision["linked_v4_poisoned_release_violations"]) == 27
    assert int(decision["linked_v4_resident_predictive_violations"]) == 0


def test_burned_seed_end_to_end_bridge_preserves_the_claim_boundary() -> None:
    decision = rows("cartpole_reward_ingestion_end_to_end_decision.csv")
    assert len(decision) == 1
    row = decision[0]
    assert row["systems_bridge_pass"] == "True"
    assert row["no_new_seed_namespace_opened"] == "True"
    assert row["learner_seed"] == "2070"
    assert row["evaluation_seed"] == "9070"
    assert float(row["clean_locked_parameter_error"]) <= 1e-10
    assert float(row["poisoned_locked_parameter_error"]) <= 1e-10
    assert row["locked_rollout_reproduction_pass"] == "True"
    assert int(row["nonzero_poison_batches"]) == 12
    assert row["all_poison_batches_rejected_by_origin_binding"] == "True"
    assert int(row["common_vulnerable_states"]) == 24
    assert int(row["clean_reference_violations"]) == 0
    assert int(row["unsigned_raw_release_violations"]) == 11
    assert int(row["unsigned_resident_violations"]) == 0
    assert int(row["compromised_producer_violations"]) == 11
    assert int(row["origin_bound_fail_closed_violations"]) == 0
    assert int(row["trusted_reference_repair_violations"]) == 0
    assert float(row["origin_bound_update_availability"]) == 0.0
    assert float(row["trusted_reference_update_availability"]) == 1.0
    assert row["benign_adaptation_utility_vs_freeze_resolved"] == "False"
    assert row["protocol_sha256"] == digest(
        ROOT / "cartpole_reward_ingestion_end_to_end_protocol.md"
    )
    assert row["harness_sha256"] == digest(
        ROOT / "safe_control_gym_cartpole_reward_ingestion_end_to_end.py"
    )


def test_end_to_end_modes_use_the_same_common_state_cohort() -> None:
    training = rows("cartpole_reward_ingestion_end_to_end_training_modes.csv")
    assert len(training) == 5
    by_mode = {row["mode"]: row for row in training}
    assert set(by_mode) == {
        "clean_reference",
        "unsigned_postproducer_mutation",
        "origin_bound_fail_closed",
        "compromised_producer_valid",
        "trusted_reference_repair",
    }
    assert int(by_mode["origin_bound_fail_closed"]["rejected_batches"]) == 12
    assert int(by_mode["trusted_reference_repair"]["repaired_records"]) == 96

    physical = rows("cartpole_reward_ingestion_end_to_end_physical.csv")
    summary = rows("cartpole_reward_ingestion_end_to_end_summary.csv")
    assert len(physical) == 7 * 24
    assert len(summary) == 7
    assert all(int(row["common_states"]) == 24 for row in summary)
