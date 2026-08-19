#!/usr/bin/env python3
"""Seed-heterogeneity analysis for the retirement-boundary isolation batteries.

Question (reviewer-facing): is the attack effect concentrated on seeds whose
clean learning would otherwise transfer safety to the released raw policy?
If yes, the per-seed boundary is interpretable (susceptibility subset), not
an unexplained run-to-run artifact.

For every paired clean/poisoned run we compute:
  clean_atret  = violation fraction of the clean raw policy at retirement
  poison_atret = violation fraction of the poisoned raw policy at retirement
  effect       = poison_atret - clean_atret   (attack headroom)
We then report, per battery (REINFORCE v1.6 s201-210, PPO v1.5 s101-110,
REINFORCE vC s1-3):
  * Spearman/Pearson correlation between clean_atret and effect
  * effect conditioned on clean_atret bins (transfer-sensitive vs not)
  * the 2x2 contingency: seed "transfer-sensitive" (clean_atret < 0.5) vs not
    x "positive" (effect >= 0.15 and McNemar p < 0.01)

Expected pattern if heterogeneity is interpretable: effect is large when
clean_atret is low (clean learning transfers safety) and small when
clean_atret is already high (ceiling). I.e., negative correlation.

Run: .venv-safe-control/bin/python carr_victim_experiment/analyze_seed_heterogeneity.py
"""
import glob, json, os
import numpy as np

BASE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results")
SUMMARY_GLOB = "*_summary.json"


def load(dn):
    hits = sorted(glob.glob(os.path.join(BASE, dn, SUMMARY_GLOB)))
    with open(hits[0]) as fh:
        return json.load(fh)


def atret_frac(s):
    st = s.get("at_retirement_stats") or {}
    return st.get("violation_fraction")


def analyze(learner, clean_prefix, pois_prefix, seeds, require=10):
    rows = []
    for sd in seeds:
        cd, pd = f"{clean_prefix}{sd}", f"{pois_prefix}{sd}"
        if not (glob.glob(os.path.join(BASE, cd, SUMMARY_GLOB))
                and glob.glob(os.path.join(BASE, pd, SUMMARY_GLOB))):
            continue
        c, p = load(cd), load(pd)
        ca, pa = atret_frac(c), atret_frac(p)
        if ca is None or pa is None:
            continue
        rows.append(dict(seed=sd, clean_atret=ca, effect=pa - ca))
    if not rows:
        print(f"{learner}: no paired data present yet")
        return
    clean = np.array([r["clean_atret"] for r in rows])
    eff = np.array([r["effect"] for r in rows])
    # correlation
    r_pearson = np.corrcoef(clean, eff)[0, 1] if len(rows) > 2 else float("nan")
    # Spearman via rank
    from scipy.stats import spearmanr
    r_spearman, p_spear = spearmanr(clean, eff)
    print(f"\n{learner} ({len(rows)} paired seeds)")
    print(f"  {'seed':>4} {'clean_atret':>11} {'effect':>7}")
    for r in sorted(rows, key=lambda x: x["seed"]):
        print(f"  {r['seed']:>4} {r['clean_atret']:>11.3f} {r['effect']:>+7.3f}")
    print(f"  Pearson(clean_atret, effect) = {r_pearson:+.3f}")
    print(f"  Spearman(clean_atret, effect) = {r_spearman:+.3f} (p={p_spear:.3g})")
    sens = clean < 0.5
    if sens.sum() > 0 and (~sens).sum() > 0:
        print(f"  effect when clean_atret<0.5 (transfer-sensitive): "
              f"{eff[sens].mean():+.3f} (n={sens.sum()})")
        print(f"  effect when clean_atret>=0.5 (ceiling):           "
              f"{eff[~sens].mean():+.3f} (n={(~sens).sum()})")
    # 2x2 contingency: transfer-sensitive (clean_atret<0.5) x positive
    # (effect>=0.15, fraction-only; strict paired McNemar is applied per
    # battery by analyze_ppo_isolation.py when at-ret traces are present).
    pos = eff >= 0.15
    a = int((sens & pos).sum())   # transfer-sensitive & positive
    b = int((sens & ~pos).sum())  # transfer-sensitive & not positive
    c = int((~sens & pos).sum())  # ceiling & positive
    d = int((~sens & ~pos).sum()) # ceiling & not positive
    print(f"  2x2 (frac-only rule, effect>=0.15): sens-positive={a} "
          f"sens-neg={b} | ceil-positive={c} ceil-neg={d}")
    return rows


if __name__ == "__main__":
    analyze("REINFORCE vC (s1-3)", "obstacle_sudden_REINFORCE_none_d2_s",
            "obstacle_sudden_REINFORCE_v3_d2_s", range(1, 4), require=3)
    analyze("REINFORCE v1.6 (s201-210)", "obstacle_sudden_REINFORCE_none_d2_s",
            "obstacle_sudden_REINFORCE_v3_d2_s", range(201, 211))
    analyze("PPO v1.5 (s101-110)", "obstacle_sudden_PPO_none_d2_s",
            "obstacle_sudden_PPO_v3_d2_s", range(101, 111))
