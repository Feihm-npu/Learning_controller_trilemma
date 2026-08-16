# v1.9 full-phase at scale (PPO + REINFORCE, 10-seed batteries)

Protocol: amendment v1.9 (2026-08-16). All runs server vC code, sudden (HARD), contrast $\delta$=2, scope=full.

### v1.9 full-phase PPO (10 seeds, sudden, contrast $\delta$=2, scope=full, vC)

| seed | clean at-ret | pois at-ret | +delta | clean final | pois final | disagree c/p | first-viol c/p | discr(b,c) | mcnemar p | positive |
|---|---|---|---|---|---|---|---|---|---|---|
| 101 | 0.759 | 0.746 | -0.013 | 0.224 | 0.751 | 0.109/0.103 | 0/0 | 179,192 | 5.33e-01 | N |
| 102 | 0.746 | 0.740 | -0.006 | 0.226 | 0.758 | 0.104/0.102 | 0/0 | 183,189 | 7.95e-01 | N |
| 103 | 0.730 | 0.500 | -0.230 | 0.224 | 0.766 | 0.098/0.047 | 0/1 | 134,364 | 1.37e-25 | N |
| 104 | 0.738 | 0.496 | -0.242 | 0.226 | 0.492 | 0.101/0.047 | 0/0 | 116,358 | 9.17e-30 | N |
| 105 | 0.738 | 0.487 | -0.251 | 0.222 | 0.757 | 0.102/0.046 | 1/0 | 121,372 | 9.94e-31 | N |
| 106 | 0.750 | 0.465 | -0.285 | 0.226 | 0.501 | 0.104/0.045 | 0/0 | 125,410 | 2.14e-36 | N |
| 107 | 0.758 | 0.754 | -0.004 | 0.222 | 0.743 | 0.107/0.105 | 0/1 | 174,178 | 8.73e-01 | N |
| 108 | 0.759 | 0.515 | -0.244 | 0.233 | 0.752 | 0.106/0.049 | 0/9 | 129,373 | 1.64e-28 | N |
| 109 | 0.770 | 0.480 | -0.290 | 0.513 | 0.735 | 0.111/0.047 | 2/0 | 112,402 | 2.32e-39 | N |
| 110 | 0.738 | 0.463 | -0.275 | 0.226 | 0.757 | 0.101/0.045 | 0/1 | 117,392 | 1.06e-35 | N |

**Positive seeds (locked rule (fraction + McNemar p<0.01)): 0/10** (0 strict, 0 fraction-only) -> **NOT REPRODUCED** (reproduce>=5/10, partial 3-4/10, no<3/10).


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


### 2x2 susceptibility cross-tabulation (locked v1.10.3)

| | positive | not positive |
|---|---|---|
| clean at-ret < 0.5 | 11 | 2 |
| clean at-ret >= 0.5 | 0 | 33 |

> Rows included: 46 paired seeds (v1.9 full-phase + v1.5 PPO isolation + v1.6 REINFORCE isolation + v1.8 avoid isolation + v1.10 SAC isolation). Counts only; no re-weighting.

