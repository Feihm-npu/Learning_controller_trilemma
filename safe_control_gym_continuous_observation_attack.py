#!/usr/bin/env python3
"""Continuous observation-FDI attacker on Safe-Control-Gym cartpole.

This is the first wiring of a continuous adaptive attacker into a standard
benchmark. At each step, a CEM attacker chooses an observation perturbation that
maximizes the gap between an LQR action computed from the attacked observation
and the action certified by the official CBF-QP filter at the true state.

The CBF filter here is intentionally strong: it certifies against the true
current state. Later lifecycle experiments should replace this oracle-state CBF
with an attacked-history plausible-set kernel and then add update-level gates.
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

from continuous_adaptive_attacker import AttackMargins, AttackWeights, cem_optimize


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


@dataclass
class AttackRunSummary:
    benchmark: str
    task: str
    controller: str
    mechanism: str
    steps: int
    budget: float
    mean_reward: float
    constraint_violation_steps: int
    constraint_violation_step_rate: float
    cbf_feasible_rate: float
    correction_rate: float
    mean_correction_norm: float
    mean_attack_norm: float
    mean_attack_linf: float
    mean_attacker_score: float


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


def build_configs(seed: int) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    task_config = dict(get_config("cartpole"))
    lqr_config = dict(get_config("lqr"))
    cbf_config = dict(get_config("cbf"))

    lqr_dir = SCG_ROOT / "examples" / "lqr" / "config_overrides" / "cartpole"
    cbf_dir = SCG_ROOT / "examples" / "cbf" / "config_overrides"
    for path in (lqr_dir / "cartpole_stab.yaml", lqr_dir / "lqr_cartpole_stab.yaml"):
        override = read_yaml(path)
        if "task_config" in override:
            deep_merge(task_config, override["task_config"])
        if "algo_config" in override:
            deep_merge(lqr_config, override["algo_config"])

    # Use the tighter CBF cartpole constraints so corrections are meaningful.
    cbf_task_override = read_yaml(cbf_dir / "cartpole_config.yaml")
    cbf_filter_override = read_yaml(cbf_dir / "cbf_config.yaml")
    deep_merge(task_config, cbf_task_override["task_config"])
    deep_merge(cbf_config, cbf_filter_override["sf_config"])

    task_config["gui"] = False
    task_config["seed"] = seed
    lqr_config["seed"] = seed
    cbf_config["seed"] = seed
    return task_config, lqr_config, cbf_config


@contextlib.contextmanager
def silence():
    with contextlib.redirect_stdout(io.StringIO()):
        yield


def certify(cbf_filter: object, obs: np.ndarray, raw_action: np.ndarray, info: dict[str, Any]) -> tuple[np.ndarray, bool, float]:
    with silence():
        certified, success = cbf_filter.certify_action(obs, raw_action, info)
    certified = np.asarray(certified, dtype=float).reshape(raw_action.shape)
    correction = float(np.linalg.norm(certified - raw_action))
    return certified, bool(success), correction


def run_attack(
    *,
    n_steps: int,
    budget: float,
    seed: int,
    use_cbf: bool,
    population: int,
    iterations: int,
) -> AttackRunSummary:
    task_config, lqr_config, cbf_config = build_configs(seed)
    env_func = partial(make, "cartpole", **task_config)
    env = env_func(gui=False)
    ctrl = make("lqr", env_func, **lqr_config)
    ctrl.reset()
    with silence():
        cbf_filter = make("cbf", env_func, **cbf_config)
        cbf_filter.reset()

    obs, info = env.reset(seed=seed)
    ctrl.reset_before_run(obs, info, env=env)

    rewards: list[float] = []
    corrections: list[float] = []
    feasible: list[bool] = []
    attack_norms: list[float] = []
    attack_linfs: list[float] = []
    scores: list[float] = []
    violations = 0

    weights = AttackWeights(stale=1.0, unsafe=0.5, freeze=2.0, stealth=0.25, magnitude=0.02)

    for step in range(n_steps):
        true_obs = np.asarray(obs, dtype=float)

        def evaluator(attack: np.ndarray) -> AttackMargins:
            attacked_obs = true_obs + attack
            raw_action = np.asarray(ctrl.select_action(attacked_obs, info), dtype=float)
            _certified, success, correction = certify(cbf_filter, true_obs, raw_action, info)
            theta_limit = 0.2
            unsafe_obs_margin = max(0.0, abs(attacked_obs[2]) - theta_limit)
            freeze_margin = 1.0 if not success else 0.0
            stealth = max(0.0, float(np.linalg.norm(attack, ord=np.inf)) - 0.8 * budget)
            magnitude = float(np.dot(attack, attack))
            return AttackMargins(
                stale=correction,
                unsafe=unsafe_obs_margin,
                freeze=freeze_margin,
                stealth_residual=stealth,
                magnitude=magnitude,
            )

        result = cem_optimize(
            evaluator,
            dim=true_obs.shape[0],
            budget=budget,
            weights=weights,
            iterations=iterations,
            population=population,
            seed=seed + step,
        )
        attack = result.attack
        attacked_obs = true_obs + attack
        raw_action = np.asarray(ctrl.select_action(attacked_obs, info), dtype=float)
        certified_action, success, correction = certify(cbf_filter, true_obs, raw_action, info)
        action = certified_action if use_cbf and success else raw_action

        obs, reward, done, info = env.step(action)
        rewards.append(float(reward))
        corrections.append(correction)
        feasible.append(success)
        attack_norms.append(float(np.linalg.norm(attack)))
        attack_linfs.append(float(np.linalg.norm(attack, ord=np.inf)))
        scores.append(result.score)
        violations += int(bool(info.get("constraint_violation", False)))

        if done:
            obs, info = env.reset()
            ctrl.reset_before_run(obs, info, env=env)

    cbf_filter.close()
    ctrl.close()
    env.close()

    correction_array = np.asarray(corrections, dtype=float)
    return AttackRunSummary(
        benchmark="safe_control_gym",
        task="cartpole",
        controller="lqr",
        mechanism="oracle_cbf_action_filter" if use_cbf else "attacked_lqr",
        steps=n_steps,
        budget=budget,
        mean_reward=float(np.mean(rewards)) if rewards else 0.0,
        constraint_violation_steps=violations,
        constraint_violation_step_rate=violations / n_steps if n_steps else 0.0,
        cbf_feasible_rate=float(np.mean(feasible)) if feasible else 0.0,
        correction_rate=float(np.mean(correction_array > 1e-8)) if correction_array.size else 0.0,
        mean_correction_norm=float(np.mean(correction_array)) if correction_array.size else 0.0,
        mean_attack_norm=float(np.mean(attack_norms)) if attack_norms else 0.0,
        mean_attack_linf=float(np.mean(attack_linfs)) if attack_linfs else 0.0,
        mean_attacker_score=float(np.mean(scores)) if scores else 0.0,
    )


def write_csv(path: Path, rows: list[AttackRunSummary]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(asdict(rows[0]).keys()))
        writer.writeheader()
        writer.writerows(asdict(row) for row in rows)


def print_markdown_table(rows: list[AttackRunSummary]) -> None:
    print("| mechanism | steps | budget | mean_reward | violations | violation_rate | feasible_rate | correction_rate | mean_attack_linf |")
    print("|---|---:|---:|---:|---:|---:|---:|---:|---:|")
    for row in rows:
        print(
            f"| {row.mechanism} | {row.steps} | {row.budget:.3f} | "
            f"{row.mean_reward:.4f} | {row.constraint_violation_steps} | "
            f"{row.constraint_violation_step_rate:.4f} | {row.cbf_feasible_rate:.4f} | "
            f"{row.correction_rate:.4f} | {row.mean_attack_linf:.4f} |"
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run continuous observation-FDI attack on Safe-Control-Gym cartpole.")
    parser.add_argument("--n-steps", type=int, default=20)
    parser.add_argument("--budget", type=float, default=0.12)
    parser.add_argument("--seed", type=int, default=2026)
    parser.add_argument("--population", type=int, default=32)
    parser.add_argument("--iterations", type=int, default=5)
    parser.add_argument("--out", type=Path, default=RESULTS_DIR / "safe_control_gym_continuous_observation_attack.csv")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    rows = [
        run_attack(
            n_steps=args.n_steps,
            budget=args.budget,
            seed=args.seed,
            use_cbf=False,
            population=args.population,
            iterations=args.iterations,
        ),
        run_attack(
            n_steps=args.n_steps,
            budget=args.budget,
            seed=args.seed,
            use_cbf=True,
            population=args.population,
            iterations=args.iterations,
        ),
    ]
    write_csv(args.out, rows)
    print_markdown_table(rows)
    print(f"wrote {args.out}")


if __name__ == "__main__":
    main()
