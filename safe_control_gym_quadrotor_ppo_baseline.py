#!/usr/bin/env python3
"""Evaluate upstream pretrained PPO on the quadrotor held-out envelope."""

from __future__ import annotations

import argparse
import csv
from dataclasses import asdict, dataclass
from functools import partial
from pathlib import Path
from statistics import median
from typing import Iterable, Sequence

import numpy as np

from safe_control_gym.utils.registration import get_config, make

import safe_control_gym_quadrotor_lifecycle_scaffold as quad
from safe_control_gym_quadrotor_mpsc_baseline import AuditState, read_audit_states


ROOT = Path(__file__).resolve().parent
RESULTS_DIR = ROOT / "results"
PPO_MODEL = (
    ROOT
    / "external"
    / "safe-control-gym"
    / "examples"
    / "mpsc"
    / "models"
    / "ppo_model_quadrotor_2D_stab.pt"
)
TASK_CONFIG = (
    ROOT
    / "external"
    / "safe-control-gym"
    / "examples"
    / "mpsc"
    / "config_overrides"
    / "quadrotor_2D"
    / "quadrotor_2D_stab.yaml"
)
PPO_CONFIG = (
    ROOT
    / "external"
    / "safe-control-gym"
    / "examples"
    / "mpsc"
    / "config_overrides"
    / "quadrotor_2D"
    / "ppo_quadrotor_2D.yaml"
)


@dataclass
class PPORollout:
    policy: str
    policy_seed: int
    source_seed: int
    source_index: int
    steps_executed: int
    violation_steps: int
    first_violation_step: int | None
    mean_reward: float


@dataclass
class PPOSummary:
    policy: str
    policy_seeds: int
    deployment_rollouts: int
    violating_rollouts: int
    deployment_violation_rate: float
    median_first_violation_step: float | None
    mean_reward: float


def build_configs(seed: int) -> tuple[dict, dict]:
    task = dict(get_config("quadrotor"))
    algo = dict(get_config("ppo"))
    quad.deep_merge(task, quad.read_yaml(TASK_CONFIG)["task_config"])
    quad.deep_merge(algo, quad.read_yaml(PPO_CONFIG)["algo_config"])
    task["seed"] = seed
    task["gui"] = False
    task["randomized_init"] = False
    task["done_on_violation"] = False
    task["done_on_out_of_bound"] = False
    algo["seed"] = seed
    return task, algo


def build_ppo(seed: int):
    task, algo = build_configs(seed)
    env_func = partial(make, "quadrotor", **task)
    controller = make("ppo", env_func, **algo, training=False)
    controller.load(PPO_MODEL)
    controller.reset()
    return task, controller


def spread_states(states: Sequence[AuditState], count: int) -> list[AuditState]:
    if count >= len(states):
        return list(states)
    indices = np.linspace(0, len(states) - 1, count, dtype=int)
    return [states[int(index)] for index in indices]


def run_policy(
    seed: int,
    states: Sequence[AuditState],
    *,
    steps: int,
) -> list[PPORollout]:
    task, controller = build_ppo(seed)
    env = make("quadrotor", **task)
    rows: list[PPORollout] = []
    for rollout, audit_state in enumerate(states):
        quad.set_quadrotor_initial_state(env, audit_state.state)
        observation, info = env.reset(seed=seed + rollout)
        first_violation: int | None = None
        rewards: list[float] = []
        executed = 0
        for step in range(steps):
            normalized_obs = controller.obs_normalizer(observation)
            action = np.clip(
                np.asarray(
                    controller.select_action(normalized_obs, info), dtype=float
                ),
                env.action_space.low,
                env.action_space.high,
            )
            observation, reward, _done, info = env.step(action)
            rewards.append(float(reward))
            executed += 1
            violated = bool(info.get("constraint_violation", False)) or bool(
                quad.state_margins(np.asarray(env.state, dtype=float))[0] > 1e-9
            )
            if violated:
                first_violation = step
                break
        rows.append(
            PPORollout(
                policy="pretrained_ppo",
                policy_seed=seed,
                source_seed=audit_state.source_seed,
                source_index=audit_state.source_index,
                steps_executed=executed,
                violation_steps=int(first_violation is not None),
                first_violation_step=first_violation,
                mean_reward=float(np.mean(rewards)),
            )
        )
    controller.close()
    env.close()
    return rows


def run_target_policy(
    seed: int,
    states: Sequence[AuditState],
    *,
    steps: int,
) -> list[PPORollout]:
    task, _algo = build_configs(seed)
    env = make("quadrotor", **task)
    bundle = quad.build_dynamics(seed)
    import safe_control_gym_quadrotor_reinforce_reward_poisoning as residual

    target, _viable = residual.choose_target(
        bundle, seed=2040, deployment_steps=steps, minimum_delay=8
    )
    rows: list[PPORollout] = []
    for rollout, audit_state in enumerate(states):
        quad.set_quadrotor_initial_state(env, audit_state.state)
        observation, info = env.reset(seed=seed + rollout)
        first_violation: int | None = None
        rewards: list[float] = []
        executed = 0
        for step in range(steps):
            physical = quad.policy_actions(
                bundle,
                np.asarray(env.state, dtype=float).reshape(1, -1),
                target,
            )[0]
            normalized = np.clip(
                (physical / float(env.hover_thrust) - 1.0)
                / float(env.norm_act_scale),
                -1.0,
                1.0,
            )
            observation, reward, _done, info = env.step(normalized)
            rewards.append(float(reward))
            executed += 1
            violated = bool(info.get("constraint_violation", False)) or bool(
                quad.state_margins(np.asarray(env.state, dtype=float))[0] > 1e-9
            )
            if violated:
                first_violation = step
                break
        rows.append(
            PPORollout(
                policy="normalized_malicious_target",
                policy_seed=seed,
                source_seed=audit_state.source_seed,
                source_index=audit_state.source_index,
                steps_executed=executed,
                violation_steps=int(first_violation is not None),
                first_violation_step=first_violation,
                mean_reward=float(np.mean(rewards)),
            )
        )
    env.close()
    return rows


def summarize(rows: Sequence[PPORollout]) -> PPOSummary:
    first_steps = [
        int(row.first_violation_step)
        for row in rows
        if row.first_violation_step is not None
    ]
    return PPOSummary(
        policy=rows[0].policy,
        policy_seeds=len({row.policy_seed for row in rows}),
        deployment_rollouts=len(rows),
        violating_rollouts=len(first_steps),
        deployment_violation_rate=len(first_steps) / len(rows),
        median_first_violation_step=(
            float(median(first_steps)) if first_steps else None
        ),
        mean_reward=float(np.mean([row.mean_reward for row in rows])),
    )


def write_csv(path: Path, rows: Iterable[object]) -> None:
    dictionaries = [asdict(row) for row in rows]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=list(dictionaries[0]))
        writer.writeheader()
        writer.writerows(dictionaries)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--policy-seeds", nargs="+", type=int, default=[2040, 2041, 2042])
    parser.add_argument("--steps", type=int, default=100)
    parser.add_argument("--rollouts", type=int, default=24)
    parser.add_argument("--include-target", action="store_true")
    parser.add_argument(
        "--sweep-rollouts",
        type=Path,
        default=RESULTS_DIR / "safe_control_gym_quadrotor_reinforce_reward_poisoning_sweep_rollouts.csv",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=RESULTS_DIR / "safe_control_gym_quadrotor_ppo_baseline.csv",
    )
    parser.add_argument(
        "--summary-out",
        type=Path,
        default=RESULTS_DIR / "safe_control_gym_quadrotor_ppo_baseline_summary.csv",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    states = spread_states(read_audit_states(args.sweep_rollouts), args.rollouts)
    pretrained_rows = [
        row
        for seed in args.policy_seeds
        for row in run_policy(seed, states, steps=args.steps)
    ]
    rows = list(pretrained_rows)
    summaries = [summarize(pretrained_rows)]
    if args.include_target:
        target_rows = [
            row
            for seed in args.policy_seeds
            for row in run_target_policy(seed, states, steps=args.steps)
        ]
        rows.extend(target_rows)
        summaries.append(summarize(target_rows))
    write_csv(args.out, rows)
    write_csv(args.summary_out, summaries)
    for summary in summaries:
        print(
            f"{summary.policy} violations={summary.violating_rollouts}/"
            f"{summary.deployment_rollouts} median_first="
            f"{summary.median_first_violation_step} reward={summary.mean_reward:.4f}"
        )
    print(f"wrote {args.summary_out}")


if __name__ == "__main__":
    main()
