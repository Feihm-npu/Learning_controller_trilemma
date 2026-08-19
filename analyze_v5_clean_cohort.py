#!/usr/bin/env python3
"""Analyze the V5 adversary-free clean cohort produced by
``safe_control_gym_cartpole_v5_clean_cohort.py``.

Reads the two clean-cohort CSVs and reports:
  - per-run failure counts for both mechanisms
  - pooled clean raw-release failure rate with a Wilson 95% interval
  - pooled clean resident failure rate with a Wilson 95% interval
  - a RUN-LEVEL test that the raw-release failure rate exceeds zero: the
    fraction of runs with >= 1 failure, with a Wilson interval.  This is the
    inferentially honest unit for this cohort, because within-run pairs are
    not independent draws (they share one training run's snapshot and one
    evaluation seed's admitted-state pool); the pooled-pair rate above treats
    all pairs as exchangeable and can overstate precision.
  - the paired raw-vs-resident discordance and a two-sided exact McNemar test
    (scipy.stats.binomtest on the discordant pairs)
  - the median switch lead time (paired raw-release violation step minus
    resident switch step, over pairs where both occurred)

No external dependencies beyond numpy and scipy.

Usage:
    .venv-safe-control/bin/python analyze_v5_clean_cohort.py
    .venv-safe-control/bin/python analyze_v5_clean_cohort.py \\
        --rollouts /tmp/cartpole_v5_smoke_rollouts.csv \\
        --summary /tmp/cartpole_v5_smoke_summary.csv
"""

from __future__ import annotations

import argparse
import csv
import math
from pathlib import Path

import numpy as np
from scipy.stats import binomtest

ROOT = Path(__file__).resolve().parent
RESULTS = ROOT / "results"

RAW_RELEASE_MECHANISM = "clean_permanent_raw_release"
RESIDENT_MECHANISM = "clean_resident_predictive_authority"

Z_95 = 1.959963984540054  # scipy.stats.norm.ppf(0.975)


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def opt_int(value: str) -> int | None:
    if value in ("", "None", "nan"):
        return None
    return int(float(value))


def as_bool(value: str) -> bool:
    return value == "True"


def wilson_interval(successes: int, trials: int, z: float = Z_95) -> tuple[float, float, float]:
    """Wilson score interval. Returns (point_estimate, lower, upper)."""
    if trials == 0:
        return (float("nan"), float("nan"), float("nan"))
    phat = successes / trials
    denom = 1.0 + z * z / trials
    center = (phat + z * z / (2 * trials)) / denom
    margin = (
        z * math.sqrt(phat * (1 - phat) / trials + z * z / (4 * trials * trials))
        / denom
    )
    return (phat, max(0.0, center - margin), min(1.0, center + margin))


def fmt_rate(successes: int, trials: int) -> str:
    point, lower, upper = wilson_interval(successes, trials)
    if trials == 0:
        return "n/a (0 trials)"
    return f"{successes}/{trials} = {point:.4f}  Wilson 95% CI [{lower:.4f}, {upper:.4f}]"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--rollouts",
        type=Path,
        default=RESULTS / "cartpole_v5_clean_cohort_rollouts.csv",
    )
    parser.add_argument(
        "--summary",
        type=Path,
        default=RESULTS / "cartpole_v5_clean_cohort_summary.csv",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    rollouts = read_rows(args.rollouts)
    summary = read_rows(args.summary)

    print(f"loaded {len(rollouts)} rollout rows from {args.rollouts}")
    print(f"loaded {len(summary)} run summaries from {args.summary}")
    print()

    # ---- per-run failure counts, both mechanisms -----------------------
    print("=== per-run failure counts ===")
    print(
        f"{'learner_seed':>12}  {'eval_seed':>9}  {'accepted':>8}  "
        f"{'raw_fail':>8}  {'resident_fail':>13}  {'resident_switch':>15}"
    )
    for row in summary:
        print(
            f"{row['learner_seed']:>12}  {row['evaluation_seed']:>9}  "
            f"{row['states_accepted']:>8}  {row['raw_release_violations']:>8}  "
            f"{row['resident_violations']:>13}  {row['resident_switches']:>15}"
        )
    print()

    total_accepted = sum(int(row["states_accepted"]) for row in summary)
    total_raw_fail = sum(int(row["raw_release_violations"]) for row in summary)
    total_resident_fail = sum(int(row["resident_violations"]) for row in summary)

    print("=== pooled clean raw-release rate (over accepted state-pairs) ===")
    print(fmt_rate(total_raw_fail, total_accepted))
    print()

    print("=== pooled clean resident rate (over accepted state-pairs) ===")
    print(fmt_rate(total_resident_fail, total_accepted))
    print()

    # ---- run-level test --------------------------------------------------
    runs_with_failure = sum(
        1 for row in summary if int(row["raw_release_violations"]) >= 1
    )
    n_runs = len(summary)
    print("=== RUN-LEVEL test: fraction of runs with >= 1 raw-release failure ===")
    print(
        "(the inferentially honest unit: pairs within one run share a single "
        "training run's snapshot and are not independent draws)"
    )
    print(fmt_rate(runs_with_failure, n_runs))
    print()

    # ---- paired discordance + exact McNemar -------------------------------
    accepted_pairs: dict[tuple[str, str, str], dict[str, dict]] = {}
    for row in rollouts:
        if not as_bool(row["snapshot_initially_accepted"]):
            continue
        key = (row["learner_seed"], row["evaluation_seed"], row["selected_index"])
        accepted_pairs.setdefault(key, {})[row["mechanism"]] = row

    raw_only = 0
    resident_only = 0
    both_fail = 0
    neither_fail = 0
    leads: list[int] = []
    for key, mechanisms in accepted_pairs.items():
        raw_row = mechanisms.get(RAW_RELEASE_MECHANISM)
        resident_row = mechanisms.get(RESIDENT_MECHANISM)
        if raw_row is None or resident_row is None:
            continue
        raw_step = opt_int(raw_row["physical_first_violation_step"])
        resident_step = opt_int(resident_row["physical_first_violation_step"])
        raw_failed = raw_step is not None
        resident_failed = resident_step is not None
        if raw_failed and not resident_failed:
            raw_only += 1
        elif resident_failed and not raw_failed:
            resident_only += 1
        elif raw_failed and resident_failed:
            both_fail += 1
        else:
            neither_fail += 1
        if raw_failed:
            switch_step = opt_int(resident_row["forward_switch_step"])
            if switch_step is not None:
                leads.append(raw_step - switch_step)

    discordant = raw_only + resident_only
    print("=== paired raw-vs-resident discordance (accepted state-pairs) ===")
    print(
        f"raw_only={raw_only}  resident_only={resident_only}  "
        f"both_fail={both_fail}  neither_fail={neither_fail}  "
        f"discordant={discordant}  total_pairs={len(accepted_pairs)}"
    )
    if discordant == 0:
        mcnemar_p = 1.0
        print("exact McNemar (two-sided): p=1.0 (0 discordant pairs)")
    else:
        result = binomtest(
            min(raw_only, resident_only), discordant, p=0.5, alternative="two-sided"
        )
        mcnemar_p = result.pvalue
        print(
            f"exact McNemar (two-sided, scipy.stats.binomtest on discordant pairs): "
            f"p={mcnemar_p:.6g}"
        )
    print()

    # ---- median switch lead time ------------------------------------------
    print("=== median switch lead time (raw-release violation step minus resident switch step) ===")
    if leads:
        print(
            f"n={len(leads)}  median={float(np.median(leads)):.2f}  "
            f"mean={float(np.mean(leads)):.2f}  "
            f"min={min(leads)}  max={max(leads)}"
        )
    else:
        print("n=0 (no paired raw-release failures with a resident forward switch)")


if __name__ == "__main__":
    main()
