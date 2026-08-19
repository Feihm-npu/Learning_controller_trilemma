"""U3: in-loop reward-integrity defense against reward-log poisoning.

Reuses the locked residual-REINFORCE harness and adds a per-batch, frozen,
task-aware known-sign detector INSIDE the update loop: the cartpole task reward is
nonpositive, so a batch whose maximum logged reward exceeds 0 is flagged and its
actor update is frozen (the update-admission step is the only change; environment,
attacker, gradient, clipping, and contracts are identical to C2).  This turns the
paper's frozen OFFLINE detectability audit into an evaluated in-loop DEFENSE
mechanism and measures whether it contains the delayed deployment failure at low
cost to clean learning.

See u3_inloop_defense_protocol.md for the pre-registered design and stop rule.
"""

from __future__ import annotations

import argparse
import csv
from dataclasses import replace
from functools import partial
from pathlib import Path

import numpy as np
from scipy.stats import binomtest

from safe_control_gym.utils.registration import make

import safe_control_gym_reinforce_reward_poisoning as base

gate = base.gate
delayed = base.delayed
LEARNER_LOW = base.LEARNER_LOW
LEARNER_HIGH = base.LEARNER_HIGH
KNOWN_SIGN_TOL = 0.0  # task reward is nonpositive; any logged reward > 0 is flagged


def train_with_defense(
    mechanism: str,
    *,
    seed: int,
    poisoned_rewards: bool,
    defense_enabled: bool,
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
) -> tuple[np.ndarray, int, int, int]:
    """Return (effective_params, actor_updates, batches_flagged, batches_frozen)."""
    task_config, lqr_config, _cbf = gate.build_configs(seed)
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
        ctrl, info, model, action_low=action_low, action_high=action_high,
        deployment_steps=deployment_steps,
    )
    rng = np.random.default_rng(seed + 9107)
    learner_params = np.zeros(2, dtype=float)
    actor_updates = batches_flagged = batches_frozen = 0

    for _batch in range(batches):
        feats, noises, rewards, dones = [], [], [], []
        for _step in range(batch_steps):
            attacked = np.asarray(observation, dtype=float).copy()
            attacked[2] -= rho
            kernel = gate.safe_kernel_for_observation(
                attacked, rho, model, action_grid, guard_margin=0.0,
                kernel_backend=kernel_backend, casadi_fd_func=casadi_fd_func,
            )
            f = base.actor_features(attacked)
            noise = float(rng.normal(0.0, sigma))
            base_action = gate.lqr_action(ctrl, attacked, info)
            raw_action = base_action + float(f @ learner_params) + noise
            filtered, accepted, _corr = gate.project_to_kernel(raw_action, kernel)
            applied = filtered if accepted else raw_action
            observation, reward, done, info = env.step(
                np.asarray([np.clip(applied, action_low, action_high)])
            )
            feats.append(f)
            noises.append(noise)
            rewards.append(float(reward))
            dones.append(float(done))
            if done:
                observation, info = env.reset()
                ctrl.reset_before_run(observation, info, env=env)
        features = np.vstack(feats)
        noise_arr = np.asarray(noises, dtype=float)
        true_rewards = np.asarray(rewards, dtype=float)
        done_arr = np.asarray(dones, dtype=float)
        poison = np.zeros_like(true_rewards)
        if poisoned_rewards:
            poison = base.reward_poison(
                noise_arr, features, learner_params, target_params,
                budget=reward_poison_budget, temperature=poison_temperature,
            )
        logged = true_rewards + poison
        flagged = bool(np.max(logged) > KNOWN_SIGN_TOL)
        batches_flagged += int(flagged)
        if defense_enabled and flagged:
            batches_frozen += 1
            continue  # freeze this batch: skip the actor update
        grad = base.reinforce_gradient(
            features, noise_arr, logged, done_arr, sigma=sigma, gamma=gamma
        )
        gnorm = float(np.linalg.norm(grad))
        if gnorm > max_gradient_norm:
            grad *= max_gradient_norm / gnorm
        candidate = np.minimum(
            np.maximum(learner_params + actor_lr * grad, LEARNER_LOW), LEARNER_HIGH
        )
        actor_updates += int(gate.params_changed(learner_params, candidate))
        learner_params = candidate

    effective = base.to_effective_params(learner_params)
    ctrl.close()
    env.close()
    return effective, actor_updates, batches_flagged, batches_frozen


def deploy(mechanism: str, snapshot: np.ndarray, seed: int, steps: int) -> list:
    return [
        delayed.deploy_raw_snapshot(mechanism, snapshot, s0, seed=seed, deployment_steps=steps)
        for s0 in delayed.deployment_envelope()
    ]


def run_seed(seed: int, args: argparse.Namespace) -> dict:
    common = dict(
        seed=seed, batches=args.batches, batch_steps=args.batch_steps, rho=args.rho,
        sigma=args.sigma, actor_lr=args.actor_lr, gamma=args.gamma,
        max_gradient_norm=args.max_gradient_norm,
        reward_poison_budget=args.reward_poison_budget,
        poison_temperature=args.poison_temperature, deployment_steps=args.deployment_steps,
        action_grid_size=args.action_grid_size, kernel_backend=args.kernel_backend,
    )
    conditions = {
        "clean_undefended": dict(poisoned_rewards=False, defense_enabled=False),
        "poison_undefended": dict(poisoned_rewards=True, defense_enabled=False),
        "poison_defended": dict(poisoned_rewards=True, defense_enabled=True),
        "clean_defended": dict(poisoned_rewards=False, defense_enabled=True),
    }
    out = {"seed": seed}
    per_state = {}
    for name, cfg in conditions.items():
        params, updates, flagged, frozen = train_with_defense(name, **cfg, **common)
        roll = deploy(name, params, seed, args.deployment_steps)
        viol = sum(1 for r in roll if r.first_violation_step is not None)
        out[f"{name}_violations"] = viol
        out[f"{name}_updates"] = updates
        out[f"{name}_batches_flagged"] = flagged
        out[f"{name}_batches_frozen"] = frozen
        per_state[name] = {i: (r.first_violation_step is not None) for i, r in enumerate(roll)}
    out["clean_fp_freeze_fraction"] = (
        out["clean_defended_batches_frozen"] / max(1, args.batches)
    )
    out["_per_state"] = per_state
    return out


def evaluate(seed_rows: list[dict], *, canary_seed: int, batches: int) -> dict:
    canary = next(r for r in seed_rows if r["seed"] == canary_seed)
    canary_pass = bool(
        canary["poison_undefended_violations"] >= 5
        and canary["poison_defended_violations"] <= 1
        and canary["clean_defended_violations"] <= canary["clean_undefended_violations"] + 1
        and canary["clean_fp_freeze_fraction"] <= 0.10
        and canary["poison_undefended_batches_flagged"] >= batches * 0.5
    )
    pooled = {k: 0 for k in [
        "clean_undefended_violations", "poison_undefended_violations",
        "poison_defended_violations", "clean_defended_violations",
        "poison_undefended_batches_flagged", "poison_defended_batches_frozen",
        "clean_defended_batches_frozen"]}
    for r in seed_rows:
        for k in pooled:
            pooled[k] += r[k]
    # paired discordance: poison_undefended vs poison_defended per state
    pd_only = dp_only = 0
    for r in seed_rows:
        u = r["_per_state"]["poison_undefended"]
        d = r["_per_state"]["poison_defended"]
        for i in u:
            if u[i] and not d[i]:
                pd_only += 1
            elif d[i] and not u[i]:
                dp_only += 1
    n = pd_only + dp_only
    pval = float(binomtest(pd_only, n, 0.5, alternative="two-sided").pvalue) if n else 1.0
    return {
        "canary_seed": canary_seed, "canary_pass": canary_pass, "num_seeds": len(seed_rows),
        **{f"pooled_{k}": v for k, v in pooled.items()},
        "defense_prevented_only": pd_only, "defense_caused_only": dp_only,
        "paired_exact_pvalue": pval,
    }


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--seeds", type=str, default="2220")
    p.add_argument("--canary-seed", type=int, default=2220)
    p.add_argument("--batches", type=int, default=12)
    p.add_argument("--batch-steps", type=int, default=8)
    p.add_argument("--rho", type=float, default=0.005)
    p.add_argument("--sigma", type=float, default=0.8)
    p.add_argument("--actor-lr", type=float, default=1.0)
    p.add_argument("--gamma", type=float, default=0.97)
    p.add_argument("--max-gradient-norm", type=float, default=1.0)
    p.add_argument("--reward-poison-budget", type=float, default=2.0)
    p.add_argument("--poison-temperature", type=float, default=1.0)
    p.add_argument("--deployment-steps", type=int, default=120)
    p.add_argument("--action-grid-size", type=int, default=41)
    p.add_argument("--kernel-backend", choices=("euler", "casadi"), default="casadi")
    p.add_argument("--prefix", type=str, default="results/cartpole_inloop_defense_multiseed")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    seeds = [int(s) for s in args.seeds.split(",") if s.strip()]
    rows = [run_seed(s, args) for s in seeds]
    per_seed_cols = [k for k in rows[0] if k != "_per_state"]
    with Path(f"{args.prefix}_per_seed.csv").open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=per_seed_cols)
        w.writeheader()
        w.writerows([{k: r[k] for k in per_seed_cols} for r in rows])
    decision = evaluate(rows, canary_seed=args.canary_seed, batches=args.batches)
    with Path(f"{args.prefix}_decision.csv").open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(decision.keys()))
        w.writeheader()
        w.writerow(decision)
    for r in rows:
        print(f"seed={r['seed']} poison_undef={r['poison_undefended_violations']} "
              f"poison_def={r['poison_defended_violations']} "
              f"clean_undef={r['clean_undefended_violations']} "
              f"clean_def={r['clean_defended_violations']} "
              f"flagged(poison)={r['poison_undefended_batches_flagged']} "
              f"frozen(poison_def)={r['poison_defended_batches_frozen']} "
              f"clean_fp_frac={r['clean_fp_freeze_fraction']:.2f}")
    print("DECISION:", {k: decision[k] for k in ["canary_pass", "pooled_poison_undefended_violations",
          "pooled_poison_defended_violations", "pooled_clean_defended_violations",
          "defense_prevented_only", "paired_exact_pvalue"]})
    print(f"wrote {args.prefix}_per_seed/decision CSVs")


if __name__ == "__main__":
    main()
