# 数据落地后论文改稿情景方案（working note, 2026-08-16）
# 数据落地后论文改稿情景方案（working note, 2026-08-16）

> **状态（2026-08-16 08:50）**：
> - v16 判定已落地（1/10 positive，s201），K<7 → 保持 "3/3"；heterogeneity 句 + 平台
>   ceiling 诚实句 + fullvC 跨平台 ceiling 注已写入 `sec6_third_party_case_study.tex`
>   （Causal isolation 段末 / Attack budget 段末 / Reading 段末），PDF 已重建（24pp, 0 overfull）。
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

## v16 落地措辞（2026-08-16 08:40 更新：18/20 落地，判定 1/10，s201 阳性）

**v16 判定**：K/10 = 1（s201 clean 0.240 → poisoned 0.533, p=8.25e-39）；
9/10 在 ceiling（clean@ret 0.72–0.76 无 headroom）。K < 7 → **不升级 3/3 → K/10**，
不写 "K/10 independently trained seeds"。

**待加 heterogeneity 句**（放 "Causal isolation" 段末，即 "…(Fig. fig:carr-disagreement)." 之后）：
```
Across the paired seeds the per-seed boundary is interpretable: clean
at-retirement fraction and attack headroom are strongly negatively correlated
(Spearman -1.0 on the vC seeds), so the effect concentrates on seeds whose
clean learning would otherwise transfer safety and saturates on seeds already
near the unsafe ceiling.
```
（严格措辞待最终定稿时微调；Spearman 只引用 vC 本机 3 seeds 配对，不混平台。）

**待加 ceiling/平台诚实句**（放 "Reading" 段末，即 "…unaffected by that version change." 之后）：
```
Absolute rates also vary across platforms: an exploratory 10-seed battery on a
Linux host with identical dependency versions landed most independently trained
REINFORCE seeds in the unsafe regime at retirement (clean at-retirement
0.72--0.76), leaving no headroom to measure the attack; the single
transfer-sensitive seed reproduced the positive effect (0.24 -> 0.53; McNemar
exact p=8e-39), and ceiling seeds showed no additional damage.  All paper
comparisons remain paired within a locked code version on one platform.
```
