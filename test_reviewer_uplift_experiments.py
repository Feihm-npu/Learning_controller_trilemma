from __future__ import annotations

import csv
import hashlib
import inspect
from pathlib import Path

import safe_control_gym_reinforce_reward_poisoning as reinforce


ROOT = Path(__file__).resolve().parent
RESULTS = ROOT / "results"


def rows(name: str) -> list[dict[str, str]]:
    with (RESULTS / name).open(newline="") as source:
        return list(csv.DictReader(source))


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_observer_is_optional_and_protocol_was_locked_before_v4() -> None:
    signature = inspect.signature(reinforce.train_reinforce)
    assert signature.parameters["batch_observer"].default is None
    protocol = (ROOT / "reviewer_uplift_experiment_protocol.md").read_text()
    assert "2100--2104" in protocol
    assert "at least 27 of 36 batches" in protocol
    assert "H in {1,3,5,10,20}" in protocol
    ledger = rows("cartpole_v4_untouched_confirmation_opened.csv")
    assert len(ledger) == 1
    assert ledger[0]["status"] == "completed"
    assert ledger[0]["protocol_sha256"] == digest(
        ROOT / "reviewer_uplift_experiment_protocol.md"
    )


def test_horizon_sweep_preserves_states_and_passes_three_horizons() -> None:
    decision = rows("cartpole_horizon_contract_sweep_decision.csv")
    assert decision == [
        {
            "locked_horizons": "5",
            "qualifying_horizons": "3",
            "qualifying_horizon_values": "3;5;10",
            "horizon_robust": "True",
            "only_h5_separates": "False",
            "locked_snapshot_match": "True",
            "locked_state_match": "True",
        }
    ]
    pooled = {
        int(row["monitor_horizon"]): row
        for row in rows("cartpole_horizon_contract_sweep_summary.csv")
        if row["scope"] == "pooled"
    }
    assert set(pooled) == {1, 3, 5, 10, 20}
    assert int(pooled[1]["resident_violations"]) == 12
    assert int(pooled[20]["poisoned_release_violations"]) == 0
    assert all(int(pooled[horizon]["resident_violations"]) == 0 for horizon in (3, 5, 10))


def test_trajectory_replay_is_exact_and_preserves_negative_bridge_result() -> None:
    decision = rows("cartpole_v3_trajectory_influence_decision.csv")
    assert len(decision) == 1
    row = decision[0]
    assert row["replay_integrity_pass"] == "True"
    assert float(row["max_gradient_reconstruction_error"]) <= 1e-10
    assert float(row["max_final_parameter_error"]) <= 1e-10
    assert int(row["poison_batches_with_progress_advantage"]) == 22
    assert int(row["required_progress_advantage_batches"]) == 27
    assert row["final_release_pattern_match"] == "True"
    assert row["successful_trajectory_bridge_pass"] == "False"


def test_v4_untouched_confirmation_is_complete_and_strong() -> None:
    assert len(rows("cartpole_v4_untouched_confirmation_batches.csv")) == 120
    assert len(rows("cartpole_v4_untouched_confirmation_training.csv")) == 10
    assert len(rows("cartpole_v4_untouched_confirmation_rollouts.csv")) == 360
    assert len(rows("cartpole_v4_untouched_confirmation_steps.csv")) == 960
    seed_rows = rows("cartpole_v4_untouched_confirmation_decision.csv")
    assert {int(row["learner_seed"]) for row in seed_rows} == set(range(2100, 2105))
    assert all(int(row["poisoned_release_violations"]) > 0 for row in seed_rows)
    aggregate = rows("cartpole_v4_untouched_confirmation_aggregate.csv")[0]
    assert aggregate["five_seed_extension_pass"] == "True"
    assert aggregate["five_seed_strong_pass"] == "True"
    assert int(aggregate["poison_only_discordant"]) == 25
    assert int(aggregate["clean_only_discordant"]) == 0
    assert float(aggregate["paired_exact_pvalue"]) < 0.05
    assert int(aggregate["resident_predictive_violations"]) == 0


def test_detector_remained_frozen_and_records_negative_realism_boundary() -> None:
    freeze = rows("cartpole_reward_detectability_freeze.csv")[0]
    assert digest(ROOT / "safe_control_gym_reward_log_detectability.py") == freeze[
        "detector_sha256"
    ]
    assert digest(RESULTS / "cartpole_reward_detectability_calibration.csv") == freeze[
        "calibration_sha256"
    ]
    decision = rows("cartpole_reward_detectability_final_decision.csv")[0]
    assert decision["calibration_seed_excluded"] == "True"
    assert decision["log_only_stealthy"] == "False"
    assert decision["negative_realism_boundary"] == "True"
    assert float(decision["known_sign_batch_tpr"]) >= 0.8
    assert float(decision["known_sign_batch_fpr"]) <= 0.05
    assert float(decision["trusted_recomputation_batch_tpr"]) == 1.0
