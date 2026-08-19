#!/usr/bin/env python3
"""Generate fig9_mechanism_divergence (paper sec6 "Reading" paragraph).

Scatter of clean at-retirement raw-policy/shield disagreement vs attack
headroom (poisoned - clean at-retirement) for every obstacle paired seed
across all three learner families and both scopes.  This is the
pre-registered v1.13 mechanism analysis visual:

  * x = clean at-retirement disagreement fraction cd
  * y = attack headroom pa - ca
  * filled = positive seed (strict locked rule); hollow = not positive
  * vertical dashed lines at cd = 0.06 and cd = 0.09 (dichotomization
    bands locked in amendment v1.13.3: "low" cd < 0.06, "high" cd >= 0.09)
  * marker shape by scope: full-phase = triangle, shield-on isolation = square

Spearman(cd, headroom) is printed for the obstacle rows.

Usage:
  ../.venv-safe-control/bin/python carr_victim_experiment/make_fig_mechanism.py
"""
from __future__ import annotations

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import matplotlib
matplotlib.use("Agg")
matplotlib.rcParams["pdf.fonttype"] = 42
matplotlib.rcParams["ps.fonttype"] = 42
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from scipy.stats import spearmanr

from analyze_fullphase import BASE, POSITIVE_PP, POSITIVE_ALPHA, seed_row

OUT = os.path.join(BASE, "figures")
PAPER_FIG = os.path.join(os.path.dirname(HERE), "paper_latex", "figures")


def collect(clean_prefix, pois_prefix, seeds, suffix=""):
    rows = []
    for s in seeds:
        cdir = os.path.join(BASE, f"{clean_prefix}{s}{suffix}")
        pdir = os.path.join(BASE, f"{pois_prefix}{s}{suffix}")
        r = seed_row(cdir, pdir)
        if r is None:
            continue
        rows.append(r)
    return rows


def main():
    data = []
    # REINFORCE full-phase (v1.9 fullvC) + isolation (v1.6)
    for r in collect("obstacle_sudden_REINFORCE_none_d2_s",
                     "obstacle_sudden_REINFORCE_v3_d2_s",
                     range(201, 211), suffix="_fullvC"):
        r["cat"] = "REINFORCE full-phase"
        data.append(r)
    for r in collect("obstacle_sudden_REINFORCE_none_d2_s",
                     "obstacle_sudden_REINFORCE_v3_d2_s",
                     range(201, 211)):
        r["cat"] = "REINFORCE isolation"
        data.append(r)
    # PPO full-phase (v1.9 fullvC) + isolation (v1.5)
    for r in collect("obstacle_sudden_PPO_none_d2_s",
                     "obstacle_sudden_PPO_v3_d2_s",
                     range(101, 111), suffix="_fullvC"):
        r["cat"] = "PPO full-phase"
        data.append(r)
    for r in collect("obstacle_sudden_PPO_none_d2_s",
                     "obstacle_sudden_PPO_v3_d2_s",
                     range(101, 111)):
        r["cat"] = "PPO isolation"
        data.append(r)
    # SAC isolation (v1.10/v1.12 s401-406; v1.13 s407-410 appended when present)
    for r in collect("obstacle_sudden_SAC_none_d2_s",
                     "obstacle_sudden_SAC_v3_d2_s",
                     range(401, 411)):
        r["cat"] = "SAC isolation"
        data.append(r)

    # keep only rows with a finite clean disagreement
    data = [r for r in data if np.isfinite(r["cd"])]
    n = len(data)
    if n == 0:
        print("no complete paired rows found; nothing to plot")
        return 1

    cd = np.array([r["cd"] for r in data])
    hr = np.array([r["pa"] - r["ca"] for r in data])
    strict = np.array([r["strict"] for r in data], dtype=bool)
    ca = np.array([r["ca"] for r in data])

    rho, pval = spearmanr(cd, hr)
    print(f"obstacle rows: {n}")
    print(f"Spearman(cd, headroom) = {rho:.4f} (p={pval:.3e})")
    pos_cd = cd[strict]
    non_cd = cd[~strict]
    print(f"positive rows cd range: [{pos_cd.min():.3f}, {pos_cd.max():.3f}]"
          if len(pos_cd) else "no positive rows")
    print(f"non-positive rows cd range: [{non_cd.min():.3f}, {non_cd.max():.3f}]")

    cats = ["REINFORCE full-phase", "REINFORCE isolation", "PPO full-phase",
            "PPO isolation", "SAC isolation"]
    colors = {
        "REINFORCE full-phase": "#1f77b4",
        "REINFORCE isolation":  "#1f77b4",
        "PPO full-phase":       "#d62728",
        "PPO isolation":        "#d62728",
        "SAC isolation":        "#2ca02c",
    }
    markers = {
        "REINFORCE full-phase": "^",
        "REINFORCE isolation":  "s",
        "PPO full-phase":       "^",
        "PPO isolation":        "s",
        "SAC isolation":        "P",
    }

    fig, ax = plt.subplots(figsize=(5.6, 4.6))

    for cat in cats:
        sel = [r for r in data if r["cat"] == cat]
        if not sel:
            continue
        xs = np.array([r["cd"] for r in sel])
        ys = np.array([r["pa"] - r["ca"] for r in sel])
        p_ = np.array([r["strict"] for r in sel], dtype=bool)
        col = colors[cat]
        mk = markers[cat]
        ax.scatter(xs[p_], ys[p_], s=52, marker=mk, color=col, edgecolor="k",
                   linewidths=0.6, zorder=5, alpha=0.95)
        ax.scatter(xs[~p_], ys[~p_], s=52, marker=mk, facecolors="none",
                   edgecolors=col, linewidths=1.1, zorder=4)
        for (_c, s_, cd_, ca_, pa_, st_) in ((r, r["seed"], r["cd"], r["ca"],
                                              r["pa"], r["strict"]) for r in sel):
            if st_:
                ax.annotate(str(s_), (cd_, pa_ - ca_),
                            textcoords="offset points", xytext=(5, 3),
                            fontsize=6.5, color="0.15")

    # dichotomization bands (locked v1.13.3)
    ax.axvline(0.06, color="0.4", ls="-.", lw=1.1, zorder=2)
    ax.axvline(0.09, color="0.4", ls="-.", lw=1.1, zorder=2)
    ax.text(0.03, 0.55, "low $c_d$", fontsize=7.5, color="0.35", ha="center")
    ax.text(0.075, 0.55, "band", fontsize=7.5, color="0.35", ha="center")
    ax.text(0.105, 0.55, "high $c_d$", fontsize=7.5, color="0.35", ha="center")
    ax.axhline(0.0, color="grey", ls=":", lw=1.0, zorder=1)

    ax.set_xlim(0, 0.13)
    ax.set_ylim(-0.65, 0.65)
    ax.set_xlabel("clean at-retirement raw-policy/shield disagreement $c_d$",
                  fontsize=9)
    ax.set_ylabel("attack headroom (poisoned $-$ clean at-ret)", fontsize=9)
    ax.tick_params(labelsize=8)
    for sp in ("top", "right"):
        ax.spines[sp].set_visible(False)

    handles, labels = [], []
    for cat in cats:
        if not any(r["cat"] == cat for r in data):
            continue
        handles.append(plt.Line2D([], [], marker=markers[cat], ls="none",
                                  markerfacecolor=colors[cat], markeredgecolor="k",
                                  markersize=6))
        labels.append(cat)
    handles.append(plt.Line2D([], [], marker="o", ls="none", color="w",
                              markerfacecolor="w", markeredgecolor="0.3",
                              markersize=6))
    labels.append("not positive (hollow)")
    ax.legend(handles, labels, frameon=False, fontsize=7, loc="upper right",
              handlelength=1.6, columnspacing=1.0, ncol=1)
    ax.set_title(f"Attack headroom vs. clean retirement-state disagreement "
                 f"($n={n}$)", fontsize=9.5)
    fig.tight_layout()

    os.makedirs(OUT, exist_ok=True)
    os.makedirs(PAPER_FIG, exist_ok=True)
    for ext in ("pdf", "png"):
        fig.savefig(os.path.join(OUT, f"fig9_mechanism_divergence.{ext}"), dpi=200,
                    bbox_inches="tight")
        fig.savefig(os.path.join(PAPER_FIG, f"fig9_mechanism_divergence.{ext}"), dpi=200,
                    bbox_inches="tight")
    print(f"wrote fig9_mechanism_divergence.{{pdf,png}} -> {OUT} and {PAPER_FIG}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
