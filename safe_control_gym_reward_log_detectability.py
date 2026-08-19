#!/usr/bin/env python3
"""Pre-registered reward-log detectability calibration and evaluation."""

from __future__ import annotations

import argparse
import csv
import hashlib
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parent
RESULTS = ROOT / "results"
V3_STEPS = RESULTS / "cartpole_v3_trajectory_influence_steps.csv"
V4_STEPS = RESULTS / "cartpole_v4_untouched_confirmation_steps.csv"
CALIBRATION = RESULTS / "cartpole_reward_detectability_calibration.csv"
OUTPUT_PREFIX = RESULTS / "cartpole_reward_detectability"
CALIBRATION_SEED = 2070
KNOWN_EVALUATION_SEEDS = (2071, 2072)
NEW_EVALUATION_SEEDS = (2100, 2101, 2102, 2103, 2104)
RECOMPUTATION_TOLERANCE = 1e-8
ENVELOPE_TOLERANCE = 1e-12


@dataclass
class CalibrationRow:
    calibration_seed: int
    clean_steps: int
    clean_batches: int
    scalar_reward_min: float
    scalar_reward_max: float
    batch_mean_center: float
    batch_mean_radius: float
    recomputation_tolerance: float
    positive_reward_threshold: float
    envelope_tolerance: float
    source_sha256: str


@dataclass
class DetectionMetric:
    scope: str
    detector: str
    level: str
    clean_units: int
    poison_units: int
    false_positives: int
    true_positives: int
    false_positive_rate: float
    true_positive_rate: float


@dataclass
class DetectabilityDecision:
    evaluation_seeds: int
    evaluation_seed_values: str
    calibration_seed_excluded: bool
    frozen_calibration_loaded: bool
    trusted_recomputation_batch_tpr: float
    trusted_recomputation_batch_fpr: float
    known_sign_batch_tpr: float
    known_sign_batch_fpr: float
    scalar_envelope_batch_tpr: float
    scalar_envelope_batch_fpr: float
    batch_mean_envelope_tpr: float
    batch_mean_envelope_fpr: float
    log_only_stealthy: bool
    simple_log_detector_reaches_80pct: bool
    negative_realism_boundary: bool


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


def source_digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def calibrate() -> CalibrationRow:
    rows = [
        row
        for row in read_rows(V3_STEPS)
        if int(row["learner_seed"]) == CALIBRATION_SEED
        and row["mechanism"] == "clean"
    ]
    if len(rows) != 96:
        raise RuntimeError(f"expected 96 clean calibration steps, got {len(rows)}")
    rewards = np.asarray([float(row["logged_reward"]) for row in rows])
    batch_means = np.asarray(
        [
            np.mean(
                [
                    float(row["logged_reward"])
                    for row in rows
                    if int(row["batch"]) == batch
                ]
            )
            for batch in range(12)
        ]
    )
    center = float(np.mean(batch_means))
    calibration = CalibrationRow(
        calibration_seed=CALIBRATION_SEED,
        clean_steps=len(rows),
        clean_batches=len(batch_means),
        scalar_reward_min=float(np.min(rewards)),
        scalar_reward_max=float(np.max(rewards)),
        batch_mean_center=center,
        batch_mean_radius=float(np.max(np.abs(batch_means - center))),
        recomputation_tolerance=RECOMPUTATION_TOLERANCE,
        positive_reward_threshold=0.0,
        envelope_tolerance=ENVELOPE_TOLERANCE,
        source_sha256=source_digest(V3_STEPS),
    )
    write_csv(CALIBRATION, [calibration])
    return calibration


def load_calibration() -> CalibrationRow:
    rows = read_rows(CALIBRATION)
    if len(rows) != 1:
        raise RuntimeError("expected one frozen detectability calibration row")
    row = rows[0]
    if int(row["calibration_seed"]) != CALIBRATION_SEED:
        raise RuntimeError("calibration seed is not the locked seed")
    return CalibrationRow(
        calibration_seed=int(row["calibration_seed"]),
        clean_steps=int(row["clean_steps"]),
        clean_batches=int(row["clean_batches"]),
        scalar_reward_min=float(row["scalar_reward_min"]),
        scalar_reward_max=float(row["scalar_reward_max"]),
        batch_mean_center=float(row["batch_mean_center"]),
        batch_mean_radius=float(row["batch_mean_radius"]),
        recomputation_tolerance=float(row["recomputation_tolerance"]),
        positive_reward_threshold=float(row["positive_reward_threshold"]),
        envelope_tolerance=float(row["envelope_tolerance"]),
        source_sha256=row["source_sha256"],
    )


def load_evaluation_rows(known_only: bool) -> tuple[list[dict[str, str]], tuple[int, ...]]:
    rows = read_rows(V3_STEPS)
    seeds = KNOWN_EVALUATION_SEEDS
    if not known_only:
        if not V4_STEPS.is_file():
            raise RuntimeError("V4 step trace is required for the frozen final evaluation")
        rows.extend(read_rows(V4_STEPS))
        seeds += NEW_EVALUATION_SEEDS
    selected = [row for row in rows if int(row["learner_seed"]) in seeds]
    expected = len(seeds) * 2 * 12 * 8
    if len(selected) != expected:
        raise RuntimeError(f"expected {expected} evaluation steps, got {len(selected)}")
    return selected, seeds


def step_flag(detector: str, row: dict[str, str], calibration: CalibrationRow) -> bool:
    logged = float(row["logged_reward"])
    true = float(row["true_reward"])
    if detector == "trusted_recomputation":
        return abs(logged - true) > calibration.recomputation_tolerance
    if detector == "known_sign":
        return logged > calibration.positive_reward_threshold
    if detector == "scalar_envelope":
        return bool(
            logged < calibration.scalar_reward_min - calibration.envelope_tolerance
            or logged > calibration.scalar_reward_max + calibration.envelope_tolerance
        )
    raise ValueError(detector)


def metrics_for_detector(
    detector: str,
    rows: list[dict[str, str]],
    calibration: CalibrationRow,
    scope: str,
) -> list[DetectionMetric]:
    clean = [row for row in rows if row["mechanism"] == "clean"]
    poison = [row for row in rows if row["mechanism"] == "fixed_target_tanh"]
    step_clean_flags = [step_flag(detector, row, calibration) for row in clean]
    step_poison_flags = [step_flag(detector, row, calibration) for row in poison]

    def batch_flags(batch_rows: list[dict[str, str]]) -> list[bool]:
        keys = sorted({(int(row["learner_seed"]), int(row["batch"])) for row in batch_rows})
        return [
            any(
                step_flag(detector, row, calibration)
                for row in batch_rows
                if (int(row["learner_seed"]), int(row["batch"])) == key
            )
            for key in keys
        ]

    batch_clean_flags = batch_flags(clean)
    batch_poison_flags = batch_flags(poison)
    return [
        DetectionMetric(
            scope=scope,
            detector=detector,
            level="step",
            clean_units=len(step_clean_flags),
            poison_units=len(step_poison_flags),
            false_positives=sum(step_clean_flags),
            true_positives=sum(step_poison_flags),
            false_positive_rate=float(np.mean(step_clean_flags)),
            true_positive_rate=float(np.mean(step_poison_flags)),
        ),
        DetectionMetric(
            scope=scope,
            detector=detector,
            level="batch",
            clean_units=len(batch_clean_flags),
            poison_units=len(batch_poison_flags),
            false_positives=sum(batch_clean_flags),
            true_positives=sum(batch_poison_flags),
            false_positive_rate=float(np.mean(batch_clean_flags)),
            true_positive_rate=float(np.mean(batch_poison_flags)),
        ),
    ]


def batch_mean_metric(
    rows: list[dict[str, str]], calibration: CalibrationRow, scope: str
) -> DetectionMetric:
    def flags(mechanism: str) -> list[bool]:
        subset = [row for row in rows if row["mechanism"] == mechanism]
        keys = sorted({(int(row["learner_seed"]), int(row["batch"])) for row in subset})
        output: list[bool] = []
        for key in keys:
            mean = float(
                np.mean(
                    [
                        float(row["logged_reward"])
                        for row in subset
                        if (int(row["learner_seed"]), int(row["batch"])) == key
                    ]
                )
            )
            output.append(
                abs(mean - calibration.batch_mean_center)
                > calibration.batch_mean_radius + calibration.envelope_tolerance
            )
        return output

    clean_flags = flags("clean")
    poison_flags = flags("fixed_target_tanh")
    return DetectionMetric(
        scope=scope,
        detector="batch_mean_envelope",
        level="batch",
        clean_units=len(clean_flags),
        poison_units=len(poison_flags),
        false_positives=sum(clean_flags),
        true_positives=sum(poison_flags),
        false_positive_rate=float(np.mean(clean_flags)),
        true_positive_rate=float(np.mean(poison_flags)),
    )


def evaluate(known_only: bool) -> DetectabilityDecision:
    calibration = load_calibration()
    rows, seeds = load_evaluation_rows(known_only)
    metrics: list[DetectionMetric] = []
    for seed in seeds:
        seed_rows = [row for row in rows if int(row["learner_seed"]) == seed]
        for detector in ("trusted_recomputation", "known_sign", "scalar_envelope"):
            metrics.extend(metrics_for_detector(detector, seed_rows, calibration, str(seed)))
        metrics.append(batch_mean_metric(seed_rows, calibration, str(seed)))
    for detector in ("trusted_recomputation", "known_sign", "scalar_envelope"):
        metrics.extend(metrics_for_detector(detector, rows, calibration, "pooled"))
    metrics.append(batch_mean_metric(rows, calibration, "pooled"))

    pooled_batch = {
        row.detector: row
        for row in metrics
        if row.scope == "pooled" and row.level == "batch"
    }
    trusted = pooled_batch["trusted_recomputation"]
    sign = pooled_batch["known_sign"]
    scalar = pooled_batch["scalar_envelope"]
    batch_mean = pooled_batch["batch_mean_envelope"]
    stealthy = bool(
        sign.true_positive_rate < 0.5
        and sign.false_positive_rate <= 0.05
        and scalar.true_positive_rate < 0.5
        and scalar.false_positive_rate <= 0.05
    )
    log_only = (sign, scalar, batch_mean)
    simple_reaches = any(
        row.true_positive_rate >= 0.8 and row.false_positive_rate <= 0.05
        for row in log_only
    )
    decision = DetectabilityDecision(
        evaluation_seeds=len(seeds),
        evaluation_seed_values=";".join(str(seed) for seed in seeds),
        calibration_seed_excluded=CALIBRATION_SEED not in seeds,
        frozen_calibration_loaded=True,
        trusted_recomputation_batch_tpr=trusted.true_positive_rate,
        trusted_recomputation_batch_fpr=trusted.false_positive_rate,
        known_sign_batch_tpr=sign.true_positive_rate,
        known_sign_batch_fpr=sign.false_positive_rate,
        scalar_envelope_batch_tpr=scalar.true_positive_rate,
        scalar_envelope_batch_fpr=scalar.false_positive_rate,
        batch_mean_envelope_tpr=batch_mean.true_positive_rate,
        batch_mean_envelope_fpr=batch_mean.false_positive_rate,
        log_only_stealthy=stealthy,
        simple_log_detector_reaches_80pct=simple_reaches,
        negative_realism_boundary=simple_reaches,
    )
    suffix = "known_v3" if known_only else "final"
    write_csv(Path(f"{OUTPUT_PREFIX}_{suffix}_metrics.csv"), metrics)
    write_csv(Path(f"{OUTPUT_PREFIX}_{suffix}_decision.csv"), [decision])
    return decision


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    actions = parser.add_mutually_exclusive_group(required=True)
    actions.add_argument("--calibrate", action="store_true")
    actions.add_argument("--evaluate", action="store_true")
    parser.add_argument(
        "--known-only",
        action="store_true",
        help="evaluate only the already known V3 seeds 2071--2072",
    )
    return parser.parse_args()


def main() -> None:
    options = parse_args()
    if options.calibrate:
        if options.known_only:
            raise ValueError("--known-only is only valid with --evaluate")
        print(calibrate())
    else:
        print(evaluate(options.known_only))


if __name__ == "__main__":
    main()
