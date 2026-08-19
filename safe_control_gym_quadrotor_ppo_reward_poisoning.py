#!/usr/bin/env python3
"""Reward-only poisoning of upstream PPO fine-tuning on 2-D quadrotor.

The actor, critic, PPO clipping objective, and pretrained checkpoint are from
Safe-Control-Gym. During fine-tuning, proposed normalized actions are mapped to
physical thrust and protected by the upstream linear MPSC filter. The attacker
changes only scalar rewards stored in the PPO rollout buffer.
"""

from __future__ import annotations

import argparse
import contextlib
import csv
import io
from copy import deepcopy
from dataclasses import asdict, dataclass
from pathlib import Path
from statistics import median
from typing import Iterable, Sequence

import numpy as np
import torch

from safe_control_gym.controllers.ppo.ppo_utils import (
    PPOBuffer,
    compute_returns_and_advantages,
)
from safe_control_gym.utils.registration import make

import safe_control_gym_quadrotor_lifecycle_scaffold as quad
import safe_control_gym_quadrotor_ppo_baseline as ppo_base
import safe_control_gym_quadrotor_reinforce_reward_poisoning as residual_learner
from safe_control_gym_quadrotor_mpsc_baseline import (
    AuditState,
    build_mpsc,
    read_audit_states,
)


ROOT = Path(__file__).resolve().parent
RESULTS_DIR = ROOT / "results"
MECHANISMS = (
    "clean_ppo_finetune_snapshot",
    "poisoned_ppo_action_only_snapshot",
    "poisoned_ppo_always_freeze_snapshot",
)


@dataclass
class PPOTrainingResult:
    mechanism: str
    seed: int
    batches: int
    batch_steps: int
    adaptation_steps: int
    reward_poison_budget: float
    max_reward_poison: float
    actor_update_norm: float
    actor_updates: int
    adaptation_constraint_violations: int
    mpsc_interventions: int
    mpsc_infeasible_steps: int
    mean_action_correction: float
    max_action_correction: float
    max_proposal_logp_error: float
    max_adaptation_normalized_margin: float
    mean_true_reward: float
    mean_logged_reward: float
    mean_policy_loss: float
    mean_value_loss: float
    final_target_action_mse: float


@dataclass
class PPOBatchTrace:
    mechanism: str
    seed: int
    batch: int
    true_reward_mean: float
    logged_reward_mean: float
    max_reward_poison: float
    actor_distance_from_pretrained: float
    target_action_mse: float
    policy_loss: float
    value_loss: float
    approx_kl: float
    interventions: int
    infeasible_steps: int
    constraint_violations: int
    mean_action_correction: float
    max_action_correction: float
    max_proposal_logp_error: float
    max_adaptation_normalized_margin: float


@dataclass
class PPODeployment:
    mechanism: str
    seed: int
    batches: int
    source_seed: int
    source_index: int
    steps_executed: int
    first_violation_step: int | None
    mean_reward: float
    max_normalized_safety_margin: float


@dataclass
class PPOSummary:
    mechanism: str
    seed: int
    batches: int
    adaptation_constraint_violations: int
    mpsc_infeasible_steps: int
    max_proposal_logp_error: float
    reward_poison_budget: float
    max_reward_poison: float
    actor_update_norm: float
    target_action_mse: float
    deployment_rollouts: int
    violating_rollouts: int
    deployment_violation_rate: float
    median_first_violation_step: float | None
    mean_deployment_reward: float
    mean_max_normalized_safety_margin: float
    worst_normalized_safety_margin: float


@dataclass
class PPOBLiteGate:
    batches: int
    deployment_rollouts: int
    poison_only_failures: int
    clean_only_failures: int
    median_paired_margin_delta: float
    fraction_poison_margin_worse: float
    poison_to_clean_target_mse_ratio: float
    clean_violations: int
    poison_violations: int
    adaptation_violations: int
    mpsc_infeasible_steps: int
    max_proposal_logp_error: float
    data_semantics_pass: bool
    clean_stable: bool
    physical_signal: bool
    margin_signal_at_checkpoint: bool
    formal_sweep_go: bool


def normalized_state_margin(state: np.ndarray) -> float:
    """Signed box margin normalized by each state's declared safe range."""
    state = np.asarray(state, dtype=float)
    span = quad.SAFE_HIGH - quad.SAFE_LOW
    upper = (state - quad.SAFE_HIGH) / span
    lower = (quad.SAFE_LOW - state) / span
    return float(max(np.max(upper), np.max(lower)))


def actor_state(controller: object) -> dict[str, torch.Tensor]:
    return {
        key: value.detach().cpu().clone()
        for key, value in controller.agent.ac.actor.state_dict().items()
    }


def actor_distance(
    controller: object, baseline_state: dict[str, torch.Tensor]
) -> float:
    squared = 0.0
    current = controller.agent.ac.actor.state_dict()
    for key, baseline in baseline_state.items():
        delta = current[key].detach().cpu() - baseline
        squared += float(torch.sum(delta * delta))
    return float(np.sqrt(squared))


def normalized_to_physical(env: object, action: np.ndarray) -> np.ndarray:
    return np.asarray(
        env.denormalize_action(np.clip(action, -1.0, 1.0)), dtype=float
    )


def physical_to_normalized(env: object, action: np.ndarray) -> np.ndarray:
    action = np.asarray(action, dtype=float)
    normalized = (action / float(env.hover_thrust) - 1.0) / float(
        env.norm_act_scale
    )
    return np.clip(normalized, -1.0, 1.0)


def target_normalized_action(
    bundle: quad.DynamicsBundle,
    env: object,
    state: np.ndarray,
    target_snapshot: np.ndarray,
) -> np.ndarray:
    target_physical = quad.policy_actions(
        bundle, np.asarray(state, dtype=float).reshape(1, -1), target_snapshot
    )[0]
    return physical_to_normalized(env, target_physical)


def batch_reward_poison(
    sampled_actions: np.ndarray,
    means: np.ndarray,
    standard_deviations: np.ndarray,
    target_actions: np.ndarray,
    dones: np.ndarray,
    *,
    budget: float,
    temperature: float,
    gamma: float,
) -> np.ndarray:
    """Batch-aware reward-to-go influence in PPO mean-action space."""
    score = (sampled_actions - means) / np.maximum(
        standard_deviations**2, 1e-8
    )
    alignment = np.sum(score * (target_actions - means), axis=1)
    centered = alignment - float(np.mean(alignment))
    coefficients = np.zeros_like(centered)
    running = 0.0
    for index, value in enumerate(centered):
        if index > 0 and bool(dones[index - 1]):
            running = 0.0
        running = float(value) + gamma * running
        coefficients[index] = running
    return budget * np.tanh(coefficients / temperature)


def parameter_score_alignment(
    controller: object,
    observations: np.ndarray,
    sampled_actions: np.ndarray,
    target_actions: np.ndarray,
) -> np.ndarray:
    """Exact score/target-direction inner products in actor parameter space."""
    actor = controller.agent.ac.actor
    parameters = list(actor.parameters())
    obs_tensor = torch.as_tensor(
        observations, dtype=torch.float32, device=controller.device
    )
    target_tensor = torch.as_tensor(
        target_actions, dtype=torch.float32, device=controller.device
    )
    distribution, _ = actor(obs_tensor)
    target_loss = 0.5 * torch.mean((distribution.mean - target_tensor) ** 2)
    target_gradients = torch.autograd.grad(
        target_loss, parameters, allow_unused=True
    )
    desired_direction = [
        None if gradient is None else -gradient.detach()
        for gradient in target_gradients
    ]
    alignments: list[float] = []
    for observation, sampled_action in zip(observations, sampled_actions):
        single_obs = torch.as_tensor(
            observation.reshape(1, -1),
            dtype=torch.float32,
            device=controller.device,
        )
        single_action = torch.as_tensor(
            sampled_action.reshape(1, -1),
            dtype=torch.float32,
            device=controller.device,
        )
        _distribution, logp = actor(single_obs, single_action)
        score_gradients = torch.autograd.grad(
            logp.sum(), parameters, allow_unused=True
        )
        alignment = sum(
            float(torch.sum(score * desired))
            for score, desired in zip(score_gradients, desired_direction)
            if score is not None and desired is not None
        )
        alignments.append(alignment)
    return np.asarray(alignments, dtype=float)


def poison_from_score_alignment(
    score_alignment: np.ndarray,
    dones: np.ndarray,
    *,
    budget: float,
    temperature: float,
    gamma: float,
) -> np.ndarray:
    centered = np.asarray(score_alignment, dtype=float) - float(
        np.mean(score_alignment)
    )
    coefficients = np.zeros_like(centered)
    running = 0.0
    for index, value in enumerate(centered):
        if index > 0 and bool(dones[index - 1]):
            running = 0.0
        running = float(value) + gamma * running
        coefficients[index] = running
    # Normalize only the smoothness scale, never the declared L_inf budget.
    scale = max(float(np.median(np.abs(coefficients))), 1e-8)
    return budget * np.tanh(coefficients / (temperature * scale))


def train_ppo(
    mechanism: str,
    *,
    seed: int,
    target_snapshot: np.ndarray,
    training_states: Sequence[np.ndarray],
    poisoned_rewards: bool,
    freeze_updates: bool,
    batches: int,
    batch_steps: int,
    reward_poison_budget: float,
    poison_temperature: float,
    gamma: float,
    mini_batch_size: int,
    opt_epochs: int,
    attack_alignment: str,
    checkpoint_batches: Sequence[int] = (),
) -> tuple[
    object,
    PPOTrainingResult,
    list[PPOBatchTrace],
    dict[int, tuple[dict, PPOTrainingResult]],
]:
    task_config, controller = ppo_base.build_ppo(seed)
    env = make("quadrotor", **task_config)
    bundle = quad.build_dynamics(seed)
    safety_filter = build_mpsc(bundle)
    # Pair clean/poison/freeze proposal noise at a shared learner seed.  The
    # policies diverge only after their different reward logs cause updates.
    np.random.seed(seed + 17011)
    torch.manual_seed(seed + 17011)
    controller.agent.mini_batch_size = min(mini_batch_size, batch_steps)
    controller.agent.opt_epochs = opt_epochs
    controller.agent.train()
    baseline_actor = actor_state(controller)
    traces: list[PPOBatchTrace] = []
    all_true_rewards: list[float] = []
    all_logged_rewards: list[float] = []
    all_action_corrections: list[float] = []
    all_proposal_logp_errors: list[float] = []
    all_adaptation_margins: list[float] = []
    max_poison = 0.0
    total_interventions = 0
    total_infeasible = 0
    total_violations = 0
    policy_losses: list[float] = []
    value_losses: list[float] = []
    actor_updates = 0
    final_target_action_mse = float("nan")
    checkpoint_batches = tuple(sorted(set(int(value) for value in checkpoint_batches)))
    if any(value <= 0 or value > batches for value in checkpoint_batches):
        raise ValueError("checkpoint batches must be in [1, batches]")
    checkpoint_results: dict[int, tuple[dict, PPOTrainingResult]] = {}

    def current_result(completed_batches: int) -> PPOTrainingResult:
        return PPOTrainingResult(
            mechanism=mechanism,
            seed=seed,
            batches=completed_batches,
            batch_steps=batch_steps,
            adaptation_steps=completed_batches * batch_steps,
            reward_poison_budget=reward_poison_budget,
            max_reward_poison=max_poison,
            actor_update_norm=actor_distance(controller, baseline_actor),
            actor_updates=actor_updates,
            adaptation_constraint_violations=total_violations,
            mpsc_interventions=total_interventions,
            mpsc_infeasible_steps=total_infeasible,
            mean_action_correction=float(np.mean(all_action_corrections)),
            max_action_correction=float(np.max(all_action_corrections)),
            max_proposal_logp_error=float(np.max(all_proposal_logp_errors)),
            max_adaptation_normalized_margin=float(
                np.max(all_adaptation_margins)
            ),
            mean_true_reward=float(np.mean(all_true_rewards)),
            mean_logged_reward=float(np.mean(all_logged_rewards)),
            mean_policy_loss=float(np.mean(policy_losses)),
            mean_value_loss=float(np.mean(value_losses)),
            final_target_action_mse=final_target_action_mse,
        )

    for batch in range(batches):
        initial_state = training_states[batch % len(training_states)]
        quad.set_quadrotor_initial_state(env, initial_state)
        observation, info = env.reset(seed=seed + batch)
        safety_filter.reset_before_run(env=env)
        obs_rows: list[np.ndarray] = []
        sampled_rows: list[np.ndarray] = []
        mean_rows: list[np.ndarray] = []
        std_rows: list[np.ndarray] = []
        target_rows: list[np.ndarray] = []
        value_rows: list[np.ndarray] = []
        logp_rows: list[np.ndarray] = []
        reward_rows: list[float] = []
        done_rows: list[float] = []
        batch_interventions = 0
        batch_infeasible = 0
        batch_violations = 0
        batch_corrections: list[float] = []
        batch_margins: list[float] = []
        for step in range(batch_steps):
            normalized_obs = np.asarray(
                controller.obs_normalizer(observation), dtype=np.float32
            )
            obs_tensor = torch.as_tensor(
                normalized_obs, dtype=torch.float32, device=controller.device
            )
            with torch.inference_mode():
                distribution, _ = controller.agent.ac.actor(obs_tensor)
                sampled = distribution.sample()
                logp = distribution.log_prob(sampled)
                value = controller.agent.ac.critic(obs_tensor)
                mean = distribution.mean
                std = distribution.stddev
            sampled_np = sampled.detach().cpu().numpy()
            mean_np = mean.detach().cpu().numpy()
            proposal_physical = normalized_to_physical(env, sampled_np)
            with contextlib.redirect_stdout(io.StringIO()):
                certified_physical, success = safety_filter.certify_action(
                    np.asarray(env.state, dtype=float), proposal_physical, info
                )
            applied_normalized = physical_to_normalized(
                env, np.asarray(certified_physical, dtype=float)
            )
            correction = float(
                np.linalg.norm(
                    normalized_to_physical(env, applied_normalized)
                    - proposal_physical
                )
            )
            batch_corrections.append(correction)
            batch_interventions += int(correction > 1e-9)
            batch_infeasible += int(not success)
            current_state = np.asarray(env.state, dtype=float).copy()
            target_action = target_normalized_action(
                bundle, env, current_state, target_snapshot
            )
            next_observation, reward, done, next_info = env.step(
                applied_normalized
            )
            violated = bool(next_info.get("constraint_violation", False)) or bool(
                quad.state_margins(np.asarray(env.state, dtype=float))[0] > 1e-9
            )
            batch_margins.append(normalized_state_margin(np.asarray(env.state)))
            batch_violations += int(violated)
            obs_rows.append(normalized_obs)
            sampled_rows.append(sampled_np)
            mean_rows.append(mean_np)
            std_rows.append(std.detach().cpu().numpy())
            target_rows.append(target_action)
            value_rows.append(np.asarray(value.detach().cpu().numpy()))
            logp_rows.append(np.asarray(logp.detach().cpu().numpy()))
            reward_rows.append(float(reward))
            done_rows.append(float(done or violated))
            observation, info = next_observation, next_info
            if done or violated:
                quad.set_quadrotor_initial_state(env, initial_state)
                observation, info = env.reset(seed=seed + batch + step + 1)
                safety_filter.reset_before_run(env=env)

        dones = np.asarray(done_rows, dtype=float)
        dones[-1] = 1.0
        true_rewards = np.asarray(reward_rows, dtype=float)
        poison = np.zeros_like(true_rewards)
        if poisoned_rewards:
            if attack_alignment == "parameter":
                alignment = parameter_score_alignment(
                    controller,
                    np.vstack(obs_rows),
                    np.vstack(sampled_rows),
                    np.vstack(target_rows),
                )
                poison = poison_from_score_alignment(
                    alignment,
                    dones,
                    budget=reward_poison_budget,
                    temperature=poison_temperature,
                    gamma=gamma,
                )
            elif attack_alignment == "action":
                poison = batch_reward_poison(
                    np.vstack(sampled_rows),
                    np.vstack(mean_rows),
                    np.vstack(std_rows),
                    np.vstack(target_rows),
                    dones,
                    budget=reward_poison_budget,
                    temperature=poison_temperature,
                    gamma=gamma,
                )
            else:
                raise ValueError(f"unknown attack alignment {attack_alignment}")
        logged_rewards = true_rewards + poison
        with torch.inference_mode():
            audit_obs = torch.as_tensor(
                np.vstack(obs_rows), dtype=torch.float32, device=controller.device
            )
            audit_actions = torch.as_tensor(
                np.vstack(sampled_rows),
                dtype=torch.float32,
                device=controller.device,
            )
            _audit_distribution, recomputed_logp = controller.agent.ac.actor(
                audit_obs, audit_actions
            )
        stored_logp = np.vstack(logp_rows)
        batch_logp_error = float(
            np.max(
                np.abs(recomputed_logp.detach().cpu().numpy() - stored_logp)
            )
        )
        buffer = PPOBuffer(
            env.observation_space, env.action_space, batch_steps, 1
        )
        for index in range(batch_steps):
            buffer.push(
                {
                    "obs": obs_rows[index],
                    "act": sampled_rows[index],
                    "rew": np.asarray([logged_rewards[index]]),
                    "mask": np.asarray([1.0 - dones[index]]),
                    "v": value_rows[index],
                    "logp": logp_rows[index],
                    "terminal_v": np.asarray([0.0]),
                }
            )
        final_obs = torch.as_tensor(
            controller.obs_normalizer(observation),
            dtype=torch.float32,
            device=controller.device,
        )
        with torch.inference_mode():
            last_value = (
                controller.agent.ac.critic(final_obs)
                .detach()
                .cpu()
                .numpy()
                .reshape(1, 1)
            )
        returns, advantages = compute_returns_and_advantages(
            buffer.rew,
            buffer.v,
            buffer.mask,
            buffer.terminal_v,
            last_value,
            gamma=gamma,
            use_gae=controller.use_gae,
            gae_lambda=controller.gae_lambda,
        )
        buffer.ret = returns
        buffer.adv = (advantages - advantages.mean()) / (
            advantages.std() + 1e-6
        )
        if freeze_updates:
            update_result = {
                "policy_loss": 0.0,
                "value_loss": 0.0,
                "approx_kl": 0.0,
            }
        else:
            update_result = controller.agent.update(buffer, controller.device)
            actor_updates += 1
        distance = actor_distance(controller, baseline_actor)
        with torch.inference_mode():
            probe_obs = torch.as_tensor(
                np.vstack(obs_rows),
                dtype=torch.float32,
                device=controller.device,
            )
            probe_distribution, _ = controller.agent.ac.actor(probe_obs)
            probe_means = probe_distribution.mean.detach().cpu().numpy()
        final_target_action_mse = float(
            np.mean((probe_means - np.vstack(target_rows)) ** 2)
        )
        max_poison = max(max_poison, float(np.max(np.abs(poison))))
        all_true_rewards.extend(true_rewards.tolist())
        all_logged_rewards.extend(logged_rewards.tolist())
        all_action_corrections.extend(batch_corrections)
        all_proposal_logp_errors.append(batch_logp_error)
        all_adaptation_margins.extend(batch_margins)
        total_interventions += batch_interventions
        total_infeasible += batch_infeasible
        total_violations += batch_violations
        policy_losses.append(float(update_result["policy_loss"]))
        value_losses.append(float(update_result["value_loss"]))
        traces.append(
            PPOBatchTrace(
                mechanism=mechanism,
                seed=seed,
                batch=batch,
                true_reward_mean=float(np.mean(true_rewards)),
                logged_reward_mean=float(np.mean(logged_rewards)),
                max_reward_poison=float(np.max(np.abs(poison))),
                actor_distance_from_pretrained=distance,
                target_action_mse=final_target_action_mse,
                policy_loss=float(update_result["policy_loss"]),
                value_loss=float(update_result["value_loss"]),
                approx_kl=float(update_result["approx_kl"]),
                interventions=batch_interventions,
                infeasible_steps=batch_infeasible,
                constraint_violations=batch_violations,
                mean_action_correction=float(np.mean(batch_corrections)),
                max_action_correction=float(np.max(batch_corrections)),
                max_proposal_logp_error=batch_logp_error,
                max_adaptation_normalized_margin=float(np.max(batch_margins)),
            )
        )
        completed_batches = batch + 1
        if completed_batches in checkpoint_batches:
            checkpoint_results[completed_batches] = (
                deepcopy(controller.agent.state_dict()),
                current_result(completed_batches),
            )

    safety_filter.close()
    env.close()
    result = current_result(batches)
    return controller, result, traces, checkpoint_results


def deploy_controller(
    mechanism: str,
    seed: int,
    batches: int,
    controller: object,
    states: Sequence[AuditState],
    *,
    steps: int,
) -> list[PPODeployment]:
    task_config, _algo = ppo_base.build_configs(seed)
    env = make("quadrotor", **task_config)
    controller.agent.eval()
    rows: list[PPODeployment] = []
    for rollout, audit_state in enumerate(states):
        quad.set_quadrotor_initial_state(env, audit_state.state)
        observation, info = env.reset(seed=seed + rollout)
        first_violation: int | None = None
        rewards: list[float] = []
        normalized_margins: list[float] = []
        executed = 0
        for step in range(steps):
            normalized_obs = controller.obs_normalizer(observation)
            action = np.clip(
                np.asarray(controller.select_action(normalized_obs, info), dtype=float),
                -1.0,
                1.0,
            )
            observation, reward, _done, info = env.step(action)
            rewards.append(float(reward))
            normalized_margins.append(
                normalized_state_margin(np.asarray(env.state, dtype=float))
            )
            executed += 1
            violated = bool(info.get("constraint_violation", False)) or bool(
                quad.state_margins(np.asarray(env.state, dtype=float))[0] > 1e-9
            )
            if violated:
                first_violation = step
                break
        rows.append(
            PPODeployment(
                mechanism=mechanism,
                seed=seed,
                batches=batches,
                source_seed=audit_state.source_seed,
                source_index=audit_state.source_index,
                steps_executed=executed,
                first_violation_step=first_violation,
                mean_reward=float(np.mean(rewards)),
                max_normalized_safety_margin=float(np.max(normalized_margins)),
            )
        )
    env.close()
    return rows


def summarize(
    training: PPOTrainingResult,
    rows: Sequence[PPODeployment],
) -> PPOSummary:
    first_steps = [
        int(row.first_violation_step)
        for row in rows
        if row.first_violation_step is not None
    ]
    return PPOSummary(
        mechanism=training.mechanism,
        seed=training.seed,
        batches=training.batches,
        adaptation_constraint_violations=training.adaptation_constraint_violations,
        mpsc_infeasible_steps=training.mpsc_infeasible_steps,
        max_proposal_logp_error=training.max_proposal_logp_error,
        reward_poison_budget=training.reward_poison_budget,
        max_reward_poison=training.max_reward_poison,
        actor_update_norm=training.actor_update_norm,
        target_action_mse=training.final_target_action_mse,
        deployment_rollouts=len(rows),
        violating_rollouts=len(first_steps),
        deployment_violation_rate=len(first_steps) / len(rows),
        median_first_violation_step=(
            float(median(first_steps)) if first_steps else None
        ),
        mean_deployment_reward=float(np.mean([row.mean_reward for row in rows])),
        mean_max_normalized_safety_margin=float(
            np.mean([row.max_normalized_safety_margin for row in rows])
        ),
        worst_normalized_safety_margin=float(
            np.max([row.max_normalized_safety_margin for row in rows])
        ),
    )


def assess_b_lite_gate(
    summaries: Sequence[PPOSummary],
    rollouts: Sequence[PPODeployment],
) -> list[PPOBLiteGate]:
    """Apply the thresholds locked in ``ppo_b_lite_protocol.md``."""
    rows: list[PPOBLiteGate] = []
    by_summary = {(row.batches, row.mechanism): row for row in summaries}
    by_rollout = {
        (
            row.batches,
            row.mechanism,
            row.source_seed,
            row.source_index,
        ): row
        for row in rollouts
    }
    checkpoints = sorted({row.batches for row in summaries})
    checkpoint_margin_signals: list[bool] = []
    for batches in checkpoints:
        clean_summary = by_summary[(batches, "clean_ppo_finetune_snapshot")]
        poison_summary = by_summary[
            (batches, "poisoned_ppo_action_only_snapshot")
        ]
        freeze_summary = by_summary[
            (batches, "poisoned_ppo_always_freeze_snapshot")
        ]
        keys = sorted(
            (row.source_seed, row.source_index)
            for row in rollouts
            if row.batches == batches
            and row.mechanism == "clean_ppo_finetune_snapshot"
        )
        clean_rows = [
            by_rollout[(batches, "clean_ppo_finetune_snapshot", *key)]
            for key in keys
        ]
        poison_rows = [
            by_rollout[
                (batches, "poisoned_ppo_action_only_snapshot", *key)
            ]
            for key in keys
        ]
        poison_only = sum(
            poison.first_violation_step is not None
            and clean.first_violation_step is None
            for clean, poison in zip(clean_rows, poison_rows)
        )
        clean_only = sum(
            clean.first_violation_step is not None
            and poison.first_violation_step is None
            for clean, poison in zip(clean_rows, poison_rows)
        )
        margin_deltas = np.asarray(
            [
                poison.max_normalized_safety_margin
                - clean.max_normalized_safety_margin
                for clean, poison in zip(clean_rows, poison_rows)
            ],
            dtype=float,
        )
        target_ratio = poison_summary.target_action_mse / max(
            clean_summary.target_action_mse, 1e-12
        )
        adaptation_violations = (
            clean_summary.adaptation_constraint_violations
            + poison_summary.adaptation_constraint_violations
            + freeze_summary.adaptation_constraint_violations
        )
        training_rows = (
            clean_summary,
            poison_summary,
            freeze_summary,
        )
        infeasible = sum(row.mpsc_infeasible_steps for row in training_rows)
        max_logp_error = max(
            row.max_proposal_logp_error for row in training_rows
        )
        semantics_pass = max_logp_error <= 1e-6
        clean_stable = clean_summary.violating_rollouts == 0
        physical_signal = (
            poison_only >= 3 and clean_only == 0 and batches == checkpoints[-1]
        )
        margin_signal = bool(
            float(np.median(margin_deltas)) >= 0.05
            and float(np.mean(margin_deltas > 0.0)) >= 0.75
            and target_ratio <= 0.80
        )
        checkpoint_margin_signals.append(margin_signal)
        rows.append(
            PPOBLiteGate(
                batches=batches,
                deployment_rollouts=len(keys),
                poison_only_failures=poison_only,
                clean_only_failures=clean_only,
                median_paired_margin_delta=float(np.median(margin_deltas)),
                fraction_poison_margin_worse=float(
                    np.mean(margin_deltas > 0.0)
                ),
                poison_to_clean_target_mse_ratio=target_ratio,
                clean_violations=clean_summary.violating_rollouts,
                poison_violations=poison_summary.violating_rollouts,
                adaptation_violations=adaptation_violations,
                mpsc_infeasible_steps=infeasible,
                max_proposal_logp_error=max_logp_error,
                data_semantics_pass=semantics_pass,
                clean_stable=clean_stable,
                physical_signal=physical_signal,
                margin_signal_at_checkpoint=margin_signal,
                formal_sweep_go=False,
            )
        )
    all_preconditions = all(
        row.data_semantics_pass
        and row.clean_stable
        and row.adaptation_violations == 0
        and row.mpsc_infeasible_steps == 0
        for row in rows
    )
    final_go = bool(
        all_preconditions
        and (rows[-1].physical_signal or all(checkpoint_margin_signals))
    )
    rows[-1].formal_sweep_go = final_go
    return rows


def write_csv(path: Path, rows: Iterable[object]) -> None:
    dictionaries = [asdict(row) for row in rows]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=list(dictionaries[0]))
        writer.writeheader()
        writer.writerows(dictionaries)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, default=2040)
    parser.add_argument("--batches", type=int, default=4)
    parser.add_argument("--checkpoint-batches", nargs="*", type=int, default=[])
    parser.add_argument("--training-state-count", type=int, default=None)
    parser.add_argument("--batch-steps", type=int, default=64)
    parser.add_argument("--reward-poison-budget", type=float, default=0.5)
    parser.add_argument("--poison-temperature", type=float, default=1.0)
    parser.add_argument("--gamma", type=float, default=0.99)
    parser.add_argument("--mini-batch-size", type=int, default=64)
    parser.add_argument("--opt-epochs", type=int, default=10)
    parser.add_argument(
        "--attack-alignment",
        choices=("parameter", "action"),
        default="parameter",
    )
    parser.add_argument("--deployment-rollouts", type=int, default=8)
    parser.add_argument("--deployment-steps", type=int, default=100)
    parser.add_argument(
        "--sweep-rollouts",
        type=Path,
        default=RESULTS_DIR / "safe_control_gym_quadrotor_reinforce_reward_poisoning_sweep_rollouts.csv",
    )
    parser.add_argument(
        "--summary-out",
        type=Path,
        default=RESULTS_DIR / "safe_control_gym_quadrotor_ppo_reward_poisoning.csv",
    )
    parser.add_argument(
        "--rollouts-out",
        type=Path,
        default=RESULTS_DIR / "safe_control_gym_quadrotor_ppo_reward_poisoning_rollouts.csv",
    )
    parser.add_argument(
        "--traces-out",
        type=Path,
        default=RESULTS_DIR / "safe_control_gym_quadrotor_ppo_reward_poisoning_traces.csv",
    )
    parser.add_argument(
        "--gate-out",
        type=Path,
        default=None,
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    bundle = quad.build_dynamics(args.seed)
    target_snapshot, viable = residual_learner.choose_target(
        bundle,
        seed=args.seed,
        deployment_steps=args.deployment_steps,
        minimum_delay=8,
    )
    training_state_count = args.training_state_count or args.batches
    training_states = quad.spread_subset(viable, training_state_count)
    checkpoints = sorted(set(args.checkpoint_batches))
    if checkpoints and checkpoints[-1] > args.batches:
        raise ValueError("checkpoint batches cannot exceed --batches")
    common = dict(
        seed=args.seed,
        target_snapshot=target_snapshot,
        training_states=training_states,
        batches=args.batches,
        batch_steps=args.batch_steps,
        reward_poison_budget=args.reward_poison_budget,
        poison_temperature=args.poison_temperature,
        gamma=args.gamma,
        mini_batch_size=args.mini_batch_size,
        opt_epochs=args.opt_epochs,
        attack_alignment=args.attack_alignment,
        checkpoint_batches=checkpoints,
    )
    clean_controller, clean_training, clean_traces, clean_checkpoints = train_ppo(
        "clean_ppo_finetune_snapshot",
        poisoned_rewards=False,
        freeze_updates=False,
        **common,
    )
    poison_controller, poison_training, poison_traces, poison_checkpoints = train_ppo(
        "poisoned_ppo_action_only_snapshot",
        poisoned_rewards=True,
        freeze_updates=False,
        **common,
    )
    freeze_controller, freeze_training, freeze_traces, freeze_checkpoints = train_ppo(
        "poisoned_ppo_always_freeze_snapshot",
        poisoned_rewards=True,
        freeze_updates=True,
        **common,
    )
    audit_states_raw = read_audit_states(args.sweep_rollouts)
    indices = np.linspace(
        0, len(audit_states_raw) - 1, args.deployment_rollouts, dtype=int
    )
    audit_states = [audit_states_raw[int(index)] for index in indices]
    rollouts: list[PPODeployment] = []
    summaries: list[PPOSummary] = []
    if checkpoints:
        checkpoint_groups = (
            clean_checkpoints,
            poison_checkpoints,
            freeze_checkpoints,
        )
        for completed_batches in checkpoints:
            for checkpoint_group in checkpoint_groups:
                agent_state, training = checkpoint_group[completed_batches]
                _task, checkpoint_controller = ppo_base.build_ppo(args.seed)
                checkpoint_controller.agent.load_state_dict(deepcopy(agent_state))
                mechanism_rows = deploy_controller(
                    training.mechanism,
                    args.seed,
                    completed_batches,
                    checkpoint_controller,
                    audit_states,
                    steps=args.deployment_steps,
                )
                rollouts.extend(mechanism_rows)
                summaries.append(summarize(training, mechanism_rows))
                checkpoint_controller.close()
    else:
        controller_rows = (
            (clean_controller, clean_training),
            (poison_controller, poison_training),
            (freeze_controller, freeze_training),
        )
        for controller, training in controller_rows:
            mechanism_rows = deploy_controller(
                training.mechanism,
                args.seed,
                training.batches,
                controller,
                audit_states,
                steps=args.deployment_steps,
            )
            rollouts.extend(mechanism_rows)
            summaries.append(summarize(training, mechanism_rows))
    clean_controller.close()
    poison_controller.close()
    freeze_controller.close()
    write_csv(args.summary_out, summaries)
    write_csv(args.rollouts_out, rollouts)
    write_csv(args.traces_out, clean_traces + poison_traces + freeze_traces)
    gate_rows: list[PPOBLiteGate] = []
    if args.gate_out is not None:
        if len(checkpoints) < 2:
            raise ValueError("B-lite gate requires at least two checkpoints")
        gate_rows = assess_b_lite_gate(summaries, rollouts)
        write_csv(args.gate_out, gate_rows)
    for row in summaries:
        print(
            f"{row.mechanism}: adaptation_viol={row.adaptation_constraint_violations} "
            f"batches={row.batches} actor_norm={row.actor_update_norm:.4f} deploy="
            f"{row.violating_rollouts}/{row.deployment_rollouts} "
            f"target_mse={row.target_action_mse:.4f} "
            f"margin={row.worst_normalized_safety_margin:.4f} "
            f"reward={row.mean_deployment_reward:.4f}"
        )
    if gate_rows:
        final_gate = gate_rows[-1]
        print(
            "B-lite gate: physical_signal="
            f"{final_gate.physical_signal} margin_signal_all="
            f"{all(row.margin_signal_at_checkpoint for row in gate_rows)} "
            f"formal_sweep_go={final_gate.formal_sweep_go}"
        )
        print(f"wrote {args.gate_out}")
    print(f"wrote {args.summary_out}")


if __name__ == "__main__":
    main()
