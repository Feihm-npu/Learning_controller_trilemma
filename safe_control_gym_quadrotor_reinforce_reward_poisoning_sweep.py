#!/usr/bin/env python3
"""Locked-hyperparameter multi-seed audit for quadrotor reward poisoning.

The attack target and learner hyperparameters are calibrated once on seed
2040, then frozen.  Each learner seed uses distinct training states, distinct
commit-certificate states, and a shared deployment set drawn only from
disjoint evaluation seeds.  Clean and poisoned snapshots are paired on every
deployment state.  A smaller paired subset also audits the expensive permanent
five-step backup shield.
"""

from __future__ import annotations

import argparse
import csv
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from statistics import median
from typing import Iterable, Sequence

import numpy as np
from scipy.stats import binomtest

import safe_control_gym_quadrotor_lifecycle_scaffold as quad
import safe_control_gym_quadrotor_reinforce_reward_poisoning as learner


ROOT = Path(__file__).resolve().parent
RESULTS_DIR = ROOT / "results"
CORE_MECHANISMS = (
    "clean_reinforce_snapshot",
    "poisoned_action_only_snapshot",
    "poisoned_always_freeze_snapshot",
    "poisoned_commit_gate_snapshot",
)
PERMANENT_MECHANISM = "poisoned_permanent_filter_snapshot"


@dataclass(frozen=True)
class HeldoutState:
    source_seed: int
    source_index: int
    state: np.ndarray


@dataclass
class SweepRollout:
    learner_seed: int
    source_seed: int
    source_index: int
    mechanism: str
    rollout: int
    init_x: float
    init_x_dot: float
    init_z: float
    init_z_dot: float
    init_theta: float
    init_theta_dot: float
    steps_executed: int
    violation_steps: int
    first_violation_step: int | None
    filter_interventions: int
    filter_rejections: int
    mean_reward: float


@dataclass
class AggregateRow:
    mechanism: str
    learner_seeds: int
    seeds_with_violation: int
    deployment_rollouts: int
    violating_rollouts: int
    deployment_violation_rate: float
    immediate_violating_rollouts: int
    delayed_violating_rollouts: int
    median_first_violation_step: float | None
    adaptation_constraint_violations: int
    filter_interventions: int
    filter_rejections: int
    mean_deployment_reward: float


@dataclass
class GateDecision:
    learner_seeds: int
    heldout_states: int
    poison_only_failures: int
    clean_only_failures: int
    paired_exact_pvalue: float
    poisoned_worse_all_seeds: bool
    clean_violation_rate: float
    poisoned_violation_rate: float
    commit_violations: int
    freeze_violations: int
    permanent_filter_violations: int
    permanent_filter_rejections: int
    adaptation_violations: int
    provisional_gate_pass: bool


def random_initial_states(seed: int, count: int) -> list[np.ndarray]:
    """Draw only random states; deterministic scaffold points are excluded."""
    rng = np.random.default_rng(seed)
    lows = np.asarray([-0.4, -0.12, 0.72, -0.12, -0.05, -0.12])
    highs = np.asarray([0.4, 0.12, 1.28, 0.12, 0.05, 0.12])
    return [rng.uniform(lows, highs) for _ in range(count)]


def admitted_heldout_states(
    bundle: quad.DynamicsBundle,
    source_seeds: Sequence[int],
    *,
    candidates_per_seed: int,
    steps: int,
    guard_margin: float,
) -> list[HeldoutState]:
    candidates = [
        HeldoutState(seed, index, state)
        for seed in source_seeds
        for index, state in enumerate(random_initial_states(seed, candidates_per_seed))
    ]
    first, margins = quad.casadi_rollout_outcomes(
        bundle,
        np.zeros((2, 2), dtype=float),
        [item.state for item in candidates],
        steps=steps,
    )
    return [
        item
        for item, first_step, margin in zip(candidates, first, margins)
        if first_step < 0 and margin <= -guard_margin
    ]


def spread_heldout(states: Sequence[HeldoutState], count: int) -> list[HeldoutState]:
    if count >= len(states):
        return list(states)
    indices = np.linspace(0, len(states) - 1, count, dtype=int)
    return [states[int(index)] for index in indices]


def attach_metadata(
    learner_seed: int,
    rows: Sequence[quad.DeploymentResult],
    states: Sequence[HeldoutState],
) -> list[SweepRollout]:
    output: list[SweepRollout] = []
    for row in rows:
        metadata = states[row.rollout]
        output.append(
            SweepRollout(
                learner_seed=learner_seed,
                source_seed=metadata.source_seed,
                source_index=metadata.source_index,
                **asdict(row),
            )
        )
    return output


def zero_snapshot_training(
    poisoned: learner.TrainingResult,
) -> learner.TrainingResult:
    return replace(
        poisoned,
        mechanism="poisoned_always_freeze_snapshot",
        actor_updates=0,
        action_filter_interventions=0,
        rejected_action_steps=0,
        adaptation_constraint_violations=0,
        pending_w00=0.0,
        pending_w01=0.0,
        pending_w10=0.0,
        pending_w11=0.0,
        final_w00=0.0,
        final_w01=0.0,
        final_w10=0.0,
        final_w11=0.0,
        commit_fraction=0.0,
    )


def train_seed(
    seed: int,
    target_snapshot: np.ndarray,
    args: argparse.Namespace,
) -> tuple[
    quad.DynamicsBundle,
    dict[str, np.ndarray],
    dict[str, learner.TrainingResult],
    list[learner.BatchTrace],
]:
    bundle = quad.build_dynamics(seed)
    training_candidates = quad.candidate_initial_states(seed)
    training_viable = quad.baseline_viable_states(
        bundle,
        training_candidates,
        steps=args.deployment_steps,
        guard_margin=0.01,
    )
    training_states = quad.spread_subset(training_viable, args.batches)
    common = dict(
        seed=seed,
        batches=args.batches,
        batch_steps=args.batch_steps,
        sigma=args.sigma,
        actor_lr=args.actor_lr,
        gamma=args.gamma,
        max_gradient_norm=args.max_gradient_norm,
        reward_poison_budget=args.reward_poison_budget,
        poison_temperature=args.poison_temperature,
        filter_grid_size=args.filter_grid_size,
        filter_z_radius=args.filter_z_radius,
        filter_theta_radius=args.filter_theta_radius,
        filter_guard_margin=args.filter_guard_margin,
        filter_backup_steps=args.filter_backup_steps,
    )
    clean_snapshot, clean_training, clean_traces = learner.train_reinforce(
        "clean_reinforce_snapshot",
        bundle,
        target_snapshot,
        training_states,
        poisoned_rewards=False,
        freeze_updates=False,
        **common,
    )
    poisoned_snapshot, poisoned_training, poison_traces = learner.train_reinforce(
        "poisoned_action_only_snapshot",
        bundle,
        target_snapshot,
        training_states,
        poisoned_rewards=True,
        freeze_updates=False,
        **common,
    )

    certificate_raw = random_initial_states(
        seed + args.certificate_seed_offset,
        args.certificate_candidates,
    )
    certificate_states = quad.exact_certificate_admission(
        bundle,
        certificate_raw,
        steps=args.deployment_steps,
        guard_margin=args.certificate_guard_margin,
    )
    if not certificate_states:
        raise RuntimeError(f"seed {seed}: no certificate state admitted")
    committed_snapshot, commit_fraction = quad.commit_backtracked_snapshot(
        bundle,
        poisoned_snapshot,
        certificate_states,
        steps=args.deployment_steps,
        guard_margin=args.certificate_guard_margin,
    )
    committed_values = learner.snapshot_fields(committed_snapshot)
    commit_training = replace(
        poisoned_training,
        mechanism="poisoned_commit_gate_snapshot",
        final_w00=committed_values[0],
        final_w01=committed_values[1],
        final_w10=committed_values[2],
        final_w11=committed_values[3],
        commit_fraction=commit_fraction,
        commit_projection_norm=float(
            np.linalg.norm(committed_snapshot - poisoned_snapshot)
        ),
        certificate_candidates=len(certificate_raw),
        certificate_admitted=len(certificate_states),
    )
    freeze_training = zero_snapshot_training(poisoned_training)
    permanent_training = replace(
        poisoned_training, mechanism=PERMANENT_MECHANISM
    )
    snapshots = {
        "clean_reinforce_snapshot": clean_snapshot,
        "poisoned_action_only_snapshot": poisoned_snapshot,
        "poisoned_always_freeze_snapshot": np.zeros((2, 2), dtype=float),
        "poisoned_commit_gate_snapshot": committed_snapshot,
        PERMANENT_MECHANISM: poisoned_snapshot,
    }
    training = {
        "clean_reinforce_snapshot": clean_training,
        "poisoned_action_only_snapshot": poisoned_training,
        "poisoned_always_freeze_snapshot": freeze_training,
        "poisoned_commit_gate_snapshot": commit_training,
        PERMANENT_MECHANISM: permanent_training,
    }
    return bundle, snapshots, training, clean_traces + poison_traces


def aggregate_rollouts(
    rows: Sequence[SweepRollout],
    summaries: Sequence[learner.ExperimentSummary],
    *,
    minimum_delay: int,
) -> list[AggregateRow]:
    output: list[AggregateRow] = []
    mechanisms = list(CORE_MECHANISMS) + [PERMANENT_MECHANISM]
    for mechanism in mechanisms:
        selected = [row for row in rows if row.mechanism == mechanism]
        if not selected:
            continue
        first_steps = [
            int(row.first_violation_step)
            for row in selected
            if row.first_violation_step is not None
        ]
        mechanism_summaries = [
            row for row in summaries if row.mechanism == mechanism
        ]
        output.append(
            AggregateRow(
                mechanism=mechanism,
                learner_seeds=len({row.learner_seed for row in selected}),
                seeds_with_violation=len(
                    {
                        row.learner_seed
                        for row in selected
                        if row.first_violation_step is not None
                    }
                ),
                deployment_rollouts=len(selected),
                violating_rollouts=len(first_steps),
                deployment_violation_rate=len(first_steps) / len(selected),
                immediate_violating_rollouts=sum(
                    step < minimum_delay for step in first_steps
                ),
                delayed_violating_rollouts=sum(
                    step >= minimum_delay for step in first_steps
                ),
                median_first_violation_step=(
                    float(median(first_steps)) if first_steps else None
                ),
                adaptation_constraint_violations=sum(
                    row.adaptation_constraint_violations
                    for row in mechanism_summaries
                ),
                filter_interventions=sum(row.filter_interventions for row in selected),
                filter_rejections=sum(row.filter_rejections for row in selected),
                mean_deployment_reward=float(
                    np.mean([row.mean_reward for row in selected])
                ),
            )
        )
    return output


def paired_gate_decision(
    rows: Sequence[SweepRollout],
    aggregate: Sequence[AggregateRow],
    summaries: Sequence[learner.ExperimentSummary],
    heldout_states: int,
) -> GateDecision:
    lookup = {
        (row.learner_seed, row.mechanism, row.source_seed, row.source_index): (
            row.first_violation_step is not None
        )
        for row in rows
        if row.mechanism in {
            "clean_reinforce_snapshot",
            "poisoned_action_only_snapshot",
        }
    }
    paired_keys = {
        (seed, source_seed, source_index)
        for seed, mechanism, source_seed, source_index in lookup
        if mechanism == "clean_reinforce_snapshot"
    }
    poison_only = 0
    clean_only = 0
    for seed, source_seed, source_index in paired_keys:
        clean = lookup[(seed, "clean_reinforce_snapshot", source_seed, source_index)]
        poison = lookup[(seed, "poisoned_action_only_snapshot", source_seed, source_index)]
        poison_only += int(poison and not clean)
        clean_only += int(clean and not poison)
    discordant = poison_only + clean_only
    pvalue = (
        float(
            binomtest(
                poison_only,
                discordant,
                p=0.5,
                alternative="two-sided",
            ).pvalue
        )
        if discordant
        else 1.0
    )
    by_mechanism = {row.mechanism: row for row in aggregate}
    per_seed = {
        seed: {
            mechanism: sum(
                row.first_violation_step is not None
                for row in rows
                if row.learner_seed == seed and row.mechanism == mechanism
            )
            for mechanism in (
                "clean_reinforce_snapshot",
                "poisoned_action_only_snapshot",
            )
        }
        for seed in {row.learner_seed for row in rows}
    }
    poisoned_worse_all = all(
        values["poisoned_action_only_snapshot"]
        > values["clean_reinforce_snapshot"]
        for values in per_seed.values()
    )
    clean = by_mechanism["clean_reinforce_snapshot"]
    poison = by_mechanism["poisoned_action_only_snapshot"]
    commit = by_mechanism["poisoned_commit_gate_snapshot"]
    freeze = by_mechanism["poisoned_always_freeze_snapshot"]
    permanent = by_mechanism.get(PERMANENT_MECHANISM)
    adaptation_violations = sum(
        row.adaptation_constraint_violations
        for row in summaries
        if row.mechanism in {
            "clean_reinforce_snapshot",
            "poisoned_action_only_snapshot",
        }
    )
    permanent_violations = permanent.violating_rollouts if permanent else 0
    permanent_rejections = permanent.filter_rejections if permanent else 0
    passed = bool(
        poisoned_worse_all
        and pvalue < 0.05
        and commit.violating_rollouts == 0
        and freeze.violating_rollouts == 0
        and permanent_violations == 0
        and permanent_rejections == 0
        and adaptation_violations == 0
    )
    return GateDecision(
        learner_seeds=len(per_seed),
        heldout_states=heldout_states,
        poison_only_failures=poison_only,
        clean_only_failures=clean_only,
        paired_exact_pvalue=pvalue,
        poisoned_worse_all_seeds=poisoned_worse_all,
        clean_violation_rate=clean.deployment_violation_rate,
        poisoned_violation_rate=poison.deployment_violation_rate,
        commit_violations=commit.violating_rollouts,
        freeze_violations=freeze.violating_rollouts,
        permanent_filter_violations=permanent_violations,
        permanent_filter_rejections=permanent_rejections,
        adaptation_violations=adaptation_violations,
        provisional_gate_pass=passed,
    )


def write_csv(path: Path, rows: Iterable[object]) -> None:
    dictionaries = [asdict(row) for row in rows]
    if not dictionaries:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=list(dictionaries[0]).copy())
        writer.writeheader()
        writer.writerows(dictionaries)


def print_aggregate(rows: Sequence[AggregateRow]) -> None:
    print("| mechanism | seeds | violations | delayed | median first | filter int/rej |", flush=True)
    print("|---|---:|---:|---:|---:|---:|", flush=True)
    for row in rows:
        first = "-" if row.median_first_violation_step is None else f"{row.median_first_violation_step:.1f}"
        print(
            f"| {row.mechanism} | {row.seeds_with_violation}/{row.learner_seeds} | "
            f"{row.violating_rollouts}/{row.deployment_rollouts} | "
            f"{row.delayed_violating_rollouts} | {first} | "
            f"{row.filter_interventions}/{row.filter_rejections} |",
            flush=True,
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--learner-seeds", nargs="+", type=int, default=[2040, 2041, 2042])
    parser.add_argument("--target-seed", type=int, default=2040)
    parser.add_argument("--evaluation-seeds", nargs="+", type=int, default=[3040, 3041, 3042])
    parser.add_argument("--evaluation-candidates-per-seed", type=int, default=16)
    parser.add_argument("--heldout-rollouts", type=int, default=24)
    parser.add_argument("--permanent-filter-rollouts", type=int, default=4)
    parser.add_argument("--batches", type=int, default=12)
    parser.add_argument("--batch-steps", type=int, default=12)
    parser.add_argument("--sigma", type=float, default=0.01)
    parser.add_argument("--actor-lr", type=float, default=0.02)
    parser.add_argument("--gamma", type=float, default=0.97)
    parser.add_argument("--max-gradient-norm", type=float, default=0.5)
    parser.add_argument("--reward-poison-budget", type=float, default=0.5)
    parser.add_argument("--poison-temperature", type=float, default=0.5)
    parser.add_argument("--deployment-steps", type=int, default=100)
    parser.add_argument("--minimum-delay", type=int, default=8)
    parser.add_argument("--certificate-seed-offset", type=int, default=5000)
    parser.add_argument("--certificate-candidates", type=int, default=16)
    parser.add_argument("--certificate-guard-margin", type=float, default=0.003)
    parser.add_argument("--filter-grid-size", type=int, default=5)
    parser.add_argument("--filter-z-radius", type=float, default=0.005)
    parser.add_argument("--filter-theta-radius", type=float, default=0.002)
    parser.add_argument("--filter-guard-margin", type=float, default=0.01)
    parser.add_argument("--filter-backup-steps", type=int, default=5)
    parser.add_argument(
        "--summary-out",
        type=Path,
        default=RESULTS_DIR / "safe_control_gym_quadrotor_reinforce_reward_poisoning_sweep.csv",
    )
    parser.add_argument(
        "--aggregate-out",
        type=Path,
        default=RESULTS_DIR / "safe_control_gym_quadrotor_reinforce_reward_poisoning_aggregate.csv",
    )
    parser.add_argument(
        "--rollouts-out",
        type=Path,
        default=RESULTS_DIR / "safe_control_gym_quadrotor_reinforce_reward_poisoning_sweep_rollouts.csv",
    )
    parser.add_argument(
        "--traces-out",
        type=Path,
        default=RESULTS_DIR / "safe_control_gym_quadrotor_reinforce_reward_poisoning_sweep_traces.csv",
    )
    parser.add_argument(
        "--decision-out",
        type=Path,
        default=RESULTS_DIR / "safe_control_gym_quadrotor_reinforce_reward_poisoning_gate.csv",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    calibration_bundle = quad.build_dynamics(args.target_seed)
    target_snapshot, _calibration_states = learner.choose_target(
        calibration_bundle,
        seed=args.target_seed,
        deployment_steps=args.deployment_steps,
        minimum_delay=args.minimum_delay,
    )
    heldout_pool = admitted_heldout_states(
        calibration_bundle,
        args.evaluation_seeds,
        candidates_per_seed=args.evaluation_candidates_per_seed,
        steps=args.deployment_steps,
        guard_margin=args.certificate_guard_margin,
    )
    heldout_states = spread_heldout(heldout_pool, args.heldout_rollouts)
    permanent_states = spread_heldout(
        heldout_states, args.permanent_filter_rollouts
    )
    print(
        f"locked_target={target_snapshot.tolist()} admitted_heldout="
        f"{len(heldout_pool)}/{len(args.evaluation_seeds) * args.evaluation_candidates_per_seed} "
        f"selected={len(heldout_states)}",
        flush=True,
    )

    summaries: list[learner.ExperimentSummary] = []
    sweep_rollouts: list[SweepRollout] = []
    traces: list[learner.BatchTrace] = []
    for seed in args.learner_seeds:
        print(f"learner_seed={seed}: training", flush=True)
        bundle, snapshots, training, seed_traces = train_seed(
            seed, target_snapshot, args
        )
        traces.extend(seed_traces)
        core_rows = quad.run_pybullet_deployments(
            bundle,
            {name: snapshots[name] for name in CORE_MECHANISMS},
            [item.state for item in heldout_states],
            seed=seed,
            steps=args.deployment_steps,
            minimum_delay=args.minimum_delay,
            filter_grid_size=args.filter_grid_size,
            z_radius=args.filter_z_radius,
            theta_radius=args.filter_theta_radius,
            filter_guard_margin=args.filter_guard_margin,
            filter_backup_steps=args.filter_backup_steps,
        )
        permanent_rows = quad.run_pybullet_deployments(
            bundle,
            {PERMANENT_MECHANISM: snapshots[PERMANENT_MECHANISM]},
            [item.state for item in permanent_states],
            seed=seed,
            steps=args.deployment_steps,
            minimum_delay=args.minimum_delay,
            filter_grid_size=args.filter_grid_size,
            z_radius=args.filter_z_radius,
            theta_radius=args.filter_theta_radius,
            filter_guard_margin=args.filter_guard_margin,
            filter_backup_steps=args.filter_backup_steps,
        )
        sweep_rollouts.extend(attach_metadata(seed, core_rows, heldout_states))
        sweep_rollouts.extend(
            attach_metadata(seed, permanent_rows, permanent_states)
        )
        for mechanism in CORE_MECHANISMS:
            mechanism_rows = [row for row in core_rows if row.mechanism == mechanism]
            summaries.append(
                learner.summarize(
                    training[mechanism],
                    mechanism_rows,
                    target_snapshot,
                    minimum_delay=args.minimum_delay,
                )
            )
        summaries.append(
            learner.summarize(
                training[PERMANENT_MECHANISM],
                permanent_rows,
                target_snapshot,
                minimum_delay=args.minimum_delay,
            )
        )
        poison_failures = sum(
            row.first_violation_step is not None
            for row in core_rows
            if row.mechanism == "poisoned_action_only_snapshot"
        )
        clean_failures = sum(
            row.first_violation_step is not None
            for row in core_rows
            if row.mechanism == "clean_reinforce_snapshot"
        )
        print(
            f"learner_seed={seed}: clean={clean_failures}/{len(heldout_states)} "
            f"poison={poison_failures}/{len(heldout_states)} "
            f"commit_fraction={training['poisoned_commit_gate_snapshot'].commit_fraction:.2f} "
            f"permanent={sum(row.first_violation_step is not None for row in permanent_rows)}/"
            f"{len(permanent_rows)}",
            flush=True,
        )

    aggregate = aggregate_rollouts(
        sweep_rollouts, summaries, minimum_delay=args.minimum_delay
    )
    decision = paired_gate_decision(
        sweep_rollouts, aggregate, summaries, len(heldout_states)
    )
    write_csv(args.summary_out, summaries)
    write_csv(args.aggregate_out, aggregate)
    write_csv(args.rollouts_out, sweep_rollouts)
    write_csv(args.traces_out, traces)
    write_csv(args.decision_out, [decision])
    print_aggregate(aggregate)
    print(
        f"paired poison-only={decision.poison_only_failures} "
        f"clean-only={decision.clean_only_failures} "
        f"p={decision.paired_exact_pvalue:.3e} "
        f"gate_pass={decision.provisional_gate_pass}",
        flush=True,
    )
    print(f"wrote {args.aggregate_out}", flush=True)
    print(f"wrote {args.decision_out}", flush=True)


if __name__ == "__main__":
    main()
