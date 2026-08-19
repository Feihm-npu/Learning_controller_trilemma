#!/usr/bin/env python3
"""Gate-aware target selection audit for the locked cartpole reward attack."""

from __future__ import annotations

import argparse
import csv
from dataclasses import asdict, dataclass
from functools import partial
from itertools import product
from pathlib import Path

import numpy as np
from safe_control_gym.utils.registration import make

import safe_control_gym_delayed_trigger_attack as delayed
import safe_control_gym_plausible_set_lifecycle_gate as gate


ROOT = Path(__file__).resolve().parent
RESULTS = ROOT / "results"


@dataclass
class TargetCandidate:
    gain: float
    bias: float
    gate_horizon: int
    gate_violating_states: int
    gate_max_margin: float
    gate_accepted: bool
    full_horizon: int
    full_violating_states: int
    full_max_margin: float
    post_gate_failure_score: int
    selected: bool


@dataclass
class EvasionDecision:
    selected_target_gain: float
    selected_target_bias: float
    locked_target_gain: float
    locked_target_bias: float
    target_matches_locked: bool
    learned_gain: float
    learned_bias: float
    learned_gate_accepted_states: int
    candidate_states: int
    learned_full_casadi_violations: int
    learned_physical_violations: int
    resident_physical_violations: int
    gate_aware_smoke_pass: bool


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as source:
        return list(csv.DictReader(source))


def write_csv(path: Path, rows: list[object]) -> None:
    dictionaries = [asdict(row) for row in rows]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=list(dictionaries[0]))
        writer.writeheader()
        writer.writerows(dictionaries)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, default=2040)
    parser.add_argument("--gate-horizon", type=int, default=5)
    parser.add_argument("--full-horizon", type=int, default=120)
    parser.add_argument(
        "--training-summary",
        type=Path,
        default=RESULTS / "safe_control_gym_reinforce_reward_poisoning.csv",
    )
    parser.add_argument(
        "--physical-rollouts",
        type=Path,
        default=RESULTS / "safe_control_gym_reinforce_reward_poisoning_rollouts.csv",
    )
    parser.add_argument(
        "--resident-summary",
        type=Path,
        default=RESULTS / "cartpole_predictive_simplex_smoke_summary.csv",
    )
    parser.add_argument(
        "--candidates-out",
        type=Path,
        default=RESULTS / "cartpole_certificate_evasion_target_candidates.csv",
    )
    parser.add_argument(
        "--decision-out",
        type=Path,
        default=RESULTS / "cartpole_certificate_evasion_smoke_decision.csv",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
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

    raw_candidates: list[tuple[tuple[int, float, int], TargetCandidate]] = []
    for gain, bias in product((-18.0, 0.0, 18.0), (-5.0, 0.0, 5.0)):
        params = np.asarray([gain, bias], dtype=float)
        gate_first, gate_margins = delayed.casadi_deployment_outcomes(
            ctrl,
            info,
            env.symbolic.fd_func,
            params,
            states,
            action_low=action_low,
            action_high=action_high,
            deployment_steps=args.gate_horizon,
        )
        full_first, full_margins = delayed.casadi_deployment_outcomes(
            ctrl,
            info,
            env.symbolic.fd_func,
            params,
            states,
            action_low=action_low,
            action_high=action_high,
            deployment_steps=args.full_horizon,
        )
        gate_violated = gate_first >= 0
        full_violated = full_first >= 0
        accepted = bool(
            not np.any(gate_violated) and np.max(gate_margins) <= 0.0
        )
        post_gate_score = int(
            np.sum(args.full_horizon - full_first[full_violated])
        )
        row = TargetCandidate(
            gain=gain,
            bias=bias,
            gate_horizon=args.gate_horizon,
            gate_violating_states=int(np.sum(gate_violated)),
            gate_max_margin=float(np.max(gate_margins)),
            gate_accepted=accepted,
            full_horizon=args.full_horizon,
            full_violating_states=int(np.sum(full_violated)),
            full_max_margin=float(np.max(full_margins)),
            post_gate_failure_score=post_gate_score,
            selected=False,
        )
        score = (
            row.full_violating_states,
            row.full_max_margin,
            row.post_gate_failure_score,
        )
        if accepted:
            raw_candidates.append((score, row))

    if not raw_candidates:
        raise RuntimeError("no target passes the reverse-switch gate")
    _score, selected = max(raw_candidates, key=lambda item: item[0])

    all_rows = [row for _score, row in raw_candidates]
    # Preserve gate-rejected candidates in the audit as well.
    admitted_keys = {(row.gain, row.bias) for row in all_rows}
    for gain, bias in product((-18.0, 0.0, 18.0), (-5.0, 0.0, 5.0)):
        if (gain, bias) not in admitted_keys:
            # Recompute only the row metadata needed for transparent output.
            params = np.asarray([gain, bias], dtype=float)
            short, short_margins = delayed.casadi_deployment_outcomes(
                ctrl,
                info,
                env.symbolic.fd_func,
                params,
                states,
                action_low=action_low,
                action_high=action_high,
                deployment_steps=args.gate_horizon,
            )
            full, full_margins = delayed.casadi_deployment_outcomes(
                ctrl,
                info,
                env.symbolic.fd_func,
                params,
                states,
                action_low=action_low,
                action_high=action_high,
                deployment_steps=args.full_horizon,
            )
            violated = full >= 0
            all_rows.append(
                TargetCandidate(
                    gain=gain,
                    bias=bias,
                    gate_horizon=args.gate_horizon,
                    gate_violating_states=int(np.sum(short >= 0)),
                    gate_max_margin=float(np.max(short_margins)),
                    gate_accepted=False,
                    full_horizon=args.full_horizon,
                    full_violating_states=int(np.sum(violated)),
                    full_max_margin=float(np.max(full_margins)),
                    post_gate_failure_score=int(
                        np.sum(args.full_horizon - full[violated])
                    ),
                    selected=False,
                )
            )
    for row in all_rows:
        row.selected = bool(row.gain == selected.gain and row.bias == selected.bias)
    ctrl.close()
    env.close()

    training_rows = read_csv(args.training_summary)
    learned_row = next(
        row
        for row in training_rows
        if row["mechanism"] == "poisoned_action_only_snapshot"
    )
    learned = np.asarray(
        [float(learned_row["pending_gain"]), float(learned_row["pending_bias"])]
    )
    locked_target = np.asarray(
        [
            float(learned_row["attack_target_gain"]),
            float(learned_row["attack_target_bias"]),
        ]
    )

    task_config, lqr_config, _cbf_config = gate.build_configs(args.seed)
    env_func = partial(make, "cartpole", **task_config)
    env = env_func(gui=False)
    ctrl = make("lqr", env_func, **lqr_config)
    ctrl.reset()
    observation, info = env.reset(seed=args.seed)
    ctrl.reset_before_run(observation, info, env=env)
    action_low = float(np.asarray(env.action_space.low).reshape(-1)[0])
    action_high = float(np.asarray(env.action_space.high).reshape(-1)[0])
    learned_short, learned_short_margins = delayed.casadi_deployment_outcomes(
        ctrl,
        info,
        env.symbolic.fd_func,
        learned,
        states,
        action_low=action_low,
        action_high=action_high,
        deployment_steps=args.gate_horizon,
    )
    learned_full, _learned_full_margins = delayed.casadi_deployment_outcomes(
        ctrl,
        info,
        env.symbolic.fd_func,
        learned,
        states,
        action_low=action_low,
        action_high=action_high,
        deployment_steps=args.full_horizon,
    )
    ctrl.close()
    env.close()

    physical_rows = [
        row
        for row in read_csv(args.physical_rollouts)
        if row["mechanism"] == "poisoned_action_only_snapshot"
    ]
    physical_violations = sum(bool(row["first_violation_step"]) for row in physical_rows)
    resident_row = next(
        row
        for row in read_csv(args.resident_summary)
        if row["contract"] == "resident_predictive_simplex"
    )
    resident_violations = int(resident_row["accepted_physical_violations"])
    selected_target = np.asarray([selected.gain, selected.bias])
    target_matches = bool(np.allclose(selected_target, locked_target))
    learned_accepted = int(
        np.sum((learned_short < 0) & (learned_short_margins <= 0.0))
    )
    full_violations = int(np.sum(learned_full >= 0))
    passed = bool(
        target_matches
        and learned_accepted == len(states)
        and full_violations > 0
        and physical_violations > 0
        and resident_violations == 0
    )
    decision = EvasionDecision(
        selected_target_gain=selected.gain,
        selected_target_bias=selected.bias,
        locked_target_gain=float(locked_target[0]),
        locked_target_bias=float(locked_target[1]),
        target_matches_locked=target_matches,
        learned_gain=float(learned[0]),
        learned_bias=float(learned[1]),
        learned_gate_accepted_states=learned_accepted,
        candidate_states=len(states),
        learned_full_casadi_violations=full_violations,
        learned_physical_violations=physical_violations,
        resident_physical_violations=resident_violations,
        gate_aware_smoke_pass=passed,
    )
    write_csv(args.candidates_out, sorted(all_rows, key=lambda row: (row.gain, row.bias)))
    write_csv(args.decision_out, [decision])
    print(decision)
    print(f"wrote {args.candidates_out}")
    print(f"wrote {args.decision_out}")


if __name__ == "__main__":
    main()

