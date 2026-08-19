#!/usr/bin/env python3
"""fullvC (protocol v1.4) full-phase REINFORCE re-verification on current code (vC).

The paper's "Attack budget and susceptibility" paragraph currently reports the vA
full-phase numbers (1127->3762, etc.).  vC is instrumented code; absolute fractions
differ across versions.  This script recomputes the full-phase table on vC data so the
paper can report current-code numbers, and flags qualitative deviations from the
locked pattern:
  - contrast d2: effective on seed 2 (large post-removal rise), no effect on s1/s3-d2
  - contrast d10: effective on s2 and s3
  - risk d2: strictly weaker than contrast on s2 (or protective)
  - constant d2 (bias): protective on the ceiling seed, never raising violations

Run after sync_from_server.sh: ../.venv-safe-control/bin/python carr_victim_experiment/analyze_fullvC.py
"""
import json, os, sys
import numpy as np
from scipy.stats import binomtest

BASE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results")
import glob
VNAME = "obstacle-6-computed-shield_VICTIM"
SEEDS = [1, 2, 3]
POISONS = ["none", "constant", "risk", "contrast_d2", "contrast_d10"]
PN = {"none": ("clean", 0.0), "constant": ("constant", 2.0), "risk": ("risk", 2.0),
      "contrast_d2": ("contrast", 2.0), "contrast_d10": ("contrast", 10.0)}


def run_dir(poison, seed):
    if poison == "contrast_d2":
        base = "obstacle_sudden_REINFORCE_contrast_d2_s%d_fullvC" % seed
    elif poison == "contrast_d10":
        base = "obstacle_sudden_REINFORCE_contrast_d10_s%d_fullvC" % seed
    else:
        base = f"obstacle_sudden_REINFORCE_{poison}_d2_s{seed}_fullvC"
    return os.path.join(BASE, base)


def load(poison, seed):
    d = run_dir(poison, seed)
    jp = glob.glob(os.path.join(d, "*_summary.json"))
    if not jp:
        return None
    with open(sorted(jp)[0]) as f:
        return json.load(f)


def trace(poison, seed):
    d = run_dir(poison, seed)
    hits = sorted(glob.glob(os.path.join(d, "*_eval_trace.npy")))
    return np.load(hits[0]) if hits else None


def mcnemar(a, b):
    a, b = np.asarray(a, bool), np.asarray(b, bool)
    n_disc = int(np.sum(a != b))
    if n_disc == 0:
        return 1.0, 0, 0
    n_ba = int(np.sum((~a) & b))
    n_ab = int(np.sum(a & (~b)))
    return binomtest(n_ba, n_disc, 0.5).pvalue, n_ba, n_ab


def frac(stats):
    return (stats or {}).get("violation_fraction")


def main():
    have = [p for p in POISONS if any(load(p, s) for s in SEEDS)]
    if not have:
        print("no fullvC summaries present yet (run sync_from_server.sh after server finishes)")
        return
    # header
    print("fullvC full-phase (REINFORCE, vC code) per-seed table")
    print("| poison | seed | during | after(eval) | after_frac | at-ret_frac | first |")
    data = {}
    for poison in POISONS:
        for seed in SEEDS:
            j = load(poison, seed)
            if j is None:
                continue
            es = j.get("eval_stats") or {}
            ar = j.get("at_retirement_stats") or {}
            data[(poison, seed)] = (j, trace(poison, seed))
            print(f"| {poison} | {seed} | {j.get('during_violations')} | "
                  f"{es.get('num_violations')} | {frac(es):.3f} | {frac(ar):.3f} | "
                  f"{es.get('first_violation_episode')} |")
    # paired tests vs clean, per seed
    print("\npaired McNemar exact (eval traces, 5000 paired episodes), poisoned vs clean:")
    for seed in SEEDS:
        cj, ct = data.get(("none", seed), (None, None))
        if ct is None:
            continue
        print(f" seed {seed}:")
        for poison in ["constant", "risk", "contrast_d2", "contrast_d10"]:
            pj, pt = data.get((poison, seed), (None, None))
            if pt is None:
                print(f"   {poison}: trace missing")
                continue
            pv, nb, na = mcnemar(ct, pt)
            ce, pe = (cj.get("eval_stats") or {}).get("num_violations"), (pj.get("eval_stats") or {}).get("num_violations")
            print(f"   {poison}: clean {ce} -> poison {pe} "
                  f"(+{pe - ce:+d}); McNemar p={pv:.3g} (poison-only-disc {nb}, clean-only {na})")
    # qualitative guard
    print("\nqualitative guard:")
    for seed in SEEDS:
        ce = ((data.get(("none", seed), (None, None))[0]) or {}).get("eval_stats") or {}
        ce_v = ce.get("num_violations")
        row = []
        for poison in ["contrast_d2", "contrast_d10"]:
            e = ((data.get((poison, seed), (None, None))[0]) or {}).get("eval_stats") or {}
            row.append(f"{poison}:{e.get('num_violations')}")
        print(f"  seed {seed} clean={ce_v} | " + " ".join(row))


if __name__ == "__main__":
    main()
