#!/usr/bin/env python3
"""Delayed-trigger certificate-lifecycle attack on Safe-Control-Gym cartpole.

This benchmark models a snapshot-commit architecture rather than an always-on
runtime shield.  During online adaptation, every applied action is protected by
the attacked-history robust action kernel.  An attacker also poisons the update
data so that the residual-policy parameters drift toward a harmful snapshot.
The committed snapshot is then evaluated without the adaptation-time filter on
a clean deployment envelope.

The benchmark deliberately does *not* claim that raw-policy certification is
necessary when a sound robust filter remains permanently online.  That
composition is an explicit escape condition and belongs to a different system
model.
"""

from __future__ import annotations

import argparse
import csv
from dataclasses import asdict, dataclass
from functools import partial
from itertools import product
from pathlib import Path
from statistics import median
from typing import Iterable

import numpy as np

from safe_control_gym.utils.registration import make

import safe_control_gym_plausible_set_lifecycle_gate as gate


ROOT = Path(__file__).resolve().parent
RESULTS_DIR = ROOT / "results"

MECHANISMS = (
    "action_only_snapshot",
    "always_freeze_snapshot",
    "lifecycle_gate_snapshot",
    "commit_lifecycle_gate_snapshot",
)


@dataclass
class TrainingResult:
    mechanism: str
    poison_steps: int
    attack_gain_step: float
    attack_bias_step: float
    learn_updates: int
    stale_steps: int
    uncertified_learning_steps: int
    action_filter_interventions: int
    rejected_action_steps: int
    constraint_violation_steps: int
    precommit_gain: float
    precommit_bias: float
    final_gain: float
    final_bias: float
    commit_projection_norm: float
    committed_nontrivial_update: bool
    certificate_candidates: int
    certificate_admitted: int


@dataclass
class DeploymentResult:
    mechanism: str
    init_x: float
    init_x_dot: float
    init_theta: float
    init_theta_dot: float
    steps_executed: int
    violation_steps: int
    first_violation_step: int | None
    mean_reward: float


@dataclass
class DelayedAttackSummary:
    mechanism: str
    seed: int
    rho: float
    guard_margin: float
    commit_guard_margin: float
    admission_guard_margin: float
    poison_steps: int
    deployment_steps: int
    attack_gain_step: float
    attack_bias_step: float
    learn_updates: int
    stale_steps: int
    uncertified_learning_steps: int
    training_constraint_violation_steps: int
    action_filter_interventions: int
    precommit_gain: float
    precommit_bias: float
    final_gain: float
    final_bias: float
    commit_projection_norm: float
    committed_nontrivial_update: bool
    certificate_candidates: int
    certificate_admitted: int
    deployment_rollouts: int
    violating_rollouts: int
    deployment_violation_rate: float
    median_first_violation_step: float | None
    mean_deployment_reward: float


def poisoned_candidate(
    params: np.ndarray,
    *,
    gain_step: float,
    bias_step: float,
) -> np.ndarray:
    """A malicious update-data gradient aimed at a delayed harmful snapshot."""
    delta = np.asarray([gain_step, bias_step], dtype=float)
    return np.minimum(np.maximum(params + delta, gate.PARAM_LOW), gate.PARAM_HIGH)


def repeated_poison_snapshot(
    delta: np.ndarray,
    *,
    poison_steps: int,
) -> np.ndarray:
    params = np.zeros(2, dtype=float)
    for _step in range(poison_steps):
        params = poisoned_candidate(
            params,
            gain_step=float(delta[0]),
            bias_step=float(delta[1]),
        )
    return params


def surrogate_deployment_score(
    ctrl: object,
    info: dict,
    model: gate.CartpoleModel,
    params: np.ndarray,
    *,
    action_low: float,
    action_high: float,
    deployment_steps: int,
) -> tuple[int, float, int]:
    """White-box Euler surrogate for ranking poisoned update directions."""
    violating_rollouts = 0
    worst_margin = -float("inf")
    early_violation_score = 0
    for initial_state in deployment_envelope():
        state = initial_state.copy()
        for step in range(deployment_steps):
            action = gate.total_policy_action(ctrl, state, info, params)
            action = float(np.clip(action, action_low, action_high))
            state = gate.cartpole_step(model, state, action)
            margin = max(
                float(np.max(state - gate.SAFE_HIGH)),
                float(np.max(gate.SAFE_LOW - state)),
            )
            worst_margin = max(worst_margin, margin)
            if margin > 0.0:
                violating_rollouts += 1
                early_violation_score += deployment_steps - step
                break
    return violating_rollouts, worst_margin, early_violation_score


def select_update_attack(
    ctrl: object,
    info: dict,
    model: gate.CartpoleModel,
    *,
    action_low: float,
    action_high: float,
    poison_steps: int,
    deployment_steps: int,
) -> np.ndarray:
    """Select an update-data poison direction using a finite white-box search."""
    best_delta: np.ndarray | None = None
    best_score: tuple[int, float, int] | None = None
    for gain_step, bias_step in product((-2.0, 0.0, 2.0), (-0.5, 0.0, 0.5)):
        delta = np.asarray([gain_step, bias_step], dtype=float)
        candidate_snapshot = repeated_poison_snapshot(
            delta,
            poison_steps=poison_steps,
        )
        score = surrogate_deployment_score(
            ctrl,
            info,
            model,
            candidate_snapshot,
            action_low=action_low,
            action_high=action_high,
            deployment_steps=deployment_steps,
        )
        if best_score is None or score > best_score:
            best_delta = delta
            best_score = score
    assert best_delta is not None
    return best_delta


def casadi_deployment_score(
    ctrl: object,
    info: dict,
    casadi_fd_func: object,
    params: np.ndarray,
    *,
    action_low: float,
    action_high: float,
    deployment_steps: int,
    initial_states: Iterable[np.ndarray] | None = None,
) -> tuple[int, float, int]:
    """Vectorized multi-step score using Safe-Control-Gym CasADi dynamics."""
    state_list = list(
        certification_envelope() if initial_states is None else initial_states
    )
    if not state_list:
        raise ValueError("initial_states must not be empty")
    first_violations, max_margins = casadi_deployment_outcomes(
        ctrl,
        info,
        casadi_fd_func,
        params,
        state_list,
        action_low=action_low,
        action_high=action_high,
        deployment_steps=deployment_steps,
    )
    violated = first_violations >= 0
    return (
        int(np.sum(violated)),
        float(np.max(max_margins)),
        int(np.sum(deployment_steps - first_violations[violated])),
    )


def casadi_deployment_outcomes(
    ctrl: object,
    info: dict,
    casadi_fd_func: object,
    params: np.ndarray,
    initial_states: Iterable[np.ndarray],
    *,
    action_low: float,
    action_high: float,
    deployment_steps: int,
) -> tuple[np.ndarray, np.ndarray]:
    """Return first violations and maximum margins for parallel trajectories.

    ``params`` may be one shared two-vector or one two-vector per trajectory.
    The LQR fast path avoids thousands of Python controller calls in commit
    sweeps while retaining a generic controller fallback.
    """
    states = np.vstack(list(initial_states))
    trajectory_params = np.asarray(params, dtype=float)
    if trajectory_params.ndim == 1:
        trajectory_params = np.repeat(
            trajectory_params.reshape(1, -1), len(states), axis=0
        )
    if trajectory_params.shape != (len(states), 2):
        raise ValueError("params must have shape (2,) or (len(initial_states), 2)")

    first_violations = np.full(len(states), -1, dtype=int)
    max_margins = np.full(len(states), -float("inf"), dtype=float)
    gain = getattr(ctrl, "gain", None)
    if gain is not None:
        gain_vector = np.asarray(gain, dtype=float).reshape(-1)
    else:
        gain_vector = None
    for step in range(deployment_steps):
        if gain_vector is not None:
            actions = (
                -(states @ gain_vector)
                + states[:, 2] * trajectory_params[:, 0]
                + trajectory_params[:, 1]
            )
            actions = np.clip(actions, action_low, action_high)
        else:
            actions = np.asarray(
                [
                    np.clip(
                        gate.total_policy_action(ctrl, state, info, row_params),
                        action_low,
                        action_high,
                    )
                    for state, row_params in zip(states, trajectory_params)
                ],
                dtype=float,
            )
        states = np.asarray(
            casadi_fd_func(x0=states.T, p=actions.reshape(1, -1))["xf"],
            dtype=float,
        ).T
        margins = np.maximum(
            np.max(states - gate.SAFE_HIGH, axis=1),
            np.max(gate.SAFE_LOW - states, axis=1),
        )
        max_margins = np.maximum(max_margins, margins)
        new_violations = (first_violations < 0) & (margins > 0.0)
        first_violations[new_violations] = step
    return first_violations, max_margins


def baseline_viable_states(
    ctrl: object,
    info: dict,
    casadi_fd_func: object,
    candidate_states: Iterable[np.ndarray],
    *,
    baseline_params: np.ndarray,
    action_low: float,
    action_high: float,
    deployment_steps: int,
    guard_margin: float = 0.0,
) -> list[np.ndarray]:
    """Keep states where the baseline retains a finite-horizon safety margin."""
    state_list = list(candidate_states)
    first_violations, max_margins = casadi_deployment_outcomes(
        ctrl,
        info,
        casadi_fd_func,
        baseline_params,
        state_list,
        action_low=action_low,
        action_high=action_high,
        deployment_steps=deployment_steps,
    )
    return [
        state
        for state, first, margin in zip(
            state_list,
            first_violations,
            max_margins,
        )
        if first < 0 and margin <= -guard_margin
    ]


def casadi_deployment_scores(
    ctrl: object,
    info: dict,
    casadi_fd_func: object,
    parameter_snapshots: Iterable[np.ndarray],
    initial_states: Iterable[np.ndarray],
    *,
    action_low: float,
    action_high: float,
    deployment_steps: int,
) -> list[tuple[int, float, int]]:
    """Score many snapshots in one vectorized dynamics rollout."""
    snapshots = np.vstack(list(parameter_snapshots))
    states = np.vstack(list(initial_states))
    trajectory_states = np.vstack([states for _snapshot in snapshots])
    trajectory_params = np.repeat(snapshots, len(states), axis=0)
    first_violations, max_margins = casadi_deployment_outcomes(
        ctrl,
        info,
        casadi_fd_func,
        trajectory_params,
        trajectory_states,
        action_low=action_low,
        action_high=action_high,
        deployment_steps=deployment_steps,
    )
    first_violations = first_violations.reshape(len(snapshots), len(states))
    max_margins = max_margins.reshape(len(snapshots), len(states))
    scores: list[tuple[int, float, int]] = []
    for snapshot_first, snapshot_margins in zip(first_violations, max_margins):
        violated = snapshot_first >= 0
        scores.append(
            (
                int(np.sum(violated)),
                float(np.max(snapshot_margins)),
                int(np.sum(deployment_steps - snapshot_first[violated])),
            )
        )
    return scores


def commit_backtracked_snapshot(
    baseline_params: np.ndarray,
    pending_params: np.ndarray,
    ctrl: object,
    info: dict,
    casadi_fd_func: object,
    *,
    action_low: float,
    action_high: float,
    deployment_steps: int,
    certificate_states: Iterable[np.ndarray] | None = None,
    certificate_guard_margin: float = 0.005,
) -> np.ndarray:
    """Commit the largest interpolation with zero certified rollout failures."""
    state_list = list(
        certification_envelope()
        if certificate_states is None
        else certificate_states
    )
    state_list = baseline_viable_states(
        ctrl,
        info,
        casadi_fd_func,
        state_list,
        baseline_params=baseline_params,
        action_low=action_low,
        action_high=action_high,
        deployment_steps=deployment_steps,
    )
    if not state_list:
        raise ValueError("baseline has no viable states in certification envelope")
    direction = np.asarray(pending_params, dtype=float) - np.asarray(
        baseline_params,
        dtype=float,
    )
    # Walk outward from the trusted baseline.  Each returned candidate is
    # independently certified; stopping at the first failure avoids assuming
    # that a distant, disconnected safe island is deployable by interpolation.
    fractions = np.linspace(0.0, 1.0, 21)
    trials = [
        np.asarray(baseline_params, dtype=float) + float(fraction) * direction
        for fraction in fractions
    ]
    accepted = trials[0]
    baseline_score = casadi_deployment_score(
        ctrl,
        info,
        casadi_fd_func,
        accepted,
        action_low=action_low,
        action_high=action_high,
        deployment_steps=deployment_steps,
        initial_states=state_list,
    )
    if baseline_score[1] > -certificate_guard_margin:
        raise ValueError(
            "trusted baseline does not satisfy the commit certificate guard margin"
        )
    if np.linalg.norm(direction) <= 1e-12:
        return accepted
    for trial in trials[1:]:
        score = casadi_deployment_score(
            ctrl,
            info,
            casadi_fd_func,
            trial,
            action_low=action_low,
            action_high=action_high,
            deployment_steps=deployment_steps,
            initial_states=state_list,
        )
        if score[0] != 0 or score[1] > -certificate_guard_margin:
            break
        accepted = trial
    return accepted


def train_snapshot(
    mechanism: str,
    *,
    seed: int,
    rho: float,
    poison_steps: int,
    gain_step: float,
    bias_step: float,
    update_attack: str,
    attack_surrogate_steps: int,
    future_span: float,
    guard_margin: float,
    commit_guard_margin: float,
    admission_guard_margin: float,
    action_grid_size: int,
) -> tuple[np.ndarray, TrainingResult]:
    if mechanism not in MECHANISMS:
        raise ValueError(f"unknown mechanism {mechanism}")

    task_config, lqr_config, _cbf_config = gate.build_configs(seed)
    env_func = partial(make, "cartpole", **task_config)
    env = env_func(gui=False)
    ctrl = make("lqr", env_func, **lqr_config)
    ctrl.reset()
    obs, info = env.reset(seed=seed)
    ctrl.reset_before_run(obs, info, env=env)

    model = gate.make_model_from_env(env)
    action_grid = gate.action_grid_from_env(env, action_grid_size)
    casadi_fd_func = env.symbolic.fd_func
    params = np.zeros(2, dtype=float)
    action_low = float(np.asarray(env.action_space.low).reshape(-1)[0])
    action_high = float(np.asarray(env.action_space.high).reshape(-1)[0])
    if update_attack == "whitebox_grid":
        attack_delta = select_update_attack(
            ctrl,
            info,
            model,
            action_low=action_low,
            action_high=action_high,
            poison_steps=poison_steps,
            deployment_steps=attack_surrogate_steps,
        )
    elif update_attack == "fixed":
        attack_delta = np.asarray([gain_step, bias_step], dtype=float)
    else:
        raise ValueError(f"unknown update attack {update_attack}")

    learn_updates = 0
    stale_steps = 0
    uncertified_steps = 0
    interventions = 0
    rejected_actions = 0
    constraint_violations = 0

    for _step in range(poison_steps):
        # The sensor component stays within the declared L_inf budget while a
        # poisoned reward/log channel supplies the malicious update gradient.
        attacked_obs = np.asarray(obs, dtype=float).copy()
        attacked_obs[2] -= rho
        current_kernel = gate.safe_kernel_for_observation(
            attacked_obs,
            rho,
            model,
            action_grid,
            guard_margin=guard_margin,
            kernel_backend="casadi",
            casadi_fd_func=casadi_fd_func,
        )

        constraints = None
        if mechanism in {"action_only_snapshot", "lifecycle_gate_snapshot"}:
            constraints = gate.parameter_constraints(
                ctrl,
                info,
                attacked_obs,
                rho,
                model,
                action_grid,
                future_span=future_span,
                guard_margin=guard_margin,
                kernel_backend="casadi",
                casadi_fd_func=casadi_fd_func,
                cbf_filter=None,
                cbf_action_tolerance=1e-5,
            )

        candidate = poisoned_candidate(
            params,
            gain_step=float(attack_delta[0]),
            bias_step=float(attack_delta[1]),
        )
        next_params = params.copy()
        if mechanism in {
            "action_only_snapshot",
            "commit_lifecycle_gate_snapshot",
        }:
            next_params = candidate
        elif mechanism == "lifecycle_gate_snapshot":
            if current_kernel.interval is not None and constraints is not None:
                projected, feasible = gate.project_params(candidate, constraints)
                if feasible:
                    next_params = np.minimum(
                        np.maximum(projected, gate.PARAM_LOW),
                        gate.PARAM_HIGH,
                    )

        changed = gate.params_changed(params, next_params)
        learn_updates += int(changed)
        parameter_violation = gate.max_param_violation(next_params, constraints)
        update_is_certified = (
            current_kernel.interval is not None
            and constraints is not None
            and parameter_violation <= 1e-7
        )
        stale_steps += int(
            mechanism == "action_only_snapshot"
            and current_kernel.interval is not None
            and parameter_violation > 1e-7
        )
        uncertified_steps += int(
            mechanism == "action_only_snapshot"
            and changed
            and not update_is_certified
        )

        raw_action = gate.total_policy_action(ctrl, attacked_obs, info, next_params)
        filtered_action, accepted, correction = gate.project_to_kernel(
            raw_action,
            current_kernel,
        )
        if accepted:
            action = filtered_action
            interventions += int(correction > 1e-8)
        else:
            # This branch is recorded as a rejection.  It is not counted as a
            # certified action and should be replaced by a system fail-safe in
            # a deployment implementation.
            action = raw_action
            rejected_actions += 1

        params = next_params
        obs, _reward, done, info = env.step(
            np.asarray([np.clip(action, action_grid[0], action_grid[-1])])
        )
        constraint_violations += int(bool(info.get("constraint_violation", False)))
        if done:
            obs, info = env.reset()
            ctrl.reset_before_run(obs, info, env=env)

    pending_params = params.copy()
    commit_projection_norm = 0.0
    certificate_candidates = 0
    certificate_admitted = 0
    if mechanism == "commit_lifecycle_gate_snapshot":
        candidate_states = certification_envelope()
        admitted_states = baseline_viable_states(
            ctrl,
            info,
            casadi_fd_func,
            candidate_states,
            baseline_params=np.zeros(2, dtype=float),
            action_low=action_low,
            action_high=action_high,
            deployment_steps=attack_surrogate_steps,
            guard_margin=admission_guard_margin,
        )
        certificate_candidates = len(candidate_states)
        certificate_admitted = len(admitted_states)
        params = commit_backtracked_snapshot(
            np.zeros(2, dtype=float),
            pending_params,
            ctrl,
            info,
            casadi_fd_func,
            action_low=action_low,
            action_high=action_high,
            deployment_steps=attack_surrogate_steps,
            certificate_states=admitted_states,
            certificate_guard_margin=commit_guard_margin,
        )
        commit_projection_norm = float(np.linalg.norm(params - pending_params))

    ctrl.close()
    env.close()
    result = TrainingResult(
        mechanism=mechanism,
        poison_steps=poison_steps,
        attack_gain_step=float(attack_delta[0]),
        attack_bias_step=float(attack_delta[1]),
        learn_updates=learn_updates,
        stale_steps=stale_steps,
        uncertified_learning_steps=uncertified_steps,
        action_filter_interventions=interventions,
        rejected_action_steps=rejected_actions,
        constraint_violation_steps=constraint_violations,
        precommit_gain=float(pending_params[0]),
        precommit_bias=float(pending_params[1]),
        final_gain=float(params[0]),
        final_bias=float(params[1]),
        commit_projection_norm=commit_projection_norm,
        committed_nontrivial_update=gate.params_changed(np.zeros(2), params),
        certificate_candidates=certificate_candidates,
        certificate_admitted=certificate_admitted,
    )
    return params, result


def deployment_envelope() -> list[np.ndarray]:
    """Interior clean states used to exercise a committed controller snapshot."""
    theta_values = (-0.15, -0.10, -0.05, 0.05, 0.10, 0.15)
    theta_dot_values = (-1.0, -0.75, -0.50, 0.0, 0.50, 0.75, 1.0)
    return [
        np.asarray([0.0, 0.0, theta, theta_dot], dtype=float)
        for theta, theta_dot in product(theta_values, theta_dot_values)
    ]


def certification_envelope() -> list[np.ndarray]:
    """Deterministic coverage set for finite-horizon commit certification.

    The 42 legacy angle/rate cases are retained, a 36-point boundary cross
    varies cart state at extreme pole states, and 86 space-filling samples vary
    all four coordinates. Evaluation states use a disjoint seed. This remains
    a sampled finite-horizon certificate, not a continuous-state proof.
    """
    rng = np.random.default_rng(1729)
    random_states = rng.uniform(
        low=np.asarray([-0.25, -0.50, -0.15, -1.0]),
        high=np.asarray([0.25, 0.50, 0.15, 1.0]),
        size=(86, 4),
    )
    boundary_states = [
        np.asarray([x, x_dot, theta, theta_dot], dtype=float)
        for x, x_dot, theta, theta_dot in product(
            (-0.25, 0.0, 0.25),
            (-0.50, 0.0, 0.50),
            (-0.15, 0.15),
            (-1.0, 1.0),
        )
    ]
    states = deployment_envelope() + boundary_states + [
        row.copy() for row in random_states
    ]
    deduplicated: list[np.ndarray] = []
    seen: set[tuple[float, ...]] = set()
    for state in states:
        key = tuple(np.round(state, 12))
        if key not in seen:
            seen.add(key)
            deduplicated.append(state)
    return deduplicated


def deploy_raw_snapshot(
    mechanism: str,
    params: np.ndarray,
    initial_state: np.ndarray,
    *,
    seed: int,
    deployment_steps: int,
) -> DeploymentResult:
    task_config, lqr_config, _cbf_config = gate.build_configs(seed)
    task_config["init_state"] = np.asarray(initial_state, dtype=float)
    env_func = partial(make, "cartpole", **task_config)
    env = env_func(gui=False)
    ctrl = make("lqr", env_func, **lqr_config)
    ctrl.reset()
    obs, info = env.reset(seed=seed)
    ctrl.reset_before_run(obs, info, env=env)
    action_low = float(np.asarray(env.action_space.low).reshape(-1)[0])
    action_high = float(np.asarray(env.action_space.high).reshape(-1)[0])

    rewards: list[float] = []
    violation_steps = 0
    first_violation: int | None = None
    for step in range(deployment_steps):
        raw_action = gate.total_policy_action(ctrl, np.asarray(obs), info, params)
        action = float(np.clip(raw_action, action_low, action_high))
        obs, reward, done, info = env.step(np.asarray([action]))
        rewards.append(float(reward))
        violation = bool(info.get("constraint_violation", False))
        violation_steps += int(violation)
        if violation and first_violation is None:
            first_violation = step
        if done:
            break

    ctrl.close()
    env.close()
    return DeploymentResult(
        mechanism=mechanism,
        init_x=float(initial_state[0]),
        init_x_dot=float(initial_state[1]),
        init_theta=float(initial_state[2]),
        init_theta_dot=float(initial_state[3]),
        steps_executed=len(rewards),
        violation_steps=violation_steps,
        first_violation_step=first_violation,
        mean_reward=float(np.mean(rewards)) if rewards else 0.0,
    )


def summarize(
    training: TrainingResult,
    deployment: list[DeploymentResult],
    *,
    seed: int,
    rho: float,
    guard_margin: float,
    commit_guard_margin: float,
    admission_guard_margin: float,
    deployment_steps: int,
) -> DelayedAttackSummary:
    first_steps = [
        row.first_violation_step
        for row in deployment
        if row.first_violation_step is not None
    ]
    violating = len(first_steps)
    return DelayedAttackSummary(
        mechanism=training.mechanism,
        seed=seed,
        rho=rho,
        guard_margin=guard_margin,
        commit_guard_margin=commit_guard_margin,
        admission_guard_margin=admission_guard_margin,
        poison_steps=training.poison_steps,
        deployment_steps=deployment_steps,
        attack_gain_step=training.attack_gain_step,
        attack_bias_step=training.attack_bias_step,
        learn_updates=training.learn_updates,
        stale_steps=training.stale_steps,
        uncertified_learning_steps=training.uncertified_learning_steps,
        training_constraint_violation_steps=training.constraint_violation_steps,
        action_filter_interventions=training.action_filter_interventions,
        precommit_gain=training.precommit_gain,
        precommit_bias=training.precommit_bias,
        final_gain=training.final_gain,
        final_bias=training.final_bias,
        commit_projection_norm=training.commit_projection_norm,
        committed_nontrivial_update=training.committed_nontrivial_update,
        certificate_candidates=training.certificate_candidates,
        certificate_admitted=training.certificate_admitted,
        deployment_rollouts=len(deployment),
        violating_rollouts=violating,
        deployment_violation_rate=violating / len(deployment) if deployment else 0.0,
        median_first_violation_step=float(median(first_steps)) if first_steps else None,
        mean_deployment_reward=float(np.mean([row.mean_reward for row in deployment])),
    )


def write_csv(path: Path, rows: Iterable[object]) -> None:
    dictionaries = [asdict(row) for row in rows]
    if not dictionaries:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(dictionaries[0].keys()))
        writer.writeheader()
        writer.writerows(dictionaries)


def print_summary(rows: Iterable[DelayedAttackSummary]) -> None:
    print(
        "| mechanism | attack delta | train violations | stale | uncertified | updates | "
        "pending -> committed | deployment violations | median first | reward |"
    )
    print("|---|---|---:|---:|---:|---:|---|---:|---:|---:|")
    for row in rows:
        first = "--" if row.median_first_violation_step is None else f"{row.median_first_violation_step:.1f}"
        print(
            f"| {row.mechanism} | ({row.attack_gain_step:.2f},{row.attack_bias_step:.2f}) | "
            f"{row.training_constraint_violation_steps} | "
            f"{row.stale_steps} | {row.uncertified_learning_steps} | "
            f"{row.learn_updates} | ({row.precommit_gain:.3f},{row.precommit_bias:.3f}) "
            f"-> ({row.final_gain:.3f},{row.final_bias:.3f}) | "
            f"{row.violating_rollouts}/{row.deployment_rollouts} | {first} | "
            f"{row.mean_deployment_reward:.3f} |"
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, default=2026)
    parser.add_argument("--rho", type=float, default=0.005)
    parser.add_argument("--poison-steps", type=int, default=12)
    parser.add_argument("--deployment-steps", type=int, default=120)
    parser.add_argument("--gain-step", type=float, default=2.0)
    parser.add_argument("--bias-step", type=float, default=-0.5)
    parser.add_argument(
        "--update-attack",
        choices=("whitebox_grid", "fixed"),
        default="whitebox_grid",
    )
    parser.add_argument("--future-span", type=float, default=0.03)
    parser.add_argument("--guard-margin", type=float, default=0.0)
    parser.add_argument("--commit-guard-margin", type=float, default=0.005)
    parser.add_argument("--admission-guard-margin", type=float, default=0.0075)
    parser.add_argument("--action-grid-size", type=int, default=41)
    parser.add_argument(
        "--summary-out",
        type=Path,
        default=RESULTS_DIR / "safe_control_gym_delayed_trigger_summary.csv",
    )
    parser.add_argument(
        "--rollouts-out",
        type=Path,
        default=RESULTS_DIR / "safe_control_gym_delayed_trigger_rollouts.csv",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    summaries: list[DelayedAttackSummary] = []
    rollouts: list[DeploymentResult] = []
    for mechanism in MECHANISMS:
        params, training = train_snapshot(
            mechanism,
            seed=args.seed,
            rho=args.rho,
            poison_steps=args.poison_steps,
            gain_step=args.gain_step,
            bias_step=args.bias_step,
            update_attack=args.update_attack,
            attack_surrogate_steps=args.deployment_steps,
            future_span=args.future_span,
            guard_margin=args.guard_margin,
            commit_guard_margin=args.commit_guard_margin,
            admission_guard_margin=args.admission_guard_margin,
            action_grid_size=args.action_grid_size,
        )
        mechanism_rollouts = [
            deploy_raw_snapshot(
                mechanism,
                params,
                initial_state,
                seed=args.seed,
                deployment_steps=args.deployment_steps,
            )
            for initial_state in deployment_envelope()
        ]
        rollouts.extend(mechanism_rollouts)
        summaries.append(
            summarize(
                training,
                mechanism_rollouts,
                seed=args.seed,
                rho=args.rho,
                guard_margin=args.guard_margin,
                commit_guard_margin=args.commit_guard_margin,
                admission_guard_margin=args.admission_guard_margin,
                deployment_steps=args.deployment_steps,
            )
        )

    write_csv(args.summary_out, summaries)
    write_csv(args.rollouts_out, rollouts)
    print_summary(summaries)
    print(f"wrote {args.summary_out}")
    print(f"wrote {args.rollouts_out}")


if __name__ == "__main__":
    main()
