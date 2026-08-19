#!/usr/bin/env python3
"""Validate P2 raw artifacts and generate TDSC frontier tables and figure."""

from __future__ import annotations

import argparse
import csv
import os
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Sequence

os.environ.setdefault("MPLCONFIGDIR", "/tmp/matplotlib-codex")

import matplotlib

# Embed TrueType rather than Type 3 so figure text stays selectable in the
# submission PDF (same convention as carr_victim_experiment/make_fig6.py).
matplotlib.rcParams["pdf.fonttype"] = 42
matplotlib.rcParams["ps.fonttype"] = 42

import matplotlib.pyplot as plt
import numpy as np


ROOT = Path(__file__).resolve().parent
RESULTS = ROOT / "results"
PAPER = ROOT / "paper_latex"
STEM = "safe_control_gym_quadrotor_security_availability_frontier"
MECHANISMS = (
    "clean_reinforce_snapshot",
    "poisoned_action_only_snapshot",
    "poisoned_commit_gate_snapshot",
    "poisoned_always_freeze_snapshot",
    "poisoned_permanent_filter_snapshot",
    "official_linear_mpsc",
)
DISPLAY = {
    "clean_reinforce_snapshot": "Clean REINFORCE",
    "poisoned_action_only_snapshot": "Poisoned raw",
    "poisoned_commit_gate_snapshot": "Poisoned commit",
    "poisoned_always_freeze_snapshot": "Always-freeze",
    "poisoned_permanent_filter_snapshot": "Permanent shield",
    "official_linear_mpsc": "Official MPSC",
}


@dataclass(frozen=True)
class FrontierTableRow:
    mechanism: str
    rollouts: int
    violations: int
    violation_ci95_low: float
    violation_ci95_high: float
    completed_rollouts: int
    mean_reward: float
    reward_ci95_low: float
    reward_ci95_high: float
    intervention_rate: float
    median_latency_ms: float
    p95_latency_ms: float
    source_file: str


@dataclass(frozen=True)
class AdmissionTableRow:
    learner_seed: int
    common_admitted: int
    candidate_states: int
    common_admission_fraction: float
    commit_fraction: float
    offline_commit_latency_seconds: float
    source_files: str


@dataclass(frozen=True)
class PairedRewardDelta:
    learner_seed: str
    mechanism: str
    paired_rollouts: int
    all_completed: bool
    mean_reward_delta_vs_freeze: float
    delta_ci95_low: float
    delta_ci95_high: float
    better_than_freeze: int
    tied_with_freeze: int
    worse_than_freeze: int
    source_file: str


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as source:
        return list(csv.DictReader(source))


def write_csv(path: Path, rows: Sequence[object]) -> None:
    dictionaries = [asdict(row) for row in rows]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=list(dictionaries[0]))
        writer.writeheader()
        writer.writerows(dictionaries)


def boolean(value: str) -> bool:
    return value.lower() == "true"


def validate_and_load() -> tuple[
    list[dict[str, str]],
    list[dict[str, str]],
    list[dict[str, str]],
    list[dict[str, str]],
    list[dict[str, str]],
]:
    paths = {
        suffix: RESULTS / f"{STEM}_{suffix}.csv"
        for suffix in (
            "admission",
            "admission_summary",
            "offline_commit_timing",
            "steps",
            "rollouts",
            "summary",
            "validity",
        )
    }
    data = {name: read_rows(path) for name, path in paths.items()}
    validity = data["validity"]
    if len(validity) != 1 or not boolean(validity[0]["audit_valid"]):
        raise RuntimeError("frontier validity artifact is absent or false")
    if float(validity[0]["max_action_interface_error"]) > float(
        validity[0]["interface_tolerance"]
    ):
        raise RuntimeError("frontier action-interface audit failed")

    admissions = data["admission"]
    admission_summaries = data["admission_summary"]
    offline = data["offline_commit_timing"]
    rollouts = data["rollouts"]
    steps = data["steps"]
    summaries = data["summary"]
    learner_seeds = sorted(
        {int(row["learner_seed"]) for row in rollouts}
    )
    if len(learner_seeds) != 3:
        raise RuntimeError("expected three learner seeds")
    if any(not boolean(row["reproduction_pass"]) for row in offline):
        raise RuntimeError("a locked commit snapshot was not reproduced")
    if any(int(row["selected_states"]) != 8 for row in admission_summaries):
        raise RuntimeError("expected eight selected states per learner seed")

    key_sets = {
        mechanism: {
            (
                int(row["learner_seed"]),
                int(row["source_seed"]),
                int(row["source_index"]),
            )
            for row in rollouts
            if row["mechanism"] == mechanism
        }
        for mechanism in MECHANISMS
    }
    reference = key_sets[MECHANISMS[0]]
    if len(reference) != 24 or any(
        keys != reference for keys in key_sets.values()
    ):
        raise RuntimeError("paired rollout keys do not match")
    selected_keys = {
        (
            int(row["learner_seed"]),
            int(row["source_seed"]),
            int(row["source_index"]),
        )
        for row in admissions
        if boolean(row["selected_for_deployment"])
    }
    if selected_keys != reference:
        raise RuntimeError(
            "deployed keys do not match certificate-selected keys"
        )

    rollout_lookup = {
        (
            int(row["learner_seed"]),
            row["mechanism"],
            int(row["source_seed"]),
            int(row["source_index"]),
        ): row
        for row in rollouts
    }
    if len(rollout_lookup) != len(rollouts):
        raise RuntimeError("duplicate frontier rollout key")
    step_counts: dict[tuple[int, str, int, int], int] = {}
    for row in steps:
        key = (
            int(row["learner_seed"]),
            row["mechanism"],
            int(row["source_seed"]),
            int(row["source_index"]),
        )
        step_counts[key] = step_counts.get(key, 0) + 1
    for key, row in rollout_lookup.items():
        if step_counts.get(key) != int(row["steps_executed"]):
            raise RuntimeError(f"step/rollout count mismatch for {key}")

    pooled = {
        row["mechanism"]: row
        for row in summaries
        if row["learner_seed"] == "pooled"
    }
    if set(pooled) != set(MECHANISMS):
        raise RuntimeError("pooled summary is incomplete")
    for mechanism, summary in pooled.items():
        selected_rollouts = [
            row for row in rollouts if row["mechanism"] == mechanism
        ]
        selected_steps = [
            row for row in steps if row["mechanism"] == mechanism
        ]
        violations = sum(
            row["first_violation_step"] != ""
            for row in selected_rollouts
        )
        checks = (
            int(summary["deployment_rollouts"]) == len(selected_rollouts),
            int(summary["violating_rollouts"]) == violations,
            int(summary["executed_steps"]) == len(selected_steps),
            int(summary["interventions"])
            == sum(boolean(row["intervened"]) for row in selected_steps),
            np.isclose(
                float(summary["mean_reward"]),
                np.mean(
                    [
                        float(row["mean_reward"])
                        for row in selected_rollouts
                    ]
                ),
            ),
            np.isclose(
                float(summary["mean_controller_latency_ms"]),
                np.mean(
                    [
                        float(row["controller_latency_ms"])
                        for row in selected_steps
                    ]
                ),
            ),
        )
        if not all(checks):
            raise RuntimeError(
                f"raw-artifact recomputation failed for {mechanism}"
            )
    return (
        summaries,
        rollouts,
        admission_summaries,
        offline,
        steps,
    )


def frontier_table_rows(
    summaries: Sequence[dict[str, str]],
) -> list[FrontierTableRow]:
    pooled = {
        row["mechanism"]: row
        for row in summaries
        if row["learner_seed"] == "pooled"
    }
    source = f"results/{STEM}_summary.csv"
    return [
        FrontierTableRow(
            mechanism=DISPLAY[mechanism],
            rollouts=int(pooled[mechanism]["deployment_rollouts"]),
            violations=int(pooled[mechanism]["violating_rollouts"]),
            violation_ci95_low=float(
                pooled[mechanism]["violation_rate_ci95_low"]
            ),
            violation_ci95_high=float(
                pooled[mechanism]["violation_rate_ci95_high"]
            ),
            completed_rollouts=int(
                pooled[mechanism]["completed_rollouts"]
            ),
            mean_reward=float(pooled[mechanism]["mean_reward"]),
            reward_ci95_low=float(
                pooled[mechanism]["mean_reward_ci95_low"]
            ),
            reward_ci95_high=float(
                pooled[mechanism]["mean_reward_ci95_high"]
            ),
            intervention_rate=float(
                pooled[mechanism]["intervention_rate"]
            ),
            median_latency_ms=float(
                pooled[mechanism]["median_controller_latency_ms"]
            ),
            p95_latency_ms=float(
                pooled[mechanism]["p95_controller_latency_ms"]
            ),
            source_file=source,
        )
        for mechanism in MECHANISMS
    ]


def admission_table_rows(
    admissions: Sequence[dict[str, str]],
    offline: Sequence[dict[str, str]],
) -> list[AdmissionTableRow]:
    timings = {int(row["learner_seed"]): row for row in offline}
    source = (
        f"results/{STEM}_admission_summary.csv; "
        f"results/{STEM}_offline_commit_timing.csv"
    )
    return [
        AdmissionTableRow(
            learner_seed=int(row["learner_seed"]),
            common_admitted=int(row["common_admitted"]),
            candidate_states=int(row["candidate_states"]),
            common_admission_fraction=float(
                row["common_admission_fraction"]
            ),
            commit_fraction=float(
                timings[int(row["learner_seed"])][
                    "recomputed_commit_fraction"
                ]
            ),
            offline_commit_latency_seconds=float(
                timings[int(row["learner_seed"])][
                    "offline_commit_latency_seconds"
                ]
            ),
            source_files=source,
        )
        for row in admissions
    ]


def bootstrap_interval(
    values: np.ndarray, *, seed: int, samples: int = 10_000
) -> tuple[float, float]:
    if len(values) == 1:
        return float(values[0]), float(values[0])
    rng = np.random.default_rng(seed)
    indices = rng.integers(
        0, len(values), size=(samples, len(values))
    )
    means = np.mean(values[indices], axis=1)
    low, high = np.percentile(means, [2.5, 97.5])
    return float(low), float(high)


def paired_reward_deltas(
    rollouts: Sequence[dict[str, str]],
) -> list[PairedRewardDelta]:
    lookup = {
        (
            int(row["learner_seed"]),
            int(row["source_seed"]),
            int(row["source_index"]),
            row["mechanism"],
        ): row
        for row in rollouts
    }
    seeds = sorted({int(row["learner_seed"]) for row in rollouts})
    mechanisms = (
        "clean_reinforce_snapshot",
        "poisoned_commit_gate_snapshot",
        "poisoned_always_freeze_snapshot",
        "poisoned_permanent_filter_snapshot",
        "official_linear_mpsc",
    )
    output: list[PairedRewardDelta] = []
    for seed_label, selected_seeds in [
        ("pooled", seeds),
        *[(str(seed), [seed]) for seed in seeds],
    ]:
        keys = sorted(
            {
                (
                    int(row["learner_seed"]),
                    int(row["source_seed"]),
                    int(row["source_index"]),
                )
                for row in rollouts
                if int(row["learner_seed"]) in selected_seeds
            }
        )
        for mechanism in mechanisms:
            differences: list[float] = []
            all_completed = True
            for learner_seed, source_seed, source_index in keys:
                mechanism_row = lookup[
                    (
                        learner_seed,
                        source_seed,
                        source_index,
                        mechanism,
                    )
                ]
                freeze_row = lookup[
                    (
                        learner_seed,
                        source_seed,
                        source_index,
                        "poisoned_always_freeze_snapshot",
                    )
                ]
                all_completed &= boolean(
                    mechanism_row["completed_horizon"]
                ) and boolean(freeze_row["completed_horizon"])
                differences.append(
                    float(mechanism_row["mean_reward"])
                    - float(freeze_row["mean_reward"])
                )
            array = np.asarray(differences, dtype=float)
            low, high = bootstrap_interval(
                array,
                seed=72026
                + sum(ord(character) for character in mechanism)
                + sum(ord(character) for character in seed_label),
            )
            tolerance = 1e-12
            output.append(
                PairedRewardDelta(
                    learner_seed=seed_label,
                    mechanism=mechanism,
                    paired_rollouts=len(array),
                    all_completed=all_completed,
                    mean_reward_delta_vs_freeze=float(np.mean(array)),
                    delta_ci95_low=low,
                    delta_ci95_high=high,
                    better_than_freeze=int(np.sum(array > tolerance)),
                    tied_with_freeze=int(
                        np.sum(np.abs(array) <= tolerance)
                    ),
                    worse_than_freeze=int(np.sum(array < -tolerance)),
                    source_file=f"results/{STEM}_rollouts.csv",
                )
            )
    return output


def frontier_tex(rows: Sequence[FrontierTableRow]) -> str:
    output = [
        "% Auto-generated by generate_tdsc_frontier_artifacts.py; do not edit.",
        r"\begin{tabular}{lrrrrr}",
        r"\toprule",
        (
            r"Mechanism & Viol./rollouts & Complete & Mean reward "
            r"& Interv. & Latency med./p95 (ms) \\"
        ),
        r"\midrule",
    ]
    for row in rows:
        reward = f"${row.mean_reward:.3f}"
        if row.mechanism == "Poisoned raw":
            reward += r"^\dagger"
        reward += "$"
        output.append(
            f"{row.mechanism} & {row.violations}/{row.rollouts} & "
            f"{row.completed_rollouts}/{row.rollouts} & {reward} & "
            f"{100.0 * row.intervention_rate:.1f}\\% & "
            f"{row.median_latency_ms:.3f}/{row.p95_latency_ms:.3f} \\\\"
        )
    output.extend([r"\bottomrule", r"\end{tabular}"])
    return "\n".join(output) + "\n"


def admission_tex(rows: Sequence[AdmissionTableRow]) -> str:
    output = [
        "% Auto-generated by generate_tdsc_frontier_artifacts.py; do not edit.",
        r"\begin{tabular}{rrrr}",
        r"\toprule",
        (
            r"Seed & Common/144 & Commit frac. & Offline (s) \\"
        ),
        r"\midrule",
    ]
    for row in rows:
        output.append(
            f"{row.learner_seed} & {row.common_admitted}/"
            f"{row.candidate_states} ({100.0 * row.common_admission_fraction:.1f}\\%) "
            f"& {row.commit_fraction:.2f} & "
            f"{row.offline_commit_latency_seconds:.2f} \\\\"
        )
    output.extend([r"\bottomrule", r"\end{tabular}"])
    return "\n".join(output) + "\n"


def plot_frontier(
    rows: Sequence[FrontierTableRow],
    output_path: Path,
) -> None:
    colors = {
        "Clean REINFORCE": "#377eb8",
        "Poisoned raw": "#e41a1c",
        "Poisoned commit": "#4daf4a",
        "Always-freeze": "#666666",
        "Permanent shield": "#984ea3",
        "Official MPSC": "#ff7f00",
    }
    markers = {
        "Clean REINFORCE": "o",
        "Poisoned raw": "X",
        "Poisoned commit": "s",
        "Always-freeze": "D",
        "Permanent shield": "^",
        "Official MPSC": "P",
    }
    fig, axes = plt.subplots(1, 2, figsize=(7.2, 3.0))
    left, right = axes
    label_positions = {
        "Clean REINFORCE": (-0.04, 0.29),
        "Always-freeze": (0.025, -0.075),
        "Poisoned commit": (-0.085, 0.09),
        "Poisoned raw": (-0.17, 0.84),
        "Permanent shield": (-0.265, 0.18),
        "Official MPSC": (-0.44, 0.10),
    }
    for row in rows:
        violation_rate = row.violations / row.rollouts
        left.errorbar(
            row.mean_reward,
            violation_rate,
            xerr=np.asarray(
                [
                    [row.mean_reward - row.reward_ci95_low],
                    [row.reward_ci95_high - row.mean_reward],
                ]
            ),
            yerr=np.asarray(
                [
                    [
                        max(
                            0.0,
                            violation_rate - row.violation_ci95_low,
                        )
                    ],
                    [
                        max(
                            0.0,
                            row.violation_ci95_high - violation_rate,
                        )
                    ],
                ]
            ),
            marker=markers[row.mechanism],
            color=colors[row.mechanism],
            markersize=6,
            capsize=2,
            linestyle="none",
        )
        left.annotate(
            row.mechanism,
            (row.mean_reward, violation_rate),
            xytext=label_positions[row.mechanism],
            textcoords="data",
            fontsize=7,
            ha="center",
            arrowprops={
                "arrowstyle": "-",
                "color": colors[row.mechanism],
                "linewidth": 0.45,
            },
        )
        if row.mechanism in {"Permanent shield", "Official MPSC"}:
            right.scatter(
                row.median_latency_ms,
                row.intervention_rate,
                marker=markers[row.mechanism],
                color=colors[row.mechanism],
                s=38,
            )
            right.annotate(
                row.mechanism,
                (row.median_latency_ms, row.intervention_rate),
                xytext=(
                    (-5, 8)
                    if row.mechanism == "Permanent shield"
                    else (5, -14)
                ),
                textcoords="offset points",
                fontsize=7,
                ha=(
                    "right"
                    if row.mechanism == "Permanent shield"
                    else "left"
                ),
            )
    raw_rows = [
        row
        for row in rows
        if row.mechanism not in {"Permanent shield", "Official MPSC"}
    ]
    raw_latency = float(
        np.exp(
            np.mean(
                np.log([row.median_latency_ms for row in raw_rows])
            )
        )
    )
    right.scatter(
        raw_latency,
        0.0,
        marker="o",
        color="#666666",
        s=38,
    )
    right.annotate(
        "Raw snapshots / commit / freeze",
        (raw_latency, 0.0),
        xytext=(6, 8),
        textcoords="offset points",
        fontsize=7,
        ha="left",
    )
    left.set_xlabel("Mean reward (higher is better)")
    left.set_ylabel("Physical violation rate")
    left.set_xlim(-0.57, 0.12)
    left.set_ylim(-0.10, 1.08)
    left.grid(alpha=0.25)
    right.set_xscale("log")
    right.set_xlabel("Median online latency (ms, log scale)")
    right.set_ylabel("Intervention rate")
    right.set_xlim(0.015, 400.0)
    right.set_ylim(-0.10, 1.08)
    right.grid(alpha=0.25, which="both")
    left.set_title("(a) Security--performance")
    right.set_title("(b) Availability--computation")
    fig.tight_layout()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, bbox_inches="tight")
    plt.close(fig)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--frontier-tex-out",
        type=Path,
        default=PAPER / "generated" / "tdsc_frontier_results.tex",
    )
    parser.add_argument(
        "--admission-tex-out",
        type=Path,
        default=PAPER / "generated" / "tdsc_frontier_admission.tex",
    )
    parser.add_argument(
        "--frontier-csv-out",
        type=Path,
        default=RESULTS / "tdsc_frontier_results.csv",
    )
    parser.add_argument(
        "--admission-csv-out",
        type=Path,
        default=RESULTS / "tdsc_frontier_admission.csv",
    )
    parser.add_argument(
        "--paired-delta-out",
        type=Path,
        default=RESULTS / "tdsc_frontier_paired_reward_deltas.csv",
    )
    parser.add_argument(
        "--figure-out",
        type=Path,
        default=(
            PAPER
            / "figures"
            / "fig4_frontier.pdf"
        ),
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    (
        summaries,
        rollouts,
        admissions,
        offline,
        _steps,
    ) = validate_and_load()
    frontier_rows = frontier_table_rows(summaries)
    admission_rows = admission_table_rows(admissions, offline)
    deltas = paired_reward_deltas(rollouts)
    args.frontier_tex_out.parent.mkdir(parents=True, exist_ok=True)
    args.frontier_tex_out.write_text(frontier_tex(frontier_rows))
    args.admission_tex_out.parent.mkdir(parents=True, exist_ok=True)
    args.admission_tex_out.write_text(admission_tex(admission_rows))
    write_csv(args.frontier_csv_out, frontier_rows)
    write_csv(args.admission_csv_out, admission_rows)
    write_csv(args.paired_delta_out, deltas)
    plot_frontier(frontier_rows, args.figure_out)
    print("raw frontier artifacts validated")
    print(f"wrote {args.frontier_tex_out}")
    print(f"wrote {args.admission_tex_out}")
    print(f"wrote {args.frontier_csv_out}")
    print(f"wrote {args.admission_csv_out}")
    print(f"wrote {args.paired_delta_out}")
    print(f"wrote {args.figure_out}")


if __name__ == "__main__":
    main()
