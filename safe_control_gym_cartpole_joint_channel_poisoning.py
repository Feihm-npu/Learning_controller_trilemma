"""U2: reward-log poisoning under a non-singleton attacked-history plausible set.

Reuses the locked residual-REINFORCE harness WITHOUT modification and only
varies the observation-FDI radius rho, which both shifts the attacked history and
sizes the plausible box X_A(h)=[theta-rho, theta+rho] over which the CasADi safe
kernel / commit certificate ranges.  At the C2 value rho=0.005 the box is
near-singleton; the locked grid raises rho so the certificate genuinely ranges
over a non-singleton box while the bounded reward-log attack (unchanged) redirects
the update.  Deployment audits the raw snapshot on true physical states.

See u2_joint_channel_protocol.md for the pre-registered design and stop rule.
"""

from __future__ import annotations

import argparse
import csv
from dataclasses import replace
from pathlib import Path

import numpy as np

import safe_control_gym_reinforce_reward_poisoning as base

gate = base.gate
delayed = base.delayed

RHO_GRID = (0.005, 0.02, 0.04)
NONSINGLETON_RHOS = (0.02, 0.04)


def run_rho(seed: int, rho: float, args: argparse.Namespace) -> dict:
    common = dict(
        seed=seed,
        batches=args.batches,
        batch_steps=args.batch_steps,
        rho=rho,
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
    clean_params, clean_tr, _ = base.train_reinforce(
        "clean", poisoned_rewards=False, freeze_updates=False, **common
    )
    poison_params, poison_tr, _ = base.train_reinforce(
        "poison", poisoned_rewards=True, freeze_updates=False, **common
    )
    _fp, freeze_tr, _ = base.train_reinforce(
        "freeze", poisoned_rewards=True, freeze_updates=True, **common
    )
    committed, cand, adm = base.commit_snapshot(
        poison_params,
        seed=seed,
        deployment_steps=args.deployment_steps,
        admission_guard_margin=args.admission_guard_margin,
        commit_guard_margin=args.commit_guard_margin,
    )
    commit_tr = replace(poison_tr, mechanism="commit")
    snapshots = {
        "clean": clean_params,
        "poison": poison_params,
        "freeze": np.zeros(2),
        "commit": committed,
    }
    trainings = {"clean": clean_tr, "poison": poison_tr, "freeze": freeze_tr, "commit": commit_tr}
    viol = {}
    rollouts = []
    for mech, tr in trainings.items():
        mech_roll = [
            delayed.deploy_raw_snapshot(
                mech, snapshots[mech], s0, seed=seed, deployment_steps=args.deployment_steps
            )
            for s0 in delayed.deployment_envelope()
        ]
        rollouts.extend([(seed, rho, mech, r) for r in mech_roll])
        viol[mech] = base.summarize(tr, mech_roll).violating_rollouts
    return {
        "seed": seed,
        "rho": rho,
        "nonsingleton": rho > 0.005,
        "plausible_halfwidth_rad": rho,
        "certificate_candidates": cand,
        "certificate_admitted": adm,
        "clean": viol["clean"],
        "poison": viol["poison"],
        "freeze": viol["freeze"],
        "commit": viol["commit"],
        "max_poison": float(poison_tr.max_reward_poison),
        "rollouts": rollouts,
    }


def evaluate(rows: list[dict], *, canary_seed: int) -> dict:
    canary_rows = [r for r in rows if r["seed"] == canary_seed]
    passing_rho = None
    for r in canary_rows:
        if (
            r["rho"] in NONSINGLETON_RHOS
            and r["nonsingleton"]
            and r["poison"] >= 5
            and r["clean"] <= 1
            and r["freeze"] == 0
            and r["commit"] == 0
        ):
            passing_rho = r["rho"]
            break
    canary_pass = passing_rho is not None
    # pooled separation at the passing rho (or the smallest non-singleton rho)
    target_rho = passing_rho if passing_rho is not None else NONSINGLETON_RHOS[0]
    pooled = {"clean": 0, "poison": 0, "freeze": 0, "commit": 0, "seeds": 0}
    for r in rows:
        if r["rho"] == target_rho:
            pooled["clean"] += r["clean"]
            pooled["poison"] += r["poison"]
            pooled["freeze"] += r["freeze"]
            pooled["commit"] += r["commit"]
            pooled["seeds"] += 1
    return {
        "canary_seed": canary_seed,
        "canary_pass": canary_pass,
        "passing_nonsingleton_rho": target_rho,
        "pooled_clean_violations": pooled["clean"],
        "pooled_poison_violations": pooled["poison"],
        "pooled_freeze_violations": pooled["freeze"],
        "pooled_commit_violations": pooled["commit"],
        "num_seeds_at_target_rho": pooled["seeds"],
    }


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--seeds", type=str, default="2210")
    p.add_argument("--canary-seed", type=int, default=2210)
    p.add_argument("--batches", type=int, default=12)
    p.add_argument("--batch-steps", type=int, default=8)
    p.add_argument("--sigma", type=float, default=0.8)
    p.add_argument("--actor-lr", type=float, default=1.0)
    p.add_argument("--gamma", type=float, default=0.97)
    p.add_argument("--max-gradient-norm", type=float, default=1.0)
    p.add_argument("--reward-poison-budget", type=float, default=2.0)
    p.add_argument("--poison-temperature", type=float, default=1.0)
    p.add_argument("--deployment-steps", type=int, default=120)
    p.add_argument("--action-grid-size", type=int, default=41)
    p.add_argument("--kernel-backend", choices=("euler", "casadi"), default="casadi")
    p.add_argument("--admission-guard-margin", type=float, default=0.0075)
    p.add_argument("--commit-guard-margin", type=float, default=0.005)
    p.add_argument("--prefix", type=str, default="results/cartpole_joint_channel_poisoning_multiseed")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    seeds = [int(s) for s in args.seeds.split(",") if s.strip()]
    rows = []
    all_rollouts = []
    for seed in seeds:
        for rho in RHO_GRID:
            r = run_rho(seed, rho, args)
            all_rollouts.extend(r.pop("rollouts"))
            rows.append(r)
            print(f"seed={seed} rho={rho} nonsingleton={r['nonsingleton']} "
                  f"clean={r['clean']} poison={r['poison']} freeze={r['freeze']} "
                  f"commit={r['commit']} cert_admitted={r['certificate_admitted']} "
                  f"max_poison={r['max_poison']:.3f}")
    frontier_path = Path(f"{args.prefix}_frontier.csv")
    frontier_path.parent.mkdir(parents=True, exist_ok=True)
    with frontier_path.open("w", newline="") as fh:
        cols = ["seed", "rho", "nonsingleton", "plausible_halfwidth_rad",
                "certificate_candidates", "certificate_admitted",
                "clean", "poison", "freeze", "commit", "max_poison"]
        w = csv.DictWriter(fh, fieldnames=cols)
        w.writeheader()
        w.writerows([{k: r[k] for k in cols} for r in rows])
    roll_path = Path(f"{args.prefix}_rollouts.csv")
    with roll_path.open("w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["seed", "rho", "mechanism", "first_violation_step", "mean_reward"])
        for seed, rho, mech, r in all_rollouts:
            w.writerow([seed, rho, mech, r.first_violation_step, r.mean_reward])
    decision = evaluate(rows, canary_seed=args.canary_seed)
    dec_path = Path(f"{args.prefix}_decision.csv")
    with dec_path.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(decision.keys()))
        w.writeheader()
        w.writerow(decision)
    print("DECISION:", decision)
    print(f"wrote {args.prefix}_frontier/rollouts/decision CSVs")


if __name__ == "__main__":
    main()
