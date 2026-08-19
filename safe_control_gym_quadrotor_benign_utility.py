#!/usr/bin/env python3
"""Benign actuator-bias utility gate for LifecycleGate.

The shifted PyBullet plant and every certificate share a trusted persistent
differential actuator bias.  Three paired residual-REINFORCE mechanisms compare
raw clean adaptation, always-freeze, and an incremental lifecycle parameter
gate.  See ``benign_utility_protocol.md`` for the locked selection and gate
rules.
"""

from __future__ import annotations

import argparse
import csv
from copy import deepcopy
from dataclasses import asdict, dataclass
from pathlib import Path
from time import perf_counter
from typing import Iterable, Sequence

import numpy as np
from scipy.stats import wilcoxon

from safe_control_gym.utils.registration import make

import safe_control_gym_quadrotor_lifecycle_scaffold as quad
import safe_control_gym_quadrotor_reinforce_reward_poisoning as learner
import safe_control_gym_quadrotor_reinforce_reward_poisoning_sweep as sweep


ROOT = Path(__file__).resolve().parent
RESULTS_DIR = ROOT / "results"
MECHANISMS = ("clean_adaptation", "always_freeze", "lifecycle_gate")
DEFAULT_BIAS_GRID = (0.0005, 0.001, 0.002, 0.003, 0.004)


@dataclass
class CalibrationRow:
    bias_magnitude: float
    deployment_rollouts: int
    violating_rollouts: int
    actuator_saturation_rollouts: int
    nominal_mean_reward: float
    shifted_mean_reward: float
    reward_loss: float
    qualifies: bool
    selected: bool


@dataclass
class UtilityTraining:
    mechanism: str
    seed: int
    bias_magnitude: float
    batches: int
    batch_steps: int
    actor_updates: int
    accepted_update_batches: int
    mean_accepted_fraction: float
    adaptation_constraint_violations: int
    actuator_saturation_steps: int
    action_filter_interventions: int
    action_filter_rejections: int
    max_action_interface_error: float
    certificate_calls: int
    certificate_runtime_seconds: float
    mean_adaptation_reward: float
    final_w00: float
    final_w01: float
    final_w10: float
    final_w11: float


@dataclass
class UtilityTrace:
    mechanism: str
    seed: int
    batch: int
    mean_reward: float
    gradient_norm: float
    candidate_update_norm: float
    accepted_fraction: float
    accepted_update_norm: float
    filter_interventions: int
    filter_rejections: int
    constraint_violations: int
    certificate_runtime_seconds: float
    w00: float
    w01: float
    w10: float
    w11: float


@dataclass
class UtilityRollout:
    mechanism: str
    learner_seed: int
    source_seed: int
    source_index: int
    bias_magnitude: float
    steps_executed: int
    first_violation_step: int | None
    mean_reward: float
    mean_mse: float
    max_normalized_safety_margin: float
    actuator_saturation_steps: int
    max_action_interface_error: float


@dataclass
class UtilityAggregate:
    mechanism: str
    learner_seeds: int
    deployment_rollouts: int
    violating_rollouts: int
    mean_reward: float
    mean_mse: float
    mean_max_normalized_safety_margin: float
    actor_updates: int
    accepted_update_batches: int
    mean_accepted_fraction: float
    adaptation_constraint_violations: int
    actuator_saturation_steps: int
    action_filter_interventions: int
    action_filter_rejections: int
    certificate_calls: int
    certificate_runtime_seconds: float


@dataclass
class UtilityDecision:
    phase: str
    bias_magnitude: float
    learner_seeds: int
    paired_rollouts: int
    clean_reward_gain_over_freeze: float
    gate_reward_gain_over_freeze: float
    gate_retained_clean_improvement: float
    fraction_gate_reward_better: float
    paired_wilcoxon_pvalue: float
    seeds_with_positive_gate_gain: int
    gate_adaptation_violations: int
    gate_deployment_violations: int
    gate_filter_rejections: int
    seeds_with_accepted_update: int
    utility_gate_pass: bool


def write_csv(path: Path, rows: Iterable[object]) -> None:
    dictionaries = [asdict(row) for row in rows]
    if not dictionaries:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=list(dictionaries[0]))
        writer.writeheader()
        writer.writerows(dictionaries)


def bias_vector(magnitude: float) -> np.ndarray:
    return np.asarray([magnitude, -magnitude], dtype=float)


def task_config_with_bias(
    bundle: quad.DynamicsBundle, magnitude: float
) -> dict:
    config = deepcopy(bundle.task_config)
    if magnitude > 0.0:
        config["disturbances"] = {
            "action": [
                {
                    "disturbance_func": "step",
                    "magnitude": float(magnitude),
                    "mask": [1.0, -1.0],
                    "step_offset": 0,
                }
            ]
        }
    else:
        config["disturbances"] = None
    return config


def actual_actions(
    bundle: quad.DynamicsBundle,
    commands: np.ndarray,
    bias: np.ndarray,
) -> np.ndarray:
    return np.clip(
        np.asarray(commands, dtype=float) + np.asarray(bias, dtype=float),
        bundle.action_low,
        bundle.action_high,
    )


def normalized_state_margin(state: np.ndarray) -> float:
    state = np.asarray(state, dtype=float)
    span = quad.SAFE_HIGH - quad.SAFE_LOW
    return float(
        max(
            np.max((state - quad.SAFE_HIGH) / span),
            np.max((quad.SAFE_LOW - state) / span),
        )
    )


def physical_state_violation(env: object) -> bool:
    """Evaluate the stated plant-safety box on the realized PyBullet state.

    Safe-Control-Gym's aggregate ``constraint_violation`` also evaluates the
    disturbed thrust before the environment applies its physical actuator
    clipping.  Under the locked shift ``actual=clip(command+bias)``, that event
    is actuator saturation rather than an applied-input bound violation, so it
    is reported separately by :func:`actuator_saturated`.
    """
    return bool(
        quad.state_margins(np.asarray(env.state, dtype=float))[0] > 1e-9
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


def biased_snapshot_outcomes(
    bundle: quad.DynamicsBundle,
    snapshots: Sequence[np.ndarray],
    initial_states: Sequence[np.ndarray],
    bias: np.ndarray,
    *,
    steps: int,
    guard_margin: float = 0.0,
) -> tuple[np.ndarray, np.ndarray]:
    snapshot_array = np.stack(snapshots).astype(float)
    initial_array = np.vstack(initial_states).astype(float)
    num_snapshots, num_states = len(snapshot_array), len(initial_array)
    states = np.tile(initial_array, (num_snapshots, 1))
    trajectory_snapshots = np.repeat(snapshot_array, num_states, axis=0)
    first = np.full(len(states), -1, dtype=int)
    max_margins = np.full(len(states), -float("inf"), dtype=float)
    for step in range(steps):
        commands = quad.trajectory_policy_actions(
            bundle, states, trajectory_snapshots
        )
        actions = actual_actions(bundle, commands, bias)
        states = np.asarray(
            bundle.fd_func(x0=states.T, p=actions.T)["xf"], dtype=float
        ).T
        margins = quad.state_margins(states, guard_margin)
        max_margins = np.maximum(max_margins, margins)
        newly = (first < 0) & (margins > 0.0)
        first[newly] = step
    return (
        first.reshape(num_snapshots, num_states),
        max_margins.reshape(num_snapshots, num_states),
    )


def bias_admitted_states(
    bundle: quad.DynamicsBundle,
    candidates: Sequence[np.ndarray],
    bias: np.ndarray,
    *,
    steps: int,
    guard_margin: float,
) -> list[np.ndarray]:
    first, margins = biased_snapshot_outcomes(
        bundle,
        [np.zeros((2, 2), dtype=float)],
        candidates,
        bias,
        steps=steps,
    )
    return [
        state
        for state, first_step, margin in zip(candidates, first[0], margins[0])
        if first_step < 0 and margin <= -guard_margin
    ]


def bias_aware_filter_action(
    bundle: quad.DynamicsBundle,
    observation: np.ndarray,
    raw_command: np.ndarray,
    baseline_command: np.ndarray,
    fixed_grid: np.ndarray,
    bias: np.ndarray,
    *,
    z_radius: float,
    theta_radius: float,
    guard_margin: float,
    backup_steps: int,
) -> tuple[np.ndarray, bool, float]:
    raw_command = np.clip(raw_command, bundle.action_low, bundle.action_high)
    baseline_command = np.clip(
        baseline_command, bundle.action_low, bundle.action_high
    )
    candidates = np.unique(
        np.round(np.vstack([raw_command, baseline_command, fixed_grid]), 12),
        axis=0,
    )
    samples = quad.plausible_states(observation, z_radius, theta_radius)
    if np.any(quad.state_margins(samples) > 0.0):
        return (
            baseline_command,
            False,
            float(np.linalg.norm(raw_command - baseline_command)),
        )
    num_actions, num_samples = len(candidates), len(samples)
    states = np.tile(samples, (num_actions, 1))
    commands = np.repeat(candidates, num_samples, axis=0)
    actions = actual_actions(bundle, commands, bias)
    forecast = np.asarray(
        bundle.fd_func(x0=states.T, p=actions.T)["xf"], dtype=float
    ).T
    valid = np.all(
        (forecast >= quad.SAFE_LOW + guard_margin)
        & (forecast <= quad.SAFE_HIGH - guard_margin),
        axis=1,
    )
    for _ in range(1, max(1, backup_steps)):
        backup_commands = quad.policy_actions(
            bundle, forecast, np.zeros((2, 2), dtype=float)
        )
        backup_actions = actual_actions(bundle, backup_commands, bias)
        forecast = np.asarray(
            bundle.fd_func(x0=forecast.T, p=backup_actions.T)["xf"],
            dtype=float,
        ).T
        valid &= np.all(
            (forecast >= quad.SAFE_LOW + guard_margin)
            & (forecast <= quad.SAFE_HIGH - guard_margin),
            axis=1,
        )
    valid = np.all(valid.reshape(num_actions, num_samples), axis=1)
    valid_candidates = candidates[valid]
    if len(valid_candidates) == 0:
        return (
            baseline_command,
            False,
            float(np.linalg.norm(raw_command - baseline_command)),
        )
    distances = np.linalg.norm(valid_candidates - raw_command, axis=1)
    projected = valid_candidates[int(np.argmin(distances))]
    return projected, True, float(np.linalg.norm(projected - raw_command))


def project_lifecycle_update(
    bundle: quad.DynamicsBundle,
    current: np.ndarray,
    candidate: np.ndarray,
    certificate_states: Sequence[np.ndarray],
    bias: np.ndarray,
    *,
    steps: int,
    guard_margin: float,
) -> tuple[np.ndarray, float, bool, float]:
    start = perf_counter()
    fractions = np.linspace(0.0, 1.0, 21)
    snapshots = [
        current + float(fraction) * (candidate - current)
        for fraction in fractions
    ]
    first, margins = biased_snapshot_outcomes(
        bundle,
        snapshots,
        certificate_states,
        bias,
        steps=steps,
        guard_margin=guard_margin,
    )
    safe = np.all((first < 0) & (margins <= 0.0), axis=1)
    runtime = perf_counter() - start
    if not bool(safe[0]):
        return current.copy(), 0.0, False, runtime
    accepted_index = 0
    for index in range(1, len(fractions)):
        if not bool(safe[index]):
            break
        accepted_index = index
    fraction = float(fractions[accepted_index])
    return snapshots[accepted_index], fraction, True, runtime


def train_mechanism(
    mechanism: str,
    bundle: quad.DynamicsBundle,
    training_states: Sequence[np.ndarray],
    certificate_states: Sequence[np.ndarray],
    bias: np.ndarray,
    *,
    seed: int,
    batches: int,
    batch_steps: int,
    sigma: float,
    actor_lr: float,
    gamma: float,
    max_gradient_norm: float,
    certificate_steps: int,
    certificate_guard_margin: float,
    filter_grid_size: int,
    filter_z_radius: float,
    filter_theta_radius: float,
    filter_guard_margin: float,
    filter_backup_steps: int,
) -> tuple[np.ndarray, UtilityTraining, list[UtilityTrace]]:
    magnitude = float(abs(bias[0]))
    env = make("quadrotor", **task_config_with_bias(bundle, magnitude))
    fixed_grid = quad.action_grid(bundle, filter_grid_size)
    rng = np.random.default_rng(seed + 19107)
    snapshot = np.zeros((2, 2), dtype=float)
    traces: list[UtilityTrace] = []
    rewards_all: list[float] = []
    actor_updates = 0
    accepted_batches = 0
    accepted_fractions: list[float] = []
    violations_total = 0
    saturation_total = 0
    interventions_total = 0
    rejections_total = 0
    interface_errors: list[float] = []
    certificate_calls = 0
    certificate_runtime = 0.0

    for batch in range(batches):
        initial_state = training_states[batch % len(training_states)]
        quad.set_quadrotor_initial_state(env, initial_state)
        observation, _info = env.reset(seed=seed + batch)
        features_rows: list[np.ndarray] = []
        noise_rows: list[np.ndarray] = []
        reward_rows: list[float] = []
        done_rows: list[float] = []
        batch_interventions = 0
        batch_rejections = 0
        batch_violations = 0
        for step in range(batch_steps):
            state_batch = np.asarray(observation, dtype=float).reshape(1, -1)
            features = quad.actor_features(state_batch)[0]
            noise = rng.normal(0.0, sigma, size=2)
            baseline_command = quad.policy_actions(
                bundle, state_batch, np.zeros((2, 2), dtype=float)
            )[0]
            mean_command = quad.policy_actions(bundle, state_batch, snapshot)[0]
            proposal = np.clip(
                mean_command + noise, bundle.action_low, bundle.action_high
            )
            command, accepted, correction = bias_aware_filter_action(
                bundle,
                np.asarray(observation, dtype=float),
                proposal,
                baseline_command,
                fixed_grid,
                bias,
                z_radius=filter_z_radius,
                theta_radius=filter_theta_radius,
                guard_margin=filter_guard_margin,
                backup_steps=filter_backup_steps,
            )
            batch_interventions += int(correction > 1e-9)
            batch_rejections += int(not accepted)
            observation, reward, done, info = env.step(command)
            expected_actual = actual_actions(bundle, command, bias)
            interface_errors.append(
                float(
                    np.max(
                        np.abs(
                            np.asarray(env.current_clipped_action, dtype=float)
                            - expected_actual
                        )
                    )
                )
            )
            saturated = actuator_saturated(env)
            violated = physical_state_violation(env)
            saturation_total += int(saturated)
            batch_violations += int(violated)
            features_rows.append(features)
            noise_rows.append(noise)
            reward_rows.append(float(reward))
            done_rows.append(float(done or violated))
            if done or violated:
                quad.set_quadrotor_initial_state(env, initial_state)
                observation, _info = env.reset(seed=seed + batch + step + 1)

        features_array = np.vstack(features_rows)
        noise_array = np.vstack(noise_rows)
        rewards = np.asarray(reward_rows, dtype=float)
        dones = np.asarray(done_rows, dtype=float)
        dones[-1] = 1.0
        gradient = learner.reinforce_gradient(
            features_array,
            noise_array,
            rewards,
            dones,
            sigma=sigma,
            gamma=gamma,
        )
        gradient_norm = float(np.linalg.norm(gradient))
        if gradient_norm > max_gradient_norm:
            gradient *= max_gradient_norm / gradient_norm
            gradient_norm = max_gradient_norm
        candidate = np.clip(
            snapshot + actor_lr * gradient,
            -learner.PARAMETER_BOUND,
            learner.PARAMETER_BOUND,
        )
        candidate_norm = float(np.linalg.norm(candidate - snapshot))
        runtime = 0.0
        if mechanism == "always_freeze":
            updated = snapshot.copy()
            fraction = 0.0
        elif mechanism == "clean_adaptation":
            updated = candidate
            fraction = 1.0
        elif mechanism == "lifecycle_gate":
            updated, fraction, _current_certified, runtime = (
                project_lifecycle_update(
                    bundle,
                    snapshot,
                    candidate,
                    certificate_states,
                    bias,
                    steps=certificate_steps,
                    guard_margin=certificate_guard_margin,
                )
            )
            certificate_calls += 1
            certificate_runtime += runtime
        else:
            raise ValueError(f"unknown mechanism {mechanism}")
        accepted_norm = float(np.linalg.norm(updated - snapshot))
        actor_updates += int(accepted_norm > 1e-12)
        accepted_batches += int(accepted_norm > 1e-12)
        accepted_fractions.append(fraction)
        snapshot = updated
        rewards_all.extend(rewards.tolist())
        violations_total += batch_violations
        interventions_total += batch_interventions
        rejections_total += batch_rejections
        w00, w01, w10, w11 = learner.snapshot_fields(snapshot)
        traces.append(
            UtilityTrace(
                mechanism=mechanism,
                seed=seed,
                batch=batch,
                mean_reward=float(np.mean(rewards)),
                gradient_norm=gradient_norm,
                candidate_update_norm=candidate_norm,
                accepted_fraction=fraction,
                accepted_update_norm=accepted_norm,
                filter_interventions=batch_interventions,
                filter_rejections=batch_rejections,
                constraint_violations=batch_violations,
                certificate_runtime_seconds=runtime,
                w00=w00,
                w01=w01,
                w10=w10,
                w11=w11,
            )
        )
    env.close()
    w00, w01, w10, w11 = learner.snapshot_fields(snapshot)
    result = UtilityTraining(
        mechanism=mechanism,
        seed=seed,
        bias_magnitude=magnitude,
        batches=batches,
        batch_steps=batch_steps,
        actor_updates=actor_updates,
        accepted_update_batches=accepted_batches,
        mean_accepted_fraction=float(np.mean(accepted_fractions)),
        adaptation_constraint_violations=violations_total,
        actuator_saturation_steps=saturation_total,
        action_filter_interventions=interventions_total,
        action_filter_rejections=rejections_total,
        max_action_interface_error=float(np.max(interface_errors)),
        certificate_calls=certificate_calls,
        certificate_runtime_seconds=certificate_runtime,
        mean_adaptation_reward=float(np.mean(rewards_all)),
        final_w00=w00,
        final_w01=w01,
        final_w10=w10,
        final_w11=w11,
    )
    return snapshot, result, traces


def run_deployments(
    bundle: quad.DynamicsBundle,
    snapshots: dict[str, np.ndarray],
    states: Sequence[sweep.HeldoutState],
    bias: np.ndarray,
    *,
    learner_seed: int,
    steps: int,
) -> list[UtilityRollout]:
    magnitude = float(abs(bias[0]))
    env = make("quadrotor", **task_config_with_bias(bundle, magnitude))
    rows: list[UtilityRollout] = []
    for mechanism, snapshot in snapshots.items():
        for rollout, item in enumerate(states):
            quad.set_quadrotor_initial_state(env, item.state)
            observation, _info = env.reset(seed=learner_seed + rollout)
            rewards: list[float] = []
            mses: list[float] = []
            margins: list[float] = []
            interface_errors: list[float] = []
            first_violation: int | None = None
            saturation_steps = 0
            executed = 0
            for step in range(steps):
                command = quad.policy_actions(
                    bundle,
                    np.asarray(observation, dtype=float).reshape(1, -1),
                    snapshot,
                )[0]
                observation, reward, _done, info = env.step(command)
                saturation_steps += int(actuator_saturated(env))
                expected_actual = actual_actions(bundle, command, bias)
                interface_errors.append(
                    float(
                        np.max(
                            np.abs(
                                np.asarray(env.current_clipped_action, dtype=float)
                                - expected_actual
                            )
                        )
                    )
                )
                rewards.append(float(reward))
                mses.append(float(info.get("mse", np.nan)))
                margins.append(normalized_state_margin(np.asarray(env.state)))
                executed += 1
                violated = physical_state_violation(env)
                if violated:
                    first_violation = step
                    break
            rows.append(
                UtilityRollout(
                    mechanism=mechanism,
                    learner_seed=learner_seed,
                    source_seed=item.source_seed,
                    source_index=item.source_index,
                    bias_magnitude=magnitude,
                    steps_executed=executed,
                    first_violation_step=first_violation,
                    mean_reward=float(np.mean(rewards)),
                    mean_mse=float(np.nanmean(mses)),
                    max_normalized_safety_margin=float(np.max(margins)),
                    actuator_saturation_steps=saturation_steps,
                    max_action_interface_error=float(np.max(interface_errors)),
                )
            )
    env.close()
    return rows


def heldout_states(
    bundle: quad.DynamicsBundle,
    source_seeds: Sequence[int],
    bias: np.ndarray,
    *,
    candidates_per_seed: int,
    count: int,
    steps: int,
    guard_margin: float,
) -> list[sweep.HeldoutState]:
    candidates = [
        sweep.HeldoutState(seed, index, state)
        for seed in source_seeds
        for index, state in enumerate(
            sweep.random_initial_states(seed, candidates_per_seed)
        )
    ]
    admitted_raw = bias_admitted_states(
        bundle,
        [item.state for item in candidates],
        bias,
        steps=steps,
        guard_margin=guard_margin,
    )
    admitted_keys = {tuple(np.asarray(state, dtype=float)) for state in admitted_raw}
    admitted = [
        item for item in candidates if tuple(item.state) in admitted_keys
    ]
    return sweep.spread_heldout(admitted, count)


def snapshot_from_training(training: UtilityTraining) -> np.ndarray:
    return np.asarray(
        [
            [training.final_w00, training.final_w01],
            [training.final_w10, training.final_w11],
        ],
        dtype=float,
    )


def aggregate(
    trainings: Sequence[UtilityTraining],
    rollouts: Sequence[UtilityRollout],
) -> list[UtilityAggregate]:
    output: list[UtilityAggregate] = []
    for mechanism in MECHANISMS:
        selected_training = [
            row for row in trainings if row.mechanism == mechanism
        ]
        selected_rollouts = [
            row for row in rollouts if row.mechanism == mechanism
        ]
        output.append(
            UtilityAggregate(
                mechanism=mechanism,
                learner_seeds=len({row.seed for row in selected_training}),
                deployment_rollouts=len(selected_rollouts),
                violating_rollouts=sum(
                    row.first_violation_step is not None
                    for row in selected_rollouts
                ),
                mean_reward=float(
                    np.mean([row.mean_reward for row in selected_rollouts])
                ),
                mean_mse=float(
                    np.mean([row.mean_mse for row in selected_rollouts])
                ),
                mean_max_normalized_safety_margin=float(
                    np.mean(
                        [
                            row.max_normalized_safety_margin
                            for row in selected_rollouts
                        ]
                    )
                ),
                actor_updates=sum(row.actor_updates for row in selected_training),
                accepted_update_batches=sum(
                    row.accepted_update_batches for row in selected_training
                ),
                mean_accepted_fraction=float(
                    np.mean(
                        [row.mean_accepted_fraction for row in selected_training]
                    )
                ),
                adaptation_constraint_violations=sum(
                    row.adaptation_constraint_violations
                    for row in selected_training
                ),
                actuator_saturation_steps=sum(
                    row.actuator_saturation_steps
                    for row in selected_training
                )
                + sum(
                    row.actuator_saturation_steps
                    for row in selected_rollouts
                ),
                action_filter_interventions=sum(
                    row.action_filter_interventions for row in selected_training
                ),
                action_filter_rejections=sum(
                    row.action_filter_rejections for row in selected_training
                ),
                certificate_calls=sum(
                    row.certificate_calls for row in selected_training
                ),
                certificate_runtime_seconds=sum(
                    row.certificate_runtime_seconds for row in selected_training
                ),
            )
        )
    return output


def decide(
    phase: str,
    bias: np.ndarray,
    trainings: Sequence[UtilityTraining],
    rollouts: Sequence[UtilityRollout],
    aggregates: Sequence[UtilityAggregate],
) -> UtilityDecision:
    by_aggregate = {row.mechanism: row for row in aggregates}
    lookup = {
        (
            row.learner_seed,
            row.source_seed,
            row.source_index,
            row.mechanism,
        ): row
        for row in rollouts
    }
    keys = sorted(
        (row.learner_seed, row.source_seed, row.source_index)
        for row in rollouts
        if row.mechanism == "always_freeze"
    )
    gate_differences = np.asarray(
        [
            lookup[(*key, "lifecycle_gate")].mean_reward
            - lookup[(*key, "always_freeze")].mean_reward
            for key in keys
        ],
        dtype=float,
    )
    if np.allclose(gate_differences, 0.0):
        pvalue = 1.0
    else:
        pvalue = float(
            wilcoxon(gate_differences, alternative="greater").pvalue
        )
    freeze_reward = by_aggregate["always_freeze"].mean_reward
    clean_gain = by_aggregate["clean_adaptation"].mean_reward - freeze_reward
    gate_gain = by_aggregate["lifecycle_gate"].mean_reward - freeze_reward
    retained = gate_gain / clean_gain if clean_gain > 0.0 else -float("inf")
    learner_seeds = sorted({row.seed for row in trainings})
    positive_seed_gains = 0
    accepted_seeds = 0
    for seed in learner_seeds:
        seed_rollouts = [row for row in rollouts if row.learner_seed == seed]
        seed_freeze = np.mean(
            [
                row.mean_reward
                for row in seed_rollouts
                if row.mechanism == "always_freeze"
            ]
        )
        seed_gate = np.mean(
            [
                row.mean_reward
                for row in seed_rollouts
                if row.mechanism == "lifecycle_gate"
            ]
        )
        positive_seed_gains += int(seed_gate > seed_freeze)
        accepted_seeds += int(
            any(
                row.seed == seed
                and row.mechanism == "lifecycle_gate"
                and row.accepted_update_batches > 0
                for row in trainings
            )
        )
    gate_training = [
        row for row in trainings if row.mechanism == "lifecycle_gate"
    ]
    gate_adaptation_violations = sum(
        row.adaptation_constraint_violations for row in gate_training
    )
    gate_rejections = sum(
        row.action_filter_rejections for row in gate_training
    )
    gate_deployment_violations = by_aggregate[
        "lifecycle_gate"
    ].violating_rollouts
    if phase == "smoke":
        passed = bool(
            clean_gain >= 0.005
            and gate_gain >= 0.005
            and gate_adaptation_violations == 0
            and gate_deployment_violations == 0
            and gate_rejections == 0
            and accepted_seeds == len(learner_seeds)
        )
    else:
        passed = bool(
            gate_gain >= 0.005
            and float(np.mean(gate_differences > 0.0)) >= 0.75
            and pvalue < 0.05
            and positive_seed_gains == len(learner_seeds)
            and retained >= 0.80
            and gate_adaptation_violations == 0
            and gate_deployment_violations == 0
            and gate_rejections == 0
            and accepted_seeds == len(learner_seeds)
        )
    return UtilityDecision(
        phase=phase,
        bias_magnitude=float(abs(bias[0])),
        learner_seeds=len(learner_seeds),
        paired_rollouts=len(keys),
        clean_reward_gain_over_freeze=clean_gain,
        gate_reward_gain_over_freeze=gate_gain,
        gate_retained_clean_improvement=retained,
        fraction_gate_reward_better=float(
            np.mean(gate_differences > 0.0)
        ),
        paired_wilcoxon_pvalue=pvalue,
        seeds_with_positive_gate_gain=positive_seed_gains,
        gate_adaptation_violations=gate_adaptation_violations,
        gate_deployment_violations=gate_deployment_violations,
        gate_filter_rejections=gate_rejections,
        seeds_with_accepted_update=accepted_seeds,
        utility_gate_pass=passed,
    )


def train_seed(
    seed: int,
    bundle: quad.DynamicsBundle,
    bias: np.ndarray,
    args: argparse.Namespace,
) -> tuple[list[UtilityTraining], list[UtilityTrace], dict[str, np.ndarray]]:
    training_raw = sweep.random_initial_states(seed, args.training_candidates)
    training_admitted = bias_admitted_states(
        bundle,
        training_raw,
        bias,
        steps=args.deployment_steps,
        guard_margin=args.admission_guard_margin,
    )
    training_states = quad.spread_subset(training_admitted, args.batches)
    certificate_raw = sweep.random_initial_states(
        seed + args.certificate_seed_offset, args.certificate_candidates
    )
    certificate_admitted = bias_admitted_states(
        bundle,
        certificate_raw,
        bias,
        steps=args.deployment_steps,
        guard_margin=args.certificate_guard_margin,
    )
    certificate_states = quad.spread_subset(
        certificate_admitted, args.certificate_states
    )
    if len(training_states) < args.batches or not certificate_states:
        raise RuntimeError(
            f"seed {seed}: insufficient bias-admitted training/certificate states"
        )
    common = dict(
        seed=seed,
        batches=args.batches,
        batch_steps=args.batch_steps,
        sigma=args.sigma,
        actor_lr=args.actor_lr,
        gamma=args.gamma,
        max_gradient_norm=args.max_gradient_norm,
        certificate_steps=args.deployment_steps,
        certificate_guard_margin=args.certificate_guard_margin,
        filter_grid_size=args.filter_grid_size,
        filter_z_radius=args.filter_z_radius,
        filter_theta_radius=args.filter_theta_radius,
        filter_guard_margin=args.filter_guard_margin,
        filter_backup_steps=args.filter_backup_steps,
    )
    trainings: list[UtilityTraining] = []
    traces: list[UtilityTrace] = []
    snapshots: dict[str, np.ndarray] = {}
    for mechanism in MECHANISMS:
        snapshot, training, mechanism_traces = train_mechanism(
            mechanism,
            bundle,
            training_states,
            certificate_states,
            bias,
            **common,
        )
        trainings.append(training)
        traces.extend(mechanism_traces)
        snapshots[mechanism] = snapshot
    return trainings, traces, snapshots


def calibrate_bias(
    bundle: quad.DynamicsBundle,
    args: argparse.Namespace,
) -> tuple[float, list[CalibrationRow]]:
    nominal_candidates = sweep.random_initial_states(
        args.development_seed, args.calibration_candidates
    )
    nominal_admitted = bias_admitted_states(
        bundle,
        nominal_candidates,
        np.zeros(2),
        steps=args.deployment_steps,
        guard_margin=args.admission_guard_margin,
    )
    states_raw = quad.spread_subset(
        nominal_admitted, args.calibration_rollouts
    )
    states = [
        sweep.HeldoutState(args.development_seed, index, state)
        for index, state in enumerate(states_raw)
    ]
    zero = {"always_freeze": np.zeros((2, 2), dtype=float)}
    nominal_rows = run_deployments(
        bundle,
        zero,
        states,
        np.zeros(2),
        learner_seed=args.development_seed,
        steps=args.deployment_steps,
    )
    nominal_reward = float(np.mean([row.mean_reward for row in nominal_rows]))
    calibration: list[CalibrationRow] = []
    selected: float | None = None
    for magnitude in args.bias_grid:
        rows = run_deployments(
            bundle,
            zero,
            states,
            bias_vector(magnitude),
            learner_seed=args.development_seed,
            steps=args.deployment_steps,
        )
        violations = sum(row.first_violation_step is not None for row in rows)
        saturation_rollouts = sum(
            row.actuator_saturation_steps > 0 for row in rows
        )
        shifted_reward = float(np.mean([row.mean_reward for row in rows]))
        loss = nominal_reward - shifted_reward
        qualifies = violations == 0 and loss >= args.calibration_reward_loss
        if qualifies and selected is None:
            selected = float(magnitude)
        calibration.append(
            CalibrationRow(
                bias_magnitude=float(magnitude),
                deployment_rollouts=len(rows),
                violating_rollouts=violations,
                actuator_saturation_rollouts=saturation_rollouts,
                nominal_mean_reward=nominal_reward,
                shifted_mean_reward=shifted_reward,
                reward_loss=loss,
                qualifies=qualifies,
                selected=False,
            )
        )
    if selected is None:
        write_csv(args.calibration_out, calibration)
        raise RuntimeError("no actuator bias satisfies the locked calibration rule")
    for row in calibration:
        row.selected = row.bias_magnitude == selected
    write_csv(args.calibration_out, calibration)
    return selected, calibration


def run_phase(
    phase: str,
    learner_seeds: Sequence[int],
    evaluation_seeds: Sequence[int],
    bundle: quad.DynamicsBundle,
    bias: np.ndarray,
    args: argparse.Namespace,
) -> tuple[
    list[UtilityTraining],
    list[UtilityTrace],
    list[UtilityRollout],
    list[UtilityAggregate],
    UtilityDecision,
]:
    states = heldout_states(
        bundle,
        evaluation_seeds,
        bias,
        candidates_per_seed=args.evaluation_candidates_per_seed,
        count=(
            args.development_rollouts
            if phase == "smoke"
            else args.heldout_rollouts
        ),
        steps=args.deployment_steps,
        guard_margin=args.admission_guard_margin,
    )
    if not states:
        raise RuntimeError(f"{phase}: no bias-admitted deployment states")
    trainings: list[UtilityTraining] = []
    traces: list[UtilityTrace] = []
    rollouts: list[UtilityRollout] = []
    for seed in learner_seeds:
        print(f"{phase} learner_seed={seed}: training", flush=True)
        seed_training, seed_traces, snapshots = train_seed(
            seed, bundle, bias, args
        )
        trainings.extend(seed_training)
        traces.extend(seed_traces)
        rollouts.extend(
            run_deployments(
                bundle,
                snapshots,
                states,
                bias,
                learner_seed=seed,
                steps=args.deployment_steps,
            )
        )
    aggregates = aggregate(trainings, rollouts)
    decision = decide(phase, bias, trainings, rollouts, aggregates)
    return trainings, traces, rollouts, aggregates, decision


def print_aggregate(rows: Sequence[UtilityAggregate]) -> None:
    print(
        "| mechanism | violations | reward | mse | accepted | cert sec |",
        flush=True,
    )
    print("|---|---:|---:|---:|---:|---:|", flush=True)
    for row in rows:
        print(
            f"| {row.mechanism} | {row.violating_rollouts}/"
            f"{row.deployment_rollouts} | {row.mean_reward:.5f} | "
            f"{row.mean_mse:.5f} | {row.mean_accepted_fraction:.3f} | "
            f"{row.certificate_runtime_seconds:.3f} |",
            flush=True,
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--mode", choices=("calibrate", "smoke", "formal", "all"), default="all"
    )
    parser.add_argument("--bias", type=float, default=None)
    parser.add_argument(
        "--bias-grid", nargs="+", type=float, default=list(DEFAULT_BIAS_GRID)
    )
    parser.add_argument("--development-seed", type=int, default=2039)
    parser.add_argument(
        "--learner-seeds", nargs="+", type=int, default=[2050, 2051, 2052]
    )
    parser.add_argument(
        "--evaluation-seeds", nargs="+", type=int, default=[3050, 3051, 3052]
    )
    parser.add_argument("--development-evaluation-seed", type=int, default=3039)
    parser.add_argument("--calibration-candidates", type=int, default=48)
    parser.add_argument("--calibration-rollouts", type=int, default=12)
    parser.add_argument("--calibration-reward-loss", type=float, default=0.01)
    parser.add_argument("--training-candidates", type=int, default=48)
    parser.add_argument("--certificate-seed-offset", type=int, default=5000)
    parser.add_argument("--certificate-candidates", type=int, default=24)
    parser.add_argument("--certificate-states", type=int, default=16)
    parser.add_argument("--evaluation-candidates-per-seed", type=int, default=16)
    parser.add_argument("--development-rollouts", type=int, default=12)
    parser.add_argument("--heldout-rollouts", type=int, default=24)
    parser.add_argument("--batches", type=int, default=12)
    parser.add_argument("--batch-steps", type=int, default=12)
    parser.add_argument("--sigma", type=float, default=0.01)
    parser.add_argument("--actor-lr", type=float, default=0.02)
    parser.add_argument("--gamma", type=float, default=0.97)
    parser.add_argument("--max-gradient-norm", type=float, default=0.5)
    parser.add_argument("--deployment-steps", type=int, default=100)
    parser.add_argument("--admission-guard-margin", type=float, default=0.01)
    parser.add_argument("--certificate-guard-margin", type=float, default=0.003)
    parser.add_argument("--filter-grid-size", type=int, default=5)
    parser.add_argument("--filter-z-radius", type=float, default=0.005)
    parser.add_argument("--filter-theta-radius", type=float, default=0.002)
    parser.add_argument("--filter-guard-margin", type=float, default=0.01)
    parser.add_argument("--filter-backup-steps", type=int, default=5)
    parser.add_argument(
        "--calibration-out",
        type=Path,
        default=RESULTS_DIR / "safe_control_gym_quadrotor_benign_utility_calibration.csv",
    )
    parser.add_argument(
        "--prefix",
        type=Path,
        default=RESULTS_DIR / "safe_control_gym_quadrotor_benign_utility",
    )
    return parser.parse_args()


def write_phase(
    prefix: Path,
    phase: str,
    trainings: Sequence[UtilityTraining],
    traces: Sequence[UtilityTrace],
    rollouts: Sequence[UtilityRollout],
    aggregates: Sequence[UtilityAggregate],
    decision: UtilityDecision,
) -> None:
    base = Path(f"{prefix}_{phase}")
    write_csv(Path(f"{base}_training.csv"), trainings)
    write_csv(Path(f"{base}_traces.csv"), traces)
    write_csv(Path(f"{base}_rollouts.csv"), rollouts)
    write_csv(Path(f"{base}_aggregate.csv"), aggregates)
    write_csv(Path(f"{base}_decision.csv"), [decision])


def main() -> None:
    args = parse_args()
    bundle = quad.build_dynamics(args.development_seed)
    if args.bias is None:
        selected_bias, calibration = calibrate_bias(bundle, args)
        print(
            "calibration selected_bias="
            f"{selected_bias:.6f} from "
            f"{[(row.bias_magnitude, round(row.reward_loss, 5), row.violating_rollouts) for row in calibration]}",
            flush=True,
        )
    else:
        selected_bias = float(args.bias)
    if args.mode == "calibrate":
        return
    bias = bias_vector(selected_bias)
    smoke_result = None
    if args.mode in {"smoke", "all"}:
        smoke_result = run_phase(
            "smoke",
            [args.development_seed],
            [args.development_evaluation_seed],
            bundle,
            bias,
            args,
        )
        write_phase(args.prefix, "smoke", *smoke_result)
        print_aggregate(smoke_result[3])
        print(f"smoke utility_gate_pass={smoke_result[4].utility_gate_pass}")
        if not smoke_result[4].utility_gate_pass:
            print("STOP: development utility smoke did not pass", flush=True)
            return
    if args.mode in {"formal", "all"}:
        formal_result = run_phase(
            "formal",
            args.learner_seeds,
            args.evaluation_seeds,
            bundle,
            bias,
            args,
        )
        write_phase(args.prefix, "formal", *formal_result)
        print_aggregate(formal_result[3])
        print(
            f"formal utility_gate_pass={formal_result[4].utility_gate_pass} "
            f"wilcoxon_p={formal_result[4].paired_wilcoxon_pvalue:.3e}",
            flush=True,
        )


if __name__ == "__main__":
    main()
