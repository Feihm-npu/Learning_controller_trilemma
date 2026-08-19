#!/usr/bin/env python3
"""Burned-seed diagnostic using homogenized clipped reward support."""

from __future__ import annotations

import numpy as np

import reward_certificate_geometry as geometry
import safe_control_gym_cartpole_prospective_gate_aware_attack as original
import safe_control_gym_reinforce_reward_poisoning as reinforce


RESULTS = original.RESULTS
OUTPUT_STEM = "cartpole_homogenized_gate_aware_2060"


class HomogenizedRewardPoisoner:
    """Maximize locked-target progress with the clipped conic support solver."""

    def __init__(self, learner_seed: int, bisection_steps: int = 40):
        self.learner_seed = learner_seed
        self.bisection_steps = bisection_steps
        self.rows: list[original.SupportBatch] = []

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
            poison = np.zeros_like(true_rewards)
            self.rows.append(
                original.SupportBatch(
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
            return poison

        unit_direction = direction / direction_norm
        scores = geometry.gaussian_score_matrix(features, exploration_noise, sigma)
        operator = geometry.centered_return_operator(dones, gamma)
        try:
            support = geometry.worst_positive_halfspace_support_with_gradient_clipping(
                current_params=learner_params,
                rewards=true_rewards,
                centered_operator=operator,
                score_matrix=scores,
                reward_budget=budget,
                actor_lr=actor_lr,
                coordinate_map=original.COORDINATE_MAP,
                halfspace_row=unit_direction,
                gradient_cap=max_gradient_norm,
                bisection_steps=self.bisection_steps,
            )
            if support.solver_status == "nonpositive_conservative_zero":
                poison = np.zeros_like(true_rewards)
                failure_reason = "no_positive_support_witness"
            else:
                poison = np.clip(support.reward_delta, -budget, budget)
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
            parameter_clipped = not np.allclose(candidate_unclipped, candidate)
            witness_value = float(
                unit_direction @ (original.COORDINATE_MAP @ candidate_unclipped)
            )
            try:
                minimum_norm = geometry.minimum_centered_return_norm(
                    true_rewards, operator, budget
                )
            except RuntimeError:
                minimum_norm = float("nan")
            row = original.SupportBatch(
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
                minimum_centered_return_norm=minimum_norm,
                max_reward_poison=float(np.max(np.abs(poison))),
                reward_l2_norm=float(np.linalg.norm(poison)),
                witness_support_error=(
                    abs(witness_value - support.support)
                    if not failure_reason
                    else float("nan")
                ),
                gradient_norm_before_clip=gradient_norm,
                gradient_clipped=gradient_clipped,
                parameter_clipped=parameter_clipped,
                nonzero_witness=bool(np.linalg.norm(poison) > 1e-10),
            )
        except (RuntimeError, ValueError) as error:
            poison = np.zeros_like(true_rewards)
            row = original.SupportBatch(
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
        print(
            f"batch={batch}: status={row.solver_status}, "
            f"edit={row.max_reward_poison:.6f}, "
            f"grad_clip={row.gradient_clipped}, param_clip={row.parameter_clipped}",
            flush=True,
        )
        return poison


def train_seed(learner_seed: int, evaluation_seed: int, args):
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
        target_effective_params=original.TARGET_EFFECTIVE,
    )
    clean_params, clean_result, _ = reinforce.train_reinforce(
        "homogenized_diagnostic_clean",
        poisoned_rewards=False,
        freeze_updates=False,
        **common,
    )
    optimizer = HomogenizedRewardPoisoner(
        learner_seed, bisection_steps=args.bisection_steps
    )
    poison_params, poison_result, _ = reinforce.train_reinforce(
        "homogenized_gate_aware_poison",
        poisoned_rewards=True,
        freeze_updates=False,
        reward_poisoner=optimizer,
        **common,
    )
    training = [
        original.TrainingRow(
            learner_seed=learner_seed,
            evaluation_seed=evaluation_seed,
            mechanism="clean",
            adaptation_constraint_violations=clean_result.adaptation_constraint_violations,
            actor_updates=clean_result.actor_updates,
            max_reward_poison=clean_result.max_reward_poison,
            nonzero_support_batches=0,
            solver_failure_batches=0,
            gradient_clipped_batches=0,
            parameter_clipped_batches=0,
            final_gain=float(clean_params[0]),
            final_bias=float(clean_params[1]),
        ),
        original.TrainingRow(
            learner_seed=learner_seed,
            evaluation_seed=evaluation_seed,
            mechanism="homogenized_gate_aware_poison",
            adaptation_constraint_violations=poison_result.adaptation_constraint_violations,
            actor_updates=poison_result.actor_updates,
            max_reward_poison=poison_result.max_reward_poison,
            nonzero_support_batches=sum(row.nonzero_witness for row in optimizer.rows),
            solver_failure_batches=sum(bool(row.failure_reason) for row in optimizer.rows),
            gradient_clipped_batches=sum(row.gradient_clipped for row in optimizer.rows),
            parameter_clipped_batches=sum(row.parameter_clipped for row in optimizer.rows),
            final_gain=float(poison_params[0]),
            final_bias=float(poison_params[1]),
        ),
    ]
    return clean_params, poison_params, optimizer.rows, training, poison_result


def main() -> None:
    args = original.parse_args()
    if args.learner_seeds != [2060] or args.evaluation_seeds != [9060]:
        raise ValueError("post-stop diagnostic is restricted to burned seeds 2060/9060")
    args.batches_out = RESULTS / f"{OUTPUT_STEM}_batches.csv"
    args.training_out = RESULTS / f"{OUTPUT_STEM}_training.csv"
    args.rollouts_out = RESULTS / f"{OUTPUT_STEM}_rollouts.csv"
    args.decision_out = RESULTS / f"{OUTPUT_STEM}_decision.csv"
    print("training burned-seed homogenized diagnostic", flush=True)
    clean, poison, support_rows, training, poison_result = train_seed(2060, 9060, args)
    print(f"clean={clean.tolist()}, poison={poison.tolist()}", flush=True)
    rollouts, decision = original.audit_seed(
        2060,
        9060,
        clean,
        poison,
        support_rows,
        poison_result,
        args,
    )
    original.write_csv(args.batches_out, support_rows)
    original.write_csv(args.training_out, training)
    original.write_csv(args.rollouts_out, rollouts)
    original.write_csv(args.decision_out, [decision])
    print(decision)


if __name__ == "__main__":
    main()
