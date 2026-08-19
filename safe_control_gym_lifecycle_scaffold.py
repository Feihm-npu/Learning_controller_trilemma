#!/usr/bin/env python3
"""Safe-Control-Gym scaffold for lifecycle-gate experiments.

This is the first runnable adapter for the standard CPS/control benchmark track.
It verifies that the official Safe-Control-Gym cartpole and 2D quadrotor
environments run in the local `.llm` environment and emits rollout metrics in
the same CSV-friendly style as the smaller lifecycle benchmarks.

The strong-baseline work will extend this scaffold with official LQR/MPC/CBF,
MPSC, Safety Layer, and RL controllers. For now, the zero/random policies are
only environment smoke baselines; they are not claimed as paper baselines.
"""

from __future__ import annotations

import csv
import os
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable

import numpy as np


ROOT = Path(__file__).resolve().parent
RESULTS_DIR = ROOT / "results"


def configure_matplotlib() -> None:
    cache_dir = Path("/tmp/matplotlib-lifecycle-gate")
    cache_dir.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("MPLCONFIGDIR", str(cache_dir))


configure_matplotlib()

import safe_control_gym  # noqa: F401
from safe_control_gym.utils.registration import make


Policy = Callable[[object, np.ndarray, np.random.Generator], np.ndarray]


@dataclass
class RolloutSummary:
    benchmark: str
    task: str
    policy: str
    episodes: int
    steps: int
    mean_reward: float
    constraint_violations: int
    violation_rate: float
    mean_action_norm: float
    mean_state_norm: float


def make_env(task: str):
    if task == "cartpole":
        return make(
            "cartpole",
            gui=False,
            task="stabilization",
            episode_len_sec=1.0,
            randomized_init=True,
            cost="quadratic",
            done_on_violation=False,
        )
    if task == "quadrotor_2d":
        return make(
            "quadrotor",
            gui=False,
            quad_type=2,
            task="stabilization",
            episode_len_sec=1.0,
            randomized_init=True,
            cost="quadratic",
            done_on_violation=False,
        )
    raise ValueError(f"unsupported task: {task}")


def zero_policy(env: object, _obs: np.ndarray, _rng: np.random.Generator) -> np.ndarray:
    low = np.asarray(env.action_space.low, dtype=float)
    high = np.asarray(env.action_space.high, dtype=float)
    return np.clip(np.zeros_like(low), low, high)


def random_policy(env: object, _obs: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    low = np.asarray(env.action_space.low, dtype=float)
    high = np.asarray(env.action_space.high, dtype=float)
    return rng.uniform(low, high).astype(float)


POLICIES: dict[str, Policy] = {
    "zero_policy_smoke": zero_policy,
    "random_policy_smoke": random_policy,
}


def rollout(task: str, policy_name: str, policy: Policy, episodes: int, seed: int) -> RolloutSummary:
    rng = np.random.default_rng(seed)
    rewards: list[float] = []
    action_norms: list[float] = []
    state_norms: list[float] = []
    violations = 0
    steps = 0

    for episode in range(episodes):
        env = make_env(task)
        obs, _ = env.reset(seed=seed + episode)
        done = False
        while not done:
            if not hasattr(env, "out_of_bounds"):
                env.out_of_bounds = False
            action = policy(env, np.asarray(obs, dtype=float), rng)
            obs, reward, done, info = env.step(action)
            rewards.append(float(reward))
            action_norms.append(float(np.linalg.norm(action)))
            state_norms.append(float(np.linalg.norm(np.asarray(obs, dtype=float))))
            violations += int(bool(info.get("constraint_violation", False)))
            steps += 1
        env.close()

    return RolloutSummary(
        benchmark="safe_control_gym",
        task=task,
        policy=policy_name,
        episodes=episodes,
        steps=steps,
        mean_reward=float(np.mean(rewards)) if rewards else 0.0,
        constraint_violations=violations,
        violation_rate=violations / steps if steps else 0.0,
        mean_action_norm=float(np.mean(action_norms)) if action_norms else 0.0,
        mean_state_norm=float(np.mean(state_norms)) if state_norms else 0.0,
    )


def write_csv(path: Path, rows: list[RolloutSummary]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(asdict(rows[0]).keys()))
        writer.writeheader()
        writer.writerows(asdict(row) for row in rows)


def print_markdown_table(rows: list[RolloutSummary]) -> None:
    print("| task | policy | episodes | steps | mean_reward | violations | violation_rate | mean_action_norm |")
    print("|---|---|---:|---:|---:|---:|---:|---:|")
    for row in rows:
        print(
            f"| {row.task} | {row.policy} | {row.episodes} | {row.steps} | "
            f"{row.mean_reward:.4f} | {row.constraint_violations} | "
            f"{row.violation_rate:.4f} | {row.mean_action_norm:.4f} |"
        )


def main() -> None:
    rows: list[RolloutSummary] = []
    for task in ("cartpole", "quadrotor_2d"):
        for policy_name, policy in POLICIES.items():
            rows.append(rollout(task, policy_name, policy, episodes=2, seed=2026))

    write_csv(RESULTS_DIR / "safe_control_gym_smoke.csv", rows)
    print_markdown_table(rows)
    print(f"wrote {RESULTS_DIR / 'safe_control_gym_smoke.csv'}")


if __name__ == "__main__":
    main()
