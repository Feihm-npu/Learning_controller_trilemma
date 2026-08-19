#!/usr/bin/env python3
"""Paired CasADi--PyBullet coverage audit for locked quadrotor snapshots.

The protocol was specified and locked before execution in
``tdsc_certificate_coverage_protocol.md``.
No state is admitted by the certificate before this audit.
"""

from __future__ import annotations

import argparse
import csv
from dataclasses import asdict, dataclass
from pathlib import Path
from time import perf_counter
from typing import Iterable, Sequence

import numpy as np
from safe_control_gym.utils.registration import make

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
MECHANISMS = (
    "clean_reinforce_snapshot",
    "poisoned_action_only_snapshot",
    "poisoned_commit_gate_snapshot",
    "poisoned_always_freeze_snapshot",
)
PRIMARY_COVERAGE_MECHANISMS = (
    "clean_reinforce_snapshot",
    "poisoned_commit_gate_snapshot",
    "poisoned_always_freeze_snapshot",
)


@dataclass(frozen=True)
class SnapshotSpec:
    learner_seed: int
    mechanism: str
    snapshot: np.ndarray


@dataclass
class PhysicalRollout:
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
    steps_executed: int
    first_violation_step: int | None
    mean_reward: float
    max_normalized_state_margin: float
    actuator_saturation_steps: int
    max_action_interface_error: float


@dataclass
class CoveragePair:
    learner_seed: int
    mechanism: str
    source_seed: int
    source_index: int
    horizon: int
    guard_margin: float
    casadi_first_violation_step: int | None
    casadi_max_state_margin: float
    certificate_safe: bool
    pybullet_first_violation_step: int | None
    pybullet_safe: bool
    pybullet_max_normalized_state_margin: float
    actuator_saturation_steps: int
    max_action_interface_error: float
    classification: str


@dataclass
class CoverageAggregate:
    learner_seed: str
    mechanism: str
    horizon: int
    guard_margin: float
    evaluated_pairs: int
    certified_pairs: int
    rejected_pairs: int
    pybullet_safe_pairs: int
    true_acceptances: int
    false_acceptances: int
    true_rejections: int
    false_rejections: int
    certificate_coverage: float
    pybullet_safe_rate: float
    false_acceptance_rate_certified: float
    false_rejection_rate_rejected: float
    worst_pybullet_normalized_margin_certified: float
    max_action_interface_error: float


@dataclass
class CoverageDecision:
    primary_horizon: int
    primary_guard_margin: float
    evaluated_pairs: int
    certified_pairs: int
    false_acceptances: int
    max_action_interface_error: float
    clean_coverage: float
    commit_coverage: float
    freeze_coverage: float
    minimum_required_coverage: float
    zero_false_acceptance: bool
    interface_audit_pass: bool
    coverage_pass: bool
    primary_gate_pass: bool
    casadi_runtime_seconds: float
    pybullet_runtime_seconds: float


def write_csv(path: Path, rows: Iterable[object]) -> None:
    dictionaries = [asdict(row) for row in rows]
    if not dictionaries:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=list(dictionaries[0]))
        writer.writeheader()
        writer.writerows(dictionaries)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as source:
        return list(csv.DictReader(source))


def load_locked_snapshots(
    summary_path: Path,
    trace_path: Path,
    learner_seeds: Sequence[int],
) -> list[SnapshotSpec]:
    summary_rows = read_csv(summary_path)
    summary_lookup = {
        (int(row["seed"]), row["mechanism"]): row
        for row in summary_rows
        if row["mechanism"] in MECHANISMS
    }
    trace_rows = read_csv(trace_path)
    final_trace: dict[tuple[int, str], dict[str, str]] = {}
    for row in trace_rows:
        key = (int(row["seed"]), row["mechanism"])
        if key not in final_trace or int(row["batch"]) > int(
            final_trace[key]["batch"]
        ):
            final_trace[key] = row
    output: list[SnapshotSpec] = []
    for seed in learner_seeds:
        raw_snapshots: dict[str, np.ndarray] = {}
        for mechanism in (
            "clean_reinforce_snapshot",
            "poisoned_action_only_snapshot",
        ):
            key = (seed, mechanism)
            if key not in final_trace:
                raise RuntimeError(
                    f"{trace_path.name}: missing locked final trace {key}"
                )
            row = final_trace[key]
            raw_snapshots[mechanism] = np.asarray(
                [
                    [float(row["w00"]), float(row["w01"])],
                    [float(row["w10"]), float(row["w11"])],
                ],
                dtype=float,
            )
        commit_key = (seed, "poisoned_commit_gate_snapshot")
        if commit_key not in summary_lookup:
            raise RuntimeError(
                f"{summary_path.name}: missing locked commit row {commit_key}"
            )
        commit_fraction = float(summary_lookup[commit_key]["commit_fraction"])
        snapshots = {
            "clean_reinforce_snapshot": raw_snapshots[
                "clean_reinforce_snapshot"
            ],
            "poisoned_action_only_snapshot": raw_snapshots[
                "poisoned_action_only_snapshot"
            ],
            "poisoned_commit_gate_snapshot": (
                commit_fraction
                * raw_snapshots["poisoned_action_only_snapshot"]
            ),
            "poisoned_always_freeze_snapshot": np.zeros(
                (2, 2), dtype=float
            ),
        }
        for mechanism in MECHANISMS:
            key = (seed, mechanism)
            if key not in summary_lookup:
                raise RuntimeError(
                    f"{summary_path.name}: missing locked summary {key}"
                )
            expected_norm = float(
                summary_lookup[key]["final_snapshot_norm"]
            )
            actual_norm = float(np.linalg.norm(snapshots[mechanism]))
            if not np.isclose(
                actual_norm, expected_norm, rtol=1e-10, atol=1e-12
            ):
                raise RuntimeError(
                    f"{key}: reconstructed norm {actual_norm} != "
                    f"locked norm {expected_norm}"
                )
            output.append(
                SnapshotSpec(
                    learner_seed=seed,
                    mechanism=mechanism,
                    snapshot=snapshots[mechanism],
                )
            )
    return output


def coverage_states(
    source_seeds: Sequence[int],
    states_per_seed: int,
) -> list[sweep.HeldoutState]:
    return [
        sweep.HeldoutState(seed, index, state)
        for seed in source_seeds
        for index, state in enumerate(
            sweep.random_initial_states(seed, states_per_seed)
        )
    ]


def normalized_state_margin(state: np.ndarray) -> float:
    state = np.asarray(state, dtype=float)
    span = quad.SAFE_HIGH - quad.SAFE_LOW
    return float(
        max(
            np.max((state - quad.SAFE_HIGH) / span),
            np.max((quad.SAFE_LOW - state) / span),
        )
    )


def actuator_saturated(env: object) -> bool:
    return bool(
        np.max(
            np.abs(
                np.asarray(env.current_noisy_physical_action, dtype=float)
                - np.asarray(env.current_clipped_action, dtype=float)
            )
        )
        > 1e-9
    )


def run_physical_rollouts(
    bundle: quad.DynamicsBundle,
    snapshots: Sequence[SnapshotSpec],
    states: Sequence[sweep.HeldoutState],
    *,
    horizons: Sequence[int],
) -> tuple[
    list[PhysicalRollout],
    dict[
        tuple[int, str, int, int, int],
        tuple[float, int, float],
    ],
]:
    env = make("quadrotor", **dict(bundle.task_config))
    rows: list[PhysicalRollout] = []
    horizon_outcomes: dict[
        tuple[int, str, int, int, int],
        tuple[float, int, float],
    ] = {}
    steps = max(horizons)
    for spec in snapshots:
        for item in states:
            quad.set_quadrotor_initial_state(env, item.state)
            reset_seed = (
                spec.learner_seed * 100_000
                + item.source_seed * 100
                + item.source_index
            )
            observation, _info = env.reset(seed=reset_seed)
            first_violation: int | None = None
            rewards: list[float] = []
            margins: list[float] = []
            interface_errors: list[float] = []
            saturation_flags: list[int] = []
            saturation_steps = 0
            for step in range(steps):
                command = quad.policy_actions(
                    bundle,
                    np.asarray(observation, dtype=float).reshape(1, -1),
                    spec.snapshot,
                )[0]
                expected_action = np.clip(
                    command, bundle.action_low, bundle.action_high
                )
                observation, reward, _done, _info = env.step(command)
                rewards.append(float(reward))
                margins.append(
                    normalized_state_margin(np.asarray(env.state, dtype=float))
                )
                interface_errors.append(
                    float(
                        np.max(
                            np.abs(
                                np.asarray(
                                    env.current_clipped_action, dtype=float
                                )
                                - expected_action
                            )
                        )
                    )
                )
                saturated = int(actuator_saturated(env))
                saturation_flags.append(saturated)
                saturation_steps += saturated
                if (
                    quad.state_margins(
                        np.asarray(env.state, dtype=float)
                    )[0]
                    > 1e-9
                ):
                    first_violation = step
                    break
            state = np.asarray(item.state, dtype=float)
            rows.append(
                PhysicalRollout(
                    learner_seed=spec.learner_seed,
                    mechanism=spec.mechanism,
                    source_seed=item.source_seed,
                    source_index=item.source_index,
                    init_x=float(state[0]),
                    init_x_dot=float(state[1]),
                    init_z=float(state[2]),
                    init_z_dot=float(state[3]),
                    init_theta=float(state[4]),
                    init_theta_dot=float(state[5]),
                    steps_executed=len(rewards),
                    first_violation_step=first_violation,
                    mean_reward=float(np.mean(rewards)),
                    max_normalized_state_margin=float(np.max(margins)),
                    actuator_saturation_steps=saturation_steps,
                    max_action_interface_error=float(
                        np.max(interface_errors)
                    ),
                )
            )
            for horizon in horizons:
                executed = min(horizon, len(margins))
                horizon_outcomes[
                    (
                        spec.learner_seed,
                        spec.mechanism,
                        item.source_seed,
                        item.source_index,
                        horizon,
                    )
                ] = (
                    float(np.max(margins[:executed])),
                    int(sum(saturation_flags[:executed])),
                    float(np.max(interface_errors[:executed])),
                )
    env.close()
    return rows, horizon_outcomes


def casadi_outcomes(
    bundle: quad.DynamicsBundle,
    snapshots: Sequence[SnapshotSpec],
    states: Sequence[sweep.HeldoutState],
    horizons: Sequence[int],
) -> dict[tuple[int, str, int, int, int], tuple[int | None, float]]:
    output: dict[
        tuple[int, str, int, int, int], tuple[int | None, float]
    ] = {}
    snapshot_arrays = [spec.snapshot for spec in snapshots]
    state_arrays = [item.state for item in states]
    for horizon in horizons:
        first, margins = quad.casadi_snapshot_outcomes(
            bundle,
            snapshot_arrays,
            state_arrays,
            steps=horizon,
        )
        for spec_index, spec in enumerate(snapshots):
            for state_index, item in enumerate(states):
                first_value = int(first[spec_index, state_index])
                output[
                    (
                        spec.learner_seed,
                        spec.mechanism,
                        item.source_seed,
                        item.source_index,
                        horizon,
                    )
                ] = (
                    None if first_value < 0 else first_value,
                    float(margins[spec_index, state_index]),
                )
    return output


def classify(certificate_safe: bool, pybullet_safe: bool) -> str:
    if certificate_safe and pybullet_safe:
        return "true_acceptance"
    if certificate_safe and not pybullet_safe:
        return "false_acceptance"
    if not certificate_safe and pybullet_safe:
        return "false_rejection"
    return "true_rejection"


def paired_rows(
    physical: Sequence[PhysicalRollout],
    model: dict[
        tuple[int, str, int, int, int], tuple[int | None, float]
    ],
    physical_horizons: dict[
        tuple[int, str, int, int, int], tuple[float, int, float]
    ],
    horizons: Sequence[int],
    guards: Sequence[float],
) -> list[CoveragePair]:
    output: list[CoveragePair] = []
    for physical_row in physical:
        for horizon in horizons:
            key = (
                physical_row.learner_seed,
                physical_row.mechanism,
                physical_row.source_seed,
                physical_row.source_index,
                horizon,
            )
            casadi_first, casadi_margin = model[key]
            (
                physical_margin,
                saturation_steps,
                interface_error,
            ) = physical_horizons[key]
            pybullet_first = physical_row.first_violation_step
            pybullet_safe = bool(
                pybullet_first is None or pybullet_first >= horizon
            )
            for guard in guards:
                certificate_safe = bool(casadi_margin <= -guard)
                output.append(
                    CoveragePair(
                        learner_seed=physical_row.learner_seed,
                        mechanism=physical_row.mechanism,
                        source_seed=physical_row.source_seed,
                        source_index=physical_row.source_index,
                        horizon=horizon,
                        guard_margin=guard,
                        casadi_first_violation_step=casadi_first,
                        casadi_max_state_margin=casadi_margin,
                        certificate_safe=certificate_safe,
                        pybullet_first_violation_step=pybullet_first,
                        pybullet_safe=pybullet_safe,
                        pybullet_max_normalized_state_margin=physical_margin,
                        actuator_saturation_steps=saturation_steps,
                        max_action_interface_error=interface_error,
                        classification=classify(
                            certificate_safe, pybullet_safe
                        ),
                    )
                )
    return output


def aggregate_group(
    rows: Sequence[CoveragePair],
    learner_seed: str,
    mechanism: str,
    horizon: int,
    guard: float,
) -> CoverageAggregate:
    certified = [row for row in rows if row.certificate_safe]
    rejected = [row for row in rows if not row.certificate_safe]
    false_acceptances = sum(
        row.classification == "false_acceptance" for row in rows
    )
    false_rejections = sum(
        row.classification == "false_rejection" for row in rows
    )
    return CoverageAggregate(
        learner_seed=learner_seed,
        mechanism=mechanism,
        horizon=horizon,
        guard_margin=guard,
        evaluated_pairs=len(rows),
        certified_pairs=len(certified),
        rejected_pairs=len(rejected),
        pybullet_safe_pairs=sum(row.pybullet_safe for row in rows),
        true_acceptances=sum(
            row.classification == "true_acceptance" for row in rows
        ),
        false_acceptances=false_acceptances,
        true_rejections=sum(
            row.classification == "true_rejection" for row in rows
        ),
        false_rejections=false_rejections,
        certificate_coverage=len(certified) / len(rows),
        pybullet_safe_rate=sum(row.pybullet_safe for row in rows) / len(rows),
        false_acceptance_rate_certified=(
            false_acceptances / len(certified) if certified else 0.0
        ),
        false_rejection_rate_rejected=(
            false_rejections / len(rejected) if rejected else 0.0
        ),
        worst_pybullet_normalized_margin_certified=(
            float(
                np.max(
                    [
                        row.pybullet_max_normalized_state_margin
                        for row in certified
                    ]
                )
            )
            if certified
            else float("nan")
        ),
        max_action_interface_error=float(
            np.max([row.max_action_interface_error for row in rows])
        ),
    )


def aggregate_pairs(
    rows: Sequence[CoveragePair],
    learner_seeds: Sequence[int],
    horizons: Sequence[int],
    guards: Sequence[float],
) -> list[CoverageAggregate]:
    output: list[CoverageAggregate] = []
    for mechanism in MECHANISMS:
        for horizon in horizons:
            for guard in guards:
                pooled = [
                    row
                    for row in rows
                    if row.mechanism == mechanism
                    and row.horizon == horizon
                    and row.guard_margin == guard
                ]
                output.append(
                    aggregate_group(
                        pooled, "pooled", mechanism, horizon, guard
                    )
                )
                for seed in learner_seeds:
                    selected = [
                        row for row in pooled if row.learner_seed == seed
                    ]
                    output.append(
                        aggregate_group(
                            selected,
                            str(seed),
                            mechanism,
                            horizon,
                            guard,
                        )
                    )
    return output


def decide(
    rows: Sequence[CoveragePair],
    *,
    primary_horizon: int,
    primary_guard: float,
    minimum_coverage: float,
    interface_tolerance: float,
    casadi_runtime: float,
    pybullet_runtime: float,
) -> CoverageDecision:
    primary = [
        row
        for row in rows
        if row.horizon == primary_horizon
        and row.guard_margin == primary_guard
    ]
    if not primary:
        raise RuntimeError("primary configuration is absent from the grid")
    coverage: dict[str, float] = {}
    for mechanism in PRIMARY_COVERAGE_MECHANISMS:
        selected = [
            row for row in primary if row.mechanism == mechanism
        ]
        coverage[mechanism] = sum(
            row.certificate_safe for row in selected
        ) / len(selected)
    false_acceptances = sum(
        row.classification == "false_acceptance" for row in primary
    )
    max_interface_error = float(
        np.max([row.max_action_interface_error for row in primary])
    )
    coverage_pass = all(
        value >= minimum_coverage for value in coverage.values()
    )
    zero_false_acceptance = false_acceptances == 0
    interface_pass = max_interface_error <= interface_tolerance
    return CoverageDecision(
        primary_horizon=primary_horizon,
        primary_guard_margin=primary_guard,
        evaluated_pairs=len(primary),
        certified_pairs=sum(row.certificate_safe for row in primary),
        false_acceptances=false_acceptances,
        max_action_interface_error=max_interface_error,
        clean_coverage=coverage["clean_reinforce_snapshot"],
        commit_coverage=coverage["poisoned_commit_gate_snapshot"],
        freeze_coverage=coverage[
            "poisoned_always_freeze_snapshot"
        ],
        minimum_required_coverage=minimum_coverage,
        zero_false_acceptance=zero_false_acceptance,
        interface_audit_pass=interface_pass,
        coverage_pass=coverage_pass,
        primary_gate_pass=(
            zero_false_acceptance and interface_pass and coverage_pass
        ),
        casadi_runtime_seconds=casadi_runtime,
        pybullet_runtime_seconds=pybullet_runtime,
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--learner-seeds", nargs="+", type=int, default=[2040, 2041, 2042]
    )
    parser.add_argument(
        "--coverage-seeds", nargs="+", type=int, default=[4050, 4051, 4052]
    )
    parser.add_argument("--states-per-seed", type=int, default=48)
    parser.add_argument(
        "--horizons", nargs="+", type=int, default=[20, 50, 100]
    )
    parser.add_argument(
        "--guards",
        nargs="+",
        type=float,
        default=[0.0, 0.001, 0.003, 0.005, 0.01],
    )
    parser.add_argument("--primary-horizon", type=int, default=100)
    parser.add_argument("--primary-guard", type=float, default=0.003)
    parser.add_argument("--minimum-coverage", type=float, default=0.25)
    parser.add_argument("--interface-tolerance", type=float, default=1e-8)
    parser.add_argument("--snapshot-source", type=Path, default=SNAPSHOT_SOURCE)
    parser.add_argument("--trace-source", type=Path, default=TRACE_SOURCE)
    parser.add_argument(
        "--physical-out",
        type=Path,
        default=RESULTS / "safe_control_gym_quadrotor_certificate_coverage_physical.csv",
    )
    parser.add_argument(
        "--pairs-out",
        type=Path,
        default=RESULTS / "safe_control_gym_quadrotor_certificate_coverage_pairs.csv",
    )
    parser.add_argument(
        "--aggregate-out",
        type=Path,
        default=RESULTS / "safe_control_gym_quadrotor_certificate_coverage_aggregate.csv",
    )
    parser.add_argument(
        "--decision-out",
        type=Path,
        default=RESULTS / "safe_control_gym_quadrotor_certificate_coverage_decision.csv",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    horizons = sorted(set(args.horizons))
    guards = sorted(set(args.guards))
    if args.primary_horizon not in horizons:
        raise ValueError("primary horizon must be present in --horizons")
    if args.primary_guard not in guards:
        raise ValueError("primary guard must be present in --guards")
    snapshots = load_locked_snapshots(
        args.snapshot_source, args.trace_source, args.learner_seeds
    )
    states = coverage_states(args.coverage_seeds, args.states_per_seed)
    physical: list[PhysicalRollout] = []
    physical_horizons: dict[
        tuple[int, str, int, int, int], tuple[float, int, float]
    ] = {}
    model: dict[
        tuple[int, str, int, int, int], tuple[int | None, float]
    ] = {}
    casadi_runtime = 0.0
    pybullet_runtime = 0.0
    for seed in args.learner_seeds:
        bundle = quad.build_dynamics(seed)
        seed_snapshots = [
            spec for spec in snapshots if spec.learner_seed == seed
        ]
        print(
            f"learner_seed={seed}: {len(seed_snapshots)} snapshots x "
            f"{len(states)} unadmitted states",
            flush=True,
        )
        start = perf_counter()
        model.update(
            casadi_outcomes(bundle, seed_snapshots, states, horizons)
        )
        casadi_runtime += perf_counter() - start
        start = perf_counter()
        seed_physical, seed_horizon_outcomes = run_physical_rollouts(
            bundle,
            seed_snapshots,
            states,
            horizons=horizons,
        )
        physical.extend(seed_physical)
        physical_horizons.update(seed_horizon_outcomes)
        pybullet_runtime += perf_counter() - start
    pairs = paired_rows(
        physical, model, physical_horizons, horizons, guards
    )
    aggregates = aggregate_pairs(
        pairs, args.learner_seeds, horizons, guards
    )
    decision = decide(
        pairs,
        primary_horizon=args.primary_horizon,
        primary_guard=args.primary_guard,
        minimum_coverage=args.minimum_coverage,
        interface_tolerance=args.interface_tolerance,
        casadi_runtime=casadi_runtime,
        pybullet_runtime=pybullet_runtime,
    )
    write_csv(args.physical_out, physical)
    write_csv(args.pairs_out, pairs)
    write_csv(args.aggregate_out, aggregates)
    write_csv(args.decision_out, [decision])
    print(
        "primary "
        f"H={decision.primary_horizon} g={decision.primary_guard_margin}: "
        f"certified={decision.certified_pairs}/{decision.evaluated_pairs} "
        f"false_accept={decision.false_acceptances} "
        f"coverage clean/commit/freeze="
        f"{decision.clean_coverage:.3f}/"
        f"{decision.commit_coverage:.3f}/"
        f"{decision.freeze_coverage:.3f} "
        f"interface={decision.max_action_interface_error:.3e} "
        f"pass={decision.primary_gate_pass}",
        flush=True,
    )
    print(
        f"runtime CasADi={casadi_runtime:.2f}s "
        f"PyBullet={pybullet_runtime:.2f}s",
        flush=True,
    )


if __name__ == "__main__":
    main()
