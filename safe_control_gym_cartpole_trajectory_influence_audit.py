#!/usr/bin/env python3
"""Replay V3 and connect its successful trajectory to reward influence geometry."""

from __future__ import annotations

import csv
from dataclasses import asdict, dataclass
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import numpy as np

import reward_certificate_geometry as geometry
import safe_control_gym_cartpole_multiseed_release_contract as contract
import safe_control_gym_cartpole_v3_fixed_target_tanh as v3
import safe_control_gym_reinforce_reward_poisoning as reinforce


ROOT = Path(__file__).resolve().parent
RESULTS = ROOT / "results"
TRAINING_SOURCE = RESULTS / "cartpole_v3_fixed_target_multiseed_training.csv"
ROLLOUT_SOURCE = RESULTS / "cartpole_v3_fixed_target_multiseed_rollouts.csv"
OUTPUT_PREFIX = RESULTS / "cartpole_v3_trajectory_influence"
LEARNER_SEEDS = (2070, 2071, 2072)
EVALUATION_SEEDS = (9070, 9071, 9072)
COORDINATE_MAP = np.diag([1.0 / reinforce.THETA_SCALE, 1.0])
REWARD_BUDGET = 2.0
GRADIENT_CAP = 1.0
ACTOR_LR = 1.0
SIGMA = 0.8
GAMMA = 0.97


@dataclass
class StepRow:
    learner_seed: int
    mechanism: str
    batch: int
    step: int
    feature_gain_coordinate: float
    feature_bias_coordinate: float
    exploration_noise: float
    true_reward: float
    logged_reward: float
    reward_delta: float
    done: float


@dataclass
class BatchAuditRow:
    learner_seed: int
    mechanism: str
    batch: int
    raw_gradient_w0: float
    raw_gradient_w1: float
    reconstructed_gradient_w0: float
    reconstructed_gradient_w1: float
    reconstruction_error: float
    raw_gradient_norm: float
    applied_gradient_norm: float
    global_gradient_norm_upper_bound: float
    gradient_clip_active: bool
    global_gradient_clip_excluded: bool
    parameter_clip_active: bool
    global_parameter_clip_excluded: bool
    minimum_centered_return_norm: float
    normalization_nonsingular: bool
    target_direction_gain: float
    target_direction_bias: float
    actual_target_progress: float
    true_reward_counterfactual_progress: float
    poison_progress_advantage: float
    exact_support_eligible: bool
    exact_target_support: float | None
    actual_target_value: float
    exact_support_gap: float | None
    exact_support_solver_status: str


@dataclass
class ReleasePathRow:
    learner_seed: int
    evaluation_seed: int
    batch: int
    selected_states: int
    poison_initially_accepted: int
    accepted_full_casadi_violations: int
    max_reverse_margin: float
    final_batch_locked_acceptance_match: bool
    final_batch_locked_full_outcome_match: bool


@dataclass
class InfluenceDecision:
    replayed_learner_seeds: int
    audited_batches: int
    poisoned_batches: int
    max_gradient_reconstruction_error: float
    max_final_parameter_error: float
    replay_integrity_pass: bool
    poison_batches_with_progress_advantage: int
    required_progress_advantage_batches: int
    exact_support_eligible_batches: int
    final_release_pattern_match: bool
    final_locked_physical_harm_seeds: int
    successful_trajectory_bridge_pass: bool


def args() -> SimpleNamespace:
    return SimpleNamespace(
        batches=12,
        batch_steps=8,
        rho=0.005,
        sigma=SIGMA,
        actor_lr=ACTOR_LR,
        gamma=GAMMA,
        max_gradient_norm=GRADIENT_CAP,
        reward_poison_budget=REWARD_BUDGET,
        poison_temperature=1.0,
        candidate_states=32,
        selected_states=24,
        monitor_horizon=5,
        deployment_steps=120,
        baseline_guard_margin=0.0075,
        action_grid_size=41,
    )


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as source:
        return list(csv.DictReader(source))


def write_csv(path: Path, rows: list[object]) -> None:
    dictionaries = [asdict(row) for row in rows]
    if not dictionaries:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=list(dictionaries[0]))
        writer.writeheader()
        writer.writerows(dictionaries)


def observer(store: list[dict[str, Any]]):
    def capture(**kwargs: Any) -> None:
        store.append(kwargs)

    return capture


def cap_and_clip_update(current: np.ndarray, raw_gradient: np.ndarray) -> np.ndarray:
    gradient = np.asarray(raw_gradient, dtype=float).copy()
    norm = float(np.linalg.norm(gradient))
    if norm > GRADIENT_CAP:
        gradient *= GRADIENT_CAP / norm
    return np.minimum(
        np.maximum(current + ACTOR_LR * gradient, reinforce.LEARNER_LOW),
        reinforce.LEARNER_HIGH,
    )


def locked_params(seed: int, mechanism: str) -> np.ndarray:
    matching = [
        row
        for row in read_rows(TRAINING_SOURCE)
        if int(row["learner_seed"]) == seed and row["mechanism"] == mechanism
    ]
    if len(matching) != 1:
        raise RuntimeError(f"missing locked {mechanism} params for {seed}")
    return np.asarray(
        [float(matching[0]["final_gain"]), float(matching[0]["final_bias"])],
        dtype=float,
    )


def step_rows(seed: int, mechanism: str, batches: list[dict[str, Any]]) -> list[StepRow]:
    output: list[StepRow] = []
    for record in batches:
        for step in range(len(record["true_rewards"])):
            output.append(
                StepRow(
                    learner_seed=seed,
                    mechanism=mechanism,
                    batch=int(record["batch"]),
                    step=step,
                    feature_gain_coordinate=float(record["features"][step, 0]),
                    feature_bias_coordinate=float(record["features"][step, 1]),
                    exploration_noise=float(record["exploration_noise"][step]),
                    true_reward=float(record["true_rewards"][step]),
                    logged_reward=float(record["logged_rewards"][step]),
                    reward_delta=float(record["reward_delta"][step]),
                    done=float(record["dones"][step]),
                )
            )
    return output


def audit_batch(seed: int, mechanism: str, record: dict[str, Any]) -> BatchAuditRow:
    scores = geometry.gaussian_score_matrix(
        record["features"], record["exploration_noise"], SIGMA
    )
    centered = geometry.centered_return_operator(record["dones"], GAMMA)
    reconstructed = geometry.normalized_reinforce_gradient(
        scores, record["logged_rewards"], centered
    )
    raw = np.asarray(record["raw_gradient"], dtype=float)
    applied = np.asarray(record["applied_gradient"], dtype=float)
    current = np.asarray(record["learner_params_before"], dtype=float)
    actual_after = np.asarray(record["learner_params_after"], dtype=float)
    unclipped_candidate = current + ACTOR_LR * applied
    parameter_clip = not np.allclose(
        unclipped_candidate, record["candidate_params"], atol=1e-12, rtol=0.0
    )

    horizon = len(record["true_rewards"])
    spectral_bound = float(np.linalg.norm(scores, ord=2) / np.sqrt(horizon))
    coordinate_bounds = np.linalg.norm(scores, axis=0) / np.sqrt(horizon)
    global_param_safe = bool(
        np.all(current - ACTOR_LR * coordinate_bounds >= reinforce.LEARNER_LOW)
        and np.all(current + ACTOR_LR * coordinate_bounds <= reinforce.LEARNER_HIGH)
    )
    try:
        minimum_norm = geometry.minimum_centered_return_norm(
            record["true_rewards"], centered, REWARD_BUDGET
        )
    except RuntimeError:
        minimum_norm = float("nan")
    nonsingular = bool(np.isfinite(minimum_norm) and minimum_norm > 1e-7)

    current_effective = reinforce.to_effective_params(current)
    target_effective = reinforce.to_effective_params(record["target_params"])
    direction = target_effective - current_effective
    direction_norm = float(np.linalg.norm(direction))
    if direction_norm > 0.0:
        direction /= direction_norm
    actual_effective = reinforce.to_effective_params(actual_after)
    counter_gradient = reinforce.reinforce_gradient(
        record["features"],
        record["exploration_noise"],
        record["true_rewards"],
        record["dones"],
        sigma=SIGMA,
        gamma=GAMMA,
    )
    counter_after = cap_and_clip_update(current, counter_gradient)
    counter_effective = reinforce.to_effective_params(counter_after)
    actual_progress = float(direction @ (actual_effective - current_effective))
    counter_progress = float(direction @ (counter_effective - current_effective))

    eligible = bool(
        mechanism == "fixed_target_tanh"
        and nonsingular
        and spectral_bound <= GRADIENT_CAP + 1e-12
        and global_param_safe
    )
    exact_support: float | None = None
    support_gap: float | None = None
    solver_status = "ineligible"
    actual_value = float(direction @ actual_effective)
    if eligible:
        support = geometry.worst_positive_halfspace_support(
            current_params=current,
            rewards=record["true_rewards"],
            centered_operator=centered,
            score_matrix=scores,
            reward_budget=REWARD_BUDGET,
            actor_lr=ACTOR_LR,
            coordinate_map=COORDINATE_MAP,
            halfspace_row=direction,
        )
        exact_support = support.support
        support_gap = exact_support - actual_value
        solver_status = support.solver_status

    return BatchAuditRow(
        learner_seed=seed,
        mechanism=mechanism,
        batch=int(record["batch"]),
        raw_gradient_w0=float(raw[0]),
        raw_gradient_w1=float(raw[1]),
        reconstructed_gradient_w0=float(reconstructed[0]),
        reconstructed_gradient_w1=float(reconstructed[1]),
        reconstruction_error=float(np.linalg.norm(reconstructed - raw)),
        raw_gradient_norm=float(np.linalg.norm(raw)),
        applied_gradient_norm=float(np.linalg.norm(applied)),
        global_gradient_norm_upper_bound=spectral_bound,
        gradient_clip_active=float(np.linalg.norm(raw)) > GRADIENT_CAP + 1e-12,
        global_gradient_clip_excluded=spectral_bound <= GRADIENT_CAP + 1e-12,
        parameter_clip_active=parameter_clip,
        global_parameter_clip_excluded=global_param_safe,
        minimum_centered_return_norm=minimum_norm,
        normalization_nonsingular=nonsingular,
        target_direction_gain=float(direction[0]),
        target_direction_bias=float(direction[1]),
        actual_target_progress=actual_progress,
        true_reward_counterfactual_progress=counter_progress,
        poison_progress_advantage=actual_progress - counter_progress,
        exact_support_eligible=eligible,
        exact_target_support=exact_support,
        actual_target_value=actual_value,
        exact_support_gap=support_gap,
        exact_support_solver_status=solver_status,
    )


def locked_rollouts(seed: int) -> dict[tuple[int, str], dict[str, str]]:
    rows = [row for row in read_rows(ROLLOUT_SOURCE) if int(row["learner_seed"]) == seed]
    lookup = {(int(row["selected_index"]), row["mechanism"]): row for row in rows}
    if len(lookup) != 72:
        raise RuntimeError(f"expected 72 locked rollout rows for {seed}, got {len(lookup)}")
    return lookup


def trace_release_path(
    learner_seed: int,
    evaluation_seed: int,
    poison_records: list[dict[str, Any]],
) -> tuple[list[ReleasePathRow], bool, bool]:
    protocol = args()
    _candidates, admitted = contract.baseline_admitted_states(
        seed=evaluation_seed,
        candidate_count=protocol.candidate_states,
        horizon=protocol.deployment_steps,
        guard_margin=protocol.baseline_guard_margin,
    )
    selected_indices = contract.order_spanning_indices(
        len(admitted), protocol.selected_states
    )
    states = [admitted[index] for index in selected_indices]
    locked = locked_rollouts(learner_seed)
    path: list[ReleasePathRow] = []
    final_acceptance_match = False
    final_full_match = False
    for record in poison_records:
        effective = np.asarray(record["effective_params_after"], dtype=float)
        short, margins, full = contract.casadi_admission(
            effective,
            states,
            seed=evaluation_seed,
            short_horizon=protocol.monitor_horizon,
            full_horizon=protocol.deployment_steps,
        )
        accepted = np.logical_and(short < 0, margins <= 0.0)
        full_failures = np.logical_and(accepted, full >= 0)
        acceptance_match = False
        full_match = False
        if int(record["batch"]) == protocol.batches - 1:
            expected_accepted = np.asarray(
                [
                    locked[(index, "poisoned_release")]["poison_initially_accepted"]
                    == "True"
                    for index in range(protocol.selected_states)
                ]
            )
            expected_full = np.asarray(
                [
                    -1
                    if locked[(index, "poisoned_release")][
                        "casadi_full_first_violation_step"
                    ]
                    == ""
                    else int(
                        locked[(index, "poisoned_release")][
                            "casadi_full_first_violation_step"
                        ]
                    )
                    for index in range(protocol.selected_states)
                ]
            )
            acceptance_match = bool(np.array_equal(accepted, expected_accepted))
            full_match = bool(np.array_equal(full, expected_full))
            final_acceptance_match = acceptance_match
            final_full_match = full_match
        path.append(
            ReleasePathRow(
                learner_seed=learner_seed,
                evaluation_seed=evaluation_seed,
                batch=int(record["batch"]),
                selected_states=len(states),
                poison_initially_accepted=int(np.sum(accepted)),
                accepted_full_casadi_violations=int(np.sum(full_failures)),
                max_reverse_margin=float(np.max(margins)),
                final_batch_locked_acceptance_match=acceptance_match,
                final_batch_locked_full_outcome_match=full_match,
            )
        )
    return path, final_acceptance_match, final_full_match


def main() -> None:
    protocol = args()
    all_steps: list[StepRow] = []
    all_batches: list[BatchAuditRow] = []
    all_path: list[ReleasePathRow] = []
    final_errors: list[float] = []
    release_matches: list[bool] = []
    physical_harm_seeds = 0

    for learner_seed, evaluation_seed in zip(LEARNER_SEEDS, EVALUATION_SEEDS):
        print(f"trajectory replay learner={learner_seed}", flush=True)
        clean_records: list[dict[str, Any]] = []
        poison_records: list[dict[str, Any]] = []
        clean, poison, _poison_result, _batch_rows, _training = v3.train_seed(
            learner_seed,
            evaluation_seed,
            protocol,
            clean_batch_observer=observer(clean_records),
            poison_batch_observer=observer(poison_records),
        )
        clean_error = float(np.linalg.norm(clean - locked_params(learner_seed, "clean")))
        poison_error = float(
            np.linalg.norm(poison - locked_params(learner_seed, "fixed_target_tanh"))
        )
        final_errors.extend([clean_error, poison_error])
        for mechanism, records in (
            ("clean", clean_records),
            ("fixed_target_tanh", poison_records),
        ):
            all_steps.extend(step_rows(learner_seed, mechanism, records))
            for record in records:
                all_batches.append(audit_batch(learner_seed, mechanism, record))
        path, acceptance_match, full_match = trace_release_path(
            learner_seed, evaluation_seed, poison_records
        )
        all_path.extend(path)
        release_matches.append(acceptance_match and full_match)
        locked = locked_rollouts(learner_seed)
        physical_harm_seeds += int(
            any(
                row["poison_initially_accepted"] == "True"
                and row["physical_first_violation_step"] != ""
                for (index, mechanism), row in locked.items()
                if mechanism == "poisoned_release"
            )
        )

    poison_audits = [row for row in all_batches if row.mechanism == "fixed_target_tanh"]
    max_reconstruction = max(row.reconstruction_error for row in all_batches)
    max_final = max(final_errors)
    positive_advantage = sum(row.poison_progress_advantage > 0.0 for row in poison_audits)
    replay_pass = bool(max_reconstruction <= 1e-10 and max_final <= 1e-10)
    final_pattern = bool(all(release_matches) and physical_harm_seeds == len(LEARNER_SEEDS))
    decision = InfluenceDecision(
        replayed_learner_seeds=len(LEARNER_SEEDS),
        audited_batches=len(all_batches),
        poisoned_batches=len(poison_audits),
        max_gradient_reconstruction_error=max_reconstruction,
        max_final_parameter_error=max_final,
        replay_integrity_pass=replay_pass,
        poison_batches_with_progress_advantage=positive_advantage,
        required_progress_advantage_batches=27,
        exact_support_eligible_batches=sum(row.exact_support_eligible for row in poison_audits),
        final_release_pattern_match=final_pattern,
        final_locked_physical_harm_seeds=physical_harm_seeds,
        successful_trajectory_bridge_pass=bool(
            replay_pass and positive_advantage >= 27 and final_pattern
        ),
    )
    write_csv(Path(f"{OUTPUT_PREFIX}_steps.csv"), all_steps)
    write_csv(Path(f"{OUTPUT_PREFIX}_batches.csv"), all_batches)
    write_csv(Path(f"{OUTPUT_PREFIX}_release_path.csv"), all_path)
    write_csv(Path(f"{OUTPUT_PREFIX}_decision.csv"), [decision])
    print(decision)


if __name__ == "__main__":
    main()
