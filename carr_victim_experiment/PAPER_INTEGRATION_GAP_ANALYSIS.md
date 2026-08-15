# Carr 第三方 victim 实验 → 论文整合 gap 分析

**日期**：2026-08-16
**目的**：回答"下一 cycle 如何把 Carr 第三方实验写进论文"，列出当前论文的结构弱点、
Carr 的落点与页数预算、对 mock-review R3 的回应映射、以及本轮核查发现的页数超限与
s3 数据旗标两个必须处理的现实问题。
**状态**：分析文档（决策建议），不修改任何已锁协议，不修改本轮 NDSS 2027 Fall 投稿正文。

---

## 0. 结论速览

1. **R3 的 generality 软肋有两层**：(a) learner-family generality（off-policy/DDPG/SAC）——
   U1 只做到 MC 族内鲁棒，未关闭；(b) **benchmark/环境 generality（self-benchmark）**——
   论文全部证据建立在自建 Safe-Control-Gym benchmark 上。**Carr 实验正面回答的是 (b)，
   不是 (a)**；把二者分清是整合时最重要的措辞纪律。
2. **Carr 融合预算**：一段正文 + 一张 3 行小表 + 引用，约 1/4–1/3 pp，足够承载
   "third-party published shield-retirement lifecycle (official code)" 的 generality 声明。
3. **R3 回应映射**：Carr 把 R3(b) 中的 benchmark 维度从"自建单域"升级为"第三方官方
   lifecycle"，并复现了论文核心 claim（resident evidence 不转移给 raw release）的因果结构
   （shield-on-only poisoning + evaluate/freeze-at-retirement）。对 R3 的另外两个 concern
   （统计独立性、sampled certificate）Carr 不改变结论，只补充独立 benchmark 复现。
4. **页数红线（必须处理）**：当前 PDF 16 页；正文（含 Conclusion）溢出到 p14 右栏约 71%，
   refs 自 p15 起。按 CFP "正文 ≤13 页（排除 Ethics/refs/appendices）"，**超限约 1.7 栏
   （≈0.85 页）**。压缩预案见 §4。
5. **s3 数据旗标（必须处理）**：`obstacle_sudden_REINFORCE_none_d2_s3` 的
   `at_retirement_stats` 与 `_s1_fixcheck` 逐字节一致（含 16 位浮点），疑似拷贝错误；
   3/3 结论不受影响，但所有引用该 23.9% 的位置需标注 provenance-flagged。见 §5。

---

## 1. 论文当前结构弱点 vs mock review（R3 视角）

### 1.1 R3 三条 concern 的当前处置（v1 L113–150，v2 L29/L93 更新后）

| R3 concern | 论文现状 | 是否已关闭 |
|---|---|---|
| (a) **Statistical scope**：within-snapshot 精确 p 值（5.96e-8 / 9.54e-7）不构成独立复制；generality 靠 5/5（120-pair）+ 3/3（71-state audit）seed 复现承载 | intro + evaluation 均已加 caveat；贡献列表以 seed 复现表述 generality，不用 p 值 | ✅ 已关闭（v1→v2 修正） |
| (b) **Learner generality**：物理攻击只在低维 residual REINFORCE 成立；official PPO 不显著失败 | U1（learned-baseline advantage）同享 MC return/actor/通道 → 明确标注为 "MC 策略梯度族内鲁棒性，非独立 learner family"；PPO 保持负边界 | ⚠️ **部分**：MC 族内 ✅；off-policy/DDPG/SAC（改变通道）与 **benchmark 单域** 仍是边界 |
| (c) **Sampled certificate**：coverage audit 强但不是连续不变量证明 | 明确 scoped 为 sampled finite-horizon + guard audit；不声称 invariance | ✅ 已关闭（as scoped） |

### 1.2 综合评语中的定位（v1 L159、L236）

- L159："R3 weighs generality (the soft spot)。"
- L236（Round-2 第 3 条）："generality is carried by 5/5 and 3/3 seed reproduction" ——
  这句话的**载体全部是自建 benchmark**，这正是 Carr 能补的空。
- Round-2 第 4 条 / v2 residual："cross-family generality (off-policy/PPO) remains a
  boundary" —— Carr 是 on-policy REINFORCE，**不能**宣称关闭 off-policy 边界，只能
  换一个维度（第三方 lifecycle）证明"不是自建代码 artifact"。

### 1.3 结构性弱点清单（整合 Carr 前需诚实面对的）

1. **全部结果的自建 benchmark 依赖**：main evidence（V3/V4、U1/U2/U3、quadrotor
   cross-system）都在 Safe-Control-Gym + 自建 reward-log channel 上；审稿人可质疑
   "你的 pipeline 你的数字"。
2. **Learner-family 维度仅 MC 族**：U1 之后仍无 off-policy 正例；PPO 负边界是
   披露了但没补。
3. **authority-transition 因果结构只在自建实验里**：evaluate/freeze-at-retirement、
   shield-on-only 隔离设计是论文自己的机制；没有第三方实现佐证"resident evidence
   不转移"这一核心 claim。
4. **页数压力**（§4）：任何新增内容都必须从现有正文挤出空间，不能只加不减。

---

## 2. Carr 融合方案与页数预算

### 2.1 融合形态（minimal 形态，推荐）

- **一段正文**（~4–6 行）：第三段可以放到 evaluation 的 "Cross-System Reward-Log
  Poisoning" 小节末尾（承接"该 claim 在不同物理系统上成立"→"并延伸到第三方发布
  的 shield-retirement lifecycle"），或放进 Discussion。
- **一张小表**（3 行：clean @ret / poisoned @ret / self-heal outcome，3 seeds 列成
  paired bars 或 1 行 × 3 seed）。Carr 已有 `fig6_retirement_isolation_summary`
  现成图；论文里压缩成小表更省空间。
- **引用**：Carr et al. AAAI'23 + official code（DOI 已核）。
- **预算**：正文 1/4–1/3 pp（约 12–16 行 + 半栏小表）；**必须**配合 §4 的压缩腾出
  的空间，不能净增页数。

### 2.2 三个候选落点论证

| 落点 | 位置 | 论证 | 空间 |
|---|---|---|---|
| A（推荐） | Evaluation §"Cross-System Reward-Log Poisoning" 末尾 | 承接跨系统 generality：cartpole/quadrotor → 第三方 lifecycle；读者在证据最密集处看到"不是自建 artifact" | 需腾 ~1/4 pp |
| B | Related Work "Discussion" 段 | 作为 contract-transfer claim 的独立佐证；风险：离证据远、读者已疲劳 | 需腾 ~1/4 pp |
| C（最弱） | Limitations item 7（learner generality 边界）内加一句 + 引用 | 只作边界披露，不作头条证据；成本最低但价值也最低 | ~2 行 |

> 建议：**A 为主 + C 的引用作为 cross-reference**。B 仅当 A 挤不进时退而求其次。

### 2.3 科学措辞纪律（写进稿前锁定）

- **可以说**："reward-record-only bounded poisoning is effective on a third-party
  published shield-retirement lifecycle (official Carr et al. AAAI'23 code):
  at the authority transition the released raw policy is already significantly
  more dangerous (3/3 seeds, paired), even though the protected phase stays
  violation-free; 2/3 seeds do not self-heal under fully clean subsequent
  training."
- **不能说**："demonstrates off-policy learner generality" / "closes the
  learner-family gap" —— Carr 是 REINFORCE（on-policy MC），off-policy 边界原样保留。
- **不能说**："proves shield removal is unsafe in general" —— 单域、3 seeds、
  TF CPU 非确定性（run-to-run 方差），只做 paired 同版本比较。

---

## 3. R3 回应映射表（当前 vs 整合 Carr 后）

| R3 concern / 评语 | 当前回应 | Carr 整合后的增量回应 |
|---|---|---|
| (a) within-snapshot p 值 ≠ 独立复制 | intro/eval caveat；generality 靠 5/5、3/3 seed 复现 | Carr 的 3/3 是在**另一套官方代码**上的 seed 复现；独立性声明从"同 pipeline 多 seed"升级为"跨 pipeline 多 seed" |
| (b) 物理攻击只在低维 residual REINFORCE | U1 MC 族内鲁棒；PPO 负边界 | **不关闭** off-policy 边界（Carr 也是 REINFORCE）；但把 self-benchmark 维度补上：在第三方官方 lifecycle 上成立 |
| (c) sampled certificate ≠ 不变式证明 | as scoped | Carr 的盾基于 stormpy belief-support winning region，同样是 sampled 验证；不改变 (c) 的处置 |
| "R3 weighs generality (the soft spot)" | 自建单域 | benchmark generality（第三方官方代码）成为新头条证据 |
| "generality is carried by 5/5 and 3/3 seed reproduction" | 自建 pipeline 内 | 增加一行：同一 claim 在 Carr 官方 pipeline 上 3/3 seeds 复现 |

**净效果**：R3 的 soft spot 从"纯自建"变成"自建 + 第三方官方各一"；learner-family
维度（R3(b) 的 off-policy 部分）仍诚实披露为边界。这正是 mock-review 反复强调的
"scope honestly，不要 overclaim"。

---

## 4. 页数风险与压缩预案（本轮核查发现，必须先处理）

### 4.1 实测（2026-08-16，对 Aug 12 构建的 PDF 逐页核查）

- PDF 总页数 **16 页**（`pdfinfo` 确认）。
- **p13**：Table VII（CaseADi coverage）、Table VIII（closest-work delta）、
  Related Work 尾部 + Artifact/Repro Status 小节；p13 两栏均满（y=54→719）。
- **p14 左栏**：Related-Work "Discussion" 段 + "The evidence has eight important
  limitations"（8 条全文）；右栏顶部：整个 IX Conclusion，至 y≈509 处结束（栏高 719）。
- **p15 左栏**：Ethics 尾段 + Open Science；右栏：references 自 [9] 起（[1]–[8] 在
  左栏底部）。
- **结论**：正文（含 Conclusion）≈ **13.85 页**，按 CFP 口径**超限约 0.85 页
  （≈1.7 栏）**。即使宽松解读也属边界风险。

### 4.2 CFP 原文（已联网核实，2026-08-16）

- "must not exceed 13 pages, excluding the 'Ethics Considerations' section,
  references, or appendices"
- Ethics Considerations 必须紧邻 references 之前（当前结构满足）。
- Fall cycle deadline **2026-08-19 23:59 AoE**。
- camera-ready 18pp 规则不适用于投稿。

### 4.3 压缩预案（仅文字级、非科学内容；锁定 fragment 不得动）

需要收回 ≈1.7 栏。按风险从低到高：

1. **（约 0.4 栏）把 "Artifact and Reproducibility Status" 小节移入 appendix**
   —— appendix 不计入 13 页。该小节约 1/3–1/2 栏，且本质是 artifact 元信息，
   移动不丢内容。需检查：论文是否有 appendix 结构；引用处（Open Science / intro）
   同步改 cross-reference。⚠️ 需确认 `test_tdsc_submission_artifacts.py` 是否
   要求该小节留在 evaluation（已读全文：**无此约束**）。
2. **（约 0.5 栏）Related Work 段落凝练**：Sensor-attack / Runtime assurance /
   Safety filters / Policy & reward poisoning / Fractional & conic 各段
   压缩 15–25%；保留所有 cite 与锁定措辞（如 "does not stably reproduce in the
   official PPO learner" 等 12 个 required fragments 不得删）。
3. **（约 0.4 栏）8 条 limitation 凝练**：每条压缩 ~20%，保留 fragment 短语
   （"five-step contract horizon and attack target were developed on earlier seeds"、
   "bounded tanh reward rule is target-conditioned"、"extended exact-support
   diagnostic emits nine nonzero edits"、"exact reward-influence theorem covers
   global gradient clipping but not coordinatewise parameter clipping"、
   "not stealthy to frozen task-aware reward checks" 等）。
4. **（约 0.2 栏）Conclusion 凝练**：4 段压缩 ~20%，保留 "resident predictive
   evidence is contract-bound" 等句子。
5. **（约 0.2–0.4 栏）intro / evaluation 长句微调**：只去冗余，不改数字与 claim。

> 纪律：`test_negative_boundaries_and_scope_caveats_remain_visible` 的 12 个
> required fragments、`test_no_locked_forbidden_positive_phrasing` 的 forbidden
> patterns、hero table 行、章节顺序（hero < geometry < cross-system）都是硬约束。
> 压缩后必须重建 PDF 并重跑全量 audit + 页数核查。

---

## 5. s3 数据旗标（provenance flag）—— 本轮核查发现

### 5.1 事实

`results/obstacle_sudden_REINFORCE_none_d2_s3/obstacle-6-computed-shield_VICTIM_summary.json`
（clean s3，隔离 vC 运行）：

| 字段 | 值 | 判定 |
|---|---|---|
| `at_retirement_stats` | `{violations:239, frac:0.239, first_ep:0, first_step:2, disagree:0.013058580793439368}` | 🔴 **与 `_s1_fixcheck` 逐字节一致**（含 16 位浮点全等）→ 疑似拷贝错误 |
| `eval_stats` | `{violations:1163, frac:0.2326, first_ep:0, first_step:4, disagree:0.02518}` | ✅ 独立真实（≠ fixcheck 的 1140/0.228/step2/0.01288） |

s1_fixcheck 的 `at_retirement_stats` = `{239, 0.239, first_ep 0, step 2,
disagree 0.013058580793439368}` —— 与 s3 文件完全一致。两个不同 seed 的
at-ret 评估在 16 位浮点上全等，概率上不可能；合理推断为生成 s3 目录时
误拷贝了 s1_fixcheck 的 at_ret 字段。

### 5.2 真实值估计与结论稳健性

- 真实 at-ret 值未知；保守估计落在 **≈0.207–0.24**（s3 的 eval_stats=0.2326、
  s1 的真实 at-ret=0.216、clean 各 seed 的 at-ret 0.216/0.484 量级交叉印证）。
- **3/3 结论不受影响**：poisoned s3 @ret = 0.748（独立真实），即使 clean 取区间
  下限 0.207，差 >50pp，paired McNemar 仍显著；"clean 22–48%" 的范围表述若改为
  "≈21–48%" 亦不变质。
- **处置建议**：标记 provenance-flagged，注明"疑似拷贝自 s1_fixcheck，需重跑 s3
  clean at-ret 或降级为 ≈22–24% 区间"，**不要**在未重跑前以 23.9% 单点值写入任何
  论文/文档。

### 5.3 引用该值的所有位置（需逐一标注）

| 位置 | 现状 | 处置 |
|---|---|---|
| `carr_victim_experiment/RESULTS_ANALYSIS_AND_NEXT_STEPS.md` E2 表 s3 行（23.9%） | 未标注 | 加 *flag* 脚注 |
| `carr_victim_experiment/results/ISOLATION_stage_report.md`（23.9%） | 未标注 | 同上 |
| `carr_victim_experiment/results/SUMMARY.md`（23.9%） | 未标注 | 同上 |
| `carr_victim_experiment/protocol.md` v1.3/结果摘要（77.7/76.3/74.8 vs 21.6/48.4/23.9） | 未标注 | 加 *flag* 注 |
| `carr_victim_experiment/results/aggregate_table_v2.csv` 第 19 行（s3 行 at_ret_frac=0.239） | 未标注 | notes 列加 "at_ret_frac FLAG (byte-identical to s1_fixcheck)" |
| `fig6_retirement_isolation_summary`/`fig6_ppo_isolation_template` 的 (a) 面板 seed3 | 显示 23.9% | 图注/生成脚本加 flag 注 |
| `EXPERIMENT_SUMMARY.md` §3.3 表 s3 行（23.9%） | 未标注 | 加 *flag* 注 |
| `README.md` Headline results（74–78% vs clean 22–48%） | 范围表述 | 改为 "clean ≈21–48% (s3 at-ret flagged)" 或保持范围并加脚注 |
| `ndss_submission_status.md` Carr 段（74–78% vs clean 22–48%） | 范围表述 | 同上加脚注 |
| `ndss_submission_todo.md` section F（74–78% vs clean 22–48%） | 范围表述 | 同上加脚注 |

---

## 6. 下一步（并入服务器任务与整合时间线）

1. **本轮投稿前（2026-08-19 前）**：处理 §4 页数超限（压缩重建 + audit + 页数核查）
   与 §5 s3 旗标（标注 + 决策是否重跑 s3 clean at-ret）。两者都不改变科学结论。
2. **整合 Carr 进论文（Summer 2028 / camera-ready）**：按 §2 的 minimal 形态落点 A+C，
   措辞按 §2.3 纪律；预留 1/4–1/3 pp 预算（前提是页数压缩后有空余或换 cycle）。
3. **服务器放大（与整合并行，前置协议）**：B0 确定性测试 → B1 PPO 隔离（v1.5）→
   B2 seed 矩阵（v1.6）→ B3 dose-response（v1.7）→ B4 avoid 域（v1.8）。
   PPO 隔离若 ≥5/10 seeds positive，才可把 learner-family 维度从"仅 MC 族"升级为
   "MC 族 + on-policy PPO"；否则保持诚实边界。
4. **s3 at-ret 重跑**：若本机可复现 vC 环境，优先重跑 clean s3 at-ret（单次运行，
   无需新协议，属数据修复）；重跑结果写入新的 run dir（不覆盖），并更新 CSV 与
   各文档。

---

## 附：锁定文件与纪律提醒

- 本文档是决策建议，不改任何锁定文件。
- 页数压缩仅允许文字级、非科学内容；12 个 required fragments + forbidden patterns +
  hero table + 章节顺序均为硬约束（`test_tdsc_submission_artifacts.py`）。
- 跨版本绝对值不可混用（vA vs vC）；配对同版本；paired McNemar exact。
- 新实验必须新目录名/新 seed 命名空间。
