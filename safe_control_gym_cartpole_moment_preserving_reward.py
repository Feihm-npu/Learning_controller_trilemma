#!/usr/bin/env python3
"""Moment-preserving sign/range-constrained S2 reward-poisoning fallback."""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import numpy as np

import safe_control_gym_cartpole_sparse_reward_permutation as s1
import safe_control_gym_cartpole_v3_fixed_target_tanh as v3
import safe_control_gym_reinforce_reward_poisoning as reinforce


ROOT = Path(__file__).resolve().parent
RESULTS = ROOT / "results"
OUTPUT_PREFIX = RESULTS / "cartpole_stealth_s2_2070"
S1_DECISION = RESULTS / "cartpole_stealth_s1_2070_decision.csv"
TARGET_EFFECTIVE = s1.TARGET_EFFECTIVE.copy()
REWARD_BUDGET = 2.0
SCALAR_LOWER = -5.888655463318784
SCALAR_UPPER = -0.01603442038059298
BISECTION_STEPS = 100


@dataclass
class ProjectionAudit:
    learner_seed: int
    batch: int
    feasible: bool
    projection_lambda: float
    desired_max_absolute_edit: float
    projected_max_absolute_edit: float
    changed_reward_steps: int
    reward_sum_error: float
    reward_mean_error: float
    scalar_lower_violation: float
    scalar_upper_violation: float
    positive_logged_rewards: int
    projection_kkt_residual: float
    current_target_distance: float
    projected_next_target_distance: float


@dataclass
class VerifiedProjectionBatch:
    learner_seed: int
    batch: int
    feasible: bool
    projection_lambda: float
    desired_max_absolute_edit: float
    projected_max_absolute_edit: float
    changed_reward_steps: int
    reward_sum_error: float
    reward_mean_error: float
    scalar_lower_violation: float
    scalar_upper_violation: float
    positive_logged_rewards: int
    projection_kkt_residual: float
    current_target_distance: float
    projected_next_target_distance: float
    learner_reward_delta_error: float
    learner_raw_gradient_error: float
    learner_next_parameter_error: float
    all_invariants_pass: bool


@dataclass
class S2StepRow:
    learner_seed: int
    batch: int
    step: int
    true_reward: float
    logged_reward: float
    reward_delta: float
    feature_gain_coordinate: float
    feature_bias_coordinate: float
    exploration_noise: float
    done: float


@dataclass
class S2SmokeDecision:
    learner_seed: int
    evaluation_seed: int
    audited_batches: int
    all_projection_invariants_pass: bool
    max_learner_reward_delta_error: float
    max_learner_raw_gradient_error: float
    max_learner_next_parameter_error: float
    adaptation_constraint_violations: int
    reward_budget_integrity: bool
    pair_keys_valid: bool
    poison_initially_accepted: int
    clean_release_violations: int
    poisoned_release_violations: int
    resident_predictive_violations: int
    poison_only_discordant: int
    clean_only_discordant: int
    paired_release_failures_with_timely_switch: int
    paired_release_failures: int
    initial_target_distance: float
    final_target_distance: float
    target_progress: float
    target_progress_pass: bool
    raw_release_effect_pass: bool
    s2_2070_smoke_pass: bool
    next_action: str


@dataclass
class StealthWPDecision:
    s1_offline_gate_pass: bool
    s1_integrity_and_target_progress_pass: bool
    s1_raw_release_effect_pass: bool
    s1_2070_smoke_pass: bool
    s2_integrity_and_target_progress_pass: bool
    s2_raw_release_effect_pass: bool
    s2_2070_smoke_pass: bool
    burned_extension_run: bool
    new_confirmation_namespace_opened: bool
    work_package_status: str


def project_box_zero_sum(
    desired: np.ndarray,
    lower: np.ndarray,
    upper: np.ndarray,
    *,
    iterations: int = BISECTION_STEPS,
) -> tuple[np.ndarray, float]:
    desired = np.asarray(desired, dtype=float)
    lower = np.asarray(lower, dtype=float)
    upper = np.asarray(upper, dtype=float)
    if desired.shape != lower.shape or desired.shape != upper.shape:
        raise ValueError("desired and projection bounds must have equal shape")
    if np.any(lower > upper + 1e-12):
        raise ValueError("projection box is empty")
    if float(np.sum(lower)) > 1e-12 or float(np.sum(upper)) < -1e-12:
        raise ValueError("zero-sum hyperplane does not intersect projection box")
    left = float(np.min(desired - upper) - 1.0)
    right = float(np.max(desired - lower) + 1.0)
    for _ in range(iterations):
        middle = 0.5 * (left + right)
        projected = np.clip(desired - middle, lower, upper)
        if float(np.sum(projected)) > 0.0:
            left = middle
        else:
            right = middle
    multiplier = 0.5 * (left + right)
    projected = np.clip(desired - multiplier, lower, upper)
    # Remove the final floating residual without changing feasibility.  A free
    # coordinate exists whenever the bisection residual is nonzero in this
    # locked problem.
    residual = float(np.sum(projected))
    if abs(residual) > 1e-14:
        free = np.flatnonzero(
            np.logical_and(projected > lower + 1e-12, projected < upper - 1e-12)
        )
        if len(free) == 0:
            raise RuntimeError("projection has no free coordinate for residual repair")
        projected[free[0]] -= residual
    return projected, multiplier


class MomentPreservingRewardAttack:
    def __init__(self, learner_seed: int) -> None:
        self.learner_seed = learner_seed
        self.audits: list[ProjectionAudit] = []
        self.deltas: list[np.ndarray] = []

    def select(self, **kwargs: Any) -> tuple[np.ndarray, ProjectionAudit]:
        rewards = np.asarray(kwargs["true_rewards"], dtype=float)
        features = np.asarray(kwargs["features"], dtype=float)
        noise = np.asarray(kwargs["exploration_noise"], dtype=float)
        current = np.asarray(kwargs["learner_params"], dtype=float)
        target = np.asarray(kwargs["target_params"], dtype=float)
        budget = float(kwargs["budget"])
        if not np.allclose(
            reinforce.to_effective_params(target),
            TARGET_EFFECTIVE,
            atol=1e-12,
            rtol=0.0,
        ):
            raise ValueError("S2 received the wrong fixed target")
        if not np.isclose(budget, REWARD_BUDGET):
            raise ValueError("S2 received the wrong reward budget")
        desired = reinforce.reward_poison(
            noise,
            features,
            current,
            target,
            budget=budget,
            temperature=1.0,
        )
        lower = np.maximum(-budget, SCALAR_LOWER - rewards)
        upper = np.minimum(budget, SCALAR_UPPER - rewards)
        delta, multiplier = project_box_zero_sum(desired, lower, upper)
        logged = rewards + delta
        raw_gradient = reinforce.reinforce_gradient(
            features,
            noise,
            logged,
            np.asarray(kwargs["dones"], dtype=float),
            sigma=float(kwargs["sigma"]),
            gamma=float(kwargs["gamma"]),
        )
        _applied, next_params = s1.apply_update(
            current,
            raw_gradient,
            actor_lr=float(kwargs["actor_lr"]),
            max_gradient_norm=float(kwargs["max_gradient_norm"]),
        )
        expected_projection = np.clip(desired - multiplier, lower, upper)
        audit = ProjectionAudit(
            learner_seed=self.learner_seed,
            batch=int(kwargs["batch"]),
            feasible=True,
            projection_lambda=multiplier,
            desired_max_absolute_edit=float(np.max(np.abs(desired))),
            projected_max_absolute_edit=float(np.max(np.abs(delta))),
            changed_reward_steps=int(np.sum(np.abs(delta) > 1e-12)),
            reward_sum_error=float(abs(np.sum(delta))),
            reward_mean_error=float(abs(np.mean(logged) - np.mean(rewards))),
            scalar_lower_violation=float(max(0.0, SCALAR_LOWER - np.min(logged))),
            scalar_upper_violation=float(max(0.0, np.max(logged) - SCALAR_UPPER)),
            positive_logged_rewards=int(np.sum(logged > 0.0)),
            projection_kkt_residual=float(
                np.max(np.abs(delta - expected_projection))
            ),
            current_target_distance=float(
                np.linalg.norm(
                    reinforce.to_effective_params(current) - TARGET_EFFECTIVE
                )
            ),
            projected_next_target_distance=float(
                np.linalg.norm(
                    reinforce.to_effective_params(next_params) - TARGET_EFFECTIVE
                )
            ),
        )
        return delta, audit

    def __call__(self, **kwargs: Any) -> np.ndarray:
        delta, audit = self.select(**kwargs)
        self.audits.append(audit)
        self.deltas.append(delta.copy())
        return delta


def invariant_pass(audit: ProjectionAudit) -> bool:
    return bool(
        audit.feasible
        and audit.projected_max_absolute_edit <= REWARD_BUDGET + 1e-10
        and audit.reward_sum_error <= 1e-10
        and audit.reward_mean_error <= 1e-10
        and audit.scalar_lower_violation <= 1e-10
        and audit.scalar_upper_violation <= 1e-10
        and audit.positive_logged_rewards == 0
        and audit.projection_kkt_residual <= 1e-10
    )


def verify_batches(
    attack: MomentPreservingRewardAttack,
    records: list[dict[str, Any]],
) -> list[VerifiedProjectionBatch]:
    if len(attack.audits) != len(records):
        raise RuntimeError("S2 attack and observer batch counts disagree")
    output: list[VerifiedProjectionBatch] = []
    for audit, delta, record in zip(attack.audits, attack.deltas, records):
        delta_error = float(
            np.linalg.norm(np.asarray(record["reward_delta"]) - delta)
        )
        reconstructed = reinforce.reinforce_gradient(
            record["features"],
            record["exploration_noise"],
            record["logged_rewards"],
            record["dones"],
            sigma=s1.SIGMA,
            gamma=s1.GAMMA,
        )
        raw_error = float(
            np.linalg.norm(reconstructed - np.asarray(record["raw_gradient"]))
        )
        # Independently reconstruct the actual capped/clipped next parameters.
        _applied, expected_next = s1.apply_update(
            record["learner_params_before"],
            reconstructed,
            actor_lr=s1.ACTOR_LR,
            max_gradient_norm=s1.GRADIENT_CAP,
        )
        next_error = float(
            np.linalg.norm(
                reinforce.to_effective_params(expected_next)
                - np.asarray(record["effective_params_after"])
            )
        )
        output.append(
            VerifiedProjectionBatch(
                **asdict(audit),
                learner_reward_delta_error=delta_error,
                learner_raw_gradient_error=raw_error,
                learner_next_parameter_error=next_error,
                all_invariants_pass=bool(
                    invariant_pass(audit)
                    and delta_error <= 1e-10
                    and raw_error <= 1e-10
                    and next_error <= 1e-10
                ),
            )
        )
    return output


def step_rows(
    seed: int, records: list[dict[str, Any]]
) -> list[S2StepRow]:
    output: list[S2StepRow] = []
    for record in records:
        for step in range(len(record["true_rewards"])):
            output.append(
                S2StepRow(
                    learner_seed=seed,
                    batch=int(record["batch"]),
                    step=step,
                    true_reward=float(record["true_rewards"][step]),
                    logged_reward=float(record["logged_rewards"][step]),
                    reward_delta=float(record["reward_delta"][step]),
                    feature_gain_coordinate=float(record["features"][step, 0]),
                    feature_bias_coordinate=float(record["features"][step, 1]),
                    exploration_noise=float(record["exploration_noise"][step]),
                    done=float(record["dones"][step]),
                )
            )
    return output


def run_s2_2070_smoke() -> S2SmokeDecision:
    s1_rows = s1.read_rows(S1_DECISION)
    if len(s1_rows) != 1 or s1_rows[0]["next_action"] != "close_s1_and_run_s2_2070_once":
        raise RuntimeError("S1 decision did not authorize the S2 fallback")
    seed, evaluation_seed = 2070, 9070
    protocol = s1.locked_args()
    attack = MomentPreservingRewardAttack(seed)
    records: list[dict[str, Any]] = []
    effective, training, traces = reinforce.train_reinforce(
        "s2_moment_preserving_projected_tanh",
        seed=seed,
        poisoned_rewards=True,
        freeze_updates=False,
        batches=protocol.batches,
        batch_steps=protocol.batch_steps,
        rho=protocol.rho,
        sigma=protocol.sigma,
        actor_lr=protocol.actor_lr,
        gamma=protocol.gamma,
        max_gradient_norm=protocol.max_gradient_norm,
        reward_poison_budget=protocol.reward_poison_budget,
        poison_temperature=protocol.poison_temperature,
        deployment_steps=protocol.deployment_steps,
        action_grid_size=protocol.action_grid_size,
        kernel_backend="casadi",
        reward_poisoner=attack,
        target_effective_params=TARGET_EFFECTIVE,
        batch_observer=s1.capture(records),
    )
    verified = verify_batches(attack, records)
    clean = s1.locked_clean_params(seed)
    rollout_rows = v3.run_contracts(
        seed, evaluation_seed, clean, effective, protocol
    )
    base_decision = v3.decide_seed(
        seed,
        evaluation_seed,
        training,
        v3.batch_rows(seed, "s2_projected_tanh", traces),
        rollout_rows,
        protocol,
    )
    initial_distance = float(np.linalg.norm(TARGET_EFFECTIVE))
    final_distance = float(np.linalg.norm(effective - TARGET_EFFECTIVE))
    invariants = all(row.all_invariants_pass for row in verified)
    target_pass = final_distance < initial_distance - 1e-12
    raw_effect = base_decision.poison_only_discordant >= 1
    smoke_pass = bool(
        invariants
        and training.adaptation_constraint_violations == 0
        and base_decision.budget_integrity
        and base_decision.pair_keys_valid
        and target_pass
        and base_decision.poison_initially_accepted >= 12
        and raw_effect
        and base_decision.resident_predictive_violations == 0
        and base_decision.paired_release_failures_with_timely_switch
        == base_decision.paired_release_failures
    )
    if not invariants or training.adaptation_constraint_violations != 0 or not target_pass:
        next_action = "diagnose_implementation_or_integrity"
    elif smoke_pass:
        next_action = "run_s2_burned_extension_2071_2072"
    else:
        next_action = "close_wp_without_new_seeds"
    decision = S2SmokeDecision(
        learner_seed=seed,
        evaluation_seed=evaluation_seed,
        audited_batches=len(verified),
        all_projection_invariants_pass=invariants,
        max_learner_reward_delta_error=max(
            row.learner_reward_delta_error for row in verified
        ),
        max_learner_raw_gradient_error=max(
            row.learner_raw_gradient_error for row in verified
        ),
        max_learner_next_parameter_error=max(
            row.learner_next_parameter_error for row in verified
        ),
        adaptation_constraint_violations=training.adaptation_constraint_violations,
        reward_budget_integrity=base_decision.budget_integrity,
        pair_keys_valid=base_decision.pair_keys_valid,
        poison_initially_accepted=base_decision.poison_initially_accepted,
        clean_release_violations=base_decision.clean_release_violations,
        poisoned_release_violations=base_decision.poisoned_release_violations,
        resident_predictive_violations=base_decision.resident_predictive_violations,
        poison_only_discordant=base_decision.poison_only_discordant,
        clean_only_discordant=base_decision.clean_only_discordant,
        paired_release_failures_with_timely_switch=(
            base_decision.paired_release_failures_with_timely_switch
        ),
        paired_release_failures=base_decision.paired_release_failures,
        initial_target_distance=initial_distance,
        final_target_distance=final_distance,
        target_progress=initial_distance - final_distance,
        target_progress_pass=target_pass,
        raw_release_effect_pass=raw_effect,
        s2_2070_smoke_pass=smoke_pass,
        next_action=next_action,
    )
    s1.write_csv(Path(f"{OUTPUT_PREFIX}_projection_batches.csv"), verified)
    s1.write_csv(Path(f"{OUTPUT_PREFIX}_steps.csv"), step_rows(seed, records))
    s1.write_csv(Path(f"{OUTPUT_PREFIX}_training.csv"), [training])
    v3.write_csv(Path(f"{OUTPUT_PREFIX}_rollouts.csv"), rollout_rows)
    v3.write_csv(Path(f"{OUTPUT_PREFIX}_base_decision.csv"), [base_decision])
    s1.write_csv(Path(f"{OUTPUT_PREFIX}_decision.csv"), [decision])
    print(decision)
    return decision


def finalize_wp() -> StealthWPDecision:
    offline_rows = s1.read_rows(
        RESULTS / "cartpole_stealth_s1_offline_decision.csv"
    )
    s1_rows = s1.read_rows(S1_DECISION)
    s2_rows = s1.read_rows(Path(f"{OUTPUT_PREFIX}_decision.csv"))
    if len(offline_rows) != 1 or len(s1_rows) != 1 or len(s2_rows) != 1:
        raise RuntimeError("missing unique S1/S2 decision artifacts")
    first = s1_rows[0]
    second = s2_rows[0]
    decision = StealthWPDecision(
        s1_offline_gate_pass=offline_rows[0]["offline_gate_pass"] == "True",
        s1_integrity_and_target_progress_pass=bool(
            first["all_permutation_invariants_pass"] == "True"
            and first["target_progress_pass"] == "True"
            and int(first["adaptation_constraint_violations"]) == 0
            and first["reward_budget_integrity"] == "True"
            and first["pair_keys_valid"] == "True"
        ),
        s1_raw_release_effect_pass=first["raw_release_effect_pass"] == "True",
        s1_2070_smoke_pass=first["s1_2070_smoke_pass"] == "True",
        s2_integrity_and_target_progress_pass=bool(
            second["all_projection_invariants_pass"] == "True"
            and second["target_progress_pass"] == "True"
            and int(second["adaptation_constraint_violations"]) == 0
            and second["reward_budget_integrity"] == "True"
            and second["pair_keys_valid"] == "True"
        ),
        s2_raw_release_effect_pass=second["raw_release_effect_pass"] == "True",
        s2_2070_smoke_pass=second["s2_2070_smoke_pass"] == "True",
        burned_extension_run=False,
        new_confirmation_namespace_opened=False,
        work_package_status="closed_insufficient_deployment_effect",
    )
    s1.write_csv(RESULTS / "cartpole_stealth_wp_decision.csv", [decision])
    print(decision)
    return decision


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--stage", required=True, choices=("s2_2070_smoke", "finalize_wp")
    )
    return parser.parse_args()


def main() -> None:
    options = parse_args()
    if options.stage == "s2_2070_smoke":
        run_s2_2070_smoke()
    else:
        finalize_wp()


if __name__ == "__main__":
    main()
