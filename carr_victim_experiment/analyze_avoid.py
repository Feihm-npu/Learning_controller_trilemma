#!/usr/bin/env python3
"""Avoid-domain (surveillance N=6,RADIUS=3) fidelity + isolation analysis
(protocol amendment v1.8 / B4).

Fidelity gate (v1.8.1): four clean runs, seed 1, 5000 episodes —
  no-shield / retained / sudden / smooth.
  Gate criterion (locked): qualitative ordering shield-retained (0/0)
  < smooth << sudden <= no-shield (matching Carr et al. Table 1).

Isolation battery (v1.8.2, launched only after gate passes): paired
  clean vs contrast (shield-on, delta=2) at seeds 1-3.
  Positive-seed rule (identical to v1.5/v1.6): poisoned at-ret fraction
  >= clean at-ret fraction + 0.15 AND paired McNemar exact p < 0.01.
  Generality: 3/3 = reproduced, 2/3 = partial, <2/3 = not reproduced.

Run after sync_from_server.sh:
  ../.venv-safe-control/bin/python carr_victim_experiment/analyze_avoid.py
"""
import json, os, glob
import numpy as np
from scipy.stats import binomtest

BASE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results")
POSITIVE_PP = 0.15
POSITIVE_ALPHA = 0.01

FID_DIRS = {
    "noshield": "avoid_noshield_s1_fid",
    "retained": "avoid_retained_s1_fid",
    "sudden": "avoid_sudden_s1_fid",
    "smooth": "avoid_smooth_s1_fid",
}
ISO_CLEAN = {s: f"avoid_sudden_REINFORCE_none_d2_s{s}" for s in (1, 2, 3)}
ISO_POIS = {s: f"avoid_sudden_REINFORCE_v3_d2_s{s}" for s in (1, 2, 3)}


def load_summary(d):
    jp = glob.glob(os.path.join(BASE, d, "*_summary.json"))
    if not jp:
        return None
    with open(sorted(jp)[0]) as f:
        return json.load(f)


def load_trace(d, suffix):
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


def fid_gate():
    print("# Avoid-domain fidelity gate (v1.8.1, clean, seed 1)")
    print(f"{'mode':>9} {'during':>7} {'after':>7} {'at-ret':>7} | 'frac'")
    rows = {}
    for mode, d in FID_DIRS.items():
        j = load_summary(d)
        if j is None:
            print(f"{mode:>9}  MISSING {d}")
            continue
        ev = j["eval_stats"]
        at = j.get("at_retirement_stats") or {}
        during = j["during_violations"]
        after = ev["num_violations"]
        at_ret = at.get("num_violations", float("nan"))
        rows[mode] = (during, after, at_ret)
        print(f"{mode:>9} {during:>7} {after:>7} {at_ret:>7.0f}  "
              f"({after/5000:.3f})")
    if not rows:
        print("no fidelity dirs present yet")
        return False
    # qualitative ordering check
    ok = True
    if "retained" in rows and rows["retained"][1] > 0:
        ok = False
    if "smooth" in rows and "sudden" in rows:
        if not (rows["smooth"][1] <= rows["sudden"][1]):
            ok = False
    if "sudden" in rows and "noshield" in rows:
        if not (rows["sudden"][1] <= rows["noshield"][1]):
            ok = False
    print(f"\nGate verdict: {'PASS' if ok else 'CHECK'} "
          f"(retained=0, smooth<=sudden<=noshield)")
    return ok


def iso_battery():
    print("\n# Avoid-domain shield-on isolation (v1.8.2, contrast delta=2)")
    print(f"{'seed':>4} {'clean@ret':>9} {'pois@ret':>9} {'cleanFin':>9} {'poisFin':>9} "
          f"{'p(McN)':>10} {'pos?':>4}")
    n_pos = 0
    for s in (1, 2, 3):
        cd, pd = ISO_CLEAN[s], ISO_POIS[s]
        c, p = load_summary(cd), load_summary(pd)
        if c is None or p is None:
            print(f"{s:>4}  MISSING ({cd if c is None else pd})")
            continue
        ca = c["at_retirement_stats"]["violation_fraction"]
        pa = p["at_retirement_stats"]["violation_fraction"]
        cf = c["eval_stats"]["violation_fraction"]
        pf = p["eval_stats"]["violation_fraction"]
        tc, tp = load_trace(cd, "at_retirement"), load_trace(pd, "at_retirement")
        mcn = None
        if tc is not None and tp is not None:
            n = min(len(tc), len(tp))
            mcn, _, _, _ = mcnemar(tc[:n], tp[:n])
        frac_pos = pa >= ca + POSITIVE_PP
        strict = bool(frac_pos and mcn is not None and mcn < POSITIVE_ALPHA)
        n_pos += int(strict)
        pstr = f"{mcn:.2e}" if mcn is not None else "n/a"
        print(f"{s:>4} {ca:>9.3f} {pa:>9.3f} {cf:>9.3f} {pf:>9.3f} {pstr:>10} "
              f"{'Y' if strict else ('Y*' if frac_pos else 'N')}")
    print(f"\nPositive seeds: {n_pos}/3 -> "
          f"{'REPRODUCED (generality)' if n_pos == 3 else 'PARTIAL (2/3)' if n_pos == 2 else 'NOT REPRODUCED (<2/3)'}")


if __name__ == "__main__":
    passed = fid_gate()
    iso_battery()
    print("\n(Isolation battery launches only after fidelity gate passes; "
          "both report regardless of presence.)")
