#!/usr/bin/env python3
"""Post-failure direction diagnostic on the burned development seed.

This script does not define or tune a confirmatory attack.  It reconstructs
the first clean batch of seed 2060 and asks whether several already available
directions have non-negative exact reward influence under the unclipped
normalized-gradient model.
"""

from __future__ import annotations

import csv
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np

import reward_certificate_geometry as geometry
import safe_control_gym_reinforce_reward_poisoning as reinforce


ROOT = Path(__file__).resolve().parent
RESULTS = ROOT / "results"
SEED = 2060
LOCKED_TARGET = np.asarray([18.0, -5.0], dtype=float)
PRIOR_HARMFUL_SNAPSHOT = np.asarray(
    [-2.3625524160241205, -5.0], dtype=float
)


@dataclass
class DirectionRow:
    name: str
    direction_gain: float
    direction_bias: float
    solver_status: str
    support: float
    clean_value: float
    minimum_centered_return_norm: float
    max_reward_poison: float
    resulting_gain: float
    resulting_bias: float
    projected_progress: float
    gradient_norm: float


def main() -> None:
    captured: dict[str, np.ndarray] = {}
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
        reinforce.train_reinforce(
            "burned_seed_direction_diagnostic",
            seed=SEED,
            poisoned_rewards=False,
            freeze_updates=False,
            batches=1,
            batch_steps=8,
            rho=0.005,
            sigma=0.8,
            actor_lr=1.0,
            gamma=0.97,
            max_gradient_norm=1.0,
            reward_poison_budget=2.0,
            poison_temperature=1.0,
            deployment_steps=120,
            action_grid_size=41,
            kernel_backend="casadi",
            target_effective_params=LOCKED_TARGET,
        )
    finally:
        reinforce.reinforce_gradient = original_gradient

    scores = geometry.gaussian_score_matrix(
        captured["features"], captured["noise"], 0.8
    )
    operator = geometry.centered_return_operator(captured["dones"], 0.97)
    coordinate_map = np.diag([1.0 / reinforce.THETA_SCALE, 1.0])
    candidates = {
        "locked_target_18_minus5": LOCKED_TARGET,
        "prior_harmful_snapshot": PRIOR_HARMFUL_SNAPSHOT,
        "negative_bias_axis": np.asarray([0.0, -1.0]),
        "negative_gain_axis": np.asarray([-1.0, 0.0]),
        "positive_gain_axis": np.asarray([1.0, 0.0]),
    }
    rows: list[DirectionRow] = []
    for name, raw_direction in candidates.items():
        direction = raw_direction / np.linalg.norm(raw_direction)
        support = geometry.worst_positive_halfspace_support(
            current_params=np.zeros(2),
            rewards=captured["rewards"],
            centered_operator=operator,
            score_matrix=scores,
            reward_budget=2.0,
            actor_lr=1.0,
            coordinate_map=coordinate_map,
            halfspace_row=direction,
            bisection_steps=40,
        )
        poison = (
            np.zeros(8)
            if support.solver_status == "nonpositive_conservative_zero"
            else support.reward_delta
        )
        gradient = geometry.normalized_reinforce_gradient(
            scores, captured["rewards"] + poison, operator
        )
        resulting = coordinate_map @ gradient
        rows.append(
            DirectionRow(
                name=name,
                direction_gain=float(direction[0]),
                direction_bias=float(direction[1]),
                solver_status=support.solver_status,
                support=support.support,
                clean_value=support.clean_value,
                minimum_centered_return_norm=(
                    support.minimum_centered_return_norm
                ),
                max_reward_poison=float(np.max(np.abs(poison))),
                resulting_gain=float(resulting[0]),
                resulting_bias=float(resulting[1]),
                projected_progress=float(direction @ resulting),
                gradient_norm=float(np.linalg.norm(gradient)),
            )
        )

    heuristic = reinforce.reward_poison(
        captured["noise"],
        captured["features"],
        np.zeros(2),
        reinforce.to_learner_params(LOCKED_TARGET),
        budget=2.0,
        temperature=1.0,
    )
    heuristic_gradient = geometry.normalized_reinforce_gradient(
        scores, captured["rewards"] + heuristic, operator
    )
    heuristic_effective = coordinate_map @ heuristic_gradient
    target_direction = LOCKED_TARGET / np.linalg.norm(LOCKED_TARGET)
    rows.append(
        DirectionRow(
            name="legacy_tanh_heuristic",
            direction_gain=float(target_direction[0]),
            direction_bias=float(target_direction[1]),
            solver_status="not_optimized",
            support=float(target_direction @ heuristic_effective),
            clean_value=float("nan"),
            minimum_centered_return_norm=float("nan"),
            max_reward_poison=float(np.max(np.abs(heuristic))),
            resulting_gain=float(heuristic_effective[0]),
            resulting_bias=float(heuristic_effective[1]),
            projected_progress=float(
                target_direction @ heuristic_effective
            ),
            gradient_norm=float(np.linalg.norm(heuristic_gradient)),
        )
    )
    path = RESULTS / "cartpole_reward_direction_diagnostic.csv"
    with path.open("w", newline="") as output:
        dictionaries = [asdict(row) for row in rows]
        writer = csv.DictWriter(output, fieldnames=list(dictionaries[0]))
        writer.writeheader()
        writer.writerows(dictionaries)
    for row in rows:
        print(row)
    print(f"wrote {path}")


if __name__ == "__main__":
    main()
