#!/usr/bin/env python3
"""Analyze v1.10 Part A: SAC retirement-boundary isolation (protocol amendment v1.10.1).

Locked rules (identical to v1.5/v1.6):
  * positive seed = poisoned at-ret >= clean at-ret + 0.15 AND paired McNemar
    exact p < 0.01 (paired at-retirement eval episodes, 1000 eps)
  * verdict (3 paired seeds 401-403):
      >= 2/3 positive -> add a SAC sentence to the Learner-boundary paragraph
                         (off-policy learner variety; NOT "off-policy generality")
      1/3             -> PARTIAL (report per-seed)
      0/3             -> SAC negative boundary (paper states SAC did not reproduce)

Smoke runs (seed 499, `sac_smoke/`, max-runs 2000) are pipeline verification
only and are NEVER included in the battery verdict.

Usage:
  python analyze_sac.py [--out results/sac_report.md] [--include-smoke]
"""
from __future__ import annotations

import argparse, glob, json, os, sys

BASE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results")
DEFAULT_AT_RET_EPS = 1000
ATRET_PATTERNS = [
    "*_at_retirement_trace.npy", "*_atretirement_trace.npy",
    "*_at_ret_trace.npy", "*_atret_trace.npy",
    "*_retirement_trace.npy", "*_ret_trace.npy",
]
POSITIVE_PP = 0.15
POSITIVE_ALPHA = 0.01

SEEDS = list(range(401, 404))
CLEAN_PREFIX = "obstacle_sudden_SAC_none_d2_s"
POIS_PREFIX = "obstacle_sudden_SAC_v3_d2_s"
SMOKE_CLEAN = "obstacle_sudden_SAC_none_d2_s499_smoke"
SMOKE_POIS = "obstacle_sudden_SAC_v3_d2_s499_smoke"


def summary_json(run_dir):
    if not os.path.isdir(run_dir):
        return None
    hits = [f for f in os.listdir(run_dir) if f.endswith("_summary.json")]
    if not hits:
        return None
    return os.path.join(run_dir, sorted(hits)[0])


def load(run_dir):
    jp = summary_json(run_dir)
    if jp is None:
        return None
    with open(jp) as fh:
        return json.load(fh)


def mcnemar_exact(b, c):
    n = b + c
    if n == 0:
        return 1.0
    try:
        from scipy.stats import binomtest
        return float(binomtest(b, n, 0.5, alternative="two-sided").pvalue)
    except ImportError:
        pass
    from math import exp, lgamma, log
    def log_comb(n, k):
        return lgamma(n + 1) - lgamma(k + 1) - lgamma(n - k + 1)
    terms = [log_comb(n, k) - n * log(2.0) for k in range(b, n + 1)]
    mx = max(terms)
    p = exp(mx + log(sum(exp(t - mx) for t in terms)))
    return min(1.0, 2.0 * p)


def atret_trace(s, run_dir):
    for pat in ATRET_PATTERNS:
        hits = sorted(glob.glob(os.path.join(run_dir, pat)))
        if hits:
            import numpy as np
            return np.load(hits[0])
    st = s.get("at_retirement_stats", {})
    for k in ("episode_flags", "episode_violations", "trace", "episode_violation_flags"):
        v = st.get(k)
        if isinstance(v, (list, tuple)) and len(v):
            import numpy as np
            return np.asarray(v, dtype=np.int8)
    return None


def seed_row(clean_dir, pois_dir):
    """Return dict for one paired seed or None if data missing/incomplete."""
    c, p = load(clean_dir), load(pois_dir)
    if c is None or p is None:
        return None
    ca = c["at_retirement_stats"]["violation_fraction"]
    pa = p["at_retirement_stats"]["violation_fraction"]
    cf = c["eval_stats"]["violation_fraction"]
    pf = p["eval_stats"]["violation_fraction"]
    cd = c["at_retirement_stats"].get("disagreement_fraction", float("nan"))
    pd = p["at_retirement_stats"].get("disagreement_fraction", float("nan"))
    cfv = c["at_retirement_stats"].get("first_violation_episode", float("nan"))
    pfv = p["at_retirement_stats"].get("first_violation_episode", float("nan"))
    tc, tp = atret_trace(c, clean_dir), atret_trace(p, pois_dir)
    b = c2 = mcn = None
    if tc is not None and tp is not None:
        n = min(len(tc), len(tp))
        b = int(((tp[:n] == 1) & (tc[:n] == 0)).sum())
        c2 = int(((tc[:n] == 1) & (tp[:n] == 0)).sum())
        mcn = mcnemar_exact(b, c2)
    frac_pos = pa >= ca + POSITIVE_PP
    strict = bool(frac_pos and mcn is not None and mcn < POSITIVE_ALPHA)
    return dict(seed=int(c["cfg"]["seed"]), ca=ca, pa=pa, cf=cf, pf=pf,
                cd=cd, pd=pd, cfv=cfv, pfv=pfv, b=b, c2=c2, mcn=mcn,
                frac_pos=frac_pos, strict=strict)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=None, help="optional markdown report path")
    ap.add_argument("--include-smoke", action="store_true",
                    help="also print the smoke runs (seed 499; never in verdict)")
    args = ap.parse_args()
    out = ["# v1.10 Part A: SAC retirement-boundary isolation (3 paired seeds)",
           "",
           "Protocol: amendment v1.10.1 (2026-08-16). Server vC code, sudden (HARD), "
           "contrast $\\delta$=2, poison scope shield-on, at-retirement eval 1000 eps, "
           "final eval 5000 eps, retirement at env-step $10^5$.",
           "",
           "| seed | clean at-ret | pois at-ret | +delta | clean final | pois final | "
           "disagree c/p | first-viol c/p | discr(b,c) | mcnemar p | positive |",
           "|---|---|---|---|---|---|---|---|---|---|---|"]
    n_pos_strict = n_pos_frac = n_pair = 0
    missing = []
    for s in SEEDS:
        row = seed_row(os.path.join(BASE, f"{CLEAN_PREFIX}{s}"),
                       os.path.join(BASE, f"{POIS_PREFIX}{s}"))
        if row is None:
            missing.append(s)
            out.append(f"| {s} | (pair incomplete) |")
            continue
        n_pair += 1
        n_pos_frac += int(row["frac_pos"])
        n_pos_strict += int(row["strict"])
        mcn = row["mcn"]
        tag = "Y" if row["strict"] else ("Y*" if row["frac_pos"] else "N")
        mcns = f"{mcn:.2e}" if mcn is not None else "-"
        bcs = f"{row['b']},{row['c2']}" if row['b'] is not None else "-"
        out.append(f"| {s} | {row['ca']:.3f} | {row['pa']:.3f} | {row['pa']-row['ca']:+.3f} | "
                   f"{row['cf']:.3f} | {row['pf']:.3f} | {row['cd']:.3f}/{row['pd']:.3f} | "
                   f"{row['cfv']:.0f}/{row['pfv']:.0f} | {bcs} | {mcns} | {tag} |")
    out.append("")
    if missing:
        out.append(f"> Pending pairs (no complete clean+contrast summary): {missing}")
        out.append("")
    n = len(SEEDS)
    basis = "locked rule (fraction + McNemar p<0.01)" if n_pos_strict or not missing \
        else "fraction-only (McNemar pending)"
    n_pos = n_pos_strict if n_pos_strict or not missing else n_pos_frac
    if n_pos >= 2:
        verdict = "POSITIVE (2/3 or 3/3) -> add a SAC sentence to the Learner-boundary paragraph (off-policy learner variety; NOT off-policy generality)"
    elif n_pos == 1:
        verdict = "PARTIAL (1/3) -> report per-seed, no generality sentence"
    else:
        verdict = "NEGATIVE (0/3) -> paper states SAC did not reproduce the retirement-boundary effect"
    out.append(f"**Positive seeds ({basis}): {n_pos}/{n}** "
               f"({n_pos_strict} strict, {n_pos_frac} fraction-only)")
    out.append(f"**Verdict (locked v1.10.1): {verdict}**")
    out.append("")
    out.append("> Positive-seed rule: poisoned at-ret >= clean at-ret + "
               f"{POSITIVE_PP} AND McNemar exact p < {POSITIVE_ALPHA}. "
               "Smoke runs (seed 499, max-runs 2000) are pipeline checks only and "
               "are excluded from the verdict.")
    if args.include_smoke:
        out.append("")
        out.append("### Smoke runs (seed 499, max-runs 2000; pipeline verification only)")
        out.append("")
        out.append("| run | clean at-ret | pois at-ret | +delta | clean final | pois final |")
        out.append("|---|---|---|---|---|---|")
        for label, cd, pd_ in (("clean", SMOKE_CLEAN, None), ("contrast", SMOKE_POIS, None)):
            c = load(os.path.join(BASE, cd))
            p = load(os.path.join(BASE, pd_)) if pd_ else None
            if c is None:
                out.append(f"| {label} | (missing) |")
            elif p is None:
                out.append(f"| {label} | {c['at_retirement_stats']['violation_fraction']:.3f} | - |")
            else:
                out.append(f"| {label} | "
                           f"{c['at_retirement_stats']['violation_fraction']:.3f} | "
                           f"{p['at_retirement_stats']['violation_fraction']:.3f} | "
                           f"{p['at_retirement_stats']['violation_fraction'] - c['at_retirement_stats']['violation_fraction']:+.3f} | "
                           f"{c['eval_stats']['violation_fraction']:.3f} | "
                           f"{p['eval_stats']['violation_fraction']:.3f} |")
    text = "\n".join(out)
    print(text)
    if args.out:
        with open(args.out, "w") as fh:
            fh.write(text + "\n")
        print(f"wrote {args.out}")


if __name__ == "__main__":
    main()
