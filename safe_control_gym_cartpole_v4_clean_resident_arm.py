#!/usr/bin/env python3
"""Additive V4 arm: resident predictive authority on the CLEAN snapshots.

The locked V4 confirmation evaluated three mechanisms -- clean_release,
poisoned_release, and resident_predictive_simplex -- but the resident arm was
run on the poisoned snapshot only (its reverse-switch margins are identical to
poisoned_release on 120/120 pairs).  The manuscript's adversary-free claim
compares clean raw release against a resident arm that was never run on a clean
snapshot.  This script supplies the missing arm.

Nothing in the locked namespace is retrained or rewritten.  The clean policy
parameters are read back from the recorded training rows, the deployment states
are read back from the recorded rollout rows, and the common paired audit set
is still defined by poison acceptance, exactly as in
``safe_control_gym_cartpole_v3_fixed_target_tanh.run_contracts``.

Usage:
    .venv-safe-control/bin/python safe_control_gym_cartpole_v4_clean_resident_arm.py
    .venv-safe-control/bin/python safe_control_gym_cartpole_v4_clean_resident_arm.py --limit 4
"""

from __future__ import annotations

import argparse
import csv
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np

import safe_control_gym_cartpole_predictive_simplex_smoke as predictive

ROOT = Path(__file__).resolve().parent
RESULTS = ROOT / "results"
SOURCE_PREFIX = RESULTS / "cartpole_v4_untouched_confirmation"
OUTPUT = RESULTS / "cartpole_v4_clean_resident_arm_rollouts.csv"
SUMMARY = RESULTS / "cartpole_v4_clean_resident_arm_summary.csv"

# Locked V4 contract parameters (safe_control_gym_cartpole_v4_reviewer_confirmation.locked_args).
MONITOR_HORIZON = 5
DEPLOYMENT_STEPS = 120


@dataclass
class CleanResidentRow:
    learner_seed: int
    evaluation_seed: int
    mechanism: str
    selected_index: int
    admitted_index: int
    init_x: float
    init_x_dot: float
    init_theta: float
    init_theta_dot: float
    poison_initially_accepted: bool
    snapshot_initially_accepted: bool
    clean_casadi_full_first_violation_step: int
    physical_first_violation_step: int
    forward_switch_step: int
    baseline_control_steps: int
    mean_reward: float
    paired_clean_release_violation_step: int


@dataclass
class CleanResidentSummary:
    pairs: int
    clean_release_violations: int
    clean_resident_violations: int
    clean_resident_forward_switches: int
    switches_before_paired_release_failure: int
    median_switch_lead_steps: float


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def snapshot_parameters(snapshot: str) -> dict[int, np.ndarray]:
    """Recorded snapshot for each locked V4 learner seed.

    ``clean`` gives the missing arm.  ``fixed_target_tanh`` reruns the poisoned
    arm the locked namespace already contains, which validates this harness
    against the recorded 27 switches and 0 physical violations.
    """
    params: dict[int, np.ndarray] = {}
    for row in read_rows(SOURCE_PREFIX.with_name(SOURCE_PREFIX.name + "_training.csv")):
        if row["mechanism"] != snapshot:
            continue
        params[int(row["learner_seed"])] = np.asarray(
            [float(row["final_gain"]), float(row["final_bias"])], dtype=float
        )
    return params


def optional_step(value: str) -> int:
    if value in ("", "-1", "None", "nan"):
        return -1
    return int(float(value))


def write_csv(path: Path, rows: list) -> None:
    if not rows:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = [asdict(row) for row in rows]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(payload[0].keys()))
        writer.writeheader()
        writer.writerows(payload)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="evaluate only the first N pairs (smoke test); 0 evaluates all",
    )
    parser.add_argument(
        "--snapshot",
        choices=("clean", "fixed_target_tanh"),
        default="clean",
        help=(
            "which recorded V4 snapshot to give resident authority; "
            "fixed_target_tanh reproduces the locked poisoned arm as a harness check"
        ),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=OUTPUT,
        help="rollout CSV destination",
    )
    args = parser.parse_args()

    params_by_seed = snapshot_parameters(args.snapshot)
    source = [
        row
        for row in read_rows(
            SOURCE_PREFIX.with_name(SOURCE_PREFIX.name + "_rollouts.csv")
        )
        if row["mechanism"] == "clean_release"
    ]
    if args.limit:
        source = source[: args.limit]

    rows: list[CleanResidentRow] = []
    for index, source_row in enumerate(source, start=1):
        learner_seed = int(source_row["learner_seed"])
        evaluation_seed = int(source_row["evaluation_seed"])
        state = np.asarray(
            [
                float(source_row["init_x"]),
                float(source_row["init_x_dot"]),
                float(source_row["init_theta"]),
                float(source_row["init_theta_dot"]),
            ],
            dtype=float,
        )
        clean_full_first = optional_step(
            source_row["casadi_full_first_violation_step"]
        )
        # The locked protocol defines the common paired audit set by poison
        # acceptance; the clean release arm used the same flag.
        initially_accepted = source_row["poison_initially_accepted"] == "True"
        rollout = predictive.run_rollout(
            "resident_predictive_simplex",
            params_by_seed[learner_seed],
            state,
            state_index=int(source_row["selected_index"]),
            initially_accepted=initially_accepted,
            casadi_full_first_violation_step=(
                clean_full_first if clean_full_first >= 0 else None
            ),
            seed=evaluation_seed,
            monitor_horizon=MONITOR_HORIZON,
            deployment_steps=DEPLOYMENT_STEPS,
        )
        rows.append(
            CleanResidentRow(
                learner_seed=learner_seed,
                evaluation_seed=evaluation_seed,
                mechanism=f"{args.snapshot}_resident_predictive_simplex",
                selected_index=int(source_row["selected_index"]),
                admitted_index=int(source_row["admitted_index"]),
                init_x=float(state[0]),
                init_x_dot=float(state[1]),
                init_theta=float(state[2]),
                init_theta_dot=float(state[3]),
                poison_initially_accepted=initially_accepted,
                snapshot_initially_accepted=(
                    source_row["snapshot_initially_accepted"] == "True"
                ),
                clean_casadi_full_first_violation_step=clean_full_first,
                physical_first_violation_step=(
                    rollout.physical_first_violation_step
                    if rollout.physical_first_violation_step is not None
                    else -1
                ),
                forward_switch_step=(
                    rollout.forward_switch_step
                    if rollout.forward_switch_step is not None
                    else -1
                ),
                baseline_control_steps=rollout.baseline_control_steps,
                mean_reward=rollout.mean_reward,
                paired_clean_release_violation_step=optional_step(
                    source_row["physical_first_violation_step"]
                ),
            )
        )
        print(
            f"[{index}/{len(source)}] seed {learner_seed} idx "
            f"{source_row['selected_index']}: "
            f"violation={rows[-1].physical_first_violation_step} "
            f"switch={rows[-1].forward_switch_step} "
            f"(paired clean release={rows[-1].paired_clean_release_violation_step})",
            flush=True,
        )

    write_csv(args.output, rows)

    release_failures = sum(
        1 for row in rows if row.paired_clean_release_violation_step >= 0
    )
    resident_failures = sum(
        1 for row in rows if row.physical_first_violation_step >= 0
    )
    switches = sum(1 for row in rows if row.forward_switch_step >= 0)
    leads = [
        row.paired_clean_release_violation_step - row.forward_switch_step
        for row in rows
        if row.paired_clean_release_violation_step >= 0 and row.forward_switch_step >= 0
    ]
    timely = sum(1 for lead in leads if lead > 0)
    summary = CleanResidentSummary(
        pairs=len(rows),
        clean_release_violations=release_failures,
        clean_resident_violations=resident_failures,
        clean_resident_forward_switches=switches,
        switches_before_paired_release_failure=timely,
        median_switch_lead_steps=(
            float(np.median(leads)) if leads else float("nan")
        ),
    )
    if args.output == OUTPUT:
        write_csv(SUMMARY, [summary])
    print(summary)


if __name__ == "__main__":
    main()
