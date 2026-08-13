# Stage-3 Novelty Risk Update：自适应控制、deception attacks 与 CBF 正结果

> 状态：原文深读复核 v2（2026-07-01）。目的不是完整综述，而是记录 stage-3 theorem 需要避开的最高风险邻域。

## 1. 当前结论

公开检索未发现直接覆盖“在线更新学习控制器 + 策略性 FDI/deception + 闭环安全证书 + 证书-学习冻结/不可能性边界”的工作。但存在三类强邻居，必须在论文中主动区分：

1. model-free adaptive predictive control under DoS/deception attacks。
2. robotic vehicle physical-attack recovery using ML/feed-forward controllers。
3. sensor attacks/faults 下的 FT-CBF、secure estimation、robust MPC 正结果。

我们的 theorem 不能声称“FDI 下安全控制不可能”。准确表述应是：当攻击诱导的状态歧义集 $X_{\mathcal A}(h)$ 使 certified kernel $K_\Gamma(h)$ 为空时，sound certificate 必须拒绝或冻结 learning；已有正结果可被解释为通过 secure estimation、冗余传感、攻击模型或 robust design 让 $K_\Gamma(h)$ 非空。

## 2. 高风险邻居

| 工作/方向 | 已覆盖 | 为什么仍未直接回答本方向 | 风险等级 |
|---|---|---|---|
| TIFS-[118], *Event-Triggered Model-Free Adaptive Predictive Control for Networked Wind-Power Microgrids Subject to Aperiodic DoS Attacks* | model-free adaptive predictive control；wind-power microgrid load-frequency control；aperiodic DoS；attack-aware gain optimization | 原文复核确认其攻击是 availability/packet dropout 型 DoS，保证是 frequency recovery、system stability 与 tracking error uniformly ultimately bounded；不是过程一致 FDI 状态不可区分，也不是在线学习控制器的 safety certificate lifecycle 冻结边界 | 高 |
| *Event-Triggered Model-Free Adaptive Predictive Control for Networked Control Systems Under Deception Attacks*，IEEE TSMC 2024 | model-free adaptive predictive control；multiplicative/additive deception attacks；networked nonlinear control systems | 原文复核确认其保证是 mean-square tracking-error boundedness；没有 invariant/barrier/reachability certificate，也没有 $X_{\mathcal A}(h)$、certificate lifecycle、update gate 或 learning freeze | 很高 |
| TDSC-[86], *Feed-Forward Controller-Based Recovery for Robotic Vehicles From Physical Attacks* | ML 设计 feed-forward recovery controller；sensor/physical attacks；robotic vehicle recovery | 是攻击后 recovery 框架，不是部署后在线更新控制器的 certified safety-security-learning 边界；公开摘要未显示 invariant/barrier 证书生命周期 | 高 |
| BADControl, USENIX Security 2026 | PID/LQR 低层控制器后门；physical triggers；poisoned operational data | 强 security/control 攻击邻居，但控制器是被后门化的低层 PID/LQR，不是在线 learning controller 维持 safety certificate | 高 |
| FIRA, USENIX Security 2026 | UAV online learning crash forensics；backdoored online learning model attribution | 确认在线学习可导致 UAV crash，但目标是事后归因/取证，不是运行时证书保持或不可能性边界 | 中高 |
| Clark/Li/Zhang 等，*Control Barrier Functions for Safe CPS Under Sensor Faults and Attacks*, CDC 2020 | sensor faults/attacks；fault-tolerant CBF；概率/条件安全保证 | 这是 CBF 正结果，依赖故障/攻击模型与估计集合；不处理 online learning update 证书生命周期。应作为“当 $K_B(h)$ 非空时可行”的正例 | 很高 |
| Zhang/Li/Clark 等，safe nonlinear systems under faults/attacks via CBFs, TAC 2025 附近 | nonlinear FT-CBF；sensor/actuator fault/attack；闭环安全正结果 | 同上，是条件性可能框架；我们的 theorem 必须限定在 $K_\Gamma(h)=\emptyset$ 的边界 | 很高 |
| *Safety of Linear Systems under Severe Sensor Attacks*, CDC 2024/arXiv 2409.08413 | omniscient sensor attacker；secure state reconstruction non-unique；exact set of plausible states；offline safe-set design；online CBF/QP safety filter | **最强技术邻居**。它已经明确处理 $X(h)$ 非单点和 CBF safety filter，几乎覆盖我们的 $X_{\mathcal A}(h)$/$K_B(h)$ 正例框架；但它不处理在线更新学习控制器、证书生命周期、learning-aware FDI 或 $K_\Gamma(h)=\emptyset$ 时 certified learning 必须冻结的三难表述 | 极高 |
| Secure estimation/control 经典线：Fawzi/Tabuada/Diggavi, Pasqualetti/Dörfler/Bullo, Mo/Sinopoli | FDI 不可检测/不可识别/可校正条件；secure estimation/control | 底层不可区分性已知，不能当新贡献。新意必须是把不可区分性接到 learning controller certificate lifecycle 与 learning-freeze frontier | 基础必引 |
| Robust/deception MPC | deception attacks；recursive feasibility/stability；robust MPC | 正结果，通常假设 bounded deception/known uncertainty；没有部署后 learning update 的证书冻结边界 | 中高 |

## 3. 对 theorem 表述的约束

为了避开已有正结果，后续 theorem 应遵守以下限定：

1. 不说“FDI 下安全控制不可能”。只说当 $K_\Gamma(h)=\emptyset$ 时，历史依赖的 certified learner 不能同时接受证书并继续 nontrivial learning。
2. 不说“首次研究 deception attacks 下 adaptive control”。已有 model-free adaptive predictive control under deception/DoS。
3. 不说“首次把 CBF 用于 sensor attacks”。已有 FT-CBF/NCBF/CBF under sensor faults and attacks。
4. 不说“首次证明隐蔽攻击不可检测”。经典 secure estimation/attack detection 已覆盖。
5. 必须把已有正结果纳入统一解释：它们通过攻击隔离、状态估计、冗余、bounded uncertainty 或 robust controller 使 $X_{\mathcal A}(h)$ 足够小，从而让 $K_\Gamma(h)$ 非空。

## 4. 可用于论文的定位句

候选定位：

> Prior work provides positive safety controllers under specified sensor faults, deception attacks, or robust uncertainty models. Our question is complementary: when an online-updated controller certifies safety from an attacked observation history, what must the certificate range over? We show that it must range over the entire FDI-induced indistinguishability set. When this set admits no common certified action, a sound mechanism must either reject the certificate, freeze learning, or obtain a trusted state anchor.

中文版本：

> 既有工作给出了若干攻击模型下的安全控制正结果；本文的问题不是否定这些正结果，而是问：当控制器依据可能被 FDI 污染的历史继续学习并签发证书时，证书必须覆盖什么对象？我们的答案是，它必须覆盖整个 FDI 诱导的状态不可区分集；一旦该集合上不存在共同可认证动作，sound 机制就必须撤销证书、冻结学习或引入可信状态锚点。

## 5. 下一步复核清单

1. 已精读 *Event-Triggered Model-Free Adaptive Predictive Control for Networked Control Systems Under Deception Attacks*；结论：无 invariant/barrier/reachability certificate 或 online learning certificate lifecycle。
2. 已精读 TIFS-[118]；结论：DoS 下的 adaptive predictive compensation 给稳定/跟踪保证，不给 safety certificate lifecycle。
3. 精读 TDSC-[86]，确认 feed-forward recovery 是否给形式化 safety invariant。
4. 精读 CDC 2020 FT-CBF 与后续 TAC/linear severe sensor attacks 工作，把它们放到 $K_B(h)\ne\emptyset$ 的正例框架中。
5. 若任一工作已经明确证明 $K_\Gamma(h)=\emptyset$ 时 certified online learning 必须冻结，则本方向需要降级或改写。

## 6. 深读进展：Severe Sensor Attacks 是最强邻居

`Safety of Linear Systems under Severe Sensor Attacks` 的公开 HTML 显示它与本方向有高度交集：

1. 攻击者模型很强：omniscient attacker，可任意 spoof 若干传感器，只限制被攻击传感器数量。
2. 它显式处理 secure state reconstruction 不唯一的 severe case。
3. 它定义并刻画所有 plausible initial/current states，而不是依赖单点估计。
4. 它用 CBF 给出 offline safe-set design 和 online QP safety filter。
5. 它的问题表述是：在传感器攻击下能否保证 linear system safety。

这意味着我们的 `stage3_certificate_extension.md` 中关于“证书必须覆盖整个 $X_{\mathcal A}(h)$”的思想在固定控制/CBF 场景中已有非常接近的正结果。后续必须调整贡献表述：

1. 不把“plausible state set under sensor attacks”当作新对象。
2. 不把“CBF/QP safety filter over all plausible states”当作新贡献。
3. 新意必须落在 **online-updated learning controller**：更新规则 $U$ 如何在被攻击历史上改变 action map，证书如何随更新失效，何时 sound 机制必须冻结 learning。
4. `certificate_gate_demo.py` 中的 `learning-aware FDI` variant 需要升级为主实验，而不是附录：它展示攻击不只扩大状态歧义集，还诱导候选更新越过 safe kernel。
5. 定理应改写为“已有 severe sensor attack safety filter 给出 $K_\Gamma(h)\ne\emptyset$ 时的控制正结果；我们补充 $K_\Gamma(h)$ 与在线学习更新之间的必要门控边界”。

推荐新的贡献边界：

| 维度 | Severe Sensor Attacks | 本方向应聚焦 |
|---|---|---|
| 状态不确定性 | exact plausible state set | 采用/引用，不主张新 |
| 安全证书 | CBF/QP safety filter | 采用为 $K_B(h)$ 正例 |
| 控制器 | fixed/non-learning safety control | online-updated learning controller |
| 攻击影响 | spoofing causes state ambiguity | spoofing also poisons update data/reward/logs |
| 主要结论 | 如何在 severe attacks 下保持 safety | 何时 safety+security 强制 learning freeze / certificate withdrawal |

## 7. 深读进展：MFAPC under deception/DoS

本节记录两篇 MFAPC 攻击场景论文的内容层面复核结论。

1. *Event-Triggered Model-Free Adaptive Predictive Control for Networked Control Systems Under Deception Attacks*，Fanghui Li and Zhongsheng Hou，IEEE TSMC 2024，DOI `10.1109/TSMC.2023.3326823`。
2. 本文处理 unknown discrete-time nonaffine nonlinear NCS，经 dynamic linearization 得到 data model；反馈通道 deception 被建模为 `z(t)=ζ(t)ψ(t)+(1-ζ(t))y(t)`，其中 `ψ(t)=g(t)(y(t)+ω(t))`，覆盖 multiplicative 和 additive deception factors。
3. 控制器是 event-triggered MFAPC，在线估计 PPD `ξ(t)`，用 I/O 数据更新预测控制输入；论文明确说不做 deception attack detection，只使用测得的 `z(t)` 构造控制器。
4. 主要理论保证是 Theorem 2：在参数条件下 tracking error `E{e(t)}` 随时间趋于有界；结论部分再次表述为 mean-square tracking-error boundedness，并分析 tracking-error 上界和 attack coefficients。
5. 未发现方法层面的 `certificate`、`barrier`、`invariant`、`reachability`、`kernel`、`lifecycle`、`freeze` 或 learning-update gate。该文证明 attacked NCS 的自适应预测控制可保持跟踪误差有界，但没有回答 certified online learner 在 FDI-induced state ambiguity 下何时必须冻结。

DoS microgrid 论文深读结论：

1. *Event-Triggered Model-Free Adaptive Predictive Control for Networked Wind-Power Microgrids Subject to Aperiodic DoS Attacks*，Rui Hou, Li Jia, Xuhui Bu, and Jianfang Li，IEEE TIFS 2026，DOI `10.1109/TIFS.2026.3657840`。
2. 本文目标是 nonlinear networked wind-power microgrid 的 load frequency control；DoS 攻击被建模为通信可用性下降/packet hijacking，二值变量 `ς_i(s)` 表示数据包正常传输或被 hijacked，并用累计 attack duration 和 switching frequency 的 deterministic bounds 描述 aperiodic DoS。
3. 方法是 secure ET-MFAPC：在线估计 PPD，multi-step adaptive prediction，receding-horizon optimization，DoS 期间暂停 ETM、复用 attack 前最后有效 packet，并通过预测补偿重构缺失输出。
4. 主要理论保证是 Theorem 1：在 attack frequency/duration 条件下实现 frequency recovery 和 system stability；证明 tracking error uniformly ultimately bounded，并给出 tolerable attack frequency/duration 边界。
5. 它不处理 integrity-type FDI 的 plausible-state set；文中只说若是 false-data injection 或 replay，需要额外 lightweight integrity-preserving preprocessing 以保证 bounded residuals。它也没有 physical safety certificate、barrier certificate、certificate lifecycle、update gate 或 learning freeze。

因此两篇 MFAPC 论文应被定位为“adaptive/predictive control under attacks already exists”。它们迫使我们避免声称首次研究攻击下自适应控制；但不直接吃掉 certificate-lifecycle trilemma，因为它们证明的是 tracking/stability/performance under specified network attacks，不是 sound safety certificate 对整个 $X_{\mathcal A}(h)$ 的覆盖要求，也不是 $K_\Gamma(h)=\emptyset$ 时 certified learner 必须拒绝、回滚或冻结的必要边界。

## 8. 立即策略调整

后续写作和 theorem 应做三点调整：

1. 把 `Safety of Linear Systems under Severe Sensor Attacks` 作为最强正例 baseline：它解决 fixed-controller safety under severe sensor attacks。
2. 把我们的 theorem 从“sensor FDI 下证书必须覆盖状态歧义集”升级为“在已有状态歧义安全过滤框架上，online update 必须被 kernel gate 约束；否则 certificate lifecycle 不 sound”。
3. 在 demo 中增加一个对照：`fixed severe-attack safety filter` 能安全但不学习；`certificate-gated learner` 在 kernel 非空时学习、kernel 空时冻结；`ungated learner` 在 learning-aware FDI 下 unsafe。
