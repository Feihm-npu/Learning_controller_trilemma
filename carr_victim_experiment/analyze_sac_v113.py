#!/usr/bin/env python3
"""Analyze pooled SAC retirement-boundary isolation (protocol amendment v1.13).

Pools seeds 401-406 (amendments v1.10.1/v1.12) + 407-410 (amendment v1.13,
server results/sac_v113) into a single ten-seed SAC isolation table, applies
the locked v1.13.3 decision rule, and runs the pre-registered mechanism
analysis (clean disagreement cd vs attack headroom).

Locked v1.13.3 decision rule:
  * positive seed = poisoned at-ret >= clean at-ret + 0.15 AND
    paired McNemar exact p < 0.01  (unchanged from v1.5.4 / v1.10.1)
  * pooled verdict (401-410):
       >= 6/10 -> "reproduces on N/10 SAC seeds (off-policy learner variety,
                   not off-policy generality)"
       4-5/10  -> "partial across ten SAC seeds: the off-policy learner-variety
                   claim is qualified to a subset of seeds"
       < 4/10  -> "SAC learner-variety evidence weakens (N/10): the off-policy
                   learner-variety claim is not supported at scale"
  * 2x2 cross-tabulation recomputed with the four new SAC rows (SAC n=10).

Pre-registered mechanism analysis (v1.13.3):
  1. cd = clean at-retirement disagreement_fraction; h = poisoned - clean
     at-retirement headroom, per paired seed, pooled over SAC 401-410.
  2. Spearman(cd, h) and Spearman(clean at-ret fraction, h) on the pooled
     namespace.
  3. Dichotomize by cd: low = cd < 0.06, high = cd >= 0.09; the 0.06-0.09
     band is reported but not dichotomized.  Expected: low-cd seeds
     reproduce (positive/protective mixture), high-cd seeds are ceiling.

Usage:
  ../.venv-safe-control/bin/python carr_victim_experiment/analyze_sac_v113.py [--out results/sac_report.md]
"""
from __future__ import annotations

import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import numpy as np
from scipy.stats import spearmanr

from analyze_fullphase import (
    BASE, POSITIVE_PP, POSITIVE_ALPHA, seed_row,
)
from susceptibility_corpus import susceptibility_2x2 as canonical_2x2

SAC_SEEDS = list(range(401, 411))  # 401-406 (v1.10/v1.12) + 407-410 (v1.13)
CLEAN_PREFIX = "obstacle_sudden_SAC_none_d2_s"
POIS_PREFIX = "obstacle_sudden_SAC_v3_d2_s"

LOW_CD, HIGH_CD = 0.06, 0.09  # locked v1.13.3 dichotomization bands


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


def mechanism_rows(rows):
    """Pre-registered v1.13.3 mechanism inputs over pooled SAC 401-410."""
    out = []
    for s, r in rows:
        if not np.isfinite(r["cd"]):
            continue
        out.append((s, r["ca"], r["cd"], r["pa"] - r["ca"], r["strict"]))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=None, help="optional markdown report path")
    args = ap.parse_args()

    rows = sac_rows()
    n_pooled = len(SAC_SEEDS)
    complete = [r for r in rows if r[1]["strict"] is not None]

    out = ["# v1.10+v1.12+v1.13 pooled SAC retirement-boundary isolation "
           "(10-seed namespace, seeds 401-410)",
           "",
           "Protocol: amendments v1.10.1 + v1.12 + v1.13 (2026-08-17). Server vC "
           "code, sudden (HARD), contrast $\\delta$=2, poison scope shield-on, "
           "at-retirement eval 1000 eps, final eval 5000 eps, retirement at "
           "env-step $10^5$.  Seeds 407-410 run on a Linux host with identical "
           "dependency versions (same locked config as v1.12.1).",
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
    out.append(f"**Positive seeds (locked rule): {n_pos}/{n_pooled}** "
               f"({len(rows)} pairs complete)"
               + (f"; missing: {missing}" if missing else "") + ".")
    out.append("")

    if n_pos >= 6:
        verdict = (f"POOLED (v1.13.3) -> reproduces on {n_pos}/10 SAC seeds "
                   "(off-policy learner variety, not off-policy generality)")
    elif n_pos >= 4:
        verdict = (f"POOLED (v1.13.3) -> partial across ten SAC seeds "
                   f"({n_pos}/10): the off-policy learner-variety claim is "
                   "qualified to a subset of seeds")
    else:
        verdict = (f"POOLED (v1.13.3) -> SAC learner-variety evidence weakens "
                   f"({n_pos}/10): the off-policy learner-variety claim is not "
                   "supported at scale")
    out.append(f"**Verdict: {verdict}**")
    out.append("")
    out.append("> Positive-seed rule: poisoned at-ret >= clean at-ret + "
               f"{POSITIVE_PP} AND McNemar exact p < {POSITIVE_ALPHA}. "
               "Smoke runs (seed 499) are pipeline checks only and are excluded.")

    # ---- pre-registered mechanism analysis (v1.13.3) ----
    mech = mechanism_rows(rows)
    out.append("")
    out.append("### Pre-registered mechanism analysis (v1.13.3, pooled SAC 401-410)")
    out.append("")
    if len(mech) < 3:
        out.append("(insufficient finite-disagreement rows for the mechanism "
                   "analysis; pending sync of seeds 407-410)")
    else:
        seeds = np.array([m[0] for m in mech])
        ca = np.array([m[1] for m in mech])
        cd = np.array([m[2] for m in mech])
        hr = np.array([m[3] for m in mech])
        strict = np.array([m[4] for m in mech], dtype=bool)
        out.append("| seed | clean at-ret | cd | headroom | positive | cd band |")
        out.append("|---|---|---|---|---|---|")
        for m in mech:
            s_, ca_, cd_, hr_, st_ = m
            band = ("low (<0.06)" if cd_ < LOW_CD else
                    "high (>=0.09)" if cd_ >= HIGH_CD else "band (0.06-0.09)")
            out.append(f"| {s_} | {ca_:.3f} | {cd_:.3f} | {hr_:+.3f} | "
                       f"{'Y' if st_ else 'N'} | {band} |")
        rho_cd, p_cd = spearmanr(cd, hr)
        rho_ca, p_ca = spearmanr(ca, hr)
        out.append("")
        out.append(f"Spearman(cd, headroom) = {rho_cd:.3f} (p={p_cd:.2e}) over "
                   f"{len(mech)} pooled SAC rows.")
        out.append(f"Spearman(clean at-ret, headroom) = {rho_ca:.3f} "
                   f"(p={p_ca:.2e}).")
        low = cd < LOW_CD
        high = cd >= HIGH_CD
        n_low_pos = int((low & strict).sum())
        n_low = int(low.sum())
        n_high_pos = int((high & strict).sum())
        n_high = int(high.sum())
        band_sel = ~low & ~high
        n_band = int(band_sel.sum())
        out.append(f"Dichotomized (bands locked: low cd<{LOW_CD}, high "
                   f"cd>={HIGH_CD}): {n_low_pos}/{n_low} low-cd seeds positive, "
                   f"{n_high_pos}/{n_high} high-cd seeds positive"
                   + (f", {n_band} in the {LOW_CD}-{HIGH_CD} band (reported, "
                      "not dichotomized)" if n_band else "") + ".")
        out.append("")
        out.append("Expected reading (v1.13.3): low-cd SAC seeds reproduce "
                   "(positive/protective mixture on clean-at-ret ~0.2 vs "
                   "ambiguous ~0.5 boundary seeds), high-cd seeds are ceiling "
                   "and do not reproduce.")

    if not missing:
        x = susceptibility_2x2()
        out.append("")
        out.append("### Recomputed 2x2 susceptibility cross-tabulation "
                   "(incl. SAC 401-410, SAC isolation n=10)")
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
