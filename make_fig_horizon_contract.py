#!/usr/bin/env python3
"""Generate fig10_horizon_contract (paper sec6 "How much lookahead" paragraph).

Reads the locked horizon sweep summary and plots the three quantities that
move together as the retained predictor's horizon grows, on the pooled V3
cohort of 72 snapshot--state pairs:

  * release admission (candidates accepted by the check at that horizon)
  * resident failures under the retained contract
  * median switching lead, in steps before the paired raw-release failure

The point of the figure is the interval: too little lookahead leaves no
recovery lead time, too much rejects the candidates the check exists to admit.

Source: results/cartpole_horizon_contract_sweep_summary.csv (scope == "pooled").
Usage:  python3 make_fig_horizon_contract.py
"""
from __future__ import annotations

import csv
import os

import matplotlib

matplotlib.use("Agg")
# Embed TrueType rather than Type 3 so figure text stays selectable in the
# submission PDF (same convention as carr_victim_experiment/make_fig6.py).
matplotlib.rcParams["pdf.fonttype"] = 42
matplotlib.rcParams["ps.fonttype"] = 42
import matplotlib.pyplot as plt

HERE = os.path.dirname(os.path.abspath(__file__))
SOURCE = os.path.join(HERE, "results", "cartpole_horizon_contract_sweep_summary.csv")
PAPER_FIG = os.path.join(HERE, "paper_latex", "figures")


def pooled_rows() -> list[dict[str, str]]:
    with open(SOURCE, newline="") as handle:
        rows = [r for r in csv.DictReader(handle) if r["scope"] == "pooled"]
    rows.sort(key=lambda r: int(r["monitor_horizon"]))
    assert rows, "no pooled rows in the horizon sweep summary"
    return rows


def main() -> None:
    rows = pooled_rows()
    horizons = [int(r["monitor_horizon"]) for r in rows]
    admitted = [int(r["poison_initially_accepted"]) for r in rows]
    selected = [int(r["selected_states"]) for r in rows]
    resident = [int(r["resident_violations"]) for r in rows]
    lead = [
        (int(r["monitor_horizon"]), float(r["median_switch_lead_steps"]))
        for r in rows
        if r["median_switch_lead_steps"]
    ]
    passed = [int(r["monitor_horizon"]) for r in rows if r["horizon_condition_pass"] == "True"]

    x = list(range(len(horizons)))
    fig, ax = plt.subplots(figsize=(3.35, 2.05))

    if passed:
        lo = x[horizons.index(min(passed))] - 0.42
        hi = x[horizons.index(max(passed))] + 0.42
        ax.axvspan(lo, hi, color="0.90", zorder=0)

    ax.plot(x, admitted, marker="o", ms=4, lw=1.4, color="#1f4e79",
            label=f"release admission (of {selected[0]})")
    ax.plot(x, resident, marker="s", ms=4, lw=1.4, ls="--", color="#a02c2c",
            label="resident failures")
    ax.set_xticks(x)
    ax.set_xticklabels([str(h) for h in horizons])
    ax.set_xlabel("retained predictor horizon (steps)", fontsize=8)
    ax.set_ylabel("pairs (of 72)", fontsize=8)
    ax.set_ylim(-4, 84)
    ax.tick_params(labelsize=7)

    twin = ax.twinx()
    twin.plot([x[horizons.index(h)] for h, _ in lead], [v for _, v in lead],
              marker="^", ms=4, lw=1.4, ls=":", color="#2e7d32",
              label="median switching lead")
    twin.set_ylabel("lead (steps)", fontsize=8)
    twin.set_ylim(-0.6, 12.6)
    twin.tick_params(labelsize=7)

    if passed:
        ax.text((lo + hi) / 2.0, 79.5, "separation condition met",
                ha="center", va="center", fontsize=6.5, color="0.35")

    handles, labels = ax.get_legend_handles_labels()
    th, tl = twin.get_legend_handles_labels()
    ax.legend(handles + th, labels + tl, fontsize=6.3, loc="center left",
              frameon=False, borderpad=0.1, handlelength=1.9,
              labelspacing=0.25)

    for spine in ("top",):
        ax.spines[spine].set_visible(False)
        twin.spines[spine].set_visible(False)

    fig.tight_layout(pad=0.25)
    os.makedirs(PAPER_FIG, exist_ok=True)
    out = os.path.join(PAPER_FIG, "fig10_horizon_contract.pdf")
    fig.savefig(out, dpi=200, bbox_inches="tight")
    plt.close(fig)
    print("wrote", out)
    print("horizons", horizons)
    print("admitted", admitted, "resident", resident, "lead", lead, "pass", passed)


if __name__ == "__main__":
    main()
