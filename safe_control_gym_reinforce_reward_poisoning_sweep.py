#!/usr/bin/env python3
"""Multi-seed held-out audit for the REINFORCE reward-poisoning attack."""

from __future__ import annotations

import argparse
import csv
from dataclasses import asdict, dataclass
from functools import partial
from pathlib import Path
from statistics import median

import numpy as np
import matplotlib.pyplot as plt
from scipy.stats import binomtest

from safe_control_gym.utils.registration import make

import safe_control_gym_delayed_trigger_attack as delayed
import safe_control_gym_plausible_set_lifecycle_gate as gate
import safe_control_gym_reinforce_reward_poisoning as reinforce


ROOT = Path(__file__).resolve().parent
RESULTS_DIR = ROOT / "results"
FIGURES_DIR = ROOT / "paper_latex" / "figures"
MECHANISMS = (
    "clean_reinforce_snapshot",
    "poisoned_action_only_snapshot",
    "poisoned_commit_gate_snapshot",
    "poisoned_always_freeze_snapshot",
)


@dataclass
class SeedSummary:
    learner_seed: int
    evaluation_seed: int
    mechanism: str
    adaptation_steps: int
    adaptation_constraint_violations: int
    reward_poison_budget: float
    max_reward_poison: float
    actor_updates: int
    attack_target_gain: float
    attack_target_bias: float
    pending_gain: float
    pending_bias: float
    final_gain: float
    final_bias: float
    candidate_rollouts: int
    admitted_rollouts: int
    admission_guard_margin: float
    commit_guard_margin: float
    violating_rollouts: int
    violation_rate: float
    median_first_violation_step: float | None
    mean_reward: float


@dataclass
class SeedRollout:
    learner_seed: int
    evaluation_seed: int
    mechanism: str
    final_gain: float
    final_bias: float
    init_x: float
    init_x_dot: float
    init_theta: float
    init_theta_dot: float
    first_violation_step: int | None
    violation_steps: int
    mean_reward: float


@dataclass
class AggregateSummary:
    mechanism: str
    learner_seeds: int
    seeds_with_violations: int
    admitted_rollouts: int
    violating_rollouts: int
    violation_rate: float
    wilson_low: float
    wilson_high: float
    mean_reward: float
    poison_only_discordant: int
    clean_only_discordant: int
    paired_exact_pvalue: float


def parse_ints(value: str) -> list[int]:
    return [int(item.strip()) for item in value.split(",") if item.strip()]


def heldout_states(
    *,
    controller_seed: int,
    evaluation_seed: int,
    count: int,
    deployment_steps: int,
    admission_guard_margin: float,
) -> list[np.ndarray]:
    rng = np.random.default_rng(evaluation_seed)
    candidates = list(
        rng.uniform(
            low=np.asarray([-0.25, -0.50, -0.15, -1.0]),
            high=np.asarray([0.25, 0.50, 0.15, 1.0]),
            size=(count, 4),
        )
    )
    task_config, lqr_config, _cbf_config = gate.build_configs(controller_seed)
    env_func = partial(make, "cartpole", **task_config)
    env = env_func(gui=False)
    ctrl = make("lqr", env_func, **lqr_config)
    ctrl.reset()
    observation, info = env.reset(seed=controller_seed)
    ctrl.reset_before_run(observation, info, env=env)
    action_low = float(np.asarray(env.action_space.low).reshape(-1)[0])
    action_high = float(np.asarray(env.action_space.high).reshape(-1)[0])
    admitted = delayed.baseline_viable_states(
        ctrl,
        info,
        env.symbolic.fd_func,
        candidates,
        baseline_params=np.zeros(2),
        action_low=action_low,
        action_high=action_high,
        deployment_steps=deployment_steps,
        guard_margin=admission_guard_margin,
    )
    ctrl.close()
    env.close()
    return admitted


def train_pair(
    seed: int,
    args: argparse.Namespace,
) -> tuple[
    np.ndarray,
    reinforce.ReinforceTrainingResult,
    np.ndarray,
    reinforce.ReinforceTrainingResult,
    np.ndarray,
]:
    common = dict(
        seed=seed,
        batches=args.batches,
        batch_steps=args.batch_steps,
        rho=args.rho,
        sigma=args.sigma,
        actor_lr=args.actor_lr,
        gamma=args.gamma,
        max_gradient_norm=args.max_gradient_norm,
        reward_poison_budget=args.reward_poison_budget,
        poison_temperature=args.poison_temperature,
        deployment_steps=args.deployment_steps,
        action_grid_size=args.action_grid_size,
        kernel_backend=args.kernel_backend,
    )
    clean_params, clean_training, _clean_traces = reinforce.train_reinforce(
        "clean_reinforce_snapshot",
        poisoned_rewards=False,
        freeze_updates=False,
        **common,
    )
    poisoned_params, poisoned_training, _poisoned_traces = reinforce.train_reinforce(
        "poisoned_action_only_snapshot",
        poisoned_rewards=True,
        freeze_updates=False,
        **common,
    )
    committed, _certificate_candidates, _certificate_admitted = (
        reinforce.commit_snapshot(
            poisoned_params,
            seed=seed,
            deployment_steps=args.deployment_steps,
            admission_guard_margin=args.admission_guard_margin,
            commit_guard_margin=args.commit_guard_margin,
        )
    )
    return (
        clean_params,
        clean_training,
        poisoned_params,
        poisoned_training,
        committed,
    )


def run(args: argparse.Namespace) -> tuple[list[SeedSummary], list[SeedRollout]]:
    summaries: list[SeedSummary] = []
    rollout_rows: list[SeedRollout] = []
    for learner_seed in args.learner_seeds:
        evaluation_seed = learner_seed + args.evaluation_seed_offset
        print(f"training learner seed={learner_seed}", flush=True)
        (
            clean_params,
            clean_training,
            poisoned_params,
            poisoned_training,
            committed_params,
        ) = train_pair(learner_seed, args)
        states = heldout_states(
            controller_seed=learner_seed,
            evaluation_seed=evaluation_seed,
            count=args.candidate_states,
            deployment_steps=args.deployment_steps,
            admission_guard_margin=args.admission_guard_margin,
        )
        print(
            f"seed={learner_seed}: clean={clean_params.tolist()}, "
            f"poisoned={poisoned_params.tolist()}, "
            f"committed={committed_params.tolist()}, "
            f"admitted={len(states)}/{args.candidate_states}",
            flush=True,
        )
        snapshots = {
            "clean_reinforce_snapshot": clean_params,
            "poisoned_action_only_snapshot": poisoned_params,
            "poisoned_commit_gate_snapshot": committed_params,
            "poisoned_always_freeze_snapshot": np.zeros(2),
        }
        for mechanism in MECHANISMS:
            params = snapshots[mechanism]
            print(
                f"deploying learner seed={learner_seed}, mechanism={mechanism}",
                flush=True,
            )
            deployments = [
                delayed.deploy_raw_snapshot(
                    mechanism,
                    params,
                    state,
                    seed=evaluation_seed,
                    deployment_steps=args.deployment_steps,
                )
                for state in states
            ]
            first_steps = [
                row.first_violation_step
                for row in deployments
                if row.first_violation_step is not None
            ]
            source = (
                clean_training
                if mechanism == "clean_reinforce_snapshot"
                else poisoned_training
            )
            final_pending = (
                clean_params
                if mechanism == "clean_reinforce_snapshot"
                else poisoned_params
            )
            summaries.append(
                SeedSummary(
                    learner_seed=learner_seed,
                    evaluation_seed=evaluation_seed,
                    mechanism=mechanism,
                    adaptation_steps=source.adaptation_steps,
                    adaptation_constraint_violations=(
                        0
                        if mechanism == "poisoned_always_freeze_snapshot"
                        else source.adaptation_constraint_violations
                    ),
                    reward_poison_budget=args.reward_poison_budget,
                    max_reward_poison=(
                        0.0
                        if mechanism == "clean_reinforce_snapshot"
                        else source.max_reward_poison
                    ),
                    actor_updates=(
                        0
                        if mechanism == "poisoned_always_freeze_snapshot"
                        else source.actor_updates
                    ),
                    attack_target_gain=source.attack_target_gain,
                    attack_target_bias=source.attack_target_bias,
                    pending_gain=float(final_pending[0]),
                    pending_bias=float(final_pending[1]),
                    final_gain=float(params[0]),
                    final_bias=float(params[1]),
                    candidate_rollouts=args.candidate_states,
                    admitted_rollouts=len(states),
                    admission_guard_margin=args.admission_guard_margin,
                    commit_guard_margin=args.commit_guard_margin,
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
                SeedRollout(
                    learner_seed=learner_seed,
                    evaluation_seed=evaluation_seed,
                    mechanism=mechanism,
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


def write_csv(path: Path, rows: list[object]) -> None:
    if not rows:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    dictionaries = [asdict(row) for row in rows]
    with path.open("w", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=list(dictionaries[0].keys()))
        writer.writeheader()
        writer.writerows(dictionaries)


def wilson_interval(successes: int, total: int, z: float = 1.96) -> tuple[float, float]:
    rate = successes / total
    denominator = 1.0 + z**2 / total
    center = (rate + z**2 / (2.0 * total)) / denominator
    half_width = (
        z
        * np.sqrt(rate * (1.0 - rate) / total + z**2 / (4.0 * total**2))
        / denominator
    )
    return max(0.0, float(center - half_width)), min(
        1.0, float(center + half_width)
    )


def aggregate(
    summaries: list[SeedSummary],
    rollouts: list[SeedRollout],
) -> list[AggregateSummary]:
    paired: dict[tuple[float, ...], dict[str, bool]] = {}
    for row in rollouts:
        key = (
            float(row.learner_seed),
            row.init_x,
            row.init_x_dot,
            row.init_theta,
            row.init_theta_dot,
        )
        paired.setdefault(key, {})[row.mechanism] = (
            row.first_violation_step is not None
        )
    poison_only = sum(
        values["poisoned_action_only_snapshot"]
        and not values["clean_reinforce_snapshot"]
        for values in paired.values()
    )
    clean_only = sum(
        values["clean_reinforce_snapshot"]
        and not values["poisoned_action_only_snapshot"]
        for values in paired.values()
    )
    discordant = poison_only + clean_only
    paired_pvalue = (
        float(binomtest(min(poison_only, clean_only), discordant, 0.5).pvalue)
        if discordant
        else 1.0
    )
    rows: list[AggregateSummary] = []
    for mechanism in MECHANISMS:
        selected = [row for row in summaries if row.mechanism == mechanism]
        violations = sum(row.violating_rollouts for row in selected)
        admitted = sum(row.admitted_rollouts for row in selected)
        low, high = wilson_interval(violations, admitted)
        rows.append(
            AggregateSummary(
                mechanism=mechanism,
                learner_seeds=len(selected),
                seeds_with_violations=sum(
                    row.violating_rollouts > 0 for row in selected
                ),
                admitted_rollouts=admitted,
                violating_rollouts=violations,
                violation_rate=violations / admitted,
                wilson_low=low,
                wilson_high=high,
                mean_reward=float(np.mean([row.mean_reward for row in selected])),
                poison_only_discordant=poison_only,
                clean_only_discordant=clean_only,
                paired_exact_pvalue=paired_pvalue,
            )
        )
    return rows


def plot_summary(rows: list[SeedSummary], path: Path) -> None:
    labels = {
        "clean_reinforce_snapshot": "Clean learner",
        "poisoned_action_only_snapshot": "Reward-poisoned",
        "poisoned_commit_gate_snapshot": "Poisoned + commit gate",
        "poisoned_always_freeze_snapshot": "Always freeze",
    }
    colors = {
        "clean_reinforce_snapshot": "#4c78a8",
        "poisoned_action_only_snapshot": "#d1495b",
        "poisoned_commit_gate_snapshot": "#00798c",
        "poisoned_always_freeze_snapshot": "#555555",
    }
    fig, axes = plt.subplots(1, 2, figsize=(7.2, 2.8), constrained_layout=True)
    x = np.arange(len(MECHANISMS))
    for index, mechanism in enumerate(MECHANISMS):
        selected = [row for row in rows if row.mechanism == mechanism]
        rates = np.asarray([row.violation_rate for row in selected])
        rewards = np.asarray([row.mean_reward for row in selected])
        axes[0].scatter(
            np.full(len(rates), index), rates, color=colors[mechanism], s=28, zorder=3
        )
        axes[0].plot(
            [index - 0.18, index + 0.18],
            [float(np.mean(rates)), float(np.mean(rates))],
            color=colors[mechanism],
            linewidth=2.0,
        )
        axes[1].scatter(
            np.full(len(rewards), index), rewards, color=colors[mechanism], s=28, zorder=3
        )
        axes[1].plot(
            [index - 0.18, index + 0.18],
            [float(np.mean(rewards)), float(np.mean(rewards))],
            color=colors[mechanism],
            linewidth=2.0,
        )
    tick_labels = [labels[mechanism] for mechanism in MECHANISMS]
    for axis in axes:
        axis.set_xticks(x, tick_labels, rotation=18, ha="right")
        axis.grid(axis="y", alpha=0.25, linewidth=0.6)
    axes[0].set_title("Held-out delayed failures")
    axes[0].set_ylabel("Violation rate")
    axes[0].set_ylim(-0.015, 0.26)
    axes[1].set_title("Deployment utility")
    axes[1].set_ylabel("Mean reward (higher is better)")
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)


def print_summary(rows: list[SeedSummary]) -> None:
    print("| mechanism | violations | admitted | seed successes | reward |")
    print("|---|---:|---:|---:|---:|")
    for mechanism in MECHANISMS:
        selected = [row for row in rows if row.mechanism == mechanism]
        violations = sum(row.violating_rollouts for row in selected)
        admitted = sum(row.admitted_rollouts for row in selected)
        successful_seeds = sum(row.violating_rollouts > 0 for row in selected)
        print(
            f"| {mechanism} | {violations}/{admitted} | {admitted} | "
            f"{successful_seeds}/{len(selected)} | "
            f"{np.mean([row.mean_reward for row in selected]):.3f} |"
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--learner-seeds", type=parse_ints, default=parse_ints("2040,2041,2042")
    )
    parser.add_argument("--evaluation-seed-offset", type=int, default=1000)
    parser.add_argument("--candidate-states", type=int, default=64)
    parser.add_argument("--batches", type=int, default=12)
    parser.add_argument("--batch-steps", type=int, default=8)
    parser.add_argument("--rho", type=float, default=0.005)
    parser.add_argument("--sigma", type=float, default=0.8)
    parser.add_argument("--actor-lr", type=float, default=1.0)
    parser.add_argument("--gamma", type=float, default=0.97)
    parser.add_argument("--max-gradient-norm", type=float, default=1.0)
    parser.add_argument("--reward-poison-budget", type=float, default=2.0)
    parser.add_argument("--poison-temperature", type=float, default=1.0)
    parser.add_argument("--deployment-steps", type=int, default=120)
    parser.add_argument("--action-grid-size", type=int, default=41)
    parser.add_argument(
        "--kernel-backend", choices=("euler", "casadi"), default="casadi"
    )
    parser.add_argument("--admission-guard-margin", type=float, default=0.0075)
    parser.add_argument("--commit-guard-margin", type=float, default=0.005)
    parser.add_argument(
        "--summary-out",
        type=Path,
        default=RESULTS_DIR / "safe_control_gym_reinforce_reward_poisoning_sweep.csv",
    )
    parser.add_argument(
        "--rollouts-out",
        type=Path,
        default=(
            RESULTS_DIR / "safe_control_gym_reinforce_reward_poisoning_sweep_rollouts.csv"
        ),
    )
    parser.add_argument(
        "--aggregate-out",
        type=Path,
        default=(
            RESULTS_DIR / "safe_control_gym_reinforce_reward_poisoning_aggregate.csv"
        ),
    )
    parser.add_argument(
        "--figure-out",
        type=Path,
        default=(
            FIGURES_DIR / "safe_control_gym_reinforce_reward_poisoning_summary.pdf"
        ),
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    summaries, rollouts = run(args)
    aggregate_rows = aggregate(summaries, rollouts)
    write_csv(args.summary_out, summaries)
    write_csv(args.rollouts_out, rollouts)
    write_csv(args.aggregate_out, aggregate_rows)
    plot_summary(summaries, args.figure_out)
    print_summary(summaries)
    print(f"wrote {args.summary_out}")
    print(f"wrote {args.rollouts_out}")
    print(f"wrote {args.aggregate_out}")
    print(f"wrote {args.figure_out}")


if __name__ == "__main__":
    main()
