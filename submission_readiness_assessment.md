> ⚠️ **过时文档（2026-08-19 标注）。** 本文件的状态判断、待办与结论均**早于**
> 2026-08-19 的三个新实验与证据审计，其中若干结论已被推翻或收窄。
> **唯一权威的当前状态与方向请读 [`usenix_direction_audit_0819.md`](usenix_direction_audit_0819.md)。**
> 本文件保留仅为历史记录，不要据此决定下一步动作。

# Submission Readiness Assessment：certificate lifecycle gate

> 状态：项目投稿评估 v8（2026-08，当前）。下方 v7/v6/v5/v4/v3/v2/v1
> 内容保留为历史基线；本页顶部的 v8 决策（回到 NDSS 2027）覆盖其中已
> 过时的 venue 与 hard-gate 状态，特别是 v7 的“保留 TDSC、不返回 NDSS”。
> **权威、机器可核对的当前状态见 `ndss_submission_status.md`。**

## v8 决策：回到 NDSS 2027 research track（当前）

v7 的 TDSC pivot 已被撤销。项目基于独立的 resident-versus-release hard
gate 把主张收窄，重新以 **NDSS 2027 research track** 为投稿主线；稿件为
匿名 conference 稿 `paper_latex/bare_conf_NDSS2027.tex`（IEEEtran
conference 模式），标题 “Protected While Learning, Unsafe When Released:
Reward Poisoning Across Runtime-Assurance Contracts”。

**当前 security claim**：在 reward-only update-log poisoning 的 split-trust
部署下（attacker 只能改 bounded reward records，runtime state/action、
代码、参数与 certification 仍 trusted），有限时域 runtime assurance 对
resident predictive authority 与 permanent raw release 给出不同安全合约。
冻结 target/attacker/detector 后的 V4 五个 untouched cartpole seeds 得到
120 个初始接受 pair：poisoned raw release `27/120`、paired clean `2/120`、
resident predictive authority `0/120`（27 个 failures 均 timely switch，
5/5 seeds 复现），horizon sweep 在 `H=3/5/10` 均分离合同；独立 one-step
resident kernel 为 `14/71`。第二系统 2D quadrotor reward-log 攻击为
`68/72` vs clean `0/72`（3/3 seeds，two-sided exact `p=6.776e-21`）。
理论侧给出 normalized reward-influence set，conic homogenization 在
global gradient-norm clipping 下给出 exact positive support，
coordinatewise parameter clipping 被排除。**阴性边界（保留）**：有效攻击
可被 task-aware reward checks 检出（trusted recomputation TPR/FPR `1/0`）、
不稳定迁移到 official PPO、且未证明 benign utility 优于 freeze。

**当前决策：以 NDSS 2027 为投稿主线。** 科学 claim 与实验已按上述收窄
口径冻结并 checksum 锁定（233 文件、73 audit tests 全通过）。仍未完成的
是作者信息、AI/利益冲突声明、NDSS portal checklist 与最终 submission
package（投稿操作 gate，非新科学实验 gate）。NDSS 2027 Fall cycle 截稿
2026-08-19。

## v7 决策（已被 v8 取代）：TDSC internal scientific red-team PASS

TDSC P0--P6 已完成。内部科学红队补齐 Simplex、linear/adaptive MPSC、
shield removal、online barrier learning 与 reward/policy poisoning 等最近
邻居；论文明确放弃“rollback/shield/reward poisoning 本身新”的表述。
quadrotor paired exact 检验由误标的一侧值修正为 two-sided
`p=6.776e-21`，并将 exact/Wilson/bootstrap 结果限定为给定三个 locked
learner snapshots 后的 block-level summary，而不是把 72 rollouts 当作
72 个 learner replicates。

同时，正文已标记 failure 后短 episode reward 不作 utility 比较，将
正式预注册口径修正为“pre-specified and locked before execution”，并
修复 action kernel 与 parameter set 的类型表述。摘要压缩至 188 words、
不含数学表达式；15 页 PDF 无 overfull、undefined reference/citation。
完整结论见 `tdsc_internal_scientific_review.md`。

**v7 当时决策（已被 v8 取代）：保留 TDSC，不返回 NDSS；冻结科学 claim
和实验，进入 coauthor/external novelty review。** 该决策随后被独立的
resident-versus-release hard gate 推翻，项目已回到 NDSS 2027（见页首
v8 与 `ndss_submission_status.md`）。当时“仍未完成作者信息、AI/利益冲突
声明、portal checklist 与最终 submission package”的投稿操作 gate 依然
适用于当前 NDSS 稿。

## v6 决策：NDSS utility hard gate 失败，转 TDSC 主线

结果前锁定的 actuator-bias utility 协议已执行。一次 measurement audit
发现 Safe-Control-Gym 的 aggregate flag 把 bias 后、physical clip 前的
actuator saturation 计作 input violation；修正为按 realized state box 计
安全结果、单独报告 saturation 后，保持原 grid/seed/state/threshold
重跑。calibration 选择最小合格值 `b=0.003 N`（0/12 state violations，
paired reward loss `0.01520`）。

唯一允许的 development smoke 结果为：

- always-freeze：reward `-0.03617`，0/12 violations；
- clean adaptation：reward `-0.04714`，相对 freeze `-0.01097`；
- LifecycleGate：reward `-0.08097`，相对 freeze `-0.04480`，0/12
  paired rollouts 优于 freeze。

LifecycleGate 在 adaptation/deployment 均为 0 violation、0 filter
rejection，11/12 batches 接受非零更新，mean accepted fraction 为
`0.8208`；12 次 certificate 共耗时 `100.93 s`。所以 utility failure
不能解释成 gate 只会冻结：当前 learner 的 safe accepted updates 本身
降低了 task utility。按协议停止，未运行 formal 三种子实验，也不
post-hoc 修改 learner、shift 或阈值。

这使两项 NDSS 增强路径均告失败：official PPO B-lite 没有稳定物理
failure，benign utility 也没有证明 learning 相对 freeze 的必要性。
尽管 residual-REINFORCE lifecycle attack、多 seed 第二系统和 strong
MPSC cost 证据仍然成立，当前 contribution package 对 NDSS 更像
weak reject。按照既定 “NDSS gate 失败则 TDSC” 决策，后续应围绕
certificate lifecycle 的完整 characterization、soundness boundary、
attack/escape-condition cost 和负面边界组织期刊稿，而不再宣称
deep-PPO generality 或已证明 gated learning utility。

TDSC 启动后的第一轮重构已完成：journal 稿把允许/禁止主张锁到
`tdsc_evidence_map.md`，核心结果表从 aggregate CSV 自动生成。第一道
coverage hard gate 也已通过：12 个锁定 snapshots 与 144 个未预筛状态
构成 1728 pairs；预先声明的 `H=100, guard=0.003` 配置认证 1293
pairs，false acceptance 为 0，clean/commit/freeze coverage 为
`0.986/0.944/1.000`，false rejection 共 5 个。unguarded 配置在
poisoned snapshots 上仍有 false acceptance，因此稿件只能主张
guarded sampled finite-horizon evidence，不能升级为 invariant proof。

## v5 决策：停止 PPO 扩展，NDSS 转向 lifecycle utility 主线

用户确认后执行了一次结果前锁定的 B-lite。预算、malicious target、attacker capability 与 exact parameter-space objective 均保持不变；只检查 16/24-batch checkpoints，并在执行前锁定 physical/margin go 条件。

- 16 batches：clean `0/24`、poison `1/24`；唯一 poison-only rollout 在 step 19 以 normalized margin `0.000913` 轻微越界。
- 24 batches：clean/poison 均为 `0/24`，16-batch 信号没有持续。
- 16/24 的 median paired margin delta 分别为 `0.00257`/`0.06490`，poison-worse fraction 为 `0.542`/`0.750`，target-MSE ratio 为 `0.756`/`0.967`。两 checkpoint 不同时满足锁定 margin 条件。
- adaptation 始终 0 violation、0 MPSC infeasible。proposal/log-prob 最大差为 `1.43e-6`，属于 float32 量级但略高于代码预设 `1e-6` precondition。

因此 B-lite 判定为 **STOP**：不启动 official PPO formal multi-seed sweep，不提高 reward budget，不重选 target，也不追加 post-hoc attack objective。PPO 只能作为“reward-only poisoning redirects updates but fixed-budget physical failures are not stable”的 robustness boundary。

NDSS research track 仍保留，但核心 claim 必须限制在两个系统上已多 seed 复现的 residual REINFORCE lifecycle vulnerability，以及 permanently-online MPSC 的安全/可用性代价。下一项比继续搜索 PPO attack 更关键的 hard gate 是：

> 在预声明的 benign dynamics、payload 或 reference shift 下，证明 LifecycleGate 相比 always-freeze 保留了可测的 task adaptation benefit，同时保持 0 violation。

必须报告 paired task reward/cost、accepted-update fraction、physical violations 和 certification/runtime cost。parameter displacement 不等于 learning utility；若 LifecycleGate 不能优于 freeze，则当前 safety--security--learning trilemma 缺少“learning 有必要”这一实证支柱，A 路线对 NDSS 仍偏 weak reject。

## v4 历史决策：NDSS 主证据增强，但 PPO generality gate 未通过

## v4 决策：NDSS 主证据增强，但 PPO generality gate 未通过

当前结论是 **继续保留 NDSS research track，但在扩展 PPO 攻击或改变 threat model 前暂停**。quadrotor 的 residual REINFORCE 结果已经从单 seed smoke 升级为锁定配置、多 seed、disjoint held-out 的主证据；official MPSC 也给出了强安全基线。与此同时，固定 `L_inf <= 0.5` reward-only 预算下的 official PPO fine-tuning 没有产生物理安全违规，构成必须诚实报告的 generality hard gate。

### 已通过：锁定 multi-seed residual learner gate

1. 攻击目标与超参数只在 development seed 2040 上确定；learner seeds 2040--2042 使用互不重叠的 training、certificate 与 deployment states。
2. 在 72 个相同、paired、baseline-admitted held-out rollouts 上，clean 为 `0/72`，poisoned action-only 为 `68/72`，且 3/3 learner seeds 均出现 delayed physical failure（median first violation step `58.5`）。
3. freeze 与 lifecycle commit 均为 `0/72`；permanently-online 5-step backup shield 为 `0/12`，有 198 次 intervention、0 rejection。适应阶段四种机制均为 0 violation。
4. poison-only discordance 为 68、clean-only 为 0，paired two-sided exact binomial `p=6.776e-21`。因此该结果不再只是单 seed smoke。

### 已通过：official MPSC 强安全基线

直接调用 Safe-Control-Gym 注册的 `linear_mpsc` 与官方 2D quadrotor 预计算模型，对三份 poisoned residual snapshots 做部署审计：

- physical violations：`0/12`；solver infeasible steps：`0`；
- intervention：`1200/1200` steps；mean action correction `0.00661`；
- mean reward `-0.3574`，明显低于 clean residual snapshot 的 `-0.0296`。

这证明 permanently-online sound filter 是有效 escape condition，也说明其安全性伴随显著 availability/performance cost，不能被表述为低成本地消除了问题。

### 未通过：official PPO reward-only physical-failure gate

1. 官方 pretrained PPO 在 held-out envelope 上 clean 为 `0/72`，mean reward `0.9305`；同一 action domain 中的 normalized malicious target 为 `72/72` delayed failures（median first `30`），说明目标本身可达且危险。
2. PPO fine-tuning 使用官方 actor/critic、PPOBuffer、clipped PPO objective、optimizer 与 checkpoint；MPSC 保护每个 adaptation action，攻击者只修改写入 rollout buffer 的 scalar reward，逐步 `L_inf <= 0.5`。
3. 8-batch fixed-budget probe 中，poisoned actor 比 clean 更接近恶意目标（target-action MSE `0.9264` vs `1.3425`），deployment reward 更低（`0.7052` vs `0.7996`），说明 reward log 确实改变了深度 PPO 的更新方向；但 clean、poison 与 freeze 均为 `0/8` physical failures。

因此目前只能主张“reward-only poisoning can redirect PPO updates and degrade performance”，**不能主张已经使 PPO 产生 unsafe deployed policy**。此外，adaptation transitions 来自 MPSC-filtered actions、buffer 中保留 policy proposal actions，这是常见 shielded-learning 接口，但 raw-policy estimator 对实际 transition 带有 off-policy mismatch；论文需要明确写出这一点。

### 当前决策点

不应在结果不显著后未经新的执行前协议审查就提高 poison budget、改变攻击能力或反复搜索超参数。下一步有两条合理路线：

1. **推荐：冻结当前 threat model。** 把 PPO 结果作为 robustness boundary/negative result，继续 NDSS 主线：以 multi-seed residual learner 证明 lifecycle vulnerability，以 official MPSC 和 backup shield 证明 escape condition及其代价；下一步补 Safety Layer/运行开销/第二 CPS，而不声称 deep-PPO attack generality。
2. **扩展 PPO hard gate。** 保持 `L_inf <= 0.5`，预先锁定额外 batch 数、learner seeds、state-selection 与 gate-aware bilevel objective，再运行一次正式 sweep。只有这一路线失败后，才能把 PPO 稳健性作为结论；若要提高预算或改变 attacker capability，必须单独更新 threat model 和实验计划。

当前不触发 TDSC pivot：residual learner 的 multi-seed physical evidence 与 strong-baseline cost 已足以维持 NDSS research track。是否继续深挖 PPO 是下一项需要确认的研究资源分配，而不是可以自动越过的工程步骤。

## v3 历史决策：第二系统 provisional pass，继续 NDSS research track

## v3 决策：第二系统 provisional pass，继续 NDSS research track

2D quadrotor 已越过“第二系统完全不产生物理后果”的 kill criterion，但目前仍是 **单 learner seed / 8 deployment rollouts 的 smoke**，不能提升为投稿级主结果：

1. 在先行 lifecycle scaffold 中，显式把官方 LQR 输出裁剪到物理推力域后，state-dependent residual snapshot 在独立 PyBullet 上产生 12/12 delayed failures（median first=18）；clipped LQR、always-freeze、35% commit 与永久 5-step backup shield 均为 0/12。
2. 单步 robust action projection 仍为 4/4 failures，只把 median first 从 27 推迟到约 40--49；因此“一步安全”不被写作 sound permanent-filter escape condition。加入 trusted-LQR 5-step backup recoverability 后才达到 0/12、0 rejection。
3. 真实 learner 使用 2-output Gaussian residual actor、真实 PyBullet transition/reward 和 reward-to-go REINFORCE。白盒攻击者只能修改 reward log，逐步预算 `L_inf <= 0.5`；它不能写 action、gradient、parameter 或 optimizer state。
4. seed 2040 smoke 中 adaptation 为 0 violation；clean `0/8`，poisoned action-only `8/8` delayed failures（median first=52），55% commit、freeze、永久 5-step backup shield均为 `0/8`。永久 shield 有 149 次 intervention、0 rejection。

这使 NDSS attack+defense 叙事继续成立，但下一道 hard gate 变为：

1. quadrotor multi-seed、disjoint held-out initial-state audit 与 paired significance；
2. official MPSC/Safety Layer 或同等级强安全基线，而不只用自建 backup shield；
3. official PPO/DDPG 或 adaptive-MPC learner family，检验结果是否依赖低维 canonical REINFORCE；
4. 系统化报告 availability、reward/tracking cost、intervention、rejection 与运行开销。

若第二系统跨 seed 不稳定、poisoned-only discordance 消失，或强基线在低 availability cost 下完全消除 lifecycle gap，则 pivot TDSC。当前判断是 **继续 NDSS research track，但仍不投稿**。

## v2 历史决策：继续 NDSS research track，但尚未达到投稿就绪

当前 smoke gate 判定为 **conditional GO for NDSS research track**，不是“现在即可投稿”。新证据已经越过单纯 position/theory note：

1. snapshot-commit 威胁模型中，适应阶段的 robust action kernel 使四种机制均无物理违规，但 action-only 允许 update-data poisoning 累积成有害部署快照。
2. 白盒有限搜索自动选择攻击更新方向 `(2,-0.5)`；dose 10/12 时 action-only 在三组未见种子的 191/191 admitted PyBullet rollouts 中产生 delayed violation。
3. margin-aware multi-step commit LifecycleGate 在相同 191 个 rollouts 上所有剂量均为 0 violation，并保留 10%--35% parameter displacement；always-freeze 也是 0 violation，但 displacement 恒为 0。该 displacement 只表示 update availability，不等同于有益学习。
4. one-step local LifecycleGate 在固定 42-state stress envelope 中仍有 1/42 violation，而 multi-step commit gate 为 0/42，支持“递归/部署期证书不能被单步 gate 替代”的 ablation。
5. 永久在线且 sound certificate 覆盖组合策略 $F\circ\pi$ 的 runtime filter 是明确 escape condition；本文攻击只针对 adaptation-filter / raw-snapshot-commit 架构。

证书的精确边界也必须明示：commit 使用 sampled 120-step CasADi certificate；只在 trusted baseline recovery margin 至少为 `0.0075` 的状态上部署，正式 held-out 集 admission 为 191/192。它不是连续状态空间 invariant-set proof。

### NDSS 保留条件与 TDSC pivot

在正式写 NDSS full paper 前还必须完成两项 hard gates：

1. ✅ 已完成 provisional pass：线性高斯 residual REINFORCE 的更新来自真实 transition/reward；`L_inf <= 2.0` reward-log poisoning 在 3/3 learner seeds 触发 delayed failures。clean `1/188`、poisoned `38/188`、commit/freeze `0/188`，paired exact `p=1.46e-11`。它消除了“攻击直接写参数/梯度”的 artifact，但仍需用官方 PPO/DDPG 或 adaptive MPC 扩展 learner family。
2. 尚未完成：迁移到第二个标准 CPS（优先 2D quadrotor），并加入 permanently-online filter、Safety Layer/robust-learning 类强基线。

若真实 learner 上 delayed trigger 不稳定复现，或第二系统中 action-only 不产生物理后果，则按既定策略 pivot 到 TDSC：保留 certificate-lifecycle 理论、边界条件与更完整的系统分析，不再用 NDSS attack+defense 主张。

## 1. 论文状态（历史 v1 基线，已被页首 v8 取代）

当前项目已经从“sensor FDI 下安全控制是否可能”的宽问题，收敛到更准确的贡献边界：已有 severe sensor attack safety filters 处理 fixed-controller safety；本项目补充 online-updated controller 的 certificate lifecycle gate，即学习更新必须受 attacked-history certified kernel 约束。

当前草稿的形态是 4--5 页短论文/position-style theory note：定义完整、核心定理可编译、最小 demo 可复现，但实验与系统证据还不足以支撑 top-tier security full paper。

| 维度 | 当前状态 | 评价 |
|---|---|---|
| Novelty boundary | 已收紧到 certificate lifecycle / learning-freeze frontier | 方向正确，避免与 severe sensor attack CBF/QP 工作正面冲突 |
| Formal result | 有必要条件 theorem 和 1D counterexample/frontier | 正确但偏定义化，容易被 reviewer 认为“显然” |
| Artifact | 有 `certificate_gate_demo.py` 和 LaTeX 初稿 | 可复现但规模太小，不足以构成安全会议实证贡献 |
| Related work positioning | 已覆盖 severe sensor attack、FT-CBF、MFAPC under attacks | 还需补 secure estimation/control 经典线和更多 CPS security 语境 |
| Security framing | 有 FDI/deception 和 learning-aware update pollution | 还缺明确 threat model：attacker knowledge、capability、goal、defender assumptions |
| Evaluation | 只有 1D analytic/minimal study | 对 top-4 security venue 明显不足 |

## 2. 主要优势

1. **问题切口干净。** 经过强邻居复核后，项目没有继续把 plausible-state safety filtering 当作新意，而是把新意放在在线更新导致证书生命周期失效的边界上。这一点对 security reviewer 有价值，因为它把 certification 和 adversarial data semantics 连接起来。

2. **核心主张容易解释。** “安全过滤 action 不够，还要过滤改变 future action map 的 update”是一个清晰、可记忆的论点。当前 introduction 已经能在前三段建立 existing work、gap 和本文问题。

3. **最小例子有说服力。** `rho=1/lambda=0.833` 的 freeze frontier 直观展示了每个真实状态 individually controllable，但共同 certified action kernel 为空。这个例子适合作为 Figure 1 或 motivating example。

## 3. 关键短板

1. **定理当前太接近定义展开。** Theorem 1 证明“若证书 sound，则 updated action 必须在 certified kernel 内”，数学上成立，但 reviewer 可能认为这是 `K_Gamma(h)` 定义的直接后果。要冲 top venue，需要把定理扩展到更非平凡的对象：未来 reachable attacked histories、parameter-level update sets、多步 certificate persistence，或 attack-induced update poisoning 与 certificate invalidation 的不可兼容性。

2. **缺真实 CPS/learning controller 证据。** 当前 1D study 是边界展示，不是安全论文实验。Top-4 reviewer 会问：在水箱、微电网、无人机、车道保持、quadrotor 或工业过程控制中，这个 gate 是否真的阻止了 unsafe certified updates？代价是多少？相比 always-freeze、fixed safety filter、ungated learner、robust MPC/CBF baseline 如何？

3. **安全威胁模型还不够会议化。** 需要单独章节明确 attacker controls 哪些传感器/日志/reward/update data、是否知道 controller 和 gate、是否能自适应攻击、目标是 physical safety violation 还是 forced freeze/availability degradation。还要明确 defender 有哪些 trusted anchors、冗余传感器、secure estimator 或 fail-safe 模式。

4. **贡献类型目前夹在 theory、position、system 之间。** 如果走 theory paper，需要更深的 theorem 和证明；如果走 security/system paper，需要真实 artifact 和评估；如果走 position paper，需要更完整 taxonomy 和 roadmap。当前版本三者都有雏形，但任何一条都还没做到投稿级强度。

5. **Related work 仍需加厚。** 必引线包括 secure estimation/control、zero-dynamics/stealthy attacks、FT-CBF/NCBF、robust MPC under deception、safe RL attack/defense、adaptive control certification。现在引用还偏少，容易被认为漏读控制安全核心文献。

## 4. 安全 venue 机会评估

以下是经验性判断，不是统计概率。

| 目标 | 当前版本机会 | 扩展后机会 | 判断 |
|---|---:|---:|---|
| IEEE S&P / USENIX Security / CCS / NDSS full paper | 很低，约 0--5% | 有真实系统与强化 theorem 后约 10--25% | 当前太短、实验太弱、定理偏显然；扩展成 attack+defense 或 defense paper 后才有机会 |
| NDSS/CCS/USENIX workshop, CPS security workshop, Safe/Robust ML workshop | 中等，约 30--50% | 较高，约 50--70% | 当前故事适合 workshop/position，尤其是 certificate lifecycle angle |
| IEEE TIFS / IEEE TDSC | 低到中等 | 中等 | 需要更系统的 threat model、算法和多系统评估；TIFS/TDSC 对 CPS/control security 语境更友好 |
| ICCPS / HSCC / RTSS / CPS-IoT Week track | 中等 | 中到较高 | 如果强化形式化模型、CBF/QP 实例和 CPS benchmarks，可能比 top-4 security 更自然 |
| CDC / ACC / control venue | 中等 | 中等 | 需要把 theorem 做成真正的 control-theoretic result，而不是 security lifecycle framing |

最现实的路线是两阶段：先以 workshop/short paper 验证叙事和边界，再扩展为 full paper。若直接冲 top-4 security，必须补真实 learning-aware attack、defense gate implementation 和多系统评估。

## 5. 推荐投稿路线

### Route A：Top-4 Security Full Paper

目标叙事：attack+defense 或 defense paper。

核心命题应改成：learning-aware FDI can invalidate safety certificates by poisoning the update path; a certificate lifecycle gate is necessary and implementable with bounded cost.

必须补的内容：

1. Threat model section：FDI/log/reward/update-data attacker；white-box adaptive attacker；trusted anchor/fail-safe assumptions。
2. System model：至少两个 online-updated controller families，例如 safe RL/NN policy update、neural MPC/adaptive MPC、MFAC/MFAPC-style online estimator。
3. Benchmarks：至少三个 CPS settings，建议 water tank、microgrid/LFC、quadrotor 或 lane keeping。
4. Baselines：ungated learner、fixed severe-attack safety filter、always-freeze、post-update action filter、robust MPC/CBF where available。
5. Metrics：unsafe rate、certificate rejection rate、learning update rate、task cost/regret、freeze duration、trusted-anchor recovery rate、attacker effort。
6. Adaptive attacks：attacker knows the gate and optimizes either for unsafe acceptance or forced freeze。
7. Theorem upgrade：从 next-action membership 扩展到 reachable-history lifecycle condition，说明 action-level filtering is insufficient for future action-map certification。

### Route B：CPS/Formal Methods Paper

目标叙事：formal certificate lifecycle for adaptive controllers under attacked histories。

必须补的内容：

1. 把 $K_\Gamma(h)$ 具体化为 CBF/QP、reachability tube 或 shield synthesis 的可计算对象。
2. 给出 necessary and sufficient conditions for safe update set nonemptiness，至少在线性/仿射系统中非平凡。
3. 给出 parameter-level projection 或 constrained update algorithm，并证明 recursive certificate preservation。
4. 用 2--3 个 CPS benchmarks 展示 gate frontier、conservatism 和 computation time。

### Route C：Workshop / Position First

目标叙事：certificate lifecycle is a missing security boundary for adaptive CPS controllers。

当前材料已经接近可投，但仍建议补：

1. 一张 Figure 1：fixed safety filter vs online update lifecycle gate。
2. 一页 threat model。
3. 一张 gap matrix table。
4. 一个更完整的 demo figure：kernel width、update rate、unsafe rate 随攻击强度变化。
5. Related work 加厚到 20--30 篇核心文献。

## 6. 近期行动优先级

1. **先补 Figure 1 和 threat model。** 这两项会显著提升安全论文可读性，不需要先做大实验。
2. **把 theorem 升级到 future action-map lifecycle。** 当前 action-at-history 条件太弱；应加入 reachable histories 或 all future certified actions 的约束。
3. **做一个真实小型 CPS benchmark。** 推荐先做 water tank 或 microgrid LFC，因为状态、安全约束和攻击模型都容易解释。
4. **实现四个 baselines。** Ungated learner、action-only filter、always-freeze、certificate-gated learner。
5. **用学习感知攻击评价 gate。** 不只调大 ambiguity radius，还要让攻击目标直接针对 update rule。
6. **补 citation。** 先补 secure estimation/control 与 FT-CBF/CBF under attacks，再补 safe RL robustness 与 adaptive control certification。

## 7. 当前建议

不要把当前版本作为 top-4 security full paper 直接提交。它现在是一个有潜力的 seed：问题定位正确，最强邻居已经避开，核心论点清楚；但还缺让安全会议相信“这是一个真实 security problem 且 defense 有实际价值”的证据。

如果目标是尽快产出，可先投 CPS/security workshop 或安全机器学习 workshop。如果目标是 top-4，需要按 Route A 扩成完整 attack+defense paper，并把 minimal theorem 从定义级 gate 提升为多步证书生命周期结果。
