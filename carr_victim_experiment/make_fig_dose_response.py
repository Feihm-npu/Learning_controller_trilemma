#!/usr/bin/env python3
"""Generate fig7_dose_response (paper "Attack budget and susceptibility", sec6).

Panel (a): contrast-budget dose response on the full-phase REINFORCE protocol,
grouped by seed (vA locked version): clean / contrast delta=2 / contrast delta=10,
post-removal violation fraction (5000-eval episodes).
Panel (b): attack-shape negative controls at delta=2 (vA locked version):
clean / risk / contrast, plus bias on seed 1.

IMPORTANT (2026-08-16, B3 data-quality finding): the v1.7 dense delta grid
(server, seed 1, delta in {0.1,0.25,0.5,1.0}) is NOT plotted here: that battery
landed on multiple run-to-run trajectory modes and is not a measurable
dose-response (see RESULTS_ANALYSIS_AND_NEXT_STEPS.md addendum). Only
within-batch paired rows of the same locked code version are plotted.

All numbers come from aggregate_table_v2.csv (vA full-phase rows); no fabricated data.
"""
import csv, os
import matplotlib
matplotlib.use("Agg")
matplotlib.rcParams["pdf.fonttype"] = 42
matplotlib.rcParams["ps.fonttype"] = 42
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

BASE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results")
OUT = os.path.join(BASE, "figures")


def load_vA_rows():
    rows = []
    with open(os.path.join(BASE, "aggregate_table_v2.csv")) as f:
        for r in csv.DictReader(f):
            if (r["version"] == "vA" and r["method"] == "REINFORCE"
                    and r["scope"] == "full" and int(r["runs"]) == 5000
                    and abs(float(r["delta"]) - 0.0) < 1e-9 or True):
                rows.append(r)
    return [r for r in rows if r["version"] == "vA" and r["method"] == "REINFORCE"
            and r["scope"] == "full" and int(r["runs"]) == 5000]


def frac(rows, seed, poison, delta):
    for r in rows:
        if (int(r["seed"]) == seed and r["poison"] == poison
                and abs(float(r["delta"]) - delta) < 1e-9):
            return int(r["after"]) / int(r["runs"])
    return None


def main():
    rows = load_vA_rows()
    seeds = [1, 2, 3]
    clean = [frac(rows, s, "clean", 0.0) for s in seeds]
    d2 = [frac(rows, s, "contrast", 2.0) for s in seeds]
    d10 = [frac(rows, s, "contrast", 10.0) for s in seeds]
    risk = [frac(rows, s, "risk", 2.0) for s in seeds]
    bias = [frac(rows, 1, "bias", 2.0), None, None]

    fig, axes = plt.subplots(1, 2, figsize=(10.5, 3.6))

    # (a) contrast budget dose response, grouped by seed
    ax = axes[0]
    x = np.arange(3); w = 0.24
    for vals, lab, col, off in [
        (clean, "clean", "#1f77b4", 0.0),
        (d2, "contrast $\\delta$=2", "#d62728", w),
        (d10, "contrast $\\delta$=10", "#9467bd", 2 * w),
    ]:
        xs_plot = [xi for xi, v in zip(x, vals) if v is not None]
        yv = [vals[xi] for xi in xs_plot]
        ax.bar([xi + off - w for xi in xs_plot], yv, w, label=lab, color=col, alpha=0.9)
        for xi, v in zip(xs_plot, yv):
            ax.text(xi + off - w, v + 0.01, f"{100*v:.0f}%", ha="center", fontsize=7)
    ax.axhline(0.5, color="grey", ls="--", lw=0.8)
    ax.set_xticks(x); ax.set_xticklabels([f"seed {s}" for s in seeds], fontsize=9)
    ax.set_ylim(0, 1.05)
    ax.set_ylabel("post-removal violation fraction", fontsize=9)
    ax.set_title("(a) contrast budget (dose response)", fontsize=9)
    ax.legend(frameon=False, fontsize=7.5, loc="upper center")
    ax.tick_params(labelsize=8)
    ax.spines["top"].set_visible(False)

    # (b) attack-shape negative controls at delta=2
    ax = axes[1]
    w = 0.18
    for vals, lab, col, off in [
        (bias, "bias ($+\\delta$ all; seed 1 only)", "#ff7f0e", -w),
        (clean, "clean", "#1f77b4", 0.0),
        (risk, "risk ($+\\delta$ on risk states)", "#2ca02c", w),
        (d2, "contrast (risk $+\\delta$, safe $-\\delta$)", "#d62728", 2 * w),
    ]:
        xs_plot = [xi for xi, v in zip(x, vals) if v is not None]
        yv = [vals[xi] for xi in xs_plot]
        ax.bar([xi + off - w for xi in xs_plot], yv, w, label=lab, color=col, alpha=0.9)
        for xi, v in zip(xs_plot, yv):
            ax.text(xi + off - w, v + 0.01, f"{100*v:.0f}%", ha="center", fontsize=7)
    ax.axhline(0.5, color="grey", ls="--", lw=0.8)
    ax.set_xticks(x); ax.set_xticklabels([f"seed {s}" for s in seeds], fontsize=9)
    ax.set_ylim(0, 1.05)
    ax.set_ylabel("post-removal violation fraction", fontsize=9)
    ax.set_title("(b) attack-shape controls at $\\delta$=2", fontsize=9)
    ax.legend(frameon=False, fontsize=7.5, loc="upper left")
    ax.tick_params(labelsize=8)
    ax.spines["top"].set_visible(False)

    fig.suptitle("Budget- and state-dependent susceptibility (full-phase REINFORCE)",
                 fontsize=10)
    fig.tight_layout(rect=(0, 0, 1, 0.92))
    os.makedirs(OUT, exist_ok=True)
    for ext in ("pdf", "png"):
        fig.savefig(os.path.join(OUT, f"fig7_dose_response.{ext}"), dpi=200)
    print("wrote fig7_dose_response.{pdf,png} (vA within-batch full-phase rows only)")
    print("clean:", [f"{v:.3f}" if v else None for v in clean])
    print("contrast d2:", [f"{v:.3f}" if v else None for v in d2])
    print("contrast d10:", [f"{v:.3f}" if v else None for v in d10])


if __name__ == "__main__":
    main()
