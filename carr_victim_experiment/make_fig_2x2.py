#!/usr/bin/env python3
"""Generate fig8_2x2_susceptibility (paper sec6 "Reading" paragraph).

Scatter of clean vs poisoned at-retirement violation fraction for every
paired seed across all locked batteries, colored by learner/domain:

  * REINFORCE full-phase (v1.9, fullvC s201-210) and isolation (v1.6, s201-210)
  * PPO full-phase (v1.9, fullvC s101-110) and isolation (v1.5, s101-110)
  * SAC isolation (v1.10/v1.12/v1.13, s401-410)
  * avoid-domain isolation (v1.8, surveillance, s1-3)

Positive-seed rule (locked): poisoned at-ret >= clean at-ret + 0.15 AND
paired McNemar exact p < 0.01  -> filled markers; otherwise hollow.

Reference lines: x = 0.5 (susceptibility boundary), y = x (identity),
y = x + 0.15 (positive-seed rule boundary).

Usage:
  ../.venv-safe-control/bin/python carr_victim_experiment/make_fig_2x2.py
"""
from __future__ import annotations

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from analyze_fullphase import (
    BASE, POSITIVE_PP, POSITIVE_ALPHA, seed_row,
)

OUT = os.path.join(BASE, "figures")
PAPER_FIG = os.path.join(
    os.path.dirname(HERE), "paper_latex", "figures")


def collect(category, clean_prefix, pois_prefix, seeds, suffix=""):
    """Return [(cat, seed, ca, pa, strict), ...] skipping incomplete pairs."""
    rows = []
    for s in seeds:
        cdir = os.path.join(BASE, f"{clean_prefix}{s}{suffix}")
        pdir = os.path.join(BASE, f"{pois_prefix}{s}{suffix}")
        r = seed_row(cdir, pdir)
        if r is None:
            continue
        rows.append((category, s, r["ca"], r["pa"], r["strict"]))
    return rows


def main():
    data = []
    # REINFORCE full-phase (v1.9 fullvC) + isolation (v1.6, local dirs)
    data += collect("REINFORCE full-phase",
                    "obstacle_sudden_REINFORCE_none_d2_s",
                    "obstacle_sudden_REINFORCE_v3_d2_s",
                    range(201, 211), suffix="_fullvC")
    data += collect("REINFORCE isolation",
                    "obstacle_sudden_REINFORCE_none_d2_s",
                    "obstacle_sudden_REINFORCE_v3_d2_s",
                    range(201, 211))
    # PPO full-phase (v1.9 fullvC) + isolation (v1.5, local dirs)
    data += collect("PPO full-phase",
                    "obstacle_sudden_PPO_none_d2_s",
                    "obstacle_sudden_PPO_v3_d2_s",
                    range(101, 111), suffix="_fullvC")
    data += collect("PPO isolation",
                    "obstacle_sudden_PPO_none_d2_s",
                    "obstacle_sudden_PPO_v3_d2_s",
                    range(101, 111))
    # SAC isolation (v1.10 s401-403 + v1.12 s404-406 + v1.13 s407-410; incomplete pairs skipped)
    data += collect("SAC isolation",
                    "obstacle_sudden_SAC_none_d2_s",
                    "obstacle_sudden_SAC_v3_d2_s",
                    range(401, 411))  # v1.10/v1.12 s401-406 + v1.13 s407-410
    # avoid-domain isolation (v1.8, surveillance)
    data += collect("avoid",
                    "avoid_sudden_REINFORCE_none_d2_s",
                    "avoid_sudden_REINFORCE_v3_d2_s",
                    range(1, 4))

    n = len(data)
    if n == 0:
        print("no complete paired rows found; nothing to plot")
        return 1

    cats = ["REINFORCE full-phase", "REINFORCE isolation", "PPO full-phase",
            "PPO isolation", "SAC isolation", "avoid"]
    colors = {
        "REINFORCE full-phase": "#1f77b4",
        "REINFORCE isolation":  "#1f77b4",
        "PPO full-phase":       "#d62728",
        "PPO isolation":        "#d62728",
        "SAC isolation":        "#2ca02c",
        "avoid":                "#9467bd",
    }
    markers = {
        "REINFORCE full-phase": "o",
        "REINFORCE isolation":  "s",
        "PPO full-phase":       "^",
        "PPO isolation":        "D",
        "SAC isolation":        "P",
        "avoid":                "X",
    }

    # 2x2 counts (strict rule) for printout / paper consistency
    lo_pos = lo_neg = hi_pos = hi_neg = 0
    for _cat, _s, ca, pa, strict in data:
        if ca < 0.5:
            if strict: lo_pos += 1
            else:      lo_neg += 1
        else:
            if strict: hi_pos += 1
            else:      hi_neg += 1

    fig, ax = plt.subplots(figsize=(5.6, 5.2))

    for cat in cats:
        sel = [r for r in data if r[0] == cat]
        if not sel:
            continue
        xs = np.array([r[2] for r in sel])
        ys = np.array([r[3] for r in sel])
        pos = np.array([r[4] for r in sel], dtype=bool)
        col = colors[cat]
        mk = markers[cat]
        # positive (strict) -> filled; not positive -> hollow
        ax.scatter(xs[pos], ys[pos], s=55, marker=mk, color=col, edgecolor="k",
                   linewidths=0.6, zorder=5, alpha=0.95)
        ax.scatter(xs[~pos], ys[~pos], s=55, marker=mk, facecolors="none",
                   edgecolors=col, linewidths=1.1, zorder=4)
        # annotate positive seeds with their id
        for (_c, s_, ca_, pa_, _st) in sel:
            if _st:
                ax.annotate(str(s_), (ca_, pa_), textcoords="offset points",
                            xytext=(5, 3), fontsize=6.5, color="0.15")

    # reference lines
    xx = np.linspace(0, 1, 100)
    ax.plot(xx, xx, color="grey", ls=":", lw=1.0, zorder=1)
    ax.plot(xx, np.clip(xx + POSITIVE_PP, 0, 1), color="0.25", ls="--", lw=1.2,
            zorder=2)
    ax.axvline(0.5, color="0.4", ls="-.", lw=1.1, zorder=2)
    ax.text(0.5, 0.03, "clean at-ret = 0.5", fontsize=7.5, color="0.35",
            ha="center")
    ax.text(0.80, 0.52, "positive rule\n$y = x + 0.15$", fontsize=7.5,
            color="0.25", ha="center", va="bottom")

    ax.set_xlim(-0.02, 1.02)
    ax.set_ylim(-0.02, 1.02)
    ax.set_aspect("equal")
    ax.set_xlabel("clean at-retirement violation fraction", fontsize=9)
    ax.set_ylabel("poisoned at-retirement violation fraction", fontsize=9)
    ax.tick_params(labelsize=8)
    for sp in ("top", "right"):
        ax.spines[sp].set_visible(False)

    handles, labels = [], []
    for cat in cats:
        if not any(r[0] == cat for r in data):
            continue
        handles.append(plt.Line2D([], [], marker=markers[cat], ls="none",
                                  markerfacecolor=colors[cat], markeredgecolor="k",
                                  markersize=6.5))
        labels.append(cat)
    handles.append(plt.Line2D([], [], marker="o", ls="none", color="w",
                              markerfacecolor="w", markeredgecolor="0.3",
                              markersize=6.5))
    labels.append("not positive (hollow)")
    leg = ax.legend(handles, labels, frameon=False, fontsize=7.5,
                    loc="upper left", bbox_to_anchor=(0.0, 1.0), ncol=1,
                    handlelength=1.6, columnspacing=1.0)
    fig.suptitle("Susceptibility rule: positive only when clean at-ret $< 0.5$",
                 fontsize=10)
    fig.tight_layout(rect=(0, 0, 1, 0.95))

    os.makedirs(OUT, exist_ok=True)
    os.makedirs(PAPER_FIG, exist_ok=True)
    for ext in ("pdf", "png"):
        fig.savefig(os.path.join(OUT, f"fig8_2x2_susceptibility.{ext}"), dpi=200)
        fig.savefig(os.path.join(PAPER_FIG, f"fig8_2x2_susceptibility.{ext}"), dpi=200)
    print(f"wrote fig8_2x2_susceptibility.{{pdf,png}} -> {OUT} and {PAPER_FIG}")
    print(f"rows plotted: {n}")
    print(f"2x2 (strict): clean<0.5 positive {lo_pos}, not {lo_neg} | "
          f"clean>=0.5 positive {hi_pos}, not {hi_neg}")
    print("per-category:")
    for cat in cats:
        sel = [r for r in data if r[0] == cat]
        if sel:
            print(f"  {cat}: n={len(sel)} pos={sum(r[4] for r in sel)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
