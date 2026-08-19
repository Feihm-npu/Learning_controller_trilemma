#!/usr/bin/env python3
"""fig6 family: REINFORCE isolation evidence (real data) + PPO isolation.

* fig6_retirement_isolation_summary.{pdf,png}  — REINFORCE vC real data (paper).
* fig6_ppo_isolation_template.{pdf,png}        — pre-registered placeholder (v1.5).
* fig6_ppo_isolation.{pdf,png}                 — REAL PPO v1.5 data, produced
  automatically when the paired run dirs obstacle_sudden_PPO_{none,v3}_d2_s{101..110}
  exist (protocol amendment v1.5.5).  No fabricated data is ever plotted.

Run: .venv-safe-control/bin/python carr_victim_experiment/make_fig6.py
"""
import glob, json, os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mtick
import numpy as np

matplotlib.rcParams.update({
    "font.family": "sans-serif",
    "font.sans-serif": ["Arial", "Helvetica", "DejaVu Sans", "sans-serif"],
    "svg.fonttype": "none",
    "pdf.fonttype": 42,
})

BASE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results")
OUT = os.path.join(BASE, "figures")
PAPER_OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                         "paper_latex", "figures")
os.makedirs(OUT, exist_ok=True)
os.makedirs(PAPER_OUT, exist_ok=True)
C, P = "#1f77b4", "#d62728"


def load(dn):
    hits = sorted(glob.glob(os.path.join(BASE, dn, "*_summary.json")))
    with open(hits[0]) as fh:
        return json.load(fh)


def exists(dn):
    return bool(glob.glob(os.path.join(BASE, dn, "*_summary.json")))


# ---- real REINFORCE isolation data (provenance-complete pairs) ----
# The original local configured-seed-3 clean at-retirement summary duplicated
# a separate fix-check record.  Its local poisoned run therefore has no valid
# paired clean endpoint.  Use the complete fresh clean/poisoned pair for every
# seed-3 panel and retain the first two pairs from the locked local batch.
seeds = [1, 2, 3]
clean = {
    1: load("obstacle_sudden_REINFORCE_none_d2_s1"),
    2: load("obstacle_sudden_REINFORCE_none_d2_s2"),
    3: load("obstacle_sudden_REINFORCE_none_d2_s3_iso_rr"),
}
pois = {
    1: load("obstacle_sudden_REINFORCE_v3_d2_s1"),
    2: load("obstacle_sudden_REINFORCE_v3_d2_s2"),
    3: load("obstacle_sudden_REINFORCE_v3_d2_s3_iso_rr"),
}
run_labels = ["local s1", "local s2", "fresh s3"]

clean_atret = np.array([clean[s]["at_retirement_stats"]["violation_fraction"] for s in seeds])
pois_atret = np.array([pois[s]["at_retirement_stats"]["violation_fraction"] for s in seeds])
clean_final = np.array([clean[s]["eval_stats"]["violation_fraction"] for s in seeds])
pois_final = np.array([pois[s]["eval_stats"]["violation_fraction"] for s in seeds])
clean_dis = np.array([clean[s]["at_retirement_stats"]["disagreement_fraction"] for s in seeds])
pois_dis = np.array([pois[s]["at_retirement_stats"]["disagreement_fraction"] for s in seeds])


def _panel(ax, cdat, pdat, fmt, vmax=0.95, labels=None, legend=False, title=None, ylab=None):
    x = np.arange(len(cdat)); w = 0.36
    b1 = ax.bar(x - w / 2, cdat, w, color=C, alpha=0.85, label="clean")
    b2 = ax.bar(x + w / 2, pdat, w, color=P, alpha=0.85,
                label="poisoned (shield-on only)")
    for clean_bar, poison_bar, clean_val, poison_val in zip(b1, b2, cdat, pdat):
        close_pair = abs(clean_val - poison_val) < 0.06
        for bar, val, extra in ((clean_bar, clean_val, 0.0),
                                (poison_bar, poison_val, 0.035 if close_pair else 0.0)):
            ax.text(bar.get_x() + bar.get_width() / 2, val + 0.015 + extra,
                    fmt % (100 * val if "%" in fmt else val),
                    ha="center", va="bottom", fontsize=6.5)
    ax.set_xticks(x)
    ax.set_xticklabels(labels or [f"seed {s}" for s in range(1, len(cdat) + 1)], fontsize=7)
    if title: ax.set_title(title, fontsize=8.5)
    if ylab: ax.set_ylabel(ylab, fontsize=8)
    ax.set_ylim(0, vmax)
    ax.yaxis.set_major_formatter(mtick.PercentFormatter(1.0, decimals=0))
    ax.tick_params(labelsize=8)
    ax.spines["top"].set_visible(False); ax.spines["right"].set_visible(False)
    if legend: ax.legend(frameon=False, fontsize=8)


# ---- fig6_retirement_isolation_summary (3 panels, real REINFORCE data) ----
fig, axes = plt.subplots(1, 3, figsize=(7.2, 2.55))
_panel(axes[0], clean_atret, pois_atret, "%.1f%%", vmax=0.95,
       labels=run_labels,
       title="(a) at retirement\n(raw policy at switch)", ylab="violation fraction")
_panel(axes[1], clean_dis, pois_dis, "%.2f%%", vmax=0.25,
       labels=run_labels,
       title="(b) at retirement\n(raw-policy/shield disagreement)")
_panel(axes[2], clean_final, pois_final, "%.1f%%", vmax=0.95,
       labels=run_labels,
       title="(c) final (5000 eps)\n(self-healing outcome)")
handles, legend_labels = axes[2].get_legend_handles_labels()
fig.legend(handles, legend_labels, loc="lower center", ncol=2,
           bbox_to_anchor=(0.5, -0.01), frameon=False, fontsize=7)
fig.tight_layout(rect=(0, 0.14, 1, 1), w_pad=1.0)
fig.savefig(os.path.join(OUT, "fig6_retirement_isolation_summary.svg"), dpi=600)
fig.savefig(os.path.join(OUT, "fig6_retirement_isolation_summary.pdf"), dpi=600)
fig.savefig(os.path.join(OUT, "fig6_retirement_isolation_summary.png"), dpi=600)
fig.savefig(os.path.join(PAPER_OUT, "fig6_retirement_isolation_summary.svg"), dpi=600)
fig.savefig(os.path.join(PAPER_OUT, "fig6_retirement_isolation_summary.pdf"), dpi=600)
fig.savefig(os.path.join(PAPER_OUT, "fig6_retirement_isolation_summary.png"), dpi=600)
print("wrote fig6_retirement_isolation_summary.{svg,pdf,png}")

# ---- fig6_ppo_isolation_template (v1.5 spec, NO fabricated data) ----
fig2, ax = plt.subplots(figsize=(9, 3.6))
pseeds = list(range(101, 111))
n = len(pseeds); xx = np.arange(n); w = 0.36
ax.bar(xx - w / 2, np.zeros(n), w, color=C, alpha=0.15, hatch="//", edgecolor=C,
       label="clean (pending v1.5)")
ax.bar(xx + w / 2, np.zeros(n), w, color=P, alpha=0.15, hatch="//", edgecolor=P,
       label="poisoned shield-on (pending v1.5)")
ax.axhline(0.5, color="grey", ls="--", lw=0.8)
ax.text(n - 0.5, 0.515, "decision rule: poisoned \u2265 clean + 15 pp AND McNemar exact p < 0.01 (positive seed)",
        ha="right", fontsize=8, color="grey")
for xi in xx:
    ax.text(xi, 0.03, "\u2014", ha="center", fontsize=8, color="grey")
axi = fig2.add_axes([0.62, 0.55, 0.30, 0.33])
_panel(axi, clean_atret, pois_atret, "%.0f%%", vmax=1.0, labels=["s1", "s2", "s3"])
axi.set_title("REINFORCE reference (real, 2/3)", fontsize=7)
ax.set_xticks(xx); ax.set_xticklabels(pseeds, fontsize=8)
ax.set_ylim(0, 1)
ax.set_xlabel("PPO seed (namespace 101\u2013110, locked in protocol amendment v1.5)", fontsize=9)
ax.set_ylabel("at-retirement violation fraction", fontsize=9)
ax.set_title("PPO retirement isolation \u2014 pre-registered figure spec (amendment v1.5; data pending server run)",
             fontsize=10)
ax.legend(frameon=False, fontsize=8, loc="upper left")
fig2.subplots_adjust(left=0.07, right=0.98, top=0.84, bottom=0.13)
for ext in ("svg", "pdf", "png"):
    fig2.savefig(os.path.join(OUT, f"fig6_ppo_isolation_template.{ext}"), dpi=600)
print("wrote fig6_ppo_isolation_template.{pdf,png}")

# ---- fig6_ppo_isolation (REAL PPO v1.5 data, produced only when present) ----
pclean_dirs = [f"obstacle_sudden_PPO_none_d2_s{s}" for s in pseeds]
ppois_dirs = [f"obstacle_sudden_PPO_v3_d2_s{s}" for s in pseeds]
have = [c and p for c, p in zip([exists(d) for d in pclean_dirs], [exists(d) for d in ppois_dirs])]
if any(have):
    pclean = [load(pclean_dirs[i]) if have[i] else None for i in range(n)]
    ppois = [load(ppois_dirs[i]) if have[i] else None for i in range(n)]
    pca = np.array([(x["at_retirement_stats"]["violation_fraction"] if x else np.nan) for x in pclean])
    ppa = np.array([(x["at_retirement_stats"]["violation_fraction"] if x else np.nan) for x in ppois])
    fig3, ax = plt.subplots(figsize=(9, 3.6))
    _panel(ax, np.nan_to_num(pca, nan=0), np.nan_to_num(ppa, nan=0), "%.1f%%", vmax=1.0,
           labels=pseeds, legend=True,
           ylab="at-retirement violation fraction")
    ax.set_title("PPO retirement isolation (shield-on poisoning, paired run indices 101\u2013110)",
                 fontsize=10)
    # mark missing seeds and the decision threshold
    for i, h in enumerate(have):
        if not h:
            ax.get_xticklabels()[i].set_color("red")
    ax.axhline(0.5, color="grey", ls="--", lw=0.8)
    ax.text(n - 0.5, 0.515, "positive: poisoned \u2265 clean + 0.15",
            ha="right", fontsize=8, color="grey")
    fig3.subplots_adjust(left=0.07, right=0.98, top=0.88, bottom=0.13)
    for ext in ("svg", "pdf", "png"):
        fig3.savefig(os.path.join(OUT, f"fig6_ppo_isolation.{ext}"), dpi=600)
    print(f"wrote fig6_ppo_isolation.{{pdf,png}} with REAL data for {sum(have)}/{n} paired seeds")
else:
    print("fig6_ppo_isolation NOT written (no PPO v1.5 data present; template kept)")


# ---- fig6_reinforce16_isolation (REAL v1.6 REINFORCE 10-seed data, produced only when present) ----
rseeds = list(range(201, 211))
rclean_dirs = [f"obstacle_sudden_REINFORCE_none_d2_s{s}" for s in rseeds]
rpois_dirs = [f"obstacle_sudden_REINFORCE_v3_d2_s{s}" for s in rseeds]
rhave = [c and p for c, p in zip([exists(d) for d in rclean_dirs], [exists(d) for d in rpois_dirs])]
if any(rhave):
    rclean = [load(rclean_dirs[i]) if rhave[i] else None for i in range(len(rseeds))]
    rpois = [load(rpois_dirs[i]) if rhave[i] else None for i in range(len(rseeds))]
    rca = np.array([(x["at_retirement_stats"]["violation_fraction"] if x else np.nan) for x in rclean])
    rpa = np.array([(x["at_retirement_stats"]["violation_fraction"] if x else np.nan) for x in rpois])
    rcf = np.array([(x["eval_stats"]["violation_fraction"] if x else np.nan) for x in rclean])
    rpf = np.array([(x["eval_stats"]["violation_fraction"] if x else np.nan) for x in rpois])
    fig4, ax4 = plt.subplots(figsize=(10, 3.6))
    xx4 = np.arange(len(rseeds))
    w4 = 0.36
    ax4.bar(xx4 - w4 / 2, np.nan_to_num(rca, nan=0), w4, color=C, alpha=0.85, label="clean")
    ax4.bar(xx4 + w4 / 2, np.nan_to_num(rpa, nan=0), w4, color=P, alpha=0.85,
            label="poisoned (shield-on only)")
    ax4.set_xticks(xx4); ax4.set_xticklabels(rseeds, fontsize=8)
    for i, h in enumerate(rhave):
        if not h:
            ax4.get_xticklabels()[i].set_color("red")
    ax4.axhline(0.5, color="grey", ls="--", lw=0.8)
    ax4.text(len(rseeds) - 0.5, 0.515,
             "decision: poisoned \u2265 clean + 15 pp AND McNemar p<0.01 (positive)",
             ha="right", fontsize=8, color="grey")
    ax4.set_ylim(0, 1)
    ax4.set_xlabel("REINFORCE seed (namespace 201\u2013210, locked in protocol amendment v1.6)", fontsize=9)
    ax4.set_ylabel("at-retirement violation fraction", fontsize=9)
    ax4.set_title("REINFORCE retirement isolation \u2014 REAL v1.6 data (shield-on poisoning, paired seeds 201\u2013210)",
                  fontsize=10)
    ax4.legend(frameon=False, fontsize=8, loc="upper left")
    ax4.spines["top"].set_visible(False); ax4.spines["right"].set_visible(False)
    fig4.tight_layout()
    for ext in ("svg", "pdf", "png"):
        fig4.savefig(os.path.join(OUT, f"fig6_reinforce16_isolation.{ext}"), dpi=600)
    print(f"wrote fig6_reinforce16_isolation.{{pdf,png}} with REAL data for {sum(rhave)}/{len(rseeds)} paired seeds")
else:
    print("fig6_reinforce16_isolation NOT written (no v1.6 REINFORCE data present)")

# ---- numeric summary printed for the report ----

print("\nREINFORCE isolation numbers (verified from summary.json):")
for i, s in enumerate(seeds):
    print(f"  seed {s}: clean at-ret {clean_atret[i]:.3f} | poisoned at-ret {pois_atret[i]:.3f} "
          f"| clean final {clean_final[i]:.3f} | poisoned final {pois_final[i]:.3f} "
          f"| disagree clean {clean_dis[i]:.3f} / poisoned {pois_dis[i]:.3f}")
