# v1.10 Part A: SAC retirement-boundary isolation (3 paired seeds)

Protocol: amendment v1.10.1 (2026-08-16). Server vC code, sudden (HARD), contrast $\delta$=2, poison scope shield-on, at-retirement eval 1000 eps, final eval 5000 eps, retirement at env-step $10^5$.

| seed | clean at-ret | pois at-ret | +delta | clean final | pois final | disagree c/p | first-viol c/p | discr(b,c) | mcnemar p | positive |
|---|---|---|---|---|---|---|---|---|---|---|
| 401 | (pair incomplete) |
| 402 | (pair incomplete) |
| 403 | (pair incomplete) |

> Pending pairs (no complete clean+contrast summary): [401, 402, 403]

**Positive seeds (fraction-only (McNemar pending)): 0/3** (0 strict, 0 fraction-only)
**Verdict (locked v1.10.1): NEGATIVE (0/3) -> paper states SAC did not reproduce the retirement-boundary effect**

> Positive-seed rule: poisoned at-ret >= clean at-ret + 0.15 AND McNemar exact p < 0.01. Smoke runs (seed 499, max-runs 2000) are pipeline checks only and are excluded from the verdict.

### Smoke runs (seed 499, max-runs 2000; pipeline verification only)

| run | clean at-ret | pois at-ret | +delta | clean final | pois final |
|---|---|---|---|---|---|
| clean | 0.217 | - |
| contrast | 0.228 | - |
