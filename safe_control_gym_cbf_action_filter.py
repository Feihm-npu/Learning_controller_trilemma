#!/usr/bin/env python3
"""Official Safe-Control-Gym CBF action-filter baseline on cartpole.

This runner uses the upstream CBF-QP safety filter directly. It compares an
uncertified action policy against the same policy wrapped by the CBF filter.
This is the standard action-only safety baseline that LifecycleGate must beat at
the update-certification level.
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
from typing import Any, Callable

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


Policy = Callable[[object, np.ndarray], np.ndarray]


@dataclass
class CBFSummary:
    benchmark: str
    task: str
    policy: str
    mechanism: str
    steps: int
    mean_reward: float
    constraint_violation_steps: int
    constraint_violation_step_rate: float
    cbf_feasible_rate: float
    correction_rate: float
    mean_correction_norm: float
    mean_action_norm: float


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


def build_configs() -> tuple[dict[str, Any], dict[str, Any]]:
    task_config = dict(get_config("cartpole"))
    sf_config = dict(get_config("cbf"))
    cbf_dir = SCG_ROOT / "examples" / "cbf" / "config_overrides"
    override = read_yaml(cbf_dir / "cartpole_config.yaml")
    sf_override = read_yaml(cbf_dir / "cbf_config.yaml")
    deep_merge(task_config, override["task_config"])
    deep_merge(sf_config, sf_override["sf_config"])
    task_config["gui"] = False
    return task_config, sf_config


def max_push_policy(env: object, _obs: np.ndarray) -> np.ndarray:
    return np.asarray(env.action_space.high, dtype=float)


def theta_push_policy(env: object, obs: np.ndarray) -> np.ndarray:
    # Push in the direction that increases the current pole-angle magnitude.
    action = np.sign(obs[2]) * np.asarray(env.action_space.high, dtype=float)
    if np.allclose(action, 0.0):
        action = np.asarray(env.action_space.high, dtype=float)
    return action


POLICIES: dict[str, Policy] = {
    "max_push": max_push_policy,
    "theta_push": theta_push_policy,
}


@contextlib.contextmanager
def silence():
    with contextlib.redirect_stdout(io.StringIO()):
        yield


def run_rollout(policy_name: str, policy: Policy, n_steps: int, seed: int, use_cbf: bool) -> CBFSummary:
    task_config, sf_config = build_configs()
    task_config["seed"] = seed
    sf_config["seed"] = seed
    env_func = partial(make, "cartpole", **task_config)
    env = env_func(gui=False)
    safety_filter = None
    if use_cbf:
        with silence():
            safety_filter = make("cbf", env_func, **sf_config)
            safety_filter.reset()

    obs, info = env.reset(seed=seed)
    rewards: list[float] = []
    action_norms: list[float] = []
    corrections: list[float] = []
    feasible: list[bool] = []
    violations = 0

    for _ in range(n_steps):
        raw_action = policy(env, np.asarray(obs, dtype=float))
        action = raw_action
        if safety_filter is not None:
            with silence():
                certified_action, success = safety_filter.certify_action(np.asarray(obs, dtype=float), raw_action, info)
            feasible.append(bool(success))
            certified_action = np.asarray(certified_action, dtype=float).reshape(raw_action.shape)
            corrections.append(float(np.linalg.norm(certified_action - raw_action)))
            if success:
                action = certified_action

        obs, reward, done, info = env.step(action)
        rewards.append(float(reward))
        action_norms.append(float(np.linalg.norm(action)))
        violations += int(bool(info.get("constraint_violation", False)))
        if done:
            obs, info = env.reset()

    if safety_filter is not None:
        safety_filter.close()
    env.close()

    correction_array = np.asarray(corrections, dtype=float)
    return CBFSummary(
        benchmark="safe_control_gym",
        task="cartpole",
        policy=policy_name,
        mechanism="cbf_action_filter" if use_cbf else "uncertified_action_policy",
        steps=n_steps,
        mean_reward=float(np.mean(rewards)) if rewards else 0.0,
        constraint_violation_steps=violations,
        constraint_violation_step_rate=violations / n_steps if n_steps else 0.0,
        cbf_feasible_rate=float(np.mean(feasible)) if feasible else 0.0,
        correction_rate=float(np.mean(correction_array > 1e-8)) if correction_array.size else 0.0,
        mean_correction_norm=float(np.mean(correction_array)) if correction_array.size else 0.0,
        mean_action_norm=float(np.mean(action_norms)) if action_norms else 0.0,
    )


def write_csv(path: Path, rows: list[CBFSummary]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(asdict(rows[0]).keys()))
        writer.writeheader()
        writer.writerows(asdict(row) for row in rows)


def print_markdown_table(rows: list[CBFSummary]) -> None:
    print("| policy | mechanism | steps | mean_reward | violations | violation_rate | feasible_rate | correction_rate | mean_correction |")
    print("|---|---|---:|---:|---:|---:|---:|---:|---:|")
    for row in rows:
        print(
            f"| {row.policy} | {row.mechanism} | {row.steps} | {row.mean_reward:.4f} | "
            f"{row.constraint_violation_steps} | {row.constraint_violation_step_rate:.4f} | "
            f"{row.cbf_feasible_rate:.4f} | {row.correction_rate:.4f} | "
            f"{row.mean_correction_norm:.4f} |"
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Safe-Control-Gym CBF action-filter baseline.")
    parser.add_argument("--n-steps", type=int, default=50)
    parser.add_argument("--seed", type=int, default=2026)
    parser.add_argument("--out", type=Path, default=RESULTS_DIR / "safe_control_gym_cbf_action_filter.csv")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    rows: list[CBFSummary] = []
    for policy_name, policy in POLICIES.items():
        rows.append(run_rollout(policy_name, policy, args.n_steps, args.seed, use_cbf=False))
        rows.append(run_rollout(policy_name, policy, args.n_steps, args.seed, use_cbf=True))
    write_csv(args.out, rows)
    print_markdown_table(rows)
    print(f"wrote {args.out}")


if __name__ == "__main__":
    main()
