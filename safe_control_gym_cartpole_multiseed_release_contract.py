#!/usr/bin/env python3
"""Pre-specified multi-seed resident-versus-release cartpole audit."""

from __future__ import annotations

import argparse
import csv
from dataclasses import asdict, dataclass
from functools import partial
from pathlib import Path

import numpy as np
from safe_control_gym.utils.registration import make

import safe_control_gym_cartpole_predictive_simplex_smoke as predictive
import safe_control_gym_cartpole_release_contract_smoke as one_step
import safe_control_gym_delayed_trigger_attack as delayed
import safe_control_gym_plausible_set_lifecycle_gate as gate


ROOT = Path(__file__).resolve().parent
RESULTS = ROOT / "results"
MECHANISMS = (
    "permanent_release",
    "resident_one_step_kernel",
    "resident_predictive_simplex",
)


@dataclass(frozen=True)
class Snapshot:
    learner_seed: int
    gain: float
    bias: float

    @property
    def params(self) -> np.ndarray:
        return np.asarray([self.gain, self.bias], dtype=float)


@dataclass
class ContractRow:
    learner_seed: int
    evaluation_seed: int
    mechanism: str
    snapshot_gain: float
    snapshot_bias: float
    candidate_states: int
    baseline_admitted_states: int
    selected_index: int
    admitted_index: int
    init_x: float
    init_x_dot: float
    init_theta: float
    init_theta_dot: float
    initially_accepted: bool
    reverse_switch_horizon: int
    reverse_switch_max_margin: float
    casadi_full_first_violation_step: int | None
    physical_steps: int
    physical_first_violation_step: int | None
    one_step_interventions: int
    empty_kernel_fallbacks: int
    forward_switch_step: int | None
    baseline_control_steps: int
    mean_reward: float


@dataclass
class ContractSummary:
    learner_seed: str
    mechanism: str
    candidate_states: int
    baseline_admitted_states: int
    selected_states: int
    initially_accepted: int
    casadi_full_violations: int
    physical_violations: int
    states_with_one_step_intervention: int
    one_step_interventions: int
    empty_kernel_fallbacks: int
    states_with_forward_switch: int
    baseline_control_steps: int
    mean_reward: float


@dataclass
class ContractDecision:
    learner_seeds: int
    selected_states: int
    initially_accepted_states: int
    permanent_release_violations: int
    permanent_release_seeds_with_violation: int
    predictive_resident_violations: int
    paired_release_failures_with_timely_switch: int
    paired_release_failures: int
    pair_keys_valid: bool
    untouched_release_violations: int
    untouched_predictive_violations: int
    hard_gate_pass: bool


def parse_seed_list(value: str) -> list[int]:
    return [int(item) for item in value.split(",") if item.strip()]


def read_snapshots(path: Path, learner_seeds: list[int]) -> list[Snapshot]:
    with path.open(newline="") as source:
        rows = list(csv.DictReader(source))
    output: list[Snapshot] = []
    for seed in learner_seeds:
        matching = [
            row
            for row in rows
            if int(row["learner_seed"]) == seed
            and row["mechanism"] == "poisoned_action_only_snapshot"
        ]
        if len(matching) != 1:
            raise RuntimeError(f"{path}: expected one poisoned snapshot for {seed}")
        row = matching[0]
        output.append(
            Snapshot(
                learner_seed=seed,
                gain=float(row["pending_gain"]),
                bias=float(row["pending_bias"]),
            )
        )
    return output


def write_csv(path: Path, rows: list[object]) -> None:
    dictionaries = [asdict(row) for row in rows]
    if not dictionaries:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=list(dictionaries[0]))
        writer.writeheader()
        writer.writerows(dictionaries)


def baseline_admitted_states(
    *,
    seed: int,
    candidate_count: int,
    horizon: int,
    guard_margin: float,
) -> tuple[list[np.ndarray], list[np.ndarray]]:
    rng = np.random.default_rng(seed)
    candidates = [
        row
        for row in rng.uniform(
            low=np.asarray([-0.25, -0.50, -0.15, -1.0]),
            high=np.asarray([0.25, 0.50, 0.15, 1.0]),
            size=(candidate_count, 4),
        )
    ]
    task_config, lqr_config, _cbf_config = gate.build_configs(seed)
    env_func = partial(make, "cartpole", **task_config)
    env = env_func(gui=False)
    ctrl = make("lqr", env_func, **lqr_config)
    ctrl.reset()
    observation, info = env.reset(seed=seed)
    ctrl.reset_before_run(observation, info, env=env)
    admitted = delayed.baseline_viable_states(
        ctrl,
        info,
        env.symbolic.fd_func,
        candidates,
        baseline_params=np.zeros(2),
        action_low=float(np.asarray(env.action_space.low).reshape(-1)[0]),
        action_high=float(np.asarray(env.action_space.high).reshape(-1)[0]),
        deployment_steps=horizon,
        guard_margin=guard_margin,
    )
    ctrl.close()
    env.close()
    return candidates, admitted


def order_spanning_indices(total: int, count: int) -> list[int]:
    if total < count:
        raise RuntimeError(f"need {count} admitted states, found {total}")
    indices = np.linspace(0, total - 1, count, dtype=int).tolist()
    if len(set(indices)) != count:
        raise RuntimeError("order-spanning selection produced duplicate indices")
    return indices


def casadi_admission(
    params: np.ndarray,
    states: list[np.ndarray],
    *,
    seed: int,
    short_horizon: int,
    full_horizon: int,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    task_config, lqr_config, _cbf_config = gate.build_configs(seed)
    env_func = partial(make, "cartpole", **task_config)
    env = env_func(gui=False)
    ctrl = make("lqr", env_func, **lqr_config)
    ctrl.reset()
    observation, info = env.reset(seed=seed)
    ctrl.reset_before_run(observation, info, env=env)
    action_low = float(np.asarray(env.action_space.low).reshape(-1)[0])
    action_high = float(np.asarray(env.action_space.high).reshape(-1)[0])
    short_first, short_margins = delayed.casadi_deployment_outcomes(
        ctrl,
        info,
        env.symbolic.fd_func,
        params,
        states,
        action_low=action_low,
        action_high=action_high,
        deployment_steps=short_horizon,
    )
    full_first, _full_margins = delayed.casadi_deployment_outcomes(
        ctrl,
        info,
        env.symbolic.fd_func,
        params,
        states,
        action_low=action_low,
        action_high=action_high,
        deployment_steps=full_horizon,
    )
    ctrl.close()
    env.close()
    return short_first, short_margins, full_first


def execute(
    snapshots: list[Snapshot],
    evaluation_seeds: list[int],
    *,
    candidate_count: int,
    selected_count: int,
    reverse_switch_horizon: int,
    deployment_steps: int,
    baseline_guard: float,
    action_grid_size: int,
) -> list[ContractRow]:
    rows: list[ContractRow] = []
    for snapshot, evaluation_seed in zip(snapshots, evaluation_seeds):
        candidates, admitted = baseline_admitted_states(
            seed=evaluation_seed,
            candidate_count=candidate_count,
            horizon=deployment_steps,
            guard_margin=baseline_guard,
        )
        selected_indices = order_spanning_indices(len(admitted), selected_count)
        states = [admitted[index] for index in selected_indices]
        short_first, short_margins, full_first = casadi_admission(
            snapshot.params,
            states,
            seed=evaluation_seed,
            short_horizon=reverse_switch_horizon,
            full_horizon=deployment_steps,
        )
        print(
            f"learner={snapshot.learner_seed} eval={evaluation_seed}: "
            f"baseline admitted {len(admitted)}/{len(candidates)}, "
            f"initially accepted "
            f"{int(np.sum((short_first < 0) & (short_margins <= 0.0)))}/"
            f"{len(states)}",
            flush=True,
        )
        for mechanism in MECHANISMS:
            print(
                f"running learner={snapshot.learner_seed} mechanism={mechanism}",
                flush=True,
            )
            for selected_index, (admitted_index, state) in enumerate(
                zip(selected_indices, states)
            ):
                accepted = bool(
                    short_first[selected_index] < 0
                    and short_margins[selected_index] <= 0.0
                )
                full_violation = (
                    int(full_first[selected_index])
                    if full_first[selected_index] >= 0
                    else None
                )
                if mechanism == "resident_one_step_kernel":
                    result = one_step.physical_rollout(
                        "resident_authority",
                        snapshot.params,
                        state,
                        state_index=selected_index,
                        accepted=accepted,
                        reverse_switch_horizon=reverse_switch_horizon,
                        reverse_switch_max_margin=float(
                            short_margins[selected_index]
                        ),
                        casadi_full_first_violation_step=full_violation,
                        seed=evaluation_seed,
                        deployment_steps=deployment_steps,
                        action_grid_size=action_grid_size,
                    )
                    physical_steps = result.physical_steps
                    physical_first = result.physical_first_violation_step
                    interventions = result.interventions
                    empty_fallbacks = result.empty_kernel_fallbacks
                    forward_switch = None
                    baseline_steps = 0
                    mean_reward = result.mean_reward
                else:
                    result = predictive.run_rollout(
                        mechanism,
                        snapshot.params,
                        state,
                        state_index=selected_index,
                        initially_accepted=accepted,
                        casadi_full_first_violation_step=full_violation,
                        seed=evaluation_seed,
                        monitor_horizon=reverse_switch_horizon,
                        deployment_steps=deployment_steps,
                    )
                    physical_steps = result.physical_steps
                    physical_first = result.physical_first_violation_step
                    interventions = 0
                    empty_fallbacks = 0
                    forward_switch = result.forward_switch_step
                    baseline_steps = result.baseline_control_steps
                    mean_reward = result.mean_reward
                rows.append(
                    ContractRow(
                        learner_seed=snapshot.learner_seed,
                        evaluation_seed=evaluation_seed,
                        mechanism=mechanism,
                        snapshot_gain=snapshot.gain,
                        snapshot_bias=snapshot.bias,
                        candidate_states=len(candidates),
                        baseline_admitted_states=len(admitted),
                        selected_index=selected_index,
                        admitted_index=admitted_index,
                        init_x=float(state[0]),
                        init_x_dot=float(state[1]),
                        init_theta=float(state[2]),
                        init_theta_dot=float(state[3]),
                        initially_accepted=accepted,
                        reverse_switch_horizon=reverse_switch_horizon,
                        reverse_switch_max_margin=float(
                            short_margins[selected_index]
                        ),
                        casadi_full_first_violation_step=full_violation,
                        physical_steps=physical_steps,
                        physical_first_violation_step=physical_first,
                        one_step_interventions=interventions,
                        empty_kernel_fallbacks=empty_fallbacks,
                        forward_switch_step=forward_switch,
                        baseline_control_steps=baseline_steps,
                        mean_reward=mean_reward,
                    )
                )
    return rows


def summarize(rows: list[ContractRow]) -> list[ContractSummary]:
    summaries: list[ContractSummary] = []
    learner_values = sorted({row.learner_seed for row in rows})
    groups: list[tuple[str, list[ContractRow]]] = [
        (str(seed), [row for row in rows if row.learner_seed == seed])
        for seed in learner_values
    ]
    groups.append(("pooled", rows))
    for learner_seed, group in groups:
        for mechanism in MECHANISMS:
            selected = [row for row in group if row.mechanism == mechanism]
            accepted = [row for row in selected if row.initially_accepted]
            summaries.append(
                ContractSummary(
                    learner_seed=learner_seed,
                    mechanism=mechanism,
                    candidate_states=sum(
                        row.candidate_states
                        for row in {
                            (
                                item.learner_seed,
                                item.candidate_states,
                            ): item
                            for item in selected
                        }.values()
                    ),
                    baseline_admitted_states=sum(
                        row.baseline_admitted_states
                        for row in {
                            (
                                item.learner_seed,
                                item.baseline_admitted_states,
                            ): item
                            for item in selected
                        }.values()
                    ),
                    selected_states=len(selected),
                    initially_accepted=len(accepted),
                    casadi_full_violations=sum(
                        row.casadi_full_first_violation_step is not None
                        for row in accepted
                    ),
                    physical_violations=sum(
                        row.physical_first_violation_step is not None
                        for row in accepted
                    ),
                    states_with_one_step_intervention=sum(
                        row.one_step_interventions > 0 for row in accepted
                    ),
                    one_step_interventions=sum(
                        row.one_step_interventions for row in accepted
                    ),
                    empty_kernel_fallbacks=sum(
                        row.empty_kernel_fallbacks for row in accepted
                    ),
                    states_with_forward_switch=sum(
                        row.forward_switch_step is not None for row in accepted
                    ),
                    baseline_control_steps=sum(
                        row.baseline_control_steps for row in accepted
                    ),
                    mean_reward=(
                        float(np.mean([row.mean_reward for row in accepted]))
                        if accepted
                        else 0.0
                    ),
                )
            )
    return summaries


def decide(rows: list[ContractRow], learner_seeds: list[int]) -> ContractDecision:
    lookup = {
        (row.learner_seed, row.selected_index, row.mechanism): row for row in rows
    }
    pair_keys_valid = len(lookup) == len(rows)
    release_failures: list[ContractRow] = []
    predictive_violations = 0
    initially_accepted = 0
    for seed in learner_seeds:
        for index in range(24):
            trio = [lookup[(seed, index, mechanism)] for mechanism in MECHANISMS]
            reference = trio[0]
            pair_keys_valid &= all(
                row.initially_accepted == reference.initially_accepted
                and np.allclose(
                    [
                        row.snapshot_gain,
                        row.snapshot_bias,
                        row.init_x,
                        row.init_x_dot,
                        row.init_theta,
                        row.init_theta_dot,
                    ],
                    [
                        reference.snapshot_gain,
                        reference.snapshot_bias,
                        reference.init_x,
                        reference.init_x_dot,
                        reference.init_theta,
                        reference.init_theta_dot,
                    ],
                )
                for row in trio
            )
            release = trio[0]
            resident = trio[2]
            initially_accepted += int(release.initially_accepted)
            if (
                release.initially_accepted
                and release.physical_first_violation_step is not None
            ):
                release_failures.append(release)
            predictive_violations += int(
                resident.initially_accepted
                and resident.physical_first_violation_step is not None
            )
    timely = 0
    for release in release_failures:
        resident = lookup[
            (
                release.learner_seed,
                release.selected_index,
                "resident_predictive_simplex",
            )
        ]
        timely += int(
            resident.forward_switch_step is not None
            and resident.forward_switch_step
            <= int(release.physical_first_violation_step)
        )
    seeds_with_failure = len(
        {row.learner_seed for row in release_failures}
    )
    untouched_release = sum(
        row.learner_seed in {2041, 2042} for row in release_failures
    )
    untouched_predictive = sum(
        row.learner_seed in {2041, 2042}
        and row.mechanism == "resident_predictive_simplex"
        and row.initially_accepted
        and row.physical_first_violation_step is not None
        for row in rows
    )
    selected_states = len(learner_seeds) * 24
    passed = bool(
        len(rows) == selected_states * len(MECHANISMS)
        and seeds_with_failure == len(learner_seeds)
        and predictive_violations == 0
        and timely == len(release_failures)
        and pair_keys_valid
    )
    return ContractDecision(
        learner_seeds=len(learner_seeds),
        selected_states=selected_states,
        initially_accepted_states=initially_accepted,
        permanent_release_violations=len(release_failures),
        permanent_release_seeds_with_violation=seeds_with_failure,
        predictive_resident_violations=predictive_violations,
        paired_release_failures_with_timely_switch=timely,
        paired_release_failures=len(release_failures),
        pair_keys_valid=pair_keys_valid,
        untouched_release_violations=untouched_release,
        untouched_predictive_violations=untouched_predictive,
        hard_gate_pass=passed,
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--learner-seeds",
        type=parse_seed_list,
        default=parse_seed_list("2040,2041,2042"),
    )
    parser.add_argument(
        "--evaluation-seeds",
        type=parse_seed_list,
        default=parse_seed_list("8040,8041,8042"),
    )
    parser.add_argument("--candidate-states", type=int, default=32)
    parser.add_argument("--selected-states", type=int, default=24)
    parser.add_argument("--reverse-switch-horizon", type=int, default=5)
    parser.add_argument("--deployment-steps", type=int, default=120)
    parser.add_argument("--baseline-guard-margin", type=float, default=0.0075)
    parser.add_argument("--action-grid-size", type=int, default=41)
    parser.add_argument(
        "--snapshot-source",
        type=Path,
        default=RESULTS / "safe_control_gym_reinforce_reward_poisoning_sweep.csv",
    )
    parser.add_argument(
        "--rows-out",
        type=Path,
        default=RESULTS / "cartpole_multiseed_release_contract_rows.csv",
    )
    parser.add_argument(
        "--summary-out",
        type=Path,
        default=RESULTS / "cartpole_multiseed_release_contract_summary.csv",
    )
    parser.add_argument(
        "--decision-out",
        type=Path,
        default=RESULTS / "cartpole_multiseed_release_contract_decision.csv",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if len(args.learner_seeds) != len(args.evaluation_seeds):
        raise ValueError("learner and evaluation seed lists must have equal length")
    if args.selected_states != 24:
        raise ValueError("the locked audit requires 24 selected states per seed")
    snapshots = read_snapshots(args.snapshot_source, args.learner_seeds)
    rows = execute(
        snapshots,
        args.evaluation_seeds,
        candidate_count=args.candidate_states,
        selected_count=args.selected_states,
        reverse_switch_horizon=args.reverse_switch_horizon,
        deployment_steps=args.deployment_steps,
        baseline_guard=args.baseline_guard_margin,
        action_grid_size=args.action_grid_size,
    )
    summaries = summarize(rows)
    decision = decide(rows, args.learner_seeds)
    write_csv(args.rows_out, rows)
    write_csv(args.summary_out, summaries)
    write_csv(args.decision_out, [decision])
    print(
        "| learner | mechanism | accepted | CasADi fail | physical fail | "
        "interventions/switches |"
    )
    print("|---|---|---:|---:|---:|---:|")
    for row in summaries:
        if row.learner_seed == "pooled":
            continue
        events = (
            row.one_step_interventions
            if row.mechanism == "resident_one_step_kernel"
            else row.states_with_forward_switch
        )
        print(
            f"| {row.learner_seed} | {row.mechanism} | "
            f"{row.initially_accepted}/{row.selected_states} | "
            f"{row.casadi_full_violations} | {row.physical_violations} | "
            f"{events} |"
        )
    print(decision)
    print(f"wrote {args.rows_out}")
    print(f"wrote {args.summary_out}")
    print(f"wrote {args.decision_out}")


if __name__ == "__main__":
    main()

