#!/usr/bin/env python3
"""Adversary-free clean cohort: >=20 independent clean training runs, no poisoning.

Motivation
----------
The paper's release-time-safety-gap-without-an-adversary claim currently rests
on 2 failures out of 120 snapshot-state pairs, and both failures come from a
single one of the 5 training runs in the locked V4 confirmation
(``safe_control_gym_cartpole_v4_reviewer_confirmation.py``, learner seed 2100,
selected indices 17 and 22).  That paired design was built to detect a
*poisoning* effect (clean vs. poisoned snapshot, same learner run); it was
never built to estimate the *clean* failure rate on its own, and 5 runs is too
few to do so credibly.  This module trains a purpose-built cohort of
independent CLEAN-only training runs (no reward poisoning anywhere) and
evaluates each one's own snapshot under exactly two release mechanisms, so the
clean rate can be estimated with a run count large enough to matter
(``analyze_v5_clean_cohort.py`` does the estimation).

Fresh seed namespace
---------------------
Learner seeds already used elsewhere in this project: 2040-2042, 2070-2072,
2100-2104; evaluation seeds already used: 8040-8042, 9100-9104; also reserved
but never run: learner 2061, 2062.  This module claims a disjoint block:
learner seeds 2300-2319, evaluation seeds 9300-9319 (20 independent runs).
Confirmed via repo-wide grep of every ``*.py`` file before committing to this
range -- no collisions found.

Deviations from the locked V3/V4 protocol (both required by the fact that
this cohort has no poisoned arm at all)
----------------------------------------------------------------------------
1. Training: ``safe_control_gym_cartpole_v3_fixed_target_tanh.train_seed``
   unconditionally trains a clean *and* a poisoned learner per call.  This
   module instead calls ``safe_control_gym_reinforce_reward_poisoning
   .train_reinforce`` directly with ``poisoned_rewards=False`` and skips the
   poisoned call entirely -- there is no adversary in this cohort, and
   training a poisoned counterpart nobody will use would double the compute
   for 20 runs for no purpose.  This does not change the clean result: the
   clean and poisoned calls in ``train_seed`` use independent env/controller
   instances seeded only from ``learner_seed`` and do not interact, so calling
   the clean branch alone is bit-for-bit identical to the clean half of
   ``train_seed`` (verified below by harness validation against the locked
   V4 clean arm).

2. Audit-set definition: ``run_contracts`` (and therefore
   ``decide_seed``/``aggregate`` in V3, and the additive
   ``safe_control_gym_cartpole_v4_clean_resident_arm.py``) always defines the
   common paired audit set -- which of the 24 deployment states count as
   "initially accepted" -- by *poison* short-horizon CasADi acceptance, since
   the paired design requires one shared set across the clean/poisoned/
   resident trio.  No poisoned snapshot exists in this cohort, so that
   definition is inapplicable.  This module instead defines the audit set by
   *clean* short-horizon CasADi acceptance (the natural analogue: does the
   only snapshot that exists pass the same admission check).  This module
   still reuses the exact same building blocks ``run_contracts`` composes --
   ``contract.baseline_admitted_states``, ``contract.order_spanning_indices``,
   ``contract.casadi_admission``, and ``predictive.run_rollout`` -- rather
   than reimplementing any of that pipeline; only the source of the
   acceptance flag passed into ``run_rollout`` differs.

Mechanisms evaluated per run, per one of its 24 deployment states
-------------------------------------------------------------------
- ``clean_permanent_raw_release``: the clean snapshot is released once and
  controls the full 120-step horizon (no runtime monitoring).
- ``clean_resident_predictive_authority``: the same five-step-ahead CasADi
  monitor from the locked protocol is retained at runtime and switches
  control to the trusted LQR baseline the first step it predicts a
  short-horizon violation.  (Internally this reuses
  ``predictive.run_rollout``'s ``"resident_predictive_simplex"`` contract
  name, which is the exact string that activates its monitoring branch; the
  recorded ``mechanism`` column uses the clean-cohort label above instead.)

Protocol values are read from
``safe_control_gym_cartpole_v4_reviewer_confirmation.locked_args()`` verbatim
-- this module does not define its own copy of the frozen hyperparameters and
never calls that module's ``main()`` or touches its one-shot opened ledger.

Usage
-----
    .venv-safe-control/bin/python safe_control_gym_cartpole_v5_clean_cohort.py
    .venv-safe-control/bin/python safe_control_gym_cartpole_v5_clean_cohort.py --limit 2 --output /tmp/cartpole_v5_smoke

Harness validation (debug-only override, not part of the main 20-run cohort):
    .venv-safe-control/bin/python safe_control_gym_cartpole_v5_clean_cohort.py \\
        --learner-seeds 2100,2101,2102,2103,2104 \\
        --evaluation-seeds 9100,9101,9102,9103,9104 \\
        --output /tmp/cartpole_v5_validation
"""

from __future__ import annotations

import argparse
import time
from dataclasses import dataclass
from pathlib import Path

import numpy as np

import safe_control_gym_cartpole_multiseed_release_contract as contract
import safe_control_gym_cartpole_predictive_simplex_smoke as predictive
import safe_control_gym_cartpole_v3_fixed_target_tanh as v3
import safe_control_gym_cartpole_v4_reviewer_confirmation as v4
import safe_control_gym_reinforce_reward_poisoning as reinforce


ROOT = Path(__file__).resolve().parent
RESULTS = ROOT / "results"
TARGET_EFFECTIVE = v3.TARGET_EFFECTIVE

# Fresh, non-colliding seed namespace (see module docstring).
LEARNER_SEEDS = tuple(range(2300, 2320))
EVALUATION_SEEDS = tuple(range(9300, 9320))

RAW_RELEASE_MECHANISM = "clean_permanent_raw_release"
RESIDENT_MECHANISM = "clean_resident_predictive_authority"
# The exact string predictive.run_rollout checks to activate its monitoring
# branch; must not be renamed.
_RESIDENT_CONTRACT_NAME = "resident_predictive_simplex"


@dataclass
class V5RolloutRow:
    learner_seed: int
    evaluation_seed: int
    mechanism: str
    selected_index: int
    init_x: float
    init_x_dot: float
    init_theta: float
    init_theta_dot: float
    snapshot_initially_accepted: bool
    casadi_full_first_violation_step: int | None
    physical_first_violation_step: int | None
    forward_switch_step: int | None
    baseline_control_steps: int
    mean_reward: float


@dataclass
class V5SeedSummary:
    learner_seed: int
    evaluation_seed: int
    states_accepted: int
    raw_release_violations: int
    resident_violations: int
    resident_switches: int


def train_clean_seed(
    learner_seed: int, protocol: argparse.Namespace
) -> tuple[np.ndarray, reinforce.ReinforceTrainingResult]:
    """Train a single clean (unpoisoned) learner under the locked protocol.

    Deliberately calls ``reinforce.train_reinforce`` directly with
    ``poisoned_rewards=False`` instead of ``v3.train_seed`` (which always
    trains a poisoned counterpart too) -- see module docstring, deviation 1.
    """
    clean_params, clean_result, _clean_traces = reinforce.train_reinforce(
        "v5_clean",
        seed=learner_seed,
        poisoned_rewards=False,
        freeze_updates=False,
        batches=protocol.batches,
        batch_steps=protocol.batch_steps,
        rho=protocol.rho,
        sigma=protocol.sigma,
        actor_lr=protocol.actor_lr,
        gamma=protocol.gamma,
        max_gradient_norm=protocol.max_gradient_norm,
        reward_poison_budget=protocol.reward_poison_budget,
        poison_temperature=protocol.poison_temperature,
        deployment_steps=protocol.deployment_steps,
        action_grid_size=protocol.action_grid_size,
        kernel_backend="casadi",
        target_effective_params=TARGET_EFFECTIVE,
    )
    return clean_params, clean_result


def run_clean_deployment(
    learner_seed: int,
    evaluation_seed: int,
    clean_params: np.ndarray,
    protocol: argparse.Namespace,
) -> list[V5RolloutRow]:
    """Evaluate one clean snapshot on its own 24 deployment states.

    Reuses the exact same building blocks
    ``safe_control_gym_cartpole_v3_fixed_target_tanh.run_contracts`` composes
    (state pool construction, order-spanning selection, CasADi admission,
    predictive rollout) but defines the audit set by CLEAN acceptance instead
    of poison acceptance -- see module docstring, deviation 2.
    """
    candidates, admitted = contract.baseline_admitted_states(
        seed=evaluation_seed,
        candidate_count=protocol.candidate_states,
        horizon=protocol.deployment_steps,
        guard_margin=protocol.baseline_guard_margin,
    )
    selected_count = min(protocol.selected_states, len(admitted))
    if selected_count < 12:
        raise RuntimeError(
            f"only {len(admitted)} baseline-admitted states; need at least 12"
        )
    selected_indices = contract.order_spanning_indices(
        len(admitted), selected_count
    )
    states = [admitted[index] for index in selected_indices]
    clean_short, clean_margins, clean_full = contract.casadi_admission(
        clean_params,
        states,
        seed=evaluation_seed,
        short_horizon=protocol.monitor_horizon,
        full_horizon=protocol.deployment_steps,
    )

    rows: list[V5RolloutRow] = []
    for selected_index, state in enumerate(states):
        clean_accepted = bool(
            clean_short[selected_index] < 0
            and clean_margins[selected_index] <= 0.0
        )
        full_violation = (
            int(clean_full[selected_index])
            if clean_full[selected_index] >= 0
            else None
        )
        for mechanism, contract_name in (
            (RAW_RELEASE_MECHANISM, RAW_RELEASE_MECHANISM),
            (RESIDENT_MECHANISM, _RESIDENT_CONTRACT_NAME),
        ):
            result = predictive.run_rollout(
                contract_name,
                clean_params,
                state,
                state_index=selected_index,
                initially_accepted=clean_accepted,
                casadi_full_first_violation_step=full_violation,
                seed=evaluation_seed,
                monitor_horizon=protocol.monitor_horizon,
                deployment_steps=protocol.deployment_steps,
            )
            rows.append(
                V5RolloutRow(
                    learner_seed=learner_seed,
                    evaluation_seed=evaluation_seed,
                    mechanism=mechanism,
                    selected_index=selected_index,
                    init_x=float(state[0]),
                    init_x_dot=float(state[1]),
                    init_theta=float(state[2]),
                    init_theta_dot=float(state[3]),
                    snapshot_initially_accepted=clean_accepted,
                    casadi_full_first_violation_step=full_violation,
                    physical_first_violation_step=(
                        result.physical_first_violation_step
                    ),
                    forward_switch_step=result.forward_switch_step,
                    baseline_control_steps=result.baseline_control_steps,
                    mean_reward=result.mean_reward,
                )
            )
    del candidates
    return rows


def summarize_seed(
    learner_seed: int, evaluation_seed: int, rows: list[V5RolloutRow]
) -> V5SeedSummary:
    raw = [row for row in rows if row.mechanism == RAW_RELEASE_MECHANISM]
    resident = [row for row in rows if row.mechanism == RESIDENT_MECHANISM]
    return V5SeedSummary(
        learner_seed=learner_seed,
        evaluation_seed=evaluation_seed,
        states_accepted=sum(row.snapshot_initially_accepted for row in raw),
        raw_release_violations=sum(
            row.physical_first_violation_step is not None for row in raw
        ),
        resident_violations=sum(
            row.physical_first_violation_step is not None for row in resident
        ),
        resident_switches=sum(
            row.forward_switch_step is not None for row in resident
        ),
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="evaluate only the first N runs (smoke test); 0 evaluates all",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=RESULTS / "cartpole_v5_clean_cohort",
        help="output prefix; writes <prefix>_rollouts.csv and <prefix>_summary.csv",
    )
    parser.add_argument(
        "--learner-seeds",
        type=v3.parse_seed_list,
        default=None,
        help=(
            "override the learner seed list (debug/validation only; the "
            "committed 20-run cohort uses the default 2300-2319 namespace)"
        ),
    )
    parser.add_argument(
        "--evaluation-seeds",
        type=v3.parse_seed_list,
        default=None,
        help="override the evaluation seed list (paired with --learner-seeds)",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    protocol = v4.locked_args()

    learner_seeds = (
        args.learner_seeds if args.learner_seeds is not None else list(LEARNER_SEEDS)
    )
    evaluation_seeds = (
        args.evaluation_seeds
        if args.evaluation_seeds is not None
        else list(EVALUATION_SEEDS)
    )
    if len(learner_seeds) != len(evaluation_seeds):
        raise ValueError("learner/evaluation seed lists must have equal length")
    pairs = list(zip(learner_seeds, evaluation_seeds))
    if args.limit:
        pairs = pairs[: args.limit]

    all_rows: list[V5RolloutRow] = []
    all_summaries: list[V5SeedSummary] = []
    wall_start = time.time()
    for index, (learner_seed, evaluation_seed) in enumerate(pairs, start=1):
        run_start = time.time()
        print(
            f"[{index}/{len(pairs)}] training clean learner seed={learner_seed} "
            f"evaluation={evaluation_seed}",
            flush=True,
        )
        clean_params, clean_result = train_clean_seed(learner_seed, protocol)
        print(
            f"[{index}/{len(pairs)}] seed={learner_seed}: clean={clean_params.tolist()} "
            f"adaptation_constraint_violations={clean_result.adaptation_constraint_violations}",
            flush=True,
        )
        rows = run_clean_deployment(
            learner_seed, evaluation_seed, clean_params, protocol
        )
        summary = summarize_seed(learner_seed, evaluation_seed, rows)
        elapsed = time.time() - run_start
        print(f"[{index}/{len(pairs)}] {summary} ({elapsed:.1f}s)", flush=True)
        all_rows.extend(rows)
        all_summaries.append(summary)

    rollouts_path = v3.output_path(args.output, "rollouts")
    summary_path = v3.output_path(args.output, "summary")
    v3.write_csv(rollouts_path, all_rows)
    v3.write_csv(summary_path, all_summaries)
    total_elapsed = time.time() - wall_start
    print(f"wrote {rollouts_path}")
    print(f"wrote {summary_path}")
    print(
        f"total wall clock: {total_elapsed:.1f}s for {len(pairs)} run(s) "
        f"({total_elapsed / max(len(pairs), 1):.1f}s/run)"
    )


if __name__ == "__main__":
    main()
