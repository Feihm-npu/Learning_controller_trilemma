#!/usr/bin/env python3
"""Lifecycle hard-gate scaffold on Safe-Control-Gym's 2-D quadrotor.

This experiment is intentionally narrower than the final reward-poisoning
study.  It first checks whether a state-dependent residual snapshot can remain
benign for several control periods and then destabilize the official clipped
LQR controller.  It compares the raw snapshot with two explicit escape
conditions: an always-frozen trusted snapshot and a permanent online action
filter.  A commit-time finite-horizon certificate backtracks a pending update
toward the trusted snapshot.

The certificate and online filter use the environment's CasADi dynamics.  The
reported deployment outcomes use independent PyBullet rollouts.  Every action
is clipped to the quadrotor's physical thrust box *before* certification or
deployment; otherwise the upstream LQR's negative-thrust request at high
altitude would be mislabeled as a lifecycle failure.
"""

from __future__ import annotations

import argparse
import contextlib
import csv
import io
from dataclasses import asdict, dataclass
from functools import partial
from itertools import product
from pathlib import Path
from statistics import median
from typing import Iterable, Sequence

import numpy as np

from safe_control_gym.utils.registration import make

from safe_control_gym_controller_baselines import (
    RESULTS_DIR,
    SCENARIOS,
    build_configs,
    deep_merge,
    read_yaml,
)


ROOT = Path(__file__).resolve().parent
SCG_ROOT = ROOT / "external" / "safe-control-gym"

SAFE_LOW = np.asarray([-2.0, -2.0, 0.0, -2.0, -0.2, -1.0])
SAFE_HIGH = np.asarray([2.0, 2.0, 2.0, 2.0, 0.2, 1.0])
FEATURE_SCALE = np.asarray([0.2, 1.0])
MECHANISMS = (
    "trusted_clipped_lqr",
    "harmful_raw_snapshot",
    "harmful_permanent_filter",
    "poisoned_always_freeze_snapshot",
    "poisoned_commit_gate_snapshot",
)


@dataclass(frozen=True)
class DynamicsBundle:
    task_config: dict
    lqr_config: dict
    gain: np.ndarray
    goal: np.ndarray
    equilibrium_action: np.ndarray
    action_low: np.ndarray
    action_high: np.ndarray
    fd_func: object
    linear_a: np.ndarray
    linear_b: np.ndarray


@dataclass(frozen=True)
class AttackCandidate:
    theta_weight: float
    theta_dot_weight: float
    violating_rollouts: int
    delayed_violations: int
    immediate_violations: int
    median_first_violation_step: float | None
    worst_margin: float


@dataclass
class DeploymentResult:
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
class MechanismSummary:
    mechanism: str
    deployment_rollouts: int
    violating_rollouts: int
    deployment_violation_rate: float
    immediate_violating_rollouts: int
    delayed_violating_rollouts: int
    median_first_violation_step: float | None
    filter_interventions: int
    filter_rejections: int
    mean_deployment_reward: float
    pending_update_norm: float
    committed_update_norm: float
    commit_fraction: float
    certificate_candidates: int
    certificate_admitted: int


def silence_stdout():
    return contextlib.redirect_stdout(io.StringIO())


def quadrotor_configs(seed: int, initial_state: np.ndarray | None = None) -> tuple[dict, dict]:
    """Build official LQR configs plus the tight MPSC safety constraints."""
    scenario = next(
        item
        for item in SCENARIOS
        if item.task_key == "quadrotor_2d" and item.algo == "lqr"
    )
    task_config, lqr_config = build_configs(scenario)
    constraint_override = read_yaml(
        SCG_ROOT
        / "examples"
        / "mpsc"
        / "config_overrides"
        / "quadrotor_2D"
        / "quadrotor_2D_stab.yaml"
    )["task_config"]
    # Keep the official LQR task/cost while importing only the safety-relevant
    # MPSC settings.  Direct physical thrust avoids normalized-action ambiguity.
    deep_merge(
        task_config,
        {
            "constraints": constraint_override["constraints"],
            "normalized_rl_action_space": False,
            "done_on_violation": False,
            "done_on_out_of_bound": False,
            "randomized_init": False,
            "seed": seed,
            "gui": False,
        },
    )
    if initial_state is None:
        initial_state = np.asarray([0.0, 0.0, 1.0, 0.0, 0.0, 0.0])
    state = np.asarray(initial_state, dtype=float)
    task_config["init_state"] = {
        "init_x": float(state[0]),
        "init_x_dot": float(state[1]),
        "init_z": float(state[2]),
        "init_z_dot": float(state[3]),
        "init_theta": float(state[4]),
        "init_theta_dot": float(state[5]),
    }
    lqr_config["seed"] = seed
    return task_config, lqr_config


def build_dynamics(seed: int) -> DynamicsBundle:
    task_config, lqr_config = quadrotor_configs(seed)
    env_func = partial(make, "quadrotor", **task_config)
    env = env_func(gui=False)
    ctrl = make("lqr", env_func, **lqr_config)
    with silence_stdout():
        ctrl.reset()
    obs, info = env.reset(seed=seed)
    ctrl.reset_before_run(obs, info, env=env)
    bundle = DynamicsBundle(
        task_config=task_config,
        lqr_config=lqr_config,
        gain=np.asarray(ctrl.gain, dtype=float),
        goal=np.asarray(env.X_GOAL, dtype=float),
        equilibrium_action=np.asarray(ctrl.model.U_EQ, dtype=float),
        action_low=np.asarray(env.action_space.low, dtype=float),
        action_high=np.asarray(env.action_space.high, dtype=float),
        fd_func=env.symbolic.fd_func,
        linear_a=(
            np.eye(env.symbolic.nx)
            + np.asarray(
                ctrl.model.df_func(ctrl.model.X_EQ, ctrl.model.U_EQ)[0],
                dtype=float,
            )
            * float(ctrl.model.dt)
        ),
        linear_b=(
            np.asarray(
                ctrl.model.df_func(ctrl.model.X_EQ, ctrl.model.U_EQ)[1],
                dtype=float,
            )
            * float(ctrl.model.dt)
        ),
    )
    ctrl.close()
    env.close()
    return bundle


def actor_features(states: np.ndarray) -> np.ndarray:
    """Pitch and pitch-rate features for a two-thrust residual actor."""
    states = np.asarray(states, dtype=float)
    return states[..., [4, 5]] / FEATURE_SCALE


def antisymmetric_snapshot(theta_weight: float, theta_dot_weight: float) -> np.ndarray:
    """Return W where residual thrust is [d, -d]."""
    first = np.asarray([theta_weight, theta_dot_weight], dtype=float)
    return np.vstack([first, -first])


def policy_actions(bundle: DynamicsBundle, states: np.ndarray, snapshot: np.ndarray) -> np.ndarray:
    states = np.atleast_2d(np.asarray(states, dtype=float))
    baseline = -(states - bundle.goal) @ bundle.gain.T + bundle.equilibrium_action
    residual = actor_features(states) @ np.asarray(snapshot, dtype=float).T
    return np.clip(baseline + residual, bundle.action_low, bundle.action_high)


def trajectory_policy_actions(
    bundle: DynamicsBundle,
    states: np.ndarray,
    trajectory_snapshots: np.ndarray,
) -> np.ndarray:
    """Evaluate one 2x2 snapshot per state without Python controller calls."""
    states = np.atleast_2d(np.asarray(states, dtype=float))
    snapshots = np.asarray(trajectory_snapshots, dtype=float)
    if snapshots.shape != (len(states), 2, 2):
        raise ValueError("trajectory_snapshots must have shape (num_states, 2, 2)")
    baseline = -(states - bundle.goal) @ bundle.gain.T + bundle.equilibrium_action
    residual = np.einsum("nij,nj->ni", snapshots, actor_features(states))
    return np.clip(baseline + residual, bundle.action_low, bundle.action_high)


def state_margins(states: np.ndarray, guard_margin: float = 0.0) -> np.ndarray:
    states = np.atleast_2d(np.asarray(states, dtype=float))
    return np.maximum(
        np.max(states - (SAFE_HIGH - guard_margin), axis=1),
        np.max((SAFE_LOW + guard_margin) - states, axis=1),
    )


def casadi_rollout_outcomes(
    bundle: DynamicsBundle,
    snapshot: np.ndarray,
    initial_states: Iterable[np.ndarray],
    *,
    steps: int,
    guard_margin: float = 0.0,
) -> tuple[np.ndarray, np.ndarray]:
    """Vectorized finite-horizon outcomes under the mean residual policy."""
    states = np.vstack(list(initial_states)).astype(float)
    first_violations = np.full(len(states), -1, dtype=int)
    max_margins = np.full(len(states), -float("inf"), dtype=float)
    for step in range(steps):
        actions = policy_actions(bundle, states, snapshot)
        states = np.asarray(
            bundle.fd_func(x0=states.T, p=actions.T)["xf"], dtype=float
        ).T
        margins = state_margins(states, guard_margin)
        max_margins = np.maximum(max_margins, margins)
        newly_violated = (first_violations < 0) & (margins > 0.0)
        first_violations[newly_violated] = step
    return first_violations, max_margins


def casadi_snapshot_outcomes(
    bundle: DynamicsBundle,
    snapshots: Iterable[np.ndarray],
    initial_states: Iterable[np.ndarray],
    *,
    steps: int,
    guard_margin: float = 0.0,
) -> tuple[np.ndarray, np.ndarray]:
    """Score many snapshots in one CasADi propagation loop.

    The result matrices have shape ``(num_snapshots, num_initial_states)``.
    This turns an attack search from thousands of CasADi calls into one call
    per control step.
    """
    snapshot_array = np.stack(list(snapshots)).astype(float)
    initial_array = np.vstack(list(initial_states)).astype(float)
    num_snapshots, num_states = len(snapshot_array), len(initial_array)
    states = np.tile(initial_array, (num_snapshots, 1))
    trajectory_snapshots = np.repeat(snapshot_array, num_states, axis=0)
    first_violations = np.full(len(states), -1, dtype=int)
    max_margins = np.full(len(states), -float("inf"), dtype=float)
    for step in range(steps):
        actions = trajectory_policy_actions(bundle, states, trajectory_snapshots)
        states = np.asarray(
            bundle.fd_func(x0=states.T, p=actions.T)["xf"], dtype=float
        ).T
        margins = state_margins(states, guard_margin)
        max_margins = np.maximum(max_margins, margins)
        newly_violated = (first_violations < 0) & (margins > 0.0)
        first_violations[newly_violated] = step
    return (
        first_violations.reshape(num_snapshots, num_states),
        max_margins.reshape(num_snapshots, num_states),
    )


def linear_snapshot_outcomes(
    bundle: DynamicsBundle,
    snapshots: Iterable[np.ndarray],
    initial_states: Iterable[np.ndarray],
    *,
    steps: int,
    guard_margin: float = 0.0,
) -> tuple[np.ndarray, np.ndarray]:
    """Fast LQR-linearization surrogate used only to rank attack targets."""
    snapshot_array = np.stack(list(snapshots)).astype(float)
    initial_array = np.vstack(list(initial_states)).astype(float)
    num_snapshots, num_states = len(snapshot_array), len(initial_array)
    states = np.tile(initial_array, (num_snapshots, 1))
    trajectory_snapshots = np.repeat(snapshot_array, num_states, axis=0)
    first_violations = np.full(len(states), -1, dtype=int)
    max_margins = np.full(len(states), -float("inf"), dtype=float)
    for step in range(steps):
        actions = trajectory_policy_actions(bundle, states, trajectory_snapshots)
        state_errors = states - bundle.goal
        action_errors = actions - bundle.equilibrium_action
        states = (
            bundle.goal
            + state_errors @ bundle.linear_a.T
            + action_errors @ bundle.linear_b.T
        )
        margins = state_margins(states, guard_margin)
        max_margins = np.maximum(max_margins, margins)
        newly_violated = (first_violations < 0) & (margins > 0.0)
        first_violations[newly_violated] = step
    return (
        first_violations.reshape(num_snapshots, num_states),
        max_margins.reshape(num_snapshots, num_states),
    )


def candidate_initial_states(seed: int, random_states: int = 24) -> list[np.ndarray]:
    """Interior states that excite lateral/pitch motion without boundary starts."""
    states = [
        np.asarray(values, dtype=float)
        for values in product(
            (-0.35, 0.0, 0.35),
            (0.0,),
            (0.75, 1.0, 1.25),
            (0.0,),
            (-0.04, 0.0, 0.04),
            (0.0,),
        )
        if abs(values[0]) + abs(values[4]) > 0.0
    ]
    rng = np.random.default_rng(seed)
    lows = np.asarray([-0.4, -0.12, 0.72, -0.12, -0.05, -0.12])
    highs = np.asarray([0.4, 0.12, 1.28, 0.12, 0.05, 0.12])
    states.extend(rng.uniform(lows, highs) for _ in range(random_states))
    return states


def baseline_viable_states(
    bundle: DynamicsBundle,
    states: Iterable[np.ndarray],
    *,
    steps: int,
    guard_margin: float = 0.0,
) -> list[np.ndarray]:
    state_list = list(states)
    first_matrix, margin_matrix = linear_snapshot_outcomes(
        bundle,
        [np.zeros((2, 2), dtype=float)],
        state_list,
        steps=steps,
    )
    first, margins = first_matrix[0], margin_matrix[0]
    return [
        state
        for state, first_step, margin in zip(state_list, first, margins)
        if first_step < 0 and margin <= -guard_margin
    ]


def spread_subset(states: Sequence[np.ndarray], count: int) -> list[np.ndarray]:
    """Select deterministic, order-spanning states instead of a prefix."""
    if count <= 0:
        raise ValueError("count must be positive")
    if count >= len(states):
        return list(states)
    indices = np.linspace(0, len(states) - 1, count, dtype=int)
    return [states[int(index)] for index in indices]


def score_attack_candidate(
    bundle: DynamicsBundle,
    initial_states: Sequence[np.ndarray],
    theta_weight: float,
    theta_dot_weight: float,
    *,
    steps: int,
    minimum_delay: int,
) -> AttackCandidate:
    snapshot = antisymmetric_snapshot(theta_weight, theta_dot_weight)
    first, margins = casadi_rollout_outcomes(
        bundle, snapshot, initial_states, steps=steps
    )
    violations = first[first >= 0]
    return AttackCandidate(
        theta_weight=theta_weight,
        theta_dot_weight=theta_dot_weight,
        violating_rollouts=int(len(violations)),
        delayed_violations=int(np.sum(violations >= minimum_delay)),
        immediate_violations=int(np.sum((violations >= 0) & (violations < minimum_delay))),
        median_first_violation_step=(
            float(median(int(value) for value in violations))
            if len(violations)
            else None
        ),
        worst_margin=float(np.max(margins)),
    )


def search_delayed_attack(
    bundle: DynamicsBundle,
    initial_states: Sequence[np.ndarray],
    *,
    steps: int,
    minimum_delay: int,
) -> tuple[np.ndarray, list[AttackCandidate]]:
    """Search policy targets; the attacker never receives parameter-write access."""
    theta_weights = (-0.08, -0.06, -0.04, -0.03, -0.02, -0.01, 0.01, 0.02, 0.03, 0.04, 0.06, 0.08)
    rate_weights = (-0.04, -0.025, -0.015, -0.008, 0.0, 0.008, 0.015, 0.025, 0.04)
    weight_pairs = list(product(theta_weights, rate_weights))
    snapshots = [antisymmetric_snapshot(*weights) for weights in weight_pairs]
    first_matrix, margin_matrix = linear_snapshot_outcomes(
        bundle,
        snapshots,
        initial_states,
        steps=steps,
    )
    candidates: list[AttackCandidate] = []
    for (theta_weight, rate_weight), first, margins in zip(
        weight_pairs, first_matrix, margin_matrix
    ):
        violations = first[first >= 0]
        candidates.append(
            AttackCandidate(
                theta_weight=theta_weight,
                theta_dot_weight=rate_weight,
                violating_rollouts=int(len(violations)),
                delayed_violations=int(np.sum(violations >= minimum_delay)),
                immediate_violations=int(
                    np.sum((violations >= 0) & (violations < minimum_delay))
                ),
                median_first_violation_step=(
                    float(median(int(value) for value in violations))
                    if len(violations)
                    else None
                ),
                worst_margin=float(np.max(margins)),
            )
        )
    # First maximize genuinely delayed failures, then coverage.  Penalizing
    # immediate failures prevents a constant-torque boundary artifact from
    # masquerading as a delayed lifecycle attack.
    best = max(
        candidates,
        key=lambda item: (
            item.delayed_violations,
            item.violating_rollouts,
            -item.immediate_violations,
            item.worst_margin,
        ),
    )
    return antisymmetric_snapshot(best.theta_weight, best.theta_dot_weight), candidates


def print_attack_search(candidates: Sequence[AttackCandidate], total: int, top: int = 12) -> None:
    ranked = sorted(
        candidates,
        key=lambda item: (
            item.delayed_violations,
            item.violating_rollouts,
            -item.immediate_violations,
            item.worst_margin,
        ),
        reverse=True,
    )[:top]
    print("| theta_w | rate_w | violating | delayed | immediate | median_first | worst_margin |")
    print("|---:|---:|---:|---:|---:|---:|---:|")
    for row in ranked:
        first = "-" if row.median_first_violation_step is None else f"{row.median_first_violation_step:.1f}"
        print(
            f"| {row.theta_weight:.3f} | {row.theta_dot_weight:.3f} | "
            f"{row.violating_rollouts}/{total} | {row.delayed_violations} | "
            f"{row.immediate_violations} | {first} | {row.worst_margin:.4f} |"
        )


def exact_certificate_admission(
    bundle: DynamicsBundle,
    candidate_states: Sequence[np.ndarray],
    *,
    steps: int,
    guard_margin: float,
) -> list[np.ndarray]:
    """Admit only states where the trusted snapshot passes the exact model."""
    first, margins = casadi_rollout_outcomes(
        bundle,
        np.zeros((2, 2), dtype=float),
        candidate_states,
        steps=steps,
    )
    return [
        state
        for state, first_step, margin in zip(candidate_states, first, margins)
        if first_step < 0 and margin <= -guard_margin
    ]


def commit_backtracked_snapshot(
    bundle: DynamicsBundle,
    pending_snapshot: np.ndarray,
    certificate_states: Sequence[np.ndarray],
    *,
    steps: int,
    guard_margin: float,
) -> tuple[np.ndarray, float]:
    """Commit the largest contiguous safe interpolation from trusted W=0."""
    fractions = np.linspace(0.0, 1.0, 21)
    trials = [float(fraction) * pending_snapshot for fraction in fractions]
    first_matrix, margin_matrix = casadi_snapshot_outcomes(
        bundle,
        trials,
        certificate_states,
        steps=steps,
    )
    accepted_index = 0
    for index, (first, margins) in enumerate(zip(first_matrix, margin_matrix)):
        safe = bool(np.all(first < 0) and np.max(margins) <= -guard_margin)
        if not safe:
            break
        accepted_index = index
    return trials[accepted_index], float(fractions[accepted_index])


def plausible_states(observation: np.ndarray, z_radius: float, theta_radius: float) -> np.ndarray:
    """Five-point declared uncertainty set over altitude and pitch sensors."""
    observation = np.asarray(observation, dtype=float)
    samples = [observation.copy()]
    for z_sign, theta_sign in product((-1.0, 1.0), repeat=2):
        sample = observation.copy()
        sample[2] += z_sign * z_radius
        sample[4] += theta_sign * theta_radius
        samples.append(sample)
    return np.vstack(samples)


def action_grid(bundle: DynamicsBundle, grid_size: int) -> np.ndarray:
    axes = [
        np.linspace(low, high, grid_size)
        for low, high in zip(bundle.action_low, bundle.action_high)
    ]
    return np.asarray(list(product(*axes)), dtype=float)


def permanent_filter_action(
    bundle: DynamicsBundle,
    observation: np.ndarray,
    raw_action: np.ndarray,
    baseline_action: np.ndarray,
    fixed_grid: np.ndarray,
    *,
    z_radius: float,
    theta_radius: float,
    guard_margin: float,
    backup_steps: int,
) -> tuple[np.ndarray, bool, float]:
    """Project onto actions with a robust trusted-controller backup rollout.

    Each candidate is applied for one exact CasADi step from every declared
    plausible state, followed by ``backup_steps - 1`` exact-model steps under
    clipped trusted LQR.  This is a finite-horizon backup shield, not a formal
    infinite-horizon invariant-set claim.  If its sampled kernel is empty, the
    function rejects the action and invokes clipped LQR as an explicit
    fail-safe.
    """
    raw_action = np.clip(np.asarray(raw_action, dtype=float), bundle.action_low, bundle.action_high)
    baseline_action = np.clip(
        np.asarray(baseline_action, dtype=float), bundle.action_low, bundle.action_high
    )
    candidates = np.vstack([raw_action, baseline_action, fixed_grid])
    # Removing duplicates matters because the exact integrator is the dominant
    # online-filter cost; preserve raw and baseline by sorting after uniqueness.
    candidates = np.unique(np.round(candidates, decimals=12), axis=0)
    samples = plausible_states(observation, z_radius, theta_radius)
    if np.any(state_margins(samples) > 0.0):
        return baseline_action, False, float(np.linalg.norm(raw_action - baseline_action))
    num_actions, num_samples = len(candidates), len(samples)
    state_batch = np.tile(samples, (num_actions, 1))
    action_batch = np.repeat(candidates, num_samples, axis=0)
    forecast_states = np.asarray(
        bundle.fd_func(x0=state_batch.T, p=action_batch.T)["xf"], dtype=float
    ).T
    valid_trajectories = np.all(
        (forecast_states >= SAFE_LOW + guard_margin)
        & (forecast_states <= SAFE_HIGH - guard_margin),
        axis=1,
    )
    for _step in range(1, max(1, backup_steps)):
        backup_actions = policy_actions(
            bundle, forecast_states, np.zeros((2, 2), dtype=float)
        )
        forecast_states = np.asarray(
            bundle.fd_func(x0=forecast_states.T, p=backup_actions.T)["xf"],
            dtype=float,
        ).T
        valid_trajectories &= np.all(
            (forecast_states >= SAFE_LOW + guard_margin)
            & (forecast_states <= SAFE_HIGH - guard_margin),
            axis=1,
        )
    valid = np.all(
        valid_trajectories.reshape(num_actions, num_samples), axis=1
    )
    valid_candidates = candidates[valid]
    if len(valid_candidates) == 0:
        return baseline_action, False, float(np.linalg.norm(raw_action - baseline_action))
    distances = np.linalg.norm(valid_candidates - raw_action, axis=1)
    projected = valid_candidates[int(np.argmin(distances))]
    return projected, True, float(np.linalg.norm(projected - raw_action))


def set_quadrotor_initial_state(env: object, state: np.ndarray) -> None:
    labels = ("X", "X_DOT", "Z", "Z_DOT", "THETA", "THETA_DOT")
    for label, value in zip(labels, np.asarray(state, dtype=float)):
        setattr(env, f"INIT_{label}", float(value))


def run_pybullet_deployments(
    bundle: DynamicsBundle,
    mechanisms: dict[str, np.ndarray],
    initial_states: Sequence[np.ndarray],
    *,
    seed: int,
    steps: int,
    minimum_delay: int,
    filter_grid_size: int,
    z_radius: float,
    theta_radius: float,
    filter_guard_margin: float,
    filter_backup_steps: int,
) -> list[DeploymentResult]:
    task_config = dict(bundle.task_config)
    env = make("quadrotor", **task_config)
    fixed_grid = action_grid(bundle, filter_grid_size)
    rows: list[DeploymentResult] = []
    for mechanism, snapshot in mechanisms.items():
        for rollout, initial_state in enumerate(initial_states):
            set_quadrotor_initial_state(env, initial_state)
            obs, _info = env.reset(seed=seed + rollout)
            first_violation: int | None = None
            violation_steps = 0
            interventions = 0
            rejections = 0
            rewards: list[float] = []
            executed = 0
            for step in range(steps):
                state_batch = np.asarray(obs, dtype=float).reshape(1, -1)
                baseline = policy_actions(
                    bundle, state_batch, np.zeros((2, 2), dtype=float)
                )[0]
                raw_action = policy_actions(bundle, state_batch, snapshot)[0]
                if "permanent_filter" in mechanism:
                    action, accepted, correction = permanent_filter_action(
                        bundle,
                        np.asarray(obs, dtype=float),
                        raw_action,
                        baseline,
                        fixed_grid,
                        z_radius=z_radius,
                        theta_radius=theta_radius,
                        guard_margin=filter_guard_margin,
                        backup_steps=filter_backup_steps,
                    )
                    interventions += int(correction > 1e-9)
                    rejections += int(not accepted)
                else:
                    action = raw_action
                obs, reward, _done, info = env.step(
                    np.clip(action, bundle.action_low, bundle.action_high)
                )
                executed += 1
                rewards.append(float(reward))
                violated = bool(info.get("constraint_violation", False)) or bool(
                    state_margins(np.asarray(env.state, dtype=float))[0] > 1e-9
                )
                violation_steps += int(violated)
                if violated and first_violation is None:
                    first_violation = step
                    # The first safety failure is absorbing for the hard-gate
                    # metric.  Stopping also avoids comparing post-crash reward.
                    break
            rows.append(
                DeploymentResult(
                    mechanism=mechanism,
                    rollout=rollout,
                    init_x=float(initial_state[0]),
                    init_x_dot=float(initial_state[1]),
                    init_z=float(initial_state[2]),
                    init_z_dot=float(initial_state[3]),
                    init_theta=float(initial_state[4]),
                    init_theta_dot=float(initial_state[5]),
                    steps_executed=executed,
                    violation_steps=violation_steps,
                    first_violation_step=first_violation,
                    filter_interventions=interventions,
                    filter_rejections=rejections,
                    mean_reward=float(np.mean(rewards)) if rewards else 0.0,
                )
            )
    env.close()
    return rows


def summarize_deployments(
    rows: Sequence[DeploymentResult],
    mechanisms: dict[str, np.ndarray],
    *,
    pending_snapshot: np.ndarray,
    committed_snapshot: np.ndarray,
    commit_fraction: float,
    minimum_delay: int,
    certificate_candidates: int,
    certificate_admitted: int,
) -> list[MechanismSummary]:
    summaries: list[MechanismSummary] = []
    for mechanism, snapshot in mechanisms.items():
        selected = [row for row in rows if row.mechanism == mechanism]
        violation_steps = [
            row.first_violation_step
            for row in selected
            if row.first_violation_step is not None
        ]
        summaries.append(
            MechanismSummary(
                mechanism=mechanism,
                deployment_rollouts=len(selected),
                violating_rollouts=len(violation_steps),
                deployment_violation_rate=(
                    len(violation_steps) / len(selected) if selected else 0.0
                ),
                immediate_violating_rollouts=sum(
                    int(step < minimum_delay) for step in violation_steps
                ),
                delayed_violating_rollouts=sum(
                    int(step >= minimum_delay) for step in violation_steps
                ),
                median_first_violation_step=(
                    float(median(violation_steps)) if violation_steps else None
                ),
                filter_interventions=sum(row.filter_interventions for row in selected),
                filter_rejections=sum(row.filter_rejections for row in selected),
                mean_deployment_reward=float(
                    np.mean([row.mean_reward for row in selected])
                ),
                pending_update_norm=float(np.linalg.norm(pending_snapshot)),
                committed_update_norm=float(np.linalg.norm(snapshot)),
                commit_fraction=(
                    commit_fraction
                    if mechanism == "poisoned_commit_gate_snapshot"
                    else float(np.linalg.norm(snapshot) > 0.0)
                ),
                certificate_candidates=(
                    certificate_candidates
                    if mechanism == "poisoned_commit_gate_snapshot"
                    else 0
                ),
                certificate_admitted=(
                    certificate_admitted
                    if mechanism == "poisoned_commit_gate_snapshot"
                    else 0
                ),
            )
        )
    return summaries


def write_rows(path: Path, rows: Sequence[object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        return
    with path.open("w", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=list(asdict(rows[0]).keys()))
        writer.writeheader()
        writer.writerows(asdict(row) for row in rows)


def print_mechanism_summary(rows: Sequence[MechanismSummary]) -> None:
    print("| mechanism | violations | immediate | delayed | median_first | filter int/rej | ||W|| | mean reward |")
    print("|---|---:|---:|---:|---:|---:|---:|---:|")
    for row in rows:
        first = "-" if row.median_first_violation_step is None else f"{row.median_first_violation_step:.1f}"
        print(
            f"| {row.mechanism} | {row.violating_rollouts}/{row.deployment_rollouts} | "
            f"{row.immediate_violating_rollouts} | {row.delayed_violating_rollouts} | "
            f"{first} | {row.filter_interventions}/{row.filter_rejections} | "
            f"{row.committed_update_norm:.5f} | {row.mean_deployment_reward:.4f} |"
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, default=2026)
    parser.add_argument("--deployment-steps", type=int, default=100)
    parser.add_argument("--minimum-delay", type=int, default=8)
    parser.add_argument("--random-states", type=int, default=24)
    parser.add_argument("--deployment-rollouts", type=int, default=12)
    parser.add_argument("--certificate-states", type=int, default=16)
    parser.add_argument("--certificate-guard-margin", type=float, default=0.003)
    parser.add_argument("--filter-grid-size", type=int, default=5)
    parser.add_argument("--filter-z-radius", type=float, default=0.005)
    parser.add_argument("--filter-theta-radius", type=float, default=0.002)
    parser.add_argument("--filter-guard-margin", type=float, default=0.001)
    parser.add_argument("--filter-backup-steps", type=int, default=5)
    parser.add_argument(
        "--mechanisms",
        nargs="+",
        choices=MECHANISMS,
        default=list(MECHANISMS),
    )
    parser.add_argument("--search-only", action="store_true")
    parser.add_argument(
        "--out",
        type=Path,
        default=RESULTS_DIR / "safe_control_gym_quadrotor_lifecycle_scaffold.csv",
    )
    parser.add_argument(
        "--rollout-out",
        type=Path,
        default=RESULTS_DIR / "safe_control_gym_quadrotor_lifecycle_scaffold_rollouts.csv",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    bundle = build_dynamics(args.seed)
    candidates = candidate_initial_states(args.seed, args.random_states)
    viable = baseline_viable_states(
        bundle,
        candidates,
        steps=args.deployment_steps,
        guard_margin=0.01,
    )
    if not viable:
        raise RuntimeError("clipped LQR has no viable states in the candidate envelope")
    snapshot, search_rows = search_delayed_attack(
        bundle,
        viable,
        steps=args.deployment_steps,
        minimum_delay=args.minimum_delay,
    )
    print(
        f"physical_actions=[{bundle.action_low.tolist()}, {bundle.action_high.tolist()}] "
        f"candidate_states={len(candidates)} baseline_viable={len(viable)}"
    )
    print_attack_search(search_rows, len(viable))
    print(f"selected_snapshot={snapshot.tolist()}")
    if args.search_only:
        return

    certificate_candidates = spread_subset(viable, args.certificate_states)
    admitted = exact_certificate_admission(
        bundle,
        certificate_candidates,
        steps=args.deployment_steps,
        guard_margin=args.certificate_guard_margin,
    )
    if not admitted:
        raise RuntimeError("trusted clipped LQR admits no exact certificate states")
    committed, fraction = commit_backtracked_snapshot(
        bundle,
        snapshot,
        admitted,
        steps=args.deployment_steps,
        guard_margin=args.certificate_guard_margin,
    )
    all_mechanisms = {
        "trusted_clipped_lqr": np.zeros((2, 2), dtype=float),
        "harmful_raw_snapshot": snapshot,
        "harmful_permanent_filter": snapshot,
        "poisoned_always_freeze_snapshot": np.zeros((2, 2), dtype=float),
        "poisoned_commit_gate_snapshot": committed,
    }
    mechanisms = {
        name: all_mechanisms[name]
        for name in args.mechanisms
    }
    deployment_states = spread_subset(viable, args.deployment_rollouts)
    rollout_rows = run_pybullet_deployments(
        bundle,
        mechanisms,
        deployment_states,
        seed=args.seed,
        steps=args.deployment_steps,
        minimum_delay=args.minimum_delay,
        filter_grid_size=args.filter_grid_size,
        z_radius=args.filter_z_radius,
        theta_radius=args.filter_theta_radius,
        filter_guard_margin=args.filter_guard_margin,
        filter_backup_steps=args.filter_backup_steps,
    )
    summaries = summarize_deployments(
        rollout_rows,
        mechanisms,
        pending_snapshot=snapshot,
        committed_snapshot=committed,
        commit_fraction=fraction,
        minimum_delay=args.minimum_delay,
        certificate_candidates=len(certificate_candidates),
        certificate_admitted=len(admitted),
    )
    write_rows(args.out, summaries)
    write_rows(args.rollout_out, rollout_rows)
    print(
        f"commit_fraction={fraction:.2f} pending_norm={np.linalg.norm(snapshot):.6f} "
        f"committed_norm={np.linalg.norm(committed):.6f} "
        f"certificate={len(admitted)}/{len(certificate_candidates)}"
    )
    print_mechanism_summary(summaries)
    print(f"wrote {args.out}")
    print(f"wrote {args.rollout_out}")


if __name__ == "__main__":
    main()
