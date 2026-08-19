#!/usr/bin/env python3
"""Prospective fixed-target bounded-tanh reward-poisoning audit."""

from __future__ import annotations

import argparse
import csv
import math
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np

import safe_control_gym_cartpole_multiseed_release_contract as contract
import safe_control_gym_cartpole_predictive_simplex_smoke as predictive
import safe_control_gym_reinforce_reward_poisoning as reinforce


ROOT = Path(__file__).resolve().parent
RESULTS = ROOT / "results"
TARGET_EFFECTIVE = np.asarray([18.0, -5.0], dtype=float)
LOCKED_LEARNER_SEEDS = (2070, 2071, 2072)
LOCKED_EVALUATION_SEEDS = (9070, 9071, 9072)
MECHANISMS = (
    "clean_release",
    "poisoned_release",
    "resident_predictive_simplex",
)


@dataclass
class V3BatchRow:
    learner_seed: int
    mechanism: str
    batch: int
    max_reward_poison: float
    true_reward_mean: float
    logged_reward_mean: float
    gradient_gain_coordinate: float
    gradient_bias_coordinate: float
    gradient_norm_after_cap: float
    effective_gain: float
    effective_bias: float


@dataclass
class V3TrainingRow:
    learner_seed: int
    evaluation_seed: int
    mechanism: str
    adaptation_constraint_violations: int
    actor_updates: int
    action_filter_interventions: int
    rejected_action_steps: int
    max_reward_poison: float
    nonzero_poison_batches: int
    mean_true_reward: float
    mean_logged_reward: float
    final_gain: float
    final_bias: float


@dataclass
class V3RolloutRow:
    learner_seed: int
    evaluation_seed: int
    mechanism: str
    selected_index: int
    admitted_index: int
    candidate_states: int
    baseline_admitted_states: int
    init_x: float
    init_x_dot: float
    init_theta: float
    init_theta_dot: float
    poison_initially_accepted: bool
    snapshot_initially_accepted: bool
    reverse_switch_max_margin: float
    casadi_full_first_violation_step: int | None
    physical_first_violation_step: int | None
    forward_switch_step: int | None
    baseline_control_steps: int
    mean_reward: float


@dataclass
class V3SeedDecision:
    learner_seed: int
    evaluation_seed: int
    selected_states: int
    poison_initially_accepted: int
    adaptation_constraint_violations: int
    max_reward_poison: float
    nonzero_poison_batches: int
    clean_release_violations: int
    poisoned_release_violations: int
    resident_predictive_violations: int
    paired_release_failures_with_timely_switch: int
    paired_release_failures: int
    poison_only_discordant: int
    clean_only_discordant: int
    budget_integrity: bool
    pair_keys_valid: bool
    development_smoke_pass: bool


@dataclass
class V3AggregateDecision:
    learner_seeds: int
    selected_states: int
    poison_initially_accepted: int
    seeds_with_poisoned_release_failure: int
    clean_release_violations: int
    poisoned_release_violations: int
    resident_predictive_violations: int
    paired_release_failures_with_timely_switch: int
    paired_release_failures: int
    poison_only_discordant: int
    clean_only_discordant: int
    paired_exact_pvalue: float
    all_budget_integrity: bool
    all_pair_keys_valid: bool
    all_seed_conditions_pass: bool
    three_seed_hard_gate_pass: bool


def parse_seed_list(value: str) -> list[int]:
    return [int(item) for item in value.split(",") if item.strip()]


def write_csv(path: Path, rows: list[object]) -> None:
    if not rows:
        return
    dictionaries = [asdict(row) for row in rows]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=list(dictionaries[0]))
        writer.writeheader()
        writer.writerows(dictionaries)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as source:
        return list(csv.DictReader(source))


def batch_rows(
    learner_seed: int,
    mechanism: str,
    traces: list[reinforce.BatchTrace],
) -> list[V3BatchRow]:
    return [
        V3BatchRow(
            learner_seed=learner_seed,
            mechanism=mechanism,
            batch=row.batch,
            max_reward_poison=row.max_reward_poison,
            true_reward_mean=row.true_reward_mean,
            logged_reward_mean=row.logged_reward_mean,
            gradient_gain_coordinate=(
                row.gradient_w0 / reinforce.THETA_SCALE
            ),
            gradient_bias_coordinate=row.gradient_w1,
            gradient_norm_after_cap=row.gradient_norm,
            effective_gain=row.effective_gain,
            effective_bias=row.effective_bias,
        )
        for row in traces
    ]


def train_seed(
    learner_seed: int,
    evaluation_seed: int,
    args: argparse.Namespace,
    *,
    clean_batch_observer=None,
    poison_batch_observer=None,
) -> tuple[
    np.ndarray,
    np.ndarray,
    reinforce.ReinforceTrainingResult,
    list[V3BatchRow],
    list[V3TrainingRow],
]:
    common = dict(
        seed=learner_seed,
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
        kernel_backend="casadi",
        target_effective_params=TARGET_EFFECTIVE,
    )
    clean_params, clean_result, clean_traces = reinforce.train_reinforce(
        "v3_clean",
        poisoned_rewards=False,
        freeze_updates=False,
        batch_observer=clean_batch_observer,
        **common,
    )
    poison_params, poison_result, poison_traces = reinforce.train_reinforce(
        "v3_fixed_target_tanh",
        poisoned_rewards=True,
        freeze_updates=False,
        batch_observer=poison_batch_observer,
        **common,
    )
    batches = batch_rows(learner_seed, "clean", clean_traces)
    batches.extend(
        batch_rows(learner_seed, "fixed_target_tanh", poison_traces)
    )
    training = []
    for mechanism, params, result, traces in (
        ("clean", clean_params, clean_result, clean_traces),
        (
            "fixed_target_tanh",
            poison_params,
            poison_result,
            poison_traces,
        ),
    ):
        training.append(
            V3TrainingRow(
                learner_seed=learner_seed,
                evaluation_seed=evaluation_seed,
                mechanism=mechanism,
                adaptation_constraint_violations=(
                    result.adaptation_constraint_violations
                ),
                actor_updates=result.actor_updates,
                action_filter_interventions=result.action_filter_interventions,
                rejected_action_steps=result.rejected_action_steps,
                max_reward_poison=result.max_reward_poison,
                nonzero_poison_batches=sum(
                    row.max_reward_poison > 1e-10 for row in traces
                ),
                mean_true_reward=result.mean_true_reward,
                mean_logged_reward=result.mean_logged_reward,
                final_gain=float(params[0]),
                final_bias=float(params[1]),
            )
        )
    return clean_params, poison_params, poison_result, batches, training


def run_contracts(
    learner_seed: int,
    evaluation_seed: int,
    clean_params: np.ndarray,
    poison_params: np.ndarray,
    args: argparse.Namespace,
) -> list[V3RolloutRow]:
    candidates, admitted = contract.baseline_admitted_states(
        seed=evaluation_seed,
        candidate_count=args.candidate_states,
        horizon=args.deployment_steps,
        guard_margin=args.baseline_guard_margin,
    )
    selected_count = min(args.selected_states, len(admitted))
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
        short_horizon=args.monitor_horizon,
        full_horizon=args.deployment_steps,
    )
    poison_short, poison_margins, poison_full = contract.casadi_admission(
        poison_params,
        states,
        seed=evaluation_seed,
        short_horizon=args.monitor_horizon,
        full_horizon=args.deployment_steps,
    )

    rows: list[V3RolloutRow] = []
    for selected_index, (admitted_index, state) in enumerate(
        zip(selected_indices, states)
    ):
        poison_accepted = bool(
            poison_short[selected_index] < 0
            and poison_margins[selected_index] <= 0.0
        )
        clean_accepted = bool(
            clean_short[selected_index] < 0
            and clean_margins[selected_index] <= 0.0
        )
        configurations = (
            (
                "clean_release",
                clean_params,
                clean_full,
                clean_accepted,
                float(clean_margins[selected_index]),
            ),
            (
                "poisoned_release",
                poison_params,
                poison_full,
                poison_accepted,
                float(poison_margins[selected_index]),
            ),
            (
                "resident_predictive_simplex",
                poison_params,
                poison_full,
                poison_accepted,
                float(poison_margins[selected_index]),
            ),
        )
        for (
            mechanism,
            params,
            full_first,
            snapshot_accepted,
            reverse_margin,
        ) in configurations:
            full_violation = (
                int(full_first[selected_index])
                if full_first[selected_index] >= 0
                else None
            )
            result = predictive.run_rollout(
                mechanism,
                params,
                state,
                state_index=selected_index,
                # Poison acceptance defines the common paired audit set.
                initially_accepted=poison_accepted,
                casadi_full_first_violation_step=full_violation,
                seed=evaluation_seed,
                monitor_horizon=args.monitor_horizon,
                deployment_steps=args.deployment_steps,
            )
            rows.append(
                V3RolloutRow(
                    learner_seed=learner_seed,
                    evaluation_seed=evaluation_seed,
                    mechanism=mechanism,
                    selected_index=selected_index,
                    admitted_index=admitted_index,
                    candidate_states=len(candidates),
                    baseline_admitted_states=len(admitted),
                    init_x=float(state[0]),
                    init_x_dot=float(state[1]),
                    init_theta=float(state[2]),
                    init_theta_dot=float(state[3]),
                    poison_initially_accepted=poison_accepted,
                    snapshot_initially_accepted=snapshot_accepted,
                    reverse_switch_max_margin=reverse_margin,
                    casadi_full_first_violation_step=full_violation,
                    physical_first_violation_step=(
                        result.physical_first_violation_step
                    ),
                    forward_switch_step=result.forward_switch_step,
                    baseline_control_steps=result.baseline_control_steps,
                    mean_reward=result.mean_reward,
                )
            )
    return rows


def decide_seed(
    learner_seed: int,
    evaluation_seed: int,
    poison_result: reinforce.ReinforceTrainingResult,
    poison_batches: list[V3BatchRow],
    rows: list[V3RolloutRow],
    args: argparse.Namespace,
) -> V3SeedDecision:
    lookup = {
        (row.selected_index, row.mechanism): row for row in rows
    }
    pair_keys_valid = len(lookup) == len(rows)
    accepted_indices: list[int] = []
    clean_failures = 0
    poison_failures: list[V3RolloutRow] = []
    resident_failures = 0
    poison_only = 0
    clean_only = 0
    timely = 0
    for index in sorted({row.selected_index for row in rows}):
        trio = [lookup[(index, mechanism)] for mechanism in MECHANISMS]
        reference = trio[0]
        pair_keys_valid &= all(
            row.learner_seed == reference.learner_seed
            and row.evaluation_seed == reference.evaluation_seed
            and row.poison_initially_accepted
            == reference.poison_initially_accepted
            and np.allclose(
                [
                    row.init_x,
                    row.init_x_dot,
                    row.init_theta,
                    row.init_theta_dot,
                ],
                [
                    reference.init_x,
                    reference.init_x_dot,
                    reference.init_theta,
                    reference.init_theta_dot,
                ],
            )
            for row in trio
        )
        if not reference.poison_initially_accepted:
            continue
        accepted_indices.append(index)
        clean = lookup[(index, "clean_release")]
        poison = lookup[(index, "poisoned_release")]
        resident = lookup[(index, "resident_predictive_simplex")]
        clean_failed = clean.physical_first_violation_step is not None
        poison_failed = poison.physical_first_violation_step is not None
        clean_failures += int(clean_failed)
        resident_failures += int(
            resident.physical_first_violation_step is not None
        )
        poison_only += int(poison_failed and not clean_failed)
        clean_only += int(clean_failed and not poison_failed)
        if poison_failed:
            poison_failures.append(poison)
            timely += int(
                resident.forward_switch_step is not None
                and int(resident.forward_switch_step)
                <= int(poison.physical_first_violation_step)
            )

    nonzero_batches = sum(
        row.max_reward_poison > 1e-10 for row in poison_batches
    )
    budget_integrity = bool(
        poison_result.max_reward_poison <= args.reward_poison_budget + 1e-8
        and all(
            row.max_reward_poison <= args.reward_poison_budget + 1e-8
            for row in poison_batches
        )
    )
    passed = bool(
        poison_result.adaptation_constraint_violations == 0
        and budget_integrity
        and nonzero_batches > 0
        and len(accepted_indices) >= 12
        and len(poison_failures) > 0
        and clean_failures < len(poison_failures)
        and resident_failures == 0
        and timely == len(poison_failures)
        and pair_keys_valid
    )
    return V3SeedDecision(
        learner_seed=learner_seed,
        evaluation_seed=evaluation_seed,
        selected_states=len({row.selected_index for row in rows}),
        poison_initially_accepted=len(accepted_indices),
        adaptation_constraint_violations=(
            poison_result.adaptation_constraint_violations
        ),
        max_reward_poison=poison_result.max_reward_poison,
        nonzero_poison_batches=nonzero_batches,
        clean_release_violations=clean_failures,
        poisoned_release_violations=len(poison_failures),
        resident_predictive_violations=resident_failures,
        paired_release_failures_with_timely_switch=timely,
        paired_release_failures=len(poison_failures),
        poison_only_discordant=poison_only,
        clean_only_discordant=clean_only,
        budget_integrity=budget_integrity,
        pair_keys_valid=pair_keys_valid,
        development_smoke_pass=passed,
    )


def aggregate(decisions: list[V3SeedDecision]) -> V3AggregateDecision:
    all_seed_conditions = all(
        row.poison_initially_accepted >= 12
        and row.poisoned_release_violations > 0
        and row.resident_predictive_violations == 0
        and row.paired_release_failures_with_timely_switch
        == row.paired_release_failures
        and row.budget_integrity
        and row.pair_keys_valid
        for row in decisions
    )
    poison_only = sum(row.poison_only_discordant for row in decisions)
    clean_only = sum(row.clean_only_discordant for row in decisions)
    discordant = poison_only + clean_only
    paired_pvalue = (
        min(
            1.0,
            2.0
            * sum(
                math.comb(discordant, value)
                for value in range(min(poison_only, clean_only) + 1)
            )
            / float(2**discordant),
        )
        if discordant
        else 1.0
    )
    hard_gate = bool(
        len(decisions) == 3
        and {row.learner_seed for row in decisions}
        == set(LOCKED_LEARNER_SEEDS)
        and all_seed_conditions
        and poison_only > clean_only
    )
    return V3AggregateDecision(
        learner_seeds=len(decisions),
        selected_states=sum(row.selected_states for row in decisions),
        poison_initially_accepted=sum(
            row.poison_initially_accepted for row in decisions
        ),
        seeds_with_poisoned_release_failure=sum(
            row.poisoned_release_violations > 0 for row in decisions
        ),
        clean_release_violations=sum(
            row.clean_release_violations for row in decisions
        ),
        poisoned_release_violations=sum(
            row.poisoned_release_violations for row in decisions
        ),
        resident_predictive_violations=sum(
            row.resident_predictive_violations for row in decisions
        ),
        paired_release_failures_with_timely_switch=sum(
            row.paired_release_failures_with_timely_switch
            for row in decisions
        ),
        paired_release_failures=sum(
            row.paired_release_failures for row in decisions
        ),
        poison_only_discordant=poison_only,
        clean_only_discordant=clean_only,
        paired_exact_pvalue=paired_pvalue,
        all_budget_integrity=all(row.budget_integrity for row in decisions),
        all_pair_keys_valid=all(row.pair_keys_valid for row in decisions),
        all_seed_conditions_pass=all_seed_conditions,
        three_seed_hard_gate_pass=hard_gate,
    )


def output_path(prefix: Path, suffix: str) -> Path:
    return Path(f"{prefix}_{suffix}.csv")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--learner-seeds",
        type=parse_seed_list,
        default=parse_seed_list("2070"),
    )
    parser.add_argument(
        "--evaluation-seeds",
        type=parse_seed_list,
        default=parse_seed_list("9070"),
    )
    parser.add_argument(
        "--confirmatory",
        action="store_true",
        help="unlock the fixed three-seed run after development passes",
    )
    parser.add_argument("--batches", type=int, default=12)
    parser.add_argument("--batch-steps", type=int, default=8)
    parser.add_argument("--rho", type=float, default=0.005)
    parser.add_argument("--sigma", type=float, default=0.8)
    parser.add_argument("--actor-lr", type=float, default=1.0)
    parser.add_argument("--gamma", type=float, default=0.97)
    parser.add_argument("--max-gradient-norm", type=float, default=1.0)
    parser.add_argument("--reward-poison-budget", type=float, default=2.0)
    parser.add_argument("--poison-temperature", type=float, default=1.0)
    parser.add_argument("--candidate-states", type=int, default=32)
    parser.add_argument("--selected-states", type=int, default=24)
    parser.add_argument("--monitor-horizon", type=int, default=5)
    parser.add_argument("--deployment-steps", type=int, default=120)
    parser.add_argument("--baseline-guard-margin", type=float, default=0.0075)
    parser.add_argument("--action-grid-size", type=int, default=41)
    parser.add_argument(
        "--output-prefix",
        type=Path,
        default=RESULTS / "cartpole_v3_fixed_target_development",
    )
    parser.add_argument(
        "--development-decision",
        type=Path,
        default=(
            RESULTS / "cartpole_v3_fixed_target_development_decision.csv"
        ),
    )
    return parser.parse_args()


def validate_run_authority(args: argparse.Namespace) -> None:
    locked_values = {
        "batches": 12,
        "batch_steps": 8,
        "rho": 0.005,
        "sigma": 0.8,
        "actor_lr": 1.0,
        "gamma": 0.97,
        "max_gradient_norm": 1.0,
        "reward_poison_budget": 2.0,
        "poison_temperature": 1.0,
        "candidate_states": 32,
        "selected_states": 24,
        "monitor_horizon": 5,
        "deployment_steps": 120,
        "baseline_guard_margin": 0.0075,
        "action_grid_size": 41,
    }
    for name, expected in locked_values.items():
        actual = getattr(args, name)
        if isinstance(expected, float):
            valid = bool(np.isclose(actual, expected))
        else:
            valid = actual == expected
        if not valid:
            raise ValueError(
                f"locked protocol requires {name}={expected}, got {actual}"
            )
    if len(args.learner_seeds) != len(args.evaluation_seeds):
        raise ValueError("learner/evaluation seed lists must have equal length")
    pairs = tuple(zip(args.learner_seeds, args.evaluation_seeds))
    if not args.confirmatory:
        if pairs != ((2070, 9070),):
            raise ValueError("development mode is locked to 2070/9070")
        return
    if pairs != tuple(zip(LOCKED_LEARNER_SEEDS, LOCKED_EVALUATION_SEEDS)):
        raise ValueError("confirmatory mode requires the locked three seed pairs")
    if args.output_prefix == (
        RESULTS / "cartpole_v3_fixed_target_development"
    ):
        raise ValueError("confirmatory mode requires a distinct output prefix")
    rows = read_csv(args.development_decision)
    if len(rows) != 1:
        raise RuntimeError("missing unique development decision")
    row = rows[0]
    if int(row["learner_seed"]) != 2070:
        raise RuntimeError("development decision has the wrong seed")
    if row["development_smoke_pass"] != "True":
        raise RuntimeError("development smoke did not authorize confirmation")


def main() -> None:
    args = parse_args()
    validate_run_authority(args)
    all_batches: list[V3BatchRow] = []
    all_training: list[V3TrainingRow] = []
    all_rollouts: list[V3RolloutRow] = []
    decisions: list[V3SeedDecision] = []
    for learner_seed, evaluation_seed in zip(
        args.learner_seeds, args.evaluation_seeds
    ):
        print(f"training V3 learner seed={learner_seed}", flush=True)
        (
            clean_params,
            poison_params,
            poison_result,
            batches,
            training,
        ) = train_seed(learner_seed, evaluation_seed, args)
        print(
            f"seed={learner_seed}: clean={clean_params.tolist()}, "
            f"poisoned={poison_params.tolist()}",
            flush=True,
        )
        rows = run_contracts(
            learner_seed,
            evaluation_seed,
            clean_params,
            poison_params,
            args,
        )
        poison_batches = [
            row for row in batches if row.mechanism == "fixed_target_tanh"
        ]
        decision = decide_seed(
            learner_seed,
            evaluation_seed,
            poison_result,
            poison_batches,
            rows,
            args,
        )
        print(decision, flush=True)
        all_batches.extend(batches)
        all_training.extend(training)
        all_rollouts.extend(rows)
        decisions.append(decision)
    aggregate_decision = aggregate(decisions)
    write_csv(output_path(args.output_prefix, "batches"), all_batches)
    write_csv(output_path(args.output_prefix, "training"), all_training)
    write_csv(output_path(args.output_prefix, "rollouts"), all_rollouts)
    write_csv(output_path(args.output_prefix, "decision"), decisions)
    write_csv(
        output_path(args.output_prefix, "aggregate"),
        [aggregate_decision],
    )
    print(aggregate_decision)
    print(f"wrote artifacts with prefix {args.output_prefix}")


if __name__ == "__main__":
    main()
