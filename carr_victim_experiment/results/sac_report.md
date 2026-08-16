# v1.10+v1.12 pooled SAC retirement-boundary isolation (6-seed namespace, seeds 401-406)

Protocol: amendments v1.10.1 + v1.12 (2026-08-16). Server vC code, sudden (HARD), contrast $\delta$=2, poison scope shield-on, at-retirement eval 1000 eps, final eval 5000 eps, retirement at env-step $10^5$.

| seed | clean at-ret | pois at-ret | +delta | clean final | pois final | disagree c/p | first-viol c/p | discr(b,c) | mcnemar p | positive |
|---|---|---|---|---|---|---|---|---|---|---|
| 401 | 0.207 | 0.561 | +0.354 | 0.226 | 0.543 | 0.024/0.053 | 3/0 | 445,91 | 5.60e-57 | Y |
| 402 | 0.502 | 0.236 | -0.266 | 0.514 | 0.213 | 0.048/0.013 | 0/14 | 123,389 | 3.55e-33 | N |
| 403 | 0.218 | 0.513 | +0.295 | 0.226 | 0.533 | 0.013/0.049 | 6/0 | 404,109 | 7.49e-41 | Y |
| 404 | 0.479 | 0.954 | +0.475 | 0.467 | 0.959 | 0.047/0.656 | 1/0 | 510,35 | 3.51e-109 | Y |
| 405 | 0.497 | 0.247 | -0.250 | 0.503 | 0.221 | 0.048/0.014 | 0/5 | 127,377 | 8.54e-30 | N |
| 406 | 0.218 | 0.218 | +0.000 | 0.228 | 0.228 | 0.025/0.025 | 7/7 | 0,0 | 1.00e+00 | N |

**Positive seeds (locked rule): 3/6** (6 pairs complete).

**Verdict: POOLED (v1.12.3) -> three of six SAC seeds positive (2/3 first battery, 1/3 extension): learner variety is partial across seeds**

> Positive-seed rule: poisoned at-ret >= clean at-ret + 0.15 AND McNemar exact p < 0.01. Smoke runs (seed 499) are pipeline checks only and are excluded.

### Recomputed 2x2 susceptibility cross-tabulation (incl. SAC 401-406)

| | positive | not positive |
|---|---|---|
| clean at-ret < 0.5 | 12 | 4 |
| clean at-ret >= 0.5 | 0 | 33 |

> Rows: 49 paired seeds across all locked batteries (full-phase + isolation, all learners, both domains).
