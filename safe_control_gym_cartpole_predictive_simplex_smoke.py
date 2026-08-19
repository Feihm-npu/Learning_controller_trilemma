#!/usr/bin/env python3
"""Repeated predictive monitoring versus permanent raw release."""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
from functools import partial
from pathlib import Path
from statistics import median

import numpy as np
from safe_control_gym.utils.registration import make

import safe_control_gym_cartpole_release_contract_smoke as contract
import safe_control_gym_delayed_trigger_attack as delayed
import safe_control_gym_plausible_set_lifecycle_gate as gate


ROOT = Path(__file__).resolve().parent
RESULTS = ROOT / "results"


@dataclass
class PredictiveRollout:
    contract: str
    state_index: int
    initial_reverse_switch_accepted: bool
    reverse_switch_horizon: int
    init_x: float
    init_x_dot: float
    init_theta: float
    init_theta_dot: float
    casadi_full_first_violation_step: int | None
    physical_steps: int
    physical_first_violation_step: int | None
    forward_switch_step: int | None
    baseline_control_steps: int
    mean_reward: float


@dataclass
class PredictiveSummary:
    contract: str
    candidate_states: int
    initially_accepted: int
    accepted_later_casadi_violations: int
    accepted_physical_violations: int
    states_with_forward_switch: int
    baseline_control_steps: int
    median_forward_switch_step: float | None
    median_physical_first_violation_step: float | None
    mean_reward: float


def run_rollout(
    contract_name: str,
    params: np.ndarray,
    initial_state: np.ndarray,
    *,
    state_index: int,
    initially_accepted: bool,
    casadi_full_first_violation_step: int | None,
    seed: int,
    monitor_horizon: int,
    deployment_steps: int,
) -> PredictiveRollout:
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
    casadi_fd_func = env.symbolic.fd_func

    switched = False
    forward_switch_step: int | None = None
    baseline_steps = 0
    first_violation: int | None = None
    rewards: list[float] = []
    if initially_accepted:
        for step in range(deployment_steps):
            state = np.asarray(observation, dtype=float)
            if contract_name == "resident_predictive_simplex" and not switched:
                predicted_first, _predicted_margins = (
                    delayed.casadi_deployment_outcomes(
                        ctrl,
                        info,
                        casadi_fd_func,
                        params,
                        [state],
                        action_low=action_low,
                        action_high=action_high,
                        deployment_steps=monitor_horizon,
                    )
                )
                if predicted_first[0] >= 0:
                    switched = True
                    forward_switch_step = step

            if switched:
                action = float(
                    np.clip(
                        gate.lqr_action(ctrl, state, info),
                        action_low,
                        action_high,
                    )
                )
                baseline_steps += 1
            else:
                action = float(
                    np.clip(
                        gate.total_policy_action(ctrl, state, info, params),
                        action_low,
                        action_high,
                    )
                )
            observation, reward, done, info = env.step(np.asarray([action]))
            rewards.append(float(reward))
            violation = bool(info.get("constraint_violation", False))
            if violation and first_violation is None:
                first_violation = step
            if done:
                break

    ctrl.close()
    env.close()
    return PredictiveRollout(
        contract=contract_name,
        state_index=state_index,
        initial_reverse_switch_accepted=initially_accepted,
        reverse_switch_horizon=monitor_horizon,
        init_x=float(initial_state[0]),
        init_x_dot=float(initial_state[1]),
        init_theta=float(initial_state[2]),
        init_theta_dot=float(initial_state[3]),
        casadi_full_first_violation_step=casadi_full_first_violation_step,
        physical_steps=len(rewards),
        physical_first_violation_step=first_violation,
        forward_switch_step=forward_switch_step,
        baseline_control_steps=baseline_steps,
        mean_reward=float(np.mean(rewards)) if rewards else 0.0,
    )


def summarize(name: str, rows: list[PredictiveRollout]) -> PredictiveSummary:
    accepted = [row for row in rows if row.initial_reverse_switch_accepted]
    first = [
        row.physical_first_violation_step
        for row in accepted
        if row.physical_first_violation_step is not None
    ]
    switches = [
        row.forward_switch_step
        for row in accepted
        if row.forward_switch_step is not None
    ]
    return PredictiveSummary(
        contract=name,
        candidate_states=len(rows),
        initially_accepted=len(accepted),
        accepted_later_casadi_violations=sum(
            row.casadi_full_first_violation_step is not None for row in accepted
        ),
        accepted_physical_violations=len(first),
        states_with_forward_switch=len(switches),
        baseline_control_steps=sum(row.baseline_control_steps for row in accepted),
        median_forward_switch_step=(
            float(median(switches)) if switches else None
        ),
        median_physical_first_violation_step=(
            float(median(first)) if first else None
        ),
        mean_reward=float(np.mean([row.mean_reward for row in accepted])),
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, default=2040)
    parser.add_argument("--monitor-horizon", type=int, default=5)
    parser.add_argument("--deployment-steps", type=int, default=120)
    parser.add_argument(
        "--snapshot-source",
        type=Path,
        default=RESULTS / "safe_control_gym_reinforce_reward_poisoning.csv",
    )
    parser.add_argument(
        "--rollouts-out",
        type=Path,
        default=RESULTS / "cartpole_predictive_simplex_smoke_rollouts.csv",
    )
    parser.add_argument(
        "--summary-out",
        type=Path,
        default=RESULTS / "cartpole_predictive_simplex_smoke_summary.csv",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    params = contract.read_locked_snapshot(args.snapshot_source)
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
        deployment_steps=args.monitor_horizon,
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

    rows: list[PredictiveRollout] = []
    names = ("permanent_release", "resident_predictive_simplex")
    for name in names:
        for index, state in enumerate(states):
            accepted = bool(short_first[index] < 0 and short_margins[index] <= 0.0)
            rows.append(
                run_rollout(
                    name,
                    params,
                    state,
                    state_index=index,
                    initially_accepted=accepted,
                    casadi_full_first_violation_step=(
                        int(full_first[index]) if full_first[index] >= 0 else None
                    ),
                    seed=args.seed,
                    monitor_horizon=args.monitor_horizon,
                    deployment_steps=args.deployment_steps,
                )
            )

    summaries = [
        summarize(name, [row for row in rows if row.contract == name])
        for name in names
    ]
    contract.write_csv(args.rollouts_out, rows)
    contract.write_csv(args.summary_out, summaries)

    print(
        "| contract | accepted | later CasADi violations | physical violations | "
        "forward switches | baseline steps | median switch | median failure |"
    )
    print("|---|---:|---:|---:|---:|---:|---:|---:|")
    for row in summaries:
        switch = (
            "NA"
            if row.median_forward_switch_step is None
            else f"{row.median_forward_switch_step:.1f}"
        )
        failure = (
            "NA"
            if row.median_physical_first_violation_step is None
            else f"{row.median_physical_first_violation_step:.1f}"
        )
        print(
            f"| {row.contract} | {row.initially_accepted}/"
            f"{row.candidate_states} | {row.accepted_later_casadi_violations} | "
            f"{row.accepted_physical_violations} | "
            f"{row.states_with_forward_switch} | {row.baseline_control_steps} | "
            f"{switch} | {failure} |"
        )
    print(f"wrote {args.rollouts_out}")
    print(f"wrote {args.summary_out}")


if __name__ == "__main__":
    main()

