#!/usr/bin/env python3
"""Trusted-state-anchor frequency/quality audit for TDSC P3.

See ``tdsc_trusted_anchor_protocol.md`` for the locked contract.
"""

from __future__ import annotations

import argparse
import csv
from dataclasses import asdict, dataclass
from pathlib import Path
from statistics import median
from time import perf_counter
from typing import Iterable, Sequence

import numpy as np

import safe_control_gym_quadrotor_certificate_coverage as coverage
import safe_control_gym_quadrotor_lifecycle_scaffold as quad
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
PERIODS = (1, 3, 6, 12)
QUALITY_ERRORS = {
    "high": (0.001, 0.0005),
    "standard": (0.005, 0.002),
}


@dataclass(frozen=True)
class AnchorCondition:
    name: str
    quality: str
    period: int
    anchor_calls: int
    anchor_call_fraction: float
    final_anchor_age: int
    z_radius: float
    theta_radius: float


@dataclass
class ReferenceReproduction:
    learner_seed: int
    locked_commit_fraction: float
    recomputed_commit_fraction: float
    snapshot_max_abs_error: float
    reproduction_pass: bool


@dataclass
class AnchorCertificate:
    learner_seed: int
    condition: str
    quality: str
    anchor_period: int
    anchor_calls: int
    anchor_call_fraction: float
    final_anchor_age: int
    z_radius: float
    theta_radius: float
    sampled_states_per_center: int
    certificate_centers: int
    certificate_centers_admitted: int
    certificate_center_coverage: float
    retained_update_fraction: float
    pending_snapshot_norm: float
    committed_snapshot_norm: float
    full_freeze: bool
    condition_trajectory_steps: int
    shared_certificate_latency_seconds: float


@dataclass
class DeploymentStateSummary:
    learner_seed: int
    candidate_states: int
    freeze_admitted_states: int
    freeze_admission_fraction: float
    selected_states: int


@dataclass
class AnchorDeploymentSummary:
    learner_seed: str
    mechanism: str
    quality: str
    anchor_period: int
    anchor_calls: int
    deployment_rollouts: int
    violating_rollouts: int
    violation_rate: float
    violation_rate_ci95_low: float
    violation_rate_ci95_high: float
    completed_rollouts: int
    completion_rate: float
    median_first_violation_step: float | None
    mean_reward: float
    actuator_saturation_steps: int
    max_action_interface_error: float
    mean_retained_update_fraction: float
    minimum_certificate_center_coverage: float


@dataclass
class AnchorValidity:
    learner_seeds: int
    anchor_conditions: int
    mechanisms: int
    paired_rollouts_per_mechanism: int
    reference_reproduction_pass: bool
    deployment_state_count_pass: bool
    paired_keys_match: bool
    monotonicity_pass: bool
    informative_sensitivity: bool
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


def build_conditions(
    periods: Sequence[int],
    qualities: Sequence[str],
    *,
    update_checkpoints: int,
    z_growth: float,
    theta_growth: float,
) -> list[AnchorCondition]:
    output: list[AnchorCondition] = []
    final_checkpoint = update_checkpoints - 1
    for quality in qualities:
        if quality not in QUALITY_ERRORS:
            raise ValueError(f"unknown anchor quality {quality}")
        base_z, base_theta = QUALITY_ERRORS[quality]
        for period in periods:
            if period <= 0:
                raise ValueError("anchor periods must be positive")
            age = final_checkpoint % period
            calls = (update_checkpoints + period - 1) // period
            output.append(
                AnchorCondition(
                    name=f"{quality}_p{period}",
                    quality=quality,
                    period=period,
                    anchor_calls=calls,
                    anchor_call_fraction=calls / update_checkpoints,
                    final_anchor_age=age,
                    z_radius=base_z + age * z_growth,
                    theta_radius=base_theta + age * theta_growth,
                )
            )
    return output


def condition_levels(
    condition: AnchorCondition,
    all_conditions: Sequence[AnchorCondition],
) -> list[tuple[float, float]]:
    """Return result-independent nested corner shells for one condition."""
    levels = {
        (candidate.z_radius, candidate.theta_radius)
        for candidate in all_conditions
        if candidate.z_radius <= condition.z_radius + 1e-15
        and candidate.theta_radius <= condition.theta_radius + 1e-15
    }
    return sorted(levels)


def nested_state_cloud(
    centers: Sequence[np.ndarray],
    levels: Sequence[tuple[float, float]],
) -> np.ndarray:
    clouds: list[np.ndarray] = []
    for center in centers:
        center = np.asarray(center, dtype=float)
        samples = [center.copy()]
        for z_radius, theta_radius in levels:
            for z_sign in (-1.0, 1.0):
                for theta_sign in (-1.0, 1.0):
                    sample = center.copy()
                    sample[2] += z_sign * z_radius
                    sample[4] += theta_sign * theta_radius
                    samples.append(sample)
        clouds.append(np.vstack(samples))
    return np.stack(clouds)


def snapshot_map(
    specs: Sequence[coverage.SnapshotSpec],
) -> dict[tuple[int, str], np.ndarray]:
    return {
        (spec.learner_seed, spec.mechanism): np.asarray(
            spec.snapshot, dtype=float
        )
        for spec in specs
    }


def reproduce_reference(
    learner_seed: int,
    bundle: quad.DynamicsBundle,
    poisoned: np.ndarray,
    locked_commit: np.ndarray,
    *,
    candidates: int,
    steps: int,
    guard_margin: float,
) -> ReferenceReproduction:
    raw_states = sweep.random_initial_states(
        learner_seed + 5000, candidates
    )
    admitted = quad.exact_certificate_admission(
        bundle,
        raw_states,
        steps=steps,
        guard_margin=guard_margin,
    )
    recomputed, fraction = quad.commit_backtracked_snapshot(
        bundle,
        poisoned,
        admitted,
        steps=steps,
        guard_margin=guard_margin,
    )
    poison_norm = float(np.linalg.norm(poisoned))
    locked_fraction = (
        float(np.linalg.norm(locked_commit)) / poison_norm
        if poison_norm > 0.0
        else 0.0
    )
    error = float(np.max(np.abs(recomputed - locked_commit)))
    passed = bool(
        np.isclose(fraction, locked_fraction, rtol=1e-10, atol=1e-12)
        and np.allclose(
            recomputed,
            locked_commit,
            rtol=1e-10,
            atol=1e-12,
        )
    )
    return ReferenceReproduction(
        learner_seed=learner_seed,
        locked_commit_fraction=locked_fraction,
        recomputed_commit_fraction=fraction,
        snapshot_max_abs_error=error,
        reproduction_pass=passed,
    )


def anchor_certificates(
    learner_seed: int,
    all_conditions: Sequence[AnchorCondition],
    bundle: quad.DynamicsBundle,
    pending_snapshot: np.ndarray,
    certificate_centers: Sequence[np.ndarray],
    *,
    steps: int,
    guard_margin: float,
    cache_dir: Path | None = None,
) -> tuple[dict[str, np.ndarray], list[AnchorCertificate]]:
    master_levels = sorted(
        {
            (condition.z_radius, condition.theta_radius)
            for condition in all_conditions
        }
    )
    cloud = nested_state_cloud(certificate_centers, master_levels)
    centers, samples_per_center, state_dimension = cloud.shape
    if state_dimension != 6:
        raise RuntimeError("unexpected quadrotor state dimension")
    flattened = cloud.reshape(centers * samples_per_center, state_dimension)
    fractions = np.linspace(0.0, 1.0, 21)
    trials = [float(fraction) * pending_snapshot for fraction in fractions]
    cached = (
        load_certificate_cache(
            cache_dir,
            learner_seed=learner_seed,
            master_levels=master_levels,
            steps=steps,
            guard_margin=guard_margin,
            fractions=fractions,
            expected_states=len(flattened),
        )
        if cache_dir is not None
        else None
    )
    if cached is None:
        start = perf_counter()
        first, margins = quad.casadi_snapshot_outcomes(
            bundle,
            trials,
            flattened,
            steps=steps,
        )
        latency = perf_counter() - start
    else:
        first, margins, latency = cached
    first = first.reshape(len(fractions), centers, samples_per_center)
    margins = margins.reshape(
        len(fractions), centers, samples_per_center
    )
    snapshots: dict[str, np.ndarray] = {}
    rows: list[AnchorCertificate] = []
    for condition in all_conditions:
        levels = condition_levels(condition, all_conditions)
        sample_indices = [0]
        for level in levels:
            master_index = master_levels.index(level)
            sample_indices.extend(
                range(1 + 4 * master_index, 1 + 4 * (master_index + 1))
            )
        condition_first = first[:, :, sample_indices]
        condition_margins = margins[:, :, sample_indices]
        center_admitted = np.all(
            (condition_first[0] < 0)
            & (condition_margins[0] <= -guard_margin),
            axis=1,
        )
        accepted_index = 0
        if np.any(center_admitted):
            for index in range(len(fractions)):
                selected_first = condition_first[
                    index, center_admitted, :
                ]
                selected_margins = condition_margins[
                    index, center_admitted, :
                ]
                safe = bool(
                    np.all(selected_first < 0)
                    and np.max(selected_margins) <= -guard_margin
                )
                if not safe:
                    break
                accepted_index = index
        committed = trials[accepted_index]
        fraction = float(fractions[accepted_index])
        admitted_count = int(np.sum(center_admitted))
        condition_samples = len(sample_indices)
        snapshots[condition.name] = committed
        rows.append(
            AnchorCertificate(
                learner_seed=learner_seed,
                condition=condition.name,
                quality=condition.quality,
                anchor_period=condition.period,
                anchor_calls=condition.anchor_calls,
                anchor_call_fraction=condition.anchor_call_fraction,
                final_anchor_age=condition.final_anchor_age,
                z_radius=condition.z_radius,
                theta_radius=condition.theta_radius,
                sampled_states_per_center=condition_samples,
                certificate_centers=centers,
                certificate_centers_admitted=admitted_count,
                certificate_center_coverage=admitted_count / centers,
                retained_update_fraction=fraction,
                pending_snapshot_norm=float(
                    np.linalg.norm(pending_snapshot)
                ),
                committed_snapshot_norm=float(
                    np.linalg.norm(committed)
                ),
                full_freeze=fraction == 0.0,
                condition_trajectory_steps=(
                    len(fractions)
                    * centers
                    * condition_samples
                    * steps
                ),
                shared_certificate_latency_seconds=latency,
            )
        )
    return snapshots, rows


def load_certificate_cache(
    cache_dir: Path,
    *,
    learner_seed: int,
    master_levels: Sequence[tuple[float, float]],
    steps: int,
    guard_margin: float,
    fractions: np.ndarray,
    expected_states: int,
) -> tuple[np.ndarray, np.ndarray, float] | None:
    files = sorted(
        cache_dir.glob(
            f"seed_{learner_seed}_fractions_*.npz"
        )
    )
    if not files:
        return None
    first = np.empty((len(fractions), expected_states), dtype=int)
    margins = np.empty((len(fractions), expected_states), dtype=float)
    seen = np.zeros(len(fractions), dtype=bool)
    total_latency = 0.0
    expected_levels = np.asarray(master_levels, dtype=float)
    for path in files:
        with np.load(path, allow_pickle=False) as data:
            if int(data["learner_seed"]) != learner_seed:
                raise RuntimeError(f"{path}: learner seed mismatch")
            if int(data["steps"]) != steps or not np.isclose(
                float(data["guard_margin"]), guard_margin
            ):
                raise RuntimeError(f"{path}: certificate contract mismatch")
            if not np.allclose(
                np.asarray(data["master_levels"], dtype=float),
                expected_levels,
                rtol=0.0,
                atol=1e-15,
            ):
                raise RuntimeError(f"{path}: anchor grid mismatch")
            indices = np.asarray(data["fraction_indices"], dtype=int)
            if np.any(indices < 0) or np.any(indices >= len(fractions)):
                raise RuntimeError(f"{path}: invalid fraction indices")
            if np.any(seen[indices]):
                raise RuntimeError(f"{path}: duplicate cached fractions")
            if not np.allclose(
                np.asarray(data["fractions"], dtype=float),
                fractions[indices],
                rtol=0.0,
                atol=1e-15,
            ):
                raise RuntimeError(f"{path}: fraction values mismatch")
            chunk_first = np.asarray(data["first"], dtype=int)
            chunk_margins = np.asarray(data["margins"], dtype=float)
            expected_shape = (len(indices), expected_states)
            if (
                chunk_first.shape != expected_shape
                or chunk_margins.shape != expected_shape
            ):
                raise RuntimeError(f"{path}: cached outcome shape mismatch")
            first[indices] = chunk_first
            margins[indices] = chunk_margins
            seen[indices] = True
            total_latency += float(data["latency_seconds"])
    if not np.all(seen):
        missing = np.flatnonzero(~seen).tolist()
        raise RuntimeError(
            f"seed {learner_seed}: incomplete certificate cache; "
            f"missing fractions {missing}"
        )
    print(
        f"learner_seed={learner_seed}: loaded {len(files)} verified "
        f"certificate cache chunks",
        flush=True,
    )
    return first, margins, total_latency


def precompute_certificate_chunk(args: argparse.Namespace) -> None:
    if args.precompute_seed not in args.learner_seeds:
        raise ValueError(
            "--precompute-seed must be present in --learner-seeds"
        )
    start_index = args.fraction_start
    stop_index = args.fraction_stop
    if not (0 <= start_index < stop_index <= 21):
        raise ValueError("fraction chunk must satisfy 0 <= start < stop <= 21")
    conditions = build_conditions(
        args.periods,
        args.qualities,
        update_checkpoints=args.update_checkpoints,
        z_growth=args.z_growth,
        theta_growth=args.theta_growth,
    )
    master_levels = sorted(
        {
            (condition.z_radius, condition.theta_radius)
            for condition in conditions
        }
    )
    specs = coverage.load_locked_snapshots(
        args.snapshot_source,
        args.trace_source,
        [args.precompute_seed],
    )
    snapshots = snapshot_map(specs)
    bundle = quad.build_dynamics(args.precompute_seed)
    pending = snapshots[
        (args.precompute_seed, "poisoned_action_only_snapshot")
    ]
    centers = sweep.random_initial_states(
        args.precompute_seed + 5000,
        args.certificate_candidates,
    )
    cloud = nested_state_cloud(centers, master_levels)
    flattened = cloud.reshape(-1, cloud.shape[-1])
    all_fractions = np.linspace(0.0, 1.0, 21)
    indices = np.arange(start_index, stop_index, dtype=int)
    selected_fractions = all_fractions[indices]
    trials = [
        float(fraction) * pending for fraction in selected_fractions
    ]
    print(
        f"precompute seed={args.precompute_seed} fractions="
        f"{start_index}:{stop_index} states={len(flattened)} "
        f"steps={args.steps}",
        flush=True,
    )
    start = perf_counter()
    first, margins = quad.casadi_snapshot_outcomes(
        bundle,
        trials,
        flattened,
        steps=args.steps,
    )
    latency = perf_counter() - start
    args.certificate_cache_dir.mkdir(parents=True, exist_ok=True)
    path = args.certificate_cache_dir / (
        f"seed_{args.precompute_seed}_fractions_"
        f"{start_index:02d}_{stop_index:02d}.npz"
    )
    np.savez(
        path,
        learner_seed=np.asarray(args.precompute_seed),
        steps=np.asarray(args.steps),
        guard_margin=np.asarray(args.guard_margin),
        master_levels=np.asarray(master_levels, dtype=float),
        fraction_indices=indices,
        fractions=selected_fractions,
        first=first,
        margins=margins,
        latency_seconds=np.asarray(latency),
    )
    print(f"wrote {path} latency={latency:.2f}s", flush=True)


def deployment_states(
    learner_seed: int,
    bundle: quad.DynamicsBundle,
    candidates: Sequence[sweep.HeldoutState],
    *,
    steps: int,
    guard_margin: float,
    count: int,
) -> tuple[list[sweep.HeldoutState], DeploymentStateSummary]:
    first, margins = quad.casadi_rollout_outcomes(
        bundle,
        np.zeros((2, 2), dtype=float),
        [item.state for item in candidates],
        steps=steps,
    )
    admitted = [
        item
        for item, first_step, margin in zip(candidates, first, margins)
        if first_step < 0 and margin <= -guard_margin
    ]
    if len(admitted) < count:
        raise RuntimeError(
            f"learner seed {learner_seed}: only {len(admitted)} "
            f"baseline-safe deployment states"
        )
    selected = sweep.spread_heldout(admitted, count)
    return selected, DeploymentStateSummary(
        learner_seed=learner_seed,
        candidate_states=len(candidates),
        freeze_admitted_states=len(admitted),
        freeze_admission_fraction=len(admitted) / len(candidates),
        selected_states=len(selected),
    )


def wilson_interval(successes: int, trials: int) -> tuple[float, float]:
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


def summarize_group(
    rows: Sequence[coverage.PhysicalRollout],
    *,
    learner_seed: str,
    mechanism: str,
    deployment_steps: int,
    condition_lookup: dict[str, AnchorCondition],
    certificates: Sequence[AnchorCertificate],
) -> AnchorDeploymentSummary:
    violations = [
        row.first_violation_step
        for row in rows
        if row.first_violation_step is not None
    ]
    low, high = wilson_interval(len(violations), len(rows))
    condition = condition_lookup.get(mechanism)
    selected_certificates = [
        row for row in certificates if row.condition == mechanism
    ]
    if learner_seed != "pooled":
        selected_certificates = [
            row
            for row in selected_certificates
            if row.learner_seed == int(learner_seed)
        ]
    return AnchorDeploymentSummary(
        learner_seed=learner_seed,
        mechanism=mechanism,
        quality=condition.quality if condition else "control",
        anchor_period=condition.period if condition else 0,
        anchor_calls=condition.anchor_calls if condition else 0,
        deployment_rollouts=len(rows),
        violating_rollouts=len(violations),
        violation_rate=len(violations) / len(rows),
        violation_rate_ci95_low=low,
        violation_rate_ci95_high=high,
        completed_rollouts=sum(
            row.first_violation_step is None
            and row.steps_executed == deployment_steps
            for row in rows
        ),
        completion_rate=sum(
            row.first_violation_step is None
            for row in rows
        )
        / len(rows),
        median_first_violation_step=(
            float(median(int(value) for value in violations))
            if violations
            else None
        ),
        mean_reward=float(np.mean([row.mean_reward for row in rows])),
        actuator_saturation_steps=sum(
            row.actuator_saturation_steps for row in rows
        ),
        max_action_interface_error=float(
            np.max([row.max_action_interface_error for row in rows])
        ),
        mean_retained_update_fraction=(
            float(
                np.mean(
                    [
                        row.retained_update_fraction
                        for row in selected_certificates
                    ]
                )
            )
            if selected_certificates
            else (0.0 if mechanism == "always_freeze" else 1.0)
        ),
        minimum_certificate_center_coverage=(
            float(
                np.min(
                    [
                        row.certificate_center_coverage
                        for row in selected_certificates
                    ]
                )
            )
            if selected_certificates
            else 1.0
        ),
    )


def summarize_deployments(
    rows: Sequence[coverage.PhysicalRollout],
    learner_seeds: Sequence[int],
    mechanisms: Sequence[str],
    condition_lookup: dict[str, AnchorCondition],
    certificates: Sequence[AnchorCertificate],
    *,
    deployment_steps: int,
) -> list[AnchorDeploymentSummary]:
    output: list[AnchorDeploymentSummary] = []
    for mechanism in mechanisms:
        pooled = [row for row in rows if row.mechanism == mechanism]
        output.append(
            summarize_group(
                pooled,
                learner_seed="pooled",
                mechanism=mechanism,
                deployment_steps=deployment_steps,
                condition_lookup=condition_lookup,
                certificates=certificates,
            )
        )
        for seed in learner_seeds:
            selected = [
                row for row in pooled if row.learner_seed == seed
            ]
            output.append(
                summarize_group(
                    selected,
                    learner_seed=str(seed),
                    mechanism=mechanism,
                    deployment_steps=deployment_steps,
                    condition_lookup=condition_lookup,
                    certificates=certificates,
                )
            )
    return output


def monotonicity_pass(
    rows: Sequence[AnchorCertificate],
    learner_seeds: Sequence[int],
    qualities: Sequence[str],
) -> bool:
    for seed in learner_seeds:
        for quality in qualities:
            selected = sorted(
                [
                    row
                    for row in rows
                    if row.learner_seed == seed
                    and row.quality == quality
                ],
                key=lambda row: row.anchor_period,
            )
            for previous, current in zip(selected, selected[1:]):
                if (
                    current.certificate_centers_admitted
                    > previous.certificate_centers_admitted
                    or current.retained_update_fraction
                    > previous.retained_update_fraction + 1e-12
                ):
                    return False
    return True


def paired_keys_match(
    rows: Sequence[coverage.PhysicalRollout],
    mechanisms: Sequence[str],
) -> bool:
    keys = {
        mechanism: {
            (
                row.learner_seed,
                row.source_seed,
                row.source_index,
            )
            for row in rows
            if row.mechanism == mechanism
        }
        for mechanism in mechanisms
    }
    reference = keys[mechanisms[0]]
    return all(value == reference for value in keys.values())


def output_paths(directory: Path, stem: str) -> dict[str, Path]:
    return {
        suffix: directory / f"{stem}_{suffix}.csv"
        for suffix in (
            "reference",
            "certificates",
            "deployment_states",
            "physical",
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
        "--periods", nargs="+", type=int, default=list(PERIODS)
    )
    parser.add_argument(
        "--qualities",
        nargs="+",
        choices=sorted(QUALITY_ERRORS),
        default=["high", "standard"],
    )
    parser.add_argument("--update-checkpoints", type=int, default=12)
    parser.add_argument("--z-growth", type=float, default=0.002)
    parser.add_argument("--theta-growth", type=float, default=0.001)
    parser.add_argument("--certificate-candidates", type=int, default=16)
    parser.add_argument("--steps", type=int, default=100)
    parser.add_argument("--reference-steps", type=int, default=100)
    parser.add_argument("--guard-margin", type=float, default=0.003)
    parser.add_argument(
        "--deployment-seeds",
        nargs="+",
        type=int,
        default=[6050, 6051, 6052],
    )
    parser.add_argument("--states-per-deployment-seed", type=int, default=48)
    parser.add_argument("--deployment-rollouts-per-seed", type=int, default=8)
    parser.add_argument("--interface-tolerance", type=float, default=1e-8)
    parser.add_argument("--snapshot-source", type=Path, default=SNAPSHOT_SOURCE)
    parser.add_argument("--trace-source", type=Path, default=TRACE_SOURCE)
    parser.add_argument(
        "--certificate-cache-dir",
        type=Path,
        default=RESULTS / "trusted_anchor_certificate_cache",
    )
    parser.add_argument("--precompute-seed", type=int)
    parser.add_argument("--fraction-start", type=int, default=0)
    parser.add_argument("--fraction-stop", type=int, default=21)
    parser.add_argument("--output-dir", type=Path, default=RESULTS)
    parser.add_argument(
        "--output-stem",
        default="safe_control_gym_quadrotor_trusted_anchor",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.precompute_seed is not None:
        precompute_certificate_chunk(args)
        return
    conditions = build_conditions(
        args.periods,
        args.qualities,
        update_checkpoints=args.update_checkpoints,
        z_growth=args.z_growth,
        theta_growth=args.theta_growth,
    )
    condition_lookup = {
        condition.name: condition for condition in conditions
    }
    specs = coverage.load_locked_snapshots(
        args.snapshot_source,
        args.trace_source,
        args.learner_seeds,
    )
    snapshots = snapshot_map(specs)
    deployment_candidates = coverage.coverage_states(
        args.deployment_seeds, args.states_per_deployment_seed
    )
    paths = output_paths(args.output_dir, args.output_stem)
    references: list[ReferenceReproduction] = []
    certificates: list[AnchorCertificate] = []
    deployment_state_rows: list[DeploymentStateSummary] = []
    physical_rows: list[coverage.PhysicalRollout] = []
    committed: dict[tuple[int, str], np.ndarray] = {}
    mechanisms = ["poisoned_raw", "always_freeze"] + [
        condition.name for condition in conditions
    ]
    for seed in args.learner_seeds:
        print(f"learner_seed={seed}: reference reconstruction", flush=True)
        bundle = quad.build_dynamics(seed)
        poisoned = snapshots[(seed, "poisoned_action_only_snapshot")]
        locked_commit = snapshots[
            (seed, "poisoned_commit_gate_snapshot")
        ]
        reference = reproduce_reference(
            seed,
            bundle,
            poisoned,
            locked_commit,
            candidates=args.certificate_candidates,
            steps=args.reference_steps,
            guard_margin=args.guard_margin,
        )
        if not reference.reproduction_pass:
            raise RuntimeError(
                f"learner seed {seed}: reference commit mismatch"
            )
        references.append(reference)
        certificate_centers = sweep.random_initial_states(
            seed + 5000, args.certificate_candidates
        )
        print(
            f"learner_seed={seed}: joint exact anchor grid "
            f"{len(conditions)} conditions",
            flush=True,
        )
        seed_committed, seed_certificates = anchor_certificates(
            seed,
            conditions,
            bundle,
            poisoned,
            certificate_centers,
            steps=args.steps,
            guard_margin=args.guard_margin,
            cache_dir=args.certificate_cache_dir,
        )
        for condition, row in zip(conditions, seed_certificates):
            committed[(seed, condition.name)] = seed_committed[
                condition.name
            ]
            certificates.append(row)
            print(
                f"learner_seed={seed}: {condition.name} centers="
                f"{row.certificate_centers_admitted}/"
                f"{row.certificate_centers} fraction="
                f"{row.retained_update_fraction:.2f}",
                flush=True,
            )
        selected_states, state_summary = deployment_states(
            seed,
            bundle,
            deployment_candidates,
            steps=args.steps,
            guard_margin=args.guard_margin,
            count=args.deployment_rollouts_per_seed,
        )
        deployment_state_rows.append(state_summary)
        deployment_specs = [
            coverage.SnapshotSpec(seed, "poisoned_raw", poisoned),
            coverage.SnapshotSpec(
                seed,
                "always_freeze",
                np.zeros((2, 2), dtype=float),
            ),
            *[
                coverage.SnapshotSpec(
                    seed,
                    condition.name,
                    committed[(seed, condition.name)],
                )
                for condition in conditions
            ],
        ]
        print(
            f"learner_seed={seed}: physical deployment "
            f"{len(mechanisms)}x{len(selected_states)}x{args.steps}",
            flush=True,
        )
        seed_physical, _horizon = coverage.run_physical_rollouts(
            bundle,
            deployment_specs,
            selected_states,
            horizons=[args.steps],
        )
        physical_rows.extend(seed_physical)
    summaries = summarize_deployments(
        physical_rows,
        args.learner_seeds,
        mechanisms,
        condition_lookup,
        certificates,
        deployment_steps=args.steps,
    )
    reference_pass = all(row.reproduction_pass for row in references)
    state_count_pass = all(
        row.selected_states >= args.deployment_rollouts_per_seed
        for row in deployment_state_rows
    )
    keys_match = paired_keys_match(physical_rows, mechanisms)
    monotonic = monotonicity_pass(
        certificates, args.learner_seeds, args.qualities
    )
    sensitivity_values = {
        (
            row.certificate_centers_admitted,
            row.retained_update_fraction,
        )
        for row in certificates
    }
    informative = len(sensitivity_values) > 1
    max_interface_error = float(
        np.max(
            [row.max_action_interface_error for row in physical_rows]
        )
    )
    interface_pass = max_interface_error <= args.interface_tolerance
    complete_summaries = len(summaries) == (
        len(mechanisms) * (len(args.learner_seeds) + 1)
    )
    decision = AnchorValidity(
        learner_seeds=len(args.learner_seeds),
        anchor_conditions=len(conditions),
        mechanisms=len(mechanisms),
        paired_rollouts_per_mechanism=(
            len(args.learner_seeds)
            * args.deployment_rollouts_per_seed
        ),
        reference_reproduction_pass=reference_pass,
        deployment_state_count_pass=state_count_pass,
        paired_keys_match=keys_match,
        monotonicity_pass=monotonic,
        informative_sensitivity=informative,
        max_action_interface_error=max_interface_error,
        interface_tolerance=args.interface_tolerance,
        interface_audit_pass=interface_pass,
        complete_summaries=complete_summaries,
        audit_valid=(
            reference_pass
            and state_count_pass
            and keys_match
            and monotonic
            and interface_pass
            and complete_summaries
        ),
    )
    if not monotonic:
        raise RuntimeError("nested anchor conditions failed monotonicity")
    write_csv(paths["reference"], references)
    write_csv(paths["certificates"], certificates)
    write_csv(paths["deployment_states"], deployment_state_rows)
    write_csv(paths["physical"], physical_rows)
    write_csv(paths["summary"], summaries)
    write_csv(paths["validity"], [decision])
    print(
        f"audit_valid={decision.audit_valid} "
        f"informative_sensitivity={decision.informative_sensitivity} "
        f"max_interface_error={decision.max_action_interface_error:.3e}",
        flush=True,
    )
    print(f"wrote {paths['summary']}", flush=True)


if __name__ == "__main__":
    main()
