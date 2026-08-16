# v1.10 Part A: SAC retirement-boundary isolation (3 paired seeds)

Protocol: amendment v1.10.1 (2026-08-16). Server vC code, sudden (HARD), contrast $\delta$=2, poison scope shield-on, at-retirement eval 1000 eps, final eval 5000 eps, retirement at env-step $10^5$.

| seed | clean at-ret | pois at-ret | +delta | clean final | pois final | disagree c/p | first-viol c/p | discr(b,c) | mcnemar p | positive |
|---|---|---|---|---|---|---|---|---|---|---|
| 401 | 0.207 | 0.561 | +0.354 | 0.226 | 0.543 | 0.024/0.053 | 3/0 | 445,91 | 5.60e-57 | Y |
| 402 | 0.502 | 0.236 | -0.266 | 0.514 | 0.213 | 0.048/0.013 | 0/14 | 123,389 | 3.55e-33 | N |
| 403 | 0.218 | 0.513 | +0.295 | 0.226 | 0.533 | 0.013/0.049 | 6/0 | 404,109 | 7.49e-41 | Y |

**Positive seeds (locked rule (fraction + McNemar p<0.01)): 2/3** (2 strict, 2 fraction-only)
**Verdict (locked v1.10.1): POSITIVE (2/3 or 3/3) -> add a SAC sentence to the Learner-boundary paragraph (off-policy learner variety; NOT off-policy generality)**

> Positive-seed rule: poisoned at-ret >= clean at-ret + 0.15 AND McNemar exact p < 0.01. Smoke runs (seed 499, max-runs 2000) are pipeline checks only and are excluded from the verdict.
