#!/usr/bin/env python3
"""Unified paired-state security--availability frontier for TDSC P2.

The locked protocol is ``tdsc_security_availability_frontier_protocol.md``.
Every mechanism is evaluated on the same certificate-selected state blocks.
Snapshot-admission latency and online controller latency are measured
separately.
"""

from __future__ import annotations

import argparse
import csv
from dataclasses import asdict, dataclass
from pathlib import Path
from statistics import median
from time import perf_counter, perf_counter_ns
from typing import Iterable, Sequence

import numpy as np
from safe_control_gym.utils.registration import make

import safe_control_gym_quadrotor_certificate_coverage as coverage
import safe_control_gym_quadrotor_lifecycle_scaffold as quad
import safe_control_gym_quadrotor_mpsc_baseline as mpsc
import safe_control_gym_quadrotor_reinforce_reward_poisoning_sweep as sweep


ROOT = Path(__file__).resolve().parent
RESULTS = ROOT / "results"
SNAPSHOT_SOURCE = (
    RESULTS / "safe_control_gym_quadrotor_reinforce_reward_poisoning_sweep.csv"
)
TRACE_SOURCE = (
    RESULTS
    / "safe_control_gym_quadrotor_reinforce_reward_poisoning_sweep_traces.csv"
)
MECHANISMS = (
    "clean_reinforce_snapshot",
    "poisoned_action_only_snapshot",
    "poisoned_commit_gate_snapshot",
    "poisoned_always_freeze_snapshot",
    "poisoned_permanent_filter_snapshot",
    "official_linear_mpsc",
)
RAW_SNAPSHOT_MECHANISMS = {
    "clean_reinforce_snapshot",
    "poisoned_action_only_snapshot",
    "poisoned_commit_gate_snapshot",
    "poisoned_always_freeze_snapshot",
}


@dataclass
class AdmissionRow:
    learner_seed: int
    source_seed: int
    source_index: int
    freeze_max_margin: float
    commit_max_margin: float
    freeze_certificate_safe: bool
    commit_certificate_safe: bool
    common_admitted: bool
    selected_for_deployment: bool


@dataclass
class AdmissionSummary:
    learner_seed: int
    candidate_states: int
    freeze_admitted: int
    commit_admitted: int
    common_admitted: int
    common_admission_fraction: float
    selected_states: int


@dataclass
class OfflineCommitTiming:
    learner_seed: int
    certificate_candidates: int
    certificate_admitted: int
    locked_commit_fraction: float
    recomputed_commit_fraction: float
    snapshot_max_abs_error: float
    reproduction_pass: bool
    offline_commit_latency_seconds: float


@dataclass
class StepRow:
    learner_seed: int
    mechanism: str
    source_seed: int
    source_index: int
    step: int
    controller_latency_ms: float
    intervened: bool
    rejected: bool
    infeasible: bool
    action_correction: float
    reward: float
    normalized_state_margin: float
    physical_violation: bool
    actuator_saturated: bool
    action_interface_error: float


@dataclass
class RolloutRow:
    learner_seed: int
    mechanism: str
    source_seed: int
    source_index: int
    init_x: float
    init_x_dot: float
    init_z: float
    init_z_dot: float
    init_theta: float
    init_theta_dot: float
    planned_steps: int
    steps_executed: int
    completed_horizon: bool
    first_violation_step: int | None
    mean_reward: float
    interventions: int
    rejections: int
    infeasible_steps: int
    mean_action_correction: float
    max_action_correction: float
    mean_controller_latency_ms: float
    median_controller_latency_ms: float
    p95_controller_latency_ms: float
    max_controller_latency_ms: float
    actuator_saturation_steps: int
    max_action_interface_error: float


@dataclass
class FrontierSummary:
    learner_seed: str
    mechanism: str
    learner_seeds: int
    deployment_rollouts: int
    violating_rollouts: int
    violation_rate: float
    violation_rate_ci95_low: float
    violation_rate_ci95_high: float
    completed_rollouts: int
    completion_rate: float
    median_first_violation_step: float | None
    mean_reward: float
    mean_reward_ci95_low: float
    mean_reward_ci95_high: float
    executed_steps: int
    interventions: int
    intervention_rate: float
    rejections: int
    rejection_rate: float
    infeasible_steps: int
    infeasible_rate: float
    mean_action_correction: float
    max_action_correction: float
    mean_controller_latency_ms: float
    median_controller_latency_ms: float
    p95_controller_latency_ms: float
    max_controller_latency_ms: float
    actuator_saturation_steps: int
    max_action_interface_error: float


@dataclass
class ValidityDecision:
    learner_seeds: int
    mechanisms: int
    paired_rollouts_per_mechanism: int
    minimum_common_admitted: int
    required_selected_states_per_seed: int
    common_set_size_pass: bool
    commit_reproduction_pass: bool
    paired_keys_match: bool
    max_action_interface_error: float
    interface_tolerance: float
    interface_audit_pass: bool
    complete_summaries: bool
    audit_valid: bool


def write_csv(path: Path, rows: Iterable[object]) -> None:
    dictionaries = [asdict(row) for row in rows]
    if not dictionaries:
        raise RuntimeError(f"refusing to write empty artifact {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=list(dictionaries[0]))
        writer.writeheader()
        writer.writerows(dictionaries)


def snapshot_lookup(
    specs: Sequence[coverage.SnapshotSpec],
) -> dict[tuple[int, str], np.ndarray]:
    return {
        (spec.learner_seed, spec.mechanism): np.asarray(
            spec.snapshot, dtype=float
        )
        for spec in specs
    }


def reproduce_commit(
    learner_seed: int,
    bundle: quad.DynamicsBundle,
    poisoned_snapshot: np.ndarray,
    locked_commit_snapshot: np.ndarray,
    *,
    candidates: int,
    steps: int,
    guard_margin: float,
) -> OfflineCommitTiming:
    raw_states = sweep.random_initial_states(
        learner_seed + 5000, candidates
    )
    start = perf_counter()
    admitted = quad.exact_certificate_admission(
        bundle,
        raw_states,
        steps=steps,
        guard_margin=guard_margin,
    )
    recomputed, fraction = quad.commit_backtracked_snapshot(
        bundle,
        poisoned_snapshot,
        admitted,
        steps=steps,
        guard_margin=guard_margin,
    )
    elapsed = perf_counter() - start
    poisoned_norm = float(np.linalg.norm(poisoned_snapshot))
    locked_fraction = (
        float(np.linalg.norm(locked_commit_snapshot)) / poisoned_norm
        if poisoned_norm > 0.0
        else 0.0
    )
    error = float(np.max(np.abs(recomputed - locked_commit_snapshot)))
    reproduction_pass = bool(
        np.isclose(fraction, locked_fraction, rtol=1e-10, atol=1e-12)
        and np.allclose(
            recomputed,
            locked_commit_snapshot,
            rtol=1e-10,
            atol=1e-12,
        )
    )
    return OfflineCommitTiming(
        learner_seed=learner_seed,
        certificate_candidates=len(raw_states),
        certificate_admitted=len(admitted),
        locked_commit_fraction=locked_fraction,
        recomputed_commit_fraction=fraction,
        snapshot_max_abs_error=error,
        reproduction_pass=reproduction_pass,
        offline_commit_latency_seconds=elapsed,
    )


def select_common_states(
    learner_seed: int,
    bundle: quad.DynamicsBundle,
    commit_snapshot: np.ndarray,
    candidates: Sequence[sweep.HeldoutState],
    *,
    steps: int,
    guard_margin: float,
    count: int,
) -> tuple[
    list[sweep.HeldoutState], list[AdmissionRow], AdmissionSummary
]:
    snapshots = [
        np.zeros((2, 2), dtype=float),
        np.asarray(commit_snapshot, dtype=float),
    ]
    first, margins = quad.casadi_snapshot_outcomes(
        bundle,
        snapshots,
        [item.state for item in candidates],
        steps=steps,
    )
    freeze_safe = (first[0] < 0) & (margins[0] <= -guard_margin)
    commit_safe = (first[1] < 0) & (margins[1] <= -guard_margin)
    common = freeze_safe & commit_safe
    admitted_indices = np.flatnonzero(common)
    if len(admitted_indices) < count:
        raise RuntimeError(
            f"learner seed {learner_seed}: common operating set has "
            f"{len(admitted_indices)} states, fewer than requested {count}"
        )
    positions = np.linspace(
        0, len(admitted_indices) - 1, count, dtype=int
    )
    selected_indices = {
        int(admitted_indices[int(position)]) for position in positions
    }
    selected = [
        item
        for index, item in enumerate(candidates)
        if index in selected_indices
    ]
    rows = [
        AdmissionRow(
            learner_seed=learner_seed,
            source_seed=item.source_seed,
            source_index=item.source_index,
            freeze_max_margin=float(margins[0, index]),
            commit_max_margin=float(margins[1, index]),
            freeze_certificate_safe=bool(freeze_safe[index]),
            commit_certificate_safe=bool(commit_safe[index]),
            common_admitted=bool(common[index]),
            selected_for_deployment=index in selected_indices,
        )
        for index, item in enumerate(candidates)
    ]
    summary = AdmissionSummary(
        learner_seed=learner_seed,
        candidate_states=len(candidates),
        freeze_admitted=int(np.sum(freeze_safe)),
        commit_admitted=int(np.sum(commit_safe)),
        common_admitted=int(np.sum(common)),
        common_admission_fraction=float(np.mean(common)),
        selected_states=len(selected),
    )
    return selected, rows, summary


def reset_seed(
    learner_seed: int, state: sweep.HeldoutState
) -> int:
    return (
        learner_seed * 100_000
        + state.source_seed * 100
        + state.source_index
    )


def timed_action(
    mechanism: str,
    bundle: quad.DynamicsBundle,
    observation: np.ndarray,
    info: dict,
    snapshots: dict[str, np.ndarray],
    fixed_grid: np.ndarray,
    safety_filter: object | None,
    *,
    filter_z_radius: float,
    filter_theta_radius: float,
    filter_guard_margin: float,
    filter_backup_steps: int,
) -> tuple[np.ndarray, float, bool, bool, bool, float]:
    state = np.asarray(observation, dtype=float).reshape(1, -1)
    if mechanism in RAW_SNAPSHOT_MECHANISMS:
        start = perf_counter_ns()
        action = quad.policy_actions(
            bundle, state, snapshots[mechanism]
        )[0]
        elapsed_ns = perf_counter_ns() - start
        return action, elapsed_ns / 1e6, False, False, False, 0.0

    poisoned = snapshots["poisoned_action_only_snapshot"]
    if mechanism == "poisoned_permanent_filter_snapshot":
        start = perf_counter_ns()
        raw_action = quad.policy_actions(bundle, state, poisoned)[0]
        baseline = quad.policy_actions(
            bundle, state, np.zeros((2, 2), dtype=float)
        )[0]
        action, accepted, correction = quad.permanent_filter_action(
            bundle,
            np.asarray(observation, dtype=float),
            raw_action,
            baseline,
            fixed_grid,
            z_radius=filter_z_radius,
            theta_radius=filter_theta_radius,
            guard_margin=filter_guard_margin,
            backup_steps=filter_backup_steps,
        )
        elapsed_ns = perf_counter_ns() - start
        return (
            action,
            elapsed_ns / 1e6,
            correction > 1e-9,
            not accepted,
            False,
            correction,
        )

    if mechanism != "official_linear_mpsc" or safety_filter is None:
        raise RuntimeError(f"unsupported mechanism {mechanism}")
    raw_start = perf_counter_ns()
    raw_action = quad.policy_actions(bundle, state, poisoned)[0]
    raw_elapsed_ns = perf_counter_ns() - raw_start
    with mpsc.silence_stdout():
        filter_start = perf_counter_ns()
        certified_action, success = safety_filter.certify_action(
            np.asarray(observation, dtype=float), raw_action, info
        )
        filter_elapsed_ns = perf_counter_ns() - filter_start
    action = np.clip(
        np.asarray(certified_action, dtype=float),
        bundle.action_low,
        bundle.action_high,
    )
    correction = float(np.linalg.norm(action - raw_action))
    return (
        action,
        (raw_elapsed_ns + filter_elapsed_ns) / 1e6,
        correction > 1e-9,
        False,
        not bool(success),
        correction,
    )


def run_mechanism(
    learner_seed: int,
    mechanism: str,
    bundle: quad.DynamicsBundle,
    snapshots: dict[str, np.ndarray],
    states: Sequence[sweep.HeldoutState],
    *,
    steps: int,
    filter_grid_size: int,
    filter_z_radius: float,
    filter_theta_radius: float,
    filter_guard_margin: float,
    filter_backup_steps: int,
) -> tuple[list[RolloutRow], list[StepRow]]:
    env = make("quadrotor", **dict(bundle.task_config))
    fixed_grid = quad.action_grid(bundle, filter_grid_size)
    safety_filter = (
        mpsc.build_mpsc(bundle)
        if mechanism == "official_linear_mpsc"
        else None
    )
    rollout_rows: list[RolloutRow] = []
    step_rows: list[StepRow] = []
    for state_item in states:
        quad.set_quadrotor_initial_state(env, state_item.state)
        observation, info = env.reset(
            seed=reset_seed(learner_seed, state_item)
        )
        if safety_filter is not None:
            safety_filter.reset_before_run(env=env)
        rewards: list[float] = []
        corrections: list[float] = []
        latencies: list[float] = []
        interventions = 0
        rejections = 0
        infeasible_steps = 0
        saturation_steps = 0
        interface_errors: list[float] = []
        first_violation: int | None = None
        for step in range(steps):
            (
                action,
                latency_ms,
                intervened,
                rejected,
                infeasible,
                correction,
            ) = timed_action(
                mechanism,
                bundle,
                np.asarray(observation, dtype=float),
                info,
                snapshots,
                fixed_grid,
                safety_filter,
                filter_z_radius=filter_z_radius,
                filter_theta_radius=filter_theta_radius,
                filter_guard_margin=filter_guard_margin,
                filter_backup_steps=filter_backup_steps,
            )
            expected_action = np.clip(
                np.asarray(action, dtype=float),
                bundle.action_low,
                bundle.action_high,
            )
            observation, reward, _done, info = env.step(expected_action)
            interface_error = float(
                np.max(
                    np.abs(
                        np.asarray(
                            env.current_clipped_action, dtype=float
                        )
                        - expected_action
                    )
                )
            )
            saturated = coverage.actuator_saturated(env)
            normalized_margin = coverage.normalized_state_margin(
                np.asarray(env.state, dtype=float)
            )
            violated = bool(
                quad.state_margins(
                    np.asarray(env.state, dtype=float)
                )[0]
                > 1e-9
            )
            rewards.append(float(reward))
            corrections.append(float(correction))
            latencies.append(float(latency_ms))
            interface_errors.append(interface_error)
            interventions += int(intervened)
            rejections += int(rejected)
            infeasible_steps += int(infeasible)
            saturation_steps += int(saturated)
            step_rows.append(
                StepRow(
                    learner_seed=learner_seed,
                    mechanism=mechanism,
                    source_seed=state_item.source_seed,
                    source_index=state_item.source_index,
                    step=step,
                    controller_latency_ms=float(latency_ms),
                    intervened=intervened,
                    rejected=rejected,
                    infeasible=infeasible,
                    action_correction=float(correction),
                    reward=float(reward),
                    normalized_state_margin=normalized_margin,
                    physical_violation=violated,
                    actuator_saturated=saturated,
                    action_interface_error=interface_error,
                )
            )
            if violated:
                first_violation = step
                break
        initial = np.asarray(state_item.state, dtype=float)
        rollout_rows.append(
            RolloutRow(
                learner_seed=learner_seed,
                mechanism=mechanism,
                source_seed=state_item.source_seed,
                source_index=state_item.source_index,
                init_x=float(initial[0]),
                init_x_dot=float(initial[1]),
                init_z=float(initial[2]),
                init_z_dot=float(initial[3]),
                init_theta=float(initial[4]),
                init_theta_dot=float(initial[5]),
                planned_steps=steps,
                steps_executed=len(rewards),
                completed_horizon=(
                    first_violation is None and len(rewards) == steps
                ),
                first_violation_step=first_violation,
                mean_reward=float(np.mean(rewards)),
                interventions=interventions,
                rejections=rejections,
                infeasible_steps=infeasible_steps,
                mean_action_correction=float(np.mean(corrections)),
                max_action_correction=float(np.max(corrections)),
                mean_controller_latency_ms=float(np.mean(latencies)),
                median_controller_latency_ms=float(np.median(latencies)),
                p95_controller_latency_ms=float(
                    np.percentile(latencies, 95)
                ),
                max_controller_latency_ms=float(np.max(latencies)),
                actuator_saturation_steps=saturation_steps,
                max_action_interface_error=float(
                    np.max(interface_errors)
                ),
            )
        )
    if safety_filter is not None:
        safety_filter.close()
    env.close()
    return rollout_rows, step_rows


def wilson_interval(successes: int, trials: int) -> tuple[float, float]:
    if trials <= 0:
        raise ValueError("Wilson interval requires at least one trial")
    z = 1.959963984540054
    proportion = successes / trials
    denominator = 1.0 + z * z / trials
    center = (
        proportion + z * z / (2.0 * trials)
    ) / denominator
    half_width = (
        z
        * np.sqrt(
            proportion * (1.0 - proportion) / trials
            + z * z / (4.0 * trials * trials)
        )
        / denominator
    )
    return (
        max(0.0, float(center - half_width)),
        min(1.0, float(center + half_width)),
    )


def bootstrap_mean_interval(
    values: Sequence[float],
    *,
    samples: int,
    seed: int,
) -> tuple[float, float]:
    array = np.asarray(values, dtype=float)
    if len(array) == 1 or samples <= 0:
        value = float(np.mean(array))
        return value, value
    rng = np.random.default_rng(seed)
    indices = rng.integers(
        0, len(array), size=(samples, len(array))
    )
    means = np.mean(array[indices], axis=1)
    low, high = np.percentile(means, [2.5, 97.5])
    return float(low), float(high)


def summarize_group(
    rollouts: Sequence[RolloutRow],
    steps: Sequence[StepRow],
    *,
    learner_seed: str,
    mechanism: str,
    bootstrap_samples: int,
) -> FrontierSummary:
    violations = [
        row.first_violation_step
        for row in rollouts
        if row.first_violation_step is not None
    ]
    violation_low, violation_high = wilson_interval(
        len(violations), len(rollouts)
    )
    rewards = [row.mean_reward for row in rollouts]
    bootstrap_seed = (
        62026
        + sum(ord(character) for character in mechanism)
        + sum(ord(character) for character in learner_seed)
    )
    reward_low, reward_high = bootstrap_mean_interval(
        rewards,
        samples=bootstrap_samples,
        seed=bootstrap_seed,
    )
    latencies = [row.controller_latency_ms for row in steps]
    corrections = [row.action_correction for row in steps]
    executed = len(steps)
    return FrontierSummary(
        learner_seed=learner_seed,
        mechanism=mechanism,
        learner_seeds=len({row.learner_seed for row in rollouts}),
        deployment_rollouts=len(rollouts),
        violating_rollouts=len(violations),
        violation_rate=len(violations) / len(rollouts),
        violation_rate_ci95_low=violation_low,
        violation_rate_ci95_high=violation_high,
        completed_rollouts=sum(
            row.completed_horizon for row in rollouts
        ),
        completion_rate=sum(
            row.completed_horizon for row in rollouts
        )
        / len(rollouts),
        median_first_violation_step=(
            float(median(int(value) for value in violations))
            if violations
            else None
        ),
        mean_reward=float(np.mean(rewards)),
        mean_reward_ci95_low=reward_low,
        mean_reward_ci95_high=reward_high,
        executed_steps=executed,
        interventions=sum(row.intervened for row in steps),
        intervention_rate=sum(row.intervened for row in steps)
        / executed,
        rejections=sum(row.rejected for row in steps),
        rejection_rate=sum(row.rejected for row in steps) / executed,
        infeasible_steps=sum(row.infeasible for row in steps),
        infeasible_rate=sum(row.infeasible for row in steps)
        / executed,
        mean_action_correction=float(np.mean(corrections)),
        max_action_correction=float(np.max(corrections)),
        mean_controller_latency_ms=float(np.mean(latencies)),
        median_controller_latency_ms=float(np.median(latencies)),
        p95_controller_latency_ms=float(
            np.percentile(latencies, 95)
        ),
        max_controller_latency_ms=float(np.max(latencies)),
        actuator_saturation_steps=sum(
            row.actuator_saturated for row in steps
        ),
        max_action_interface_error=float(
            np.max([row.action_interface_error for row in steps])
        ),
    )


def summarize(
    rollouts: Sequence[RolloutRow],
    steps: Sequence[StepRow],
    learner_seeds: Sequence[int],
    *,
    bootstrap_samples: int,
) -> list[FrontierSummary]:
    output: list[FrontierSummary] = []
    for mechanism in MECHANISMS:
        pooled_rollouts = [
            row for row in rollouts if row.mechanism == mechanism
        ]
        pooled_steps = [
            row for row in steps if row.mechanism == mechanism
        ]
        output.append(
            summarize_group(
                pooled_rollouts,
                pooled_steps,
                learner_seed="pooled",
                mechanism=mechanism,
                bootstrap_samples=bootstrap_samples,
            )
        )
        for seed in learner_seeds:
            seed_rollouts = [
                row
                for row in pooled_rollouts
                if row.learner_seed == seed
            ]
            seed_steps = [
                row
                for row in pooled_steps
                if row.learner_seed == seed
            ]
            output.append(
                summarize_group(
                    seed_rollouts,
                    seed_steps,
                    learner_seed=str(seed),
                    mechanism=mechanism,
                    bootstrap_samples=bootstrap_samples,
                )
            )
    return output


def paired_keys_match(
    rollouts: Sequence[RolloutRow],
) -> bool:
    key_sets = {
        mechanism: {
            (row.learner_seed, row.source_seed, row.source_index)
            for row in rollouts
            if row.mechanism == mechanism
        }
        for mechanism in MECHANISMS
    }
    reference = key_sets[MECHANISMS[0]]
    return all(keys == reference for keys in key_sets.values())


def output_paths(directory: Path, stem: str) -> dict[str, Path]:
    return {
        suffix: directory / f"{stem}_{suffix}.csv"
        for suffix in (
            "admission",
            "admission_summary",
            "offline_commit_timing",
            "steps",
            "rollouts",
            "summary",
            "validity",
        )
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--learner-seeds",
        nargs="+",
        type=int,
        default=[2040, 2041, 2042],
    )
    parser.add_argument(
        "--candidate-seeds",
        nargs="+",
        type=int,
        default=[5050, 5051, 5052],
    )
    parser.add_argument("--states-per-candidate-seed", type=int, default=48)
    parser.add_argument("--paired-rollouts-per-seed", type=int, default=8)
    parser.add_argument("--steps", type=int, default=100)
    parser.add_argument("--certificate-guard-margin", type=float, default=0.003)
    parser.add_argument("--commit-candidates", type=int, default=16)
    parser.add_argument("--commit-steps", type=int, default=100)
    parser.add_argument("--filter-grid-size", type=int, default=5)
    parser.add_argument("--filter-z-radius", type=float, default=0.005)
    parser.add_argument("--filter-theta-radius", type=float, default=0.002)
    parser.add_argument("--filter-guard-margin", type=float, default=0.01)
    parser.add_argument("--filter-backup-steps", type=int, default=5)
    parser.add_argument("--bootstrap-samples", type=int, default=10_000)
    parser.add_argument("--interface-tolerance", type=float, default=1e-8)
    parser.add_argument("--snapshot-source", type=Path, default=SNAPSHOT_SOURCE)
    parser.add_argument("--trace-source", type=Path, default=TRACE_SOURCE)
    parser.add_argument("--output-dir", type=Path, default=RESULTS)
    parser.add_argument(
        "--output-stem",
        default="safe_control_gym_quadrotor_security_availability_frontier",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.paired_rollouts_per_seed <= 0 or args.steps <= 0:
        raise ValueError("paired rollout count and steps must be positive")
    specs = coverage.load_locked_snapshots(
        args.snapshot_source,
        args.trace_source,
        args.learner_seeds,
    )
    snapshots = snapshot_lookup(specs)
    candidates = coverage.coverage_states(
        args.candidate_seeds, args.states_per_candidate_seed
    )
    paths = output_paths(args.output_dir, args.output_stem)
    admission_rows: list[AdmissionRow] = []
    admission_summaries: list[AdmissionSummary] = []
    offline_rows: list[OfflineCommitTiming] = []
    rollout_rows: list[RolloutRow] = []
    step_rows: list[StepRow] = []
    for seed in args.learner_seeds:
        print(f"learner_seed={seed}: reconstructing commit", flush=True)
        bundle = quad.build_dynamics(seed)
        seed_snapshots = {
            mechanism: snapshots[(seed, mechanism)]
            for mechanism in coverage.MECHANISMS
        }
        offline = reproduce_commit(
            seed,
            bundle,
            seed_snapshots["poisoned_action_only_snapshot"],
            seed_snapshots["poisoned_commit_gate_snapshot"],
            candidates=args.commit_candidates,
            steps=args.commit_steps,
            guard_margin=args.certificate_guard_margin,
        )
        if not offline.reproduction_pass:
            raise RuntimeError(
                f"learner seed {seed}: locked commit reproduction failed"
            )
        offline_rows.append(offline)
        selected, seed_admission, admission_summary = (
            select_common_states(
                seed,
                bundle,
                seed_snapshots["poisoned_commit_gate_snapshot"],
                candidates,
                steps=args.steps,
                guard_margin=args.certificate_guard_margin,
                count=args.paired_rollouts_per_seed,
            )
        )
        admission_rows.extend(seed_admission)
        admission_summaries.append(admission_summary)
        print(
            f"learner_seed={seed}: common operating set "
            f"{admission_summary.common_admitted}/"
            f"{admission_summary.candidate_states}; selected="
            f"{len(selected)}",
            flush=True,
        )
        for mechanism in MECHANISMS:
            print(
                f"learner_seed={seed}: {mechanism} "
                f"{len(selected)}x{args.steps}",
                flush=True,
            )
            mechanism_rollouts, mechanism_steps = run_mechanism(
                seed,
                mechanism,
                bundle,
                seed_snapshots,
                selected,
                steps=args.steps,
                filter_grid_size=args.filter_grid_size,
                filter_z_radius=args.filter_z_radius,
                filter_theta_radius=args.filter_theta_radius,
                filter_guard_margin=args.filter_guard_margin,
                filter_backup_steps=args.filter_backup_steps,
            )
            rollout_rows.extend(mechanism_rollouts)
            step_rows.extend(mechanism_steps)
            print(
                f"learner_seed={seed}: {mechanism} violations="
                f"{sum(row.first_violation_step is not None for row in mechanism_rollouts)}"
                f"/{len(mechanism_rollouts)}",
                flush=True,
            )
    summaries = summarize(
        rollout_rows,
        step_rows,
        args.learner_seeds,
        bootstrap_samples=args.bootstrap_samples,
    )
    max_interface_error = float(
        np.max([row.action_interface_error for row in step_rows])
    )
    common_size_pass = all(
        row.common_admitted >= args.paired_rollouts_per_seed
        for row in admission_summaries
    )
    reproduction_pass = all(row.reproduction_pass for row in offline_rows)
    keys_match = paired_keys_match(rollout_rows)
    interface_pass = max_interface_error <= args.interface_tolerance
    complete_summaries = len(summaries) == (
        len(MECHANISMS) * (len(args.learner_seeds) + 1)
    )
    decision = ValidityDecision(
        learner_seeds=len(args.learner_seeds),
        mechanisms=len(MECHANISMS),
        paired_rollouts_per_mechanism=(
            len(args.learner_seeds) * args.paired_rollouts_per_seed
        ),
        minimum_common_admitted=min(
            row.common_admitted for row in admission_summaries
        ),
        required_selected_states_per_seed=args.paired_rollouts_per_seed,
        common_set_size_pass=common_size_pass,
        commit_reproduction_pass=reproduction_pass,
        paired_keys_match=keys_match,
        max_action_interface_error=max_interface_error,
        interface_tolerance=args.interface_tolerance,
        interface_audit_pass=interface_pass,
        complete_summaries=complete_summaries,
        audit_valid=(
            common_size_pass
            and reproduction_pass
            and keys_match
            and interface_pass
            and complete_summaries
        ),
    )
    write_csv(paths["admission"], admission_rows)
    write_csv(paths["admission_summary"], admission_summaries)
    write_csv(paths["offline_commit_timing"], offline_rows)
    write_csv(paths["steps"], step_rows)
    write_csv(paths["rollouts"], rollout_rows)
    write_csv(paths["summary"], summaries)
    write_csv(paths["validity"], [decision])
    print(
        f"audit_valid={decision.audit_valid} paired_rollouts="
        f"{decision.paired_rollouts_per_mechanism} "
        f"max_interface_error={decision.max_action_interface_error:.3e}",
        flush=True,
    )
    print(f"wrote {paths['summary']}", flush=True)


if __name__ == "__main__":
    main()
