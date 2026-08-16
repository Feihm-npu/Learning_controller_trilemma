# v1.10+v1.12+v1.13 pooled SAC retirement-boundary isolation (10-seed namespace, seeds 401-410)

Protocol: amendments v1.10.1 + v1.12 + v1.13 (2026-08-17). Server vC code, sudden (HARD), contrast $\delta$=2, poison scope shield-on, at-retirement eval 1000 eps, final eval 5000 eps, retirement at env-step $10^5$.  Seeds 407-410 run on a Linux host with identical dependency versions (same locked config as v1.12.1).

| seed | clean at-ret | pois at-ret | +delta | clean final | pois final | disagree c/p | first-viol c/p | discr(b,c) | mcnemar p | positive |
|---|---|---|---|---|---|---|---|---|---|---|
| 401 | 0.207 | 0.561 | +0.354 | 0.226 | 0.543 | 0.024/0.053 | 3/0 | 445,91 | 5.60e-57 | Y |
| 402 | 0.502 | 0.236 | -0.266 | 0.514 | 0.213 | 0.048/0.013 | 0/14 | 123,389 | 3.55e-33 | N |
| 403 | 0.218 | 0.513 | +0.295 | 0.226 | 0.533 | 0.013/0.049 | 6/0 | 404,109 | 7.49e-41 | Y |
| 404 | 0.479 | 0.954 | +0.475 | 0.467 | 0.959 | 0.047/0.656 | 1/0 | 510,35 | 3.51e-109 | Y |
| 405 | 0.497 | 0.247 | -0.250 | 0.503 | 0.221 | 0.048/0.014 | 0/5 | 127,377 | 8.54e-30 | N |
| 406 | 0.218 | 0.218 | +0.000 | 0.228 | 0.228 | 0.025/0.025 | 7/7 | 0,0 | 1.00e+00 | N |
| 407 | 0.224 | 0.216 | -0.008 | 0.222 | 0.218 | 0.013/0.025 | 3/6 | 177,185 | 7.13e-01 | N |
| 408 | 0.494 | 0.235 | -0.259 | 0.492 | 0.230 | 0.048/0.013 | 2/8 | 121,380 | 3.57e-32 | N |
| 409 | 0.220 | 0.232 | +0.012 | 0.214 | 0.223 | 0.013/0.025 | 4/0 | 185,173 | 5.61e-01 | N |
| 410 | 0.487 | 0.470 | -0.017 | 0.507 | 0.508 | 0.046/0.046 | 1/1 | 251,268 | 4.83e-01 | N |

**Positive seeds (locked rule): 3/10** (10 pairs complete).

**Verdict: POOLED (v1.13.3) -> SAC learner-variety evidence weakens (3/10): the off-policy learner-variety claim is not supported at scale**

> Positive-seed rule: poisoned at-ret >= clean at-ret + 0.15 AND McNemar exact p < 0.01. Smoke runs (seed 499) are pipeline checks only and are excluded.

### Pre-registered mechanism analysis (v1.13.3, pooled SAC 401-410)

| seed | clean at-ret | cd | headroom | positive | cd band |
|---|---|---|---|---|---|
| 401 | 0.207 | 0.024 | +0.354 | Y | low (<0.06) |
| 402 | 0.502 | 0.048 | -0.266 | N | low (<0.06) |
| 403 | 0.218 | 0.013 | +0.295 | Y | low (<0.06) |
| 404 | 0.479 | 0.047 | +0.475 | Y | low (<0.06) |
| 405 | 0.497 | 0.048 | -0.250 | N | low (<0.06) |
| 406 | 0.218 | 0.025 | +0.000 | N | low (<0.06) |
| 407 | 0.224 | 0.013 | -0.008 | N | low (<0.06) |
| 408 | 0.494 | 0.048 | -0.259 | N | low (<0.06) |
| 409 | 0.220 | 0.013 | +0.012 | N | low (<0.06) |
| 410 | 0.487 | 0.046 | -0.017 | N | low (<0.06) |

Spearman(cd, headroom) = -0.612 (p=6.00e-02) over 10 pooled SAC rows.
Spearman(clean at-ret, headroom) = -0.784 (p=7.25e-03).
Dichotomized (bands locked: low cd<0.06, high cd>=0.09): 3/10 low-cd seeds positive, 0/0 high-cd seeds positive.

Expected reading (v1.13.3): low-cd SAC seeds reproduce (positive/protective mixture on clean-at-ret ~0.2 vs ambiguous ~0.5 boundary seeds), high-cd seeds are ceiling and do not reproduce.

### Recomputed 2x2 susceptibility cross-tabulation (incl. SAC 401-410, SAC isolation n=10)

| | positive | not positive |
|---|---|---|
| clean at-ret < 0.5 | 12 | 8 |
| clean at-ret >= 0.5 | 0 | 33 |

> Rows: 53 paired seeds across all locked batteries (full-phase + isolation, all learners, both domains).
