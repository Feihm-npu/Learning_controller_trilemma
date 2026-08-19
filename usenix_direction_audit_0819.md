# USENIX Security 2027 — 方向审计与交接（2026-08-19）

> **本文件是当前唯一权威的状态与方向文档。**
> 它取代 `usenix_submission_status.md`、`usenix_submission_plan.md`、
> `usenix_critical_review_2026-08-19.md` 的**结论部分**，以及 `EXPERIMENT_SUMMARY.md`
> 中与本文冲突的任何陈述。那几份文件已加过时横幅，保留仅为历史。
> `*_protocol.md` 与 `carr_victim_experiment/protocol.md` **不过时**——它们是预注册记录，是证据。

目标场地不变：USENIX Security 2027。本文档记录 08-19 当天三个新实验、一次证据审计，
以及由此产生的**方向性结论与执行结果**。

> **执行更新（08-19，论文自检后）**：正文现以 V5 无对抗队列和 V6
> sign/envelope-constrained 时长实验为主证据。V6 不再被解释为“及时切换但基线已失去
> 可恢复性”：116 个接受对的配对账本为 27 个两臂都失败、19 个仅 raw 失败、7 个仅
> resident 失败、63 个都不失败。论文据此把 raw-policy warning 与 baseline handoff
> 写成两个独立证据义务。Carr 的 53-run 训练级语料、54-comparison 配置级表和
> disagreement marker 也已分开定义。第 5、7、8、9 节记录最终状态。

---

## 0. 一句话现状

论文的 lifecycle 叙事**成立且比之前结实**（两个独立实验家族，代码级确认）；
无对抗缺口从 2 个轶事升级为可推断的率估计；
而当天最重要的发现是：**一个规避任务感知检查的攻击者，在更长的受保护 bootstrap
下，既能造成 raw-release 失败，也能暴露 resident contract 的第二次授权转移问题。**
V6 中所有 34 个 resident 失败都发生在切换后，但其中 7 个没有配对的 raw-policy
失败。因此数据支持的结论不是“基线已经不可恢复”，而是：对 raw policy 的滚动检查
不能自动证明接管 baseline 从 handoff state 出发的安全性。论文已把这条
baseline-handoff obligation 前置为核心结论。

---

## 1. 当天新增的三个实验

三个 driver 都是**追加式**：不重训已锁定产物、不修改任何既有脚本、
各自写自己的 CSV。环境用 `.venv-safe-control/bin/python`（当天补装了 CPU 版 torch）。

### 1.1 clean resident 臂（补齐从未跑过的对照）

**动机**：V4 只有 `clean_release` / `poisoned_release` / `resident_predictive_simplex` 三臂，
而第三臂的 `reverse_switch_max_margin` 与 poisoned 逐行相同 120/120、与 clean 只有 4/120。
即**常驻臂只在 poisoned snapshot 上跑过**，摘要里"同一预测保留在运行时则零失败"
所对比的那一臂从未被测量。

- 脚本：`safe_control_gym_cartpole_v4_clean_resident_arm.py`
- 产物：`results/cartpole_v4_clean_resident_arm_{rollouts,summary}.csv`
- **结果：clean resident predictive authority = 0/120 violations，2 次 forward switch
  （step 7 和 6），对应 raw-release 失败在 step 11 和 10，两次都提前 4 步。**
- **harness 自校验**：`--snapshot fixed_target_tanh` 重放 poisoned 臂，复现出已锁定的
  **27 switches / 0 violations**，逐项一致。

摘要那句话现在为真——此前只是从未被测过。

### 1.2 EVID-01：20 run 无对抗队列

**动机**：无对抗缺口原本是 2/120，且两次失败都在 5 个 run 中的同一个里，
配对精确检验 p=0.50。论文自己写着"不声称未受攻击的发布普遍不安全"。

- 脚本：`safe_control_gym_cartpole_v5_clean_cohort.py`、`analyze_v5_clean_cohort.py`
- 产物：`results/cartpole_v5_clean_cohort_{rollouts,summary}.csv` + `_run.log`
- 种子命名空间：learner 2300–2319，evaluation 9300–9319（全新，无碰撞）
- **硬校验**：driver 先在旧命名空间（2100–2104/9100–9104）重跑，复现出**完全相同的
  2/120**，含两个失败状态的 index（17、22）与首次违规步（11、10），clean 参数 bit-for-bit 一致。

**结果**（五步检查接受了全部 480 个对，每 run 24/24）：

| 量 | 计数 | Wilson 95% CI |
|---|---|---|
| clean 永久 raw release 失败 | **10 / 480** = 2.08% | [1.14%, 3.79%] |
| clean resident predictive authority 失败 | **0 / 480** | [0, 0.79%] |
| **有 ≥1 次失败的训练 run** | **5 / 20** = 25% | **[11.2%, 46.9%]** |

- 配对 discordance 10 个全部指向 raw release，0 个反向 → **精确配对 p = 0.00195**
- 切换提前量中位 **4 步**（4–5）
- 失败分布在 run 2305(5)、2306(2)、2310(1)、2313(1)、2314(1)——不是单 run 伪影

**口径差异（必须写进论文）**：这批 480 的准入集由 **clean** CasADi 接受定义，
而 V4 的 120 由 **poisoned** 接受定义（锁定代码把三条臂都绑在 poison acceptance 上）。
构造不同，分母不能直接互换。

### 1.3 v6：受检测约束的攻击者 × 时长扫描

**动机**（原 SEC-01）：论文自证"有效 ⇒ 可检测"——in-loop sign gate 把 39/126 打到 0/126、
FPR 0；而两个隐蔽变体（s1 置换、s2 矩保持）满足不变量、把参数推向有害目标
（target_progress 1.87 / 2.64）却造成 **0/24** 失败，且**都只在 seed 2070 一个 realization 上跑过**。

**机理测量**（我当天补做的）：poisoned batch 的 `logged_reward_mean` 最高到 **+0.975**，
而 true reward 恒 ≤ −0.154；**60 个 poisoned batch 里 12 个 batch 均值为正**。
有效攻击的杀伤来自把 reward 推过零点，而 known-sign 检查瞄准的正是这一点。

**检测器的确切可行集**（读自 `results/cartpole_reward_detectability_calibration.csv`，seed 2070）：

| 检查 | 谓词 | 约束 |
|---|---|---|
| `trusted_recomputation` | `\|logged − true\| > 1e-8` | **任何编辑都触发；按构造排除在约束集之外** |
| `known_sign` | `logged > 0.0` | `logged ≤ 0` |
| `scalar_envelope` | 越出 `[−5.888655463318784, −0.01603442038059298]`（tol 1e-12） | **绑定约束，比 sign 更严** |
| `batch_mean_envelope` | batch 均值越出 `−0.4915801615623531 ± 2.5533217417018235` | 很松 |

两个仿真平台的 reward 都是 authenticated state/action 的确定函数，因而平台内可以做
trusted recomputation。实验刻意暴露 reward-ingestion interface 以隔离该接口被使用时的
后果，**不能作为这两个 benchmark 原生缺少 recomputation 的证据**。部署适用条件限于
reward 依赖 runtime plane 不可见的外部 KPI、延迟质量标签或人工反馈的同类接口。

- 脚本：`safe_control_gym_cartpole_v6_duration_stealth_attack.py`
- 产物：`results/cartpole_v6_duration_{rollouts,batches,summary}.csv` + `_run.log`
- 种子：learner 2400–2404 / evaluation 9400–9404；时长 `batches ∈ {12, 24, 48}`；
  条件 `clean` / `unconstrained`（论文锁定的 tanh 规则，阳性对照）/ `constrained`
- 投影：算出同样的 tanh 编辑 → 逐元素裁剪进
  `[max(−budget, min−true), min(budget, max−true)]` → batch 均值越界则整体收缩；
  **真实 reward 已在包络外超过一个预算的步，攻击者放弃编辑（poison=0）并计数**
  （这类步无论如何都会被标记，不是攻击造成的）。断言只在攻击者有可行选择的步上生效。

**完整结果（5 seed / 条件 / 时长）：**

| 时长 | 条件 | 接受对 | raw 失败 | **resident 失败** | sign 标记 | envelope 标记 |
|---|---|---|---|---|---|---|
| 12 | clean | 120 | 4 (3.3%) | 0 | 0/60 | 0/60 |
| 12 | **constrained** | 120 | **17 (14.2%)** | 0 | **0/60** | **0/60** |
| 12 | unconstrained | 119 | 36 (30.3%) | 0 | 56/60 | 56/60 |
| 24 | clean | 120 | 6 (5.0%) | 0 | 0/120 | 1/120 |
| 24 | **constrained** | 120 | **15 (12.5%)** | 0 | **0/120** | **0/120** |
| 24 | unconstrained | 120 | 16 (13.3%) | 0 | 89/120 | 96/120 |
| 48 | clean | 120 | 9 (7.5%) | 0 | 0/240 | 6/240 |
| 48 | **constrained** | 116 | **46 (39.7%)** | **34** | **0/240** | **2/240** |
| 48 | unconstrained | 117 | 54 (46.2%) | 38 | 144/240 | 160/240 |

**读法：**

1. **隐蔽是免费的，在每个时长都成立。** 受约束攻击的 known-sign 标记恒为
   0/60、0/120、0/240。envelope 标记在长时长下**比 clean 还少**（2/240 vs clean 6/240），
   因为包络在 12-batch clean 上标定，clean 自己跑长了会漂出去——这本身是
   **检测器 FPR 不跨时长稳定**的证据，值得写。
2. **"隐蔽要付一半效力"只是 duration-12 的产物。** 到 48 时 39.7% vs 无约束 46.2%，代价几乎归零。
3. **时长放大攻击**：受约束 14.2% → 12.5% → **39.7%**；clean 3.3% → 5.0% → 7.5%。

### 1.4 v6 里最重要的那条：raw-policy warning 与 baseline handoff 是两个义务

Duration 48 时 **resident predictive authority 失败 34 次**（clean 仍 0），集中在 5 个
learner seed 中的 2 个（2400 和 2403，各 17 次）。所有 34 次失败都发生在切换后，
切换后到违规中位 1 步、最多 2 步。必须同时看同一初态下的配对 raw rollout：

| raw 失败 | resident 失败 | 配对数 | 可支持的读法 |
|---:|---:|---:|---|
| 是 | 是 | **27** | 切换比配对 raw 失败早 4 步（中位；范围 4–5） |
| 是 | 否 | **19** | resident contract 避免了配对 raw 失败 |
| 否 | 是 | **7** | resident-only；不存在可定义的 raw-failure lead |
| 否 | 否 | **63** | 两个 contract 都未失败 |

这 7 个 resident-only 结果排除了“全部 34 次 resident 失败都有及时的配对 raw warning”
这一读法。实验没有构造或验证 LQR recovery set，因此也不能据此判定换一个切换时刻
是否会避免违规。可直接支持的结论是：trigger 给出的是 raw-policy warning；它不构成
baseline 从实际 handoff state 接管的安全证据。

与 Könighofer 的 lookahead 讨论相比，本文现在采用更窄且可验证的区分：horizon sweep
测量 raw-policy warning time；duration sweep 测量包含 baseline handoff 的完整 resident
contract。前者不能替代对接管 controller 的独立证据。

---

## 2. 证据审计：lifecycle 线的真实版图

一次只读审计（覆盖全仓库实验）得出，并经我用代码复核：

### 2.1 一个被推翻的怀疑

我曾怀疑只有第三方 Carr 研究真正实例化了完整 lifecycle，Safe-Control-Gym 那几个只是
"检查用一次 vs 常驻"的 CONTRACT 问题。**这被代码级证据推翻**：

- **Carr**：`rl_simulator.py` 初始化 `shield_on=True` 屏蔽每个动作，到
  `step == shield_switch_episode` 置假，train 与 eval env 同时切——一次离散的授权转移。
- **Safe-Control-Gym**：适应期 `safe_control_gym_reinforce_reward_poisoning.py:308-319`
  每步 kernel 投影覆盖动作；部署期 `safe_control_gym_cartpole_predictive_simplex_smoke.py:104-121`
  中 `clean_release` / `poisoned_release` 的 `switched` 永不为真，
  **72/120/480 个部署步一次 kernel 调用都没有**。

所以 lifecycle 由**两个独立家族**实例化，约 **49–50 个被引用的独立训练 run**（另加 v5 的 20 个）。

### 2.2 一个需要写进论文的细节

训练期过滤器**不是无条件**的：kernel 为空时代码 fall through 到未过滤动作
（`safe_control_gym_reinforce_reward_poisoning.py:316`）。但实际数据里
`rejected_action_steps = 0`、`adaptation_constraint_violations = 0`、
`action_filter_interventions = 96`——**该路径在所有报告的运行里从未触发**。
摘要"every training transition is certified safe"在数据上为真，
但**靠测量成立而非靠构造成立**。加一句话即可。

### 2.3 分类：ADJACENT 类实验吃掉了版面

审计把每个实验分为 `LIFECYCLE` / `CONTRACT` / `ATTACK-CHANNEL` / `CERTIFICATE-SEMANTICS` / `ADJACENT`。
结论：**覆盖率审计、trusted anchor、benign utility、可检测性、frontier、影响几何**
全是 ADJACENT——不测核心主张，却占大量版面。
"贡献平庸化"的观感有很大一部分来自这个编排问题，不是数据问题。

---

## 3. 已被推翻或必须收窄的旧结论

| 旧结论 | 状态 | 证据 | 论文位置 |
|---|---|---|---|
| "effective fixed attack was **readily detectable** by the task-aware checks" | **已推翻，当天已改** | v6：受约束攻击 0 标记且有效 | `sec4_evaluation.tex` §6.4、`sec3_threat_model.tex` §3.5、`sec5_related_work.tex` §8.1，claim-lock 已同步 |
| "resident predictive authority 0/120、0/72、0/71" | **已收窄** | v6 dur48：34/116 失败，其中 7 个 resident-only | 摘要、评估、讨论均把 raw-policy warning 与 baseline handoff 分开 |
| "Stealth halves the effect"（我当天写入 §6.4） | **已删除** | dur48 时代价几乎归零 | 以完整 12/24/48 时长表替代 |
| 无对抗缺口 = 2/120，不声称是率 | **已升级** | v5：10/480、5/20 run、CI 排除零 | 摘要、引言、评估、结论 |
| stealth 作为 limitation | **已改**：stealth 现在是发现不是局限 | v6 | `sec5_related_work.tex` §8.1 |

---

## 4. 证据与 artifact 问题的处置

### 4.1 三个 P0 的完成状态

1. **AUC 0.95 已从论文删除。** 原分析没有生成该数的代码路径；当天补入的
   `carr_victim_experiment/analyze_disagreement_marker.py` 可执行，但显示语料边界存在歧义：

   | 过滤 | n | positive | non-positive | AUC |
   |---|---|---|---|---|
   | 全部 shape | 58 | 15 | 43 | 0.933 |
   | 仅 contrast | 54 | 14 | 40 | 0.944 |
   | contrast + δ=2 + 排除 fixcheck | **52** | **13** | **39** | **0.947** |
   | **论文** | **50** | **11** | **39** | **0.953** |

   差 2 行，全在 REINFORCE 层（我得 22，论文 20）。根因是**去重规则只存在于当时的操作里，
   没有落到代码或散文**。
   可执行的原始 marker 表为 **58 行、15 positive、43 non-positive**；两条历史
   REINFORCE 成员判定没有可执行去重规则，因此这些原始总数不作为 marker 的分析分母。
   不依赖这两条成员判定的量为：high-band **32** 且 0 阳性、positive 最大 clean
   disagreement **0.047**、non-positive 延伸到 **0.111**、PPO **20/20**、SAC **3/10**。
   正文和附录只解释这些排除性结论；`AUC`、"50 runs"、"11 positive"、
   "eleven of 18" 及相应 claim-lock 均已删除。

2. **Carr 驱动修改已纳入 artifact。** `carr_victim_experiment/upstream/carr_reward_poisoning.patch`
   锁定上游提交 `b01dbe8b40e2167bdc1d93dea7b43e96f1a835ee`，包含
   `model_simulator.py`、`rl_simulator.py` 与 `run_carr_victim.py` 的完整修改；已在一个从该
   提交新建的干净 checkout 上执行 `git apply` 和 `git diff --check`。README 给出重建命令，
   因而审稿人可检查训练期 shield、退役事件和 reward poison 路径。

3. **`susceptibility_2x2` 已归一。** 新增 `carr_victim_experiment/susceptibility_corpus.py`，
   将 canonical 语料锁为 REINFORCE 20、PPO 20、SAC 10、avoidance 3，共 **53** 个 run；
   三个分析脚本均调用这一实现，结果固定为 low positive 12、low non-positive 8、
   high positive 0、high non-positive 33。论文同时明确：另一个 **54-comparison** 表是
   obstacle-only 配置级记账，它用 4 个复用两个 run index 的探索性比较替换 3 个 avoid
   run，因此不用于训练级 prevalence 或独立性检验；disagreement marker 又是第三套语料。

### 4.2 两个科学问题的当前处置

- **UTIL-01（已转成部署规则）**：全仓库扫描确认，**freeze 在每一个配置里都不劣于 clean adaptation**
  （benign −0.03617 vs −0.04714；cartpole −0.117 vs −0.197；quadrotor frontier −0.023 vs −0.025；
  smoke −0.0153 vs −0.0156）。benign 审计 `utility_gate_pass=False`、
  `fraction_gate_reward_better=0.0`、`paired_wilcoxon_pvalue=1.0`、`learner_seeds=1`。
  标定只扫了 bias 0.0005–0.004 N，选中的 0.003 N 的 reward loss 仅 0.0152，12 个 batch 追不回来。
  正文现明确采用选项 (b)：所研究部署没有测得的良性适应收益；只有当预先测得的适应收益
  超过授权转移风险，且每个接收 authority 的 controller 都有独立证据，运行时适应才有部署依据。
- **NOV-01（已前置）**：与 Könighofer 的 delta 已写进相关工作和讨论；本文区分
  raw-policy warning 与 baseline-handoff evidence。由于没有验证 LQR recovery set，论文不再
  主张“及时切换后基线已不可恢复”。

---

## 5. 论文当前状态

- 构建与最终门禁已完成；精确数字见第 9 节“最终锁定”记录
- manifest：`python3 generate_tdsc_reproducibility_manifest.py`（**必须在最终 PDF 构建之后跑**，PDF 在校验清单里）
- 全文**零破折号**（用户要求）；`adversary` 已统一为 `attacker`
- **Open Science 附录的匿名 artifact 链接由用户自行更新**，我未改

当天已完成的其他修改（详见 `usenix_critical_review_2026-08-19.md` 附录 B/C/D）：
撤销 CFP 禁止的空白压缩、图改名消除 PDF 内的 `tdsc` 字样、删除 IEEE 版遗留 build、
artifact 路径匿名化、新增 4 条经我逐条核实的文献、Table 1 增加 read-access 列、
Table 3 标注 snapshot 条件并加入 clean resident 行、Carr 排除脚注补齐四点事实。

---

## 6. 已执行的叙事决策

当前主线由“证据不可跨授权转移传递”具体化为两次独立的授权变化：

> **有限 release check 不能证明永久 raw release；对 raw policy 的滚动 warning
> 也不能证明 baseline handoff。**

作者已接受并执行以下顺序：

1. 主线不再把上游完整性写成充分防线：可信重算能关闭 reward 编辑通道，
   但不能证明授权移除后的长时域行为；无对抗缺口也出现在 5/20 个 run。
2. 攻击侧用 §1.4 的配对结果：受约束攻击规避检查；resident contract 在 19 个配对上
   避免 raw 失败，同时出现 7 个 resident-only 失败，因而必须单独验证 baseline handoff。
3. UTIL-01 按 4.2(b) 转成决策规则前置。
4. 主文压缩 ADJACENT 类实验，新增完整 V5 clean cohort 与 V6 duration sweep 表，
   让主张、证据和防御边界在同一条证据链上。

---

## 7. 给新 session 的操作须知

- **Python 环境**：`.venv-safe-control/bin/python`（当天补装 CPU torch）。
  **不要用** `.venv-safe-control/bin/pip`（shebang 指向旧路径，仓库搬过家）；用 `python -m pip`。
  `/home/feihm/llm-fei/.llm` 有 torch 但**没有** casadi/pybullet/gymnasium，跑不了实验。
- **shell cwd 会漂移**，所有命令用绝对路径。
- `.gitignore` 已删除全局 `*.py` 规则；Python 源文件现在会进入 `git status`，可由提交者显式纳入版本控制。
- 改任何被锁文件后：先重建 PDF，**再**跑 `generate_tdsc_reproducibility_manifest.py`，最后跑 pytest。
- 已用种子命名空间：learner 2039–2042、2050–2052(未跑)、2061–2062(保留未跑)、2070–2072、
  2100–2104、2200–2202、2210–2212、2220–2222、**2300–2319**、**2400–2404**；
  evaluation 3039、8040–8042、9070、9100–9104、**9300–9319**、**9400–9404**。
- 已知环境问题（与本次无关）：`test_lifecycle_gate_semantics.py` 等因 `safe_control_gym`
  相关依赖在收集阶段报错。

---

## 8. 当天新增文件清单

**实验 driver 与分析脚本**（均为新增，未改任何既有脚本）

| 文件 | 作用 |
|---|---|
| `safe_control_gym_cartpole_v4_clean_resident_arm.py` | 补齐 clean resident 臂（含 `--snapshot` 自校验开关） |
| `safe_control_gym_cartpole_v5_clean_cohort.py` | EVID-01 20-run 无对抗队列 |
| `analyze_v5_clean_cohort.py` | 上者的 Wilson/McNemar/run 级分析 |
| `safe_control_gym_cartpole_v6_duration_stealth_attack.py` | 受检测约束攻击 × 时长扫描 |
| `carr_victim_experiment/analyze_two_sided_and_null.py` | 双边记账 + clean-vs-clean null |
| `carr_victim_experiment/analyze_disagreement_marker.py` | 补上 AUC/band/LOFO 的缺失复现路径 |
| `carr_victim_experiment/susceptibility_corpus.py` | 53-run canonical susceptibility 语料与唯一 2×2 实现 |
| `carr_victim_experiment/upstream/carr_reward_poisoning.patch` | 锁定 Carr 上游提交的可重建驱动与 simulator 修改 |

**结果文件**

`results/cartpole_v4_clean_resident_arm_{rollouts,summary}.csv`、
`results/cartpole_v5_clean_cohort_{rollouts,summary}.csv`、
`results/cartpole_v6_duration_{rollouts,batches,summary}.csv`、
`carr_victim_experiment/results/{two_sided_accounting,clean_clean_null,disagreement_marker}.csv`

**文档**

`usenix_direction_audit_0819.md`（本文件，权威）、
`usenix_critical_review_2026-08-19.md`（当天早些时候的 124 条审稿清单 + 处置记录，仍有效但结论以本文为准）

---

## 9. 最终锁定

若与第 5 节的中间状态冲突，以本节为准。

- 最终构建：`cd paper_latex && latexmk -pdf -interaction=nonstopmode -halt-on-error usenix_sec2027.tex`
  → **0 error、0 overfull、0 undefined**
- 最终版面：**正文 13 页**；Conclusion 完整结束于第 13 页；Ethical Considerations
  是第 14 页首个内容块；总 **29 页**
- 最终 manifest：在 PDF 之后重生成，checksum inventory 覆盖 **310 个文件**，含 V4/V5/V6
  脚本与结果、Carr driver patch、server scripts、canonical susceptibility 实现和最终 PDF
- 最终门禁：
  `PYTHONDONTWRITEBYTECODE=1 .venv-safe-control/bin/python -m pytest test_tdsc_submission_artifacts.py -q -p no:cacheprovider`
  → **24/24 通过**
- 完整本地测试：`PYTHONDONTWRITEBYTECODE=1 .venv-safe-control/bin/python -m pytest -q -p no:cacheprovider`
  → **81/81 通过**；仅有 3 条 CVXPY solver accuracy warning，无测试失败
- Carr 重建：锁定上游提交的新 checkout 上 `git apply` 与 `git diff --check` 均通过
- Git 可见性：全局 `*.py` 忽略规则已删除，新增源文件和 CSV 均不再被忽略；当前混合工作树
  未由本次执行自动提交，提交者应按 manifest inventory 纳入正式 artifact commit
- 唯一仍需作者在投稿系统完成的动作：用匿名归档的实际地址替换 Open Science 中的匿名
  artifact 链接/记录；本地源、清单和校验已就绪
