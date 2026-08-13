# 小方向：学习型工业控制器 safety↔security↔learning 三难

**用途**：对**在线更新的学习型工业控制器**（RL/神经 MPC/LLM-in-loop），在**过程感知的策略性 security 对手**（FDI/传感器欺骗，*非*有界扰动）下，"**可认证安全**（闭环物理安全包络）∧ **security**"是否可能？安全（保守/固定/可分析）—安保（自适应/不可预测）—学习（持续更新）三者是否有**被证明的根本张力**？

**状态**：已进入 **NDSS 2027 research-track presentation-hardening 阶段**。当前主线不是早期的普适“三难/不可能性”叙事，而是一个更窄且有实证支撑的 security claim：reward-only update-log poisoning 下，有限时域 runtime assurance 对“控制权常驻于受保护组合策略”与“永久释放 raw learner”给出不同的安全合约。冻结 target/attacker/detector 后的 V4 五个 untouched seeds 得到 poisoned raw release `27/120`、paired clean `2/120`、resident predictive authority `0/120`，27 个 poisoned failures 均有 timely switch，且 5/5 seeds 复现；锁定 horizon sweep 在 `H=3/5/10` 均分离合同。独立旧快照审计保留 one-step resident kernel `14/71` failure 的阴性结果。理论已通过 conic homogenization 扩展到 normalization singularity 与 global gradient-norm clipping：V3 从旧条件 `0/36` eligible 提升到 `22/36` verified batches，但 coordinatewise parameter clipping 仍排除。扩展 solver 在 burned seed 上产生 `9/12` nonzero edits 仍为 `0/24` release failure，因此仍只作为 batch audit。有效攻击可被简单 log checks 检出，PPO 与 benign-adaptation utility 也继续作为阴性边界。

**本目录内容**：
- `research_state.md` — round-6 核验判定（What/Why/最接近工作/为何没答/开放核 + **诚实剔除**"异常检测结构性必输"那条）。
- `stage1_problem_formalization.md` — stage-1 精确化初稿：系统模型、攻击者族、证书定义、三难定义、候选命题、hero example 与 kill criteria。
- `gap_matrix.md` — 近邻文献四轴 gap matrix：在线更新控制器、策略性 FDI/欺骗、闭环安全证书、形式化结论。
- `stage3_feasibility_plan.md` — stage-3 入口计划：选择“可信状态缺失下的不可能性边界”为主线，给出 toy theorem、hero experiment、贡献雏形与 kill criteria。
- `stage3_toy_theorem.md` — stage-3 theorem 草稿：一维系统中 FDI 不可区分性导致 sound certificate 必须撤销或冻结 learning 的证明。
- `stage3_minimal_example.md` — stage-3 最小数值例子：给出具体参数、安全动作区间、learning gate 阈值和 hero experiment 曲线雏形。
- `stage3_certificate_extension.md` — stage-3 证书推广：把单步 theorem 推广到 invariant set、barrier certificate、reachability 和 runtime shield 的必要条件。
- `stage3_certificate_gated_learner.md`、`certificate_gate_demo.py` — certificate-gated learner 伪代码与 1D 可运行 demo。
- `stage3_novelty_risk_update.md` — stage-3 新颖性风险更新：记录自适应预测控制、deception attacks、FT-CBF/secure estimation 等强邻居与避让表述。
- `stage3_revised_positioning.md` — stage-3 修订定位：承认 severe sensor attack CBF/QP safety filter 为 baseline，把新意收紧到 online update 的 certificate lifecycle gate。
- `submission_readiness_assessment.md` — 当前论文成熟度、投稿安全 venue 机会与下一步路线评估。
- `tdsc_evidence_map.md` — TDSC result-to-claim contract：允许/禁止主张、证据层级、P0--P5 期刊工作包与 submission gate。
- `stage4_topvenue_research_blueprint.md` — 面向安全顶会/顶刊的 research gap、attack+defense 方案、理论升级和实验矩阵。
- `lifecycle_gate_benchmark.py` — 初版 benchmark，比较 ungated、nominal action filter、robust action filter、always-freeze 与 lifecycle gate。
- `two_tank_lifecycle_benchmark.py` — 二维 two-tank-style CPS benchmark，复现 action filtering 与 update gating 的分离。
- `nonlinear_tank_lifecycle_benchmark.py` — 非线性 two-tank benchmark，用区间/网格 observer 估计 attacked-history plausible set，复现 update gating 与 action filtering 的分离。
- `parameter_update_gate_benchmark.py` — 参数级 update gate benchmark：对线性策略 `u=kz+b` 构造 certified halfspace set，并把 poisoned update 投影回参数可行域。
- `matrix_parameter_gate_benchmark.py` — 多维参数级 update gate：对 two-tank 线性策略 `u=k1*z1+k2*z2+b` 构造 future-history halfspace set。
- `adaptive_attack_benchmark.py` — 有限搜索 adaptive attacker：按 stale、unsafe、freeze 目标选择 poisoned update / ambiguity budget。
- `safe_control_gym_experiment_plan.md`、`safe_control_gym_lifecycle_scaffold.py`、`continuous_adaptive_attacker.py` — Safe-Control-Gym 主线：cartpole/2D quadrotor 标准 benchmark scaffold 与连续 adaptive attacker 目标/CEM 优化器。SWaT/WaDi/iTrust 记录为 deferred track。
- `safe_control_gym_controller_baselines.py`、`safe_control_gym_cbf_action_filter.py` — Safe-Control-Gym 官方控制器/安全过滤器 baseline adapter：LQR、linear-MPC 与 cartpole CBF action-only filter。
- `safe_control_gym_continuous_observation_attack.py` — Safe-Control-Gym cartpole 连续 observation-FDI attacker：CEM 每步优化观测扰动，对比 attacked LQR 与 oracle-state CBF action filter。
- `safe_control_gym_plausible_set_lifecycle_gate.py` — Safe-Control-Gym cartpole attacked-history plausible-set gate：只用 attacked observation 与攻击半径计算 robust action kernel，并对 LQR+linear residual 的 poisoned update 做 LifecycleGate projection。当前支持 Euler、CasADi discrete dynamics、official CBF sampled backend。
- `safe_control_gym_delayed_trigger_attack.py` — NDSS track 的 snapshot-commit delayed-trigger benchmark：在线适应阶段用 robust action kernel 保护当前动作，同时污染 update-data；随后用多步 CasADi commit gate 认证可部署快照，并在 clean deployment envelope 中测量延迟物理违规。commit 只在 trusted baseline 保持 recovery margin 的状态域内激活；该模型明确不覆盖永久在线且证书针对组合策略 $F\circ\pi$ 的 runtime filter。
- `safe_control_gym_delayed_trigger_sweep.py` — delayed-trigger 的 poison-dose 与 held-out-state 稳健性实验：三组未参与 margin 校准的随机种子上 admission 191/192；高剂量 action-only 为 191/191 delayed violations，commit gate 在所有剂量均为 0/191，并保留 10%--35% 参数位移（仅表示 update availability，不等同于有益学习）。输出 CSV 与 `paper_latex/figures/safe_control_gym_delayed_trigger_summary.pdf`。
- `safe_control_gym_reinforce_reward_poisoning.py`、`safe_control_gym_reinforce_reward_poisoning_sweep.py` — 真实 learner hard gate：线性高斯 residual actor 从真实 PyBullet transition/reward 计算标准 reward-to-go REINFORCE gradient；攻击者只能对 reward log 加 `L_inf <= 2.0` 的有界污染，不能写参数或梯度。3 learner seeds 的独立 held-out 审计中 clean 为 1/188、reward-poisoned action-only 为 38/188、commit gate 与 freeze 均为 0/188；37 个 paired rollouts 仅 poisoned 失败、0 个仅 clean 失败（exact `p=1.46e-11`）。输出 aggregate CSV 与 `paper_latex/figures/safe_control_gym_reinforce_reward_poisoning_summary.pdf`。
- `safe_control_gym_quadrotor_lifecycle_scaffold.py` — 第二标准 CPS 的 snapshot-commit scaffold。显式把官方 LQR 请求裁剪到 2D quadrotor 的物理推力域；状态依赖 harmful snapshot 在分散初始域的独立 PyBullet 部署中产生 12/12 delayed violations，而 trusted LQR、35% commit interpolation、always-freeze 与 5-step permanent backup shield 均为 0/12。一步 filter 仍为 4/4 failure，实证说明“一步安全”不能替代 backup recoverability。
- `safe_control_gym_quadrotor_reinforce_reward_poisoning.py` — 2D quadrotor 真实 learner smoke：2-output Gaussian residual actor 只从真实 PyBullet transition/reward 做 reward-to-go REINFORCE；batch-aware 白盒攻击仅修改 reward log，预算 `L_inf <= 0.5`。单 seed smoke 中 clean 为 0/8、poisoned action-only 为 8/8 delayed violations（median first=52），55% commit、freeze 与永久 5-step backup shield 均为 0/8；适应阶段所有机制为 0 violation。该结果是第二系统 provisional pass，不是多 seed 主结果。
- `safe_control_gym_quadrotor_reinforce_reward_poisoning_sweep.py` — 锁定 seed-2040 超参数后的第二系统主审计。learner seeds 2040--2042 在独立 certification/evaluation states 上得到 clean `0/72`、poisoned action-only `68/72`（3/3 seeds，全部 delayed，median first=58.5）、commit/freeze `0/72`；paired discordance 为 68 poison-only 对 0 clean-only（two-sided exact `p=6.78e-21`）。permanent backup shield 为 0/12、198 interventions、0 rejection。
- `safe_control_gym_quadrotor_mpsc_baseline.py` — official Safe-Control-Gym linear MPSC 的早期 12-rollout adapter 核验，加载 upstream pretrained RPI artifact；其 0/12 安全结果证明接口可用，但旧 reward/latency 数字不再用于跨机制比较。论文中的 MPSC 成本结论统一来自下述 P2 相同 24-block paired-state frontier。
- `safe_control_gym_quadrotor_security_availability_frontier.py`、`tdsc_security_availability_frontier_protocol.md` — TDSC P2 的统一 paired-state frontier。三个 learner seeds 各自从新的 144-state pool 中按 commit/freeze 共同证书选择 8 个状态，六种机制使用完全相同的 24 个 state/learner blocks：poisoned raw `23/24` 失败，clean/commit/freeze/permanent shield/official MPSC 均 `0/24`。commit 共同覆盖率为 `90.3--100%`、离线 latency `8.49--9.32 s/seed`；shield 干预 `511/2400`、median latency `221.9 ms`，MPSC 干预 `2400/2400`、median latency `59.7 ms`。`generate_tdsc_frontier_artifacts.py` 从 raw rollout/step CSV 重算一致性并生成论文表图与 paired reward delta。
- `safe_control_gym_quadrotor_trusted_anchor_audit.py`、`tdsc_trusted_anchor_protocol.md` — TDSC P3 的 trusted-state-anchor sensitivity。anchor periods `1/3/6/12` 对应 12 次更新中的 `12/4/2/1` 次 trusted calls，并锁定 high/standard 两档 z/theta 误差和 freshness growth。八种 anchor-conditioned commits 均为 `0/24` 物理失败、16/16 certificate centers；只有 `P=12` 将 fractions 从 `0.55/0.40/0.70` 降到 `0.50/0.40/0.65`，两档质量在 0.05 resolution 下不可区分。`generate_tdsc_anchor_artifacts.py` 重算 raw artifacts 并生成论文表与 paired-freeze reward boundary。
- `safe_control_gym_quadrotor_ppo_baseline.py`、`safe_control_gym_quadrotor_ppo_reward_poisoning.py`、`ppo_b_lite_protocol.md` — official pretrained PPO 与 locked reward-only B-lite。pretrained PPO 为 0/72，normalized malicious target 为 72/72 delayed failures。固定 `L_inf <= 0.5` 的 B-lite 在 16 batches 得到 clean 0/24、poison 1/24 的边界级信号，但 24 batches 又回到 clean/poison 0/24；执行前锁定的 physical/margin 条件均未通过，因此停止 formal PPO multi-seed sweep。该结果只能写成 update redirection/robustness boundary，不可表述为 deep-PPO attack success。
- `safe_control_gym_quadrotor_benign_utility.py`、`benign_utility_protocol.md` — 已执行的 NDSS benign-utility hard gate。锁定 calibration 选择 `0.003 N` differential actuator bias；开发 smoke 中 freeze/clean/gate reward 为 `-0.03617/-0.04714/-0.08097`，均为 0/12 deployment violations。gate 在 11/12 batches 接受更新（mean fraction `0.8208`）但 0/12 paired rollouts 优于 freeze，故触发 stop，未启动 formal。该结果否定“gate 已证明有益学习”这一表述；项目随后依靠独立的 resident-versus-release hard gate 重构为更窄的 NDSS security claim。
- `generate_tdsc_result_table.py` — 从锁定 cartpole/quadrotor aggregate CSV 自动生成 8-row end-to-end 主表，并从 coverage aggregate 生成独立 coverage 表；每行在 `results/tdsc_core_results.csv` 和 `results/tdsc_coverage_results.csv` 中携带 source-file provenance。永久 shield/MPSC 只在统一 P2 表中比较，不再混入旧 12-rollout subset。
- `generate_tdsc_reproducibility_manifest.py`、`ndss_reproducibility_manifest.md` — 当前 NDSS 投稿 artifact 锁：记录完整重跑命令、环境/依赖版本、上游 Safe-Control-Gym commit、所有种子命名空间，并为 source/raw/generated/model/figure/PDF 文件生成 `results/tdsc_artifact_checksums.csv` 的 SHA-256 inventory；`tdsc_reproducibility_manifest.md` 仅保留兼容指针。`test_tdsc_submission_artifacts.py` 自动审计表格 source link、旧口径混排、禁用主张、NDSS 格式锁和 checksum 一致性。
- `tdsc_certificate_coverage_protocol.md`、`safe_control_gym_quadrotor_certificate_coverage.py` — TDSC P1 的 CasADi--PyBullet model-mismatch audit。对 12 个锁定 snapshots 与 144 个未预筛独立状态共 1728 pairs，primary `H=100, guard=0.003` 认证 1293 pairs、0 false acceptance；clean/commit/freeze coverage 为 `0.986/0.944/1.000`，有 5 个 false rejection。unguarded grid 在 poisoned snapshots 上出现 1/2/1 个 false acceptance（H=20/50/100），因此正 guard 是实证必要边界但仍不构成 continuous invariant proof。
- `paper_latex/bare_conf_NDSS2027.tex` — 使用 NDSS 官方 conference 模式的匿名 research-track 工作稿；主线已重构为 adversarial reward-update log 下的 resident authority 与 permanent raw release 合约分离，并保留 PPO/utility 阴性边界。
- `cartpole_prospective_gate_aware_attack_protocol.md`、`safe_control_gym_cartpole_prospective_gate_aware_attack.py` — fresh-seed prospective attack hard gate，已按锁定 stop rule 失败：seed `2060` 上 SOCP optimizer 为 `0/12` nonzero witnesses、raw release `0/24` failure；首批目标投影不可正向推动，后 11 批 reward box 跨越 normalization singularity。`2061/2062` 未执行。burned-seed V2 诊断仅得到 1 个非零 batch，仍为 `0/24` failure，因此不能把 exact support theorem 宣称为通用 attack optimizer。
- `clipped_reward_influence_theory_wp.md`、`reward_certificate_geometry.py`、`safe_control_gym_cartpole_clipped_influence_audit.py` — 基于 fractional homogenization 与 second-order feasibility cone 的理论扩展。unit smoke 覆盖旧 solver 一致性、零点退化和 cap-active 解析例；锁定 V3 trajectory 上 `22/36` batches 获得 verified clipped support，18 个跨 normalization singularity、20 个跨旧 gradient-bound exclusion，最大 witness 误差 `3.67e-5`，所有实际更新均受 support 上界约束。
- `theory_optimization_literature_route.md` — 从 Operations Research、SIAM Journal on Optimization、Mathematical Programming 等理论 venue 映射当前 conic derivation，并记录 coordinatewise clipping 的 mixed-integer/disjunctive 后续路线与当前 no-go 理由。
- `threat_model_realism_review.md` — 锁定 split-trust learning/runtime planes、reward-ingestion 最小攻击面、日志 provenance/recomputation/detection/containment 的区别，以及 reviewer objection 对应答法；不改变任何实验结果。
- `homogenized_gate_aware_poststop_protocol.md`、`safe_control_gym_cartpole_homogenized_gate_aware_diagnostic.py` — 只使用 burned `2060/9060` 的 post-stop constructor 诊断。新 solver 产生 `9/12` nonzero edits，但 poisoned snapshot 虽 `24/24` 通过五步检查，仍为 `0/24` raw-release failure；未打开 `2061/2062`。
- `cartpole_v3_fixed_target_tanh_protocol.md`、`safe_control_gym_cartpole_v3_fixed_target_tanh.py` — 独立锁定的 prospective V3 hard gate。development `2070/9070` 先以 poisoned/clean/resident=`11/0/0` 通过，随后无调参执行 `2071/2072`。三 seed 共 `72/72` 五步接受，poisoned permanent raw release=`23/72`、clean=`2/72`、resident predictive authority=`0/72`，23 个 failure 全部 timely switch；21 poison-only 对 0 clean-only，exact `p=9.5367e-7`。这解决 fixed-target attack 的 retrospective evidence 风险，但不把 `tanh` shaping 宣称为 joint gate optimizer。
- `safe_control_gym_paper_sweep.py` — Safe-Control-Gym 论文主实验批处理：多 seed / 多 ambiguity radius 聚合 CasADi robust kernel、official CBF sampled reference 与 freeze-frontier，并生成独立论文图。
- `generate_benchmark_artifacts.py`、`results/`、`paper_latex/figures/` — 将 1D、linearized tank、nonlinear tank、parameter-level 与 adaptive benchmark 输出为 CSV，并生成论文用 summary figures。

**相关/交叉方向**：
- `../../06_ai_industrial/llm_in_ot_loop/`、`../../06_ai_industrial/industrial_edge_sidechannel/`（共享 CPS/OT 威胁模型与语料）。
- 与方向①支柱 D 呼应（学习型控制器的认证也是"算子下保持"的特例，但此处对手=策略性 FDI、属性=闭环物理安全包络）。
- 总览：`../../../_overview/brainstorm_round6_foundational_gaps.md`（问题5 原始核验）、`../../06_ai_industrial/brainstorm_round5_ai_industrial.md`（CPS 背景）。

## 共享语料 raw_materials（所有子项目通用，重要）
本子项目**不复制论文数据**。原始论文与统计信息统一放在**项目根目录的 `raw_materials/`**：
- `raw_materials/TDSC/`、`raw_materials/TIFS/`、`raw_materials/top4/`：各 venue 的 `paper_table_*.md`、`research_report_*.md`、原始导出 CSV（CPS/ICS/控制 多在 TDSC/TIFS/top4）。
- `raw_materials/AI_conferences/`：safe-RL/neural-controller 认证理论亦见 NeurIPS/ICML/ICLR。
- 引用编号：`TDSC-[n]`/`TIFS-[n]`/`top4-[n]` → 对应 `raw_materials/.../paper_table_*.md`。

在本目录启动 agent 任务时：默认只读本目录内容；**需要查论文/统计时再去访问 `raw_materials/`**，不要读其它方向目录。

## 项目级规则
见根目录 `brainstorm_rules.md`。跨方向总览见根目录 `_overview/`。
