# USENIX Security 2027 Cycle 1 — 论文状态梳理

> 更新 2026-08-18。取代 `ndss_submission_status.md` 的版面与投稿部分；
> 科学结论与 claim-lock 契约不变，证据来源仍是该文件与 `results/*.csv`。

## 1. 投稿目标

- 目标：**USENIX Security 2027, Cycle 1**。
- **截止日期（2026-08-18 核对检索结果确认，CFP 页面对自动抓取返回 403，建议在
  HotCRP 里再核一次）**：
  - 强制注册 **2026-08-18 AoE**，正文 **2026-08-25 AoE**；
  - 注册时固定 **title、完整作者列表（含 ORCID）、topics**；abstract 只要求
    tentative，之后可改；
  - **Cycle 1 被拒的论文不能投同届 Cycle 2**（注册后不提交不构成 rejection）。
- 时间预算的直接含义：**不要再开新实验**。下面第 5 节按"零成本 / 低成本 /
  不要做"分了三档。

## 2. 形式状态：全绿

| 项 | 状态 |
|---|---|
| 正文（标题+摘要→Conclusion） | **13.0 pp**（要求 ≤13），结束于第 13 页页底 |
| PDF 总页数 | 26（附录+参考文献不计入限制） |
| 版心 / 字号 / 行距 | 7.0×9.0in、10pt、12.0pt，由 `usenix.sty` 提供，未手改 |
| overfull box / undefined ref / undefined cite | 0 / 0 / 0 |
| Open Science 附录 | 有（强制项） |
| Ethical Considerations 附录 | 有（含 stakeholder、harm、披露论证） |
| 匿名性 | 作者块为空；正文无致谢/基金/URL/机构名；PDF 元数据 Author/Title 为空 |
| claim-lock 测试 | 19/19 通过（含新增的 13 页上限自动检查） |

构建：`cd paper_latex && latexmk -pdf usenix_sec2027.tex`。

## 3. 正文结构与页预算

| # | 节 | 页 |
|---|---|---|
| — | 标题 + 摘要 | 0.37 |
| 1 | Introduction（Fig.1 信任边界） | 1.13 |
| 2 | Background and Problem Model | 0.86 |
| 3 | Threat Model（Table 1 写边界 + 适用条件） | 1.79 |
| 4 | Contract-Aware Update Analysis | 1.35 |
| 5 | Third-Party Shield-Retirement Case Study（Fig.2–3, Table 2） | 1.38 |
| 6 | Controlled Mechanism Study（Fig.4, Table 3–5） | 3.88 |
| 7 | Related Work（Table 6 delta 表） | 1.16 |
| 8 | Discussion and Limitations | 0.75 |
| 9 | Conclusion | 0.34 |

正文 4 图 6 表；附录 8 图 4 表。附录 A–I：证明 / 连续提升 / SOC 支撑 /
影响审计 / 边界 / 第三方 battery / LifecycleGate 基准 / 证书覆盖 / 统一前沿。

## 4. 科学主张分层（这是审稿人真正会评的东西）

### A 档 — 强、可直接主张

| 主张 | 证据 |
|---|---|
| 有限的 release 证据只在 runtime authority 仍驻留时有效 | V4 五个未触碰训练run：poisoned raw `27/120` vs clean `2/120` vs resident `0/120`，27 次均为及时切换；V3 `23/72`；独立审计 `19/71`。H=3/5/10 均满足预声明分离条件 |
| 单步动作安全不足以支撑该 release 契约 | one-step resident kernel `14/71` 失败 + 41 次空 kernel |
| 跨系统可复现 | Quadrotor：clean `0/72` vs reward-only poisoning `68/72`（全延迟）；Cartpole `1/188` vs `38/188` |
| 第三方生命周期保真度 | 复现 Carr Table 1 的定性排序（shield < smooth ≪ sudden ≤ no-shield），两个环境都成立 |
| 上游防御可完全封堵 | 冻结审计：trusted recomputation TPR/FPR `1.000/0`；task-aware 检查 TPR>0.90, FPR≤0.036 |

### B 档 — 真实但条件化（论文已按条件化措辞写）

| 主张 | 证据 | 条件 |
|---|---|---|
| 第三方 shield 退役边界上的因果隔离 | 3 个 provenance-complete 配对中 2 个阳性（3.6× / 1.6×），第 3 对新生成后未复现（0.241→0.242） | 依赖训练实现 |
| 跨 learner family 的影响 | REINFORCE 10-run 3 阳性；PPO 10-run 1 阳性；SAC 10-run 3 阳性 3 保护 4 无变化 | 无任一 family 内可靠成功 |
| 易感性前置条件（D_ret marker） | 50 run 语料：11 个阳性全在低分歧带（<0.06），32 个高分歧 run 无一阳性，AUC 0.953 | 描述性、事后测量、obstacle 域内 |
| 精确 batch reward 影响支撑 | 36 个 poisoned batch 中 22 个有验证见证；最大误差 3.67e-5 | 单 batch；不含坐标级参数裁剪 |
| U1 学习基线变体 | `40/126` vs `2/126` | 同族内稳健性，非独立 learner family |
| U2 非单点 plausible set | ρ=0.02/0.04：`44/126`/`61/126` vs `4/126`/`3/126` | 仅"持续"，非单调趋势、未触 freeze frontier |
| U3 in-loop known-sign gate | `39/126`→`0/126` | 安全性只等于 always-freeze，价值在选择性；sign-valid 攻击可绕过 |

### C 档 — 明确的负面边界（必须保持可见，是这篇论文可信度的来源）

- 官方 PPO：只有 checkpoint 级更新重定向，无稳定物理失败。
- Benign adaptation utility：LifecycleGate 相对 always-freeze 无任何配对 rollout 提升。
- 有效攻击**不隐蔽**：被 task-aware 检查检出；可信重算完全封堵。
- 精确支撑攻击构造路线失败（预声明门未过）；实际多批次攻击是固定 tanh 规则，不是 gate 优化器。
- 所有证书都是采样有限视界，不是连续状态不变集证明。

## 5. 面向 USENIX 的风险排序与应对

**R1（最高）——"这个攻击上游一句话就封死了"。** 审稿人会引用你自己的
TPR/FPR `1.000/0`。现有防守：§3.2 的 *Applicability condition* 段，把攻击面
限定在"reward 语义无法在高完整性平面内重建"（延迟质量标签 / 人工反馈 /
外部 KPI）。**这是全篇最该被读到的一段**，目前位置正确但只有一段；
Intro 里没有对应的一句话钩子。

**R2 —— 可利用性是条件化的。** 2/3、3/10、1/10、3/10 这些计数，在
"characterization paper"框架下是诚实，在"attack paper"框架下会被读成不可靠。
现有防守：论文把 D_ret 前置条件写成结果而不是借口（高分歧 = 强排除条件）。
这是全篇最聪明的一步棋，但要确保 Intro/摘要把它作为**发现**呈现。

**R3 —— 新颖性是组合式的。** 每个成分都已存在（Simplex、shield retirement、
reward poisoning）。赢在"证据不能跨权限交接复用"这一观察是否读起来非平凡。
现有防守：delta 表（Table 6）+ 漏洞类命名。

**R4 —— 纯仿真、低维学习器。** 无硬件、无真实 OT 部署。这是硬边界，只能诚实标注。

**R5 —— LifecycleGate 作为防御缺正向 utility 证据。** 已作为负面边界写明。
风险在于审稿人问"那你提的防御到底有什么用"。答案在契约分离表里（resident
authority 0/120），但 LifecycleGate 这个名字承载了太多它没证明的东西。

## 6. 截止前可做的事（按性价比）

**零成本（纯写作，建议做）**
1. Intro 加一句适用条件钩子，把 §3.2 的限定前移，抢在 R1 之前。
2. 摘要加入 quadrotor `68/72` vs `0/72`——目前最强的跨系统泛化信号，摘要里没有。
   现摘要 184 词，加一句仍在 200 词内；需检查是否仍 13 页。
3. 考虑弱化 "LifecycleGate" 这个产品名在正文的出现频率（它的 benchmark 已进附录）。

**低成本（可选）**
4. 让 Fig.3（D_ret 机制图）的 caption 更自解释——它承载了 B 档最重要的主张。

**不要做**
- 不要重开 PPO sweep、benign-utility 正式 run、精确支撑攻击路线。这三个都过不了
  预声明门，事后重开会毁掉负面结果的可信度——而负面结果正是这篇论文可信的原因。
- 不要在截止前开新 seed 命名空间。

## 7. 需要你决定

- [x] 确认 Cycle 1 截止日期（见第 1 节）。
- [x] 标题定稿并写入 `usenix_sec2027.tex:78`：
      **A Release Test Is Not Runtime Authority: Evidence Reuse at
      Runtime-Assurance Authority Transitions**（注册后不可改；旧候选留在文件注释里）。
- [ ] 8-24 做 go/no-go：判据见第 8 节。
- [ ] 注册时 topics 建议 CPS / embedded & control security 为主、ML security 为次。
- [ ] 作者名单 + 每人 ORCID（注册后不可改）。

## 8. 2026-08-18 主线重构（已执行）

把论文的主语从 "reward poisoning" 换成 "release-gate / authority transition"。
动机：原 headline claim 会被论文自己的 Table 5（trusted recomputation
TPR/FPR `1.000/0`）直接反驳。重构后核心 claim 变成非对抗命题——**一次性
release 检查 ≠ 保留的 runtime authority**——recomputation 从"反驳"降级为
"scoping"：它移除放大器，不移除 gap。

改动（全部零新实验，证据与 claim-lock 契约不变）：

| # | 位置 | 改动 |
|---|---|---|
| 1 | `usenix_sec2027.tex` | 标题；摘要重写（199 词），contract gap 打头，clean `2/120` 作为 non-adversarial witness，攻击作为放大器 |
| 2 | `sec1_introduction.tex` | 新增"无对手也能测到 gap"段与"对手放大 gap"段；applicability condition 钩子前移到 Intro；删除只定义一次、后文从未使用的 *certificate-evasive*；Evidence 段改为控制实验在前、Carr 在后 |
| 3 | `sec1_introduction.tex` | contributions 四条重写，**删掉 reward-influence geometry 那条**（正文已下沉） |
| 4 | `sec3_methodology.tex` → `appendix_support.tex` | §4.2 的 normalized zonotope / SOCP 命题下沉附录，正文压成一段 + 边界句；`\subsection{Certificate-Gated Update...}` 新增"一次性 vs 递归执行"对比段 |
| 5 | `sec3_methodology.tex` → `appendix_proofs.tex` | Prop *Action filtering is not update certification* statement 下沉（正文留 3 句 + 指针） |
| 6 | `sec4_evaluation.tex` | 新增 *The gap without an attacker* 段（clean 2/120 的读法，明确不外推）；horizon sweep 从一句话扩成独立段，写出三条同向曲线：接受数 72/72/72/57/49、switch lead 中位数 0/2/4/9、resident 失败 12→0 |
| 7 | `sec5_related_work.tex` | §8 Discussion 三段并两段并加"gap 先于 attack surface"的排序句；conic 分析块压成指向附录的一句；§7 各块收紧 |
| 8 | `sec6_conclusion.tex` | 以 "A release test is not runtime authority" 开篇，控制实验在前、Carr 在后，整体压短 |
| 9 | `test_tdsc_submission_artifacts.py` | 收紧 `test_usenix_body_fits_thirteen_pages`：原来只断言 Ethics ≤ p14，正文溢到第 14 页仍会绿灯；现在 Ethics 落在 p14 时额外要求 p14 首个文本块就是该标题 |

页面预算：重构一度把正文推到 14 页（Conclusion 溢出）。注意**早期章节的删减会被
浮动体吸收**，有效删减位置在最后一个浮动体（Table 6，p12）之后，即 §7 尾 / §8 / §9。
最终 13.0 pp、0 overfull、0 undefined、PDF 26 页、claim-lock 19/19。

### go/no-go 判据（8-24）

拿重构后的 Intro + Abstract 自读：读起来是"我们发现并系统测量了一个 release
contract gap，reward 通道是其中一个放大器"→ 提交；读起来仍是"我们做了个 reward
攻击"→ 撤回注册，投 Cycle 2（2027-01-19 注册），把 5 个月投入
experience/curriculum-selection 第二通道。


## 9. 模拟审稿回应（同日第二轮，已执行）

模拟审稿给 6–6.5/10 Weak Accept，指出五个提交前必修项。全部已改，无新实验。

**最关键的一项已核实为真**：Könighofer et al., *Online shielding for
reinforcement learning*（ISSE 2022, doi 10.1007/s11334-022-00480-4）结论逐字为
"the final learned policies inflict more safety violations than conventionally
learned policies, when executed in unshielded environments. Hence, to guarantee
safety of control policies obtained through shielded (or unshielded) RL,
shielding needs to be applied during execution in the field."（从 arXiv:2212.01861
PDF 提取原文核对）。这是本文 non-adversarial claim 的最近先验，原 bib 里没有。

| # | 改动 |
|---|---|
| 1 | 新增 `konighofer_online_shielding_2022` 引用；§7 开出专门段落**主动承认**该现象已知，并给两条 delta：(a) 他们的结论"execution 时必须保留 shield"在本文测量中**必要但不充分**——one-step resident kernel 就是 execution 时保留的，仍 14/71 失败，真正要保住的是 switching lead time；(b) 本文对象是 retirement **decision** 本身（repeated recoverability trigger ≠ one-time release credential）+ 对抗性 provenance |
| 2 | Intro 在 "Existing mechanisms" 段点名该先验并写出"我们问的是不同问题" |
| 3 | 摘要与 Intro 的 evidence tuple 对齐 Prop 1 的"may change one or more components"：hero transition 改变的是 **authority + horizon**，poisoning 再加 **provenance**，composition→raw 才动 **subject**。同一 over-claim 另外出现在 §8 Discussion 与 Appendix A 的 Prop 1 证明里，一并修正（模拟审稿只点了摘要/Intro） |
| 4 | 删除普遍性措辞："commonly commissioned" → "are commissioned"；"ordinary engineering practice retire..." → "Published learning-enabled control workflows study retirement of..."；"the standard way" → "a standard way" |
| 5 | `sec4_evaluation.tex:4` "located the authority-transition **vulnerability** in an independently published lifecycle" → "located the **authority transition** in..."，与 §7 "not the soundness of their original claims" 一致 |

页面代价：新的 closest-prior 段约 22 栏行。用真正重复的内容抵：§8 的 defense
taxonomy（§9 已完整重述一遍）、§8.1 里 reward-influence scope 那句（§4.2 已有且
locked 串在那边）、Conclusion 的 conditionality 从句（§8 已有）。最终仍
13.0 pp、0 overfull、0 undefined、26 页、claim-lock 19/19。


## 10. 模拟审稿第三轮（同日，已执行）

模拟审稿反对第 9 节里"我们证否了 Könighofer 的结论"这种措辞。**核实后该反对成立**：
原文 §4 讨论里已有

> "the safety of actions is only analysed within a finite horizon k. Therefore,
> the agent might end up in situations where any available action induces a
> high probability of violating the specification. It is therefore important to
> pick a finite horizon k large enough… there is a natural trade-off between
> the computational overhead… and the number of safety violations…"

也就是说"有限 horizon 太短会走进所有动作都不安全的状态"他们已经写了——本文那 41 次
empty kernel 正是这个情形的实例。necessary-but-insufficient 的说法会被同一批
reviewer 直接反杀，已撤回。

改成的口径（§7 + Intro）：

- §7 **同时承认他们的两个观察**（shielded learning ≠ 安全 raw policy；有限 horizon
  需要足够 lookahead），明说 **"We claim neither observation"**，并主动把 41 次
  empty kernel 写成对他们那条 caveat 的印证；
- delta 定位在两点：(i) 对象是 **retirement decision** 本身（同一个有限预测，一次性
  花掉当 release credential ≠ 保留为逐步复评的 recoverability trigger）；
  (ii) horizon sweep 量化的第二根轴是 **release admission**，而他们的 trade-off 另一端
  是 **computational overhead**——不是同一个代价。这一句也写进了 §6 正文图旁。
- Intro 改成 retain-vs-retire 的文献张力：Könighofer 建议保留，Carr/Hsu 的 workflow
  选择退役，未解决的问题因此不是"shield 有没有用"，而是"什么证据能正当化把 action
  authority 交给 raw policy"。
- 摘要最后一处普遍性措辞也软化："are commissioned" → "can be commissioned"，
  "Deployments then retire" → "A deployment can then retire"（199 词，仍在 200 内）。

**新图（正文 Fig. 3）**：`make_fig_horizon_contract.py` →
`paper_latex/figures/fig10_horizon_contract.pdf`，从
`results/cartpole_horizon_contract_sweep_summary.csv` 的 pooled 行读数（不硬编码），
一张单栏图同时给三条曲线：release admission 72/72/72/57/49、median switching lead
0/2/4/9、resident failures 12/0/0/0/0，阴影标出满足预声明分离条件的 horizon。
脚本与图都已登记进 manifest（267 文件）。

**图位交换**：susceptibility scatter（`fig9_mechanism_divergence`，原正文 Fig. 3）
移入 Appendix F。两张都留会把正文推到 14 页；论文的 intellectual center 已经变成
"release test ≠ runtime authority"，horizon 图直接对应标题，susceptibility 图是
attack characterization，且附录已有 `fig8_2x2_susceptibility` 承载同类证据。
§5 正文文字（11/11 低分歧、0/32 高分歧、AUC 0.953）全部保留并指向附录图。

交换腾出的空间用来把第 9 节里**纯为版面砍掉**的内容加回去：§8 的完整 defense
taxonomy、§8.1 的 reward-influence scope 句、Conclusion 的 conditionality 从句。

当前：正文约 12.3 页（Ethics 起于 p13），0 overfull、0 undefined、PDF 27 页、
claim-lock 19/19。**正文还剩约 0.7 页余量**。


## 11. 全文一致性审计 + 空间投放（同日第四轮，已执行）

### 11.1 修掉的一致性缺陷（11 处）

| # | 问题 | 位置 |
|---|---|---|
| 1 | §2 第四种失效模式仍是攻击者优先叙述（"shield 保住每个 transition **while corrupted reward records influence the learner**"），与 §1 的"gap 先于 attack surface"直接矛盾 | `sec2_background.tex` |
| 2–4 | **三个正文浮动体从未被正文引用**：Table 4（跨系统）、Table 6（delta 表）、Fig. 2（Carr 隔离） | eval / related / case study |
| 5 | 附录表当正文表引（"Table 10 and Fig. 4 show…"），而紧邻一句却写了规范的 "Table 7 in Appendix E" | `sec4_evaluation.tex` |
| 6 | "the same **integrity boundary**" / "exposes an **integrity boundary**" 把攻击者语汇挂在 Carr lifecycle 上，与 §7 的 "not the soundness of their original claims" 打架 | `sec6_third_party_case_study.tex` |
| 7 | §4.3 → §6 的前向指针在压版面时丢失 | `sec3_methodology.tex` |
| 8–9 | 附录两图（dose-response、matrix-parameter-gate）无引用 | 附录 |
| 10 | 覆盖审计附录**没有 `\label`**，无法被引用 | `sec8_appendix.tex` → `sec:appendix-coverage` |
| 11 | 正文 `LifecycleGate` 3 次中的 2 次（§6.6 benign 审计）改为 "the certificate-gated learner"——该段紧接着就说它 improves no paired rollout over freeze，产品名在此承担负面工作 | `sec4_evaluation.tex` |

现在 dangling ref = 0，orphan float = 0。

### 11.2 正文空间投放（A → B → C）

**A. 新增 §6.6 "Sizing a Release Gate"**（正文缺的"so what"）。此前 Prop 1 给了"改变了哪些前提就要重建哪些证据"，horizon sweep 给了"lookahead 下界由 backup 恢复时间决定"，**两者从未在正文接上**。新小节把它们接上，分两条：

- *Retiring authority*：需重建 Prop 1 中被改变的前提；本文契约里是 **authority + horizon**；再跑一次同样的检查两个义务都不解除。
- *Retaining authority*：lookahead 有下界（backup 恢复所需 lead time：h=1 零 lead 仍留 12 次失败；h=3–10 提前 2–9 步、零失败）和上界（可承受的 admission 损失：5→10、5→20 分别多拒 15 和 23 / 72）。**两个边界都能在部署方自己的 backup 和候选池上用同一套 sweep 测出来，不需要攻击模型。**

**B. 1728-pair 覆盖审计进 §6.7**：certified 1293 中零 PyBullet 违反；poisoned raw 违反 403/432、覆盖 0.062（informative rejection 而非空洞证据）；零 guard 时 horizon 20/50/100 各有 1/2/1 次 false acceptance，任意锁定正 guard 清零 false acceptance 但抬高 false rejection。结论句：**guard margin 是 horizon 之外的第二个可测旋钮，且它是对模型失配标定的，不是对攻击者标定的。**

**C. 跨系统结果接主线**：quadrotor `0/72 → 68/72` 不再只是报数，明写"每一次失败都延迟到适应期之后，所以受保护阶段对它们一无所报——分离跟随的是 authority transition 而不是平台"。

### 11.3 版面账

A 单独就吃掉了全部 ~91 行余量（浮动体重排）。B、C 靠删真冗余买单：§6.5 的三位小数延迟值与逐机制 reward 值（附录 I 已有表）、commit 可用性细节（附录 E 已有）、§8 第三次重述 defense taxonomy（§6.6 与 §9 已各有一次）、§5 两处同义重复句。

**期间 claim-lock 抓到一个我自己的错误**：我把 §6.4 结尾 "This gate therefore implements the measured detectability boundary" 当冗余删了，实际它是 U3 的锁定限定语（防止把 in-loop gate 读成通用防御）。已恢复被锁的那半句。这正是这套 claim-lock 存在的意义。

最终：正文 **13.0 页整**（p14 首块即 Ethical Considerations），0 overfull、0 undefined、PDF 27 页、claim-lock 19/19、manifest 267 文件。


## 12. 提交前自检（同日第五轮）

### 12.1 通过项

| 检查 | 结果 |
|---|---|
| 正文页数 | **13 / 13**（p14 首块即 Ethical Considerations） |
| 版心 / 字号 / 行距 | 612×792pt US Letter，7.0×9.0in，10pt/12.0pt，未手改 |
| overfull box / undefined ref / undefined cite | 0 / 0 / 0 |
| 匿名性 | `\author{}` 空；正文与附录无致谢、基金、机构、个人名、artifact URL；**PDF 元数据 Title/Author 均为空** |
| 必需附录 | Ethical Considerations + Open Science 均在，且顺序为 Ethics → Open Science → References → 附录 A–I |
| 引用完整性 | 39 条参考文献，**0 个 `[?]`/`??` 断引** |
| 图表引用 | dangling ref 0，**orphan float 0** |
| 草稿残留 | 无 TODO/FIXME/TBD/placeholder；无 NDSS/TDSC 残留 |
| 数字一致性 | 摘要 / Intro / §6 / §9 的 2-120、27-120、14/71、3.6、1.6 全部一致 |
| 字体嵌入 | 全部嵌入（子集化） |
| PDF 体积 | 0.48 MB |
| claim-lock | 19/19 |

### 12.2 自检中修掉的两个真问题

1. **正文图存在 Type 3 字体**（page 9 新增的 horizon 图、page 12 的 Fig. 4）。仓库里
   `carr_victim_experiment/make_fig6.py` 早有 `pdf.fonttype: 42` 的惯例，但
   `make_fig_horizon_contract.py` 与 `generate_tdsc_frontier_artifacts.py` 没跟。
   两个脚本都已补上并重新生成。重跑 frontier 生成器前先备份了它的 5 个锁定产物
   （2 个 `generated/*.tex` + 3 个 `results/*.csv`），**重跑后逐字节相同**，只有图变了。
   现在**正文 0 页含 Type 3**。

2. **`.venv-safe-control` 的 editable 安装指向仓库搬迁前的旧路径**
   （`.../research_brainstorm/directions/07_foundational_ai_security/...`），
   导致 `safe_control_gym` 无法 import、5 个测试模块收集失败。已把
   `site-packages/safe_control_gym.pth` 改为当前路径。修复后
   `.venv-safe-control/bin/python -m pytest` = **50 passed**。

### 12.3 未处理项（已知、有意保留）

- **附录图仍含 Type 3**（p20–22、24–27）。它们由
  `generate_benchmark_artifacts.py` 等**会重跑基准**的脚本产出，重新生成有让锁定
  CSV 漂移的风险，而 USENIX 的格式检查不查 Type 3。判断：收益（附录图文字可选中）
  低于风险，保持现状。若要修：给这些脚本加同样两行 rcParams，按上面的
  备份-重跑-逐字节比对流程操作。
- **`test_lifecycle_gate_semantics.py` 仍无法收集**：`.venv-safe-control` 里没有
  `torch`（系统环境有 2.9.0）。该模块导入 quadrotor PPO 实验模块。装 torch 是
  ~GB 级下载且会改动环境，未擅自执行。

### 12.4 提交前仍需你做的事（非论文缺陷）

1. 作者名单 + 每人 ORCID（注册时固定，不可改）。
2. topics 选择（建议 CPS / embedded & control security 为主、ML security 为次）。
3. **按 Open Science 附录的承诺，实际通过提交系统上传匿名化 artifact 归档**——
   附录写的是"submitted as an anonymized archive through the submission system"，
   这句话必须兑现，且包内不能有作者信息。
4. 上传前最后跑一次：`cd paper_latex && latexmk -pdf usenix_sec2027.tex` →
   `python3 generate_tdsc_reproducibility_manifest.py` → `pytest test_tdsc_submission_artifacts.py`。
