"""U1 second learner family: reward-log poisoning against an online A2C actor.

This reuses the locked REINFORCE harness (environment, CasADi action-kernel
filter, bounded reward-log attacker, commit/freeze contracts, deployment audit)
without modification and changes ONLY the learner update rule: the constant
batch-mean baseline of REINFORCE is replaced by a learned linear per-state value
critic (advantage actor--critic).  The threat model is identical to the paper's
C2 study: the attacker writes only the scalar reward log within an L-infinity
budget and never writes actions, gradients, actor/critic parameters, optimizer
state, dynamics, or deployment states.  The critic is trained by the trusted
learner from logged rewards.

See u1_second_learner_family_protocol.md for the pre-registered design and stop
rule.  Do not tune critic hyperparameters against the outcome.
"""

from __future__ import annotations

import argparse
import csv
from dataclasses import asdict, replace
from functools import partial
from pathlib import Path
from statistics import median

import numpy as np
from scipy.stats import binomtest

from safe_control_gym.utils.registration import make

import safe_control_gym_reinforce_reward_poisoning as base

gate = base.gate
delayed = base.delayed
ROOT = base.ROOT
RESULTS_DIR = base.RESULTS_DIR
LEARNER_LOW = base.LEARNER_LOW
LEARNER_HIGH = base.LEARNER_HIGH

MECHANISMS = (
    "clean_a2c_snapshot",
    "poisoned_action_only_snapshot",
    "poisoned_always_freeze_snapshot",
    "poisoned_commit_gate_snapshot",
)


def a2c_gradient(
    features: np.ndarray,
    exploration_noise: np.ndarray,
    logged_rewards: np.ndarray,
    dones: np.ndarray,
    critic_params: np.ndarray,
    *,
    sigma: float,
    gamma: float,
    critic_lr: float,
    critic_steps: int,
) -> tuple[np.ndarray, np.ndarray]:
    """Advantage actor--critic gradient with a learned linear value baseline.

    Returns (policy_gradient, updated_critic_params).  The critic is fit by
    gradient regression to the reward-to-go returns computed from the logged
    (possibly poisoned) rewards; the advantage is the state-dependent residual.
    """
    returns = base.reward_to_go(logged_rewards, dones, gamma=gamma)
    critic = np.asarray(critic_params, dtype=float).copy()
    for _ in range(critic_steps):
        values = features @ critic
        residual = returns - values
        critic = critic + critic_lr * np.mean(residual[:, None] * features, axis=0)
    values = features @ critic
    advantages = returns - values
    scale = float(np.std(advantages))
    if scale > 1e-8:
        advantages = advantages / scale
    scores = exploration_noise[:, None] * features / (sigma**2)
    gradient = np.mean(advantages[:, None] * scores, axis=0)
    return gradient, critic


def train_a2c(
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
    critic_lr: float,
    critic_steps: int,
) -> tuple[np.ndarray, base.ReinforceTrainingResult, list[base.BatchTrace]]:
    """Mirror of train_reinforce with the actor--critic update rule.

    Only the gradient block differs from the locked REINFORCE loop; the
    environment, action-kernel filter, attacker, clipping, and parameter box are
    identical.
    """
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
    target_params = base.choose_attack_target(
        ctrl,
        info,
        model,
        action_low=action_low,
        action_high=action_high,
        deployment_steps=deployment_steps,
    )

    rng = np.random.default_rng(seed + 9107)
    learner_params = np.zeros(2, dtype=float)
    critic_params = np.zeros(2, dtype=float)
    traces: list[base.BatchTrace] = []
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
            features = base.actor_features(attacked_observation)
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
            poison = base.reward_poison(
                noise_array,
                features_array,
                learner_params,
                target_params,
                budget=reward_poison_budget,
                temperature=poison_temperature,
            )
        logged_rewards = true_rewards + poison
        raw_gradient, critic_params = a2c_gradient(
            features_array,
            noise_array,
            logged_rewards,
            dones,
            critic_params,
            sigma=sigma,
            gamma=gamma,
            critic_lr=critic_lr,
            critic_steps=critic_steps,
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

        effective = base.to_effective_params(learner_params)
        maximum_poison = max(maximum_poison, float(np.max(np.abs(poison))))
        true_rewards_all.extend(true_rewards.tolist())
        logged_rewards_all.extend(logged_rewards.tolist())
        gradient_norms.append(gradient_norm)
        traces.append(
            base.BatchTrace(
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

    effective = base.to_effective_params(learner_params)
    ctrl.close()
    env.close()
    result = base.ReinforceTrainingResult(
        mechanism=mechanism,
        seed=seed,
        batches=batches,
        batch_steps=batch_steps,
        adaptation_steps=batches * batch_steps,
        reward_poison_budget=reward_poison_budget,
        max_reward_poison=maximum_poison,
        attack_target_gain=float(base.to_effective_params(target_params)[0]),
        attack_target_bias=float(base.to_effective_params(target_params)[1]),
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


def run_seed(seed: int, args: argparse.Namespace) -> dict:
    """Run the four contracts for one learner seed and return per-state outcomes."""
    common = dict(
        seed=seed,
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
        critic_lr=args.critic_lr,
        critic_steps=args.critic_steps,
    )
    clean_params, clean_training, clean_traces = train_a2c(
        "clean_a2c_snapshot", poisoned_rewards=False, freeze_updates=False, **common
    )
    poison_params, poison_training, poison_traces = train_a2c(
        "poisoned_action_only_snapshot",
        poisoned_rewards=True,
        freeze_updates=False,
        **common,
    )
    _freeze_params, freeze_training, freeze_traces = train_a2c(
        "poisoned_always_freeze_snapshot",
        poisoned_rewards=True,
        freeze_updates=True,
        **common,
    )
    committed, cand, admitted = base.commit_snapshot(
        poison_params,
        seed=seed,
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
        certificate_candidates=cand,
        certificate_admitted=admitted,
    )
    snapshots = {
        "clean_a2c_snapshot": clean_params,
        "poisoned_action_only_snapshot": poison_params,
        "poisoned_always_freeze_snapshot": np.zeros(2),
        "poisoned_commit_gate_snapshot": committed,
    }
    training_rows = [clean_training, poison_training, freeze_training, commit_training]
    summaries: list[base.ReinforceSummary] = []
    rollouts: list = []
    per_state_fail: dict[str, dict[int, bool]] = {}
    for training in training_rows:
        mech_rollouts = [
            delayed.deploy_raw_snapshot(
                training.mechanism,
                snapshots[training.mechanism],
                initial_state,
                seed=seed,
                deployment_steps=args.deployment_steps,
            )
            for initial_state in delayed.deployment_envelope()
        ]
        rollouts.extend(mech_rollouts)
        summaries.append(base.summarize(training, mech_rollouts))
        per_state_fail[training.mechanism] = {
            i: (row.first_violation_step is not None)
            for i, row in enumerate(mech_rollouts)
        }
    return {
        "seed": seed,
        "summaries": summaries,
        "rollouts": rollouts,
        "traces": clean_traces + poison_traces + freeze_traces,
        "per_state_fail": per_state_fail,
        "max_poison": float(poison_training.max_reward_poison),
    }


def evaluate(seed_results: list[dict], *, canary_seed: int) -> dict:
    """Compute per-seed and pooled outcomes plus the locked canary decision."""
    def viol(summ_list, mech):
        for s in summ_list:
            if s.mechanism == mech:
                return s.violating_rollouts
        return 0

    per_seed = []
    poison_only = clean_only = 0
    pooled_clean = pooled_poison = pooled_commit = pooled_freeze = 0
    seeds_with_poison_fail = 0
    for r in seed_results:
        c = viol(r["summaries"], "clean_a2c_snapshot")
        p = viol(r["summaries"], "poisoned_action_only_snapshot")
        f = viol(r["summaries"], "poisoned_always_freeze_snapshot")
        cm = viol(r["summaries"], "poisoned_commit_gate_snapshot")
        pooled_clean += c
        pooled_poison += p
        pooled_freeze += f
        pooled_commit += cm
        seeds_with_poison_fail += int(p > 0)
        cf = r["per_state_fail"]["clean_a2c_snapshot"]
        pf = r["per_state_fail"]["poisoned_action_only_snapshot"]
        for i in cf:
            if pf[i] and not cf[i]:
                poison_only += 1
            elif cf[i] and not pf[i]:
                clean_only += 1
        per_seed.append(
            {"seed": r["seed"], "clean": c, "poison": p, "freeze": f, "commit": cm,
             "max_poison": r["max_poison"]}
        )

    canary = next(r for r in seed_results if r["seed"] == canary_seed)
    cc = viol(canary["summaries"], "clean_a2c_snapshot")
    cp = viol(canary["summaries"], "poisoned_action_only_snapshot")
    cf_ = viol(canary["summaries"], "poisoned_always_freeze_snapshot")
    ccm = viol(canary["summaries"], "poisoned_commit_gate_snapshot")
    canary_pass = bool(
        cp >= 5 and cc <= 1 and cf_ == 0 and ccm == 0
        and canary["max_poison"] <= 2.0 + 1e-8
    )
    n_disc = poison_only + clean_only
    if n_disc > 0:
        pval = float(binomtest(poison_only, n_disc, 0.5, alternative="two-sided").pvalue)
    else:
        pval = 1.0
    return {
        "per_seed": per_seed,
        "canary_seed": canary_seed,
        "canary_pass": canary_pass,
        "canary_clean": cc,
        "canary_poison": cp,
        "canary_freeze": cf_,
        "canary_commit": ccm,
        "pooled_clean_violations": pooled_clean,
        "pooled_poison_violations": pooled_poison,
        "pooled_freeze_violations": pooled_freeze,
        "pooled_commit_violations": pooled_commit,
        "seeds_with_poison_failure": seeds_with_poison_fail,
        "poison_only_discordant": poison_only,
        "clean_only_discordant": clean_only,
        "paired_exact_pvalue": pval,
        "num_seeds": len(seed_results),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seeds", type=str, default="2200")
    parser.add_argument("--canary-seed", type=int, default=2200)
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
    parser.add_argument("--kernel-backend", choices=("euler", "casadi"), default="casadi")
    parser.add_argument("--admission-guard-margin", type=float, default=0.0075)
    parser.add_argument("--commit-guard-margin", type=float, default=0.005)
    parser.add_argument("--critic-lr", type=float, default=0.5)
    parser.add_argument("--critic-steps", type=int, default=5)
    parser.add_argument("--prefix", type=str, default="results/cartpole_a2c_reward_poisoning")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    seeds = [int(s) for s in args.seeds.split(",") if s.strip()]
    seed_results = [run_seed(seed, args) for seed in seeds]
    all_summaries = []
    all_rollouts = []
    all_traces = []
    for r in seed_results:
        all_summaries.extend(r["summaries"])
        all_rollouts.extend(r["rollouts"])
        all_traces.extend(r["traces"])
    base.write_csv(Path(f"{args.prefix}_summary.csv"), all_summaries)
    base.write_csv(Path(f"{args.prefix}_rollouts.csv"), all_rollouts)
    base.write_csv(Path(f"{args.prefix}_traces.csv"), all_traces)
    decision = evaluate(seed_results, canary_seed=args.canary_seed)
    dec_path = Path(f"{args.prefix}_decision.csv")
    dec_path.parent.mkdir(parents=True, exist_ok=True)
    with dec_path.open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(decision.keys() - {"per_seed"}))
        writer.writeheader()
        writer.writerow({k: v for k, v in decision.items() if k != "per_seed"})
    per_seed_path = Path(f"{args.prefix}_per_seed.csv")
    with per_seed_path.open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(decision["per_seed"][0].keys()))
        writer.writeheader()
        writer.writerows(decision["per_seed"])
    print("per-seed:", decision["per_seed"])
    print(
        f"canary seed {decision['canary_seed']}: clean={decision['canary_clean']} "
        f"poison={decision['canary_poison']} freeze={decision['canary_freeze']} "
        f"commit={decision['canary_commit']} -> PASS={decision['canary_pass']}"
    )
    print(
        f"pooled clean={decision['pooled_clean_violations']} "
        f"poison={decision['pooled_poison_violations']} "
        f"freeze={decision['pooled_freeze_violations']} "
        f"commit={decision['pooled_commit_violations']}; "
        f"poison_only={decision['poison_only_discordant']} "
        f"clean_only={decision['clean_only_discordant']} "
        f"p={decision['paired_exact_pvalue']:.3e}"
    )
    print(f"wrote {args.prefix}_summary/rollouts/traces/decision/per_seed CSVs")


if __name__ == "__main__":
    main()
