#!/usr/bin/env python3
"""Poison-dose and held-out-state sweep for the delayed-trigger benchmark."""

from __future__ import annotations

import argparse
import csv
from dataclasses import asdict, dataclass
from functools import partial
from pathlib import Path
from statistics import median

import matplotlib.pyplot as plt
import numpy as np

from safe_control_gym.utils.registration import make

import safe_control_gym_delayed_trigger_attack as delayed
import safe_control_gym_plausible_set_lifecycle_gate as gate


ROOT = Path(__file__).resolve().parent
RESULTS_DIR = ROOT / "results"
FIGURES_DIR = ROOT / "paper_latex" / "figures"
MECHANISMS = ("action_only", "commit_gate", "always_freeze")


@dataclass
class SweepSummary:
    poison_steps: int
    mechanism: str
    evaluation_seed: int
    candidate_rollouts: int
    admitted_rollouts: int
    certificate_candidates: int
    certificate_admitted: int
    admission_guard_margin: float
    commit_guard_margin: float
    pending_gain: float
    pending_bias: float
    final_gain: float
    final_bias: float
    retained_update_fraction: float
    violating_rollouts: int
    violation_rate: float
    median_first_violation_step: float | None
    mean_reward: float


@dataclass
class SweepRollout:
    poison_steps: int
    mechanism: str
    evaluation_seed: int
    final_gain: float
    final_bias: float
    init_x: float
    init_x_dot: float
    init_theta: float
    init_theta_dot: float
    first_violation_step: int | None
    violation_steps: int
    mean_reward: float


def parse_ints(value: str) -> list[int]:
    return [int(item.strip()) for item in value.split(",") if item.strip()]


def heldout_candidates(seed: int, count: int) -> list[np.ndarray]:
    """Sample clean states independently from the commit certificate seed."""
    rng = np.random.default_rng(seed)
    states = rng.uniform(
        low=np.asarray([-0.25, -0.50, -0.15, -1.0]),
        high=np.asarray([0.25, 0.50, 0.15, 1.0]),
        size=(count, 4),
    )
    return [row.copy() for row in states]


def write_rows(path: Path, rows: list[object]) -> None:
    if not rows:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    dictionaries = [asdict(row) for row in rows]
    with path.open("w", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=list(dictionaries[0].keys()))
        writer.writeheader()
        writer.writerows(dictionaries)


def plot_summary(rows: list[SweepSummary], path: Path) -> None:
    labels = {
        "action_only": "Action-only snapshot",
        "commit_gate": "Commit LifecycleGate",
        "always_freeze": "Always freeze",
    }
    colors = {
        "action_only": "#d1495b",
        "commit_gate": "#00798c",
        "always_freeze": "#555555",
    }
    markers = {"action_only": "o", "commit_gate": "s", "always_freeze": "^"}
    doses = sorted({row.poison_steps for row in rows})
    fig, axes = plt.subplots(1, 2, figsize=(7.2, 2.75), constrained_layout=True)

    for mechanism in MECHANISMS:
        means: list[float] = []
        lows: list[float] = []
        highs: list[float] = []
        retention: list[float] = []
        for dose in doses:
            selected = [
                row
                for row in rows
                if row.mechanism == mechanism and row.poison_steps == dose
            ]
            rates = np.asarray([row.violation_rate for row in selected], dtype=float)
            means.append(float(np.mean(rates)))
            lows.append(float(np.min(rates)))
            highs.append(float(np.max(rates)))
            retention.append(float(selected[0].retained_update_fraction))
        means_array = np.asarray(means)
        axes[0].plot(
            doses,
            means_array,
            color=colors[mechanism],
            marker=markers[mechanism],
            linewidth=1.8,
            markersize=4.5,
            label=labels[mechanism],
        )
        axes[0].fill_between(
            doses,
            lows,
            highs,
            color=colors[mechanism],
            alpha=0.12,
            linewidth=0,
        )
        axes[1].plot(
            doses,
            retention,
            color=colors[mechanism],
            marker=markers[mechanism],
            linewidth=1.8,
            markersize=4.5,
            label=labels[mechanism],
        )

    axes[0].set_title("Delayed physical failure")
    axes[0].set_xlabel("Poison updates")
    axes[0].set_ylabel("Held-out violation rate")
    axes[0].set_ylim(-0.03, 1.03)
    axes[0].grid(alpha=0.25, linewidth=0.6)
    axes[1].set_title("Update availability under attack")
    axes[1].set_xlabel("Poison updates")
    axes[1].set_ylabel("Committed / pending displacement")
    axes[1].set_ylim(-0.03, 1.03)
    axes[1].grid(alpha=0.25, linewidth=0.6)
    axes[0].legend(frameon=False, fontsize=8, loc="upper left")
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)


def run(args: argparse.Namespace) -> tuple[list[SweepSummary], list[SweepRollout]]:
    task_config, lqr_config, _cbf_config = gate.build_configs(args.controller_seed)
    env_func = partial(make, "cartpole", **task_config)
    env = env_func(gui=False)
    ctrl = make("lqr", env_func, **lqr_config)
    ctrl.reset()
    observation, info = env.reset(seed=args.controller_seed)
    ctrl.reset_before_run(observation, info, env=env)
    action_low = float(np.asarray(env.action_space.low).reshape(-1)[0])
    action_high = float(np.asarray(env.action_space.high).reshape(-1)[0])
    casadi_fd_func = env.symbolic.fd_func

    certificate_candidates = delayed.certification_envelope()
    certificate_admitted = delayed.baseline_viable_states(
        ctrl,
        info,
        casadi_fd_func,
        certificate_candidates,
        baseline_params=np.zeros(2),
        action_low=action_low,
        action_high=action_high,
        deployment_steps=args.deployment_steps,
        guard_margin=args.admission_guard_margin,
    )

    pending_by_dose: dict[int, np.ndarray] = {}
    commit_by_dose: dict[int, np.ndarray] = {}
    commit_cache: dict[tuple[float, float], np.ndarray] = {}
    attack_delta = np.asarray([args.gain_step, args.bias_step], dtype=float)
    for dose in args.poison_steps:
        pending = delayed.repeated_poison_snapshot(attack_delta, poison_steps=dose)
        pending_by_dose[dose] = pending
        print(f"certifying dose={dose}, pending={pending.tolist()}", flush=True)
        pending_key = (round(float(pending[0]), 10), round(float(pending[1]), 10))
        if pending_key not in commit_cache:
            commit_cache[pending_key] = delayed.commit_backtracked_snapshot(
                np.zeros(2),
                pending,
                ctrl,
                info,
                casadi_fd_func,
                action_low=action_low,
                action_high=action_high,
                deployment_steps=args.deployment_steps,
                certificate_states=certificate_admitted,
                certificate_guard_margin=args.commit_guard_margin,
            )
        commit_by_dose[dose] = commit_cache[pending_key].copy()
        print(
            f"certified dose={dose}, committed={commit_by_dose[dose].tolist()}",
            flush=True,
        )

    admitted_by_seed: dict[int, list[np.ndarray]] = {}
    for seed in args.evaluation_seeds:
        admitted_by_seed[seed] = delayed.baseline_viable_states(
            ctrl,
            info,
            casadi_fd_func,
            heldout_candidates(seed, args.candidate_states_per_seed),
            baseline_params=np.zeros(2),
            action_low=action_low,
            action_high=action_high,
            deployment_steps=args.deployment_steps,
            guard_margin=args.admission_guard_margin,
        )
        print(
            f"held-out seed={seed}: admitted {len(admitted_by_seed[seed])}/"
            f"{args.candidate_states_per_seed}",
            flush=True,
        )
    ctrl.close()
    env.close()

    cache: dict[tuple[int, float, float], list[delayed.DeploymentResult]] = {}
    summaries: list[SweepSummary] = []
    rollout_rows: list[SweepRollout] = []
    for dose in args.poison_steps:
        pending = pending_by_dose[dose]
        snapshots = {
            "action_only": pending,
            "commit_gate": commit_by_dose[dose],
            "always_freeze": np.zeros(2),
        }
        for mechanism in MECHANISMS:
            params = snapshots[mechanism]
            pending_norm = float(np.linalg.norm(pending))
            retained = (
                float(np.linalg.norm(params) / pending_norm)
                if pending_norm > 1e-12
                else 0.0
            )
            for seed in args.evaluation_seeds:
                states = admitted_by_seed[seed]
                cache_key = (seed, round(float(params[0]), 10), round(float(params[1]), 10))
                if cache_key not in cache:
                    print(
                        f"deploying seed={seed}, params={params.tolist()}, "
                        f"rollouts={len(states)}",
                        flush=True,
                    )
                    cache[cache_key] = [
                        delayed.deploy_raw_snapshot(
                            mechanism,
                            params,
                            state,
                            seed=seed,
                            deployment_steps=args.deployment_steps,
                        )
                        for state in states
                    ]
                deployments = cache[cache_key]
                first_steps = [
                    row.first_violation_step
                    for row in deployments
                    if row.first_violation_step is not None
                ]
                summaries.append(
                    SweepSummary(
                        poison_steps=dose,
                        mechanism=mechanism,
                        evaluation_seed=seed,
                        candidate_rollouts=args.candidate_states_per_seed,
                        admitted_rollouts=len(states),
                        certificate_candidates=len(certificate_candidates),
                        certificate_admitted=len(certificate_admitted),
                        admission_guard_margin=args.admission_guard_margin,
                        commit_guard_margin=args.commit_guard_margin,
                        pending_gain=float(pending[0]),
                        pending_bias=float(pending[1]),
                        final_gain=float(params[0]),
                        final_bias=float(params[1]),
                        retained_update_fraction=retained,
                        violating_rollouts=len(first_steps),
                        violation_rate=len(first_steps) / len(states),
                        median_first_violation_step=(
                            float(median(first_steps)) if first_steps else None
                        ),
                        mean_reward=float(
                            np.mean([row.mean_reward for row in deployments])
                        ),
                    )
                )
                rollout_rows.extend(
                    SweepRollout(
                        poison_steps=dose,
                        mechanism=mechanism,
                        evaluation_seed=seed,
                        final_gain=float(params[0]),
                        final_bias=float(params[1]),
                        init_x=row.init_x,
                        init_x_dot=row.init_x_dot,
                        init_theta=row.init_theta,
                        init_theta_dot=row.init_theta_dot,
                        first_violation_step=row.first_violation_step,
                        violation_steps=row.violation_steps,
                        mean_reward=row.mean_reward,
                    )
                    for row in deployments
                )
    return summaries, rollout_rows


def print_compact(rows: list[SweepSummary]) -> None:
    print("| dose | mechanism | committed params | retained | violations | reward |")
    print("|---:|---|---|---:|---:|---:|")
    for dose in sorted({row.poison_steps for row in rows}):
        for mechanism in MECHANISMS:
            selected = [
                row
                for row in rows
                if row.poison_steps == dose and row.mechanism == mechanism
            ]
            violating = sum(row.violating_rollouts for row in selected)
            admitted = sum(row.admitted_rollouts for row in selected)
            print(
                f"| {dose} | {mechanism} | "
                f"({selected[0].final_gain:.2f},{selected[0].final_bias:.2f}) | "
                f"{selected[0].retained_update_fraction:.2f} | "
                f"{violating}/{admitted} | "
                f"{np.mean([row.mean_reward for row in selected]):.3f} |"
            )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--controller-seed", type=int, default=2026)
    parser.add_argument("--evaluation-seeds", type=parse_ints, default=parse_ints("2030,2031,2032"))
    parser.add_argument("--poison-steps", type=parse_ints, default=parse_ints("0,4,6,8,9,10,12"))
    parser.add_argument("--candidate-states-per-seed", type=int, default=64)
    parser.add_argument("--deployment-steps", type=int, default=120)
    parser.add_argument("--gain-step", type=float, default=2.0)
    parser.add_argument("--bias-step", type=float, default=-0.5)
    parser.add_argument("--commit-guard-margin", type=float, default=0.005)
    parser.add_argument("--admission-guard-margin", type=float, default=0.0075)
    parser.add_argument(
        "--summary-out",
        type=Path,
        default=RESULTS_DIR / "safe_control_gym_delayed_trigger_sweep.csv",
    )
    parser.add_argument(
        "--rollouts-out",
        type=Path,
        default=RESULTS_DIR / "safe_control_gym_delayed_trigger_sweep_rollouts.csv",
    )
    parser.add_argument(
        "--figure-out",
        type=Path,
        default=FIGURES_DIR / "safe_control_gym_delayed_trigger_summary.pdf",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    summaries, rollouts = run(args)
    write_rows(args.summary_out, summaries)
    write_rows(args.rollouts_out, rollouts)
    plot_summary(summaries, args.figure_out)
    print_compact(summaries)
    print(f"wrote {args.summary_out}")
    print(f"wrote {args.rollouts_out}")
    print(f"wrote {args.figure_out}")


if __name__ == "__main__":
    main()
