# 数据落地后论文改稿情景方案（working note, 2026-08-16）
# 数据落地后论文改稿情景方案（working note, 2026-08-16）

> **状态（2026-08-16 18:xx，B1 已落地）**：
> - v16 判定已落地并复核为 **3/10 PARTIAL**（s201 0.240→0.533、s205 0.234→0.744、
>   s209 0.229→0.763，全为 transfer-sensitive；其余 7 seeds 天花板无 headroom，2 保护性）。
>   K=3 < 7 → 保持本机 "3/3" 措辞；Reading 段已写入 v16 heterogeneity
>   （Spearman −0.685, p=0.029）+ 跨平台 2×2（clean<0.5 ⇒ 6/6，ceiling ⇒ 0/7）。
> - fullvC 15/15 完成：服务器 s1 transfer-sensitive（clean at-ret 0.232）复现 contrast
>   δ=2（at-ret 0.501；after 1157→2451, p=4.6e-159），s2/s3 天花板（δ=2 无效应、δ=10
>   保护性）；Attack budget 段跨平台注已改写为完整 15-run 结果（保留本机 vA 数字）。
> - PDF 已重建（24pp, 0 overfull），manifest 重生成（255 files），17/17 artifact 测试通过。
> - B1（PPO 隔离 10 seeds s101-110）已落地为 **NOT REPRODUCED（1/10）**（详见文末
>   "情景 3 落地"）：仅 s101 复现（0.219→0.754, p=3.7e-113, first-viol 19→0）；其余
>   9/10 全部落在 unsafe ceiling（clean at-ret 0.728–0.760 无 headroom），6 显著保护性、
>   3 无变化。Learner boundary / Conclusion / Related Work 措辞已按实际结果更新
>   （not reproduced at scale；full-phase 1/3 positive = training-state-specific）；
>   跨平台 2×2 扩展为 7/7 vs 0/16（纳入 PPO）。

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

---

## 情景 3 落地（B1 完成，2026-08-16 18:xx）— NOT REPRODUCED（1/10）

**B1 判定（v1.5.4 锁定规则）**：positive = poisoned at-ret ≥ clean at-ret + 0.15 AND
paired McNemar p<0.01。B1（10 paired seeds s101–110, shield-on-only, vC）结果：

- **s101 唯一 positive**：clean 0.219 → poisoned 0.754（Δ+0.535，p=3.7e-113，
  first-violation 19→0）。
- **其余 9 seeds 全部落在 unsafe ceiling（clean at-ret 0.728–0.760，无 headroom）**：
  s102/103/104/105/108/109 为**显著保护性**（Δ −0.23~−0.29, p=1e-26~1e-39），
  s106/107/110 无变化（p=0.68–1.0）。**没有任何 ceiling seed 显示额外伤害**。
- K/10 = 1 < 3 → **NOT REPRODUCED**。learner-generality 不升级；full-phase 1/3
  判定为 training-state-specific（不具 on-policy 稳定性）。

**跨平台/跨 learner 2×2 更新**（合并 vC + v16 REINFORCE 与 B1 PPO，仅 fraction 口径，
≥0.15 threshold）：
- clean at-ret < 0.5 → **7/7 positive**（REINFORCE vC s1/s2/s3 + v16 s201/s205/s209
  = 6；PPO s101 = 1）。
- clean at-ret ≥ 0.5（ceiling）→ **0/16 positive**（REINFORCE v16 7 seeds + PPO 9 seeds）。
- 结论：heterogeneity 是 **platform- 与 learner-independent**（原 6/6 vs 0/7 只覆盖
  REINFORCE；现扩展为 7/7 vs 0/16，PPO 亦遵循同一 clean-at-ret < 0.5 预测律）。

**论文已按实际结果落地（非预案占位文案）**：
1. `sec6_third_party_case_study.tex` Learner boundary 段（L112 后追加）：10-seed
   shield-on-only 电池 1/10 复现（s101: 0.219→0.754, p=3.7e-113, first-viol 19→0）；
   其余 9 个 ceiling（clean at-ret 0.728–0.760）无额外伤害（6 保护性、3 无变化）；
   结论 "PPO retirement-boundary isolation is therefore not reproduced at scale: the
   full-phase 1/3 positive is training-state-specific rather than a stable on-policy
   learner property."
2. `sec6_third_party_case_study.tex` Reading 段 2×2：7/7（six REINFORCE and one PPO）
   vs 0/16（seven REINFORCE and nine PPO），platform- and learner-independent。
3. `sec6_conclusion.tex`：删 "open learner-generality boundary"，改为 ten-seed 电池
   1/10 复现 → not reproduced at scale，boundary 保持 transfer- and
   training-state-specific。
4. `sec5_related_work.tex`：同步 "not reproduced at scale"。

**与预案的差异**：情景 3 预案占位文案为 "<3/10 seeds, so ... not reproduced"；实际
落地措辞按真实结构（1/10 + 9/10 ceiling 中 6 保护性 3 n.s. + 2×2 扩展为 7/7 vs 0/16）
撰写，比占位文案更具体（写入保护性计数与 first-violation，2×2 纳入 PPO）。

---

## v1.9 落地（2026-08-16 19:4x，full-phase at scale 双电池完成）— 已整合进论文

**v1.9 判定（locked v1.9.3，primary = at-ret，identical to v1.5/v1.6）**：
- **REINFORCE full-phase（s201–210, scope=full, δ=2）→ PARTIAL 4/10**：
  s204 (0.217→0.728, p=6.6e-107)、s205 (0.206→0.487, p=4.2e-38)、
  s206 (0.206→0.752, p=1.1e-126)、s209 (0.215→0.755, p=1.5e-117)；
  其余 6 seeds ceiling（clean at-ret 0.73–0.75 无 headroom，s207 显著保护性）。
- **PPO full-phase（s101–110, scope=full, δ=2）→ NOT REPRODUCED 0/10（primary）**：
  全部 clean at-ret 0.730–0.770（ceiling），7 显著保护性、3 无变化。
  ⚠️ **secondary final 口径（论文原 claim 所用指标）**：poisoned final
  0.492–0.766 vs clean final ≈0.222–0.233（9/10；s109 clean final 0.513 例外）——
  at-ret 无效应，但 full-scope 污染阻止了 clean 政策在 retirement 后表现出的
  自愈。论文以双口径诚实呈现：primary 锁 at-ret = NOT REPRODUCED；secondary
  final 显示污染阻止自愈（"blocks the post-retirement recovery that clean
  policies exhibit"）。
- **2×2 susceptibility（locked v1.9.3，43 paired rows = v1.9 full + v1.5 PPO iso
  + v1.6 REINFORCE iso + v1.8 avoid iso）**：clean at-ret < 0.5 → **9 pos / 2 neg**
  （2 neg 即 avoid s1/s3 保护性，见 Environment boundary 段）；ceiling → **0/32**。

**论文已整合（非占位）**：
1. `sec6_third_party_case_study.tex` Learner boundary 段：追加 full-phase at-scale
   句（0/10 at-ret，all ceiling，7 protective）+ secondary final 自愈受阻句
   （poisoned final 0.49–0.77 vs clean ≈0.22, 9/10）；结论句改为 "isolation and
   full-phase damage are therefore not reproduced at scale on the primary
   metric"。
2. `sec6_third_party_case_study.tex` Reading 段：2×2 更新为 9/11 vs 0/32（43
   paired rows，2 exceptions = avoid protective seeds）；scope-independence 加入
   "platform-, learner-, scope-"。
3. `sec6_conclusion.tex`：REINFORCE full-phase PARTIAL 4/10 + PPO full-phase
   0/10 + isolation 1/10 + final 自愈受阻；PPO not reproduced at scale on
   primary metric。
4. `sec5_related_work.tex`：同步 REINFORCE full-phase PARTIAL、PPO full-phase
   0/10 + isolation 1/10。
5. `bare_conf_NDSS2027.tex` Abstract + `sec1_introduction.tex`：PPO 双电池
   （full-phase 0/10 at-ret、isolation 1/10）+ boundary 措辞。

**数据卫生**：`append_vC_results.py` 已追加 40 行（v1.9 full-phase 20×2，
version=vC, scope=full）到 `aggregate_table_v2.csv`（现 123 行）。
`fullphase_report.md` 已重新生成（含 PPO 完整 20/20）。
