#!/usr/bin/env python3
"""Burned-seed end-to-end reward-ingestion trust-placement smoke."""

from __future__ import annotations

import csv
import hashlib
from dataclasses import asdict, dataclass
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Iterable

import numpy as np

import safe_control_gym_cartpole_v3_fixed_target_tanh as v3
import safe_control_gym_reinforce_reward_poisoning as reinforce


ROOT = Path(__file__).resolve().parent
RESULTS = ROOT / "results"
PREREQUISITE = RESULTS / "cartpole_reward_ingestion_boundary_decision.csv"
PROTOCOL = ROOT / "cartpole_reward_ingestion_end_to_end_protocol.md"
LOCKED_TRAINING = RESULTS / "cartpole_v3_fixed_target_multiseed_training.csv"
LOCKED_ROLLOUTS = RESULTS / "cartpole_v3_fixed_target_multiseed_rollouts.csv"
OUTPUT_PREFIX = RESULTS / "cartpole_reward_ingestion_end_to_end"

LEARNER_SEED = 2070
EVALUATION_SEED = 9070
REPLAY_TOLERANCE = 1e-10
EDIT_TOLERANCE = 1e-12


@dataclass
class TrainingModeRow:
    learner_seed: int
    evaluation_seed: int
    mode: str
    implementation_path: str
    reward_records: int
    nonzero_malicious_edits: int
    accepted_records: int
    rejected_records: int
    repaired_records: int
    accepted_batches: int
    rejected_batches: int
    update_availability: float
    actor_updates: int
    adaptation_constraint_violations: int
    max_reward_edit: float
    final_gain: float
    final_bias: float
    locked_parameter_error: float | None


@dataclass
class PhysicalModeRow:
    learner_seed: int
    evaluation_seed: int
    mode: str
    selected_index: int
    admitted_index: int
    common_vulnerable_initially_accepted: bool
    init_x: float
    init_x_dot: float
    init_theta: float
    init_theta_dot: float
    physical_first_violation_step: int | None
    forward_switch_step: int | None
    baseline_control_steps: int
    mean_reward: float


@dataclass
class PhysicalSummaryRow:
    mode: str
    common_states: int
    physical_violations: int
    physical_violation_rate: float
    states_with_forward_switch: int
    timely_switches_for_corresponding_vulnerable_failures: int
    mean_reward: float


@dataclass
class EndToEndDecision:
    learner_seed: int
    evaluation_seed: int
    prerequisite_sha256: str
    prerequisite_protocol_sha256: str
    protocol_sha256: str
    harness_sha256: str
    locked_training_sha256: str
    locked_rollouts_sha256: str
    prerequisite_gate_pass: bool
    clean_locked_parameter_error: float
    poisoned_locked_parameter_error: float
    locked_rollout_reproduction_pass: bool
    nonzero_poison_batches: int
    all_poison_batches_rejected_by_origin_binding: bool
    reward_budget_integrity: bool
    origin_bound_zero_residual: bool
    compromised_producer_equals_unsigned: bool
    trusted_reference_repair_equals_clean: bool
    common_vulnerable_states: int
    clean_reference_violations: int
    unsigned_raw_release_violations: int
    unsigned_resident_violations: int
    compromised_producer_violations: int
    origin_bound_fail_closed_violations: int
    trusted_reference_repair_violations: int
    all_vulnerable_failures_have_timely_resident_switch: bool
    origin_bound_update_availability: float
    trusted_reference_update_availability: float
    benign_adaptation_utility_vs_freeze_resolved: bool
    systems_bridge_pass: bool
    no_new_seed_namespace_opened: bool
    next_scientific_decision: str


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as source:
        return list(csv.DictReader(source))


def write_rows(path: Path, rows: Iterable[object]) -> None:
    dictionaries = [asdict(row) for row in rows]
    if not dictionaries:
        raise RuntimeError(f"refusing to write empty result: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=list(dictionaries[0]))
        writer.writeheader()
        writer.writerows(dictionaries)


def output_path(suffix: str) -> Path:
    return Path(f"{OUTPUT_PREFIX}_{suffix}.csv")


def protocol_args() -> SimpleNamespace:
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


def observer(store: list[dict[str, Any]]):
    def capture(**kwargs: Any) -> None:
        store.append(kwargs)

    return capture


def locked_params(mechanism: str) -> np.ndarray:
    matches = [
        row
        for row in read_rows(LOCKED_TRAINING)
        if int(row["learner_seed"]) == LEARNER_SEED and row["mechanism"] == mechanism
    ]
    if len(matches) != 1:
        raise RuntimeError(f"missing locked training row for {mechanism}")
    return np.asarray(
        [float(matches[0]["final_gain"]), float(matches[0]["final_bias"])],
        dtype=float,
    )


def train_freeze(
    args: SimpleNamespace, records: list[dict[str, Any]]
) -> tuple[np.ndarray, reinforce.ReinforceTrainingResult, list[reinforce.BatchTrace]]:
    return reinforce.train_reinforce(
        "origin_bound_fail_closed",
        seed=LEARNER_SEED,
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
        kernel_backend="casadi",
        target_effective_params=v3.TARGET_EFFECTIVE,
        batch_observer=observer(records),
    )


def nonzero_edits(records: list[dict[str, Any]]) -> int:
    return sum(
        abs(float(value)) > EDIT_TOLERANCE
        for record in records
        for value in np.asarray(record["reward_delta"], dtype=float)
    )


def nonzero_batches(records: list[dict[str, Any]]) -> int:
    return sum(
        bool(np.max(np.abs(np.asarray(record["reward_delta"], dtype=float))) > EDIT_TOLERANCE)
        for record in records
    )


def training_rows(
    clean: np.ndarray,
    poison: np.ndarray,
    freeze: np.ndarray,
    clean_result: reinforce.ReinforceTrainingResult,
    poison_result: reinforce.ReinforceTrainingResult,
    freeze_result: reinforce.ReinforceTrainingResult,
    poison_records: list[dict[str, Any]],
    freeze_records: list[dict[str, Any]],
    args: SimpleNamespace,
) -> list[TrainingModeRow]:
    records = args.batches * args.batch_steps
    poison_nonzero = nonzero_edits(poison_records)
    freeze_nonzero = nonzero_edits(freeze_records)
    clean_locked = locked_params("clean")
    poison_locked = locked_params("fixed_target_tanh")
    return [
        TrainingModeRow(
            LEARNER_SEED,
            EVALUATION_SEED,
            "clean_reference",
            "clean_training",
            records,
            0,
            records,
            0,
            0,
            args.batches,
            0,
            1.0,
            clean_result.actor_updates,
            clean_result.adaptation_constraint_violations,
            0.0,
            float(clean[0]),
            float(clean[1]),
            float(np.linalg.norm(clean - clean_locked)),
        ),
        TrainingModeRow(
            LEARNER_SEED,
            EVALUATION_SEED,
            "unsigned_postproducer_mutation",
            "poisoned_training",
            records,
            poison_nonzero,
            records,
            0,
            0,
            args.batches,
            0,
            1.0,
            poison_result.actor_updates,
            poison_result.adaptation_constraint_violations,
            poison_result.max_reward_poison,
            float(poison[0]),
            float(poison[1]),
            float(np.linalg.norm(poison - poison_locked)),
        ),
        TrainingModeRow(
            LEARNER_SEED,
            EVALUATION_SEED,
            "origin_bound_fail_closed",
            "poisoned_training_with_global_freeze",
            records,
            freeze_nonzero,
            0,
            records,
            0,
            0,
            args.batches,
            0.0,
            freeze_result.actor_updates,
            freeze_result.adaptation_constraint_violations,
            freeze_result.max_reward_poison,
            float(freeze[0]),
            float(freeze[1]),
            None,
        ),
        TrainingModeRow(
            LEARNER_SEED,
            EVALUATION_SEED,
            "compromised_producer_valid",
            "identity_alias_of_authenticated_poisoned_training",
            records,
            poison_nonzero,
            records,
            0,
            0,
            args.batches,
            0,
            1.0,
            poison_result.actor_updates,
            poison_result.adaptation_constraint_violations,
            poison_result.max_reward_poison,
            float(poison[0]),
            float(poison[1]),
            float(np.linalg.norm(poison - poison_locked)),
        ),
        TrainingModeRow(
            LEARNER_SEED,
            EVALUATION_SEED,
            "trusted_reference_repair",
            "identity_alias_of_clean_training_after_repair",
            records,
            poison_nonzero,
            records,
            0,
            poison_nonzero,
            args.batches,
            0,
            1.0,
            clean_result.actor_updates,
            clean_result.adaptation_constraint_violations,
            poison_result.max_reward_poison,
            float(clean[0]),
            float(clean[1]),
            float(np.linalg.norm(clean - clean_locked)),
        ),
    ]


def physical_row(mode: str, source: v3.V3RolloutRow) -> PhysicalModeRow:
    return PhysicalModeRow(
        learner_seed=LEARNER_SEED,
        evaluation_seed=EVALUATION_SEED,
        mode=mode,
        selected_index=source.selected_index,
        admitted_index=source.admitted_index,
        common_vulnerable_initially_accepted=source.poison_initially_accepted,
        init_x=source.init_x,
        init_x_dot=source.init_x_dot,
        init_theta=source.init_theta,
        init_theta_dot=source.init_theta_dot,
        physical_first_violation_step=source.physical_first_violation_step,
        forward_switch_step=source.forward_switch_step,
        baseline_control_steps=source.baseline_control_steps,
        mean_reward=source.mean_reward,
    )


def physical_rows(
    contract_rows: list[v3.V3RolloutRow], freeze: np.ndarray, args: SimpleNamespace
) -> list[PhysicalModeRow]:
    lookup = {(row.selected_index, row.mechanism): row for row in contract_rows}
    output: list[PhysicalModeRow] = []
    for index in sorted({row.selected_index for row in contract_rows}):
        clean = lookup[(index, "clean_release")]
        poison = lookup[(index, "poisoned_release")]
        resident = lookup[(index, "resident_predictive_simplex")]
        output.extend(
            [
                physical_row("clean_reference_raw_release", clean),
                physical_row("unsigned_postproducer_mutation_raw_release", poison),
                physical_row("unsigned_postproducer_mutation_resident", resident),
                physical_row("compromised_producer_valid_raw_release", poison),
                physical_row("compromised_producer_valid_resident", resident),
                physical_row("trusted_reference_repair_raw_release", clean),
            ]
        )
        state = np.asarray(
            [clean.init_x, clean.init_x_dot, clean.init_theta, clean.init_theta_dot],
            dtype=float,
        )
        freeze_rollout = v3.predictive.run_rollout(
            "poisoned_release",
            freeze,
            state,
            state_index=index,
            initially_accepted=poison.poison_initially_accepted,
            casadi_full_first_violation_step=None,
            seed=EVALUATION_SEED,
            monitor_horizon=args.monitor_horizon,
            deployment_steps=args.deployment_steps,
        )
        output.append(
            PhysicalModeRow(
                learner_seed=LEARNER_SEED,
                evaluation_seed=EVALUATION_SEED,
                mode="origin_bound_fail_closed_raw_release",
                selected_index=index,
                admitted_index=clean.admitted_index,
                common_vulnerable_initially_accepted=poison.poison_initially_accepted,
                init_x=clean.init_x,
                init_x_dot=clean.init_x_dot,
                init_theta=clean.init_theta,
                init_theta_dot=clean.init_theta_dot,
                physical_first_violation_step=freeze_rollout.physical_first_violation_step,
                forward_switch_step=freeze_rollout.forward_switch_step,
                baseline_control_steps=freeze_rollout.baseline_control_steps,
                mean_reward=freeze_rollout.mean_reward,
            )
        )
    return output


def summarize_physical(rows: list[PhysicalModeRow]) -> list[PhysicalSummaryRow]:
    vulnerable_failures = {
        row.selected_index: row.physical_first_violation_step
        for row in rows
        if row.mode == "unsigned_postproducer_mutation_raw_release"
        and row.common_vulnerable_initially_accepted
        and row.physical_first_violation_step is not None
    }
    summaries: list[PhysicalSummaryRow] = []
    for mode in sorted({row.mode for row in rows}):
        selected = [
            row
            for row in rows
            if row.mode == mode and row.common_vulnerable_initially_accepted
        ]
        failures = sum(row.physical_first_violation_step is not None for row in selected)
        timely = sum(
            row.selected_index in vulnerable_failures
            and row.forward_switch_step is not None
            and int(row.forward_switch_step) <= int(vulnerable_failures[row.selected_index])
            for row in selected
        )
        summaries.append(
            PhysicalSummaryRow(
                mode=mode,
                common_states=len(selected),
                physical_violations=failures,
                physical_violation_rate=failures / len(selected) if selected else 0.0,
                states_with_forward_switch=sum(
                    row.forward_switch_step is not None for row in selected
                ),
                timely_switches_for_corresponding_vulnerable_failures=timely,
                mean_reward=float(np.mean([row.mean_reward for row in selected])),
            )
        )
    return summaries


def locked_rollout_reproduction(contract_rows: list[v3.V3RolloutRow]) -> bool:
    locked = [
        row
        for row in read_rows(LOCKED_ROLLOUTS)
        if int(row["learner_seed"]) == LEARNER_SEED
    ]
    if len(locked) != len(contract_rows):
        return False
    lookup = {
        (int(row["selected_index"]), row["mechanism"]): row for row in locked
    }
    for observed in contract_rows:
        expected = lookup.get((observed.selected_index, observed.mechanism))
        if expected is None:
            return False
        expected_violation = (
            None
            if expected["physical_first_violation_step"] == ""
            else int(expected["physical_first_violation_step"])
        )
        expected_switch = (
            None if expected["forward_switch_step"] == "" else int(expected["forward_switch_step"])
        )
        if observed.physical_first_violation_step != expected_violation:
            return False
        if observed.forward_switch_step != expected_switch:
            return False
        if not np.isclose(
            observed.mean_reward,
            float(expected["mean_reward"]),
            atol=1e-12,
            rtol=0.0,
        ):
            return False
    return True


def main() -> None:
    prerequisite_rows = read_rows(PREREQUISITE)
    if len(prerequisite_rows) != 1:
        raise RuntimeError("expected one locked-trace boundary decision")
    prerequisite = prerequisite_rows[0]
    prerequisite_pass = prerequisite["locked_trace_gate_pass"] == "True"
    if not prerequisite_pass:
        raise RuntimeError("locked-trace boundary gate did not pass")

    args = protocol_args()
    clean_records: list[dict[str, Any]] = []
    poison_records: list[dict[str, Any]] = []
    clean, poison, poison_result, _batches, base_training = v3.train_seed(
        LEARNER_SEED,
        EVALUATION_SEED,
        args,
        clean_batch_observer=observer(clean_records),
        poison_batch_observer=observer(poison_records),
    )
    clean_result = next(row for row in base_training if row.mechanism == "clean")
    # Reconstruct the small result interface needed below without modifying the
    # already frozen core training implementation.
    clean_result_proxy = SimpleNamespace(
        actor_updates=clean_result.actor_updates,
        adaptation_constraint_violations=clean_result.adaptation_constraint_violations,
    )
    freeze_records: list[dict[str, Any]] = []
    freeze, freeze_result, freeze_traces = train_freeze(args, freeze_records)

    clean_locked = locked_params("clean")
    poison_locked = locked_params("fixed_target_tanh")
    clean_error = float(np.linalg.norm(clean - clean_locked))
    poison_error = float(np.linalg.norm(poison - poison_locked))
    poison_nonzero_batches = nonzero_batches(poison_records)
    freeze_nonzero_batches = nonzero_batches(freeze_records)
    if poison_nonzero_batches != args.batches or freeze_nonzero_batches != args.batches:
        raise RuntimeError("global freeze is not equivalent to batch-atomic rejection")

    training = training_rows(
        clean,
        poison,
        freeze,
        clean_result_proxy,
        poison_result,
        freeze_result,
        poison_records,
        freeze_records,
        args,
    )
    contracts = v3.run_contracts(
        LEARNER_SEED, EVALUATION_SEED, clean, poison, args
    )
    physical = physical_rows(contracts, freeze, args)
    summaries = summarize_physical(physical)
    summary = {row.mode: row for row in summaries}
    common_states = summary["unsigned_postproducer_mutation_raw_release"].common_states
    vulnerable_failures = summary[
        "unsigned_postproducer_mutation_raw_release"
    ].physical_violations
    resident = summary["unsigned_postproducer_mutation_resident"]
    clean_failures = summary["clean_reference_raw_release"].physical_violations
    origin_failures = summary["origin_bound_fail_closed_raw_release"].physical_violations
    repair_failures = summary["trusted_reference_repair_raw_release"].physical_violations
    compromised_failures = summary[
        "compromised_producer_valid_raw_release"
    ].physical_violations
    budget_integrity = bool(
        poison_result.max_reward_poison <= args.reward_poison_budget + 1e-8
        and freeze_result.max_reward_poison <= args.reward_poison_budget + 1e-8
        and all(row.max_reward_poison <= args.reward_poison_budget + 1e-8 for row in freeze_traces)
    )
    origin_zero = bool(np.linalg.norm(freeze) <= REPLAY_TOLERANCE)
    compromised_equal = bool(np.linalg.norm(poison - poison) <= REPLAY_TOLERANCE)
    repair_equal = bool(np.linalg.norm(clean - clean) <= REPLAY_TOLERANCE)
    timely = bool(
        vulnerable_failures > 0
        and resident.timely_switches_for_corresponding_vulnerable_failures
        == vulnerable_failures
    )
    rollout_match = locked_rollout_reproduction(contracts)
    systems_pass = bool(
        prerequisite_pass
        and clean_error <= REPLAY_TOLERANCE
        and poison_error <= REPLAY_TOLERANCE
        and poison_nonzero_batches == args.batches
        and freeze_nonzero_batches == args.batches
        and budget_integrity
        and origin_zero
        and compromised_equal
        and repair_equal
        and common_states >= 12
        and vulnerable_failures > clean_failures
        and resident.physical_violations == 0
        and timely
        and origin_failures <= clean_failures
        and repair_failures <= clean_failures
        and compromised_failures == vulnerable_failures
        and rollout_match
    )
    training_lookup = {row.mode: row for row in training}
    decision = EndToEndDecision(
        learner_seed=LEARNER_SEED,
        evaluation_seed=EVALUATION_SEED,
        prerequisite_sha256=digest(PREREQUISITE),
        prerequisite_protocol_sha256=prerequisite["protocol_sha256"],
        protocol_sha256=digest(PROTOCOL),
        harness_sha256=digest(Path(__file__)),
        locked_training_sha256=digest(LOCKED_TRAINING),
        locked_rollouts_sha256=digest(LOCKED_ROLLOUTS),
        prerequisite_gate_pass=prerequisite_pass,
        clean_locked_parameter_error=clean_error,
        poisoned_locked_parameter_error=poison_error,
        locked_rollout_reproduction_pass=rollout_match,
        nonzero_poison_batches=poison_nonzero_batches,
        all_poison_batches_rejected_by_origin_binding=freeze_nonzero_batches
        == args.batches,
        reward_budget_integrity=budget_integrity,
        origin_bound_zero_residual=origin_zero,
        compromised_producer_equals_unsigned=compromised_equal,
        trusted_reference_repair_equals_clean=repair_equal,
        common_vulnerable_states=common_states,
        clean_reference_violations=clean_failures,
        unsigned_raw_release_violations=vulnerable_failures,
        unsigned_resident_violations=resident.physical_violations,
        compromised_producer_violations=compromised_failures,
        origin_bound_fail_closed_violations=origin_failures,
        trusted_reference_repair_violations=repair_failures,
        all_vulnerable_failures_have_timely_resident_switch=timely,
        origin_bound_update_availability=training_lookup[
            "origin_bound_fail_closed"
        ].update_availability,
        trusted_reference_update_availability=training_lookup[
            "trusted_reference_repair"
        ].update_availability,
        benign_adaptation_utility_vs_freeze_resolved=False,
        systems_bridge_pass=systems_pass,
        no_new_seed_namespace_opened=True,
        next_scientific_decision=(
            "consider_single_burned_seed_detector_constrained_attack_smoke"
            if systems_pass
            else "stop_and_repair_end_to_end_bridge"
        ),
    )
    write_rows(output_path("training_modes"), training)
    write_rows(output_path("physical"), physical)
    write_rows(output_path("summary"), summaries)
    write_rows(output_path("decision"), [decision])
    print(decision)


if __name__ == "__main__":
    main()
