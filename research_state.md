> ⚠️ **过时文档（2026-08-19 标注）。** 本文件的状态判断、待办与结论均**早于**
> 2026-08-19 的三个新实验与证据审计，其中若干结论已被推翻或收窄。
> **唯一权威的当前状态与方向请读 [`usenix_direction_audit_0819.md`](usenix_direction_audit_0819.md)。**
> 本文件保留仅为历史记录，不要据此决定下一步动作。

# 方向⑤ 研究状态（round-6 核验，stage-1 精确化初稿已建立）

> 来源：`_overview/brainstorm_round6_foundational_gaps.md` 问题5 + 核验 agent（2024–2026，含控制/CPS 文献）。状态＝**🟢OPEN（对精确组合近真空），stage-1 精确化初稿已建立**。

## 问题（What，stage-1 精确化头条）
对**在线更新的学习型工业控制器**（RL/神经 MPC/LLM-in-loop），在**过程感知的策略性 security 对手**（FDI/欺骗，*非*有界扰动）下，"**可认证安全包络 ∧ security**"是否可能？**safety（固定保守）—security（自适应）—learning（更新）** 是否存在被证明的根本张力？可证伪：要么给"更新中控制器在策略性对手下维持安全证书"的框架，要么证明三元组不可能同时满足。

## 为什么重要（Why）
工业/航空/能源在把学习型控制器推进闭环，而传统认证（DO-178C 式）**假设控制器固定、可分析、规约不变**。一旦控制器更新、又面对会在物理约束内做手脚的对手，认证是否**还适用**成了悬空地基——关系到关键基础设施能否安全地用 AI 控制。

## 为什么难且至今未解（Why hard & open）
难在三者两两冲突，且要把"对手"从有界扰动升级成**过程感知策略性注入**。每个配料都有、但**那个三元组合空缺**：
- 学习型控制器可达性/安全验证只对**固定控制器 + 标称/有界扰动**成熟：`Safety Verification of CPS with RL Control`（Tran et al., EMSOFT/TECS'19，star-set，AINNCS 谱系）。
- 对抗式安全包络只针对**有界扰动对手**：`ISAACS`（L4DC'23, 2212.03228）/`Gameplay Filters`（CoRL'24, 2405.00846，对手=disturbance 非 FDI，控制器固定）；`Certifying Safety in RL under Adversarial Perturbation`（2212.14115）；Everett（2004.06496）。
- "更新作废证书"只在 **NN 回归**层处理：`Certified Continual Learning for NN Regression`（2407.06697）；航空 `Closing the Certification Gaps in Adaptive Flight Control`（NASA'08）只点名工程缺口、无对手。
- `Position: Certified Robustness Does Not (Yet) Imply Model Security`（ICML'25, 2506.13024）是张力概念骨架，但 position、非 CPS 控制定理。`Vulnerability Analysis for Safe RL in CPS`（TCPS'24）/`Backdoor Attacks on Safe RL-Enabled CPS`（TCAD'24）只证 safe-RL 可被攻击，不形式化、不解决。

## 开放核（为何没答）
(更新中控制器) ×(过程感知策略性对手) ×(闭环安全证书) 组合**未解**；safety↔security↔learning **三难从未被形式化为根本张力**；既无肯定框架也无不可能性证明。

## 诚实剔除（不要做的相邻坑）
同域"**ICS 的 ML 异常检测是不是结构性必输**"——**别做**。"过程一致隐蔽攻击不可检测"自 `Pasqualetti et al.`（IEEE TAC'13，zero-dynamics）/`Urbina et al.`（CCS'16）**已是定论**；"高保真必输"普适版**很可能为假**（`Attack Detection using Time Series Foundation Models` 2606.06347 能抓模型隐蔽攻击）。只剩"对学习型检测器、保真度↔可容许有害动作单调扩张"窄定理且有争议。本方向头条应是**三难/认证**（Q2），不是异常检测必输（Q1）。

## 判定与下一步
🟢OPEN（部分触及 → 精确组合近真空，但边界已收紧）。**当前投稿主线为
NDSS 2027 research track（presentation-hardening 阶段）；权威当前状态见
`ndss_submission_status.md`。** 稿件为匿名 conference 稿
`paper_latex/bare_conf_NDSS2027.tex`（IEEEtran conference 模式），标题
“Protected While Learning, Unsafe When Released: Reward Poisoning Across
Runtime-Assurance Contracts”。当前 claim 已从早期普适三难/不可能性叙事
收窄为：在 reward-only update-log poisoning 的 split-trust 部署下（攻击者
只能改 bounded reward records，runtime state/action、代码、参数与
certification 仍 trusted），有限时域 runtime assurance 对“resident
predictive authority”与“permanent raw release”给出不同安全合约——冻结
target/attacker/detector 后 V4 五个 untouched cartpole seeds 得
poisoned raw release `27/120`、paired clean `2/120`、resident `0/120`
（27 个 failures 均 timely switch，5/5 seeds 复现，`H=3/5/10` 均分离），
独立旧快照 one-step resident kernel `14/71` 为阴性对照。**历史决策（已被
取代）**：项目曾于 2026-07-30 临时从 NDSS 下调到 TDSC 主线并产出 15 页
IEEE Computer Society journal 稿、通过 P0--P6 internal gates；该 pivot
随后被独立的 resident-versus-release hard gate 撤销，重新回到 NDSS。
作者信息、AI/利益冲突声明与 portal submission package 仍未完成。
cartpole 已完成 3-seed reward-only REINFORCE hard
gate；2D quadrotor 也已完成锁定配置的 3-learner-seed、disjoint held-out
replication：clean `0/72`、poisoned action-only `68/72`，3/3 seeds 均产生
delayed failures，freeze/commit `0/72`，paired two-sided exact
`p=6.776e-21`。统一 24-block audit 中 poisoned raw `23/24`，commit、
freeze、permanent shield 和 official linear MPSC 均为 `0/24`；shield/MPSC
分别干预 `511/2400` 与 `2400/2400` steps，安全 escape condition 的
coverage、availability 与 performance cost 已可比较。

learner-family generality 的 bounded audit 已结束。official pretrained PPO clean 为 `0/72`，normalized malicious target 为 `72/72` delayed failures；固定 `L_inf <= 0.5` 的 locked B-lite 在 16 batches 出现 clean `0/24`、poison `1/24` 的轻微边界信号，但到 24 batches clean/poison 又均为 `0/24`。执行前锁定的 physical/margin 条件未通过，因此停止 formal PPO multi-seed sweep，不提高预算或改变 attacker capability；目前不能主张 deep-PPO unsafe-policy attack 成功。

NDSS 必过的 **benign adaptation utility vs always-freeze** 已按结果前锁定协议执行并失败。actuator-bias calibration 选择 `b=0.003 N`；开发 smoke 中 freeze/clean/gate reward 分别为 `-0.03617/-0.04714/-0.08097`，三者部署均为 `0/12` violation。gate 在 11/12 batches 接受更新、平均接受比例 `0.8208`，却在 0/12 paired rollouts 优于 freeze，且 12 次证书耗时 `100.93 s`。因此失败不是单纯 forced freeze，而是当前短批次 REINFORCE 的安全更新没有正 utility signal。按执行前锁定规则未运行 formal multi-seed utility 实验；结合 PPO B-lite 阴性结果，当前证据不足以支撑早期 NDSS 所需的 learner generality 与 learning-necessity 主张；这在当时触发了向 TDSC 的临时 pivot，但项目随后依靠独立的 resident-versus-release hard gate 把主张收窄，并重构为当前的 NDSS 2027 security claim（benign-utility 与 PPO 失败均保留为 NDSS 的阴性边界）。

（历史 TDSC 阶段）曾完成第一道 coverage hard gate，并把 residual learner 证据、official MPSC 成本、PPO 与 benign-utility 阴性边界放入当时的 IEEE Computer Society journal 稿；该 journal 稿已被当前 NDSS 2027 conference 稿取代，但下述 coverage/成本证据仍在 NDSS paired audits 中沿用。独立的 CasADi--PyBullet audit 在 144 个未做 certificate admission 的状态上评估 12 个锁定 snapshots：primary `H=100, guard=0.003` 在 1728 pairs 中认证 1293 个、0 false acceptance，clean/commit/freeze coverage 为 `0.986/0.944/1.000`，5 个 safe pairs 被 conservatively rejected。unguarded poisoned snapshot 在 H=20/50/100 分别出现 1/2/1 个 false acceptance，明确了 guard/model-mismatch 边界；该结果只支持 sampled finite-horizon claim。

**stage-1 精确化初稿已建立**：见 `stage1_problem_formalization.md` 与 `gap_matrix.md`。**stage-3 主线已收敛**：见 `stage3_feasibility_plan.md`，优先攻击命题 B（可信状态缺失下的不可能性边界），命题 C 作为逃逸条件/正例边界。**toy theorem、最小数值例子、证书推广和 certificate-gated learner demo 已建立**：见 `stage3_toy_theorem.md`、`stage3_minimal_example.md`、`stage3_certificate_extension.md`、`stage3_certificate_gated_learner.md`、`certificate_gate_demo.py`。**trusted-anchor / learning-aware FDI variants 与新颖性风险更新已建立**：见 `stage3_novelty_risk_update.md`。最新复核显示 `Safety of Linear Systems under Severe Sensor Attacks` 已覆盖 fixed-controller severe sensor attack safety filter，是最强邻居；本方向新意收紧到 online-updated learning controller 的 certificate lifecycle gate / learning-freeze frontier，而不是 plausible-state CBF 本身。**NDSS 2027 conference LaTeX 稿已落地并可编译**：见 `paper_latex/bare_conf_NDSS2027.tex`（IEEEtran conference 模式、匿名 research-track 稿，标题 “Protected While Learning, Unsafe When Released”，14 页含参考文献、正文 ≤13 页）。曾用的 15 页 IEEE Computer Society journal 稿保留为历史产物。

> 待办材料：`raw_materials/top4/`（S&P/USENIX/CCS/NDSS 的 CPS/控制）、`raw_materials/TDSC|TIFS/`（CPS/ICS）；CPS 背景见 `../../06_ai_industrial/brainstorm_round5_ai_industrial.md`。
