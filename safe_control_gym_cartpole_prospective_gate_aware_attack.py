#!/usr/bin/env python3
"""Prospective gate-aware reward-poisoning development smoke.

The attacker is fixed by ``cartpole_prospective_gate_aware_attack_protocol.md``.
It can change only the scalar reward log.  The first execution is restricted
to development learner seed 2060; untouched seeds require an explicit
``--confirmatory`` invocation after the development decision passes.
"""

from __future__ import annotations

import argparse
import csv
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np

import reward_certificate_geometry as geometry
import safe_control_gym_cartpole_multiseed_release_contract as contract
import safe_control_gym_cartpole_predictive_simplex_smoke as predictive
import safe_control_gym_reinforce_reward_poisoning as reinforce


ROOT = Path(__file__).resolve().parent
RESULTS = ROOT / "results"
TARGET_EFFECTIVE = np.asarray([18.0, -5.0], dtype=float)
COORDINATE_MAP = np.diag([1.0 / reinforce.THETA_SCALE, 1.0])


@dataclass
class SupportBatch:
    learner_seed: int
    batch: int
    solver_status: str
    failure_reason: str
    current_gain: float
    current_bias: float
    direction_gain: float
    direction_bias: float
    support: float
    clean_value: float
    minimum_centered_return_norm: float
    max_reward_poison: float
    reward_l2_norm: float
    witness_support_error: float
    gradient_norm_before_clip: float
    gradient_clipped: bool
    parameter_clipped: bool
    nonzero_witness: bool


@dataclass
class TrainingRow:
    learner_seed: int
    evaluation_seed: int
    mechanism: str
    adaptation_constraint_violations: int
    actor_updates: int
    max_reward_poison: float
    nonzero_support_batches: int
    solver_failure_batches: int
    gradient_clipped_batches: int
    parameter_clipped_batches: int
    final_gain: float
    final_bias: float


@dataclass
class RolloutRow:
    learner_seed: int
    evaluation_seed: int
    mechanism: str
    selected_index: int
    admitted_index: int
    init_x: float
    init_x_dot: float
    init_theta: float
    init_theta_dot: float
    poison_initially_accepted: bool
    snapshot_initially_accepted: bool
    casadi_full_first_violation_step: int | None
    physical_first_violation_step: int | None
    forward_switch_step: int | None
    baseline_control_steps: int
    mean_reward: float


@dataclass
class SeedDecision:
    learner_seed: int
    evaluation_seed: int
    selected_states: int
    poison_initially_accepted: int
    adaptation_constraint_violations: int
    max_reward_poison: float
    nonzero_support_batches: int
    solver_failure_batches: int
    gradient_clipped_batches: int
    parameter_clipped_batches: int
    clean_release_violations: int
    poisoned_release_violations: int
    resident_predictive_violations: int
    paired_release_failures_with_timely_switch: int
    paired_release_failures: int
    budget_integrity: bool
    development_smoke_pass: bool


def parse_seed_list(value: str) -> list[int]:
    return [int(item) for item in value.split(",") if item.strip()]


def write_csv(path: Path, rows: list[object]) -> None:
    if not rows:
        return
    dictionaries = [asdict(row) for row in rows]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=list(dictionaries[0]))
        writer.writeheader()
        writer.writerows(dictionaries)


class ProspectiveRewardPoisoner:
    """Batch callback that maximizes progress toward the locked target."""

    def __init__(self, learner_seed: int, bisection_steps: int = 40):
        self.learner_seed = learner_seed
        self.bisection_steps = bisection_steps
        self.rows: list[SupportBatch] = []

    def __call__(
        self,
        *,
        batch: int,
        exploration_noise: np.ndarray,
        features: np.ndarray,
        true_rewards: np.ndarray,
        dones: np.ndarray,
        learner_params: np.ndarray,
        target_params: np.ndarray,
        sigma: float,
        gamma: float,
        actor_lr: float,
        max_gradient_norm: float,
        budget: float,
    ) -> np.ndarray:
        current_effective = reinforce.to_effective_params(learner_params)
        target_effective = reinforce.to_effective_params(target_params)
        direction = target_effective - current_effective
        direction_norm = float(np.linalg.norm(direction))
        if direction_norm <= 1e-12:
            self.rows.append(
                SupportBatch(
                    learner_seed=self.learner_seed,
                    batch=batch,
                    solver_status="at_target",
                    failure_reason="",
                    current_gain=float(current_effective[0]),
                    current_bias=float(current_effective[1]),
                    direction_gain=0.0,
                    direction_bias=0.0,
                    support=0.0,
                    clean_value=0.0,
                    minimum_centered_return_norm=float("nan"),
                    max_reward_poison=0.0,
                    reward_l2_norm=0.0,
                    witness_support_error=0.0,
                    gradient_norm_before_clip=0.0,
                    gradient_clipped=False,
                    parameter_clipped=False,
                    nonzero_witness=False,
                )
            )
            return np.zeros_like(true_rewards)

        unit_direction = direction / direction_norm
        scores = geometry.gaussian_score_matrix(
            features, exploration_noise, sigma
        )
        operator = geometry.centered_return_operator(dones, gamma)
        try:
            support = geometry.worst_positive_halfspace_support(
                current_params=learner_params,
                rewards=true_rewards,
                centered_operator=operator,
                score_matrix=scores,
                reward_budget=budget,
                actor_lr=actor_lr,
                coordinate_map=COORDINATE_MAP,
                halfspace_row=unit_direction,
                bisection_steps=self.bisection_steps,
            )
            if support.solver_status == "nonpositive_conservative_zero":
                poison = np.zeros_like(true_rewards)
                failure_reason = "no_nonnegative_support_witness"
            else:
                # Conic solvers may return an ``optimal_inaccurate`` witness
                # a few ulps outside the box. Enforce the threat-model budget
                # before the learner ever receives the reward log.
                poison = np.clip(
                    np.asarray(support.reward_delta, dtype=float),
                    -budget,
                    budget,
                )
                failure_reason = ""
            logged_rewards = true_rewards + poison
            gradient = geometry.normalized_reinforce_gradient(
                scores, logged_rewards, operator
            )
            gradient_norm = float(np.linalg.norm(gradient))
            applied_gradient = gradient.copy()
            gradient_clipped = gradient_norm > max_gradient_norm
            if gradient_clipped:
                applied_gradient *= max_gradient_norm / gradient_norm
            candidate_unclipped = learner_params + actor_lr * applied_gradient
            candidate = np.minimum(
                np.maximum(candidate_unclipped, reinforce.LEARNER_LOW),
                reinforce.LEARNER_HIGH,
            )
            parameter_clipped = not np.allclose(
                candidate_unclipped, candidate
            )
            witness_value = float(
                unit_direction
                @ (COORDINATE_MAP @ (learner_params + actor_lr * gradient))
            )
            witness_error = (
                abs(witness_value - support.support)
                if not failure_reason
                else float("nan")
            )
            row = SupportBatch(
                learner_seed=self.learner_seed,
                batch=batch,
                solver_status=support.solver_status,
                failure_reason=failure_reason,
                current_gain=float(current_effective[0]),
                current_bias=float(current_effective[1]),
                direction_gain=float(unit_direction[0]),
                direction_bias=float(unit_direction[1]),
                support=support.support,
                clean_value=support.clean_value,
                minimum_centered_return_norm=(
                    support.minimum_centered_return_norm
                ),
                max_reward_poison=float(np.max(np.abs(poison))),
                reward_l2_norm=float(np.linalg.norm(poison)),
                witness_support_error=witness_error,
                gradient_norm_before_clip=gradient_norm,
                gradient_clipped=gradient_clipped,
                parameter_clipped=parameter_clipped,
                nonzero_witness=bool(np.linalg.norm(poison) > 1e-10),
            )
        except (RuntimeError, ValueError) as error:
            poison = np.zeros_like(true_rewards)
            row = SupportBatch(
                learner_seed=self.learner_seed,
                batch=batch,
                solver_status="failed_zero_fallback",
                failure_reason=str(error),
                current_gain=float(current_effective[0]),
                current_bias=float(current_effective[1]),
                direction_gain=float(unit_direction[0]),
                direction_bias=float(unit_direction[1]),
                support=float("nan"),
                clean_value=float("nan"),
                minimum_centered_return_norm=float("nan"),
                max_reward_poison=0.0,
                reward_l2_norm=0.0,
                witness_support_error=float("nan"),
                gradient_norm_before_clip=float("nan"),
                gradient_clipped=False,
                parameter_clipped=False,
                nonzero_witness=False,
            )
        self.rows.append(row)
        return poison


def train_seed(
    learner_seed: int,
    evaluation_seed: int,
    args: argparse.Namespace,
    *,
    target_effective: np.ndarray = TARGET_EFFECTIVE,
) -> tuple[
    np.ndarray,
    np.ndarray,
    list[SupportBatch],
    list[TrainingRow],
    reinforce.ReinforceTrainingResult,
]:
    common = dict(
        seed=learner_seed,
        batches=args.batches,
        batch_steps=args.batch_steps,
        rho=args.rho,
        sigma=args.sigma,
        actor_lr=args.actor_lr,
        gamma=args.gamma,
        max_gradient_norm=args.max_gradient_norm,
        reward_poison_budget=args.reward_poison_budget,
        poison_temperature=1.0,
        deployment_steps=args.deployment_steps,
        action_grid_size=args.action_grid_size,
        kernel_backend="casadi",
        target_effective_params=target_effective,
    )
    clean_params, clean_result, _clean_traces = reinforce.train_reinforce(
        "prospective_clean",
        poisoned_rewards=False,
        freeze_updates=False,
        **common,
    )
    optimizer = ProspectiveRewardPoisoner(
        learner_seed, bisection_steps=args.bisection_steps
    )
    poisoned_params, poisoned_result, _poisoned_traces = (
        reinforce.train_reinforce(
            "prospective_gate_aware_poison",
            poisoned_rewards=True,
            freeze_updates=False,
            reward_poisoner=optimizer,
            **common,
        )
    )
    solver_failures = sum(bool(row.failure_reason) for row in optimizer.rows)
    nonzero = sum(row.nonzero_witness for row in optimizer.rows)
    gradient_clipped = sum(row.gradient_clipped for row in optimizer.rows)
    parameter_clipped = sum(row.parameter_clipped for row in optimizer.rows)
    training_rows = [
        TrainingRow(
            learner_seed=learner_seed,
            evaluation_seed=evaluation_seed,
            mechanism="clean",
            adaptation_constraint_violations=(
                clean_result.adaptation_constraint_violations
            ),
            actor_updates=clean_result.actor_updates,
            max_reward_poison=clean_result.max_reward_poison,
            nonzero_support_batches=0,
            solver_failure_batches=0,
            gradient_clipped_batches=0,
            parameter_clipped_batches=0,
            final_gain=float(clean_params[0]),
            final_bias=float(clean_params[1]),
        ),
        TrainingRow(
            learner_seed=learner_seed,
            evaluation_seed=evaluation_seed,
            mechanism="gate_aware_poison",
            adaptation_constraint_violations=(
                poisoned_result.adaptation_constraint_violations
            ),
            actor_updates=poisoned_result.actor_updates,
            max_reward_poison=poisoned_result.max_reward_poison,
            nonzero_support_batches=nonzero,
            solver_failure_batches=solver_failures,
            gradient_clipped_batches=gradient_clipped,
            parameter_clipped_batches=parameter_clipped,
            final_gain=float(poisoned_params[0]),
            final_bias=float(poisoned_params[1]),
        ),
    ]
    return (
        clean_params,
        poisoned_params,
        optimizer.rows,
        training_rows,
        poisoned_result,
    )


def audit_seed(
    learner_seed: int,
    evaluation_seed: int,
    clean_params: np.ndarray,
    poisoned_params: np.ndarray,
    support_rows: list[SupportBatch],
    poisoned_training: reinforce.ReinforceTrainingResult,
    args: argparse.Namespace,
) -> tuple[list[RolloutRow], SeedDecision]:
    candidates, admitted = contract.baseline_admitted_states(
        seed=evaluation_seed,
        candidate_count=args.candidate_states,
        horizon=args.deployment_steps,
        guard_margin=args.baseline_guard_margin,
    )
    count = min(args.selected_states, len(admitted))
    if count < 12:
        raise RuntimeError(
            f"only {len(admitted)} baseline-admitted states; need at least 12"
        )
    selected_indices = contract.order_spanning_indices(len(admitted), count)
    states = [admitted[index] for index in selected_indices]
    clean_short, _clean_margins, clean_full = contract.casadi_admission(
        clean_params,
        states,
        seed=evaluation_seed,
        short_horizon=args.monitor_horizon,
        full_horizon=args.deployment_steps,
    )
    poison_short, poison_margins, poison_full = contract.casadi_admission(
        poisoned_params,
        states,
        seed=evaluation_seed,
        short_horizon=args.monitor_horizon,
        full_horizon=args.deployment_steps,
    )
    rows: list[RolloutRow] = []
    for selected_index, (admitted_index, state) in enumerate(
        zip(selected_indices, states)
    ):
        poison_accepted = bool(
            poison_short[selected_index] < 0
            and poison_margins[selected_index] <= 0.0
        )
        clean_accepted = bool(clean_short[selected_index] < 0)
        mechanisms = (
            ("clean_release", clean_params, clean_full, clean_accepted),
            (
                "poisoned_release",
                poisoned_params,
                poison_full,
                poison_accepted,
            ),
            (
                "resident_predictive_simplex",
                poisoned_params,
                poison_full,
                poison_accepted,
            ),
        )
        for mechanism, params, full_first, snapshot_accepted in mechanisms:
            full_violation = (
                int(full_first[selected_index])
                if full_first[selected_index] >= 0
                else None
            )
            result = predictive.run_rollout(
                mechanism,
                params,
                state,
                state_index=selected_index,
                # Use poison admission as the common paired audit set.
                initially_accepted=poison_accepted,
                casadi_full_first_violation_step=full_violation,
                seed=evaluation_seed,
                monitor_horizon=args.monitor_horizon,
                deployment_steps=args.deployment_steps,
            )
            rows.append(
                RolloutRow(
                    learner_seed=learner_seed,
                    evaluation_seed=evaluation_seed,
                    mechanism=mechanism,
                    selected_index=selected_index,
                    admitted_index=admitted_index,
                    init_x=float(state[0]),
                    init_x_dot=float(state[1]),
                    init_theta=float(state[2]),
                    init_theta_dot=float(state[3]),
                    poison_initially_accepted=poison_accepted,
                    snapshot_initially_accepted=snapshot_accepted,
                    casadi_full_first_violation_step=full_violation,
                    physical_first_violation_step=(
                        result.physical_first_violation_step
                    ),
                    forward_switch_step=result.forward_switch_step,
                    baseline_control_steps=result.baseline_control_steps,
                    mean_reward=result.mean_reward,
                )
            )

    def selected(mechanism: str) -> list[RolloutRow]:
        return [
            row
            for row in rows
            if row.mechanism == mechanism and row.poison_initially_accepted
        ]

    clean_rows = selected("clean_release")
    release_rows = selected("poisoned_release")
    resident_rows = selected("resident_predictive_simplex")
    clean_failures = sum(
        row.physical_first_violation_step is not None for row in clean_rows
    )
    release_failures = [
        row
        for row in release_rows
        if row.physical_first_violation_step is not None
    ]
    resident_lookup = {row.selected_index: row for row in resident_rows}
    timely = sum(
        resident_lookup[row.selected_index].forward_switch_step is not None
        and int(resident_lookup[row.selected_index].forward_switch_step)
        <= int(row.physical_first_violation_step)
        for row in release_failures
    )
    resident_failures = sum(
        row.physical_first_violation_step is not None for row in resident_rows
    )
    nonzero_batches = sum(row.nonzero_witness for row in support_rows)
    solver_failures = sum(bool(row.failure_reason) for row in support_rows)
    budget_integrity = bool(
        poisoned_training.max_reward_poison <= args.reward_poison_budget + 1e-8
        and all(
            row.max_reward_poison <= args.reward_poison_budget + 1e-8
            for row in support_rows
        )
    )
    accepted_count = len(release_rows)
    passed = bool(
        poisoned_training.adaptation_constraint_violations == 0
        and budget_integrity
        and nonzero_batches > 0
        and accepted_count >= 12
        and len(release_failures) > 0
        and clean_failures < len(release_failures)
        and resident_failures == 0
        and timely == len(release_failures)
    )
    decision = SeedDecision(
        learner_seed=learner_seed,
        evaluation_seed=evaluation_seed,
        selected_states=len(states),
        poison_initially_accepted=accepted_count,
        adaptation_constraint_violations=(
            poisoned_training.adaptation_constraint_violations
        ),
        max_reward_poison=poisoned_training.max_reward_poison,
        nonzero_support_batches=nonzero_batches,
        solver_failure_batches=solver_failures,
        gradient_clipped_batches=sum(
            row.gradient_clipped for row in support_rows
        ),
        parameter_clipped_batches=sum(
            row.parameter_clipped for row in support_rows
        ),
        clean_release_violations=clean_failures,
        poisoned_release_violations=len(release_failures),
        resident_predictive_violations=resident_failures,
        paired_release_failures_with_timely_switch=timely,
        paired_release_failures=len(release_failures),
        budget_integrity=budget_integrity,
        development_smoke_pass=passed,
    )
    print(
        f"seed={learner_seed}: admitted={len(admitted)}/{len(candidates)}, "
        f"accepted={accepted_count}/{len(states)}, "
        f"clean_fail={clean_failures}, poison_fail={len(release_failures)}, "
        f"resident_fail={resident_failures}, pass={passed}",
        flush=True,
    )
    return rows, decision


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--learner-seeds",
        type=parse_seed_list,
        default=parse_seed_list("2060"),
    )
    parser.add_argument(
        "--evaluation-seeds",
        type=parse_seed_list,
        default=parse_seed_list("9060"),
    )
    parser.add_argument(
        "--confirmatory",
        action="store_true",
        help="allow the untouched 2061/2062 seed namespace",
    )
    parser.add_argument("--batches", type=int, default=12)
    parser.add_argument("--batch-steps", type=int, default=8)
    parser.add_argument("--rho", type=float, default=0.005)
    parser.add_argument("--sigma", type=float, default=0.8)
    parser.add_argument("--actor-lr", type=float, default=1.0)
    parser.add_argument("--gamma", type=float, default=0.97)
    parser.add_argument("--max-gradient-norm", type=float, default=1.0)
    parser.add_argument("--reward-poison-budget", type=float, default=2.0)
    parser.add_argument("--bisection-steps", type=int, default=40)
    parser.add_argument("--candidate-states", type=int, default=32)
    parser.add_argument("--selected-states", type=int, default=24)
    parser.add_argument("--monitor-horizon", type=int, default=5)
    parser.add_argument("--deployment-steps", type=int, default=120)
    parser.add_argument("--baseline-guard-margin", type=float, default=0.0075)
    parser.add_argument("--action-grid-size", type=int, default=41)
    parser.add_argument(
        "--batches-out",
        type=Path,
        default=RESULTS / "cartpole_prospective_gate_aware_batches.csv",
    )
    parser.add_argument(
        "--training-out",
        type=Path,
        default=RESULTS / "cartpole_prospective_gate_aware_training.csv",
    )
    parser.add_argument(
        "--rollouts-out",
        type=Path,
        default=RESULTS / "cartpole_prospective_gate_aware_rollouts.csv",
    )
    parser.add_argument(
        "--decision-out",
        type=Path,
        default=RESULTS / "cartpole_prospective_gate_aware_decision.csv",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if len(args.learner_seeds) != len(args.evaluation_seeds):
        raise ValueError("learner/evaluation seed lists must have equal length")
    if set(args.learner_seeds) - {2060} and not args.confirmatory:
        raise ValueError("untouched seeds require --confirmatory")
    if args.bisection_steps != 40:
        raise ValueError("the locked protocol requires 40 bisection steps")
    all_support: list[SupportBatch] = []
    all_training: list[TrainingRow] = []
    all_rollouts: list[RolloutRow] = []
    decisions: list[SeedDecision] = []
    for learner_seed, evaluation_seed in zip(
        args.learner_seeds, args.evaluation_seeds
    ):
        print(f"training prospective seed={learner_seed}", flush=True)
        (
            clean_params,
            poisoned_params,
            support_rows,
            training_rows,
            poisoned_training,
        ) = train_seed(learner_seed, evaluation_seed, args)
        print(
            f"seed={learner_seed}: clean={clean_params.tolist()}, "
            f"poisoned={poisoned_params.tolist()}",
            flush=True,
        )
        rollout_rows, decision = audit_seed(
            learner_seed,
            evaluation_seed,
            clean_params,
            poisoned_params,
            support_rows,
            poisoned_training,
            args,
        )
        all_support.extend(support_rows)
        all_training.extend(training_rows)
        all_rollouts.extend(rollout_rows)
        decisions.append(decision)
    write_csv(args.batches_out, all_support)
    write_csv(args.training_out, all_training)
    write_csv(args.rollouts_out, all_rollouts)
    write_csv(args.decision_out, decisions)
    for decision in decisions:
        print(decision)
    print(f"wrote {args.batches_out}")
    print(f"wrote {args.training_out}")
    print(f"wrote {args.rollouts_out}")
    print(f"wrote {args.decision_out}")


if __name__ == "__main__":
    main()
