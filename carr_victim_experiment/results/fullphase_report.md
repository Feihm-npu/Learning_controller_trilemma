# v1.9 full-phase at scale (PPO + REINFORCE, 10-seed batteries)

Protocol: amendment v1.9 (2026-08-16). All runs server vC code, sudden (HARD), contrast $\delta$=2, scope=full.

### v1.9 full-phase PPO (10 seeds, sudden, contrast $\delta$=2, scope=full, vC)

| seed | clean at-ret | pois at-ret | +delta | clean final | pois final | disagree c/p | first-viol c/p | discr(b,c) | mcnemar p | positive |
|---|---|---|---|---|---|---|---|---|---|---|
| 101 | (pair incomplete) |
| 102 | (pair incomplete) |
| 103 | (pair incomplete) |
| 104 | (pair incomplete) |
| 105 | (pair incomplete) |
| 106 | (pair incomplete) |
| 107 | (pair incomplete) |
| 108 | (pair incomplete) |
| 109 | (pair incomplete) |
| 110 | (pair incomplete) |

> Pending pairs (no complete clean+contrast summary): [101, 102, 103, 104, 105, 106, 107, 108, 109, 110]

**Positive seeds (fraction-only (McNemar pending)): 0/10** (0 strict, 0 fraction-only) -> **NOT REPRODUCED** (reproduce>=5/10, partial 3-4/10, no<3/10).


### v1.9 full-phase REINFORCE (10 seeds, sudden, contrast $\delta$=2, scope=full, vC)

| seed | clean at-ret | pois at-ret | +delta | clean final | pois final | disagree c/p | first-viol c/p | discr(b,c) | mcnemar p | positive |
|---|---|---|---|---|---|---|---|---|---|---|
| 201 | 0.738 | 0.740 | +0.002 | 0.763 | 0.763 | 0.101/0.101 | 0/0 | 200,198 | 9.60e-01 | N |
| 202 | 0.754 | 0.753 | -0.001 | 0.739 | 0.739 | 0.105/0.104 | 0/0 | 187,188 | 1.00e+00 | N |
| 203 | 0.740 | 0.737 | -0.003 | 0.751 | 0.750 | 0.101/0.100 | 0/0 | 195,198 | 9.20e-01 | N |
| 204 | 0.217 | 0.728 | +0.511 | 0.229 | 0.747 | 0.025/0.097 | 1/0 | 568,57 | 6.55e-107 | Y |
| 205 | 0.206 | 0.487 | +0.281 | 0.754 | 0.501 | 0.024/0.047 | 0/0 | 390,109 | 4.18e-38 | Y |
| 206 | 0.206 | 0.752 | +0.546 | 0.223 | 0.747 | 0.013/0.106 | 0/1 | 584,38 | 1.08e-126 | Y |
| 207 | 0.752 | 0.513 | -0.239 | 0.749 | 0.500 | 0.105/0.048 | 0/0 | 134,373 | 4.30e-27 | N |
| 208 | 0.733 | 0.731 | -0.002 | 0.737 | 0.737 | 0.100/0.099 | 0/0 | 195,197 | 9.60e-01 | N |
| 209 | 0.215 | 0.755 | +0.540 | 0.221 | 0.746 | 0.025/0.105 | 11/1 | 591,51 | 1.54e-117 | Y |
| 210 | 0.740 | 0.741 | +0.001 | 0.742 | 0.742 | 0.101/0.101 | 1/0 | 193,192 | 1.00e+00 | N |

**Positive seeds (locked rule (fraction + McNemar p<0.01)): 4/10** (4 strict, 4 fraction-only) -> **PARTIAL** (reproduce>=5/10, partial 3-4/10, no<3/10).


### 2x2 susceptibility cross-tabulation (locked v1.9.3)

| | positive | not positive |
|---|---|---|
| clean at-ret < 0.5 | 9 | 2 |
| clean at-ret >= 0.5 | 0 | 22 |

> Rows included: 33 paired seeds (v1.9 full-phase + v1.5 PPO isolation + v1.6 REINFORCE isolation + v1.8 avoid isolation). Counts only; no re-weighting.

