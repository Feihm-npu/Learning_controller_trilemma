#!/usr/bin/env python3
"""Locked monitor-horizon sweep over the already released V3 snapshots."""

from __future__ import annotations

import csv
from dataclasses import asdict, dataclass
from pathlib import Path
from statistics import median

import numpy as np

import safe_control_gym_cartpole_multiseed_release_contract as contract
import safe_control_gym_cartpole_predictive_simplex_smoke as predictive


ROOT = Path(__file__).resolve().parent
RESULTS = ROOT / "results"
TRAINING_SOURCE = RESULTS / "cartpole_v3_fixed_target_multiseed_training.csv"
ROLLOUT_SOURCE = RESULTS / "cartpole_v3_fixed_target_multiseed_rollouts.csv"
OUTPUT_PREFIX = RESULTS / "cartpole_horizon_contract_sweep"
LEARNER_SEEDS = (2070, 2071, 2072)
EVALUATION_SEEDS = (9070, 9071, 9072)
HORIZONS = (1, 3, 5, 10, 20)
CANDIDATE_STATES = 32
SELECTED_STATES = 24
DEPLOYMENT_STEPS = 120
BASELINE_GUARD_MARGIN = 0.0075


@dataclass
class HorizonRow:
    learner_seed: int
    evaluation_seed: int
    monitor_horizon: int
    selected_index: int
    admitted_index: int
    poison_initially_accepted: bool
    clean_initially_accepted: bool
    clean_first_violation_step: int | None
    poison_first_violation_step: int | None
    resident_first_violation_step: int | None
    resident_switch_step: int | None
    switch_lead_steps: int | None
    resident_baseline_steps: int
    poison_reverse_max_margin: float


@dataclass
class HorizonSummary:
    scope: str
    monitor_horizon: int
    learner_seeds: int
    selected_states: int
    poison_initially_accepted: int
    clean_release_violations: int
    poisoned_release_violations: int
    resident_violations: int
    seeds_with_poisoned_release_failure: int
    poison_only_discordant: int
    clean_only_discordant: int
    paired_failures_with_timely_switch: int
    paired_release_failures: int
    resident_switches: int
    min_switch_lead_steps: int | None
    median_switch_lead_steps: float | None
    max_switch_lead_steps: int | None
    horizon_condition_pass: bool


@dataclass
class HorizonDecision:
    locked_horizons: int
    qualifying_horizons: int
    qualifying_horizon_values: str
    horizon_robust: bool
    only_h5_separates: bool
    locked_snapshot_match: bool
    locked_state_match: bool


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as source:
        return list(csv.DictReader(source))


def write_csv(path: Path, rows: list[object]) -> None:
    dictionaries = [asdict(row) for row in rows]
    if not dictionaries:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=list(dictionaries[0]))
        writer.writeheader()
        writer.writerows(dictionaries)


def optional_int(value: str) -> int | None:
    return None if value == "" else int(value)


def load_snapshots() -> dict[tuple[int, str], np.ndarray]:
    rows = read_rows(TRAINING_SOURCE)
    snapshots: dict[tuple[int, str], np.ndarray] = {}
    for seed in LEARNER_SEEDS:
        for mechanism in ("clean", "fixed_target_tanh"):
            matching = [
                row
                for row in rows
                if int(row["learner_seed"]) == seed
                and row["mechanism"] == mechanism
            ]
            if len(matching) != 1:
                raise RuntimeError(
                    f"expected one {mechanism} snapshot for learner seed {seed}"
                )
            snapshots[(seed, mechanism)] = np.asarray(
                [float(matching[0]["final_gain"]), float(matching[0]["final_bias"])],
                dtype=float,
            )
    return snapshots


def locked_rollout_lookup() -> dict[tuple[int, int, str], dict[str, str]]:
    rows = read_rows(ROLLOUT_SOURCE)
    lookup = {
        (int(row["learner_seed"]), int(row["selected_index"]), row["mechanism"]): row
        for row in rows
    }
    expected = len(LEARNER_SEEDS) * SELECTED_STATES * 3
    if len(lookup) != expected:
        raise RuntimeError(f"locked rollout table has {len(lookup)} keys, expected {expected}")
    return lookup


def summarize(scope: str, horizon: int, rows: list[HorizonRow]) -> HorizonSummary:
    accepted = [row for row in rows if row.poison_initially_accepted]
    clean_failures = [row for row in accepted if row.clean_first_violation_step is not None]
    poison_failures = [row for row in accepted if row.poison_first_violation_step is not None]
    resident_failures = [
        row for row in accepted if row.resident_first_violation_step is not None
    ]
    leads = [row.switch_lead_steps for row in poison_failures if row.switch_lead_steps is not None]
    seed_count = len({row.learner_seed for row in rows})
    seeds_with_failure = len({row.learner_seed for row in poison_failures})
    timely = sum(
        row.resident_switch_step is not None
        and int(row.resident_switch_step) <= int(row.poison_first_violation_step)
        for row in poison_failures
    )
    condition = bool(
        len(accepted) >= 36
        and seeds_with_failure >= 2
        and not resident_failures
        and timely == len(poison_failures)
    )
    return HorizonSummary(
        scope=scope,
        monitor_horizon=horizon,
        learner_seeds=seed_count,
        selected_states=len(rows),
        poison_initially_accepted=len(accepted),
        clean_release_violations=len(clean_failures),
        poisoned_release_violations=len(poison_failures),
        resident_violations=len(resident_failures),
        seeds_with_poisoned_release_failure=seeds_with_failure,
        poison_only_discordant=sum(
            row.poison_first_violation_step is not None
            and row.clean_first_violation_step is None
            for row in accepted
        ),
        clean_only_discordant=sum(
            row.clean_first_violation_step is not None
            and row.poison_first_violation_step is None
            for row in accepted
        ),
        paired_failures_with_timely_switch=timely,
        paired_release_failures=len(poison_failures),
        resident_switches=sum(row.resident_switch_step is not None for row in accepted),
        min_switch_lead_steps=min(leads) if leads else None,
        median_switch_lead_steps=float(median(leads)) if leads else None,
        max_switch_lead_steps=max(leads) if leads else None,
        horizon_condition_pass=condition,
    )


def main() -> None:
    snapshots = load_snapshots()
    locked = locked_rollout_lookup()
    snapshot_match = True
    state_match = True
    output_rows: list[HorizonRow] = []
    summaries: list[HorizonSummary] = []

    for learner_seed, evaluation_seed in zip(LEARNER_SEEDS, EVALUATION_SEEDS):
        candidates, admitted = contract.baseline_admitted_states(
            seed=evaluation_seed,
            candidate_count=CANDIDATE_STATES,
            horizon=DEPLOYMENT_STEPS,
            guard_margin=BASELINE_GUARD_MARGIN,
        )
        selected_indices = contract.order_spanning_indices(len(admitted), SELECTED_STATES)
        states = [admitted[index] for index in selected_indices]
        clean_params = snapshots[(learner_seed, "clean")]
        poison_params = snapshots[(learner_seed, "fixed_target_tanh")]

        for selected_index, (admitted_index, state) in enumerate(zip(selected_indices, states)):
            locked_poison = locked[(learner_seed, selected_index, "poisoned_release")]
            locked_clean = locked[(learner_seed, selected_index, "clean_release")]
            state_match &= admitted_index == int(locked_poison["admitted_index"])
            state_match &= np.allclose(
                state,
                [
                    float(locked_poison["init_x"]),
                    float(locked_poison["init_x_dot"]),
                    float(locked_poison["init_theta"]),
                    float(locked_poison["init_theta_dot"]),
                ],
                atol=1e-12,
                rtol=0.0,
            )
            snapshot_match &= int(locked_poison["candidate_states"]) == len(candidates)

        for horizon in HORIZONS:
            print(
                f"horizon sweep learner={learner_seed} evaluation={evaluation_seed} H={horizon}",
                flush=True,
            )
            clean_short, clean_margins, _clean_full = contract.casadi_admission(
                clean_params,
                states,
                seed=evaluation_seed,
                short_horizon=horizon,
                full_horizon=DEPLOYMENT_STEPS,
            )
            poison_short, poison_margins, poison_full = contract.casadi_admission(
                poison_params,
                states,
                seed=evaluation_seed,
                short_horizon=horizon,
                full_horizon=DEPLOYMENT_STEPS,
            )
            seed_rows: list[HorizonRow] = []
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
                locked_clean = locked[(learner_seed, selected_index, "clean_release")]
                locked_poison = locked[(learner_seed, selected_index, "poisoned_release")]
                clean_first = optional_int(locked_clean["physical_first_violation_step"])
                poison_first = optional_int(locked_poison["physical_first_violation_step"])
                full_first = (
                    int(poison_full[selected_index])
                    if poison_full[selected_index] >= 0
                    else None
                )
                resident = predictive.run_rollout(
                    "resident_predictive_simplex",
                    poison_params,
                    state,
                    state_index=selected_index,
                    initially_accepted=poison_accepted,
                    casadi_full_first_violation_step=full_first,
                    seed=evaluation_seed,
                    monitor_horizon=horizon,
                    deployment_steps=DEPLOYMENT_STEPS,
                )
                switch_lead = (
                    int(poison_first) - int(resident.forward_switch_step)
                    if poison_accepted
                    and poison_first is not None
                    and resident.forward_switch_step is not None
                    else None
                )
                seed_rows.append(
                    HorizonRow(
                        learner_seed=learner_seed,
                        evaluation_seed=evaluation_seed,
                        monitor_horizon=horizon,
                        selected_index=selected_index,
                        admitted_index=admitted_index,
                        poison_initially_accepted=poison_accepted,
                        clean_initially_accepted=clean_accepted,
                        clean_first_violation_step=(clean_first if poison_accepted else None),
                        poison_first_violation_step=(poison_first if poison_accepted else None),
                        resident_first_violation_step=resident.physical_first_violation_step,
                        resident_switch_step=resident.forward_switch_step,
                        switch_lead_steps=switch_lead,
                        resident_baseline_steps=resident.baseline_control_steps,
                        poison_reverse_max_margin=float(poison_margins[selected_index]),
                    )
                )
            output_rows.extend(seed_rows)
            summaries.append(summarize(str(learner_seed), horizon, seed_rows))

    pooled_summaries: list[HorizonSummary] = []
    for horizon in HORIZONS:
        pooled = [row for row in output_rows if row.monitor_horizon == horizon]
        pooled_summaries.append(summarize("pooled", horizon, pooled))
    summaries.extend(pooled_summaries)
    qualifying = [row.monitor_horizon for row in pooled_summaries if row.horizon_condition_pass]
    decision = HorizonDecision(
        locked_horizons=len(HORIZONS),
        qualifying_horizons=len(qualifying),
        qualifying_horizon_values=";".join(str(value) for value in qualifying),
        horizon_robust=len(qualifying) >= 3,
        only_h5_separates=qualifying == [5],
        locked_snapshot_match=snapshot_match,
        locked_state_match=state_match,
    )
    write_csv(Path(f"{OUTPUT_PREFIX}_rows.csv"), output_rows)
    write_csv(Path(f"{OUTPUT_PREFIX}_summary.csv"), summaries)
    write_csv(Path(f"{OUTPUT_PREFIX}_decision.csv"), [decision])
    print(decision)


if __name__ == "__main__":
    main()
