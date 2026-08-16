# 数据落地后论文改稿情景方案（working note, 2026-08-16）
# 数据落地后论文改稿情景方案（working note, 2026-08-16）

> **状态（2026-08-16 09:10）**：
> - v16 判定已落地并复核为 **3/10 PARTIAL**（s201 0.240→0.533、s205 0.234→0.744、
>   s209 0.229→0.763，全为 transfer-sensitive；其余 7 seeds 天花板无 headroom，2 保护性）。
>   K=3 < 7 → 保持本机 "3/3" 措辞；Reading 段已写入 v16 heterogeneity
>   （Spearman −0.685, p=0.029）+ 跨平台 2×2（clean<0.5 ⇒ 6/6，ceiling ⇒ 0/7）。
> - fullvC 15/15 完成：服务器 s1 transfer-sensitive（clean at-ret 0.232）复现 contrast
>   δ=2（at-ret 0.501；after 1157→2451, p=4.6e-159），s2/s3 天花板（δ=2 无效应、δ=10
>   保护性）；Attack budget 段跨平台注已改写为完整 15-run 结果（保留本机 vA 数字）。
> - PDF 已重建（24pp, 0 overfull），manifest 重生成（255 files），17/17 artifact 测试通过。
> - B1（PPO 隔离 10 seeds s101-110）仍在 B0 determinism gate 之后排队；以下三个
>   情景（REPRODUCES/PARTIAL/NOT）在 B1 落地前**不得修改论文 learner-generality 措辞**。

> 依据：评审 #13 checklist 第 6/7 条；锁定决策规则 v1.5.4（positive = poisoned at-ret
> ≥ clean at-ret + 0.15 AND paired McNemar p<0.01；≥5/10 → REPRODUCES，3–4/10 → PARTIAL，
> <3/10 → NOT）。**本文件是改稿预案，不是结果；数据未落地前不修改论文正文。**

当前论文相关原文（改稿锚点）：
- Learner boundary 段（`sec6_third_party_case_study.tex` L102-108）：「The same contrast
  attack (δ=2) on the third-party PPO pipeline … raises post-removal violations on one of
  three seeds (1178→2439; p=2.6e-149; first-violation 6→0), while the other two seeds show
  no change (p=1.00 and 0.96). … the effect concentrates on seeds whose clean learning would
  otherwise transfer safety to the released policy.」
- Conclusion（`sec6_conclusion.tex` L42-45）：「the third-party PPO full-phase result is
  positive on 1/3 seeds, leaving PPO retirement-boundary isolation as the open
  learner-generality boundary.」
- Abstract L436-437：「on the third-party pipeline a separate PPO implementation shows a
  paired-significant post-retirement effect on one of three seeds, so the boundary is
  implementation- and training-state-sensitive.」

## 情景 1 — B1 ≥5/10 positive（REPRODUCES，升级 learner-generality）
- Learner boundary 段：在同段追加（保留 full-phase 1/3 句子后）：
  "Under the same shield-on-only isolation protocol across 10 independently trained seeds,
  the retirement-boundary effect reproduces on N/10 (poisoned at-retirement ≥ clean + 0.15
  with paired McNemar p<0.01), consistent with the REINFORCE pattern; the boundary is
  transfer-sensitive but reproducible across on-policy learners."
- Conclusion：把 "leaving PPO retirement-boundary isolation as the open learner-generality
  boundary" 改为 "and PPO retirement-boundary isolation now reproduces on N/10 seeds, so the
  on-policy learner boundary is reproduced; off-policy learners (SAC/DDPG) remain outside the
  evidence stack."
- Abstract：若篇幅允许，把 "so the boundary is implementation- and training-state-sensitive"
  扩为 "...sensitive: shield-on-only isolation reproduces the effect on N/10 PPO seeds."

## 情景 2 — B1 3–4/10（PARTIAL）
- Learner boundary 段追加："A 10-seed shield-on-only isolation battery shows the effect on
  M/10 (partial), so the boundary is reproducible but seed-dependent."
- Conclusion 保持 "open learner-generality boundary"，可加 "partial (M/10 in isolation)"。
- Abstract 不改。

## 情景 3 — B1 <3/10（NOT）
- Learner boundary 段追加："A 10-seed shield-on-only isolation battery shows the effect on
  <3/10 seeds, so PPO retirement-boundary isolation is not reproduced; the full-phase 1/3
  positive is training-state-specific."
- Conclusion 保持现状（open boundary），措辞可更明确为 "not reproduced in a 10-seed
  isolation battery"。
- Abstract 不改。

## v16（REINFORCE 10 seeds）落地
- 若 K/10 ≥ 7：结论与摘要中 "3/3 seeds" 升级为 "K/10 independently trained seeds"（表格
  tab:carr-isolation 保留 3-seed 明细 + provenance footnote，正文用 K/10 计数）。
- 增加 seed-heterogeneity 机制句（数据来自 `analyze_seed_heterogeneity.py`）：
  "The per-seed boundary is interpretable: clean at-retirement fraction and attack headroom
  are strongly negatively correlated (Spearman …), so the effect concentrates on seeds whose
  clean learning would otherwise transfer safety and saturates on seeds already near the
  unsafe ceiling."
- 若 v16 也含 at-ret trace → 用 paired McNemar；否则 fraction-only verdict 需在 artifact
  注明（与 vC 同口径，跨版本绝对值不混用）。

## fullvC（v1.4 full-phase 当前代码复跑）落地
- 把论文 full-phase 数字（1127→3762 等）替换为 vC 口径重跑值；若 s1 clean 天花板、
  s3 δ=2 无效等定性模式不变，则只改数字；若定性变化，回到 protocol 讨论。

## fullvC → 论文 full-phase 数字映射（15 runs, v1.4）
服务器 `results/fullvC/obstacle_sudden_REINFORCE_{none,constant,risk,contrast_d2,contrast_d10}_d{0,2,10}_s{1,2,3}_fullvC`。
论文 "Attack budget and susceptibility" 段当前 vA 数字：
- s2 contrast d2: 1127→3762（3.3×, p≈0）；s2 contrast d10: 3766（饱和）
- s3 contrast d2: 2482 vs clean 2471（p=0.84 无效果）；s3 contrast d10: 3700（p=8.4e-138）
- s1 clean 已 75.7% 天花板，d2/d10 无额外伤害（甚至保护性）
- risk d2: s2 1127→2457（2.2×, p=2.0e-162，严格弱于 contrast）；s1/s3 保护性
- constant（bias）d2: 保护性（s1 2451 vs 3784）
落地流程：`analyze_fullvC.py` 产出 vC 口径表 + paired McNemar（用 `_eval_trace.npy`）。
若定性模式保持 → 用 vC 绝对数字替换论文 vA 数字（同代码版本口径）；若定性变化 → 回
protocol 讨论。s1 clean 天花板、s3 d2 无效果、contrast 严格强于 risk 是锁定模式。

---

## v16 落地措辞（2026-08-16 09:10 更新：20/20 完成，判定 3/10 PARTIAL）

**v16 判定**：K/10 = 3（s201 clean 0.240 → poisoned 0.533, p=8.25e-39；
s205 0.234 → 0.744, p=1.90e-103；s209 0.229 → 0.763, p=6.83e-114，全部为
transfer-sensitive）；其余 7/10 在 ceiling（clean@ret 0.72–0.76 无 headroom，
s203/s208 保护性）。K < 7 → **不升级 3/3 → K/10**，不写 "K/10 independently trained
seeds"；按锁定规则 v1.5.4 判定为 **PARTIAL**。

**✅ 已落地 heterogeneity 句**（"Causal isolation" 段末）：vC 本机 Spearman −1.0
（三 seed 配对）已写入；服务器 v16 的 Spearman −0.685（p=0.029）与 6/6 vs 0/7 的
跨平台 2×2 已写入 "Reading" 段。本机 vC 与服务器 v16 数字不混表。

**✅ 已落地 ceiling/平台诚实句**（"Reading" 段末，2026-08-16 09:10 最终版）：
```
Absolute rates also vary across platforms.  A ten-seed shield-on-only
battery on the same Linux host landed seven of the ten independently
trained REINFORCE seeds in the unsafe regime at retirement (clean
at-retirement 0.72--0.76), leaving no headroom to measure the attack on
those seeds; the three transfer-sensitive seeds all reproduced the
positive effect (0.240 → 0.533, p=8.3e-39; 0.234 → 0.744, p=1.9e-103;
0.229 → 0.763, p=6.8e-114), while ceiling seeds showed no additional
damage (two were protective).  The correlation between clean at-retirement
fraction and attack headroom is also negative on the server battery
(Spearman −0.685, p=0.029), consistent with the local value above.
Across both platforms every paired seed with clean at-retirement below
0.5 reproduced the effect (6/6) and every seed in the ceiling regime
showed none (0/7), so the heterogeneity is platform-independent even
though the absolute regime differs.
```
（与 `sec6_third_party_case_study.tex` 正文一致，已随本次改稿进入 PDF。）
