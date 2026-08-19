#!/usr/bin/env python3
"""Reproduce the retirement-state disagreement marker statistics.

The manuscript reports an AUC for clean at-retirement raw-policy/shield
disagreement as a marker of attack susceptibility, together with the low/high
band counts and a leave-one-family-out check.  Until now no script in the
artifact computed any of it: the numbers existed only as prose.  This script
supplies the missing code path so every reported figure is reproducible.

Definitions follow the manuscript:

* A paired run is *positive* when the poisoned at-retirement violation fraction
  exceeds its clean pair by at least 0.15.  (The protocol's second clause, a
  paired exact McNemar with p < 0.01, never binds at this episode count; see
  the case-study section.)
* The disagreement bands are low < 0.06 and high >= 0.09, fixed after analysis
  of 46 of the corpus rows.  The band edges are therefore in-sample.
* The corpus is the obstacle domain rows that carry disagreement
  instrumentation (``at_ret_disagree`` present on both members of a pair).

Reported quantities: band cross-tabulation, ROC AUC with a Hanley--McNeil
logit interval, Spearman correlations, and leave-one-family-out accuracy of
the low-band rule.

Usage:
    python3 carr_victim_experiment/analyze_disagreement_marker.py
"""

from __future__ import annotations

import argparse
import collections
import csv
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parent
AGGREGATE = ROOT / "results" / "aggregate_table_v2.csv"
OUT = ROOT / "results" / "disagreement_marker.csv"

POSITIVE_DELTA = 0.15
LOW_BAND = 0.06
HIGH_BAND = 0.09


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return [row for row in csv.DictReader(handle) if not row["flag"]]


def number(value: str) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def build_corpus(rows: list[dict[str, str]]) -> list[dict[str, object]]:
    """Pair clean and poisoned records that carry disagreement instrumentation."""
    groups: dict[tuple, dict[str, list[dict[str, str]]]] = collections.defaultdict(
        lambda: collections.defaultdict(list)
    )
    for row in rows:
        if row["env"] != "obstacle":
            continue
        key = (row["method"], row["condition"], row["scope"], row["version"], row["seed"])
        side = "clean" if row["poison"] == "clean" else row["poison"]
        groups[key][side].append(row)

    corpus: list[dict[str, object]] = []
    for key, sides in groups.items():
        if "clean" not in sides:
            continue
        clean = sides["clean"][0]
        clean_rate = number(clean["at_ret_frac"])
        clean_disagree = number(clean["at_ret_disagree"])
        if clean_rate is None or clean_disagree is None:
            continue
        for shape, entries in sides.items():
            if shape == "clean":
                continue
            for entry in entries:
                poisoned_rate = number(entry["at_ret_frac"])
                if poisoned_rate is None:
                    continue
                delta = poisoned_rate - clean_rate
                corpus.append(
                    {
                        "method": key[0],
                        "scope": key[2],
                        "version": key[3],
                        "run_index": key[4],
                        "shape": shape,
                        "clean_at_ret": clean_rate,
                        "poisoned_at_ret": poisoned_rate,
                        "delta": delta,
                        "clean_disagreement": clean_disagree,
                        "positive": delta >= POSITIVE_DELTA,
                        "band": "low"
                        if clean_disagree < LOW_BAND
                        else ("high" if clean_disagree >= HIGH_BAND else "middle"),
                    }
                )
    return corpus


def roc_auc(scores_pos: list[float], scores_neg: list[float]) -> float:
    """AUC via the Mann--Whitney U identity, with ties counted as one half."""
    if not scores_pos or not scores_neg:
        return float("nan")
    wins = 0.0
    for a in scores_pos:
        for b in scores_neg:
            if a < b:
                wins += 1.0
            elif a == b:
                wins += 0.5
    return wins / (len(scores_pos) * len(scores_neg))


def hanley_mcneil_interval(auc: float, n_pos: int, n_neg: int) -> tuple[float, float]:
    """Logit-transformed Hanley--McNeil interval (avoids overshooting 1.0)."""
    if not (0.0 < auc < 1.0) or n_pos == 0 or n_neg == 0:
        return float("nan"), float("nan")
    q1 = auc / (2.0 - auc)
    q2 = 2.0 * auc * auc / (1.0 + auc)
    var = (
        auc * (1.0 - auc)
        + (n_pos - 1) * (q1 - auc * auc)
        + (n_neg - 1) * (q2 - auc * auc)
    ) / (n_pos * n_neg)
    se = math.sqrt(max(var, 0.0))
    logit = math.log(auc / (1.0 - auc))
    se_logit = se / (auc * (1.0 - auc))
    lo = logit - 1.959963985 * se_logit
    hi = logit + 1.959963985 * se_logit
    return 1.0 / (1.0 + math.exp(-lo)), 1.0 / (1.0 + math.exp(-hi))


def spearman(xs: list[float], ys: list[float]) -> float:
    def rank(values: list[float]) -> list[float]:
        order = sorted(range(len(values)), key=lambda i: values[i])
        ranks = [0.0] * len(values)
        i = 0
        while i < len(order):
            j = i
            while j + 1 < len(order) and values[order[j + 1]] == values[order[i]]:
                j += 1
            shared = (i + j) / 2.0 + 1.0
            for k in range(i, j + 1):
                ranks[order[k]] = shared
            i = j + 1
        return ranks

    rx, ry = rank(xs), rank(ys)
    n = len(xs)
    mx, my = sum(rx) / n, sum(ry) / n
    num = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    den = math.sqrt(sum((a - mx) ** 2 for a in rx) * sum((b - my) ** 2 for b in ry))
    return num / den if den else float("nan")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--aggregate", type=Path, default=AGGREGATE)
    args = parser.parse_args()

    corpus = build_corpus(read_rows(args.aggregate))
    corpus.sort(key=lambda row: (row["method"], row["run_index"], row["scope"]))

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(corpus[0].keys()))
        writer.writeheader()
        writer.writerows(corpus)

    positives = [row for row in corpus if row["positive"]]
    negatives = [row for row in corpus if not row["positive"]]
    print(f"corpus rows: {len(corpus)}  positive: {len(positives)}  non-positive: {len(negatives)}")

    bands = collections.Counter((row["band"], row["positive"]) for row in corpus)
    print("\nband cross-tabulation (band, positive) -> count")
    for band in ("low", "middle", "high"):
        for flag in (True, False):
            print(f"  {band:<7} positive={str(flag):<5} {bands[(band, flag)]}")

    if positives:
        print(f"\nmax clean disagreement among positives: "
              f"{max(row['clean_disagreement'] for row in positives):.3f}")
        print(f"max clean disagreement among non-positives: "
              f"{max(row['clean_disagreement'] for row in negatives):.3f}")

    auc = roc_auc(
        [row["clean_disagreement"] for row in positives],
        [row["clean_disagreement"] for row in negatives],
    )
    lo, hi = hanley_mcneil_interval(auc, len(positives), len(negatives))
    print(f"\nAUC (low disagreement predicts positive) = {auc:.4f}")
    print(f"  Hanley--McNeil logit 95% CI = [{lo:.3f}, {hi:.3f}]  "
          f"(n_pos={len(positives)}, n_neg={len(negatives)})")

    rho_head = spearman(
        [row["clean_disagreement"] for row in corpus],
        [row["clean_at_ret"] for row in corpus],
    )
    rho_delta = spearman(
        [row["clean_disagreement"] for row in corpus],
        [row["delta"] for row in corpus],
    )
    print(f"\nSpearman(clean disagreement, clean at-retirement violation) = {rho_head:.3f}")
    print(f"Spearman(clean disagreement, attack headroom delta)          = {rho_delta:.3f}")

    print("\nleave-one-family-out accuracy of the low-band rule "
          "(predict positive iff clean disagreement < 0.06)")
    for family in sorted({row["method"] for row in corpus}):
        held = [row for row in corpus if row["method"] == family]
        correct = sum((row["band"] == "low") == row["positive"] for row in held)
        print(f"  {family:<10} {correct}/{len(held)}")

    print(f"\nwrote {OUT}")


if __name__ == "__main__":
    main()
