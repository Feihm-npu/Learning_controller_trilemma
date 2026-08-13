# Stage-3 可行性计划：从三难到可证明边界

> 状态：stage-3 入口计划（2026-06-30）。基于 `stage1_problem_formalization.md` 与 `gap_matrix.md`，并补充复核 ISAACS、Gameplay Filters、FIRA、BADControl、adversarial RL safety certification、Certified Continual Learning 等最高风险近邻后的收敛判断。

## 1. 主线选择

主线选择：**命题 B：可信状态缺失下的不可能性边界**。

原因：

1. 它最贴近 security 论文的强项：用不可区分性刻画 FDI/欺骗对手，而不是再做一个控制/机器人 safety filter。
2. 它能明确避开 ISAACS/Gameplay Filters：这些工作处理 disturbance/model error/sim-to-real gap，并假设 safety rollout 的状态语义可信；本主线攻击的是“证书所依据的观测历史是否对应真实状态”。
3. 它能吸收 Certified Continual Learning 的启发，但对象从 NN 回归证书换成闭环物理安全证书，并加入策略性 FDI。
4. 它给出清晰三难：若没有可信状态锚点，certified safety + strategic security 会迫使控制器冻结到极保守安全核，从而牺牲 nontrivial learning。

命题 C 保留为逃逸条件：如果存在可信最小传感子集、状态不确定集足够小、更新幅度受限和增量证书检查，则可以得到条件性可能框架。命题 A 作为中间 lemma：证书一般不在学习更新算子下自动保持。

## 2. 可证明问题表述

目标定理雏形：

给定闭环系统、观测通道和在线更新规则。若存在两个真实状态轨迹 $\tau^+$ 和 $\tau^-$，它们在攻击者 FDI 下对控制器、更新规则和认证器产生相同观测历史，但在某个时刻需要互斥的安全控制动作集合，则任何只依赖该历史的机制都无法同时：

1. 对两个真实轨迹都维持闭环 safety certificate。
2. 抵抗该策略性 FDI 对手。
3. 在该歧义区域执行非平凡学习更新或性能驱动动作。

换言之，系统只能三选二：

| 选择 | 得到 | 失去 |
|---|---|---|
| safety + security | 必须拒绝证书、冻结学习或切到极保守 fallback | learning |
| safety + learning | 在标称/有界扰动下可证 | security |
| security + learning | 可持续适应攻击环境 | certified safety |

## 3. 最小 toy theorem

使用一维不稳定线性系统：

$$
x_{t+1}=\lambda x_t+u_t,\quad |u_t|\le u_{\max},\quad y_t=x_t+a_t,\quad S=[-1,1]
$$

其中 $\lambda>1$。控制器、学习器和认证器只能看到 $y_{0:t}$ 与自身动作历史。攻击者通过 $a_t$ 让两个不同真实状态产生相同观测，例如 $y_t=0$。

在状态 $x^+=1-\epsilon$ 附近，保持安全要求：

$$
u_t \le 1-\lambda(1-\epsilon)
$$

在状态 $x^-=-1+\epsilon$ 附近，保持安全要求：

$$
u_t \ge -1+\lambda(1-\epsilon)
$$

当 $\lambda(1-\epsilon)>1$ 时，两侧安全动作集合可以变成互斥或只剩极小交集。若观测历史相同，任意确定性控制器必须输出同一 $u_t$，因此无法同时证明两个真实状态下一步都安全。随机控制器也只能把违反概率分配到其中一个世界，不能给确定性 safety certificate。

该 toy theorem 的关键不是“攻击者任意改所有传感器所以无解”，而是：**一旦 FDI 使真实状态集合跨越需要相反控制动作的安全边界，任何基于单一观测历史的证书都必须撤销；如果仍允许学习更新或性能动作，就会失去 certified safety**。

## 4. 学习维度如何进入

仅证明 sensor spoofing 下控制不可能还不够，必须让 learning 成为定理的一部分。建议用三步方式嵌入：

1. 更新同态性：若两个世界产生相同观测/奖励/日志历史，则 $U$ 产生相同 $\theta_{t+1}$。
2. 证书不守恒：即使 $\pi_{\theta_t}$ 对一个状态不确定集有证书，$U$ 的非零更新可改变 action map，使原有安全动作交集变小或消失。
3. 三难结论：认证器若要对 A2/A3 FDI sound，就必须在歧义集过大时拒绝更新、拒绝证书或强制 fallback；因此 nontrivial online learning 只能在可信状态不确定集足够小时发生。

可形式化为一个 gating theorem：

$$
\mathsf{LearnAllowed}(H_t)=1 \Rightarrow \bigcap_{x\in X(H_t)} U_{safe}(x,\theta_t) \ne \emptyset
$$

其中 $X(H_t)$ 是观测历史 $H_t$ 下所有过程一致真实状态集合，$U_{safe}$ 是下一步或多步证书允许的动作集合。若交集为空，则任何继续学习并输出性能动作的机制都不能同时 sound。

## 5. Hero experiment

最小实验只需证明定理直觉，不需要大系统：

| 实验组 | 设置 | 预期结果 |
|---|---|---|
| Fixed robust fallback | 不学习，只用最保守动作/停止策略 | safety 保持，但性能和学习为零 |
| Online learner under nominal data | 用安全域内数据更新 $K_t$ 或策略参数 | 标称性能提升，证书可重算 |
| Online learner under process-consistent FDI | 攻击者维持 $y_t$ 安全、真实 $x_t$ 漂移 | 旧证书失效，真实状态越界 |
| Certificate-gated learner | 只有 $X(H_t)$ 的 safe-action 交集非空才更新 | 安全保持，但在攻击下频繁冻结，展示 learning 被 security+safety 压缩 |
| Trusted anchor variant | 给一个可信符号/区间传感器或状态 bound | 部分恢复学习，作为命题 C 正例 |

核心图：横轴攻击强度/状态歧义半径，纵轴分别画 certified region、learning update rate、unsafe rate。预期出现三难相变：攻击强度越大，要维持 certified safety，学习更新率越接近 0。

## 6. 论文贡献雏形

如果 stage-3 可行，贡献可以写成：

1. 形式化：提出 learning controller certificate lifecycle under strategic FDI 的模型，区分 disturbance robustness 与 security deception。
2. 不可能性：证明观测不可区分且安全动作互斥时，任何历史依赖认证/更新机制无法同时满足 safety-security-learning。
3. 边界框架：给出 certificate-gated learning 的必要条件，说明可信状态锚点、歧义集大小和更新幅度如何决定学习是否允许。
4. 实证：用低维系统和一个 CPS benchmark 展示固定 robust filter、普通在线学习和 certificate-gated learning 的三难曲线。

## 7. 需要立即复核的 novelty risks

| 文献 | 当前判断 | 下一步 |
|---|---|---|
| ISAACS | disturbance/model error safety filter；非 FDI，非在线更新 | 摘录正文中 disturbance/admissible uncertainty 定义 |
| Gameplay Filters | online runtime imagination；offline learning safety filter；非部署后更新证书 | 摘录 state/dynamics/disturbance 和 filter 定义 |
| *Certifying Safety in RL under Adversarial Perturbation Attacks* | POMDP 输入扰动与 PSRL safety；非工业 FDI/更新 | 复核是否有多步策略攻击/更新机制 |
| *Certified Continual Learning for NN Regression* | 证书随再训练保持，但非闭环控制 | 复核其 certificate definition，作为命题 A 背景 |
| FIRA | UAV online learning 事故归因，非预防性证书 | 摘录其 forensic/causal attribution 定位 |
| BADControl | PID/LQR 后门攻击，非在线学习证书 | 摘录 poisoning + physical trigger + low-level controller 定位 |
| TIFS-[118] | DoS 下 model-free adaptive predictive control，最强本地 risk | 需读摘要/正文确认是否有 deception/FDI 与 invariant certificate |
| TDSC-[86] | ML feed-forward recovery from physical attacks | 需确认是 recovery controller 还是 safety-certified learning |

## 8. Stage-3 完成标准

1. 写出 toy theorem 的正式假设、结论和证明草稿。
2. 明确攻击者不是全能：限制为过程一致 FDI、传感器子集或状态歧义半径。
3. 给出 certificate-gated learning 的必要条件或伪代码。
4. 完成一个可复现实验脚本或至少手算数值例子。
5. 复核最高风险文献，确认没有直接证明同一不可能性。

当前进展：第 1-3 项的证明草稿已固化到 `stage3_toy_theorem.md`，第 4 项的手算数值例子已固化到 `stage3_minimal_example.md`，invariant/barrier/reachability/shield 推广已固化到 `stage3_certificate_extension.md`，certificate-gated learner 伪代码与 1D demo 已固化到 `stage3_certificate_gated_learner.md` 和 `certificate_gate_demo.py`，trusted-anchor / learning-aware FDI variants 已加入 demo，新颖性风险更新见 `stage3_novelty_risk_update.md`。最新复核显示 `Safety of Linear Systems under Severe Sensor Attacks` 是最强邻居并已覆盖 fixed-controller plausible-state CBF/QP safety filter；修订后的贡献定位见 `stage3_revised_positioning.md`。下一步按该定位改写 theorem/贡献叙事。

## 9. Stage-3 kill criteria

1. toy theorem 只能证明“无可信传感器就无法控制”的常识，而无法体现学习更新或证书生命周期。
2. 正例/逃逸条件变成完整鲁棒 MPC/CBF 框架，吞掉主线并撞控制文献。
3. TIFS-[118] 或相邻自适应控制论文已经处理 deception attacks + adaptive controller + invariant/safety certificate。
4. 实验曲线无法区别 bounded disturbance、sensor FDI 和 learning-aware FDI。
5. 贡献无法落到 security venue 熟悉的不可区分性/对手模型语言。
