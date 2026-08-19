#!/usr/bin/env python3
"""Analyze pooled SAC retirement-boundary isolation (protocol amendment v1.12).

Pools seeds 401-403 (amendment v1.10.1) + 404-406 (amendment v1.12, server
results/sac_v112) into a single six-seed SAC isolation table, then applies the
locked v1.12.3 decision rule:

  * positive seed = poisoned at-ret >= clean at-ret + 0.15 AND
    paired McNemar exact p < 0.01  (unchanged from v1.5.4 / v1.10.1)
  * pooled verdict:
       >= 4/6 -> "reproduces on N/6 SAC seeds (off-policy learner variety,
                  not off-policy generality)"
       3/6    -> "three of six SAC seeds positive (2/3 first battery, 1/3
                  extension): learner variety partial across seeds"
       < 3/6  -> "SAC isolation partial (N/6): off-policy learner-variety
                  claim weakened accordingly"

Also prints the recomputed 2x2 susceptibility cross-tabulation with the new
SAC rows (paper Reading paragraph + fig8 data).

Usage:
  ../.venv-safe-control/bin/python carr_victim_experiment/analyze_sac_v112.py [--out results/sac_report.md]
"""
from __future__ import annotations

import argparse, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from analyze_fullphase import (
    BASE, POSITIVE_PP, POSITIVE_ALPHA, seed_row,
)
from susceptibility_corpus import susceptibility_2x2 as canonical_2x2

SAC_SEEDS = list(range(401, 407))
CLEAN_PREFIX = "obstacle_sudden_SAC_none_d2_s"
POIS_PREFIX = "obstacle_sudden_SAC_v3_d2_s"


def sac_rows():
    rows = []
    for s in SAC_SEEDS:
        r = seed_row(os.path.join(BASE, f"{CLEAN_PREFIX}{s}"),
                     os.path.join(BASE, f"{POIS_PREFIX}{s}"))
        if r is None:
            continue
        rows.append((s, r))
    return rows


def collect(category, clean_prefix, pois_prefix, seeds, suffix=""):
    out = []
    for s in seeds:
        r = seed_row(os.path.join(BASE, f"{clean_prefix}{s}{suffix}"),
                     os.path.join(BASE, f"{pois_prefix}{s}{suffix}"))
        if r is not None:
            out.append((category, r["ca"], r["strict"]))
    return out


def susceptibility_2x2():
    """Return the canonical 53-run cross-tabulation, including SAC 401--410."""
    return canonical_2x2(BASE, seed_row)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=None, help="optional markdown report path")
    args = ap.parse_args()

    rows = sac_rows()
    out = ["# v1.10+v1.12 pooled SAC retirement-boundary isolation "
           "(6-seed namespace, seeds 401-406)",
           "",
           "Protocol: amendments v1.10.1 + v1.12 (2026-08-16). Server vC code, "
           "sudden (HARD), contrast $\\delta$=2, poison scope shield-on, "
           "at-retirement eval 1000 eps, final eval 5000 eps, retirement at "
           "env-step $10^5$.",
           "",
           "| seed | clean at-ret | pois at-ret | +delta | clean final | pois final | "
           "disagree c/p | first-viol c/p | discr(b,c) | mcnemar p | positive |",
           "|---|---|---|---|---|---|---|---|---|---|---|"]
    n_pos = 0
    missing = [s for s in SAC_SEEDS if s not in {r[0] for r in rows}]
    for s, r in rows:
        n_pos += int(r["strict"])
        tag = "Y" if r["strict"] else ("Y*" if r["frac_pos"] else "N")
        mcns = f"{r['mcn']:.2e}" if r["mcn"] is not None else "-"
        bcs = f"{r['b']},{r['c2']}" if r["b"] is not None else "-"
        out.append(
            f"| {s} | {r['ca']:.3f} | {r['pa']:.3f} | {r['pa']-r['ca']:+.3f} | "
            f"{r['cf']:.3f} | {r['pf']:.3f} | {r['cd']:.3f}/{r['pd']:.3f} | "
            f"{r['cfv']:.0f}/{r['pfv']:.0f} | {bcs} | {mcns} | {tag} |")
    for s in missing:
        out.append(f"| {s} | (pair incomplete) |")
    out.append("")
    out.append(f"**Positive seeds (locked rule): {n_pos}/{len(SAC_SEEDS)}** "
               f"({len(rows)} pairs complete)"
               + (f"; missing: {missing}" if missing else "") + ".")
    out.append("")
    if n_pos >= 4:
        verdict = (f"POOLED (v1.12.3) -> reproduces on {n_pos}/6 SAC seeds "
                   "(off-policy learner variety, not off-policy generality)")
    elif n_pos == 3:
        verdict = ("POOLED (v1.12.3) -> three of six SAC seeds positive "
                   "(2/3 first battery, 1/3 extension): learner variety is "
                   "partial across seeds")
    else:
        verdict = (f"POOLED (v1.12.3) -> SAC isolation is partial ({n_pos}/6): "
                   "the off-policy learner-variety claim is weakened accordingly")
    out.append(f"**Verdict: {verdict}**")
    out.append("")
    out.append("> Positive-seed rule: poisoned at-ret >= clean at-ret + "
               f"{POSITIVE_PP} AND McNemar exact p < {POSITIVE_ALPHA}. "
               "Smoke runs (seed 499) are pipeline checks only and are excluded.")
    if not missing:
        x = susceptibility_2x2()
        out.append("")
        out.append("### Recomputed 2x2 susceptibility cross-tabulation "
                   "(canonical corpus, incl. SAC 401-410)")
        out.append("")
        out.append("| | positive | not positive |")
        out.append("|---|---|---|")
        out.append(f"| clean at-ret < 0.5 | {x['lo_pos']} | {x['lo_neg']} |")
        out.append(f"| clean at-ret >= 0.5 | {x['hi_pos']} | {x['hi_neg']} |")
        out.append("")
        out.append(f"> Rows: {x['n']} paired seeds across all locked batteries "
                   "(full-phase + isolation, all learners, both domains).")

    text = "\n".join(out)
    print(text)
    if args.out:
        with open(args.out, "w") as fh:
            fh.write(text + "\n")
        print(f"wrote {args.out}")


if __name__ == "__main__":
    main()
