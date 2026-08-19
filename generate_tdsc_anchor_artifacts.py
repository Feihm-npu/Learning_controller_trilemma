#!/usr/bin/env python3
"""Validate P3 raw artifacts and generate the TDSC anchor table."""

from __future__ import annotations

import argparse
import csv
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Sequence

import numpy as np


ROOT = Path(__file__).resolve().parent
RESULTS = ROOT / "results"
PAPER = ROOT / "paper_latex"
STEM = "safe_control_gym_quadrotor_trusted_anchor"
CONDITIONS = (
    "high_p1",
    "high_p3",
    "high_p6",
    "high_p12",
    "standard_p1",
    "standard_p3",
    "standard_p6",
    "standard_p12",
)
MECHANISMS = ("poisoned_raw", "always_freeze", *CONDITIONS)


@dataclass(frozen=True)
class AnchorTableRow:
    quality: str
    anchor_period: int
    anchor_calls: int
    final_anchor_age: int
    z_radius: float
    theta_radius: float
    sampled_states_per_center: int
    retained_fraction_seed_2040: float
    retained_fraction_seed_2041: float
    retained_fraction_seed_2042: float
    mean_retained_fraction: float
    minimum_center_coverage: float
    physical_violations: int
    physical_rollouts: int
    source_files: str


@dataclass(frozen=True)
class AnchorRewardDelta:
    condition: str
    paired_rollouts: int
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
]:
    certificates = read_rows(RESULTS / f"{STEM}_certificates.csv")
    physical = read_rows(RESULTS / f"{STEM}_physical.csv")
    summaries = read_rows(RESULTS / f"{STEM}_summary.csv")
    references = read_rows(RESULTS / f"{STEM}_reference.csv")
    validity = read_rows(RESULTS / f"{STEM}_validity.csv")
    if len(validity) != 1 or not boolean(validity[0]["audit_valid"]):
        raise RuntimeError("trusted-anchor validity artifact is false")
    if len(references) != 3 or any(
        not boolean(row["reproduction_pass"]) for row in references
    ):
        raise RuntimeError("trusted-anchor reference reproduction failed")
    if len(certificates) != 24:
        raise RuntimeError("expected 24 learner/anchor certificate rows")
    certificate_keys = {
        (int(row["learner_seed"]), row["condition"])
        for row in certificates
    }
    expected_certificate_keys = {
        (seed, condition)
        for seed in (2040, 2041, 2042)
        for condition in CONDITIONS
    }
    if certificate_keys != expected_certificate_keys:
        raise RuntimeError("anchor certificate grid is incomplete")

    key_sets = {
        mechanism: {
            (
                int(row["learner_seed"]),
                int(row["source_seed"]),
                int(row["source_index"]),
            )
            for row in physical
            if row["mechanism"] == mechanism
        }
        for mechanism in MECHANISMS
    }
    reference_keys = key_sets[MECHANISMS[0]]
    if len(reference_keys) != 24 or any(
        keys != reference_keys for keys in key_sets.values()
    ):
        raise RuntimeError("anchor deployment keys are not paired")
    if max(
        float(row["max_action_interface_error"]) for row in physical
    ) > 1e-8:
        raise RuntimeError("anchor physical interface audit failed")

    pooled = {
        row["mechanism"]: row
        for row in summaries
        if row["learner_seed"] == "pooled"
    }
    if set(pooled) != set(MECHANISMS):
        raise RuntimeError("anchor pooled summaries are incomplete")
    for mechanism, summary in pooled.items():
        selected = [
            row for row in physical if row["mechanism"] == mechanism
        ]
        violations = sum(
            row["first_violation_step"] != "" for row in selected
        )
        if (
            int(summary["deployment_rollouts"]) != len(selected)
            or int(summary["violating_rollouts"]) != violations
            or not np.isclose(
                float(summary["mean_reward"]),
                np.mean([float(row["mean_reward"]) for row in selected]),
            )
        ):
            raise RuntimeError(
                f"anchor raw-artifact recomputation failed for {mechanism}"
            )

    for seed in (2040, 2041, 2042):
        for quality in ("high", "standard"):
            selected = sorted(
                [
                    row
                    for row in certificates
                    if int(row["learner_seed"]) == seed
                    and row["quality"] == quality
                ],
                key=lambda row: int(row["anchor_period"]),
            )
            fractions = [
                float(row["retained_update_fraction"])
                for row in selected
            ]
            centers = [
                int(row["certificate_centers_admitted"])
                for row in selected
            ]
            if any(
                current > previous + 1e-12
                for previous, current in zip(
                    fractions, fractions[1:]
                )
            ) or any(
                current > previous
                for previous, current in zip(centers, centers[1:])
            ):
                raise RuntimeError("anchor monotonicity recomputation failed")
    return certificates, physical, summaries


def table_rows(
    certificates: Sequence[dict[str, str]],
    summaries: Sequence[dict[str, str]],
) -> list[AnchorTableRow]:
    certificate_lookup = {
        (int(row["learner_seed"]), row["condition"]): row
        for row in certificates
    }
    pooled = {
        row["mechanism"]: row
        for row in summaries
        if row["learner_seed"] == "pooled"
    }
    source = (
        f"results/{STEM}_certificates.csv; "
        f"results/{STEM}_summary.csv"
    )
    output: list[AnchorTableRow] = []
    for condition in CONDITIONS:
        seed_rows = [
            certificate_lookup[(seed, condition)]
            for seed in (2040, 2041, 2042)
        ]
        fractions = [
            float(row["retained_update_fraction"])
            for row in seed_rows
        ]
        summary = pooled[condition]
        output.append(
            AnchorTableRow(
                quality=seed_rows[0]["quality"].capitalize(),
                anchor_period=int(seed_rows[0]["anchor_period"]),
                anchor_calls=int(seed_rows[0]["anchor_calls"]),
                final_anchor_age=int(seed_rows[0]["final_anchor_age"]),
                z_radius=float(seed_rows[0]["z_radius"]),
                theta_radius=float(seed_rows[0]["theta_radius"]),
                sampled_states_per_center=int(
                    seed_rows[0]["sampled_states_per_center"]
                ),
                retained_fraction_seed_2040=fractions[0],
                retained_fraction_seed_2041=fractions[1],
                retained_fraction_seed_2042=fractions[2],
                mean_retained_fraction=float(np.mean(fractions)),
                minimum_center_coverage=min(
                    float(row["certificate_center_coverage"])
                    for row in seed_rows
                ),
                physical_violations=int(summary["violating_rollouts"]),
                physical_rollouts=int(summary["deployment_rollouts"]),
                source_files=source,
            )
        )
    return output


def bootstrap_interval(
    values: np.ndarray, *, seed: int, samples: int = 10_000
) -> tuple[float, float]:
    rng = np.random.default_rng(seed)
    indices = rng.integers(
        0, len(values), size=(samples, len(values))
    )
    means = np.mean(values[indices], axis=1)
    low, high = np.percentile(means, [2.5, 97.5])
    return float(low), float(high)


def reward_deltas(
    physical: Sequence[dict[str, str]],
) -> list[AnchorRewardDelta]:
    lookup = {
        (
            int(row["learner_seed"]),
            int(row["source_seed"]),
            int(row["source_index"]),
            row["mechanism"],
        ): row
        for row in physical
    }
    keys = sorted(
        {
            (
                int(row["learner_seed"]),
                int(row["source_seed"]),
                int(row["source_index"]),
            )
            for row in physical
        }
    )
    output: list[AnchorRewardDelta] = []
    for condition in CONDITIONS:
        differences = np.asarray(
            [
                float(lookup[(*key, condition)]["mean_reward"])
                - float(lookup[(*key, "always_freeze")]["mean_reward"])
                for key in keys
            ]
        )
        low, high = bootstrap_interval(
            differences,
            seed=82026
            + sum(ord(character) for character in condition),
        )
        output.append(
            AnchorRewardDelta(
                condition=condition,
                paired_rollouts=len(differences),
                mean_reward_delta_vs_freeze=float(
                    np.mean(differences)
                ),
                delta_ci95_low=low,
                delta_ci95_high=high,
                better_than_freeze=int(np.sum(differences > 1e-12)),
                tied_with_freeze=int(
                    np.sum(np.abs(differences) <= 1e-12)
                ),
                worse_than_freeze=int(
                    np.sum(differences < -1e-12)
                ),
                source_file=f"results/{STEM}_physical.csv",
            )
        )
    return output


def anchor_tex(rows: Sequence[AnchorTableRow]) -> str:
    output = [
        "% Auto-generated by generate_tdsc_anchor_artifacts.py; do not edit.",
        r"\begin{tabular}{lrrrrrrr}",
        r"\toprule",
        (
            r"Quality & $P$ & Calls & Age & Radius $(z,\theta)$ "
            r"& Samples & Retained 2040/41/42 & Viol. \\"
        ),
        r"\midrule",
    ]
    previous_quality: str | None = None
    for row in rows:
        if (
            previous_quality is not None
            and row.quality != previous_quality
        ):
            output.append(r"\midrule")
        output.append(
            f"{row.quality} & {row.anchor_period} & {row.anchor_calls} & "
            f"{row.final_anchor_age} & "
            f"$({row.z_radius:.3f},{row.theta_radius:.4f})$ & "
            f"{row.sampled_states_per_center} & "
            f"{row.retained_fraction_seed_2040:.2f}/"
            f"{row.retained_fraction_seed_2041:.2f}/"
            f"{row.retained_fraction_seed_2042:.2f} & "
            f"{row.physical_violations}/{row.physical_rollouts} \\\\"
        )
        previous_quality = row.quality
    output.extend([r"\bottomrule", r"\end{tabular}"])
    return "\n".join(output) + "\n"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--tex-out",
        type=Path,
        default=PAPER / "generated" / "tdsc_anchor_results.tex",
    )
    parser.add_argument(
        "--csv-out",
        type=Path,
        default=RESULTS / "tdsc_anchor_results.csv",
    )
    parser.add_argument(
        "--reward-delta-out",
        type=Path,
        default=RESULTS / "tdsc_anchor_paired_reward_deltas.csv",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    certificates, physical, summaries = validate_and_load()
    rows = table_rows(certificates, summaries)
    deltas = reward_deltas(physical)
    args.tex_out.parent.mkdir(parents=True, exist_ok=True)
    args.tex_out.write_text(anchor_tex(rows))
    write_csv(args.csv_out, rows)
    write_csv(args.reward_delta_out, deltas)
    print("raw trusted-anchor artifacts validated")
    print(f"wrote {args.tex_out}")
    print(f"wrote {args.csv_out}")
    print(f"wrote {args.reward_delta_out}")


if __name__ == "__main__":
    main()
