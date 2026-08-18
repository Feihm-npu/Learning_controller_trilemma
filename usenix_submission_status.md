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
