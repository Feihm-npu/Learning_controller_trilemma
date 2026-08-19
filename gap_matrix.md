> ⚠️ **过时文档（2026-08-19 标注）。** 本文件的状态判断、待办与结论均**早于**
> 2026-08-19 的三个新实验与证据审计，其中若干结论已被推翻或收窄。
> **唯一权威的当前状态与方向请读 [`usenix_direction_audit_0819.md`](usenix_direction_audit_0819.md)。**
> 本文件保留仅为历史记录，不要据此决定下一步动作。

# 近邻文献 Gap Matrix：learning controller trilemma

> 状态：stage-1 初稿（2026-06-30）。来源包括本目录 round-6 核验、本地 `raw_materials/TDSC|TIFS|top4|AI_conferences` 轻量核验，以及外部近邻检索。目标是判断是否已有工作直接回答“在线更新学习型控制器 × 策略性 FDI/欺骗对手 × 闭环安全证书”。

## 1. 判定轴

| 轴 | 是什么 | 为什么关键 |
|---|---|---|
| 在线更新控制器 | 部署后控制策略 action map 会因学习而改变 | 区分传统固定控制器认证 |
| 策略性 FDI/欺骗对手 | 对手理解过程和控制器，操控传感/观测/奖励/日志 | 区分普通有界扰动和 security threat |
| 闭环安全证书 | 证明真实物理状态保持在安全包络内 | 区分经验 attack/defense 和 certification |
| 形式化结论 | theorem、证书、可达性、屏障、不可区分性或不可能性 | 区分系统演示和 foundational gap |

直接命中需要四轴同时较强成立，尤其前三轴必须同时成立。

## 2. 外部近邻

| 文献 | 在线更新控制器 | 策略性 FDI/欺骗 | 闭环安全证书 | 形式化结论 | 为什么没答 |
|---|---:|---:|---:|---:|---|
| Tran et al., *Safety Verification of Cyber-Physical Systems with Reinforcement Learning Control*, EMSOFT/TECS 2019 | 否 | 否 | 是 | 是 | 验证固定 RL/NN 控制器；没有在线更新和 FDI 对手。 |
| Hsu et al., *ISAACS: Iterative Soft Adversarial Actor-Critic for Safety*, L4DC 2023 | 否 | 部分 | 是/部分 | 是/部分 | 对手是扰动/模型误差式 safety game，不是过程感知 FDI；部署控制器不学习更新。 |
| Nguyen et al., *Gameplay Filters: Robust Zero-Shot Safety through Adversarial Imagination*, CoRL/PMLR 2024/2025 | 否 | 部分 | 是/部分 | 是/部分 | 运行时“想象”博弈不是在线更新；对手是物理扰动/模型误差，不是欺骗传感和学习数据。 |
| Wu/Sibai/Vorobeychik, *Certifying Safety in RL under Adversarial Perturbation Attacks*, 2022/2024 | 否 | 部分 | 部分 | 是 | 面向观测扰动半径/PSRL 安全，不是工业过程一致 FDI，也不处理证书随更新保持。 |
| Lütjens et al., *Certified Adversarial Robustness for Deep Reinforcement Learning*, CoRL 2020 | 否 | 部分 | 否/部分 | 是 | 证明 action-value/动作选择鲁棒，不是闭环物理安全不变性。 |
| Pham & Sun, *Certified Continual Learning for Neural Network Regression*, ISSTA 2024 | 是 | 否 | 否/部分 | 是 | 维护 NN 回归性质，不是控制闭环证书；没有 FDI/security 对手。 |
| Jacklin/NASA, *Closing the Certification Gaps in Adaptive Flight Control Software*, AIAA 2008 | 是/部分 | 否 | 部分 | 否/部分 | 点名自适应飞控认证缺口，但无现代 RL/NN security 对手和形式化闭环证书。 |
| Jiang/Liu/Kong, *Backdoor Attacks on Safe RL-Enabled CPS*, EMSOFT/TCAD 2024 | 部分 | 是/部分 | 否 | 部分 | 证明 safe RL 可被攻击，不给证书保持、撤销或不可能边界。 |
| Chen et al., adversarial/MARL FDI detection in smart grid, 2024 | 否 | 是 | 否 | 部分 | 学习主体多为攻击/检测器，不是在线更新控制器；目标是检测而非 certified safety。 |
| Eghtesad et al., MARL for FDI attacks on transportation networks, AAMAS 2024 | 否 | 是 | 否 | 部分 | 搜索策略性数据注入攻击，不处理工业控制器证书。 |
| Cullen et al., *Position: Certified Robustness Does Not (Yet) Imply Model Security*, ICML 2025 | 否 | 概念层 | 否 | 否 | 支持“certificate ≠ security”论点，但不是 CPS/control 定理。 |

## 3. 本地语料高相关条目

| 编号 | 论文 | 在线更新控制器 | 策略性 FDI/欺骗 | 闭环安全证书 | 形式化结论 | 作用 |
|---|---|---:|---:|---:|---:|---|
| TIFS-[118] | *Event-Triggered Model-Free Adaptive Predictive Control for Networked Wind-Power Microgrids Subject to Aperiodic DoS Attacks* | 是/部分：在线 PPD 估计、预测补偿、attack-aware gain optimization | 部分：aperiodic DoS/packet hijacking，非过程一致 FDI | 否：frequency recovery/stability，不是 physical safety certificate | 是：UUB tracking error 与 tolerable attack duration/frequency | 原文复核确认是自适应控制+DoS 正结果；不处理 plausible-state safety kernel 或 learning freeze gate。 |
| IEEE TSMC 2024 | *Event-Triggered Model-Free Adaptive Predictive Control for Networked Control Systems Under Deception Attacks* | 是/部分：在线 PPD 估计与 ET-MFAPC | 是/部分：multiplicative/additive feedback-channel deception | 否：tracking control，不是 invariant/barrier/reachability certificate | 是：mean-square tracking-error boundedness | 最接近“adaptive control + deception”的风险项；但无 certificate lifecycle、$X_{\mathcal A}(h)$ 或 update freeze。 |
| TDSC-[86] | *Feed-Forward Controller-Based Recovery for Robotic Vehicles From Physical Attacks* | 部分 | 是 | 否/不清 | 不清 | ML 控制器恢复+物理攻击，需复核是否有形式化 safety。 |
| top4-[110] | *BADControl: Backdoor Attacks Against Control Systems* | 否 | 是 | 否 | 不清 | 控制系统攻击邻居，支持 safe controller 可被攻击。 |
| top4-[59] | *FIRA: Enabling Automatic Forensic Investigation of UAVs* | 部分 | 部分 | 否 | 否/不清 | 涉及 UAV online-learning/backdoor 取证，偏事后分析。 |
| TDSC-[15] | *Distributed Cooperative Control for Heterogeneous Connected Systems With Uncertainty and Cyber-Attacks* | 否/不清 | 部分 | 部分 | 是/可能 | 控制理论型 cyber-attack 保证，但未见学习更新和证书生命周期。 |
| TIFS-[25] | *Unfairness Attack and Unified Provable Defense on AI-Powered Internet of Energy* | 部分 | 部分 | 否/不清 | 是 | AI-powered energy provable defense，需避免与“能源 AI 攻防”混淆。 |
| TDSC-[81] | *Analysis on the Feasibility of D-FACTS Devices for Localizing FDI Attacks in Smart Grids* | 否 | 是 | 否 | 是 | 支持 FDI 威胁模型，不是控制器认证。 |
| TIFS-[216] | *Bilevel Cyber-Induced Overloads Mechanism for False Data Injection Attacks Considering Post-Attack Economic Dispatch* | 否 | 是 | 否 | 部分 | 支持策略性 FDI/电力系统攻击背景。 |
| TIFS-[149] | *CCPA via Load Redistribution: Sequential Strategies and Vulnerability Analysis in Power Systems* | 否 | 部分 | 否 | 部分 | 支持多步策略攻击背景。 |
| TIFS-[252] | *State Partition-Particle Filter Detection for Cyber-Physical Attacks* | 否 | 部分 | 否 | 部分 | 检测方向背景，不应作为主线。 |
| TIFS-[268] | *ENClose: Encrypted Nonlinear Closed-Loop Control over FHE* | 否 | 否 | 部分 | 是/可能 | 闭环控制+安全计算邻域，非 FDI/learning。 |
| TIFS-[277] | *DP Event-Triggered Average Consensus under f-Local Byzantine Attacks* | 否 | 部分 | 部分 | 是/可能 | Byzantine 弹性控制邻域，非在线学习证书。 |
| top4-[118] | *TAT: Attesting Trajectory Integrity of Industrial Robotic Arms* | 否 | 部分 | 部分 | 可能 | 工业机器人可信轨迹，但不是学习控制器 safety certificate。 |
| top4-[122] | *SoK: Security of Cyber-physical Systems Under Intentional Electromagnetic Interference Attacks* | 否 | 是/部分 | 否 | 否 | 支持传感器/物理欺骗威胁面。 |
| top4-[297] | *Banshee: Target Switch Attacks on Gimbal-Stabilized Visual Tracking Systems via Acoustic Injection* | 否 | 是 | 否 | 否/不清 | 支持传感器欺骗 threat model。 |
| top4-[348] | *Physics-Aware Testing of Black-Box ICS* | 否 | 部分 | 否 | 否/不清 | 支持 ICS 物理语义测试。 |
| top4-[629] | *ConTest: CPS Input Space in Fuzz Testing with Control Theory* | 否 | 部分 | 否 | 不清 | 控制理论辅助 CPS fuzzing，不是认证三难。 |
| top4-[693] | *Security-Aware Sensor Fusion with MATE* | 否/不清 | 是/部分 | 否 | 不清 | 支持恶意传感融合背景。 |
| top4-[727] | *Towards Real-Time Defense Against Object-Based LiDAR Attacks in Autonomous Driving* | 否 | 是 | 否 | 不清 | 支持自动驾驶传感欺骗防御。 |
| top4-[910] | *PhyFuzz: Detecting Sensor Vulnerabilities with Physical Signal Fuzzing* | 否 | 是/部分 | 否 | 否/不清 | 支持物理信号传感器攻击面。 |
| top4-[950] | *SoK: Understanding the Fundamentals and Implications of Sensor Out-of-band Vulnerabilities* | 否 | 是 | 否 | 否 | 支持传感器 OOB 欺骗背景。 |

## 4. Gap 总结

| 邻域 | 已有强工作 | 已解决 | 未解决 |
|---|---|---|---|
| 固定 RL/NN 控制器验证 | Tran et al. 2019 | 闭环可达性/安全验证 | 在线更新、策略性 FDI、证书生命周期 |
| Robust safety filter | ISAACS, Gameplay Filters | 有界扰动/模型误差下 runtime safety | 过程感知欺骗、学习数据污染、security semantics |
| Adversarial RL robustness | Wu et al.; Lütjens et al. | 范数观测扰动下策略/动作鲁棒性 | CPS FDI 的多步过程一致性和真实状态安全 |
| Certified continual learning | Pham & Sun 2024 | NN 回归性质随持续学习保持 | 物理闭环证书、控制器更新、恶意传感数据 |
| Adaptive controller certification | NASA 2008 | 工程认证缺口被指出 | 恶意攻击、现代学习控制器、形式化三难 |
| Safe-RL/CPS attacks | Backdoor attacks on safe RL-enabled CPS 等 | safe RL 可被攻击 | 如何维持/撤销/重建闭环安全证书 |
| FDI/MARL 攻击检测 | 智能电网/交通网络 FDI 检测与攻击搜索 | 策略性注入/检测器训练 | 学习控制器自身的 certified safety-security-learning 边界 |
| CPS/ICS physical attack 系统论文 | top4/TDSC/TIFS 多篇 | 真实传感器/机器人/PLC 攻击面 | 认证学习控制器的基础理论 |

## 5. 当前 novelty 判定

本地与外部核验均支持当前判定：

**OPEN（部分触及，但精确组合近真空）**。

更准确地说，单点组件都不新：RL 控制器验证不新，adversarial safety filter 不新，FDI 攻击/检测不新，continual learning 证书不新，自适应控制认证缺口也不新。仍然开放的是这些组件的交叉处：**当控制器在部署后学习，攻击者又能用过程一致的 FDI 污染观测/更新数据时，闭环 safety certificate 如何保持、何时必须撤销、何时根本不可能保持**。

## 6. 下一步复核清单

1. 复读 TIFS-[118]、TDSC-[86]、top4-[110]、top4-[59] 原文或摘要，确认是否有“证书/不变集/屏障/可达性”层面的保证。
2. 复读 ISAACS/Gameplay Filters 正文，精确摘出其 adversary 是 disturbance/model error 而非 FDI 的证据句。
3. 复读 *Certifying Safety in RL under Adversarial Perturbation Attacks*，确认其 perturbation model 与工业 FDI 的区别。
4. 检索关键词组合：`certificate carrying controller update`, `learning-based MPC false data injection safety certificate`, `adaptive control barrier certificate sensor attack`, `online RL controller FDI safety verification`。
5. stage-3 已选择命题 B 为主线：可信状态缺失下的不可能性边界；命题 C 作为逃逸条件/正例边界。下一步写正式 toy theorem，并复核 TIFS-[118]/TDSC-[86] 原文。
