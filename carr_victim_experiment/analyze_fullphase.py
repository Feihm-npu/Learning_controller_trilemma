#!/usr/bin/env python3
"""Analyze v1.9 full-phase attack at scale (PPO + REINFORCE 10-seed batteries).

Reads per-run `*_summary.json` + `*_at_retirement_trace.npy` for paired clean /
contrast runs and applies the locked v1.9.3 rules:
  * positive seed = poisoned at-ret fraction >= clean at-ret fraction + 0.15
    AND paired McNemar exact p < 0.01 (paired at-retirement eval episodes)
  * decision rule (10 seeds/learner) = REPRODUCES >= 5/10; PARTIAL 3-4/10;
    NOT REPRODUCED < 3/10.
Also prints the locked 2x2 susceptibility cross-tabulation
({clean at-ret < 0.5} x {positive}) across v1.9 + v1.5 + v1.6 + v1.8 + v1.10 (SAC).

Run dirs (server vC code, `_fullvC` suffix):
  obstacle_sudden_PPO_{none,v3}_d2_s{101..110}_fullvC
  obstacle_sudden_REINFORCE_{none,v3}_d2_s{201..210}_fullvC

Usage:
  python analyze_fullphase.py [--out results/fullphase_report.md]
"""
from __future__ import annotations

import argparse, glob, json, os, sys

from susceptibility_corpus import append_markdown, susceptibility_2x2 as canonical_2x2

BASE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results")
DEFAULT_AT_RET_EPS = 1000
ATRET_PATTERNS = [
    "*_at_retirement_trace.npy", "*_atretirement_trace.npy",
    "*_at_ret_trace.npy", "*_atret_trace.npy",
    "*_retirement_trace.npy", "*_ret_trace.npy",
]
POSITIVE_PP = 0.15
POSITIVE_ALPHA = 0.01

BATTERIES = {
    "PPO":       dict(seeds=range(101, 111), clean="obstacle_sudden_PPO_none_d2_s",          pois="obstacle_sudden_PPO_v3_d2_s"),
    "REINFORCE": dict(seeds=range(201, 211), clean="obstacle_sudden_REINFORCE_none_d2_s",    pois="obstacle_sudden_REINFORCE_v3_d2_s"),
}

# v1.8 avoid-domain isolation rows (already complete locally) for the 2x2.
AVOID_ROWS = [
    # seed, clean_at_ret, poison_at_ret, positive
    (1, 0.267, 0.000, False),
    (2, 0.000, 0.272, True),
    (3, 0.135, 0.038, False),
]

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

def analyze_battery(learner, cfg, out_lines):
    seeds = cfg["seeds"]
    n_pos_frac, n_pos_strict, n_pair, missing = 0, 0, 0, []
    rows = []
    hdr = (f"### v1.9 full-phase {learner} (10 seeds, sudden, contrast $\\delta$=2, "
           f"scope=full, vC)")
    out_lines.append(hdr)
    out_lines.append("")
    out_lines.append("| seed | clean at-ret | pois at-ret | +delta | clean final | pois final | "
                     "disagree c/p | first-viol c/p | discr(b,c) | mcnemar p | positive |")
    out_lines.append("|---|---|---|---|---|---|---|---|---|---|---|")
    for s in seeds:
        cdir = os.path.join(BASE, f"{cfg['clean']}{s}_fullvC")
        pdir = os.path.join(BASE, f"{cfg['pois']}{s}_fullvC")
        row = seed_row(cdir, pdir)
        if row is None:
            missing.append(s)
            out_lines.append(f"| {s} | (pair incomplete) |")
            continue
        rows.append(row)
        n_pair += 1
        n_pos_frac += int(row["frac_pos"])
        n_pos_strict += int(row["strict"])
        mcn = row["mcn"]
        tag = "Y" if row["strict"] else ("Y*" if row["frac_pos"] else "N")
        mcns = f"{mcn:.2e}" if mcn is not None else "-"
        bcs = f"{row['b']},{row['c2']}" if row['b'] is not None else "-"
        out_lines.append(
            f"| {s} | {row['ca']:.3f} | {row['pa']:.3f} | {row['pa']-row['ca']:+.3f} | "
            f"{row['cf']:.3f} | {row['pf']:.3f} | {row['cd']:.3f}/{row['pd']:.3f} | "
            f"{row['cfv']:.0f}/{row['pfv']:.0f} | {bcs} | {mcns} | {tag} |")
    out_lines.append("")
    if missing:
        out_lines.append(f"> Pending pairs (no complete clean+contrast summary): {missing}")
        out_lines.append("")
    n = len(seeds)
    if n_pos_strict or not missing:
        n_pos = n_pos_strict
        basis = "locked rule (fraction + McNemar p<0.01)"
        if missing:
            out_lines.append(f"> {len(missing)}/{n} pairs still incomplete; verdict basis may "
                             "change as runs finish.")
            out_lines.append("")
    else:
        n_pos = n_pos_frac
        basis = "fraction-only (McNemar pending)"
    verdict = ("REPRODUCES" if n_pos >= 5 else "PARTIAL" if n_pos >= 3 else "NOT REPRODUCED")
    out_lines.append(f"**Positive seeds ({basis}): {n_pos}/{n}** "
                     f"({n_pos_strict} strict, {n_pos_frac} fraction-only) "
                     f"-> **{verdict}** (reproduce>=5/10, partial 3-4/10, no<3/10).")
    out_lines.append("")
    return dict(learner=learner, n_pos_strict=n_pos_strict, n_pos_frac=n_pos_frac,
                n_pair=n_pair, missing=missing, verdict=verdict, rows=rows)

def susceptibility_2x2(out_lines):
    """Append the canonical 53-run cross-tabulation."""
    cells = canonical_2x2(BASE, seed_row)
    append_markdown(out_lines, cells)
    return cells

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=None, help="optional markdown report path")
    args = ap.parse_args()
    out_lines = ["# v1.9 full-phase at scale (PPO + REINFORCE, 10-seed batteries)",
                 "",
                 "Protocol: amendment v1.9 (2026-08-16). All runs server vC code, "
                 "sudden (HARD), contrast $\\delta$=2, scope=full.",
                 ""]
    results = {}
    for learner, cfg in BATTERIES.items():
        results[learner] = analyze_battery(learner, cfg, out_lines)
        out_lines.append("")
    susceptibility_2x2(out_lines)
    text = "\n".join(out_lines)
    print(text)
    if args.out:
        with open(args.out, "w") as fh:
            fh.write(text + "\n")
        print(f"wrote {args.out}")

if __name__ == "__main__":
    main()
