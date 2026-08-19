#!/usr/bin/env python3
"""Dose-response analysis (protocol amendment v1.7 / B3).

Reads the v1.7 dose series on the server's transfer-sensitive seed 1 (vC code)
after sync_from_server.sh, reuses the existing vC full-phase rows at delta in
{2, 10}, and reports:
  - post-removal (final) and at-retirement violation fractions vs delta;
  - paired McNemar exact vs clean on the same seed (final-eval episodes);
  - min effective delta (poisoned final >= clean final + 0.15 AND p < 0.01);
  - at-retirement disagreement monotonicity (descriptive mechanism signal);
  - shield-on-only series under the same grid (stricter causal scope).

Run after sync_from_server.sh:
  ../.venv-safe-control/bin/python carr_victim_experiment/analyze_dose_response.py
"""
import json, os, glob
import numpy as np
from scipy.stats import binomtest

BASE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results")

FULL_DIRS = {
    0.0:  "obstacle_sudden_REINFORCE_none_d2_s1_fullvC",
    0.1:  "obstacle_sudden_REINFORCE_contrast_d0p1_s1_doser",
    0.25: "obstacle_sudden_REINFORCE_contrast_d0p25_s1_doser",
    0.5:  "obstacle_sudden_REINFORCE_contrast_d0p5_s1_doser",
    1.0:  "obstacle_sudden_REINFORCE_contrast_d1p0_s1_doser",
    2.0:  "obstacle_sudden_REINFORCE_contrast_d2_s1_fullvC",
    10.0: "obstacle_sudden_REINFORCE_contrast_d10_s1_fullvC",
}
SHIELDON_DIRS = {
    0.0:  "obstacle_sudden_REINFORCE_none_d0_s1_shieldon_doser",
    0.1:  "obstacle_sudden_REINFORCE_contrast_d0p1_s1_shieldon_doser",
    0.25: "obstacle_sudden_REINFORCE_contrast_d0p25_s1_shieldon_doser",
    0.5:  "obstacle_sudden_REINFORCE_contrast_d0p5_s1_shieldon_doser",
    1.0:  "obstacle_sudden_REINFORCE_contrast_d1p0_s1_shieldon_doser",
    2.0:  "obstacle_sudden_REINFORCE_contrast_d2p0_s1_shieldon_doser",
}


def load_summary(d):
    jp = glob.glob(os.path.join(BASE, d, "*_summary.json"))
    if not jp:
        return None
    with open(sorted(jp)[0]) as f:
        return json.load(f)


def load_trace(d, suffix="eval"):
    hits = sorted(glob.glob(os.path.join(BASE, d, f"*_{suffix}_trace.npy")))
    return np.load(hits[0]) if hits else None


def mcnemar(a, b):
    a, b = np.asarray(a, bool), np.asarray(b, bool)
    n_disc = int(np.sum(a != b))
    if n_disc == 0:
        return 1.0, 0, 0, 0
    n_ba = int(np.sum((~a) & b))
    n_ab = int(np.sum(a & (~b)))
    return binomtest(n_ba, n_disc, 0.5).pvalue, n_ba, n_ab, n_disc


def series(dirs):
    out = []
    clean = None
    for d in sorted(dirs):
        j = load_summary(dirs[d])
        if j is None:
            out.append({"delta": d, "present": False})
            continue
        ev, at = j["eval_stats"], j["at_retirement_stats"]
        row = {
            "delta": d, "present": True,
            "final_frac": ev["violation_fraction"],
            "at_ret_frac": at["violation_fraction"],
            "at_ret_first": at.get("first_violation_episode"),
            "disagreement": at.get("disagreement_fraction"),
            "mutated": (j.get("poison_stats") or {}).get("mutated_records"),
            "total_delta": (j.get("poison_stats") or {}).get("total_delta"),
        }
        tr = load_trace(dirs[d], "eval")
        if tr is not None and clean is not None and clean[0] is not None:
            p, ab, ba, nd = mcnemar(clean[0], tr)
            row["p"] = p
            row["n_ab"], row["n_ba"], row["n_disc"] = ab, ba, nd
        if d == 0.0:
            clean = (tr, row["final_frac"])
        out.append(row)
    return out


def main():
    print("# Dose-response (protocol v1.7 / B3), transfer-sensitive seed 1, vC")
    for label, dirs in [("FULL-PHASE", FULL_DIRS), ("SHIELD-ON", SHIELDON_DIRS)]:
        rows = series(dirs)
        present = [r for r in rows if r.get("present")]
        print(f"\n## {label}")
        if not present:
            print("no dose dirs present yet (run sync_from_server.sh after server finishes)")
            continue
        hdr = f"{'delta':>6} {'final':>7} {'at-ret':>7} {'disagr':>7} {'p(McN)':>10} {'mutated':>9} {'eff?':>5}"
        print(hdr)
        clean_frac = next(r["final_frac"] for r in rows if r["delta"] == 0.0)
        for r in rows:
            if not r.get("present"):
                print(f"{r['delta']:>6}  (missing)")
                continue
            eff = ""
            if r["delta"] > 0 and "p" in r:
                eff = "Y" if (r["final_frac"] >= clean_frac + 0.15 and r["p"] < 0.01) else "n"
            pstr = f"{r['p']:.2e}" if "p" in r else "n/a"
            print(f"{r['delta']:>6} {r['final_frac']:>7.3f} {r['at_ret_frac']:>7.3f} "
                  f"{r['disagreement']:>7.4f} {pstr:>10} {r['mutated']:>9.0f} {eff:>5}")
        # min effective delta
        effs = [r["delta"] for r in rows if r.get("present") and r["delta"] > 0 and r.get("p") is not None
                and r["final_frac"] >= clean_frac + 0.15 and r["p"] < 0.01]
        print(f"clean final frac = {clean_frac:.3f}; min effective delta = {min(effs) if effs else None}")
        # disagreement monotonicity (descriptive)
        dd = [(r["delta"], r["disagreement"]) for r in rows if r.get("present") and r["delta"] > 0]
        inc = sum(1 for a, b in zip(dd, dd[1:]) if a[1] <= b[1])
        if dd:
            print(f"at-ret disagreement over {len(dd)} positive-delta points: "
                  f"non-decreasing in {inc}/{len(dd)-1} steps "
                  f"(values {[round(x[1],4) for x in dd]})")


if __name__ == "__main__":
    main()
