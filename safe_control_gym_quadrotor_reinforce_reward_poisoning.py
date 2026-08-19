#!/usr/bin/env python3
"""Bounded reward poisoning of a shielded 2-D quadrotor REINFORCE actor.

The attacker may change only scalar rewards recorded by the learner, with an
explicit per-step L-infinity budget.  It cannot write actions, gradients, or
parameters.  The learner is a two-output Gaussian residual actor over pitch
and pitch rate, trained from real PyBullet transitions with reward-to-go
REINFORCE.  A finite-horizon backup shield protects every adaptation action.

After adaptation, the learned mean-policy snapshot is compared under five
lifecycle mechanisms: clean learning, reward-poisoned action-only deployment,
always-freeze, commit-time backtracking, and a permanent backup shield.
"""

from __future__ import annotations

import argparse
import csv
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from statistics import median
from typing import Iterable, Sequence

import numpy as np

from safe_control_gym.utils.registration import make

import safe_control_gym_quadrotor_lifecycle_scaffold as quad


ROOT = Path(__file__).resolve().parent
RESULTS_DIR = ROOT / "results"
PARAMETER_BOUND = 0.08
MECHANISMS = (
    "clean_reinforce_snapshot",
    "poisoned_action_only_snapshot",
    "poisoned_always_freeze_snapshot",
    "poisoned_commit_gate_snapshot",
    "poisoned_permanent_filter_snapshot",
)


@dataclass
class TrainingResult:
    mechanism: str
    seed: int
    batches: int
    batch_steps: int
    adaptation_steps: int
    sigma: float
    actor_lr: float
    reward_poison_budget: float
    max_reward_poison: float
    target_w00: float
    target_w01: float
    target_w10: float
    target_w11: float
    actor_updates: int
    action_filter_interventions: int
    rejected_action_steps: int
    adaptation_constraint_violations: int
    mean_true_reward: float
    mean_logged_reward: float
    mean_gradient_norm: float
    pending_w00: float
    pending_w01: float
    pending_w10: float
    pending_w11: float
    final_w00: float
    final_w01: float
    final_w10: float
    final_w11: float
    commit_fraction: float
    commit_projection_norm: float
    certificate_candidates: int
    certificate_admitted: int


@dataclass
class BatchTrace:
    mechanism: str
    seed: int
    batch: int
    true_reward_mean: float
    logged_reward_mean: float
    max_reward_poison: float
    gradient_norm: float
    w00: float
    w01: float
    w10: float
    w11: float
    distance_to_target: float
    filter_interventions: int
    filter_rejections: int
    constraint_violations: int


@dataclass
class ExperimentSummary:
    mechanism: str
    seed: int
    reward_poison_budget: float
    max_reward_poison: float
    adaptation_constraint_violations: int
    actor_updates: int
    action_filter_interventions: int
    rejected_action_steps: int
    pending_snapshot_norm: float
    final_snapshot_norm: float
    distance_to_target: float
    commit_fraction: float
    certificate_candidates: int
    certificate_admitted: int
    deployment_rollouts: int
    violating_rollouts: int
    deployment_violation_rate: float
    immediate_violating_rollouts: int
    delayed_violating_rollouts: int
    median_first_violation_step: float | None
    deployment_filter_interventions: int
    deployment_filter_rejections: int
    mean_deployment_reward: float


def reward_to_go(rewards: np.ndarray, dones: np.ndarray, gamma: float) -> np.ndarray:
    returns = np.zeros_like(rewards, dtype=float)
    running = 0.0
    for index in range(len(rewards) - 1, -1, -1):
        running = float(rewards[index]) + gamma * running * (1.0 - dones[index])
        returns[index] = running
    return returns


def reward_poison(
    exploration_noise: np.ndarray,
    features: np.ndarray,
    learner_snapshot: np.ndarray,
    target_snapshot: np.ndarray,
    *,
    budget: float,
    temperature: float,
    sigma: float,
    gamma: float,
    dones: np.ndarray,
) -> np.ndarray:
    """Maximize target-aligned REINFORCE progress through rewards alone.

    Reward-to-go couples reward ``j`` to every earlier score in the same
    episode.  The recurrence below computes that exact linear influence on the
    inner product between the learner gradient and ``target - current``.  The
    attacker then applies a smooth bounded sign.  It never substitutes a
    gradient or parameter update.
    """
    direction = np.asarray(target_snapshot, dtype=float) - np.asarray(
        learner_snapshot, dtype=float
    )
    scores = (
        exploration_noise[:, :, None] * features[:, None, :] / float(sigma**2)
    )
    score_alignment = np.einsum("tij,ij->t", scores, direction)
    # REINFORCE centers returns, so only centered score alignment contributes.
    centered = score_alignment - float(np.mean(score_alignment))
    coefficients = np.zeros_like(centered)
    running = 0.0
    for index, value in enumerate(centered):
        if index > 0 and bool(dones[index - 1]):
            running = 0.0
        running = float(value) + gamma * running
        coefficients[index] = running
    return budget * np.tanh(coefficients / temperature)


def reinforce_gradient(
    features: np.ndarray,
    exploration_noise: np.ndarray,
    logged_rewards: np.ndarray,
    dones: np.ndarray,
    *,
    sigma: float,
    gamma: float,
) -> np.ndarray:
    """Gaussian-mean reward-to-go REINFORCE gradient for a 2x2 actor."""
    returns = reward_to_go(logged_rewards, dones, gamma)
    advantages = returns - float(np.mean(returns))
    scale = float(np.std(advantages))
    if scale > 1e-8:
        advantages = advantages / scale
    scores = (
        exploration_noise[:, :, None] * features[:, None, :] / float(sigma**2)
    )
    return np.mean(advantages[:, None, None] * scores, axis=0)


def snapshot_fields(snapshot: np.ndarray) -> tuple[float, float, float, float]:
    flat = np.asarray(snapshot, dtype=float).reshape(-1)
    return tuple(float(value) for value in flat)  # type: ignore[return-value]


def choose_target(
    bundle: quad.DynamicsBundle,
    *,
    seed: int,
    deployment_steps: int,
    minimum_delay: int,
) -> tuple[np.ndarray, list[np.ndarray]]:
    candidates = quad.candidate_initial_states(seed)
    viable = quad.baseline_viable_states(
        bundle, candidates, steps=deployment_steps, guard_margin=0.01
    )
    target, _rows = quad.search_delayed_attack(
        bundle,
        viable,
        steps=deployment_steps,
        minimum_delay=minimum_delay,
    )
    return target, viable


def train_reinforce(
    mechanism: str,
    bundle: quad.DynamicsBundle,
    target_snapshot: np.ndarray,
    training_states: Sequence[np.ndarray],
    *,
    seed: int,
    poisoned_rewards: bool,
    freeze_updates: bool,
    batches: int,
    batch_steps: int,
    sigma: float,
    actor_lr: float,
    gamma: float,
    max_gradient_norm: float,
    reward_poison_budget: float,
    poison_temperature: float,
    filter_grid_size: int,
    filter_z_radius: float,
    filter_theta_radius: float,
    filter_guard_margin: float,
    filter_backup_steps: int,
) -> tuple[np.ndarray, TrainingResult, list[BatchTrace]]:
    env = make("quadrotor", **bundle.task_config)
    fixed_grid = quad.action_grid(bundle, filter_grid_size)
    rng = np.random.default_rng(seed + 9107)
    snapshot = np.zeros((2, 2), dtype=float)
    all_true_rewards: list[float] = []
    all_logged_rewards: list[float] = []
    gradient_norms: list[float] = []
    traces: list[BatchTrace] = []
    actor_updates = 0
    total_interventions = 0
    total_rejections = 0
    total_violations = 0
    maximum_poison = 0.0

    for batch in range(batches):
        initial_state = training_states[batch % len(training_states)]
        quad.set_quadrotor_initial_state(env, initial_state)
        observation, _info = env.reset(seed=seed + batch)
        feature_rows: list[np.ndarray] = []
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
            baseline = quad.policy_actions(
                bundle, state_batch, np.zeros((2, 2), dtype=float)
            )[0]
            mean_action = quad.policy_actions(bundle, state_batch, snapshot)[0]
            raw_action = np.clip(
                mean_action + noise, bundle.action_low, bundle.action_high
            )
            applied_action, accepted, correction = quad.permanent_filter_action(
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
            batch_interventions += int(correction > 1e-9)
            batch_rejections += int(not accepted)
            observation, reward, done, info = env.step(applied_action)
            violated = bool(info.get("constraint_violation", False)) or bool(
                quad.state_margins(np.asarray(env.state, dtype=float))[0] > 1e-9
            )
            batch_violations += int(violated)
            feature_rows.append(features)
            noise_rows.append(noise)
            reward_rows.append(float(reward))
            done_rows.append(float(done or violated))
            if done or violated:
                # A correct smoke should never enter this branch; resetting
                # prevents a single mismatch from corrupting the whole batch.
                quad.set_quadrotor_initial_state(env, initial_state)
                observation, _info = env.reset(seed=seed + batch + step + 1)

        features_array = np.vstack(feature_rows)
        noise_array = np.vstack(noise_rows)
        true_rewards = np.asarray(reward_rows, dtype=float)
        dones = np.asarray(done_rows, dtype=float)
        dones[-1] = 1.0
        poison = np.zeros_like(true_rewards)
        if poisoned_rewards:
            poison = reward_poison(
                noise_array,
                features_array,
                snapshot,
                target_snapshot,
                budget=reward_poison_budget,
                temperature=poison_temperature,
                sigma=sigma,
                gamma=gamma,
                dones=dones,
            )
        logged_rewards = true_rewards + poison
        gradient = reinforce_gradient(
            features_array,
            noise_array,
            logged_rewards,
            dones,
            sigma=sigma,
            gamma=gamma,
        )
        gradient_norm = float(np.linalg.norm(gradient))
        if gradient_norm > max_gradient_norm:
            gradient *= max_gradient_norm / gradient_norm
            gradient_norm = max_gradient_norm
        candidate = np.clip(
            snapshot + actor_lr * gradient, -PARAMETER_BOUND, PARAMETER_BOUND
        )
        if not freeze_updates:
            actor_updates += int(np.linalg.norm(candidate - snapshot) > 1e-12)
            snapshot = candidate

        maximum_poison = max(maximum_poison, float(np.max(np.abs(poison))))
        all_true_rewards.extend(true_rewards.tolist())
        all_logged_rewards.extend(logged_rewards.tolist())
        gradient_norms.append(gradient_norm)
        total_interventions += batch_interventions
        total_rejections += batch_rejections
        total_violations += batch_violations
        w00, w01, w10, w11 = snapshot_fields(snapshot)
        traces.append(
            BatchTrace(
                mechanism=mechanism,
                seed=seed,
                batch=batch,
                true_reward_mean=float(np.mean(true_rewards)),
                logged_reward_mean=float(np.mean(logged_rewards)),
                max_reward_poison=float(np.max(np.abs(poison))),
                gradient_norm=gradient_norm,
                w00=w00,
                w01=w01,
                w10=w10,
                w11=w11,
                distance_to_target=float(np.linalg.norm(snapshot - target_snapshot)),
                filter_interventions=batch_interventions,
                filter_rejections=batch_rejections,
                constraint_violations=batch_violations,
            )
        )

    env.close()
    target_values = snapshot_fields(target_snapshot)
    pending_values = snapshot_fields(snapshot)
    result = TrainingResult(
        mechanism=mechanism,
        seed=seed,
        batches=batches,
        batch_steps=batch_steps,
        adaptation_steps=batches * batch_steps,
        sigma=sigma,
        actor_lr=actor_lr,
        reward_poison_budget=reward_poison_budget,
        max_reward_poison=maximum_poison,
        target_w00=target_values[0],
        target_w01=target_values[1],
        target_w10=target_values[2],
        target_w11=target_values[3],
        actor_updates=actor_updates,
        action_filter_interventions=total_interventions,
        rejected_action_steps=total_rejections,
        adaptation_constraint_violations=total_violations,
        mean_true_reward=float(np.mean(all_true_rewards)),
        mean_logged_reward=float(np.mean(all_logged_rewards)),
        mean_gradient_norm=float(np.mean(gradient_norms)),
        pending_w00=pending_values[0],
        pending_w01=pending_values[1],
        pending_w10=pending_values[2],
        pending_w11=pending_values[3],
        final_w00=pending_values[0],
        final_w01=pending_values[1],
        final_w10=pending_values[2],
        final_w11=pending_values[3],
        commit_fraction=1.0,
        commit_projection_norm=0.0,
        certificate_candidates=0,
        certificate_admitted=0,
    )
    return snapshot, result, traces


def final_snapshot(training: TrainingResult) -> np.ndarray:
    return np.asarray(
        [
            [training.final_w00, training.final_w01],
            [training.final_w10, training.final_w11],
        ],
        dtype=float,
    )


def summarize(
    training: TrainingResult,
    rollout_rows: Sequence[quad.DeploymentResult],
    target_snapshot: np.ndarray,
    *,
    minimum_delay: int,
) -> ExperimentSummary:
    first_steps = [
        int(row.first_violation_step)
        for row in rollout_rows
        if row.first_violation_step is not None
    ]
    pending = np.asarray(
        [
            [training.pending_w00, training.pending_w01],
            [training.pending_w10, training.pending_w11],
        ]
    )
    final = final_snapshot(training)
    return ExperimentSummary(
        mechanism=training.mechanism,
        seed=training.seed,
        reward_poison_budget=training.reward_poison_budget,
        max_reward_poison=training.max_reward_poison,
        adaptation_constraint_violations=training.adaptation_constraint_violations,
        actor_updates=training.actor_updates,
        action_filter_interventions=training.action_filter_interventions,
        rejected_action_steps=training.rejected_action_steps,
        pending_snapshot_norm=float(np.linalg.norm(pending)),
        final_snapshot_norm=float(np.linalg.norm(final)),
        distance_to_target=float(np.linalg.norm(final - target_snapshot)),
        commit_fraction=training.commit_fraction,
        certificate_candidates=training.certificate_candidates,
        certificate_admitted=training.certificate_admitted,
        deployment_rollouts=len(rollout_rows),
        violating_rollouts=len(first_steps),
        deployment_violation_rate=(
            len(first_steps) / len(rollout_rows) if rollout_rows else 0.0
        ),
        immediate_violating_rollouts=sum(step < minimum_delay for step in first_steps),
        delayed_violating_rollouts=sum(step >= minimum_delay for step in first_steps),
        median_first_violation_step=(
            float(median(first_steps)) if first_steps else None
        ),
        deployment_filter_interventions=sum(
            row.filter_interventions for row in rollout_rows
        ),
        deployment_filter_rejections=sum(row.filter_rejections for row in rollout_rows),
        mean_deployment_reward=float(
            np.mean([row.mean_reward for row in rollout_rows])
        ),
    )


def write_csv(path: Path, rows: Iterable[object]) -> None:
    dictionaries = [asdict(row) for row in rows]
    if not dictionaries:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=list(dictionaries[0].keys()))
        writer.writeheader()
        writer.writerows(dictionaries)


def print_summary(rows: Sequence[ExperimentSummary]) -> None:
    print("| mechanism | train viol | updates | ||pending|| -> ||final|| | deploy viol | delayed | median first | filter int/rej |")
    print("|---|---:|---:|---:|---:|---:|---:|---:|")
    for row in rows:
        first = "-" if row.median_first_violation_step is None else f"{row.median_first_violation_step:.1f}"
        print(
            f"| {row.mechanism} | {row.adaptation_constraint_violations} | "
            f"{row.actor_updates} | {row.pending_snapshot_norm:.5f} -> "
            f"{row.final_snapshot_norm:.5f} | {row.violating_rollouts}/"
            f"{row.deployment_rollouts} | {row.delayed_violating_rollouts} | "
            f"{first} | {row.deployment_filter_interventions}/"
            f"{row.deployment_filter_rejections} |"
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, default=2040)
    parser.add_argument("--batches", type=int, default=12)
    parser.add_argument("--batch-steps", type=int, default=12)
    parser.add_argument("--sigma", type=float, default=0.01)
    parser.add_argument("--actor-lr", type=float, default=0.02)
    parser.add_argument("--gamma", type=float, default=0.97)
    parser.add_argument("--max-gradient-norm", type=float, default=0.5)
    parser.add_argument("--reward-poison-budget", type=float, default=0.5)
    parser.add_argument("--poison-temperature", type=float, default=0.5)
    parser.add_argument("--deployment-steps", type=int, default=100)
    parser.add_argument("--deployment-rollouts", type=int, default=8)
    parser.add_argument("--minimum-delay", type=int, default=8)
    parser.add_argument("--certificate-states", type=int, default=12)
    parser.add_argument("--certificate-guard-margin", type=float, default=0.003)
    parser.add_argument("--filter-grid-size", type=int, default=5)
    parser.add_argument("--filter-z-radius", type=float, default=0.005)
    parser.add_argument("--filter-theta-radius", type=float, default=0.002)
    parser.add_argument("--filter-guard-margin", type=float, default=0.01)
    parser.add_argument("--filter-backup-steps", type=int, default=5)
    parser.add_argument(
        "--mechanisms",
        nargs="+",
        choices=MECHANISMS,
        default=list(MECHANISMS),
    )
    parser.add_argument(
        "--summary-out",
        type=Path,
        default=RESULTS_DIR / "safe_control_gym_quadrotor_reinforce_reward_poisoning.csv",
    )
    parser.add_argument(
        "--rollouts-out",
        type=Path,
        default=RESULTS_DIR / "safe_control_gym_quadrotor_reinforce_reward_poisoning_rollouts.csv",
    )
    parser.add_argument(
        "--traces-out",
        type=Path,
        default=RESULTS_DIR / "safe_control_gym_quadrotor_reinforce_reward_poisoning_traces.csv",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    bundle = quad.build_dynamics(args.seed)
    target_snapshot, viable_states = choose_target(
        bundle,
        seed=args.seed,
        deployment_steps=args.deployment_steps,
        minimum_delay=args.minimum_delay,
    )
    training_states = quad.spread_subset(viable_states, args.batches)
    common = dict(
        seed=args.seed,
        batches=args.batches,
        batch_steps=args.batch_steps,
        sigma=args.sigma,
        actor_lr=args.actor_lr,
        gamma=args.gamma,
        max_gradient_norm=args.max_gradient_norm,
        reward_poison_budget=args.reward_poison_budget,
        poison_temperature=args.poison_temperature,
        filter_grid_size=args.filter_grid_size,
        filter_z_radius=args.filter_z_radius,
        filter_theta_radius=args.filter_theta_radius,
        filter_guard_margin=args.filter_guard_margin,
        filter_backup_steps=args.filter_backup_steps,
    )
    clean_snapshot, clean_training, clean_traces = train_reinforce(
        "clean_reinforce_snapshot",
        bundle,
        target_snapshot,
        training_states,
        poisoned_rewards=False,
        freeze_updates=False,
        **common,
    )
    poisoned_snapshot, poison_training, poison_traces = train_reinforce(
        "poisoned_action_only_snapshot",
        bundle,
        target_snapshot,
        training_states,
        poisoned_rewards=True,
        freeze_updates=False,
        **common,
    )
    if "poisoned_always_freeze_snapshot" in args.mechanisms:
        _frozen_snapshot, freeze_training, freeze_traces = train_reinforce(
            "poisoned_always_freeze_snapshot",
            bundle,
            target_snapshot,
            training_states,
            poisoned_rewards=True,
            freeze_updates=True,
            **common,
        )
    else:
        freeze_training = replace(
            poison_training,
            mechanism="poisoned_always_freeze_snapshot",
            actor_updates=0,
            pending_w00=0.0,
            pending_w01=0.0,
            pending_w10=0.0,
            pending_w11=0.0,
            final_w00=0.0,
            final_w01=0.0,
            final_w10=0.0,
            final_w11=0.0,
        )
        freeze_traces = []

    certificate_candidates = quad.spread_subset(
        viable_states, args.certificate_states
    )
    admitted = quad.exact_certificate_admission(
        bundle,
        certificate_candidates,
        steps=args.deployment_steps,
        guard_margin=args.certificate_guard_margin,
    )
    committed_snapshot, commit_fraction = quad.commit_backtracked_snapshot(
        bundle,
        poisoned_snapshot,
        admitted,
        steps=args.deployment_steps,
        guard_margin=args.certificate_guard_margin,
    )
    committed_values = snapshot_fields(committed_snapshot)
    commit_training = replace(
        poison_training,
        mechanism="poisoned_commit_gate_snapshot",
        final_w00=committed_values[0],
        final_w01=committed_values[1],
        final_w10=committed_values[2],
        final_w11=committed_values[3],
        commit_fraction=commit_fraction,
        commit_projection_norm=float(
            np.linalg.norm(committed_snapshot - poisoned_snapshot)
        ),
        certificate_candidates=len(certificate_candidates),
        certificate_admitted=len(admitted),
    )
    filter_training = replace(
        poison_training,
        mechanism="poisoned_permanent_filter_snapshot",
    )

    training_by_mechanism = {
        "clean_reinforce_snapshot": clean_training,
        "poisoned_action_only_snapshot": poison_training,
        "poisoned_always_freeze_snapshot": freeze_training,
        "poisoned_commit_gate_snapshot": commit_training,
        "poisoned_permanent_filter_snapshot": filter_training,
    }
    snapshots = {
        "clean_reinforce_snapshot": clean_snapshot,
        "poisoned_action_only_snapshot": poisoned_snapshot,
        "poisoned_always_freeze_snapshot": np.zeros((2, 2), dtype=float),
        "poisoned_commit_gate_snapshot": committed_snapshot,
        "poisoned_permanent_filter_snapshot": poisoned_snapshot,
    }
    selected_snapshots = {name: snapshots[name] for name in args.mechanisms}
    deployment_states = quad.spread_subset(
        viable_states, args.deployment_rollouts
    )
    rollout_rows = quad.run_pybullet_deployments(
        bundle,
        selected_snapshots,
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
    summaries = [
        summarize(
            training_by_mechanism[name],
            [row for row in rollout_rows if row.mechanism == name],
            target_snapshot,
            minimum_delay=args.minimum_delay,
        )
        for name in args.mechanisms
    ]
    write_csv(args.summary_out, summaries)
    write_csv(args.rollouts_out, rollout_rows)
    write_csv(args.traces_out, clean_traces + poison_traces + freeze_traces)
    print(f"target_snapshot={target_snapshot.tolist()}")
    print(f"clean_snapshot={clean_snapshot.tolist()}")
    print(f"poisoned_snapshot={poisoned_snapshot.tolist()}")
    print(
        f"commit_fraction={commit_fraction:.2f} "
        f"committed_snapshot={committed_snapshot.tolist()} "
        f"certificate={len(admitted)}/{len(certificate_candidates)}"
    )
    print_summary(summaries)
    print(f"wrote {args.summary_out}")
    print(f"wrote {args.rollouts_out}")
    print(f"wrote {args.traces_out}")


if __name__ == "__main__":
    main()
