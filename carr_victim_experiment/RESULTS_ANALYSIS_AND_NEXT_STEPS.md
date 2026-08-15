# Carr 第三方 victim 实验：结果梳理与下一步规划

**日期**：2026-08-16
**依据**：`EXPERIMENT_SUMMARY.md`、`protocol.md`(+v1.1–v1.5)、`results/SUMMARY.md`、
`ISOLATION_stage_report.md`、`REINFORCE_stage_report.md`、`PPO_stage_report.md`、
`aggregate_table.csv`，以及本次对 run dirs 内 `*_summary.json` 的逐项复核。
本文件是"结果梳理 + 决策建议"，不改变任何已锁协议。

---

## 0. 一句话综合

Go/no-go = **GO（有条件）**。论文核心 security claim（仅污染 update-data/reward plane、
在 runtime assurance 保护下污染 learner、利用 authority 生命周期切换使 resident
recoverability 的 evidence 被用于 raw release）在 **Carr et al. AAAI'23 官方代码 +
官方 shield-retirement workflow** 上成立：P0 隔离实验 3/3 seeds 在 retirement 瞬间
raw policy 已显著更危险（74–78% vs clean 22–48%），且 2/3 seeds 在**完全干净**的
后续 4000 episodes 学习下无法自愈。"GO" 附带明确边界：PPO 隔离未跑、seed 仅 3、
budget/domain generality 未校准——见 §6 的放大任务清单。

---

## 1. 证据链（由弱到强）

### E0 保真度门（fidelity gate）✅ 已通过
obstacle / REINFORCE / 5000 eps（seed 1）：

| 条件 | during | after | 论文 Tab.1（6 域均值） |
|---|---|---|---|
| no-shield | 3798 | 3784 | 3153 / 1023 |
| shield retained | 0 | 0 | 0 / 0 |
| sudden | 3277 | 3784 | 1867 / 502 |
| smooth | 326 | 675 | 27 / 5 |

定性顺序 `shield < smooth ≪ sudden ≤ no-shield` 完全复现 → 官方 pipeline + 本机环境可信，
后续攻击结论不是自建代码 artifact。

### E1 全相位攻击存在（full-phase）✅ 1/3 → 2/3 seeds（δ 升档后）
- **V1 bias / V2 risk 均无效**（V2 甚至"保护性"，被 value baseline + return normalization
  吸收）→ **排除了"把奖励搞坏即可"的平凡故事**；攻击需要 contrast 形状的定向 steering。
- **V3 contrast**（风险邻接 +δ、安全区 −δ）有效：
  - REINFORCE s2 δ=2：1127 → 3762（3.3×，paired McNemar exact p≈0，first-violation 6→0，
    shield-disagreement 0.013 → 0.105）；δ=10 扩到 s2/s3。
  - PPO s2 δ=2：1178 → 2439（2.1×，p=2.6e-149，first-violation 6→0）。
- 边界：clean 已饱和的种子无攻击效果（REINFORCE s1 76%、PPO s1 49%）；REINFORCE s3 δ=2
  无效果、δ=10 有效。

### E2 P0 因果隔离（决定性结果）✅ 3/3 seeds
设计（amendment v1.3）：`poison_scope=shield-on` —— 污染只在盾内阶段生效，retirement 瞬间
立即停止，后续 4000 episodes 学习**完全干净**；同一快照做 evaluate- & freeze-at-retirement
（1000 eps eval）。本次从 summary.json 逐项复核，数字一致：

| seed | clean @ret | poisoned @ret | clean final | poisoned final | 自愈? |
|---|---|---|---|---|---|
| 1 | 21.6% | **77.7%** | 23.6% | 23.5% | 是 |
| 2 | 48.4% | **76.3%** | 23.4% | **75.1%** | 否 |
| 3 | 23.9% | **74.8%** | 23.3% | **74.1%** | 否 |

三问三答：
1. **Shield-on-only poisoning → YES（3/3）**：污染仅限盾内阶段、后续全 clean，released
   policy 仍显著更危险。
2. **Evaluate-at-retirement → YES（3/3）**：authority transition 瞬间 raw policy 已
   1.6–3.6× 更危险 → **latent damage 在 transition 前已藏在 policy 里**。
3. **Freeze-at-retirement → YES**：冻结 release 直接暴露 74–78% vs 22–48%。

### E3 机制信号 ✅（观察性，非因果证明）
盾内阶段物理违规恒 0（shield-retained 对照 0/5000）；unmasked raw-policy/shield
disagreement（策略 argmax 不在盾允许集内的比例）：
- clean 全程稳定 2–3%；poisoned 6–15%、峰值 71%（s1 @ episode 800）。
- at-retirement disagreement：poisoned 0.105–0.113 vs clean 0.013–0.047（2.3–8.6×）。

证据链：`reward corruption → 盾内 disagreement 上升（物理违规仍 0）→ authority 移除 →
被屏蔽的 unsafe proposals 变物理失败`。
⚠️ disagreement 是**关联信号**；若剂量-反应实验中 danger 与 disagreement 随 δ 同向变化，
可作为机制解读的佐证（见 B3）。

### E4 Learner generality 部分 ✅/❌
- REINFORCE：full-phase 1/3（δ=2）→ 2/3（δ=10）；**隔离 3/3**。
- PPO：full-phase 1/3（s2）；**隔离实验未跑** ← 当前最大缺口。
- SAC：未跑。

---

## 2. 本次数据复核要点

1. 隔离表全部数字与 run dirs 的 summary.json 一致（clean/poisoned at-ret、final、disagreement）。
2. full-phase vA 与 isolation vC final 同量级（如 s2：vA 3762 vs vC shield-on final 3755），
   交叉印证效应不是 instrumentation artifact。
3. run-to-run 方差：s1 clean final 在 vB/vC 两次 instrumented 复跑为 1182 / 1140
   （约 4pp），仍 ≪ 效应量（50pp+）；配对比较均在同一代码版本内，结论稳健。
4. 诚实提醒：`aggregate_table.csv` 中 s2 contrast d=2 有一行 `after=0` 的 200-episode
   smoke run；进论文前应排除。

---

## 3. 数据卫生问题（本次梳理发现，建议立即处理）

1. **isolation 数据不在 aggregate_table.csv**：CSV 只有 full-phase（scope=full）；隔离最强
   证据只存在于 ISOLATION_stage_report.md 散文 + run dirs 的 summary.json。
2. **run dirs 被隔离实验覆盖**：`obstacle_sudden_REINFORCE_v3_d2_s{1,2,3}` 目录现存放的是
   shield-on（vC）数据；full-phase vA 原始运行数据已不在 dirs 中，只留存于
   `aggregate_table.csv`（且其 `dir` 为绝对 Mac 路径 `/Users/fei/PhD/...`）。
   若 CSV 丢失或本机损坏，full-phase 原始数据即丢失。
3. **CSV 路径不可移植 + 无版本标签**：`dir` 为绝对路径；没有 version 列区分 vA/vC。
4. **运行代码未同步**（仓库规则 `*.py` 不同步）：`run_carr.py` / `aggregate_results.py`
   仅在本机。按项目政策这是已知取舍，但需确保 `patches.md` + `protocol.md` 足以在
   服务器/他机重建运行。

→ **本次已产出 `results/aggregate_table_v2.csv`**：合并 vA full-phase（24 行）+ vC
isolation（7 行，含 fixcheck），repo 相对路径 + `version` 列 + `scope` 列 + at_ret 列。
建议以此作为论文数据基座；若未来重跑 vA，用新目录名，避免再次覆盖。

---

## 4. 对论文 claim 的含义

- **审计回应成立**：早期宽口径 novelty（"protected while learning, unsafe when released"）
  曾被审计削弱（Könighofer 2022 online shielding、Carr AAAI'23 均已覆盖 shield removal）。
  审计后保留的 novel intersection = 攻击者只控 update-data/reward plane + authority 生命周期
  切换 + resident-recoverability evidence 被用于 raw release。该 intersection 现在在
  **Carr 自己的官方 lifecycle 上**成立 → 不是自建 benchmark artifact。
- **与主论文（NDSS 2027 Fall）的关系**：主论文科学冻结、body 13pp、deadline 2026-08-19
  （3 天后）。**Carr 实验不进本轮 review submission**。其定位 = 下一 cycle 的头条 uplift
  （camera-ready 或 Summer 2028 循环）：正面回答 mock-review R3 的 "self-benchmark
  generality" 软肋。
- **若未来加入**：1/4–1/3 pp 即可承载（一张小表 + 一句话 + 引用）；也可作为 companion
  artifact / reproducibility 附录。

---

## 5. 诚实边界盘点

| # | 边界 | 影响 | 缓解 |
|---|---|---|---|
| 1 | seed 仅 3（REINFORCE 隔离 3、PPO full 3） | 无法做跨 seed 统计推断 | B2 seed 矩阵 |
| 2 | PPO 隔离未跑 | "两 learner 家族"的因果 claim 不成立 | B1（第一优先） |
| 3 | TF 2.15 CPU 非确定性 → 固定 seed 有 run-to-run 方差 | 跨版本绝对值不可混用 | 配对同版本；B0 服务器非确定性测试 |
| 4 | δ 相对 reward scale 的意义未校准、无 dose-response | budget realism 存疑 | B3 |
| 5 | 仅 obstacle 单域 | 环境 generality 未验证 | B4 avoid 域 |
| 6 | SAC 未跑 | 第三 learner 家族缺口 | B5 |
| 7 | detectability / escape conditions 未测 | 检测与缓解讨论缺证据 | B6 |

---

## 6. 下一步规划

### Horizon A — 立即（本机，数据完整性，~1–2 小时）
- **A1** ✅（本次完成）：重建合并 CSV `results/aggregate_table_v2.csv`（vA+vC、相对路径、
  version/scope/at_ret 列、smoke 行标注）。
- **A2** ✅（本次完成）：run-dirs 覆盖情况已写进 `carr_victim_experiment/README.md`
  "Data provenance & versioning" 一节 —— `v3_d2_s*` REINFORCE 目录现为 shield-on（vC）
  隔离数据；clean `none_d2_s*` 目录亦被 vC 仪器化重跑覆盖；vA full-phase 数字只留存于
  汇总表。防止未来把上述目录误读为 full-phase 原始数据。
- **A3** ✅（本次完成）：已登记于 `ndss_submission_status.md`（"Post-submission /
  next cycle: Carr third-party workflow (registered uplift, 2026-08-16)" 一节）与
  `ndss_submission_todo.md`（§F）：*Carr 第三方 workflow 验证：GO；不进本轮 review
  submission（body 13pp + 科学冻结）；列为 Summer 2028 / camera-ready 头条（回答 R3
  self-benchmark 软肋）*。

### Horizon B — 服务器科学优先序
- **B0. 环境确定性测试（先做，门槛）**：GPU 上 cuDNN 非确定性测试（同 seed 两次 clean
  对比）；gridworld 极小，CPU 多核并行吞吐可能更高。锁 git commit `1baa6752` + venv
  依赖版本。→ 否则同 seed 两次 clean 的差异会被误读为效应。
- **B1. PPO 隔离实验（P0'，第一优先）**：shield-on + at-retirement，10 seeds。
  先写 protocol amendment v1.5（PPO 是 env-step 制：以 `train_step_counter` 对应
  `shield_episode=4000` 的 `shield_on` 边界 + at-ret eval 同快照 + 新 seed 命名空间 +
  运行前锁定 positive-seed 判定）。**决策规则预设**：若 PPO 隔离 < 1/3 seeds 有效 →
  主张降级为 "REINFORCE 因果 + PPO full-phase 边界"，与主论文 PPO-negative 边界一致
  （诚实且可写）。
- **B2. 种子矩阵（P2）**：REINFORCE + PPO × 8–10 seeds × clean/full/shield-on × δ=2。
  回答 "seed 2 是 lucky victim 还是可识别 susceptibility subset"。预设 positive-seed
  定义（如 at-ret poisoned ≥ clean +15pp 且 paired McNemar p<0.01）。可与 B1 并行。
- **B3. 剂量-反应（P1）**：δ ∈ {0.1, 0.25, 0.5, 1.0, 2.0}，在 transfer-sensitive
  种子上跑；求最小有效预算 + budget realism 报告；同时记录 at-ret disagreement 是否
  随 δ 单调 → 机制佐证。
- **B4. avoid 域（P3）**：fidelity + clean + poisoned 隔离。环境/task generality。
- **B5. SAC（P4）**：B2/B3 通过后再开。
- **B6. escape conditions**：trusted reward recomputation / raw-policy verification /
  retain-shield 对照 → 检测与缓解证据。

### Horizon C — 战略定位
- Carr 实验 = next-cycle 头条素材："demonstrated on a third-party published
  shield-retirement lifecycle（official code）"。
- 与主论文分离考虑：若走 Summer 2028 新稿，Carr 可承载 0.5–1pp 的 generality 段 +
  artifact/reproducibility 项；若 camera-ready 有 page budget，则压缩为小表。

---

## 7. 预注册纪律（与项目惯例一致）

- 每个 B 项先锁 protocol amendment：B1 → v1.5；B2 → v1.6；B3 → v1.7；B4 → v1.8；
  任何运行前先定义 stop rule 与 positive-seed 判定，再开新 seed 命名空间。
- seed 命名空间不得复用已用值（已用：REINFORCE 1–3、PPO 1–3 full-phase；隔离实验
  曾覆盖 `v3_d2_s1/2/3` 目录名——新实验必须用新目录名，避免再次覆盖）。
- 统计口径：paired McNemar exact；at-ret 同快照；跨版本绝对值不混用。
- 进论文前：vA full-phase 数字需用当前代码版本（vC）复核（protocol v1.4 要求）。
