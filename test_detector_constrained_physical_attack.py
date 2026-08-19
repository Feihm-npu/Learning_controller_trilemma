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


def test_detector_constrained_attack_integrity_passes_but_physical_gate_fails() -> None:
    decision = rows("cartpole_detector_constrained_physical_attack_decision.csv")
    assert len(decision) == 1
    row = decision[0]
    assert row["learner_seed"] == "2070"
    assert row["evaluation_seed"] == "9070"
    assert row["all_invariants_pass"] == "True"
    assert float(row["max_learner_reward_delta_error"]) == 0.0
    assert float(row["max_learner_raw_gradient_error"]) == 0.0
    assert float(row["max_learner_next_parameter_error"]) == 0.0
    assert int(row["adaptation_constraint_violations"]) == 0
    assert row["reward_budget_integrity"] == "True"
    assert int(row["nonzero_edit_batches"]) == 12
    assert int(row["poison_initially_accepted"]) == 24
    assert int(row["clean_release_violations"]) == 0
    assert int(row["poisoned_release_violations"]) == 0
    assert int(row["resident_predictive_violations"]) == 0
    assert int(row["poison_only_discordant"]) == 0
    assert row["detector_constrained_physical_smoke_pass"] == "False"
    assert row["new_seed_namespace_opened"] == "False"
    assert row["next_action"] == "close_r2_insufficient_physical_effect_no_new_seeds"
    assert row["protocol_sha256"] == digest(
        ROOT / "cartpole_detector_constrained_physical_attack_protocol.md"
    )
    assert row["harness_sha256"] == digest(
        ROOT / "safe_control_gym_cartpole_detector_constrained_physical_attack.py"
    )


def test_detector_constraints_hold_for_every_consumed_reward() -> None:
    batches = rows("cartpole_detector_constrained_physical_attack_batches.csv")
    steps = rows("cartpole_detector_constrained_physical_attack_steps.csv")
    assert len(batches) == 12
    assert len(steps) == 96
    assert all(row["all_invariants_pass"] == "True" for row in batches)
    assert all(int(row["positive_logged_rewards"]) == 0 for row in batches)
    assert all(float(row["scalar_lower_violation"]) <= 1e-10 for row in batches)
    assert all(float(row["scalar_upper_violation"]) <= 1e-10 for row in batches)
    assert all(float(row["batch_mean_lower_violation"]) <= 1e-10 for row in batches)
    assert all(float(row["batch_mean_upper_violation"]) <= 1e-10 for row in batches)
    assert all(float(row["reward_budget_violation"]) <= 1e-10 for row in batches)
    assert sum(int(row["candidate_reward_vectors"]) for row in batches) == 12324
    assert all(int(row["public_short_accepted"]) == 14 for row in batches)
    assert max(int(row["public_long_violations"]) for row in batches) == 2


def test_frozen_scalar_detectors_are_evaded_but_trusted_recomputation_is_not() -> None:
    detector_rows = {
        row["detector"]: row
        for row in rows("cartpole_detector_constrained_physical_attack_detectors.csv")
    }
    assert set(detector_rows) == {
        "trusted_recomputation",
        "known_sign",
        "scalar_envelope",
        "batch_mean_envelope",
    }
    assert float(detector_rows["known_sign"]["poisoned_true_positive_rate"]) == 0.0
    assert float(detector_rows["scalar_envelope"]["poisoned_true_positive_rate"]) == 0.0
    assert float(detector_rows["batch_mean_envelope"]["poisoned_true_positive_rate"]) == 0.0
    assert float(
        detector_rows["trusted_recomputation"]["poisoned_true_positive_rate"]
    ) == 1.0
    decision = rows("cartpole_detector_constrained_physical_attack_decision.csv")[0]
    assert decision["log_only_stealthy_under_frozen_scalar_checks"] == "True"
