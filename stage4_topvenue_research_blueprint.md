> ⚠️ **过时文档（2026-08-19 标注）。** 本文件的状态判断、待办与结论均**早于**
> 2026-08-19 的三个新实验与证据审计，其中若干结论已被推翻或收窄。
> **唯一权威的当前状态与方向请读 [`usenix_direction_audit_0819.md`](usenix_direction_audit_0819.md)。**
> 本文件保留仅为历史记录，不要据此决定下一步动作。

# Stage-4 Top-Venue Research Blueprint：certificate lifecycle attacks and gates

> 状态：顶会/顶刊导向研究蓝图 v1（2026-07-01）。目标是把当前 certificate lifecycle seed 推进成安全顶会/顶刊可审稿的 attack+defense / theory+system paper。

## 1. 最终 research gap

已有工作回答了三个相邻问题，但没有回答它们的交叉点：

1. **Severe sensor attack safety filters** 回答：当传感器攻击导致状态不唯一时，固定控制器如何对 plausible-state set 做 CBF/QP safety filtering。
2. **FT-CBF / robust MPC / secure estimation** 回答：在特定攻击、故障或有界不确定性模型下，如何让可行安全 kernel 保持非空。
3. **MFAC/MFAPC under DoS/deception** 回答：自适应预测控制如何在网络攻击下保持跟踪误差有界或频率稳定。

它们没有回答：**当控制器在部署后继续从被攻击历史中学习，证书如何随更新保持？**

关键区别是，在线学习控制器的认证对象会移动。传统 filter 只决定当前 action 是否安全；online update 会改变未来 action map。因此，FDI 不只污染 state estimation，还污染 update path，使 certificate 可能变成 stale certificate。

顶会级 gap 可以表述为：

> Existing severe-attack safety filters certify actions for a fixed controller snapshot. They do not certify the learning update that changes the future action map. Under strategic FDI, this creates a certificate-lifecycle attack surface: the current action may be filtered while the updated controller silently leaves the certified kernel.

## 2. 论文应主张什么，不应主张什么

应主张：

1. 在线更新控制器存在一个被忽略的 **certificate lifecycle attack surface**。
2. 只过滤当前 action 不足以证明 updated learner 仍处于 certified operation。
3. Sound certified learning 需要一个 **lifecycle gate**：更新后的 policy 必须在当前及未来 attacked-history kernels 内保持可认证。
4. 当 kernel 为空或 update 离开 kernel 时，系统必须在 safety certificate、learning progress、trusted-state assumption 之间牺牲至少一项。

不应主张：

1. 不主张 sensor attack 下 safety control 不可能。
2. 不主张首次提出 plausible-state set 或 CBF/QP safety filter。
3. 不主张首次研究 adaptive control under attacks。
4. 不主张 gate 是完整 controller synthesis；它是 certificate lifecycle layer。

## 3. 核心科学问题

### RQ1：learning-aware FDI 是否能制造 certificate staleness？

攻击目标不是直接让当前 action unsafe，而是让 learner 接受一个改变 future action map 的 update，使 raw policy 离开 certified kernel。

可证伪指标：在 ungated 或 action-only-filtered learner 中，`stale_certified_policy > 0` 或 `unsafe_certified > 0`。

### RQ2：action-only filtering 是否足够？

比较 robust action filter 与 lifecycle gate。若 robust action filter 每步都投影当前 action，但仍允许参数更新到 kernel 外，则它维护了当前 physical action，却没有维护 learner certificate。

可证伪指标：`unsafe_certified = 0` 但 `stale_certified_policy > 0`。这证明“action safety”和“update certification”是不同属性。

### RQ3：lifecycle gate 能否消除 unsafe/stale certified operation？

Gate 应满足：

1. kernel 非空且 candidate update 在 kernel 内：allow。
2. kernel 非空但 candidate update 离开 kernel：project/constrain/reject。
3. kernel 为空：freeze/reject/request anchor。

可证伪指标：`unsafe_certified = 0` 且 `stale_certified_policy = 0`，同时比 `always_freeze` 有更高 `learn_updates`。

### RQ4：trusted anchors 能否恢复 learning？

当 FDI ambiguity 太大导致 kernel 为空，可信状态锚点、冗余传感器、攻击隔离或 secure estimator 可收缩 `X_A(h)`，让 learning 恢复。

可证伪指标：anchor 后 kernel width 增大、cert reject rate 降低、learn update rate 恢复。

## 4. 目标系统方案：LifecycleGate

LifecycleGate 不替代 CBF/QP safety filter，而是把它提升为 update gate。

```text
Input: attacked history h_t, current policy theta_t, update rule U, certificate Gamma

1. X <- EstimatePlausibleStates(h_t, A)
2. K <- ComputeCertifiedKernel(X, Gamma)
3. theta_candidate <- U(theta_t, h_t)
4. if K is empty:
       reject certificate; freeze or rollback update; request anchor/fail-safe
5. else if pi_{theta_candidate} violates K on current or reachable attacked histories:
       project/constrain/reject theta_candidate
6. else:
       accept update and certificate
```

需要强调的工程接口：

1. `EstimatePlausibleStates` 可来自 severe sensor attack estimator、secure estimation、interval observer 或 attack hypothesis set。
2. `ComputeCertifiedKernel` 可来自 invariant set、CBF/QP、reachability tube 或 runtime shield。
3. `ProjectUpdate` 是本项目需要具体化的部分：从 action-level projection 升级到 parameter-level constrained update。

## 5. 理论升级路线

当前 theorem 是单步必要条件，顶会版本需要四个更强结论。

### Theorem A：action-only filter insufficiency

存在系统、攻击历史、update rule 和 safety filter，使得每一步 applied action 被 robust filter 投影为安全，但更新后的 raw policy 离开 certified kernel。因此 action filtering 不蕴含 learner certificate preservation。

价值：直接回应 reviewer 的“为什么不直接用 robust safety filter？”

### Theorem B：future-history lifecycle condition

若 updated learner 在未来 reachable attacked histories 上继续声称 certified operation，则必须满足：

$$
\forall h'\in\mathcal H_{\mathcal A}(h,\theta_{t+1}),\quad
\pi_{\theta_{t+1}}(h')\in K_\Gamma(h').
$$

这比当前 `pi(theta+)(h) in K(h)` 更强，避免 theorem 被认为是定义展开。

### Theorem C：monotone freeze frontier

在一类线性/仿射系统和 convex safety kernels 中，若 attack ambiguity set 单调扩张，则 certified update set 单调收缩；当 kernel 为空时，任何非平凡 certified update 都不存在。

价值：把 `rho=1/lambda` toy frontier 推广为一般现象。

### Theorem D：trusted-anchor escape condition

若 trusted anchor 将 ambiguity radius 从 `rho` 收缩到 `rho'`，且 `K_Gamma(rho')` 非空，则 certified learning 可恢复；否则只能继续 freeze/reject。

价值：避免论文过度悲观，给系统设计建议。

## 6. 初版 benchmark：已实现

脚本：`lifecycle_gate_benchmark.py`。

系统：

$$
x_{t+1}=1.2x_t+u_t,
\quad |u_t|\le 0.2,
\quad S=[-1,1].
$$

攻击历史报告 `y=0`，但 plausible-state set 为 `[-rho,rho]`。学习感知 FDI 每步把 learner action parameter 往 `+u_max` 推动。比较五种机制：

1. `ungated`：直接学习并执行。
2. `nominal_action_filter`：只按 nominal state `y=0` 过滤 action。
3. `robust_action_filter_update_ungated`：按 plausible-state kernel 过滤当前 action，但不 gate update。
4. `always_freeze`：保守冻结学习。
5. `lifecycle_gate_project`：按 certified kernel 约束 update。

关键结果摘录：

| rho | K(rho) | mechanism | unsafe_certified | stale_certified_policy | uncertified_learning | learn_updates |
|---:|---|---|---:|---:|---:|---:|
| 0.800 | [-0.040,0.040] | nominal_action_filter | 5 | 5 | 0 | 3 |
| 0.800 | [-0.040,0.040] | robust_action_filter_update_ungated | 0 | 5 | 0 | 3 |
| 0.800 | [-0.040,0.040] | lifecycle_gate_project | 0 | 0 | 0 | 1 |
| 0.900 | empty | robust_action_filter_update_ungated | 0 | 0 | 3 | 3 |
| 0.900 | empty | lifecycle_gate_project | 0 | 0 | 0 | 0 |

解释：

1. Nominal filtering 在 FDI 下会接受 unsafe certified action。
2. Robust action filtering 能让当前 applied action 安全，但 updated policy 已离开 kernel，形成 stale certificate。
3. Kernel 为空时，若仍更新，就是 uncertified learning。
4. Lifecycle gate 消除 unsafe/stale/uncertified learning，但代价是 projection 或 freeze。

这组结果已经给出顶会叙事的最小证据，但还不足以投稿。下一步必须在更接近 CPS 的 benchmark 中复现同类指标。

## 7. Two-tank CPS-style benchmark：已实现

脚本：`two_tank_lifecycle_benchmark.py`。

系统是二维液位偏差模型：

$$
x_{t+1}=Ax_t+Bu_t,
\quad A=\begin{bmatrix}1.08&0.04\\0.02&1.03\end{bmatrix},
\quad B=\begin{bmatrix}1\\0.1\end{bmatrix},
\quad |u_t|\le 0.15,
\quad x_t\in[-1,1]^2.
$$

攻击历史报告 nominal sensor reading `y=(0,0)`，但真实状态可位于 `X_A(h)=[-rho,rho]^2`。certified kernel 由对所有 box corners 的一步安全约束精确计算。学习感知 FDI 每步推动控制器参数向更大的 pump command 移动。

关键结果摘录：

| rho | K(rho) | mechanism | unsafe_certified | stale_certified_policy | uncertified_learning | learn_updates |
|---:|---|---|---:|---:|---:|---:|
| 0.800 | [-0.104,0.104] | nominal_action_filter | 4 | 4 | 0 | 3 |
| 0.800 | [-0.104,0.104] | robust_action_filter_update_ungated | 0 | 4 | 0 | 3 |
| 0.800 | [-0.104,0.104] | lifecycle_gate_project | 0 | 0 | 0 | 2 |
| 0.850 | [-0.048,0.048] | robust_action_filter_update_ungated | 0 | 5 | 0 | 3 |
| 0.850 | [-0.048,0.048] | lifecycle_gate_project | 0 | 0 | 0 | 1 |
| 0.920 | empty | robust_action_filter_update_ungated | 0 | 0 | 3 | 3 |
| 0.920 | empty | lifecycle_gate_project | 0 | 0 | 0 | 0 |

解释：

1. Two-tank benchmark 复现了 toy result：nominal action filtering 在 FDI ambiguity 下会接受 unsafe certified action。
2. Robust action filtering 可以使 applied action 安全，但如果 update 不受 gate 约束，raw updated policy 仍会离开 certified kernel，形成 stale certified policy。
3. 当 kernel 为空时，继续更新不再是 certified learning；这被记录为 `uncertified_learning`。
4. LifecycleGate 消除 unsafe/stale/uncertified learning，并在 kernel 非空时保留部分 learning updates，因此比 always-freeze 更有实用价值。

这一步把核心 insight 从 1D frontier 推进到二维 CPS-style model。它仍不是最终 top-venue 证据，但足以指导下一步真实 benchmark：更高保真 two-tank simulator、microgrid LFC 或 safe-RL controller。

## 7.1 Nonlinear two-tank benchmark：已实现

脚本：`nonlinear_tank_lifecycle_benchmark.py`。

系统是带平方根流量项的非线性 two-tank 模型，attacked history 报告 nominal level vector，interval observer 返回 nominal 周围的 plausible-state box。`certified_kernel(rho)` 通过在 box 上取网格样本计算共同一步安全动作集合。

关键结果摘录：

| rho | K(rho) | mechanism | unsafe_certified | stale_certified_policy | uncertified_learning | learn_updates |
|---:|---|---|---:|---:|---:|---:|
| 0.200 | [-0.180,0.071] | nominal_action_filter | 4 | 4 | 0 | 3 |
| 0.200 | [-0.180,0.071] | robust_action_filter_update_ungated | 0 | 4 | 0 | 3 |
| 0.200 | [-0.180,0.071] | lifecycle_gate_project | 0 | 0 | 0 | 2 |
| 0.300 | [-0.180,-0.051] | robust_action_filter_update_ungated | 0 | 5 | 0 | 3 |
| 0.300 | [-0.180,-0.051] | lifecycle_gate_project | 0 | 0 | 0 | 1 |
| 0.450 | empty | robust_action_filter_update_ungated | 0 | 0 | 3 | 3 |
| 0.450 | empty | lifecycle_gate_project | 0 | 0 | 0 | 0 |

解释：非线性水箱模型中仍然出现同一 lifecycle failure：action-only robust filtering 可以保证当前 applied action，但 update 不受 gate 约束时 raw policy 会离开 kernel；kernel 为空时继续更新属于 uncertified learning。LifecycleGate 以 projection/freeze 代价消除 unsafe/stale/uncertified learning。

## 7.2 Parameter-level update gate：已实现

脚本：`parameter_update_gate_benchmark.py`。

系统仍使用一维不稳定线性模型，但 controller 不再是单个 action 参数，而是线性策略：

$$
u=kz+b.
$$

对 future attacked observation grid 中每个 $z$，攻击族诱导 plausible interval $[z-\rho,z+\rho]$，从而得到一个 safe-action kernel。要求 $kz+b$ 落在所有这些 kernel 中，会得到关于 $(k,b)$ 的线性 halfspace 约束。Parameter gate 使用循环半空间投影把 poisoned candidate update 投回 certified parameter set。

关键结果摘录：

| rho | mechanism | stale_certified_policy | unsafe_certified | learn_updates |
|---:|---|---:|---:|---:|
| 0.700 | robust_action_filter_update_ungated | 5 | 0 | 5 |
| 0.700 | lifecycle_gate_project | 0 | 0 | 2 |
| 0.800 | robust_action_filter_update_ungated | 5 | 0 | 5 |
| 0.800 | lifecycle_gate_project | 0 | 0 | 1 |
| 0.850 | robust_action_filter_update_ungated | 0 | 0 | 5 |
| 0.850 | lifecycle_gate_project | 0 | 0 | 0 |

解释：current-action filtering 可以让当前 $z=0$ 的 applied action 安全，但不约束 future action map；因此 raw policy 在 future observation grid 上 stale。Parameter-level gate 直接约束 $(k,b)$，消除 stale certified policy，并随着 certified set 缩小逐步降低 update rate。

## 7.3 Multidimensional parameter-level gate：已实现

脚本：`matrix_parameter_gate_benchmark.py`。

系统使用 linearized two-tank dynamics，controller 为二维观测上的线性策略：

$$
u=k_1z_1+k_2z_2+b.
$$

对 $3\times3$ future attacked observation grid，每个 $z=(z_1,z_2)$ 诱导 plausible state box，并计算共同 one-step safe-action interval。要求 $k_1z_1+k_2z_2+b$ 落入所有 interval，得到 $(k_1,k_2,b)$ 上的 halfspace-certified parameter set。

关键结果摘录：

| rho | mechanism | stale_certified_policy | unsafe_certified | learn_updates |
|---:|---|---:|---:|---:|
| 0.450 | robust_action_filter_update_ungated | 5 | 0 | 5 |
| 0.450 | lifecycle_gate_project | 0 | 0 | 5 |
| 0.500 | robust_action_filter_update_ungated | 5 | 0 | 5 |
| 0.500 | lifecycle_gate_project | 0 | 0 | 5 |

解释：多维参数 gate 证明 halfspace 方案不是标量策略特例。即使 current-action filter 在 $z=(0,0)$ 处保持 applied action 安全，raw policy 在 future observation grid 上仍 stale；parameter projection 直接保持 future-history certified set membership。

## 7.4 Adaptive attacker stress test：已实现

脚本：`adaptive_attack_benchmark.py`。

攻击者不再使用固定 poison step，而是在有限候选方向中白盒选择，使 `stale_certified_policy`、`unsafe_certified` 或 forced-freeze objective 最大化；forced-freeze 场景还允许攻击者在 budget 内选择最收缩 kernel 的 ambiguity radius。

关键结果摘录：

| goal | rho budget | mechanism | uncertified_learning | stale_certified_policy | unsafe_certified | learn_updates |
|---|---:|---|---:|---:|---:|---:|
| stale | 0.800 | robust_action_filter_update_ungated | 0 | 5 | 0 | 5 |
| stale | 0.800 | lifecycle_gate_project | 0 | 0 | 0 | 1 |
| unsafe | 0.800 | robust_action_filter_update_ungated | 0 | 5 | 0 | 5 |
| unsafe | 0.800 | lifecycle_gate_project | 0 | 0 | 0 | 5 |
| freeze | 0.840 | robust_action_filter_update_ungated | 5 | 0 | 0 | 5 |
| freeze | 0.840 | lifecycle_gate_project | 0 | 0 | 0 | 0 |

解释：adaptive attacker 能稳定制造 action-filter 与 update-gate 的分离，但不能绕过 sound lifecycle gate。到 freeze frontier 后，action filter 可以拒绝当前动作却仍允许 uncertified learner update；LifecycleGate 直接拒绝 certificate/update。

## 8. 顶会级实验矩阵

### Benchmarks

优先级从高到低：

1. **Safe-Control-Gym cartpole / 2D quadrotor**：作为当前主线标准 benchmark。它有可复现 safe-control/RL 环境、传统控制与学习控制 baseline，并适合连续 FDI/adaptive attacker。
2. **EPANET / water distribution closed-loop benchmark**：作为 CPS/ICS 叙事补强。它与当前 two-tank 结果连续，但需要封装 pump/tank controller loop。
3. **Microgrid load-frequency control / PowerGym**：与 MFAPC/DoS/deception literature 对齐，适合顶刊/TIFS/TDSC 叙事。
4. **SWaT/WaDi/iTrust 靶场**：记录为 deferred track，暂不执行。短期只作为 threat realism 和 related-work anchor；中长期可申请数据/远程访问，但不阻塞当前主线。

### Current execution track

当前先执行 Safe-Control-Gym 主线：

1. Cartpole stabilization：用于快速验证 continuous adaptive attacker、action-only filter、LifecycleGate 的分离。
2. 2D quadrotor trajectory/stabilization：作为主实验，接入更强 baseline，包括 MPC、CBF/MPSC/Safety Layer、RARL/RAP 类安全/鲁棒 baseline。
3. Continuous adaptive attacker：从 finite-search update attack 升级到 PGD/CEM/CasADi-style 连续优化，目标函数联合最大化 stale margin、unsafe margin、forced-freeze margin，并加入 attack budget/stealth residual 约束。
4. EPANET track 暂列为第二阶段：完成 Safe-Control-Gym 结果后，再封装 water distribution closed-loop pump/tank benchmark。

### Controllers

至少实现两类：

1. Adaptive linear policy 或 adaptive MPC：便于形式化 update set。
2. Safe RL / neural policy fine-tuning：便于安全顶会叙事。

### Attacks

1. State ambiguity FDI：让多个 physical states 共享同一 attacked history。
2. Update poisoning：通过 manipulated logs/rewards/telemetry 推动 candidate update 离开 kernel。
3. Adaptive bypass attack：attacker 知道 LifecycleGate，优化 unsafe acceptance。
4. Freeze attack：attacker 不追求 unsafe，而是扩张 ambiguity 迫使 learning 停止。

### Baselines

1. Ungated online learner。
2. Nominal action filter。
3. Robust action filter without update gate。
4. Always-freeze。
5. Oracle trusted-state learner。
6. LifecycleGate variants：project、reject、anchor-assisted。

### Metrics

1. `unsafe_certified_rate`：证书接受但真实/plausible state 不安全。
2. `stale_certified_policy_rate`：证书接受但 raw updated policy 离开 kernel。
3. `uncertified_learning_rate`：证书拒绝后仍发生非平凡学习。
4. `learn_update_rate`：非平凡学习比例。
5. `freeze_rate` / `freeze_duration`。
6. task cost / regret / tracking error。
7. safety-filter intervention rate。
8. trusted-anchor recovery rate。
9. computation overhead。

## 9. 安全顶会论文形态

建议写成 attack+defense paper，而不是 pure theory note。

核心标题方向：

1. `Certificate Staleness in Online Learning Controllers under Sensor Deception`
2. `When Safety Certificates Must Freeze Learning`
3. `Lifecycle-Gated Certification for Online Learning Controllers under FDI`

摘要主张：

> Here we show that sensor deception creates a certificate-lifecycle vulnerability in online-updated controllers. Existing severe-attack filters can protect the action applied at the current step, but they do not certify the update that changes the controller's future action map. We demonstrate learning-aware FDI attacks that create stale certified policies, prove a lifecycle gate condition, and implement LifecycleGate to prevent unsafe or uncertified updates.

论文结构：

1. Introduction：从具体攻击例子进入 certificate staleness。
2. Background：severe sensor attack safety filters、CBF kernels、online learning controllers。
3. Threat Model：FDI/log/reward/update-data attacker，white-box adaptive attacker，defender assumptions。
4. Certificate Lifecycle Attacks：nominal unsafe、robust-action-filter stale、freeze attack。
5. LifecycleGate Design：接口、算法、projection/rejection/anchor variants。
6. Theory：Theorems A--D。
7. Evaluation：RQ1--RQ6。
8. Discussion：trusted anchors、availability tradeoff、deployment guidance。
9. Related Work。

## 10. Kill criteria and pivots

必须提前定义失败条件：

1. 若真实 CPS benchmark 中 robust action filter without update gate 足以让 raw policy 永远不离开 kernel，则 certificate lifecycle gap 变弱；需要 pivot 到 availability/freeze attack 或 parameter-level certification cost。
2. 若 LifecycleGate 基本等价于 always-freeze，说明过度保守；需要引入 trusted anchors、partial update、safe subspace learning。
3. 若 adaptive attacker 能稳定绕过 gate，说明 kernel computation 或 threat model 不 sound；需要收紧 attack family 或加入 verified estimator。
4. 若 theorem 仍被认为定义化，则必须转向更强的 multi-step reachable-history theorem 或 impossibility frontier。

## 11. 立即执行计划

1. ✅ 已完成：把 `lifecycle_gate_benchmark.py` 和 `two_tank_lifecycle_benchmark.py` 输出转成 CSV 和图：kernel width、unsafe/stale rate、learn update rate。生成脚本为 `generate_benchmark_artifacts.py`，输出位于 `results/` 和 `paper_latex/figures/lifecycle_gate_summary.pdf`。
2. ✅ 已完成：将 two-tank 从线性化模型升级到 nonlinear tank simulator，并用 interval/grid observer 估计 `X_A(h)`；脚本为 `nonlinear_tank_lifecycle_benchmark.py`。
3. ✅ 已完成：实现 parameter-level update gate；当前版本覆盖 scalar linear policy `u=kz+b` 和 two-tank 线性策略 `u=k1*z1+k2*z2+b`，均构造 halfspace-certified parameter set 并投影 poisoned update。下一步是扩展到 MPC 或 NN policy。
4. ✅ 已完成：加入 finite-search adaptive attacker，最大化 `unsafe_certified`、`stale_certified_policy` 或 forced-freeze objective。
5. ✅ 已完成：把 theorem 升级到 future-history lifecycle condition，并新增 linear-policy halfspace proposition。
6. ✅ 已完成：在 LaTeX 中新增 Threat Model、Lifecycle Attack 和 LifecycleGate Design sections，并在 Minimal Study 中接入 benchmark summary figure。
7. ✅ 已完成：记录 SWaT/WaDi/iTrust 为 deferred track；当前主线切换到 Safe-Control-Gym cartpole/2D quadrotor。已拉取官方仓库到 `external/safe-control-gym`，并在 `/home/feihm/llm-fei/.llm` 环境中安装最小依赖。
8. ✅ 已完成：新增 `safe_control_gym_lifecycle_scaffold.py` 和 `continuous_adaptive_attacker.py`。前者验证 Safe-Control-Gym cartpole/2D quadrotor rollout 并输出 `results/safe_control_gym_smoke.csv`；后者提供连续 adaptive attacker 目标和 CEM optimizer。
9. ✅ 已完成：接入官方 LQR 与 linear-MPC baseline adapter，输出 `results/safe_control_gym_controller_baselines.csv`。当前为 20-step smoke run：cartpole/quadrotor_2d 上 LQR 与 linear-MPC 均为 zero constraint violations。
10. ✅ 已完成：接入官方 cartpole CBF action-only filter，输出 `results/safe_control_gym_cbf_action_filter.csv`。`theta_push` 未认证策略 violation rate 为 0.867，CBF action filter 降到 0.033。
11. ✅ 已完成：把 continuous observation-FDI attacker 接入 cartpole，输出 `results/safe_control_gym_continuous_observation_attack.csv`。当前 CEM attack 下 attacked LQR violation rate 为 0.55，oracle-state CBF action filter 降到 0.20。
12. ✅ 已完成：新增 `safe_control_gym_plausible_set_lifecycle_gate.py`，把 oracle-state CBF 对照替换为 attacked-history plausible-set sampled one-step kernel，并把 LQR+linear residual 的 poisoned update 放入 LifecycleGate projection loop。输出 `results/safe_control_gym_plausible_set_lifecycle_gate.csv`；当前 20-step snapshot 中，attacked LQR+residual violation rate 为 0.05，plausible action-only filter violation rate 为 0.00 但 stale-certified rate 为 0.10，LifecycleGate 的 violation/stale/uncertified rates 均为 0.00，learn update rate 为 0.95。
13. ✅ 已完成：把 robust kernel 升级为 Safe-Control-Gym CasADi discrete dynamics backend，并加入 official CBF sampled backend。CasADi 10-step snapshot 输出 `results/safe_control_gym_plausible_set_lifecycle_gate_casadi.csv`：attacked LQR+residual violation rate 0.10；action-only filter violation rate 0.00 但 stale-certified rate 0.40；LifecycleGate violation/stale/uncertified rates 均为 0.00，learn update rate 1.00。
14. ✅ 已完成：单独验证 freeze-frontier，输出 `results/safe_control_gym_freeze_frontier_casadi.csv` 与 `results/safe_control_gym_freeze_frontier_casadi_highrho.csv`。`rho=0.01 -> 0.05` 下 action-only empty-kernel rate 从 0.333 上升到 1.000；`rho=0.06/0.08` 维持 action-only empty-kernel rate 1.000。
15. ✅ 已完成：新增 `safe_control_gym_paper_sweep.py`，把 Safe-Control-Gym 结果收敛成多 seed / multi-rho 聚合表与独立论文图。当前 mini sweep 输出 `results/safe_control_gym_paper_mini_aggregate.csv` 和 `paper_latex/figures/safe_control_gym_paper_mini_summary.pdf`；2-seed `rho=0.03` 下，action-only filter stale-certified rate 0.333、uncertified-learning rate 1.000，LifecycleGate stale/uncertified rates 0.000、learn-update rate 1.000。
16. ✅ 已完成：修复 universal future-history gate 的 empty-kernel 语义，并新增 `safe_control_gym_delayed_trigger_attack.py`。白盒 update-data 搜索自动选择 `(2,-0.5)` 更新方向；snapshot-commit 模型的适应阶段均无物理违规。提交后 action-only poisoned snapshot 在 42/42 clean deployment-envelope rollouts 中产生 delayed violation；局部 one-step LifecycleGate 为 1/42；带 `0.005` 鲁棒裕量的多步 CasADi commit LifecycleGate 把 pending `(18,-5)` 投影为非平凡 `(1.8,-0.5)`，达到 0/42；always-freeze 同为 0/42 但无更新。永久在线且证书覆盖组合策略 $F\circ\pi$ 的 robust filter 是明确逃逸条件，不属于该攻击模型。
17. ✅ 已完成：新增 `safe_control_gym_delayed_trigger_sweep.py`，跨 poison dose `0/4/6/8/9/10/12` 与三组未见 deployment seeds 验证。commit 前要求 trusted baseline recovery margin `0.0075`，最终接纳 191/192 held-out states；commit gate 所有剂量 0/191，action-only 在 dose 10/12 为 191/191；gate 保留 10%--35% 参数位移，freeze 为 0%。这只证明 attack 下的 update availability，不把恶意候选位移解释为有益学习。证书仍是 sampled finite-horizon guarantee，不是连续状态空间证明。
18. ✅ 已完成第一阶段真实 learner hard gate：新增线性高斯 residual REINFORCE actor，更新严格由真实 PyBullet transition/reward 的 reward-to-go policy gradient 产生；攻击者仅可添加 `L_inf <= 2.0` reward-log poison，不能写参数或梯度。3 learner seeds 的 held-out 结果为 clean `1/188`、poisoned action-only `38/188`（3/3 seeds）、commit gate/freeze `0/188`；paired exact test 为 37 poison-only 对 0 clean-only，`p=1.46e-11`。commit 对每个 poisoned pending snapshot 保留非零 5% interpolation。该结果说明攻击显著放大学习漂移风险，不声称 clean stochastic learner 绝对零风险；当前 actor 仍是低维 canonical REINFORCE，不是深度 PPO/DDPG。
19. ✅ 已完成第二系统 provisional smoke：新增 2D quadrotor lifecycle scaffold 与 2-output Gaussian residual REINFORCE learner。先修复官方 LQR 负推力请求与物理动作域之间的接口问题；手工 target scaffold 上 raw snapshot 为 12/12 delayed failures，35% commit、freeze、clipped LQR 和永久 5-step backup shield 均为 0/12。reward-only learner smoke 中攻击者仅修改 `L_inf <= 0.5` reward log；seed 2040 上 clean `0/8`、poisoned action-only `8/8`（median first=52）、55% commit/freeze/permanent shield `0/8`，适应阶段 0 violation。一步 projector 仍为 4/4 failure，不能冒充 sound permanent-filter escape condition。
20. ✅ 已完成 locked multi-seed/disjoint held-out quadrotor audit：clean `0/72`、poisoned action-only `68/72`（3/3 learner seeds；68 poison-only/0 clean-only，two-sided exact `p=6.78e-21`）、commit/freeze `0/72`；commit 分别保留 55%/40%/70% pending update。永久 5-step backup shield 为 0/12、198 interventions、0 rejection。
21. ✅ 已完成 official linear MPSC 强基线：安装 `pytope`/`pycddlib`/`cvxpy` 并加载 upstream pretrained RPI artifact。三个 poisoned snapshots 上 0/12 violations、0 infeasible solves，但 1200/1200 steps 全部干预，mean reward `-0.357`，体现显著 availability/performance cost。
22. ⚠️ official PPO hard gate 当前为阴性 safety result：pretrained clean PPO 为 0/72，normalized malicious target 为 72/72 unsafe（median first=30）；exact parameter-space reward-only attack 在 8-batch 后把 poisoned actor 推得比 clean 更接近 target，并将 reward 从 clean `0.800` 降至 `0.705`，但 clean/poison/freeze 仍均为 0/8 violations。继续提高预算或改变 threat model 前需要明确研究选择；不可把该结果写成 deep-PPO attack success。
23. 🛑 locked PPO B-lite 已触发 stop：固定预算/target/objective 下，16-batch clean 0/24、poison 1/24，但该边界级 failure 在 24-batch 消失（两者均 0/24）；两个执行前锁定的 go 条件均未通过，不启动 formal PPO multi-seed sweep，也不提高预算或改变 attacker capability。
24. 🛑 locked benign-utility gate 已触发 stop：calibration 选择 `0.003 N` differential actuator bias；开发 smoke 的 freeze/clean/gate reward 为 `-0.03617/-0.04714/-0.08097`，均为 0/12 deployment violations。LifecycleGate 在 11/12 batches 接受更新（mean fraction `0.8208`），但 0/12 paired rollouts 优于 freeze，12 次 certificate 耗时 `100.93 s`。不启动 formal，不 post-hoc 调参；按既定标准从 NDSS research track 转向 TDSC。
23. 扩充 bibliography：secure estimation/control、zero-dynamics attacks、CBF under attacks、adaptive control certification。

## 12. 当前判断

当前项目已经有清晰 gap，但还没有完整解决。真正要解决的问题不是“证明一个 gate”，而是证明：

1. 没有 update gate 时，在线学习控制器会产生 certificate lifecycle failure。
2. 这种 failure 在真实 CPS 控制任务中出现，而不是 toy artifact。
3. LifecycleGate 能以低于 always-freeze 的代价消除 unsafe/stale certified operation。
4. Trusted anchors 给出恢复 learning 的系统路径。

只要这四点成立，项目就从 position seed 变成安全顶会/顶刊可竞争的研究问题。
