#!/usr/bin/env python3
"""Analyze P0' PPO retirement-boundary isolation (protocol amendment v1.5).

Reads per-run `*_summary.json` for paired clean and poisoned runs and applies
the locked v1.5.4 rules:
  * positive seed = poisoned at-ret fraction >= clean at-ret fraction + 0.15
    AND paired McNemar exact p < 0.01 (paired at-retirement eval episodes)
  * decision rule (10 seeds) = REPRODUCES >= 5/10; PARTIAL 3-4/10;
    NOT REPRODUCED < 3/10.

Sanity mode (default) runs the same pipeline on the REINFORCE vC isolation
data used in the paper (seeds 1-3) and must report 3/3 positive.

Usage:
  python analyze_ppo_isolation.py             # REINFORCE vC sanity check (seeds 1-3)
  python analyze_ppo_isolation.py --ppo       # PPO v1.5 battery (seeds 101-110)
  python analyze_ppo_isolation.py --ppo --out results/ppo_isolation_report.md
"""
import argparse, glob, json, os, sys

BASE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results")
DEFAULT_AT_RET_EPS = 1000  # v1.3 / v1.5 locked: at-retirement eval = 1000 episodes

# explicit at-retirement per-episode trace naming patterns (in priority order).
# The final eval trace (`*_eval_trace.npy`, 5000 eps) must NEVER be matched here.
ATRET_PATTERNS = [
    "*_at_retirement_trace.npy", "*_atretirement_trace.npy",
    "*_at_ret_trace.npy", "*_atret_trace.npy",
    "*_retirement_trace.npy", "*_ret_trace.npy",
]

POSITIVE_PP = 0.15       # locked: poisoned >= clean + 15 pp
POSITIVE_ALPHA = 0.01    # locked: McNemar exact p < 0.01


def summary_json(run_dir):
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
    """Two-sided exact McNemar on discordant counts b (poison-only) / c (clean-only)."""
    n = b + c
    if n == 0:
        return 1.0
    try:
        from scipy.stats import binomtest
        return float(binomtest(b, n, 0.5, alternative="two-sided").pvalue)
    except ImportError:
        pass
    # log-space exact fallback (stable for n up to 10^4+; scipy is preferred)
    from math import exp, lgamma, log
    def log_comb(n, k):
        return lgamma(n + 1) - lgamma(k + 1) - lgamma(n - k + 1)
    terms = [log_comb(n, k) - n * log(2.0) for k in range(b, n + 1)]
    mx = max(terms)
    p = exp(mx + log(sum(exp(t - mx) for t in terms)))
    return min(1.0, 2.0 * p)


def at_ret_eps(s):
    """Expected at-retirement eval length from cfg, else locked default."""
    cfg = s.get("cfg", {})
    for k in ("at_retirement_eps", "at_ret_episodes"):
        if k in cfg:
            return int(cfg[k])
    return DEFAULT_AT_RET_EPS


def atret_trace(s, run_dir):
    """Return per-episode at-retirement binary violation vector or None.

    Sources, in order: (1) explicit at-ret trace file; (2) a vector embedded in
    the summary under at_retirement_stats; (3) a *.npy whose length equals the
    expected at-ret episode count.  Never returns the final-eval trace.
    """
    npy_glob = os.path.join(run_dir, "*.npy")
    existing = {os.path.basename(p) for p in glob.glob(npy_glob)}

    for pat in ATRET_PATTERNS:
        hits = sorted(glob.glob(os.path.join(run_dir, pat)))
        if hits:
            import numpy as np
            return np.load(hits[0])

    # embedded vector in summary
    st = s.get("at_retirement_stats", {})
    for k in ("episode_flags", "episode_violations", "trace", "episode_violation_flags"):
        v = st.get(k)
        if isinstance(v, (list, tuple)) and len(v):
            import numpy as np
            return np.asarray(v, dtype=np.int8)

    # length-matched fallback: only if a run dir has a single *.npy of the
    # exact expected at-ret length (won't match the 5000-ep final eval trace)
    eps = at_ret_eps(s)
    for f in sorted(existing):
        try:
            import numpy as np
            t = np.load(os.path.join(run_dir, f))
        except Exception:
            continue
        if getattr(t, "shape", (0,)) and t.shape[0] == eps:
            return t
    return None


def analyze(learner, seeds, clean_prefix, pois_prefix, require_mcnemar_for_verdict=True):
    import numpy as np
    print(f"# {learner} retirement-boundary isolation")
    print(f"| seed | clean at-ret | pois at-ret | +delta | clean final | pois final | "
          f"at-ret discr c/p | first-viol c/p | discr(b,c) | mcnemar p | positive |")
    print("|---|---|---|---|---|---|---|---|---|---|---|")
    n_pos_strict, n_pos_frac, missing_mcn = 0, 0, 0
    rows = []
    for s in seeds:
        clean_dir = os.path.join(BASE, f"{clean_prefix}{s}")
        pois_dir = os.path.join(BASE, f"{pois_prefix}{s}")
        if not (os.path.isdir(clean_dir) and os.path.isdir(pois_dir)):
            print(f"| {s} | MISSING DIR {clean_dir if not os.path.isdir(clean_dir) else pois_dir} |")
            missing_mcn += 1
            rows.append(None)
            continue
        c, p = load(clean_dir), load(pois_dir)
        if c is None or p is None:
            print(f"| {s} | MISSING SUMMARY "
                  f"({clean_dir if c is None else pois_dir}) |")
            missing_mcn += 1
            rows.append(None)
            continue
        ca = c["at_retirement_stats"]["violation_fraction"]
        pa = p["at_retirement_stats"]["violation_fraction"]
        cf = c["eval_stats"]["violation_fraction"]
        pf = p["eval_stats"]["violation_fraction"]
        cd = c["at_retirement_stats"].get("disagreement_fraction", float("nan"))
        pd = p["at_retirement_stats"].get("disagreement_fraction", float("nan"))
        cfv = c["at_retirement_stats"].get("first_violation_episode", float("nan"))
        pfv = p["at_retirement_stats"].get("first_violation_episode", float("nan"))

        b = c2 = None
        mcn = None
        tc, tp = atret_trace(c, clean_dir), atret_trace(p, pois_dir)
        if tc is not None and tp is not None:
            n = min(len(tc), len(tp))
            b = int(((tp[:n] == 1) & (tc[:n] == 0)).sum())
            c2 = int(((tc[:n] == 1) & (tp[:n] == 0)).sum())
            mcn = mcnemar_exact(b, c2)

        frac_pos = pa >= ca + POSITIVE_PP
        if mcn is not None:
            strict = frac_pos and mcn < POSITIVE_ALPHA
        else:
            strict = False
            missing_mcn += 1
        n_pos_frac += int(frac_pos)
        n_pos_strict += int(strict)
        tag = "Y" if strict else ("Y*" if frac_pos else "N")
        rows.append((s, ca, pa, pa - ca, cf, pf, cd, pd, cfv, pfv, b, c2, mcn, frac_pos, strict, tag))
        print(f"| {s} | {ca:.3f} | {pa:.3f} | {pa-ca:+.3f} | {cf:.3f} | {pf:.3f} | "
              f"{cd:.3f}/{pd:.3f} | {cfv:.0f}/{pfv:.0f} | "
              f"{b},{c2} | {mcn:.2e} | {tag} |" if mcn is not None else
              f"| {s} | {ca:.3f} | {pa:.3f} | {pa-ca:+.3f} | {cf:.3f} | {pf:.3f} | "
              f"{cd:.3f}/{pd:.3f} | {cfv:.0f}/{pfv:.0f} | "
              f"- | - | {tag} |")

    # ---- locked decision rule ----
    n = len(seeds)
    n_eff = n - sum(1 for r in rows if r is None)
    if require_mcnemar_for_verdict and missing_mcn:
        print(f"\n[WARNING] {missing_mcn}/{n} seeds lack paired at-retirement "
              f"episode traces -> McNemar exact unavailable; locked rule not fully applied. "
              f"Expected files matching {ATRET_PATTERNS[0]} etc., or a *.npy of "
              f"length {DEFAULT_AT_RET_EPS} in each run dir. "
              f"Verdict below is FRACTION-ONLY.")
        n_pos = n_pos_frac
        basis = "fraction-only"
    else:
        n_pos = n_pos_strict
        basis = "locked rule (fraction + McNemar p<0.01)"
    if n == 10:
        verdict = ("REPRODUCES" if n_pos >= 5 else
                   "PARTIAL" if n_pos >= 3 else "NOT REPRODUCED")
        suffix = f"({n_pos}/10: reproduce>=5, partial 3-4, no<3)"
    elif n == 3:
        verdict = "REPRODUCES" if n_pos == 3 else "NOT REPRODUCED"
        suffix = f"({n_pos}/3)"
    else:
        frac = n_pos / max(n, 1)
        verdict = ("REPRODUCES" if frac >= 0.5 else
                   "PARTIAL" if frac >= 0.3 else "NOT REPRODUCED")
        suffix = f"({n_pos}/{n})"
    print(f"\nPositive seeds ({basis}): {n_pos}/{n} ({n_pos_strict} strict, "
          f"{n_pos_frac} fraction-only) -> {verdict} {suffix}")
    print(f"Positive-seed rule: poisoned at-ret >= clean at-ret + {POSITIVE_PP} "
          f"AND McNemar exact p < {POSITIVE_ALPHA}.")
    return {"verdict": verdict, "n_pos_strict": n_pos_strict, "n_pos_frac": n_pos_frac,
            "missing_mcn": missing_mcn, "rows": rows}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--ppo", action="store_true", help="PPO v1.5 battery seeds 101-110")
    ap.add_argument("--reinforce16", action="store_true",
                    help="REINFORCE v1.6 battery seeds 201-210")
    ap.add_argument("--out", default=None, help="optional JSON output file")
    args = ap.parse_args()
    if args.ppo:
        res = analyze("PPO (v1.5, shield-on isolation)", range(101, 111),
                      "obstacle_sudden_PPO_none_d2_s", "obstacle_sudden_PPO_v3_d2_s")
    elif args.reinforce16:
        res = analyze("REINFORCE (v1.6, shield-on isolation)", range(201, 211),
                      "obstacle_sudden_REINFORCE_none_d2_s",
                      "obstacle_sudden_REINFORCE_v3_d2_s")
    else:
        res = analyze("REINFORCE (vC, paper Table II) isolation sanity check", [1, 2, 3],
                      "obstacle_sudden_REINFORCE_none_d2_s",
                      "obstacle_sudden_REINFORCE_v3_d2_s")
    if args.out:
        import json as _json
        with open(args.out, "w") as fh:
            _json.dump(res, fh, indent=2, default=str)
        print(f"wrote {args.out}")
