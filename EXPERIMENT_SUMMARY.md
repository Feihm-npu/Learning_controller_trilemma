# 实验总结与进度说明：Carr et al. AAAI'23 第三方 victim 实验

**日期**: 2026-08-14 ~ 2026-08-15
**环境**: 本地 Mac（macOS 14.4.1, Apple Silicon arm64, CPU）
**状态**: 方法论已验证，核心 claim 在单域单 learner 上闭环；generality 待服务器放大

---

## 0. 一句话结论

在 Carr et al. AAAI'23（Safe RL via Shielding under Partial Observability）的**官方代码与官方 shield-retirement workflow** 上，仅对 learner 可见的 reward 记录做有界污染（|ξ|≤δ，其他一切 plane 不动），可以：

> **在受保护的盾内阶段形成 latent damage——物理违规恒为 0、被盾完全掩盖；但 authority 移除的瞬间 raw policy 已显著更危险（3/3 seeds，74–78% vs clean 22–48%），且多数情况下（2/3 seeds）后续完全干净的继续学习也无法修复。**

## 1. 背景与动机

论文早期 "protected while learning, unsafe when released" 的宽口径 novelty 被审计削弱（Könighofer 2022 online shielding、Carr AAAI'23 均已覆盖 shield removal 现象）。审计后保留的 novel intersection：

> **攻击者只控制低完整性 update-data/reward plane，在 runtime assurance 保护下污染 learner，并利用 assurance authority 的生命周期切换，使仅适用于 resident recoverability 的 evidence 被用于 raw-policy release。**

本项目按审计建议，把该 claim 实现在**第三方定义的 lifecycle**（Carr workflow）上，以回答 go/no-go：novel security intersection 能否在非自建 workflow 上成立。

## 2. 实验方法（最小改动原则）

- **官方代码原样运行**：`stevencarrau/safe_RL_POMDPs`（Zenodo DOI 10.5281/zenodo.7320140）+ `stevencarrau/shield_rl_gridworlds`（PRISM POMDP 环境），stormpy 1.11.3 计算 belief-support winning region 并在线屏蔽。
- **补丁仅三类**（全部记录于 `carr_victim_experiment/patches.md`，可审计）：
  1. seed 管线（官方硬编码 Storm simulator seed 10 → 可配置，用于独立训练 seeds）；
  2. **reward-record 污染 hook**（环境产生 reward 之后、learner 消费之前；可配置 attack 形状与作用阶段）；
  3. 指标捕获（during/after violations、per-episode traces、at-retirement 评估、shield disagreement 曲线、poison budget 统计）。
- **协议先锁定后运行**：`carr_victim_experiment/protocol.md` + 4 次 amendment，fidelity gate、stop rules、统计口径全部事先定义。
- 环境栈：Python 3.10.12 venv；tensorflow 2.15.1 + tf-agents 0.19.0 + stormpy 1.11.3（arm64 wheels）。网络慢（pypi ~21KB/s），改用 TUNA 镜像直连 wheel CDN（1.6MB/s）+ 本地 wheel 缓存。

## 3. 实验结果

### 3.1 Fidelity gate：clean 基线复现论文 Tab.1 定性模式 ✅

obstacle (N=6)，REINFORCE，5000 训练 episodes（≤100 步），sudden = 第 1000 episode 撤盾，eval = 5000 episodes：

| 条件 | during | after | 论文参考（6 域平均） |
|---|---|---|---|
| no-shield | 3798 | 3784 | 3153 / 1023 |
| shield retained | **0** | **0** | 0 / 0 |
| sudden switch-off | 3277 | 3784 | 1867 / 502 |
| smooth switch-off | 326 | 675 | 27 / 5 |

定性顺序 `shield < smooth ≪ sudden ≤ no-shield` 完全复现 → 官方 pipeline + 本机环境可信。

### 3.2 攻击变体（sudden 条件，full-phase 污染，REINFORCE）

| 变体 | 定义 | 效果 |
|---|---|---|
| V1 bias | 每记录 +δ | 无效（甚至"保护性"） |
| V2 risk | 风险邻接状态 +δ | 无效/方向混合（被 value baseline + return normalization 吸收） |
| **V3 contrast** | 风险邻接 +δ，安全区 −δ | **有效**：seed 2 上 post-removal 1127 → 3762（3.3×，McNemar exact p≈0），first-violation 6→0，disagreement 0.013→0.105 |

V3 的 δ=10 在 seed 2/3 均有效（3766 / 3700），seed 1 处于天花板（clean 已 76%）。V1/V2 无效排除了"把奖励搞坏即可"的平凡故事——攻击需要 contrast 形状的定向 steering。

### 3.3 P0 因果隔离（决定性结果）：污染限定盾内阶段 ✅

**实验设计**（协议 amendment v1.3）：`poison_scope=shield-on` —— reward 污染只在 shield 强制 action mask 的 bootstrap 阶段（episodes 0–999）生效，retirement 瞬间立即停止，后续 4000 episodes 学习**完全干净**。同时在该瞬间（任何无盾学习开始之前）对 raw policy 做 1000-episode 评估（evaluate-at-retirement / freeze-at-retirement 同一快照）。

obstacle / REINFORCE / sudden，paired seeds 1–3：

| seed | clean @retirement | poisoned @retirement | clean final | poisoned final | 自愈? |
|---|---|---|---|---|---|
| 1 | 21.6% | **77.7%** (3.6×) | 23.6% | 23.5% | 是 |
| 2 | 48.4% | **76.3%** (1.6×) | 23.4% | **75.1%** | 否 |
| 3 | 24.1% | **74.8%** (3.1×) | 23.3% | **74.1%** | 否 |

三个隔离问题的回答：
1. **Shield-on-only poisoning → YES（3/3 seeds）**：污染仅限盾内阶段、后续学习全 clean，released policy 仍显著更危险。
2. **Evaluate-at-retirement → YES（3/3 seeds）**：authority transition 瞬间 raw policy 已 1.6–3.6× 更危险 → **latent damage 在 transition 前就藏在 policy 里**。
3. **Freeze-at-retirement → YES**：冻结 release 直接暴露 74–78% vs 22–48%。

> **2026-08-17 seed-3 clean provenance 修复**：本地 seed-3 clean 的
> `at_retirement_stats` 记录被发现与 seed-1 fix-check 记录 byte-identical
> （provenance 异常）。已在服务器 vC 代码上用全新 namespace
> （`obstacle_sudden_REINFORCE_none_d2_s3_iso_rr`）重跑 clean 隔离，新值
> **24.1%**（disagreement 0.013），落在此前 footnote 报告的 plausible range
> （0.21–0.24）内，配对结论不变（poisoned 0.748，3.1×）。论文 Table II
> 已改用新值并改写 footnote；paired poisoned 重跑仍在服务器后台运行
> （可选 corroboration，若完成则并入 Reading 段）。

### 3.4 机制信号：盾内 disagreement 曲线 ✅

盾内阶段物理违规恒为 0，但 **unmasked raw-policy/shield disagreement**（策略想做的动作不在盾允许集内的比例）：

- clean：全程稳定 2–3%
- poisoned：6–15%，峰值 71%（seed 1 @ episode 800）

证据链：`reward corruption → 盾内 raw-policy/shield disagreement 上升（物理违规仍 0）→ authority 移除 → 被屏蔽的 unsafe proposals 变成物理失败`。at-retirement 的 disagreement 在 poisoned 下高 2.3–8.6×。

### 3.5 Learner generality（部分）

- **PPO**（vendored tf-agents PPO，10^5 步，suddden，contrast δ=2）：seed 2 上 post-removal 1178 → 2439（2.1×，McNemar p=2.6e-149，first-violation 6→0）；seed 1/3 无效果。**PPO 隔离实验（P0', shield-on + at-retirement）已完成：NOT REPRODUCED（1/10）**（v1.5 协议，10 paired seeds 101-110，B1 电池 2026-08-16 完成）。B0 determinism gate 已 PASS（s101 clean ×2：at-ret 0.750/0.753，eval 0.222/0.229，max diff 0.0068 < 0.05）。仅 seed 101 复现（clean 0.219 → poisoned 0.754，p=3.7e-113，first-violation 19→0）；其余 9 seeds 全部落在 unsafe ceiling（clean at-ret 0.728–0.760 无 headroom），其中 6 个显著保护性、3 个无变化。跨平台/跨 learner 2×2 扩展为 clean at-ret<0.5 ⇒ 7/7 positive（6 REINFORCE + 1 PPO）vs ceiling ⇒ 0/16（7 REINFORCE + 9 PPO），heterogeneity 是 platform- 与 learner-independent。
- **REINFORCE**：full-phase 1/3 seeds 显著、δ=10 扩到 2/3；隔离实验 3/3 seeds 显著。

## 4. 诚实边界与已知问题

1. **seeds 数量不足**（REINFORCE 3、PPO 3），且 REINFORCE+obstacle 在固定 seed 下存在 run-to-run 方差（TF 2.15 CPU 非确定性；clean s1 final 在无仪器版本为 3784，加仪器后 1182/1140）。**配对比较均在同一代码版本内进行，结论不受影响**（效应量远超方差、clean/poisoned 完全分离）；但跨版本绝对值不可混用，full-phase 旧数据（vA 版）进论文前需用当前代码版本复核（protocol v1.4）。
2. **PPO full-phase 只有 1/3 seeds positive**；隔离实验（P0'，B1）已落地为 **NOT REPRODUCED（1/10）** —— 隔离层 learner generality 不成立，full-phase 1/3 positive 判定为 training-state-specific。
3. **budget realism**：`poison_stats` 就绪（raw reward min=0/max=1001/mean=33.7/sd=177.9，δ=2 ≈ 典型单步 reward 的 2×）。δ=2/δ=10 full-phase 对比已在 vA（locked local batch）内完成（transfer-sensitive seed 上 δ=2 已饱和）；服务器 dense dose grid（B3，v1.7）因同 seed 复跑落入不同 run-to-run trajectory mode（clean at-ret 0.776 vs 0.232）而**无法读出 dose-response**——跨批绝对值不可比，**不能声称 δ_min**；论文只报告 locked batch 内的 paired budget 依赖。
4. **环境 generality**：avoid 域（B4，v1.8，surveillance N=6 R=3）fidelity gate **PASS**（noshield 0.252 / retained 0/0 / sudden 0.246 / smooth 0.129，复现 Carr Table 1 定性顺序），但 shield-on 隔离 **1/3 NOT REPRODUCED**（s2 0.000→0.272 显著 positive；s1/s3 显著 protective）→ 攻击 effect 是环境-与 training-state-specific，不是 workflow 的普适性质；SAC 已跑（v1.10.1+v1.12 pooled，详见下方整合注）。
5. **detectability / escape conditions 未测**（trusted reward recomputation、raw-policy verification、retain shield 对照）。

## 5. 进度状态与服务器任务清单（按优先级）

| 优先级 | 任务 | 目的 |
|---|---|---|
| **P0'** | ✅ 完成（B1，2026-08-16）：PPO 隔离（shield-on + at-retirement，10 seeds）**NOT REPRODUCED 1/10**；learner generality 不成立，2×2 扩展为 7/7 vs 0/16 | 补最大缺口：learner generality |
| P2 | REINFORCE + PPO × 各 8–10 seeds 完整矩阵（clean / full / shield-on，δ=2） | 把 seed 方差变成统计推断；回答"seed 2 是 lucky victim 还是可识别 susceptibility subset" |
| P1 | ⚠️ 完成但无信息量（B3，v1.7）：dense dose grid 因 run-to-run trajectory 方差不可读（fig7 恢复为 within-batch fullvC budget）；无 δ_min claim | budget realism：仅 locked batch 内 paired 对比有效 |
| P3 | ✅ 完成（B4，v1.8）：avoid fidelity PASS + shield-on 隔离 **1/3 NOT REPRODUCED**（环境特定） | 环境/task generality：生命周期模式普适、攻击 effect 环境特定 |
| 复核 | vA 版 full-phase 数据用当前代码版本重跑 | 进论文前数据一致性 |
| P4 | ✅ 完成（B5，v1.10.1+v1.12+v1.13，2026-08-17）：SAC shield-on 隔离 pooled 10-seed **POSITIVE 3/10**（s401/403/404；s402/405/408 保护性反向、s406/407/409/410 无效应） | learner-family generality（partial across-seed learner variety，禁称 off-policy generality） |
| 新增 | escape conditions（recomputation / raw verification / retain shield） | detectability 与缓解 |

**服务器注意事项**（供参考，非运行说明）：锁 git commit（`1baa6752`）+ venv 依赖版本；GPU 上 cuDNN 非确定性需先测（同 seed 两次 clean 对比），必要时 CPU 多核并行（gridworld 极小，CPU 吞吐更高）。

## 6. 文件索引

- `carr_victim_experiment/protocol.md` —— 锁定协议 + v1.1–v1.5 amendments
- `carr_victim_experiment/patches.md` —— 对上游的全部修改（可审计）
- `carr_victim_experiment/results/SUMMARY.md` —— 总摘要
- `carr_victim_experiment/results/ISOLATION_stage_report.md` —— P0 隔离实验报告
- `carr_victim_experiment/results/REINFORCE_stage_report.md`、`PPO_stage_report.md`
- `carr_victim_experiment/results/aggregate_table.csv` —— 全部 runs 汇总表
- `carr_victim_experiment/results/figures/fig1–fig5` —— 基线、clean-vs-poisoned、cumulative violations、retirement isolation、disagreement curves
- `carr_victim_experiment/upstream/` —— vendored 官方代码（PRISM 模型等；Python 代码按仓库规则不同步到 GitHub）

> 注：本仓库 .gitignore 规则"Python 代码不同步"；实验运行代码保留在本机 `carr_victim_experiment/`（venv、wheels_cache 亦不上传）。

> **2026-08-16 论文整合**：上述 Carr 结果已写入正文 Section IV（Third-Party Shield-Retirement Case Study，23-pp working build）：fidelity gate、REINFORCE 3/3 seeds 退休边界因果隔离、PPO full-phase learner boundary（1/3 seeds）、dose-response 与 bias/risk 负对照（Attack budget and susceptibility 段）。摘要与 Intro 明确区分 official SCG PPO 不转移 与 第三方 Carr PPO 1/3 seeds positive。PPO 隔离（P0'）已落地为 **1/10 NOT REPRODUCED**：论文删去 “open learner-generality boundary” 措辞，改为 “PPO retirement-boundary isolation is not reproduced at scale; the full-phase 1/3 positive is training-state-specific”，2×2 扩展为 7/7 vs 0/16。

> **2026-08-16 第二轮整合（B3/B4 + fig7 修复）**：B3 dose battery（v1.7）为 data-quality finding（跨批 trajectory 方差，fig7 由误导性 dense-grid 恢复为 committed within-batch fullvC 图，工作树与 `paper_latex/figures/` 均正确）；B4 avoid 域（v1.8）fidelity PASS、隔离 **1/3 NOT REPRODUCED**（环境特定）。论文 sec6 增补 "trajectory-variance limitation" 句与 "Environment boundary" 段（24-pp working build）；manifest 重新生成，17/17 artifact tests 通过。


> **2026-08-17 SAC v1.13 pooled + 2×2 最终整合**：SAC 隔离按协议 v1.12+v1.13 扩展至 pooled
> 10-seed 命名空间（s401–410，配置同 v1.10.1，服务器 vC 代码，防护开启隔离；s407–410 为
> Linux host 复核批次）。按锁定规则（poisoned at-ret ≥ clean at-ret +0.15 且 paired
> McNemar p<0.01）：**3/10 positive**（s401 0.207→0.561 p=5.6e-57；s403 0.218→0.513
> p=7.5e-41；s404 0.479→0.954 p=3.5e-109）；三个反向保护（s402 0.502→0.236 p=3.6e-33；
> s405 0.497→0.247 p=8.5e-30；s408 0.494→0.235 p=3.6e-32）；四个无效应（s406 0.218→0.218
> p=1.00、s407 p=0.71、s409 p=0.56、s410 p=0.48）。→ learner variety 是 **partial
> across-seed 信号，不是 off-policy generality**；off-policy learner-variety evidence
> weakens at scale (3/10)。2×2 重新计算为 **12/20 below-0.5 positive vs 0/33 ceiling
> （53 paired rows，full-phase + isolation + both domains）**，8 个例外 = avoid 域两个保护性
> + SAC 六个 non-reproducing（405/408 保护性、406/407/409/410 无效应）。fig8 已更新为
> 53 rows、fig9 为 50 rows；`sac_report.md` 为最终版；`aggregate_table_v2.csv` = 146 rows
> （+10 SAC 行）。论文摘要/Intro/sec6/Conclusion/Related Work 已按 3/10 与 12/20 vs 0/33
> 更新；摘要已 trim 回 ≤200 words；PDF 27pp、0 overfull；manifest 重生成，artifact tests
> 通过。
