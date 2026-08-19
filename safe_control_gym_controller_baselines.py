#!/usr/bin/env python3
"""Run official Safe-Control-Gym controller baselines.

This adapter uses the upstream Safe-Control-Gym controller implementations and
their example YAML overrides, then writes compact CSV summaries for this
project. It is the bridge from our minimal lifecycle artifacts to standard
control baselines such as LQR and linear MPC.
"""

from __future__ import annotations

import argparse
import contextlib
import csv
import io
import os
from dataclasses import asdict, dataclass
from functools import partial
from pathlib import Path
from typing import Any

import numpy as np
import yaml


ROOT = Path(__file__).resolve().parent
SCG_ROOT = ROOT / "external" / "safe-control-gym"
RESULTS_DIR = ROOT / "results"


def configure_matplotlib() -> None:
    cache_dir = Path("/tmp/matplotlib-lifecycle-gate")
    cache_dir.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("MPLCONFIGDIR", str(cache_dir))


configure_matplotlib()

import safe_control_gym  # noqa: F401
from safe_control_gym.utils.registration import get_config, make


@dataclass(frozen=True)
class BaselineScenario:
    task_key: str
    scg_task: str
    folder: str
    algo: str
    config_family: str


@dataclass
class BaselineSummary:
    benchmark: str
    task: str
    controller: str
    config_family: str
    requested_steps: int
    episodes: int
    recorded_steps: int
    mean_reward: float
    total_reward: float
    constraint_violation_episodes: int
    constraint_violation_steps: int
    constraint_violation_step_rate: float
    mean_action_norm: float
    mean_state_norm: float


SCENARIOS: tuple[BaselineScenario, ...] = (
    BaselineScenario("cartpole", "cartpole", "cartpole", "lqr", "lqr"),
    BaselineScenario("quadrotor_2d", "quadrotor", "quadrotor_2D", "lqr", "lqr"),
    BaselineScenario("cartpole", "cartpole", "cartpole", "linear_mpc", "mpc"),
    BaselineScenario("quadrotor_2d", "quadrotor", "quadrotor_2D", "linear_mpc", "mpc"),
)


def deep_merge(base: dict[str, Any], updates: dict[str, Any]) -> dict[str, Any]:
    for key, value in updates.items():
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            deep_merge(base[key], value)
        else:
            base[key] = value
    return base


def read_yaml(path: Path) -> dict[str, Any]:
    with path.open() as f:
        return yaml.safe_load(f) or {}


def override_paths(scenario: BaselineScenario) -> tuple[Path, Path]:
    base = SCG_ROOT / "examples" / scenario.config_family / "config_overrides" / scenario.folder
    task_override = base / f"{scenario.folder}_stab.yaml"
    algo_override = base / f"{scenario.algo}_{scenario.folder}_stab.yaml"
    return task_override, algo_override


def build_configs(scenario: BaselineScenario) -> tuple[dict[str, Any], dict[str, Any]]:
    task_config = dict(get_config(scenario.scg_task))
    algo_config = dict(get_config(scenario.algo))
    for path in override_paths(scenario):
        override = read_yaml(path)
        if "task_config" in override:
            deep_merge(task_config, override["task_config"])
        if "algo_config" in override:
            deep_merge(algo_config, override["algo_config"])
    task_config["gui"] = False
    return task_config, algo_config


def flatten_episodes(values: list[np.ndarray]) -> np.ndarray:
    if not values:
        return np.array([])
    arrays = [np.asarray(value) for value in values if np.asarray(value).size > 0]
    if not arrays:
        return np.array([])
    return np.concatenate(arrays, axis=0)


@contextlib.contextmanager
def maybe_silence(enabled: bool):
    if not enabled:
        yield
        return
    with contextlib.redirect_stdout(io.StringIO()):
        yield


def run_scenario(scenario: BaselineScenario, n_steps: int, seed: int, silence_solver: bool) -> BaselineSummary:
    task_config, algo_config = build_configs(scenario)
    task_config["seed"] = seed
    algo_config["seed"] = seed

    env_func = partial(make, scenario.scg_task, **task_config)
    env = env_func(gui=False)
    ctrl = make(scenario.algo, env_func, **algo_config)
    with maybe_silence(silence_solver):
        ctrl.reset()

    rewards: list[float] = []
    actions: list[np.ndarray] = []
    states: list[np.ndarray] = []
    violation_steps = 0
    violation_episodes = 0
    episodes = 1
    episode_had_violation = False

    obs, info = env.reset(seed=seed)
    ctrl.reset_before_run(obs, info, env=env)
    for _ in range(n_steps):
        with maybe_silence(silence_solver):
            action = ctrl.select_action(obs, info)
        obs, reward, done, info = env.step(action)
        rewards.append(float(reward))
        actions.append(np.asarray(action, dtype=float))
        states.append(np.asarray(env.state, dtype=float))
        violated = bool(info.get("constraint_violation", False))
        violation_steps += int(violated)
        episode_had_violation = episode_had_violation or violated
        if done:
            violation_episodes += int(episode_had_violation)
            episodes += 1
            episode_had_violation = False
            obs, info = env.reset()
            ctrl.reset_before_run(obs, info, env=env)

    violation_episodes += int(episode_had_violation)
    ctrl.close()
    env.close()

    rewards_arr = np.asarray(rewards, dtype=float)
    actions_arr = np.asarray(actions, dtype=float)
    states_arr = np.asarray(states, dtype=float)
    recorded_steps = int(rewards_arr.shape[0])
    return BaselineSummary(
        benchmark="safe_control_gym",
        task=scenario.task_key,
        controller=scenario.algo,
        config_family=scenario.config_family,
        requested_steps=n_steps,
        episodes=episodes,
        recorded_steps=recorded_steps,
        mean_reward=float(np.mean(rewards_arr)) if rewards_arr.size else 0.0,
        total_reward=float(np.sum(rewards_arr)) if rewards_arr.size else 0.0,
        constraint_violation_episodes=violation_episodes,
        constraint_violation_steps=violation_steps,
        constraint_violation_step_rate=violation_steps / recorded_steps if recorded_steps else 0.0,
        mean_action_norm=float(np.mean(np.linalg.norm(actions_arr, axis=1))) if actions_arr.size else 0.0,
        mean_state_norm=float(np.mean(np.linalg.norm(states_arr, axis=1))) if states_arr.size else 0.0,
    )


def write_csv(path: Path, rows: list[BaselineSummary]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(asdict(rows[0]).keys()))
        writer.writeheader()
        writer.writerows(asdict(row) for row in rows)


def print_markdown_table(rows: list[BaselineSummary]) -> None:
    print("| task | controller | steps | mean_reward | violation_steps | violation_rate | mean_action_norm |")
    print("|---|---|---:|---:|---:|---:|---:|")
    for row in rows:
        print(
            f"| {row.task} | {row.controller} | {row.recorded_steps} | "
            f"{row.mean_reward:.4f} | {row.constraint_violation_steps} | "
            f"{row.constraint_violation_step_rate:.4f} | {row.mean_action_norm:.4f} |"
        )


def selected_scenarios(tasks: set[str], controllers: set[str]) -> list[BaselineScenario]:
    return [
        scenario
        for scenario in SCENARIOS
        if scenario.task_key in tasks and scenario.algo in controllers
    ]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Safe-Control-Gym official baseline smoke tests.")
    parser.add_argument("--tasks", nargs="+", default=["cartpole", "quadrotor_2d"], choices=["cartpole", "quadrotor_2d"])
    parser.add_argument("--controllers", nargs="+", default=["lqr", "linear_mpc"], choices=["lqr", "linear_mpc"])
    parser.add_argument("--n-steps", type=int, default=40)
    parser.add_argument("--seed", type=int, default=2026)
    parser.add_argument("--show-solver-output", action="store_true")
    parser.add_argument("--out", type=Path, default=RESULTS_DIR / "safe_control_gym_controller_baselines.csv")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    rows = [
        run_scenario(
            scenario,
            n_steps=args.n_steps,
            seed=args.seed,
            silence_solver=not args.show_solver_output,
        )
        for scenario in selected_scenarios(set(args.tasks), set(args.controllers))
    ]
    write_csv(args.out, rows)
    print_markdown_table(rows)
    print(f"wrote {args.out}")


if __name__ == "__main__":
    main()
