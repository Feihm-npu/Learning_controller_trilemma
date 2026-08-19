#!/usr/bin/env python3
"""Official Safe-Control-Gym linear-MPSC baseline for poisoned snapshots.

This adapter avoids the upstream ``BaseExperiment`` wrapper, which is
incompatible with the newer Gymnasium wrapper installed in this workspace. It
does not modify MPSC semantics: it instantiates the registered ``linear_mpsc``
filter, loads the upstream pretrained quadrotor RPI artifact, and calls
``certify_action`` on every proposed action.
"""

from __future__ import annotations

import argparse
import contextlib
import csv
import io
from dataclasses import asdict, dataclass
from functools import partial
from pathlib import Path
from statistics import median
from typing import Iterable, Sequence

import numpy as np

from safe_control_gym.utils.registration import make

import safe_control_gym_quadrotor_lifecycle_scaffold as quad


ROOT = Path(__file__).resolve().parent
RESULTS_DIR = ROOT / "results"
MODEL_PATH = (
    ROOT
    / "external"
    / "safe-control-gym"
    / "examples"
    / "mpsc"
    / "models"
    / "linear_mpsc_quadrotor_2D.pkl"
)
MPSC_CONFIG_PATH = (
    ROOT
    / "external"
    / "safe-control-gym"
    / "examples"
    / "mpsc"
    / "config_overrides"
    / "quadrotor_2D"
    / "linear_mpsc_quadrotor_2D.yaml"
)


@dataclass(frozen=True)
class AuditState:
    source_seed: int
    source_index: int
    state: np.ndarray


@dataclass
class MPSCRollout:
    learner_seed: int
    source_seed: int
    source_index: int
    steps_executed: int
    violation_steps: int
    first_violation_step: int | None
    interventions: int
    infeasible_steps: int
    mean_correction: float
    max_correction: float
    mean_reward: float


@dataclass
class MPSCSummary:
    learner_seeds: int
    deployment_rollouts: int
    violating_rollouts: int
    deployment_violation_rate: float
    median_first_violation_step: float | None
    interventions: int
    infeasible_steps: int
    mean_correction: float
    max_correction: float
    mean_reward: float


def silence_stdout():
    return contextlib.redirect_stdout(io.StringIO())


def read_poisoned_snapshots(path: Path) -> dict[int, np.ndarray]:
    latest: dict[int, tuple[int, np.ndarray]] = {}
    with path.open(newline="") as input_file:
        for row in csv.DictReader(input_file):
            if row["mechanism"] != "poisoned_action_only_snapshot":
                continue
            seed = int(row["seed"])
            batch = int(row["batch"])
            snapshot = np.asarray(
                [
                    [float(row["w00"]), float(row["w01"])],
                    [float(row["w10"]), float(row["w11"])],
                ]
            )
            if seed not in latest or batch > latest[seed][0]:
                latest[seed] = (batch, snapshot)
    return {seed: value[1] for seed, value in latest.items()}


def read_audit_states(path: Path) -> list[AuditState]:
    unique: dict[tuple[int, int], AuditState] = {}
    with path.open(newline="") as input_file:
        for row in csv.DictReader(input_file):
            if row["mechanism"] != "poisoned_action_only_snapshot":
                continue
            key = (int(row["source_seed"]), int(row["source_index"]))
            unique.setdefault(
                key,
                AuditState(
                    source_seed=key[0],
                    source_index=key[1],
                    state=np.asarray(
                        [
                            float(row["init_x"]),
                            float(row["init_x_dot"]),
                            float(row["init_z"]),
                            float(row["init_z_dot"]),
                            float(row["init_theta"]),
                            float(row["init_theta_dot"]),
                        ]
                    ),
                ),
            )
    return list(unique.values())


def spread_states(states: Sequence[AuditState], count: int) -> list[AuditState]:
    if count >= len(states):
        return list(states)
    indices = np.linspace(0, len(states) - 1, count, dtype=int)
    return [states[int(index)] for index in indices]


def build_mpsc(bundle: quad.DynamicsBundle):
    env_func = partial(make, "quadrotor", **bundle.task_config)
    config = quad.read_yaml(MPSC_CONFIG_PATH)["sf_config"]
    with silence_stdout():
        safety_filter = make("linear_mpsc", env_func, **config)
        safety_filter.load(MODEL_PATH)
    return safety_filter


def run_audit(
    learner_seed: int,
    snapshot: np.ndarray,
    bundle: quad.DynamicsBundle,
    states: Sequence[AuditState],
    *,
    steps: int,
) -> list[MPSCRollout]:
    env = make("quadrotor", **bundle.task_config)
    safety_filter = build_mpsc(bundle)
    rows: list[MPSCRollout] = []
    for rollout, audit_state in enumerate(states):
        quad.set_quadrotor_initial_state(env, audit_state.state)
        observation, info = env.reset(seed=learner_seed + rollout)
        safety_filter.reset_before_run(env=env)
        first_violation: int | None = None
        violation_steps = 0
        interventions = 0
        infeasible_steps = 0
        corrections: list[float] = []
        rewards: list[float] = []
        executed = 0
        for step in range(steps):
            raw_action = quad.policy_actions(
                bundle,
                np.asarray(observation, dtype=float).reshape(1, -1),
                snapshot,
            )[0]
            with silence_stdout():
                certified_action, success = safety_filter.certify_action(
                    np.asarray(observation, dtype=float), raw_action, info
                )
            certified_action = np.clip(
                np.asarray(certified_action, dtype=float),
                bundle.action_low,
                bundle.action_high,
            )
            correction = float(np.linalg.norm(certified_action - raw_action))
            corrections.append(correction)
            interventions += int(correction > 1e-9)
            infeasible_steps += int(not success)
            observation, reward, _done, info = env.step(certified_action)
            rewards.append(float(reward))
            executed += 1
            violated = bool(info.get("constraint_violation", False)) or bool(
                quad.state_margins(np.asarray(env.state, dtype=float))[0] > 1e-9
            )
            violation_steps += int(violated)
            if violated:
                first_violation = step
                break
        rows.append(
            MPSCRollout(
                learner_seed=learner_seed,
                source_seed=audit_state.source_seed,
                source_index=audit_state.source_index,
                steps_executed=executed,
                violation_steps=violation_steps,
                first_violation_step=first_violation,
                interventions=interventions,
                infeasible_steps=infeasible_steps,
                mean_correction=float(np.mean(corrections)),
                max_correction=float(np.max(corrections)),
                mean_reward=float(np.mean(rewards)),
            )
        )
    safety_filter.close()
    env.close()
    return rows


def summarize(rows: Sequence[MPSCRollout]) -> MPSCSummary:
    first_steps = [
        int(row.first_violation_step)
        for row in rows
        if row.first_violation_step is not None
    ]
    return MPSCSummary(
        learner_seeds=len({row.learner_seed for row in rows}),
        deployment_rollouts=len(rows),
        violating_rollouts=len(first_steps),
        deployment_violation_rate=len(first_steps) / len(rows),
        median_first_violation_step=(
            float(median(first_steps)) if first_steps else None
        ),
        interventions=sum(row.interventions for row in rows),
        infeasible_steps=sum(row.infeasible_steps for row in rows),
        mean_correction=float(np.mean([row.mean_correction for row in rows])),
        max_correction=float(np.max([row.max_correction for row in rows])),
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
    parser.add_argument("--steps", type=int, default=100)
    parser.add_argument("--rollouts-per-seed", type=int, default=4)
    parser.add_argument(
        "--traces",
        type=Path,
        default=RESULTS_DIR / "safe_control_gym_quadrotor_reinforce_reward_poisoning_sweep_traces.csv",
    )
    parser.add_argument(
        "--sweep-rollouts",
        type=Path,
        default=RESULTS_DIR / "safe_control_gym_quadrotor_reinforce_reward_poisoning_sweep_rollouts.csv",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=RESULTS_DIR / "safe_control_gym_quadrotor_mpsc_baseline.csv",
    )
    parser.add_argument(
        "--summary-out",
        type=Path,
        default=RESULTS_DIR / "safe_control_gym_quadrotor_mpsc_baseline_summary.csv",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    snapshots = read_poisoned_snapshots(args.traces)
    audit_states = spread_states(
        read_audit_states(args.sweep_rollouts), args.rollouts_per_seed
    )
    rows: list[MPSCRollout] = []
    for seed, snapshot in sorted(snapshots.items()):
        print(f"MPSC learner_seed={seed}: {len(audit_states)} rollouts", flush=True)
        bundle = quad.build_dynamics(seed)
        seed_rows = run_audit(
            seed, snapshot, bundle, audit_states, steps=args.steps
        )
        rows.extend(seed_rows)
        print(
            f"MPSC learner_seed={seed}: violations="
            f"{sum(row.first_violation_step is not None for row in seed_rows)}/"
            f"{len(seed_rows)} infeasible_steps="
            f"{sum(row.infeasible_steps for row in seed_rows)}",
            flush=True,
        )
    summary = summarize(rows)
    write_csv(args.out, rows)
    write_csv(args.summary_out, [summary])
    print(
        f"MPSC aggregate violations={summary.violating_rollouts}/"
        f"{summary.deployment_rollouts} interventions={summary.interventions} "
        f"infeasible_steps={summary.infeasible_steps} "
        f"mean_reward={summary.mean_reward:.4f}",
        flush=True,
    )
    print(f"wrote {args.summary_out}", flush=True)


if __name__ == "__main__":
    main()
