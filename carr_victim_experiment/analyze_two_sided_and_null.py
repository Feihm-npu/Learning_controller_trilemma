#!/usr/bin/env python3
"""Two-sided corpus accounting and a clean-versus-clean null for the Carr lifecycle.

Two questions the locked one-sided positivity rule cannot answer on its own:

1.  Does bounded reward-record poisoning shift the population mean of this
    corpus, or is the reported effect conditional on the realized retirement
    state?  We classify every paired at-retirement comparison as positive,
    protective, or unchanged at the locked +/-0.15 effect-size threshold and run
    a two-sided sign test on the paired deltas.

2.  What false-positive rate does the positivity rule carry under pure
    replication noise?  A clean run carries no poisoning under either scope
    label, so two clean records of the same configuration under different scope
    labels are independent clean replicates.  We score those clean/clean pairs
    with the same threshold.

Reads results/aggregate_table_v2.csv only; writes two CSVs and prints a summary.

Usage:
    python3 carr_victim_experiment/analyze_two_sided_and_null.py
"""

from __future__ import annotations

import argparse
import collections
import csv
import math
import statistics
from pathlib import Path

ROOT = Path(__file__).resolve().parent
AGGREGATE = ROOT / "results" / "aggregate_table_v2.csv"
TWO_SIDED_OUT = ROOT / "results" / "two_sided_accounting.csv"
NULL_OUT = ROOT / "results" / "clean_clean_null.csv"

# Locked positivity effect-size threshold (see sec6_third_party_case_study.tex).
THRESHOLD = 0.15
CEILING = 0.5


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return [row for row in csv.DictReader(handle) if not row["flag"]]


def number(value: str) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def classify(delta: float) -> str:
    if delta >= THRESHOLD:
        return "positive"
    if delta <= -THRESHOLD:
        return "protective"
    return "unchanged"


def sign_test(deltas: list[float]) -> tuple[int, int, int, float]:
    up = sum(1 for d in deltas if d > 0)
    down = sum(1 for d in deltas if d < 0)
    ties = len(deltas) - up - down
    n = up + down
    if n == 0:
        return up, down, ties, float("nan")
    tail = sum(math.comb(n, k) for k in range(min(up, down) + 1))
    return up, down, ties, min(1.0, 2 * tail / 2**n)


def two_sided_accounting(rows: list[dict[str, str]]) -> list[dict[str, object]]:
    groups: dict[tuple, dict[str, list[dict[str, str]]]] = collections.defaultdict(
        lambda: collections.defaultdict(list)
    )
    for row in rows:
        key = (row["method"], row["condition"], row["scope"], row["version"], row["seed"])
        side = "clean" if row["poison"] == "clean" else row["poison"]
        groups[key][side].append(row)

    out: list[dict[str, object]] = []
    for key, sides in groups.items():
        if "clean" not in sides:
            continue
        clean = sides["clean"][0]
        clean_at_ret = number(clean["at_ret_frac"])
        if clean_at_ret is None:
            continue
        for shape, entries in sides.items():
            if shape == "clean":
                continue
            for entry in entries:
                poisoned_at_ret = number(entry["at_ret_frac"])
                if poisoned_at_ret is None:
                    continue
                delta = poisoned_at_ret - clean_at_ret
                out.append(
                    {
                        "method": key[0],
                        "scope": key[2],
                        "version": key[3],
                        "run_index": key[4],
                        "shape": shape,
                        "clean_at_ret": clean_at_ret,
                        "poisoned_at_ret": poisoned_at_ret,
                        "delta": delta,
                        "outcome": classify(delta),
                        "stratum": "sub-ceiling" if clean_at_ret < CEILING else "ceiling",
                        "clean_disagreement": number(clean["at_ret_disagree"]),
                    }
                )
    return out


def clean_clean_null(rows: list[dict[str, str]]) -> list[dict[str, object]]:
    groups: dict[tuple, list[dict[str, str]]] = collections.defaultdict(list)
    for row in rows:
        if row["poison"] != "clean" or not row["at_ret_frac"]:
            continue
        groups[(row["method"], row["condition"], row["seed"])].append(row)

    out: list[dict[str, object]] = []
    for key, entries in groups.items():
        for i in range(len(entries)):
            for j in range(i + 1, len(entries)):
                a, b = entries[i], entries[j]
                left, right = float(a["at_ret_frac"]), float(b["at_ret_frac"])
                out.append(
                    {
                        "method": key[0],
                        "run_index": key[2],
                        "left_scope": a["scope"],
                        "left_version": a["version"],
                        "left_at_ret": left,
                        "right_scope": b["scope"],
                        "right_version": b["version"],
                        "right_at_ret": right,
                        "abs_delta": abs(right - left),
                        "same_code_version": a["version"] == b["version"],
                        "exceeds_threshold": abs(right - left) >= THRESHOLD,
                    }
                )
    return out


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    if not rows:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--aggregate", type=Path, default=AGGREGATE)
    args = parser.parse_args()

    rows = read_rows(args.aggregate)
    paired = two_sided_accounting(rows)
    contrast = [row for row in paired if row["shape"] == "contrast"]
    write_csv(TWO_SIDED_OUT, paired)

    counts = collections.Counter(row["outcome"] for row in contrast)
    up, down, ties, pvalue = sign_test([row["delta"] for row in contrast])
    print(f"contrast at-retirement comparisons: {len(contrast)}")
    print(f"  positive {counts['positive']}  protective {counts['protective']}  "
          f"unchanged {counts['unchanged']}")
    print(f"  two-sided sign test: up={up} down={down} ties={ties} p={pvalue:.4f}")
    for method in ("REINFORCE", "PPO", "SAC"):
        subset = [row for row in contrast if row["method"] == method]
        if not subset:
            continue
        print(
            f"  {method:<10} n={len(subset):>2} "
            f"mean delta {statistics.mean(row['delta'] for row in subset):+.3f} "
            f"{dict(collections.Counter(row['outcome'] for row in subset))}"
        )
    for stratum in ("sub-ceiling", "ceiling"):
        subset = [row for row in contrast if row["stratum"] == stratum]
        print(
            f"  {stratum:<12} n={len(subset):>2} "
            f"{dict(collections.Counter(row['outcome'] for row in subset))}"
        )

    null = clean_clean_null(rows)
    write_csv(NULL_OUT, null)
    same = [row for row in null if row["same_code_version"]]
    cross = [row for row in null if not row["same_code_version"]]
    print(f"\nclean-versus-clean replicate pairs: {len(null)}")
    for name, subset in (("same code version", same), ("cross code version", cross)):
        exceed = [row for row in subset if row["exceeds_threshold"]]
        median = statistics.median(row["abs_delta"] for row in subset) if subset else float("nan")
        largest = max((row["abs_delta"] for row in subset), default=float("nan"))
        print(
            f"  {name:<19} n={len(subset):>2}  "
            f"|delta|>={THRESHOLD}: {len(exceed)}  "
            f"median |delta| {median:.3f}  max |delta| {largest:.3f}"
        )
    print(f"\nwrote {TWO_SIDED_OUT}\nwrote {NULL_OUT}")


if __name__ == "__main__":
    main()
