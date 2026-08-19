#!/usr/bin/env python3
"""Audit the conic clipped-support extension on the locked V3 trajectories."""

from __future__ import annotations

import csv
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np

import reward_certificate_geometry as geometry
import safe_control_gym_reinforce_reward_poisoning as reinforce


ROOT = Path(__file__).resolve().parent
RESULTS = ROOT / "results"
STEPS_SOURCE = RESULTS / "cartpole_v3_trajectory_influence_steps.csv"
BATCH_SOURCE = RESULTS / "cartpole_v3_trajectory_influence_batches.csv"
TRAINING_SOURCE = RESULTS / "cartpole_v3_fixed_target_multiseed_training.csv"
OUTPUT_PREFIX = RESULTS / "cartpole_v3_clipped_influence"
LEARNER_SEEDS = (2070, 2071, 2072)
TARGET_EFFECTIVE = np.asarray([18.0, -5.0], dtype=float)
COORDINATE_MAP = np.diag([1.0 / reinforce.THETA_SCALE, 1.0])
REWARD_BUDGET = 2.0
GRADIENT_CAP = 1.0
ACTOR_LR = 1.0
SIGMA = 0.8
GAMMA = 0.97


@dataclass
class ClippedInfluenceRow:
    learner_seed: int
    batch: int
    current_gain: float
    current_bias: float
    normalization_singular_in_old_audit: bool
    old_global_gradient_clip_excluded: bool
    actual_gradient_clip_active: bool
    actual_parameter_clip_active: bool
    global_parameter_clip_excluded: bool
    exact_clipped_support_eligible: bool
    target_direction_gain: float
    target_direction_bias: float
    exact_target_support: float | None
    actual_target_value: float
    exact_support_gap: float | None
    actual_fraction_of_optimal_increment: float | None
    witness_support_error: float | None
    witness_max_reward_poison: float | None
    witness_centered_return_norm: float | None
    witness_raw_gradient_norm: float | None
    witness_gradient_clipped: bool | None
    solver_status: str


@dataclass
class ClippedInfluenceDecision:
    poisoned_batches: int
    old_exact_support_eligible_batches: int
    exact_clipped_support_eligible_batches: int
    newly_covered_normalization_singular_batches: int
    newly_covered_possible_gradient_clip_batches: int
    actual_parameter_clip_batches: int
    parameter_clip_excluded_batches: int
    maximum_witness_support_error: float
    all_witness_budgets_valid: bool
    all_actual_updates_bounded_by_support: bool
    final_parameter_reconstruction_error: float
    clipped_theory_audit_pass: bool


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as source:
        return list(csv.DictReader(source))


def write_csv(path: Path, rows: list[object]) -> None:
    dictionaries = [asdict(row) for row in rows]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=list(dictionaries[0]))
        writer.writeheader()
        writer.writerows(dictionaries)


def cap_and_clip(current: np.ndarray, raw_gradient: np.ndarray) -> np.ndarray:
    gradient = np.asarray(raw_gradient, dtype=float).copy()
    norm = float(np.linalg.norm(gradient))
    if norm > GRADIENT_CAP:
        gradient *= GRADIENT_CAP / norm
    return np.minimum(
        np.maximum(current + ACTOR_LR * gradient, reinforce.LEARNER_LOW),
        reinforce.LEARNER_HIGH,
    )


def locked_final(seed: int) -> np.ndarray:
    matching = [
        row
        for row in read_rows(TRAINING_SOURCE)
        if int(row["learner_seed"]) == seed
        and row["mechanism"] == "fixed_target_tanh"
    ]
    if len(matching) != 1:
        raise RuntimeError(f"missing locked poisoned final parameters for {seed}")
    return reinforce.to_learner_params(
        np.asarray(
            [float(matching[0]["final_gain"]), float(matching[0]["final_bias"])],
            dtype=float,
        )
    )


def main() -> None:
    step_rows = [
        row
        for row in read_rows(STEPS_SOURCE)
        if row["mechanism"] == "fixed_target_tanh"
    ]
    old_batches = {
        (int(row["learner_seed"]), int(row["batch"])): row
        for row in read_rows(BATCH_SOURCE)
        if row["mechanism"] == "fixed_target_tanh"
    }
    output: list[ClippedInfluenceRow] = []
    final_errors: list[float] = []

    for seed in LEARNER_SEEDS:
        current = np.zeros(2, dtype=float)
        for batch in range(12):
            batch_steps = sorted(
                (
                    row
                    for row in step_rows
                    if int(row["learner_seed"]) == seed
                    and int(row["batch"]) == batch
                ),
                key=lambda row: int(row["step"]),
            )
            if len(batch_steps) != 8:
                raise RuntimeError(f"expected eight steps for seed {seed} batch {batch}")
            features = np.asarray(
                [
                    [
                        float(row["feature_gain_coordinate"]),
                        float(row["feature_bias_coordinate"]),
                    ]
                    for row in batch_steps
                ],
                dtype=float,
            )
            noise = np.asarray(
                [float(row["exploration_noise"]) for row in batch_steps], dtype=float
            )
            true_rewards = np.asarray(
                [float(row["true_reward"]) for row in batch_steps], dtype=float
            )
            logged_rewards = np.asarray(
                [float(row["logged_reward"]) for row in batch_steps], dtype=float
            )
            dones = np.asarray([float(row["done"]) for row in batch_steps], dtype=float)
            scores = geometry.gaussian_score_matrix(features, noise, SIGMA)
            operator = geometry.centered_return_operator(dones, GAMMA)
            raw_gradient = geometry.normalized_reinforce_gradient(
                scores, logged_rewards, operator
            )
            candidate = cap_and_clip(current, raw_gradient)
            raw_norm = float(np.linalg.norm(raw_gradient))
            applied = raw_gradient.copy()
            if raw_norm > GRADIENT_CAP:
                applied *= GRADIENT_CAP / raw_norm
            unclipped_candidate = current + ACTOR_LR * applied
            actual_parameter_clip = not np.allclose(
                candidate, unclipped_candidate, atol=1e-12, rtol=0.0
            )

            # Cauchy--Schwarz bounds each normalized raw-gradient coordinate;
            # global norm clipping supplies the independent cap bound.
            coordinate_bounds = np.minimum(
                np.linalg.norm(scores, axis=0) / np.sqrt(len(batch_steps)),
                GRADIENT_CAP,
            )
            global_parameter_safe = bool(
                np.all(
                    current - ACTOR_LR * coordinate_bounds
                    >= reinforce.LEARNER_LOW - 1e-12
                )
                and np.all(
                    current + ACTOR_LR * coordinate_bounds
                    <= reinforce.LEARNER_HIGH + 1e-12
                )
            )

            current_effective = reinforce.to_effective_params(current)
            target_direction = TARGET_EFFECTIVE - current_effective
            target_direction /= np.linalg.norm(target_direction)
            actual_effective = reinforce.to_effective_params(candidate)
            actual_value = float(target_direction @ actual_effective)
            current_value = float(target_direction @ current_effective)
            old = old_batches[(seed, batch)]
            old_singular = old["normalization_nonsingular"] != "True"
            old_gradient_safe = old["global_gradient_clip_excluded"] == "True"

            exact_support: float | None = None
            exact_gap: float | None = None
            fraction: float | None = None
            witness_error: float | None = None
            witness_budget: float | None = None
            witness_norm: float | None = None
            witness_raw_norm: float | None = None
            witness_clipped: bool | None = None
            status = "parameter_clip_not_globally_excluded"
            support_eligible = False
            if global_parameter_safe:
                print(f"clipped support learner={seed} batch={batch}", flush=True)
                try:
                    support = geometry.worst_positive_halfspace_support_with_gradient_clipping(
                        current_params=current,
                        rewards=true_rewards,
                        centered_operator=operator,
                        score_matrix=scores,
                        reward_budget=REWARD_BUDGET,
                        actor_lr=ACTOR_LR,
                        coordinate_map=COORDINATE_MAP,
                        halfspace_row=target_direction,
                        gradient_cap=GRADIENT_CAP,
                        bisection_steps=35,
                    )
                except RuntimeError as error:
                    status = f"witness_recovery_failed:{error}"
                else:
                    support_eligible = True
                    exact_support = support.support
                    exact_gap = exact_support - actual_value
                    optimal_increment = exact_support - current_value
                    actual_increment = actual_value - current_value
                    if optimal_increment > 1e-10:
                        fraction = actual_increment / optimal_increment
                    witness_error = support.witness_support_error
                    witness_budget = float(np.max(np.abs(support.reward_delta)))
                    witness_norm = support.witness_centered_return_norm
                    witness_raw_norm = support.witness_raw_gradient_norm
                    witness_clipped = support.witness_gradient_clipped
                    status = support.solver_status

            output.append(
                ClippedInfluenceRow(
                    learner_seed=seed,
                    batch=batch,
                    current_gain=float(current_effective[0]),
                    current_bias=float(current_effective[1]),
                    normalization_singular_in_old_audit=old_singular,
                    old_global_gradient_clip_excluded=old_gradient_safe,
                    actual_gradient_clip_active=raw_norm > GRADIENT_CAP + 1e-12,
                    actual_parameter_clip_active=actual_parameter_clip,
                    global_parameter_clip_excluded=global_parameter_safe,
                    exact_clipped_support_eligible=support_eligible,
                    target_direction_gain=float(target_direction[0]),
                    target_direction_bias=float(target_direction[1]),
                    exact_target_support=exact_support,
                    actual_target_value=actual_value,
                    exact_support_gap=exact_gap,
                    actual_fraction_of_optimal_increment=fraction,
                    witness_support_error=witness_error,
                    witness_max_reward_poison=witness_budget,
                    witness_centered_return_norm=witness_norm,
                    witness_raw_gradient_norm=witness_raw_norm,
                    witness_gradient_clipped=witness_clipped,
                    solver_status=status,
                )
            )
            current = candidate
        final_errors.append(float(np.linalg.norm(current - locked_final(seed))))

    eligible = [row for row in output if row.exact_clipped_support_eligible]
    witness_errors = [
        float(row.witness_support_error)
        for row in eligible
        if row.witness_support_error is not None
    ]
    budgets_valid = all(
        row.witness_max_reward_poison is not None
        and row.witness_max_reward_poison <= REWARD_BUDGET + 1e-6
        for row in eligible
    )
    actual_bounded = all(
        row.exact_support_gap is not None and row.exact_support_gap >= -2e-5
        for row in eligible
    )
    maximum_error = max(witness_errors, default=float("inf"))
    final_error = max(final_errors)
    decision = ClippedInfluenceDecision(
        poisoned_batches=len(output),
        old_exact_support_eligible_batches=sum(
            old["exact_support_eligible"] == "True" for old in old_batches.values()
        ),
        exact_clipped_support_eligible_batches=len(eligible),
        newly_covered_normalization_singular_batches=sum(
            row.normalization_singular_in_old_audit for row in eligible
        ),
        newly_covered_possible_gradient_clip_batches=sum(
            not row.old_global_gradient_clip_excluded for row in eligible
        ),
        actual_parameter_clip_batches=sum(row.actual_parameter_clip_active for row in output),
        parameter_clip_excluded_batches=sum(
            row.global_parameter_clip_excluded for row in output
        ),
        maximum_witness_support_error=maximum_error,
        all_witness_budgets_valid=budgets_valid,
        all_actual_updates_bounded_by_support=actual_bounded,
        final_parameter_reconstruction_error=final_error,
        clipped_theory_audit_pass=bool(
            len(eligible) > 0
            and maximum_error <= 5e-5
            and budgets_valid
            and actual_bounded
            and final_error <= 1e-10
        ),
    )
    write_csv(Path(f"{OUTPUT_PREFIX}_batches.csv"), output)
    write_csv(Path(f"{OUTPUT_PREFIX}_decision.csv"), [decision])
    print(decision)


if __name__ == "__main__":
    main()
