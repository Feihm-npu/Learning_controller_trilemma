#!/usr/bin/env python3
"""One-shot five-seed untouched confirmation of the exact locked V3 protocol."""

from __future__ import annotations

import csv
import hashlib
import math
from dataclasses import asdict, dataclass
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import safe_control_gym_cartpole_v3_fixed_target_tanh as v3


ROOT = Path(__file__).resolve().parent
RESULTS = ROOT / "results"
OUTPUT_PREFIX = RESULTS / "cartpole_v4_untouched_confirmation"
OPENED_LEDGER = RESULTS / "cartpole_v4_untouched_confirmation_opened.csv"
PROTOCOL = ROOT / "reviewer_uplift_experiment_protocol.md"
DETECTOR = ROOT / "safe_control_gym_reward_log_detectability.py"
DETECTOR_CALIBRATION = RESULTS / "cartpole_reward_detectability_calibration.csv"
DETECTOR_FREEZE = RESULTS / "cartpole_reward_detectability_freeze.csv"
LEARNER_SEEDS = (2100, 2101, 2102, 2103, 2104)
EVALUATION_SEEDS = (9100, 9101, 9102, 9103, 9104)


@dataclass
class V4StepRow:
    learner_seed: int
    mechanism: str
    batch: int
    step: int
    feature_gain_coordinate: float
    feature_bias_coordinate: float
    exploration_noise: float
    true_reward: float
    logged_reward: float
    reward_delta: float
    done: float


@dataclass
class V4AggregateDecision:
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
    all_adaptation_safe: bool
    all_budget_integrity: bool
    all_pair_keys_valid: bool
    detector_frozen_before_new_seeds: bool
    four_of_five_seed_generality: bool
    five_seed_extension_pass: bool
    five_seed_strong_pass: bool


@dataclass
class OpenedLedger:
    opened_on: str
    status: str
    learner_seeds: str
    evaluation_seeds: str
    protocol_sha256: str
    detector_sha256: str
    detector_calibration_sha256: str


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_csv(path: Path, rows: list[object]) -> None:
    dictionaries = [asdict(row) for row in rows]
    if not dictionaries:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=list(dictionaries[0]))
        writer.writeheader()
        writer.writerows(dictionaries)


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as source:
        return list(csv.DictReader(source))


def locked_args() -> SimpleNamespace:
    return SimpleNamespace(
        batches=12,
        batch_steps=8,
        rho=0.005,
        sigma=0.8,
        actor_lr=1.0,
        gamma=0.97,
        max_gradient_norm=1.0,
        reward_poison_budget=2.0,
        poison_temperature=1.0,
        candidate_states=32,
        selected_states=24,
        monitor_horizon=5,
        deployment_steps=120,
        baseline_guard_margin=0.0075,
        action_grid_size=41,
    )


def validate_and_open_ledger() -> OpenedLedger:
    if OPENED_LEDGER.exists():
        raise RuntimeError(
            "the untouched namespace has already been opened; refusing a second run"
        )
    frozen = read_rows(DETECTOR_FREEZE)
    if len(frozen) != 1 or frozen[0]["new_seed_namespace_unopened"] != "True":
        raise RuntimeError("missing valid pre-seed detector freeze")
    if sha256(DETECTOR) != frozen[0]["detector_sha256"]:
        raise RuntimeError("detector changed after its pre-seed freeze")
    if sha256(DETECTOR_CALIBRATION) != frozen[0]["calibration_sha256"]:
        raise RuntimeError("detector calibration changed after its pre-seed freeze")
    ledger = OpenedLedger(
        opened_on="2026-08-03",
        status="in_progress",
        learner_seeds=";".join(str(seed) for seed in LEARNER_SEEDS),
        evaluation_seeds=";".join(str(seed) for seed in EVALUATION_SEEDS),
        protocol_sha256=sha256(PROTOCOL),
        detector_sha256=sha256(DETECTOR),
        detector_calibration_sha256=sha256(DETECTOR_CALIBRATION),
    )
    write_csv(OPENED_LEDGER, [ledger])
    return ledger


def collector(store: list[dict[str, Any]]):
    def capture(**kwargs: Any) -> None:
        store.append(kwargs)

    return capture


def convert_steps(
    learner_seed: int, mechanism: str, records: list[dict[str, Any]]
) -> list[V4StepRow]:
    rows: list[V4StepRow] = []
    for record in records:
        for step in range(len(record["true_rewards"])):
            rows.append(
                V4StepRow(
                    learner_seed=learner_seed,
                    mechanism=mechanism,
                    batch=int(record["batch"]),
                    step=step,
                    feature_gain_coordinate=float(record["features"][step, 0]),
                    feature_bias_coordinate=float(record["features"][step, 1]),
                    exploration_noise=float(record["exploration_noise"][step]),
                    true_reward=float(record["true_rewards"][step]),
                    logged_reward=float(record["logged_rewards"][step]),
                    reward_delta=float(record["reward_delta"][step]),
                    done=float(record["dones"][step]),
                )
            )
    return rows


def exact_pvalue(poison_only: int, clean_only: int) -> float:
    discordant = poison_only + clean_only
    if discordant == 0:
        return 1.0
    return min(
        1.0,
        2.0
        * sum(
            math.comb(discordant, value)
            for value in range(min(poison_only, clean_only) + 1)
        )
        / float(2**discordant),
    )


def aggregate(
    decisions: list[v3.V3SeedDecision],
    training: list[v3.V3TrainingRow],
) -> V4AggregateDecision:
    poison_only = sum(row.poison_only_discordant for row in decisions)
    clean_only = sum(row.clean_only_discordant for row in decisions)
    pvalue = exact_pvalue(poison_only, clean_only)
    failure_seeds = sum(row.poisoned_release_violations > 0 for row in decisions)
    all_adaptation_safe = all(row.adaptation_constraint_violations == 0 for row in training)
    integrity = bool(
        all_adaptation_safe
        and all(row.budget_integrity for row in decisions)
        and all(row.pair_keys_valid for row in decisions)
    )
    resident_failures = sum(row.resident_predictive_violations for row in decisions)
    failures = sum(row.paired_release_failures for row in decisions)
    timely = sum(row.paired_release_failures_with_timely_switch for row in decisions)
    extension_pass = bool(
        len(decisions) == 5
        and {row.learner_seed for row in decisions} == set(LEARNER_SEEDS)
        and integrity
        and resident_failures == 0
        and timely == failures
        and failure_seeds >= 4
        and poison_only > clean_only
        and pvalue < 0.05
    )
    return V4AggregateDecision(
        learner_seeds=len(decisions),
        selected_states=sum(row.selected_states for row in decisions),
        poison_initially_accepted=sum(row.poison_initially_accepted for row in decisions),
        seeds_with_poisoned_release_failure=failure_seeds,
        clean_release_violations=sum(row.clean_release_violations for row in decisions),
        poisoned_release_violations=sum(
            row.poisoned_release_violations for row in decisions
        ),
        resident_predictive_violations=resident_failures,
        paired_release_failures_with_timely_switch=timely,
        paired_release_failures=failures,
        poison_only_discordant=poison_only,
        clean_only_discordant=clean_only,
        paired_exact_pvalue=pvalue,
        all_adaptation_safe=all_adaptation_safe,
        all_budget_integrity=all(row.budget_integrity for row in decisions),
        all_pair_keys_valid=all(row.pair_keys_valid for row in decisions),
        detector_frozen_before_new_seeds=True,
        four_of_five_seed_generality=failure_seeds >= 4,
        five_seed_extension_pass=extension_pass,
        five_seed_strong_pass=bool(extension_pass and failure_seeds == 5),
    )


def main() -> None:
    ledger = validate_and_open_ledger()
    protocol = locked_args()
    all_batches: list[v3.V3BatchRow] = []
    all_training: list[v3.V3TrainingRow] = []
    all_rollouts: list[v3.V3RolloutRow] = []
    all_steps: list[V4StepRow] = []
    decisions: list[v3.V3SeedDecision] = []

    for learner_seed, evaluation_seed in zip(LEARNER_SEEDS, EVALUATION_SEEDS):
        print(f"opening untouched learner={learner_seed} evaluation={evaluation_seed}", flush=True)
        clean_records: list[dict[str, Any]] = []
        poison_records: list[dict[str, Any]] = []
        clean, poison, poison_result, batches, training = v3.train_seed(
            learner_seed,
            evaluation_seed,
            protocol,
            clean_batch_observer=collector(clean_records),
            poison_batch_observer=collector(poison_records),
        )
        rollout_rows = v3.run_contracts(
            learner_seed,
            evaluation_seed,
            clean,
            poison,
            protocol,
        )
        decision = v3.decide_seed(
            learner_seed,
            evaluation_seed,
            poison_result,
            [row for row in batches if row.mechanism == "fixed_target_tanh"],
            rollout_rows,
            protocol,
        )
        print(decision, flush=True)
        all_batches.extend(batches)
        all_training.extend(training)
        all_rollouts.extend(rollout_rows)
        all_steps.extend(convert_steps(learner_seed, "clean", clean_records))
        all_steps.extend(
            convert_steps(learner_seed, "fixed_target_tanh", poison_records)
        )
        decisions.append(decision)

    aggregate_decision = aggregate(decisions, all_training)
    v3.write_csv(v3.output_path(OUTPUT_PREFIX, "batches"), all_batches)
    v3.write_csv(v3.output_path(OUTPUT_PREFIX, "training"), all_training)
    v3.write_csv(v3.output_path(OUTPUT_PREFIX, "rollouts"), all_rollouts)
    v3.write_csv(v3.output_path(OUTPUT_PREFIX, "decision"), decisions)
    write_csv(v3.output_path(OUTPUT_PREFIX, "steps"), all_steps)
    write_csv(v3.output_path(OUTPUT_PREFIX, "aggregate"), [aggregate_decision])
    ledger.status = "completed"
    write_csv(OPENED_LEDGER, [ledger])
    print(aggregate_decision)


if __name__ == "__main__":
    main()
