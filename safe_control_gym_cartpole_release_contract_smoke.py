#!/usr/bin/env python3
"""Resident-authority versus permanent raw-release contract smoke.

The experiment intentionally gives both contracts the same locked poisoned
snapshot, initial states, and five-step reverse-switch evidence.  Only the
post-admission authority differs.
"""

from __future__ import annotations

import argparse
import csv
from dataclasses import asdict, dataclass
from functools import partial
from pathlib import Path
from statistics import median
from typing import Iterable

import numpy as np
from safe_control_gym.utils.registration import make

import safe_control_gym_delayed_trigger_attack as delayed
import safe_control_gym_plausible_set_lifecycle_gate as gate


ROOT = Path(__file__).resolve().parent
RESULTS = ROOT / "results"


@dataclass
class ContractRollout:
    contract: str
    state_index: int
    accepted_by_reverse_switch: bool
    reverse_switch_horizon: int
    reverse_switch_max_margin: float
    casadi_full_first_violation_step: int | None
    init_x: float
    init_x_dot: float
    init_theta: float
    init_theta_dot: float
    physical_steps: int
    physical_first_violation_step: int | None
    interventions: int
    empty_kernel_fallbacks: int
    mean_reward: float


@dataclass
class ContractSummary:
    contract: str
    candidate_states: int
    reverse_switch_accepted: int
    accepted_later_casadi_violations: int
    accepted_physical_violations: int
    resident_interventions: int
    empty_kernel_fallbacks: int
    median_physical_first_violation_step: float | None
    mean_reward: float


def read_locked_snapshot(path: Path) -> np.ndarray:
    with path.open(newline="") as source:
        rows = list(csv.DictReader(source))
    matching = [
        row for row in rows if row["mechanism"] == "poisoned_action_only_snapshot"
    ]
    if len(matching) != 1:
        raise RuntimeError(f"{path}: expected one poisoned action-only row")
    row = matching[0]
    return np.asarray(
        [float(row["pending_gain"]), float(row["pending_bias"])], dtype=float
    )


def write_csv(path: Path, rows: Iterable[object]) -> None:
    dictionaries = [asdict(row) for row in rows]
    if not dictionaries:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=list(dictionaries[0]))
        writer.writeheader()
        writer.writerows(dictionaries)


def singleton_casadi_kernel(
    state: np.ndarray,
    action_grid: np.ndarray,
    casadi_fd_func: object,
) -> gate.KernelResult:
    """Exact ``rho=0`` specialization without duplicate box corners."""

    next_states = gate.casadi_step_batch(
        casadi_fd_func,
        np.asarray(state, dtype=float).reshape(1, -1),
        np.asarray(action_grid, dtype=float),
    )
    valid_mask = np.all(
        next_states >= gate.SAFE_LOW[None, None, :], axis=(1, 2)
    )
    valid_mask &= np.all(
        next_states <= gate.SAFE_HIGH[None, None, :], axis=(1, 2)
    )
    valid = [
        float(action)
        for action in np.asarray(action_grid, dtype=float)[valid_mask]
    ]
    if not valid:
        return gate.KernelResult(None, tuple(), 0.0, "no_common_action")
    return gate.KernelResult(
        (min(valid), max(valid)),
        tuple(valid),
        max(valid) - min(valid),
        "",
    )


def physical_rollout(
    contract: str,
    params: np.ndarray,
    initial_state: np.ndarray,
    *,
    state_index: int,
    accepted: bool,
    reverse_switch_horizon: int,
    reverse_switch_max_margin: float,
    casadi_full_first_violation_step: int | None,
    seed: int,
    deployment_steps: int,
    action_grid_size: int,
) -> ContractRollout:
    task_config, lqr_config, _cbf_config = gate.build_configs(seed)
    task_config["init_state"] = np.asarray(initial_state, dtype=float)
    env_func = partial(make, "cartpole", **task_config)
    env = env_func(gui=False)
    ctrl = make("lqr", env_func, **lqr_config)
    ctrl.reset()
    observation, info = env.reset(seed=seed)
    ctrl.reset_before_run(observation, info, env=env)
    action_low = float(np.asarray(env.action_space.low).reshape(-1)[0])
    action_high = float(np.asarray(env.action_space.high).reshape(-1)[0])
    action_grid = np.linspace(action_low, action_high, action_grid_size)
    model = gate.make_model_from_env(env)
    casadi_fd_func = env.symbolic.fd_func

    rewards: list[float] = []
    interventions = 0
    empty_fallbacks = 0
    first_violation: int | None = None
    if accepted:
        for step in range(deployment_steps):
            state = np.asarray(observation, dtype=float)
            raw_action = gate.total_policy_action(ctrl, state, info, params)
            raw_action = float(np.clip(raw_action, action_low, action_high))
            action = raw_action
            if contract == "resident_authority":
                kernel = singleton_casadi_kernel(
                    state,
                    action_grid,
                    casadi_fd_func,
                )
                if kernel.interval is None:
                    action = float(
                        np.clip(
                            gate.lqr_action(ctrl, state, info),
                            action_low,
                            action_high,
                        )
                    )
                    empty_fallbacks += 1
                    interventions += int(abs(action - raw_action) > 1e-9)
                else:
                    lower, upper = kernel.interval
                    if not (lower <= raw_action <= upper):
                        action, accepted_action, _correction = gate.project_to_kernel(
                            raw_action, kernel
                        )
                        if not accepted_action:
                            raise RuntimeError("nonempty kernel rejected projection")
                        interventions += 1
            observation, reward, done, info = env.step(np.asarray([action]))
            rewards.append(float(reward))
            violation = bool(info.get("constraint_violation", False))
            if violation and first_violation is None:
                first_violation = step
            if done:
                break

    ctrl.close()
    env.close()
    return ContractRollout(
        contract=contract,
        state_index=state_index,
        accepted_by_reverse_switch=accepted,
        reverse_switch_horizon=reverse_switch_horizon,
        reverse_switch_max_margin=reverse_switch_max_margin,
        casadi_full_first_violation_step=casadi_full_first_violation_step,
        init_x=float(initial_state[0]),
        init_x_dot=float(initial_state[1]),
        init_theta=float(initial_state[2]),
        init_theta_dot=float(initial_state[3]),
        physical_steps=len(rewards),
        physical_first_violation_step=first_violation,
        interventions=interventions,
        empty_kernel_fallbacks=empty_fallbacks,
        mean_reward=float(np.mean(rewards)) if rewards else 0.0,
    )


def summarize(contract: str, rows: list[ContractRollout]) -> ContractSummary:
    accepted = [row for row in rows if row.accepted_by_reverse_switch]
    physical_first = [
        row.physical_first_violation_step
        for row in accepted
        if row.physical_first_violation_step is not None
    ]
    return ContractSummary(
        contract=contract,
        candidate_states=len(rows),
        reverse_switch_accepted=len(accepted),
        accepted_later_casadi_violations=sum(
            row.casadi_full_first_violation_step is not None for row in accepted
        ),
        accepted_physical_violations=len(physical_first),
        resident_interventions=sum(row.interventions for row in accepted),
        empty_kernel_fallbacks=sum(row.empty_kernel_fallbacks for row in accepted),
        median_physical_first_violation_step=(
            float(median(physical_first)) if physical_first else None
        ),
        mean_reward=(
            float(np.mean([row.mean_reward for row in accepted]))
            if accepted
            else 0.0
        ),
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, default=2040)
    parser.add_argument("--reverse-switch-horizon", type=int, default=5)
    parser.add_argument("--deployment-steps", type=int, default=120)
    parser.add_argument("--action-grid-size", type=int, default=41)
    parser.add_argument(
        "--snapshot-source",
        type=Path,
        default=RESULTS / "safe_control_gym_reinforce_reward_poisoning.csv",
    )
    parser.add_argument(
        "--rollouts-out",
        type=Path,
        default=RESULTS / "cartpole_release_contract_smoke_rollouts.csv",
    )
    parser.add_argument(
        "--summary-out",
        type=Path,
        default=RESULTS / "cartpole_release_contract_smoke_summary.csv",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    params = read_locked_snapshot(args.snapshot_source)
    states = delayed.deployment_envelope()

    task_config, lqr_config, _cbf_config = gate.build_configs(args.seed)
    env_func = partial(make, "cartpole", **task_config)
    env = env_func(gui=False)
    ctrl = make("lqr", env_func, **lqr_config)
    ctrl.reset()
    observation, info = env.reset(seed=args.seed)
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
        deployment_steps=args.reverse_switch_horizon,
    )
    full_first, _full_margins = delayed.casadi_deployment_outcomes(
        ctrl,
        info,
        env.symbolic.fd_func,
        params,
        states,
        action_low=action_low,
        action_high=action_high,
        deployment_steps=args.deployment_steps,
    )
    ctrl.close()
    env.close()

    rows: list[ContractRollout] = []
    for contract in ("permanent_release", "resident_authority"):
        for index, state in enumerate(states):
            accepted = bool(short_first[index] < 0 and short_margins[index] <= 0.0)
            rows.append(
                physical_rollout(
                    contract,
                    params,
                    state,
                    state_index=index,
                    accepted=accepted,
                    reverse_switch_horizon=args.reverse_switch_horizon,
                    reverse_switch_max_margin=float(short_margins[index]),
                    casadi_full_first_violation_step=(
                        int(full_first[index]) if full_first[index] >= 0 else None
                    ),
                    seed=args.seed,
                    deployment_steps=args.deployment_steps,
                    action_grid_size=args.action_grid_size,
                )
            )

    summaries = [
        summarize(contract, [row for row in rows if row.contract == contract])
        for contract in ("permanent_release", "resident_authority")
    ]
    write_csv(args.rollouts_out, rows)
    write_csv(args.summary_out, summaries)

    print(
        "| contract | accepted | later CasADi violations | physical violations | "
        "interventions | empty fallbacks | median first | reward |"
    )
    print("|---|---:|---:|---:|---:|---:|---:|---:|")
    for row in summaries:
        first = (
            "NA"
            if row.median_physical_first_violation_step is None
            else f"{row.median_physical_first_violation_step:.1f}"
        )
        print(
            f"| {row.contract} | {row.reverse_switch_accepted}/"
            f"{row.candidate_states} | {row.accepted_later_casadi_violations} | "
            f"{row.accepted_physical_violations} | "
            f"{row.resident_interventions} | {row.empty_kernel_fallbacks} | "
            f"{first} | {row.mean_reward:.4f} |"
        )
    print(f"wrote {args.rollouts_out}")
    print(f"wrote {args.summary_out}")


if __name__ == "__main__":
    main()
