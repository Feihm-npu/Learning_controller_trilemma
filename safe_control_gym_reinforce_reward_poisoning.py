#!/usr/bin/env python3
"""Delayed-trigger reward poisoning against an online REINFORCE residual actor.

Unlike the synthetic update-direction benchmark, this experiment never lets
the attacker write parameters or gradients.  The learner samples actions from
a Gaussian residual policy, records real PyBullet rewards, computes standard
reward-to-go REINFORCE gradients, and updates its two actor parameters.  A
white-box attacker may only add a bounded value to each logged reward.

The adaptation-time robust action kernel protects every applied action.  The
learned mean-policy snapshot is then committed and deployed without that
filter, matching the snapshot-commit scope of the delayed-trigger benchmark.
"""

from __future__ import annotations

import argparse
import csv
from dataclasses import asdict, dataclass, replace
from functools import partial
from itertools import product
from pathlib import Path
from statistics import median
from typing import Callable, Iterable

import numpy as np

from safe_control_gym.utils.registration import make

import safe_control_gym_delayed_trigger_attack as delayed
import safe_control_gym_plausible_set_lifecycle_gate as gate


ROOT = Path(__file__).resolve().parent
RESULTS_DIR = ROOT / "results"
THETA_SCALE = 0.2
LEARNER_LOW = np.asarray([-3.6, -5.0], dtype=float)
LEARNER_HIGH = np.asarray([3.6, 5.0], dtype=float)
MECHANISMS = (
    "clean_reinforce_snapshot",
    "poisoned_action_only_snapshot",
    "poisoned_always_freeze_snapshot",
    "poisoned_commit_gate_snapshot",
)


@dataclass
class ReinforceTrainingResult:
    mechanism: str
    seed: int
    batches: int
    batch_steps: int
    adaptation_steps: int
    reward_poison_budget: float
    max_reward_poison: float
    attack_target_gain: float
    attack_target_bias: float
    actor_updates: int
    action_filter_interventions: int
    rejected_action_steps: int
    adaptation_constraint_violations: int
    mean_true_reward: float
    mean_logged_reward: float
    mean_gradient_norm: float
    pending_gain: float
    pending_bias: float
    final_gain: float
    final_bias: float
    commit_projection_norm: float
    committed_nontrivial_update: bool
    certificate_candidates: int
    certificate_admitted: int


@dataclass
class ReinforceSummary:
    mechanism: str
    seed: int
    batches: int
    batch_steps: int
    adaptation_steps: int
    reward_poison_budget: float
    max_reward_poison: float
    attack_target_gain: float
    attack_target_bias: float
    adaptation_constraint_violations: int
    actor_updates: int
    action_filter_interventions: int
    rejected_action_steps: int
    mean_true_reward: float
    mean_logged_reward: float
    mean_gradient_norm: float
    pending_gain: float
    pending_bias: float
    final_gain: float
    final_bias: float
    commit_projection_norm: float
    certificate_candidates: int
    certificate_admitted: int
    deployment_rollouts: int
    violating_rollouts: int
    deployment_violation_rate: float
    median_first_violation_step: float | None
    mean_deployment_reward: float


@dataclass
class BatchTrace:
    mechanism: str
    batch: int
    true_reward_mean: float
    logged_reward_mean: float
    max_reward_poison: float
    gradient_w0: float
    gradient_w1: float
    gradient_norm: float
    learner_w0: float
    learner_w1: float
    effective_gain: float
    effective_bias: float


def actor_features(observation: np.ndarray) -> np.ndarray:
    """Normalized features for a linear Gaussian residual actor."""
    observation = np.asarray(observation, dtype=float)
    return np.asarray([observation[2] / THETA_SCALE, 1.0], dtype=float)


def to_effective_params(learner_params: np.ndarray) -> np.ndarray:
    """Convert normalized actor weights to ``gain * theta + bias`` form."""
    learner_params = np.asarray(learner_params, dtype=float)
    return np.asarray(
        [learner_params[0] / THETA_SCALE, learner_params[1]],
        dtype=float,
    )


def to_learner_params(effective_params: np.ndarray) -> np.ndarray:
    effective_params = np.asarray(effective_params, dtype=float)
    return np.asarray(
        [effective_params[0] * THETA_SCALE, effective_params[1]],
        dtype=float,
    )


def reward_poison(
    exploration_noise: np.ndarray,
    features: np.ndarray,
    learner_params: np.ndarray,
    target_params: np.ndarray,
    *,
    budget: float,
    temperature: float,
) -> np.ndarray:
    """Bounded reward shaping that favors samples toward a target mean policy.

    This changes only the logged scalar rewards.  The policy-gradient score,
    sampled actions, transitions, and optimizer are computed by the learner.
    """
    current_means = features @ np.asarray(learner_params, dtype=float)
    target_means = features @ np.asarray(target_params, dtype=float)
    alignment = exploration_noise * (target_means - current_means)
    return budget * np.tanh(alignment / temperature)


def reward_to_go(
    rewards: np.ndarray,
    dones: np.ndarray,
    *,
    gamma: float,
) -> np.ndarray:
    returns = np.zeros_like(rewards, dtype=float)
    running = 0.0
    for index in range(len(rewards) - 1, -1, -1):
        running = float(rewards[index]) + gamma * running * (1.0 - dones[index])
        returns[index] = running
    return returns


def reinforce_gradient(
    features: np.ndarray,
    exploration_noise: np.ndarray,
    logged_rewards: np.ndarray,
    dones: np.ndarray,
    *,
    sigma: float,
    gamma: float,
) -> np.ndarray:
    """Standard Gaussian-mean REINFORCE gradient with reward-to-go."""
    returns = reward_to_go(logged_rewards, dones, gamma=gamma)
    advantages = returns - float(np.mean(returns))
    scale = float(np.std(advantages))
    if scale > 1e-8:
        advantages = advantages / scale
    scores = exploration_noise[:, None] * features / (sigma**2)
    return np.mean(advantages[:, None] * scores, axis=0)


def choose_attack_target(
    ctrl: object,
    info: dict,
    model: gate.CartpoleModel,
    *,
    action_low: float,
    action_high: float,
    deployment_steps: int,
) -> np.ndarray:
    """Choose the worst target policy, not an update, by deployment loss."""
    best: np.ndarray | None = None
    best_score: tuple[int, float, int] | None = None
    for gain, bias in product((-18.0, 0.0, 18.0), (-5.0, 0.0, 5.0)):
        effective = np.asarray([gain, bias], dtype=float)
        score = delayed.surrogate_deployment_score(
            ctrl,
            info,
            model,
            effective,
            action_low=action_low,
            action_high=action_high,
            deployment_steps=deployment_steps,
        )
        if best_score is None or score > best_score:
            best = effective
            best_score = score
    assert best is not None
    return to_learner_params(best)


def train_reinforce(
    mechanism: str,
    *,
    seed: int,
    poisoned_rewards: bool,
    freeze_updates: bool,
    batches: int,
    batch_steps: int,
    rho: float,
    sigma: float,
    actor_lr: float,
    gamma: float,
    max_gradient_norm: float,
    reward_poison_budget: float,
    poison_temperature: float,
    deployment_steps: int,
    action_grid_size: int,
    kernel_backend: str,
    reward_poisoner: Callable[..., np.ndarray] | None = None,
    target_effective_params: np.ndarray | None = None,
    batch_observer: Callable[..., None] | None = None,
) -> tuple[np.ndarray, ReinforceTrainingResult, list[BatchTrace]]:
    task_config, lqr_config, _cbf_config = gate.build_configs(seed)
    env_func = partial(make, "cartpole", **task_config)
    env = env_func(gui=False)
    ctrl = make("lqr", env_func, **lqr_config)
    ctrl.reset()
    observation, info = env.reset(seed=seed)
    ctrl.reset_before_run(observation, info, env=env)
    model = gate.make_model_from_env(env)
    casadi_fd_func = env.symbolic.fd_func
    action_grid = gate.action_grid_from_env(env, action_grid_size)
    action_low = float(np.asarray(env.action_space.low).reshape(-1)[0])
    action_high = float(np.asarray(env.action_space.high).reshape(-1)[0])
    if target_effective_params is None:
        target_params = choose_attack_target(
            ctrl,
            info,
            model,
            action_low=action_low,
            action_high=action_high,
            deployment_steps=deployment_steps,
        )
    else:
        target_params = to_learner_params(target_effective_params)

    rng = np.random.default_rng(seed + 9107)
    learner_params = np.zeros(2, dtype=float)
    traces: list[BatchTrace] = []
    true_rewards_all: list[float] = []
    logged_rewards_all: list[float] = []
    gradient_norms: list[float] = []
    maximum_poison = 0.0
    interventions = 0
    rejected_actions = 0
    constraint_violations = 0
    actor_updates = 0

    for batch in range(batches):
        feature_rows: list[np.ndarray] = []
        noise_rows: list[float] = []
        reward_rows: list[float] = []
        done_rows: list[float] = []
        for _step in range(batch_steps):
            attacked_observation = np.asarray(observation, dtype=float).copy()
            attacked_observation[2] -= rho
            kernel = gate.safe_kernel_for_observation(
                attacked_observation,
                rho,
                model,
                action_grid,
                guard_margin=0.0,
                kernel_backend=kernel_backend,
                casadi_fd_func=casadi_fd_func,
            )
            features = actor_features(attacked_observation)
            noise = float(rng.normal(0.0, sigma))
            base_action = gate.lqr_action(ctrl, attacked_observation, info)
            raw_action = base_action + float(features @ learner_params) + noise
            filtered_action, accepted, correction = gate.project_to_kernel(
                raw_action,
                kernel,
            )
            if accepted:
                applied_action = filtered_action
                interventions += int(correction > 1e-8)
            else:
                applied_action = raw_action
                rejected_actions += 1
            observation, reward, done, info = env.step(
                np.asarray([np.clip(applied_action, action_low, action_high)])
            )
            violation = bool(info.get("constraint_violation", False))
            constraint_violations += int(violation)
            feature_rows.append(features)
            noise_rows.append(noise)
            reward_rows.append(float(reward))
            done_rows.append(float(done))
            if done:
                observation, info = env.reset()
                ctrl.reset_before_run(observation, info, env=env)

        features_array = np.vstack(feature_rows)
        noise_array = np.asarray(noise_rows, dtype=float)
        true_rewards = np.asarray(reward_rows, dtype=float)
        dones = np.asarray(done_rows, dtype=float)
        poison = np.zeros_like(true_rewards)
        if poisoned_rewards:
            if reward_poisoner is None:
                poison = reward_poison(
                    noise_array,
                    features_array,
                    learner_params,
                    target_params,
                    budget=reward_poison_budget,
                    temperature=poison_temperature,
                )
            else:
                poison = np.asarray(
                    reward_poisoner(
                        batch=batch,
                        exploration_noise=noise_array,
                        features=features_array,
                        true_rewards=true_rewards,
                        dones=dones,
                        learner_params=learner_params.copy(),
                        target_params=target_params.copy(),
                        sigma=sigma,
                        gamma=gamma,
                        actor_lr=actor_lr,
                        max_gradient_norm=max_gradient_norm,
                        budget=reward_poison_budget,
                    ),
                    dtype=float,
                )
                if poison.shape != true_rewards.shape:
                    raise ValueError("reward_poisoner returned an invalid shape")
                if np.max(np.abs(poison)) > reward_poison_budget + 1e-8:
                    raise ValueError("reward_poisoner exceeded the reward budget")
        logged_rewards = true_rewards + poison
        learner_params_before = learner_params.copy()
        raw_gradient = reinforce_gradient(
            features_array,
            noise_array,
            logged_rewards,
            dones,
            sigma=sigma,
            gamma=gamma,
        )
        gradient = raw_gradient.copy()
        gradient_norm = float(np.linalg.norm(gradient))
        if gradient_norm > max_gradient_norm:
            gradient *= max_gradient_norm / gradient_norm
            gradient_norm = max_gradient_norm
        candidate = np.minimum(
            np.maximum(learner_params + actor_lr * gradient, LEARNER_LOW),
            LEARNER_HIGH,
        )
        if not freeze_updates:
            actor_updates += int(gate.params_changed(learner_params, candidate))
            learner_params = candidate

        if batch_observer is not None:
            batch_observer(
                batch=batch,
                features=features_array.copy(),
                exploration_noise=noise_array.copy(),
                true_rewards=true_rewards.copy(),
                logged_rewards=logged_rewards.copy(),
                reward_delta=poison.copy(),
                dones=dones.copy(),
                learner_params_before=learner_params_before,
                target_params=target_params.copy(),
                raw_gradient=raw_gradient.copy(),
                applied_gradient=gradient.copy(),
                candidate_params=candidate.copy(),
                learner_params_after=learner_params.copy(),
                effective_params_after=to_effective_params(learner_params),
            )

        effective = to_effective_params(learner_params)
        maximum_poison = max(maximum_poison, float(np.max(np.abs(poison))))
        true_rewards_all.extend(true_rewards.tolist())
        logged_rewards_all.extend(logged_rewards.tolist())
        gradient_norms.append(gradient_norm)
        traces.append(
            BatchTrace(
                mechanism=mechanism,
                batch=batch,
                true_reward_mean=float(np.mean(true_rewards)),
                logged_reward_mean=float(np.mean(logged_rewards)),
                max_reward_poison=float(np.max(np.abs(poison))),
                gradient_w0=float(gradient[0]),
                gradient_w1=float(gradient[1]),
                gradient_norm=gradient_norm,
                learner_w0=float(learner_params[0]),
                learner_w1=float(learner_params[1]),
                effective_gain=float(effective[0]),
                effective_bias=float(effective[1]),
            )
        )

    effective = to_effective_params(learner_params)
    ctrl.close()
    env.close()
    result = ReinforceTrainingResult(
        mechanism=mechanism,
        seed=seed,
        batches=batches,
        batch_steps=batch_steps,
        adaptation_steps=batches * batch_steps,
        reward_poison_budget=reward_poison_budget,
        max_reward_poison=maximum_poison,
        attack_target_gain=float(to_effective_params(target_params)[0]),
        attack_target_bias=float(to_effective_params(target_params)[1]),
        actor_updates=actor_updates,
        action_filter_interventions=interventions,
        rejected_action_steps=rejected_actions,
        adaptation_constraint_violations=constraint_violations,
        mean_true_reward=float(np.mean(true_rewards_all)),
        mean_logged_reward=float(np.mean(logged_rewards_all)),
        mean_gradient_norm=float(np.mean(gradient_norms)),
        pending_gain=float(effective[0]),
        pending_bias=float(effective[1]),
        final_gain=float(effective[0]),
        final_bias=float(effective[1]),
        commit_projection_norm=0.0,
        committed_nontrivial_update=gate.params_changed(np.zeros(2), effective),
        certificate_candidates=0,
        certificate_admitted=0,
    )
    return effective, result, traces


def commit_snapshot(
    pending_params: np.ndarray,
    *,
    seed: int,
    deployment_steps: int,
    admission_guard_margin: float,
    commit_guard_margin: float,
) -> tuple[np.ndarray, int, int]:
    task_config, lqr_config, _cbf_config = gate.build_configs(seed)
    env_func = partial(make, "cartpole", **task_config)
    env = env_func(gui=False)
    ctrl = make("lqr", env_func, **lqr_config)
    ctrl.reset()
    observation, info = env.reset(seed=seed)
    ctrl.reset_before_run(observation, info, env=env)
    action_low = float(np.asarray(env.action_space.low).reshape(-1)[0])
    action_high = float(np.asarray(env.action_space.high).reshape(-1)[0])
    casadi_fd_func = env.symbolic.fd_func
    candidates = delayed.certification_envelope()
    admitted = delayed.baseline_viable_states(
        ctrl,
        info,
        casadi_fd_func,
        candidates,
        baseline_params=np.zeros(2),
        action_low=action_low,
        action_high=action_high,
        deployment_steps=deployment_steps,
        guard_margin=admission_guard_margin,
    )
    committed = delayed.commit_backtracked_snapshot(
        np.zeros(2),
        pending_params,
        ctrl,
        info,
        casadi_fd_func,
        action_low=action_low,
        action_high=action_high,
        deployment_steps=deployment_steps,
        certificate_states=admitted,
        certificate_guard_margin=commit_guard_margin,
    )
    ctrl.close()
    env.close()
    return committed, len(candidates), len(admitted)


def summarize(
    training: ReinforceTrainingResult,
    deployments: list[delayed.DeploymentResult],
) -> ReinforceSummary:
    first_steps = [
        row.first_violation_step
        for row in deployments
        if row.first_violation_step is not None
    ]
    return ReinforceSummary(
        mechanism=training.mechanism,
        seed=training.seed,
        batches=training.batches,
        batch_steps=training.batch_steps,
        adaptation_steps=training.adaptation_steps,
        reward_poison_budget=training.reward_poison_budget,
        max_reward_poison=training.max_reward_poison,
        attack_target_gain=training.attack_target_gain,
        attack_target_bias=training.attack_target_bias,
        adaptation_constraint_violations=training.adaptation_constraint_violations,
        actor_updates=training.actor_updates,
        action_filter_interventions=training.action_filter_interventions,
        rejected_action_steps=training.rejected_action_steps,
        mean_true_reward=training.mean_true_reward,
        mean_logged_reward=training.mean_logged_reward,
        mean_gradient_norm=training.mean_gradient_norm,
        pending_gain=training.pending_gain,
        pending_bias=training.pending_bias,
        final_gain=training.final_gain,
        final_bias=training.final_bias,
        commit_projection_norm=training.commit_projection_norm,
        certificate_candidates=training.certificate_candidates,
        certificate_admitted=training.certificate_admitted,
        deployment_rollouts=len(deployments),
        violating_rollouts=len(first_steps),
        deployment_violation_rate=(
            len(first_steps) / len(deployments) if deployments else 0.0
        ),
        median_first_violation_step=(
            float(median(first_steps)) if first_steps else None
        ),
        mean_deployment_reward=float(
            np.mean([row.mean_reward for row in deployments])
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


def print_summary(rows: list[ReinforceSummary]) -> None:
    print(
        "| mechanism | train violations | updates | pending -> committed | "
        "deployment violations | median first | reward |"
    )
    print("|---|---:|---:|---|---:|---:|---:|")
    for row in rows:
        first = (
            "--"
            if row.median_first_violation_step is None
            else f"{row.median_first_violation_step:.1f}"
        )
        print(
            f"| {row.mechanism} | {row.adaptation_constraint_violations} | "
            f"{row.actor_updates} | ({row.pending_gain:.3f},{row.pending_bias:.3f}) "
            f"-> ({row.final_gain:.3f},{row.final_bias:.3f}) | "
            f"{row.violating_rollouts}/{row.deployment_rollouts} | {first} | "
            f"{row.mean_deployment_reward:.3f} |"
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, default=2040)
    parser.add_argument("--batches", type=int, default=12)
    parser.add_argument("--batch-steps", type=int, default=8)
    parser.add_argument("--rho", type=float, default=0.005)
    parser.add_argument("--sigma", type=float, default=0.8)
    parser.add_argument("--actor-lr", type=float, default=1.0)
    parser.add_argument("--gamma", type=float, default=0.97)
    parser.add_argument("--max-gradient-norm", type=float, default=1.0)
    parser.add_argument("--reward-poison-budget", type=float, default=2.0)
    parser.add_argument("--poison-temperature", type=float, default=1.0)
    parser.add_argument("--deployment-steps", type=int, default=120)
    parser.add_argument("--action-grid-size", type=int, default=41)
    parser.add_argument(
        "--kernel-backend", choices=("euler", "casadi"), default="casadi"
    )
    parser.add_argument("--admission-guard-margin", type=float, default=0.0075)
    parser.add_argument("--commit-guard-margin", type=float, default=0.005)
    parser.add_argument(
        "--summary-out",
        type=Path,
        default=RESULTS_DIR / "safe_control_gym_reinforce_reward_poisoning.csv",
    )
    parser.add_argument(
        "--rollouts-out",
        type=Path,
        default=RESULTS_DIR / "safe_control_gym_reinforce_reward_poisoning_rollouts.csv",
    )
    parser.add_argument(
        "--traces-out",
        type=Path,
        default=RESULTS_DIR / "safe_control_gym_reinforce_reward_poisoning_traces.csv",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    clean_params, clean_training, clean_traces = train_reinforce(
        "clean_reinforce_snapshot",
        seed=args.seed,
        poisoned_rewards=False,
        freeze_updates=False,
        batches=args.batches,
        batch_steps=args.batch_steps,
        rho=args.rho,
        sigma=args.sigma,
        actor_lr=args.actor_lr,
        gamma=args.gamma,
        max_gradient_norm=args.max_gradient_norm,
        reward_poison_budget=args.reward_poison_budget,
        poison_temperature=args.poison_temperature,
        deployment_steps=args.deployment_steps,
        action_grid_size=args.action_grid_size,
        kernel_backend=args.kernel_backend,
    )
    poison_params, poison_training, poison_traces = train_reinforce(
        "poisoned_action_only_snapshot",
        seed=args.seed,
        poisoned_rewards=True,
        freeze_updates=False,
        batches=args.batches,
        batch_steps=args.batch_steps,
        rho=args.rho,
        sigma=args.sigma,
        actor_lr=args.actor_lr,
        gamma=args.gamma,
        max_gradient_norm=args.max_gradient_norm,
        reward_poison_budget=args.reward_poison_budget,
        poison_temperature=args.poison_temperature,
        deployment_steps=args.deployment_steps,
        action_grid_size=args.action_grid_size,
        kernel_backend=args.kernel_backend,
    )
    _freeze_params, freeze_training, freeze_traces = train_reinforce(
        "poisoned_always_freeze_snapshot",
        seed=args.seed,
        poisoned_rewards=True,
        freeze_updates=True,
        batches=args.batches,
        batch_steps=args.batch_steps,
        rho=args.rho,
        sigma=args.sigma,
        actor_lr=args.actor_lr,
        gamma=args.gamma,
        max_gradient_norm=args.max_gradient_norm,
        reward_poison_budget=args.reward_poison_budget,
        poison_temperature=args.poison_temperature,
        deployment_steps=args.deployment_steps,
        action_grid_size=args.action_grid_size,
        kernel_backend=args.kernel_backend,
    )

    committed, certificate_candidates, certificate_admitted = commit_snapshot(
        poison_params,
        seed=args.seed,
        deployment_steps=args.deployment_steps,
        admission_guard_margin=args.admission_guard_margin,
        commit_guard_margin=args.commit_guard_margin,
    )
    commit_training = replace(
        poison_training,
        mechanism="poisoned_commit_gate_snapshot",
        final_gain=float(committed[0]),
        final_bias=float(committed[1]),
        commit_projection_norm=float(np.linalg.norm(committed - poison_params)),
        committed_nontrivial_update=gate.params_changed(np.zeros(2), committed),
        certificate_candidates=certificate_candidates,
        certificate_admitted=certificate_admitted,
    )
    training_rows = [
        clean_training,
        poison_training,
        freeze_training,
        commit_training,
    ]
    snapshots = {
        "clean_reinforce_snapshot": clean_params,
        "poisoned_action_only_snapshot": poison_params,
        "poisoned_always_freeze_snapshot": np.zeros(2),
        "poisoned_commit_gate_snapshot": committed,
    }
    summaries: list[ReinforceSummary] = []
    rollouts: list[delayed.DeploymentResult] = []
    for training in training_rows:
        mechanism_rollouts = [
            delayed.deploy_raw_snapshot(
                training.mechanism,
                snapshots[training.mechanism],
                initial_state,
                seed=args.seed,
                deployment_steps=args.deployment_steps,
            )
            for initial_state in delayed.deployment_envelope()
        ]
        rollouts.extend(mechanism_rollouts)
        summaries.append(summarize(training, mechanism_rollouts))

    write_csv(args.summary_out, summaries)
    write_csv(args.rollouts_out, rollouts)
    write_csv(args.traces_out, clean_traces + poison_traces + freeze_traces)
    print_summary(summaries)
    print(f"wrote {args.summary_out}")
    print(f"wrote {args.rollouts_out}")
    print(f"wrote {args.traces_out}")


if __name__ == "__main__":
    main()
