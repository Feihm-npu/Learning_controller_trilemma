# USENIX Security 2027 转投：计划与执行状态

> 创建 2026-08-18，同日执行完毕。取代 `ndss_submission_status.md` /
> `ndss_submission_todo.md` 的版面部分；科学结论与 claim-lock 契约不变。

## 0. 结果

| 指标 | NDSS (IEEEtran) | USENIX 迁移后 | USENIX 要求 |
|---|---|---|---|
| 正文（含标题/摘要 → Conclusion） | ~22.5 pp | **13.0 pp** | ≤13 pp |
| PDF 总页数 | 23 | 26 | 不限 |
| overfull box | 0 | **0** | — |
| undefined ref/cite | 0 | **0** | — |
| Open Science 附录 | NDSS 措辞 | **有** | 强制 |
| Ethical Considerations 附录 | 有 | **有** | 强烈建议 |
| claim-lock 测试 | 18/18 | **19/19** | — |

正文结束于第 13 页页底，Ethical Considerations 起于第 14 页页首。

版面实测（`usenix_sec2027.pdf`）：US Letter 612×792pt；正文主字号 10pt，
基线行距 12.0pt；文本块由 `usenix.sty` 设定为 7.0in × 9.0in
（`\textwidth=505.89pt, \textheight=650.43pt`），未手改任何几何量。

## 1. 文件变更

**新增**

| 文件 | 说明 |
|---|---|
| `paper_latex/usenix_sec2027.tex` | USENIX 主文件 |
| `paper_latex/usenix.sty` | 官方模板 |
| `paper_latex/sections/sec7_ethics_usenix.tex` | Ethical Considerations + Open Science |
| `paper_latex/sections/sec2_background.tex` | 原 §2 Model + §4 Failure modes 合并 |
| `paper_latex/sections/appendix_proofs.tex` | 6 个命题/引理/定理的证明 |
| `paper_latex/sections/appendix_lift.tex` | 连续提升定理、单调性、kernel 实例化、极小反例 |
| `paper_latex/sections/appendix_support.tex` | SOC 精确正支撑定理 + 证明 |
| `paper_latex/sections/appendix_influence.tex` | reward-influence 实现审计（22/36 批次） |
| `paper_latex/sections/appendix_boundaries.tex` | anchor / PPO / benign-utility / measurement 边界 |
| `paper_latex/sections/appendix_thirdparty.tex` | PPO+SAC battery、dose–response、第二环境、2×2 交叉表 |
| `paper_latex/sections/appendix_benchmarks.tex` | 原 §8.1–8.7 LifecycleGate 玩具基准 |
| `usenix_reproducibility_manifest.md` | 取代 `ndss_reproducibility_manifest.md`（后者改为指针） |

**删除**：`bare_conf_NDSS2027.{tex,pdf,bbl,html}`、`sections/sec7_ethics.tex`、
以及原 `sec2_preliminary.tex` / `sec4_lifecycle_attacks.tex` /
`sec5_lifecycle_gate_design.tex`（内容已并入其他文件）。

**注意**：section 文件名的数字前缀已与正文节号脱节
（`sec3_methodology.tex` 现在是 §4，`sec6_third_party_case_study.tex` 是 §5）。
为保留 git 历史没有重命名；如需整理是独立的一次改名提交。

## 2. 正文结构（13 pp）

| # | 节 | 实测页 |
|---|---|---|
| — | 标题 + 摘要 | 0.4 |
| 1 | Introduction（含 Fig.1） | 1.18 |
| 2 | Background and Problem Model | 0.89 |
| 3 | Threat Model（含 Table 1 + 适用条件论证） | 1.78 |
| 4 | Contract-Aware Update Analysis | 1.47 |
| 5 | Third-Party Shield-Retirement Case Study | 1.58 |
| 6 | Controlled Mechanism Study | 3.97 |
| 7 | Related Work（含 delta 表） | 0.97 |
| 8 | Discussion and Limitations | 0.74 |
| 9 | Conclusion | 0.35 |

附录顺序：Ethical Considerations → Open Science → References →
A 证明 → B 连续提升 → C SOC 支撑 → D 影响审计 → E 边界 →
F 第三方 battery → G LifecycleGate 基准 → H 证书覆盖 → I 统一前沿。

正文保留的图表：Fig.1 信任边界、Fig.2 Carr 隔离、Fig.3 disagreement 机制、
Fig.4 统一前沿；Table 1 写边界、Table 2 Carr 隔离、Table 3 契约分离、
Table 4 跨系统、Table 5 reward 完整性、Table 6 delta 表。

## 3. 内容层面做了什么

- **叙事重心前移**：Intro 第一段直接讲"训练时用 shield 保护、调试完成后退役"
  这一标准模式，第二段给出漏洞类命名 —— *evidence reuse across an authority
  transition*（利用方式：*shield-retirement poisoning*）。
- **摘要重写**（184 词）：先给正面结论 + 一句 "Exploitability is conditional on
  the realized retirement state"，非阳性计数移入正文。
- **威胁模型现实性**：§3.2 新增 *Applicability condition* 段，正面论证
  historian/ingestion broker/replay buffer 的可达性，并把"reward 何时不能被可信端
  重算"写成明确的适用条件（延迟质量标签、人工反馈、外部 KPI），同时明说
  确定性 reward 场景下可信重算直接消除该通道。
- **去对冲**：所有 caveat 收进 §8.1 Limitations 的四个具名段落
  （marker 是描述性的 / 形式结果的验证范围 / 经验普适性 / 威胁模型起点）。
- **标题**：改为 `Trained Behind a Shield, Unsafe Without It: Reward Poisoning at
  Runtime-Assurance Authority Transitions`。不喜欢可直接改
  `usenix_sec2027.tex` 第 74 行，已留注释。
- **有意偏离计划的一处**：契约名保留四个而非三个。one-step resident kernel 是
  一个有独立结果（14/71）的实验臂，删名会让 Table 3 读不通，仅在正文明确标注
  它是 negative control。

## 4. 排版层面做了什么（均不触碰字号/行距/版心）

- `caption` 宏包设 9pt（IEEEtran 原本就是 8pt，article 默认 10pt，22 个 caption 差近 1 页）。
- 调 article 浮动体参数（`topfraction` 等），否则 5 张图被推到文末，PDF 多出 3 页。
- 收紧 `\textfloatsep` / `\floatsep` / `\intextsep` 与 display skip（`\AtBeginDocument`）。
- 参考文献用 `\footnotesize` 包裹（IEEEtran.bst 保留）。

## 5. 工程侧同步

- `test_tdsc_submission_artifacts.py`
  - `manuscript_text()` 与全部锁定项指向 `usenix_sec2027.tex`；
  - `test_ndss_submission_format_lock` → `test_usenix_submission_format_lock`：
    断言 article+usenix.sty、无 `\IEEEpubid`/`\IEEEpeerreviewmaketitle`/`\appendices`、
    无 "NDSS"、作者块为空、Ethics/Open Science 两个附录存在、且未手改版心几何；
  - **新增** `test_usenix_body_fits_thirteen_pages`：直接从 PDF 里找
    "Ethical Considerations" 所在页，断言 ≤14（即正文 ≤13 页）；
  - 两处锁定原文随改写同步更新（语义不变）：
    `covers global Euclidean gradient clipping` →
    `under global Euclidean gradient-norm clipping`；
    `added a pole-angle bias with radius` → `a pole-angle bias of radius`。
- `generate_tdsc_reproducibility_manifest.py`：paper source / submission PDF /
  构建命令 / 手册标题全部改为 USENIX；补入 `usenix.sty`、
  `usenix_submission_plan.md`，以及此前漏登记的
  `fig6_ppo_isolation.pdf` 和 `fig9_mechanism_divergence.pdf`。
- `results/tdsc_artifact_checksums.csv` 已重新生成（264 个文件）。
  **改任何被锁文件后都要重跑一次 `generate_tdsc_reproducibility_manifest.py`，
  且必须在最终 PDF 构建之后跑**（PDF 本身在校验清单里）。

## 6. 还需要你做的事

- [ ] **确认 USENIX Security 2027 的投稿轮次与截止日期**（有多个 cycle，需查官网 CFP）。
- [ ] **匿名 artifact 的实际访问方式**：`sec7_ethics_usenix.tex` 的 Open Science
      段目前写的是"通过提交系统提供匿名归档"，提交前需换成真实做法
      （匿名仓库链接或上传包），并确认包内没有作者信息。
- [ ] 提交前最后跑一次：
      `cd paper_latex && latexmk -pdf usenix_sec2027.tex` →
      `python3 generate_tdsc_reproducibility_manifest.py` →
      `pytest test_tdsc_submission_artifacts.py`。
- [ ] 已知的环境问题（与本次改动无关）：`test_lifecycle_gate_semantics.py` 等 5 个
      测试因 `safe_control_gym` 无法 import 而在收集阶段报错，
      `.venv-safe-control` 里只有 dist-info。需要时重装该包。
