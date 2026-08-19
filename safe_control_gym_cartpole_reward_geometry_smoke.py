#!/usr/bin/env python3
"""Real-batch normalized reward-influence and halfspace-support smoke."""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
from functools import partial
from pathlib import Path

import numpy as np
from safe_control_gym.utils.registration import make

import reward_certificate_geometry as geometry
import safe_control_gym_plausible_set_lifecycle_gate as gate
import safe_control_gym_reinforce_reward_poisoning as reinforce


ROOT = Path(__file__).resolve().parent
RESULTS = ROOT / "results"


@dataclass
class GeometryRow:
    constraint_index: int
    row_gain: float
    row_bias: float
    bound: float
    clean_value: float
    worst_support: float
    robust_margin: float
    witness_value: float
    witness_support_error: float
    witness_max_reward_poison: float
    witness_gradient_norm: float
    witness_gradient_clipped: bool
    witness_parameter_clipped: bool
    support_exact: bool
    robust_for_budget: bool


@dataclass
class GeometryDecision:
    seed: int
    batch_steps: int
    reward_budget: float
    constraints: int
    gradient_reconstruction_error: float
    clean_gradient_norm: float
    clean_gradient_clipped: bool
    clean_parameter_clipped: bool
    minimum_centered_return_norm: float
    minimum_robust_margin: float
    constraints_not_robust: int
    maximum_witness_support_error: float
    geometry_smoke_pass: bool


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, default=2040)
    parser.add_argument("--batch-steps", type=int, default=8)
    parser.add_argument("--rho", type=float, default=0.005)
    parser.add_argument("--sigma", type=float, default=0.8)
    parser.add_argument("--actor-lr", type=float, default=1.0)
    parser.add_argument("--gamma", type=float, default=0.97)
    parser.add_argument("--max-gradient-norm", type=float, default=1.0)
    parser.add_argument("--reward-budget", type=float, default=2.0)
    parser.add_argument("--action-grid-size", type=int, default=41)
    parser.add_argument(
        "--rows-out",
        type=Path,
        default=RESULTS / "cartpole_reward_geometry_smoke_rows.csv",
    )
    parser.add_argument(
        "--decision-out",
        type=Path,
        default=RESULTS / "cartpole_reward_geometry_smoke_decision.csv",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    captured: dict[str, np.ndarray | float] = {}
    original_gradient = reinforce.reinforce_gradient

    def capture_gradient(
        features: np.ndarray,
        exploration_noise: np.ndarray,
        logged_rewards: np.ndarray,
        dones: np.ndarray,
        *,
        sigma: float,
        gamma: float,
    ) -> np.ndarray:
        captured.update(
            features=np.asarray(features, dtype=float).copy(),
            noise=np.asarray(exploration_noise, dtype=float).copy(),
            rewards=np.asarray(logged_rewards, dtype=float).copy(),
            dones=np.asarray(dones, dtype=float).copy(),
            sigma=float(sigma),
            gamma=float(gamma),
        )
        return original_gradient(
            features,
            exploration_noise,
            logged_rewards,
            dones,
            sigma=sigma,
            gamma=gamma,
        )

    reinforce.reinforce_gradient = capture_gradient
    try:
        effective_params, _training, traces = reinforce.train_reinforce(
            "reward_geometry_smoke",
            seed=args.seed,
            poisoned_rewards=False,
            freeze_updates=False,
            batches=1,
            batch_steps=args.batch_steps,
            rho=args.rho,
            sigma=args.sigma,
            actor_lr=args.actor_lr,
            gamma=args.gamma,
            max_gradient_norm=args.max_gradient_norm,
            reward_poison_budget=args.reward_budget,
            poison_temperature=1.0,
            deployment_steps=120,
            action_grid_size=args.action_grid_size,
            kernel_backend="casadi",
        )
    finally:
        reinforce.reinforce_gradient = original_gradient

    features = np.asarray(captured["features"], dtype=float)
    noise = np.asarray(captured["noise"], dtype=float)
    rewards = np.asarray(captured["rewards"], dtype=float)
    dones = np.asarray(captured["dones"], dtype=float)
    scores = geometry.gaussian_score_matrix(features, noise, args.sigma)
    operator = geometry.centered_return_operator(dones, args.gamma)
    reconstructed = geometry.normalized_reinforce_gradient(
        scores, rewards, operator
    )
    artifact_gradient = original_gradient(
        features,
        noise,
        rewards,
        dones,
        sigma=args.sigma,
        gamma=args.gamma,
    )
    reconstruction_error = float(
        np.max(np.abs(reconstructed - artifact_gradient))
    )
    clean_gradient_norm = float(np.linalg.norm(artifact_gradient))
    clean_gradient_clipped = clean_gradient_norm > args.max_gradient_norm
    clean_unclipped_learner = args.actor_lr * artifact_gradient
    clean_clipped_learner = np.minimum(
        np.maximum(clean_unclipped_learner, reinforce.LEARNER_LOW),
        reinforce.LEARNER_HIGH,
    )
    clean_parameter_clipped = not np.allclose(
        clean_unclipped_learner, clean_clipped_learner
    )
    np.testing.assert_allclose(
        reinforce.to_effective_params(clean_clipped_learner),
        effective_params,
        atol=1e-12,
        rtol=1e-12,
    )

    task_config, lqr_config, _cbf_config = gate.build_configs(args.seed)
    env_func = partial(make, "cartpole", **task_config)
    env = env_func(gui=False)
    ctrl = make("lqr", env_func, **lqr_config)
    ctrl.reset()
    observation, info = env.reset(seed=args.seed)
    ctrl.reset_before_run(observation, info, env=env)
    constraints = gate.parameter_constraints(
        ctrl,
        info,
        np.zeros(4, dtype=float),
        args.rho,
        gate.make_model_from_env(env),
        gate.action_grid_from_env(env, args.action_grid_size),
        future_span=0.03,
        guard_margin=0.0,
        kernel_backend="casadi",
        casadi_fd_func=env.symbolic.fd_func,
        cbf_filter=None,
        cbf_action_tolerance=1e-5,
    )
    ctrl.close()
    env.close()
    if constraints is None:
        raise RuntimeError("locked geometry gate is infeasible")

    coordinate_map = np.diag([1.0 / reinforce.THETA_SCALE, 1.0])
    rows: list[GeometryRow] = []
    minimum_norm = float("inf")
    for index, (row, bound) in enumerate(
        zip(constraints.rows, constraints.bounds)
    ):
        support = geometry.worst_positive_halfspace_support(
            current_params=np.zeros(2),
            rewards=rewards,
            centered_operator=operator,
            score_matrix=scores,
            reward_budget=args.reward_budget,
            actor_lr=args.actor_lr,
            coordinate_map=coordinate_map,
            halfspace_row=row,
            bisection_steps=40,
        )
        support_exact = (
            support.solver_status != "nonpositive_conservative_zero"
        )
        if support_exact:
            witness_gradient = geometry.normalized_reinforce_gradient(
                scores, rewards + support.reward_delta, operator
            )
            witness_gradient_norm = float(np.linalg.norm(witness_gradient))
            witness_unclipped = args.actor_lr * witness_gradient
            witness_clipped = np.minimum(
                np.maximum(witness_unclipped, reinforce.LEARNER_LOW),
                reinforce.LEARNER_HIGH,
            )
            witness_effective = coordinate_map @ witness_unclipped
            witness_value = float(row @ witness_effective)
            support_error = abs(witness_value - support.support)
            gradient_clipped = witness_gradient_norm > args.max_gradient_norm
            parameter_clipped = not np.allclose(
                witness_unclipped, witness_clipped
            )
        else:
            witness_gradient_norm = float("nan")
            witness_value = float("nan")
            support_error = float("nan")
            gradient_clipped = False
            parameter_clipped = False
        robust_margin = float(bound - support.support)
        rows.append(
            GeometryRow(
                constraint_index=index,
                row_gain=float(row[0]),
                row_bias=float(row[1]),
                bound=float(bound),
                clean_value=support.clean_value,
                worst_support=support.support,
                robust_margin=robust_margin,
                witness_value=witness_value,
                witness_support_error=support_error,
                witness_max_reward_poison=float(
                    np.max(np.abs(support.reward_delta))
                ),
                witness_gradient_norm=witness_gradient_norm,
                witness_gradient_clipped=gradient_clipped,
                witness_parameter_clipped=parameter_clipped,
                support_exact=support_exact,
                robust_for_budget=bool(
                    robust_margin >= -1e-6
                    and not gradient_clipped
                    and not parameter_clipped
                ),
            )
        )
        minimum_norm = min(
            minimum_norm, support.minimum_centered_return_norm
        )

    exact_errors = [
        row.witness_support_error for row in rows if row.support_exact
    ]
    max_error = max(exact_errors) if exact_errors else 0.0
    minimum_margin = min(row.robust_margin for row in rows)
    invalid_witnesses = sum(
        row.support_exact
        and (row.witness_gradient_clipped or row.witness_parameter_clipped)
        for row in rows
    )
    decision = GeometryDecision(
        seed=args.seed,
        batch_steps=args.batch_steps,
        reward_budget=args.reward_budget,
        constraints=len(rows),
        gradient_reconstruction_error=reconstruction_error,
        clean_gradient_norm=clean_gradient_norm,
        clean_gradient_clipped=clean_gradient_clipped,
        clean_parameter_clipped=clean_parameter_clipped,
        minimum_centered_return_norm=minimum_norm,
        minimum_robust_margin=minimum_margin,
        constraints_not_robust=sum(row.robust_margin < -1e-6 for row in rows),
        maximum_witness_support_error=max_error,
        geometry_smoke_pass=bool(
            reconstruction_error <= 1e-10
            and not clean_gradient_clipped
            and not clean_parameter_clipped
            and minimum_norm > 1e-7
            and invalid_witnesses == 0
            and max_error <= 1e-4
        ),
    )
    contract_rows = [asdict(row) for row in rows]
    args.rows_out.parent.mkdir(parents=True, exist_ok=True)
    import csv

    with args.rows_out.open("w", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=list(contract_rows[0]))
        writer.writeheader()
        writer.writerows(contract_rows)
    with args.decision_out.open("w", newline="") as output:
        dictionary = asdict(decision)
        writer = csv.DictWriter(output, fieldnames=list(dictionary))
        writer.writeheader()
        writer.writerow(dictionary)
    print(decision)
    print(f"wrote {args.rows_out}")
    print(f"wrote {args.decision_out}")


if __name__ == "__main__":
    main()
