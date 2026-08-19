> ℹ️ **仍然有效，但结论以另一份为准（2026-08-19 标注）。** 本文件是当天早些时候的
> 124 条审稿清单与处置记录，逐条定位与修法仍可用。但当天稍晚的三个新实验推翻/收窄了
> 其中若干结论（尤其 SEC-01、EVID-01、resident authority 的有效范围）。
> **当前权威状态与方向请读 [`usenix_direction_audit_0819.md`](usenix_direction_audit_0819.md)。**

# USENIX Security 2027 投稿前批判性审稿 — 中途汇总

> 生成 2026-08-19。审稿 workflow 被手动中止，本文件汇总**已完成部分**。
> 全程 read-only，仓库未被修改（`git status` 已确认 clean）。
> 论文版本：`paper_latex/usenix_sec2027.pdf`（27 pp，正文 13 pp，build 2026-08-18 23:55）。

---

## 0. 执行状态

| 维度 | 状态 | 发现数 |
|---|---|---|
| 1. `usenix-format` USENIX CFP 逐项合规 | ✅ 完成（已抓取 Sec '27 真实 CFP + 官方模板 zip） | 9 |
| 2. `usenix-fit` PC 视角接收门槛 | ✅ 完成 | 16 |
| 3. `numeric-consistency` 全文数字交叉核对 | ❌ **未完成**（分析已做完，被中止于输出前） | — |
| 4. `logic-overclaim` claim–evidence 对齐 | ✅ 完成 | 16 |
| 5. `statistics` 统计严谨性（nature-statistics） | ✅ 完成 | 12 |
| 6. `citations` 文献核实 + 相关工作缺口（nature-ref-verifier） | ❌ **未完成**（Part A 机械检查已做，Part B 进行中） | — |
| 7. `figures-tables` 图表（渲染 27 页 PNG 实际查看） | ✅ 完成 | 19 |
| 8. `structure-terminology` 结构/术语/阅读负担 | ✅ 完成 | 18 |
| 9. `ai-writing-body` 摘要+正文语言（nature-polishing） | ✅ 完成 | 17 |
| 10. `ai-writing-appendix` 附录+Ethics+标题摘要 | ✅ 完成 | 17 |
| **Verify 阶段（对抗性验证）** | ❌ **未运行** | — |
| **Completeness critic / 合成** | ❌ 未运行 | — |

**合计 124 条发现，均为单 agent 未经对抗性验证的结论。**
我本人另行独立复核了 3 条（下文标 `【我已验证】`）。其余请当作"高质量线索"而非定论。

---

## 1. 总体判断

按目前证据，这篇稿子**以现状投 USENIX Security 2027 大概率被拒**，但拒的原因不是数据错，
而是三件事叠加：

1. **合规风险是可以当场致命的**：Open Science 附录承诺了一个不存在的 artifact 访问路径，
   而 artifact 本身完全没做匿名化（`/home/feihm`、NUS 邮箱、git history）。CFP 明文写
   "may be rejected without review"。这是唯一一条**过了 2026-08-28 就再也补不回来**的问题。
2. **novelty 的最强反驳是论文自己给出来的**：§7 明确把"shield 训练出来的策略脱离 shield 不安全"
   归给 Könighofer et al. 2022 并说 "We claim neither observation"，而摘要第二段恰恰用这条当
   头条证据（"The gap does not require an adversary"）。审稿人不需要做任何功课就能引用作者反驳作者。
3. **安全贡献被论文自己关掉了**：一行 "reward 非正" 语义检查把 39/126 打到 0/126、FPR=0；
   而所有能绕过该检查的攻击变体都"不造成部署危害"。也就是说在整个已评估攻击空间里，
   **有效 ⇒ 可检测，隐蔽 ⇒ 无效**，中间没有点。

真正扎实的东西是有的，而且不该被埋掉：**contract/horizon 结果**——一个 5 步 release check
花掉一次当凭证 ≠ 保留它当 recoverability trigger；lookahead 的下界由 backup 的恢复 lead time 决定、
上界由 operator 能接受的 admission 损失决定，且**两者都能在不知道攻击模型的情况下测出来**。
这是一条 operator 能直接用的规则，也是唯一一条不依赖 attacker 的贡献。
Limitations 一节的坦诚程度也远高于平均水平——本轮 P1 里有相当一部分，问题不是"没承认"，
而是"正文别处的说法与 Limitations 自相矛盾且没有互相指路"。

---

## 2. USENIX 场地标准逐项检查

CFP 来源：`https://www.usenix.org/conference/usenixsecurity27/call-for-papers`（2026-08-19 抓取）。
关键日期：**Cycle 1 注册 2026-08-18（已过）→ 投稿 2026-08-25 → artifact 2026-08-28**。

| 要求 | 状态 | 证据 |
|---|---|---|
| `usenix.sty` 未改 | ✅ PASS | 与官方模板 zip **字节一致**（diff exit 0） |
| documentclass / 版心 / 字号 / 行距 | ✅ PASS | 实测 612×792pt、7.03in×8.99in、baseline 11.96pt、10pt Times |
| 正文 ≤13 页 | ✅ PASS（**零余量**） | 正文 p.1–13，Ethics 起于 p.14 顶；p.13 两栏都到 baseline 713.2 / 720pt |
| References / Appendices 不计页 | ✅ PASS | pp.14–15 / pp.16–27 |
| Open Science 附录（强制） | ⚠️ **FAIL** | 只写"通过提交系统的匿名归档"，**无 URL**；CFP 要求 anonymous.4open.science + SEC27，且投稿后 PDF 不能改 |
| Ethical Considerations 附录 | ✅ PASS | 内容 paper-specific，引 Menlo + USENIX ethics |
| 稿件本身匿名 | ✅ PASS | `\author{}` 空、无致谢/基金/URL/路径；PDF /Info 全空；zlib 全流扫描无 `feihm`/`ndss` |
| **Artifact 匿名** | ❌ **FAIL** | `usenix_reproducibility_manifest.md:10` 含 `/home/feihm/llm-fei/.llm/bin/python3`；`aggregate_table_v2.csv` 含 115 条绝对路径；`server_scripts/*.sh` 含 `/home/feihm/anaconda3`；git history 含 `Feihm-npu <fei.hongming@u.nus.edu>` |
| 无空白压缩 / 字体默认值改动 | ⚠️ **RISK** | 见 FMT-01/FMT-02：`\textfloatsep` 20→10pt、`\floatsep` 12→8pt、display skip 10→5pt，约回收 0.3 栏；CFP 明文 "forbidden and may result in rejection" |
| 灰度可读 | ⚠️ **FAIL（Fig.2）** | clean RGB(64,139,191) vs poisoned RGB(220,71,72)，luminance 122.5 vs 115.7 → 灰度下同色 |
| 附录不必读 / 正文自足 | ⚠️ 3 处不自足 | guard-margin 结论无数字（sec4:371）、§6.7 "full figures" 全推附录、§6 开头把 filtering-vs-admission 分离整体推给 Appendix G |
| 同时投稿披露 | ⚠️ **RISK** | `bare_conf_compsoc.pdf` 是同一工作的 IEEE-compsoc(TDSC 版式) 完整 build（2026-07-31，标题不同）；`ndss_*.md`/`tdsc_*.md` 在 artifact checksum 清单里；正文无任何 prior/parallel version 说明 |
| PDF 内部残留 | ⚠️ **FAIL** | `/PTEX.FileName (./figures//tdsc_security_availability_frontier.pdf)` —— **TDSC = IEEE TDSC** `【我已验证】` |
| 字体嵌入 | ⚠️ 12 个 Type 3 | 来自 9 个 matplotlib 图（`pdf.fonttype` 未设 42），文字不可搜索、缩放呈位图 |
| HotCRP 自动格式检查 | ✅ 会 PASS | 它只测页面/版心/字号/行距/页数 |
| ML-work 附加要求（威胁模型四要素） | ✅ PASS | 但**投稿时 topic 必须选 Cyber-physical systems security，不能选 Security of ML**，否则有 topic desk-reject 风险 |
| Abstract ≤200 词 | ✅ 197 词 | |
| 页码 | ✅ 有，居中页脚 | |
| 参考文献 URL 全活 | ✅ 18/18 HTTP 200 | 抽验 `burbano_badcontrol_2026` / `mirzaeedodangeh_safe_updates_2026` / `capone_bandit_safe_control_2025` 与出版页逐字相符，无幻觉引用迹象 |

---

## 3. P0 —— 会导致 desk-reject 或致命审稿意见

### [ANON-01] Artifact 完全没做匿名化，且截止后无法补救
- **位置**：`usenix_reproducibility_manifest.md:10,59,65,71,77,83,89,95,101,107…`；
  `carr_victim_experiment/results/aggregate_table_v2.csv`（115 条绝对路径）；
  `carr_victim_experiment/server_scripts/*.sh`；git history
- **原文**：`| python | 3.10.12 ... | /home/feihm/llm-fei/.llm/bin/python3 |`
- **问题**：Open Science 附录承诺 reviewer 能拿到 artifact；reviewer 打开的第一个文件就是这份
  manifest，里面是作者用户名 + home 目录；git commit 里是真名 + `u.nus.edu` 邮箱。
- **审稿人会怎么用它**：CFP 原文 "Authors are solely responsible for ensuring no identifying
  information is exposed (e.g., usernames, organization names, commit history)" +
  "may be rejected without review"。
- **解决方案**：打包前 ①manifest 里所有解释器路径换成 `python3` / `./.venv/bin/python`；
  ②CSV 路径列改 repo-relative；③shell 脚本用 `${ARTIFACT_ROOT}`/`${CONDA_PREFIX}`；
  ④**不带 `.git` 目录**打平快照，或传 anonymous.4open.science（conference ID `SEC27`，
  过期日设在 shepherd 批准之后）；⑤打包后跑
  `grep -rIl -e feihm -e nus.edu -e '/home/' <archive>` 要求 0 命中，再重跑 checksum。
- **置信度**：PLAUSIBLE（路径泄漏本身确定，是否会被判 reject 取决于 chair）

### [OSCI-01 / OS-01] Open Science 附录写了一个不存在的访问路径
- **位置**：`sections/sec7_ethics_usenix.tex:53-55`
- **原文**：> For anonymous review, the artifact is submitted as an anonymized archive through the submission system, so the review committees can access every component without contacting the authors.
- **问题**：这是**现在时陈述句**，声称 reviewer 已经能拿到全部组件。CFP 明确要求
  "artifacts must be shared through anonymous links"，且 "Anonymous URLs should be included
  in the paper's Open Science Appendix"。更关键：投稿后有 3 天 artifact 上传宽限期，
  但**这期间 PDF 不能改**——链接必须在 8-25 当天就在 PDF 里。
- **审稿人会怎么用它**：一篇整篇论证"证据必须重新建立、不能靠断言跨边界"的论文，
  在自己的合规附录里放了一条无法核实的证据断言。这是这篇论文唯一吸收不了的可信度失分。
- **解决方案**：8-25 前把这句换成真实路径：
  `All artifacts are available for anonymous review at https://anonymous.4open.science/r/<id> (conference ID SEC27; access remains open through the shepherd-approval deadline).`
  **先建仓再定稿**，保证 PDF 里的链接第一天就是活的。若确定不提供，就诚实写
  "Artifacts are not distributed during anonymous review. On acceptance we will publish…"。
- **置信度**：CONFIRMED

### [CLM-01] 摘要的非对抗性结论，比较的是一组从未跑过的实验臂
- **位置**：`usenix_sec2027.tex:97-100`（并见 `sec1_introduction.tex:55-60`、`sec6_conclusion.tex:7-9`）
- **原文**：> The gap does not require an adversary. In a controlled Safe-Control-Gym study, snapshots that passed a five-step release check failed on 2 of 120 pairs once released raw, whereas the same prediction retained at runtime failed on none; a one-step filter did not suffice.
- **问题**：三个数字来自三条不同臂。agent 核对 `results/cartpole_v4_untouched_confirmation_rollouts.csv`：
  文件里只有 `clean_release` / `poisoned_release` / `resident_predictive_simplex` 三个 mechanism；
  `resident_predictive_simplex` 的 `reverse_switch_max_margin` 列与 `poisoned_release` **逐字节相同**，
  即 resident 臂**只在 poisoned snapshot 上跑过**。协议文件
  `cartpole_v3_fixed_target_tanh_protocol.md:65` 也这么写。仓库里**不存在 clean resident 臂**。
  "a one-step filter did not suffice" 的 14/71 更是来自另一个不相交 cohort（2040–2042 / 8040–8042），
  同样只有 poisoned snapshot。
- **审稿人会怎么用它**：USENIX 的 Open Science 让审稿人很可能真去要原始数据。
  "clean raw release 会失败、clean resident authority 不会"——这个论文头条对比**没测过**。
- **解决方案**：二选一。①**补跑**：在同样 120 对 state 上跑 clean snapshot 的 resident predictive
  authority，作为第四行报出来（agent 判断大概率是 0/120：两个 clean 失败点 2100/idx17、idx22 的
  CasADi 首次违规在 step 11 和 10，远在 5 步 lookahead 之外）。②不补跑就改写摘要，把条件标清楚：
  `…failed on 2 of 120 pairs once released raw; under bounded reward-record poisoning the same prediction retained at runtime failed on none of 120 and switched before all 27 failures, while a one-step resident kernel on a disjoint poisoned cohort still failed on 14 of 71.`
  §1 和 §9 同步改。**Table 3 也要相应改标（见 CLM-02）**。
- **置信度**：PLAUSIBLE（结论强，但基于 agent 对 CSV 的读取，未经二次验证——**建议你亲自复核这一条**）

### [NOV-01] 非对抗性头条结论，论文自己归给了 Könighofer et al. 2022
- **位置**：`sections/sec5_related_work.tex:21-27` vs `usenix_sec2027.tex:97-100`
- **原文**：> Könighofer et al. establish the non-adversarial half of this observation: policies trained under an online shield inflict more unshielded violations than conventionally trained ones, so shielding must be applied during execution. […] We claim neither observation.
- **问题**：agent 核对了原文，Könighofer 的结论逐字是 "the final learned policies inflict more
  safety violations than conventionally learned policies, when executed in unshielded environments"，
  其 Table 1 已经报了同样的四路对比，而且**已经周期性地无 shield 评估过 raw policy**
  （"Every 10,000 steps of training, we execute the current policy for 1000 games without a shield"）。
  论文声称的两个 delta 中，第二个（lookahead 不足）在同一段里也被承认是 prior work。
- **审稿人会怎么用它**：> "Strip the naming and the tuple, and the empirical claim is Könighofer 2022 Table 1 re-run in Safe-Control-Gym with n=120 instead of n=1000 games."
- **解决方案**：把非对抗性结果从头条降级为 replication，摘要第二段开头就归属：
  `Könighofer et al. showed that shield-trained policies are unsafe when the shield is removed; we show the stronger and unaddressed fact that the finite check used to authorize the removal is itself the evidence that fails.`
  然后让真正的 delta 承担经验重量——**做一个 Könighofer 的实验做不出来的测量**
  （例如：遵循他们的建议保留 shield，但 shield 是**有限 horizon** 的，照样失败）。
- **置信度**：PLAUSIBLE（引文与原文核对过；"是否只是 reframing" 是判断题）

### [SEC-01] 攻击被一行语义检查完全关掉，且论文自己证明了这一点
- **位置**：`sections/sec4_evaluation.tex:261-269`、`:254-257`、`sections/sec3_threat_model.tex:76-78`
- **原文**：> this gate reduced poisoned raw-release failures from 39/126 to 0/126 and froze 35 of 36 poisoned batches. […] It detects the sign-violating effective attack, while the sign-respecting variants evade the check and independently caused no deployment harm.
- **问题**：**有效 ⇒ 可检测；隐蔽 ⇒ 无效**，整个已评估攻击空间里没有中间点。
  加上 trusted recomputation TPR 1.000/FPR 0，攻击面被两道极廉价的防御同时关死。
  而作为"自适应攻击者评估"的证据很薄：两个 shape 变体、**只在一个 development realization 上**、
  n=24 rollouts；`appendix_benchmarks.tex:154-156` 的 finite-search 白盒攻击者只跑在
  toy 标量/二维 tank 抽象上打 LifecycleGate，没打 provenance binding / recomputation / commit admission。
- **审稿人会怎么用它**：> "The attack is defeated by a sign check and by recomputation; the residual contribution is the contract observation, which is prior work."
- **解决方案**：①构造真正的自适应攻击者——把 sign / envelope / moment / recomputation 约束
  **作为显式约束写进投毒优化**（而不是事后 shape 变体），在全部 5 个 V4 run 上跑，
  报告"是否存在受约束攻击仍保留部署危害"；②若不存在，就把这当**正面结论**重构论文：
  §6.4 改名 "Why the reward-record channel is closable"，攻击从贡献列表降为动机性存在性证明。
  **不要保留现在这种"把攻击当威胁呈现、证据却显示它已关闭"的框架。**
- **置信度**：CONFIRMED（文本事实）/ PLAUSIBLE（严重度判断）

### [EFF-01] 语料里"保护性"结果和"阳性"结果一样多，正文一个字没提
- **位置**：`sections/appendix_thirdparty.tex:26-34,46,63-65,71,99-102` vs `sec6_third_party_case_study.tex:135-140`
- **原文**：> Three runs were positive […], three were protective, and four were unchanged.
- **问题**：按附录自己的措辞点数：SAC 3 protective、PPO shield-on-only 6 protective、
  第二个 gridworld 2 protective（p=8.4e-81、1.3e-15）、shape 控制若干 protective ——
  **至少 11 个 protective，对 11 个 positive**。而正文唯一的语料级总结
  （"12 of 20 … none of 33 ceiling runs was positive"）把所有显著反向结果都折进中性词
  "non-positive"。positivity 规则本身按构造就是单边的。
- **审稿人会怎么用它**：> "This is a variance source, not an attack." —— 对攻击类论文这是致命的内部效度反驳，
  并且回头削弱第三方头条（2/3）和摘要的 3.6/1.6。
- **解决方案**：在 §5 加语料级**双边**记账：positive / protective / unchanged 按 learner family
  和 domain 分层的计数表，外加对全部 53 个 paired at-retirement delta 做符号检验或双边置换检验。
  若不显著，诚实的说法是"bounded reward-record poisoning 能在易感 realization 上造成大幅
  at-retirement 损伤，但不移动总体均值"，摘要和 §5 头条按这个改。
- **置信度**：PLAUSIBLE（计数需复核；措辞事实确定）

### [UTIL-01] 在论文自己的每一个配置里，"不学习"都占优
- **位置**：`generated/tdsc_frontier_results.tex`、`generated/tdsc_core_results.tex`、`appendix_boundaries.tex:32-38`
- **原文**：> Mean reward ordered freeze, clean, commit, shield, MPSC from $-0.023$ to $-0.457$; […] no mechanism improved on freeze in any of the 24 blocks.
- **问题**：Always-freeze 0/24 violations、reward −0.023，**优于** Clean REINFORCE（−0.024）；
  cartpole 上 freeze 0 violations/−0.117 优于 clean 1 violation/−0.197；benign 审计里
  LifecycleGate "improves no paired rollout over freeze"。论文自己在
  `sec3_threat_model.tex:182-184` 立的标准是 "useful learning requires paired task improvement
  over always-freeze"，**全文没有任何地方达标**。
- **审稿人会怎么用它**：整条威胁链的前提是"部署需要在线适应"。若 freeze 在安全和收益上都更好，
  前提坍塌，下游所有 contract / 攻击 / 防御都在回答一个没人问的问题。
- **解决方案**：补一个**在线学习确实优于 always-freeze** 的 benign 场景（比 0.003 N 差动执行器
  偏置更大的扰动，或最优点随时间漂移的任务），用同样的 paired-block bootstrap 报在 §6 frontier
  小节之前。若在现有 harness 里找不到，就在 §8 明说"所研究的部署没有已证明的适应收益，
  结论因此以 operator 出于所测收益之外的理由适应为条件"，并把 §3.6 的 availability/utility 措辞去掉。
- **置信度**：CONFIRMED（数字来自 generated 表）

### [STAT-01] 伪重复：n=3 训练轮次旁边印着 p = 2.6×10⁻¹⁴⁹
- **位置**：`sections/appendix_thirdparty.tex:11-13`，同型再现于 `:16-17, :29, :57, :61, :70, :99-102`
- **原文**：> violations in one of three paired runs, from 1178 to 2439 (McNemar exact $p=2.6\times10^{-149}$).
- **问题**：所有第三方 McNemar 的单位是**单个 clean/poisoned 冻结策略对的一个评估 episode**
  （n=5000 episodes / `analyze_fullphase.py:62-68` 的 `binomtest(b,b+c,0.5)`），
  而科学 claim 是关于**训练轮次**的，同一句话里写着"one of three"。
  唯一的 conditional-scope 免责声明在正文 `sec6:131-133`，距此约 9 页，使用处从未重述。
- **审稿人会怎么用它**：这是教科书级 pseudoreplication。而且论文的 per-run "positive" 标签
  本身就是由这些 episode 级 p 值定义的，所以反驳会传导到 Table 2、12/20 vs 0/33、11/11 vs 0/32 和 AUC。
- **解决方案**：①在 Appendix F 第一段（任何 p 值之前）插入 scope 段落，明确"单位是 episode、
  不携带跨训练轮次的重复性、训练级重复数随各 battery 给出"；②把每个极端值换成
  **效应量 + 区间 + 截断 p**，例：
  `from 1178/5000 to 2439/5000 evaluation episodes (paired risk difference $+0.252$, 95% CI …; exact McNemar $p<10^{-4}$, conditional on this one policy pair)`；
  ③**全文任何地方不再印小于 10⁻⁴ 的 p**。
- **置信度**：CONFIRMED

---

## 4. P1 —— 审稿人会作为主要 concern 提出

### 4.1 威胁模型与证据强度

| ID | 位置 | 问题 | 解决方案 |
|---|---|---|---|
| **THR-02** | `sec3_threat_model.tex:91-94` vs `sec1_introduction.tex:79-81` | 能力自相矛盾。Intro 说 "bounded scalar reward records … **and nothing else**"，但实际攻击规则 `2\tanh(\epsilon_t(\mu^\star_t-\mu_t))` 需要**每步读取当前策略均值 $\mu_t$**，还要知道 plant-specific 有害目标 $(18,-5)$。Table 1 标题是 "Evaluated **write** boundary"，静默省略了读能力 | Table 1 加 "Read authority" 列并逐项论证；或做 parameter-blind 消融（$\mu_t$ 换成陈旧/估计值），或改写 Intro 去掉 "and nothing else" |
| **THR-03** | `sec3_threat_model.tex:65-70` | 两条引用不支撑所设访问。`nist_ot_security_2023` 是 SP 800-82r3 通用指南，`mitre_data_historian` 是 ATT&CK **资产页**（A0006），不是 technique 也不是任何被攻破的 RL 更新路径。无 CVE、无 ICS-CERT、无厂商产品、无实际部署 | §3.2 加至少一个具体可引实例（某工业 RL/自适应控制产品或参考架构 + 该路径上的已知弱点类，用 T0872/T0889 这类 technique 而非资产页）；否则改标题为 "Hypothesized applicability" 并在 §1/§8 明说 prevalence 未知 |
| **ARTIFACT-01** | `sec1_introduction.tex:14-16` | 被攻击的对象**没有引用**。五步 lookahead 当一次性 release 凭证是作者自己的构造，在 development run 上调过参 | 引一个真实用有限 rollout 当 release 凭证的 workflow/标准/认证实践；找不到就明确重构为 "constructed-baseline sensitivity analysis"，重心移到 horizon sweep |
| **CONF-01** | `appendix_thirdparty.tex:72-74` | 重跑 **clean** 配置（无攻击者）把 at-retirement 从 0.232 挪到 0.776 —— 3.3× 摆动，等于甚至超过声称的攻击效应（0.216→0.777, 3.6×）。paired 设计控制不了 mode 进入 | Appendix F 加 clean-vs-clean null battery（≥10 对），用同样 positivity 规则算该规则在 null 下的假阳性率 |
| **EVID-01** | `sec4_evaluation.tex:38-40` | 2/120 的两次失败**集中在 5 个 run 中的 1 个**，另 4 个 run 全 0；无统计检验；作者自己在 :47-48 说设计不支持这个 claim，但摘要/Intro/贡献 2/结论都当既成结果 | 补一个专为 clean rate 设计的 cohort（≥20 独立训练 run）；在此之前改成存在性 claim 并注明"出现在 5 个 run 中的 1 个" |
| **NOV-02** | `sec6_third_party_case_study.tex:20-25` | Carr 自己的**未投毒** sudden retirement 已经 3277/3784 violations，与 no-shield（3798/3784）几乎不可区分——基线已经饱和，攻击者的边际贡献论文从未量化 | Interpretation 段加边际风险陈述：多少 post-retirement 风险归因于攻击者、多少归因于 retirement 本身；明说 ceiling realization 里攻击者无关紧要 |

### 4.2 形式化部分

| ID | 位置 | 问题 | 解决方案 |
|---|---|---|---|
| **PROP-01 / CLM-10 / PRF-01** | `sec3_threat_model.tex:131-138` + `appendix_proofs.tex:4-14` | Proposition 1 是定义伪装成定理：`unsound`、`evidence obligation`、`re-established` 全文无定义。证明的关键句 **"A conclusion derived from one premise set is not preserved after a premise is removed or weakened"** 作为全称命题是**错的**——去掉前提使推导失效，不使结论为假。贡献 1 的动词 "show" 挂在这上面 | ①形式化：给出 $E \vdash_C \varphi$ 判断，soundness 定义为"接受 ⇒ $C_{deploy}$ 下安全"，命题变成"$\vdash$ 在分量改变下非单调"，证明是一行存在性见证（指向 `appendix_lift.tex:164-181` 的极小反例 + 2/120）；②或降级为 `\begin{definition}`，删证明，贡献 1 改 "define … and use it to organize"。**另外把 "is not preserved" 改成 "is no longer entailed"** |
| **PRF-02** | `appendix_proofs.tex:48-56` | Theorem 1 的假设 "sound **lifecycle certificate**" 在全文只出现两次：假设本身，和**它自己证明的第一行**。证明提供了让定理立即成立的定义 | 把该定义移到 §2.2（Definition 1 之后），证明改成直接对 $h'$ 逐点应用 Lemma 1；并在 §4 诚实加一句 "Theorem 1 unfolds the lifecycle certificate semantics" |
| **PRF-03** | `appendix_proofs.tex:58-64` | "the two inequalities above" 指向空处——真正的指代对象在 11 页之前的 `sec3_methodology.tex:70-75`，且**没有 `\label`**（全文 30 个 equation 环境只有 7 个带 label） | 给该式加 `\label{eq:parameter-gate-halfspaces}` 并改成 `the two inequalities of~\eqref{...}`；`appendix_benchmarks.tex:64` 的 "the system above" 同病 |
| **PRF-04** | `appendix_support.tex:4-5` | 附录 C 说 "states and proves"，但 Proposition 5 的证明在附录 A，且**渲染顺序颠倒**：证明在 p.16，命题在 p.17。附录 A 内部证明顺序也是乱的（Prop1, Lem1, Prop3, Thm1, Prop2, Prop5） | 把 Prop 5 的证明搬进 `appendix_support.tex`；附录 A 按陈述顺序重排；给 `appendix_proofs.tex` 加一句开场（它是唯一冷启动于 `\begin{proof}` 的附录） |
| **THEORY-01 / CLM-11** | `appendix_influence.tex:32-35` | Theorem 3（`thm:reward-halfspace-support`）和 Proposition 4（`prop:plausible-monotonicity`）**全文从未被 `\ref` 引用**。而 Theorem 3 按作者自己的审计解释不了所评估的攻击：预注册的机制判据**失败**（22/36 vs 要求 27/36），目标方向推进只在 6/20 批次成立 | Theorem 3 在 `sec3_methodology.tex:96` 用一句话说明其作用（"给出 per-batch 不可跨越证书，因此攻击必须是 multi-batch"）并按编号引用；Prop 4 在 anchor 审计处引用或删除。**考虑把 §4.2 + 附录 C 整体移出正文**，腾出的版面给 EVID-01/EFF-01/UTIL-01 所需的补充实验 |

### 4.3 统计

| ID | 位置 | 问题 | 解决方案 |
|---|---|---|---|
| **STAT-02** | `sec6_third_party_case_study.tex:142-145` | **循环证据**。$D_{ret}$ 和 clean at-retirement violation 不是两个量，是一个量测了两次：agent 从 `aggregate_table_v2.csv` 重算得 Pearson r = 0.988、Spearman 0.968，比值中位数 0.136；协议里 $D_{ret}$ 的定义（unmasked argmax 落在 shielded set 之外的步数比例）与 unshielded violation 是嵌套的。于是 0.06/0.09 band 只是 clean-violation 0.5 切分的换名，"high disagreement 排除所有阳性"归约为"攻击无法抬高已在天花板的违规率" | 改写为"同一 retirement state 的第二个视角而非独立视角"，删掉 "sharper"；Limitations 加一句明说这是 ceiling effect。若要保留 "sharper"，必须同时报 clean violation 的 AUC 让读者看增量 |
| **STAT-04** | `usenix_sec2027.tex:97-100` | 全文唯一**没有任何推断支持**的对比：clean raw 2/120 (Wilson [0.005,0.059]) vs clean resident 0/120 ([0,0.031])，区间重叠；两个 discordant 全同向 ⇒ **双侧精确配对 p = 0.50**。而论文别处印到 1e-149 | 自己把这个不显著的 p 报出来（比让审稿人算出来安全得多）：`…two discordant pairs, both against raw release, giving a two-sided exact paired $p=0.50$; we report the two failures as witnesses of the mechanism, not as evidence of a rate difference.` |
| **STAT-05** | `sec4_evaluation.tex:74-77` | 正文**没有一个头条比例带区间**。Wilson 95%：2/120 [0.005,0.059]；27/120 [0.159,0.308]；19/71 [0.179,0.381]；14/71 [0.121,0.304]；0/33 [0,0.104]；0/32 [0,0.107]。尤其 19/71 vs 14/71 用来论证 "Residence alone is not the remedy"，但两者**不可区分**（unpaired Fisher p = 0.43），且两个 resident 机制之间没有任何配对检验 | Table 3 / Table 4 加 Wilson 列；"none of 33/32 was positive" 后加上界（0.104/0.107）；一步 kernel 那句改成"不声称与 raw release 有差别，只声称达不到 0/71" |
| **STAT-06** | `sec6_third_party_case_study.tex:147-151` | AUC 0.953 报到三位小数，11 阳性 + 39 阴性，**无区间**（Hanley–McNeil SE ≈ 0.046，logit 95% CI ≈ [0.73, 0.99]），band 在同一语料上选的。而**真正做过的内部验证没写进稿子**：`EXPERIMENT_SUMMARY.md:93-97` 记录 leave-one-family-out 为 REINFORCE 20/20、PPO 20/20、**SAC 3/10**，且 `test_tdsc_submission_artifacts.py:246` 主动禁止 "leave-one-family-out accuracy" 出现在中心节 | 改成 `AUC $0.95$ (95% CI $0.73$–$0.99$, Hanley–McNeil logit)`，删掉或标注 Mann–Whitney p 为描述性，**把 SAC 3/10 写进去**（它是 marker 不跨 family 迁移的最强证据），并把 fresh pair 并入语料重算一次 AUC 而不是单独分析 |
| **STAT-07** | `sec6_third_party_case_study.tex:135-137` | 全文 grep `bonferroni|holm|FDR|multiple compar|multiplicity` **0 命中**。检验族很大（53 个 paired run 各带 positivity 检验 + 6 个精确配对检验 + 2 Spearman + 1 MW/AUC，外加 contract/horizon/guard/radius/anchor/budget/shape/family/domain/scope/endpoint 的扫描）。"locked" 用了 20+ 次却**全文未定义**——没有文档名、没有版本、没有日期。真正的辩护材料存在（`carr_victim_experiment/protocol.md:3` "locked 2026-08-14 (before any experiment run)" + 13 个带日期的修订块），但只读 PDF 的审稿人看不到 | §6 开头加 "Statistical analysis and pre-registration" 段：写明协议锁定日期、修订块机制、artifact 带 SHA-256、**明说不做多重比较校正及理由**（每个检验是带预声明规则的 per-run 描述性对比，无 claim 依赖单个阈值跨越，battery 全量报告含负面判决 PPO 1/10、SAC 3/10）。并在 §5 首次使用处定义 "locked" |
| **STAT-08 / CLM-04** | `sec6_third_party_case_study.tex:34-37` | **三个阈值只披露了一个的时序**。附录承认 0.06/0.09 band 是看了 46 行之后定的；但 (a) +0.15/p<0.01 的 positivity 规则首见于 `protocol.md` v1.5（2026-08-16），而 v1.4（08-15）**已经报了后来成为 Table 2 前两行的结果**；(b) 53-run 2×2 用的 clean-violation 0.5 切分在 `protocol.md:486-488` 里被描述为"检验既有 2×2 claim"，即读自更早的行 | 把 band-chronology 段扩成覆盖全部三个阈值、带日期：明说 Table 2 那三对是被一条**后于它们**的规则标注的，而其余 50 个 run 是前瞻标注的。**主动全披露比只披露一个更好看** |
| **STAT-09** | `sec4_evaluation.tex:30-31` | "two-sided exact paired" **没有命名任何检验**，同一措辞带了 6 个 p 值；软件/版本全文缺失（artifact 里有：Python 3.10.12 / NumPy 1.26.4 / SciPy 1.12.0）；第三方检验的"配对"定义（按 episode index 配对，`n = min(len(tc), len(tp))`）读者无从知晓；p = 9.537e-7 印到四位有效数字 | 在 §6 开头加一段 *Statistical analysis*：命名 exact McNemar（$\pi=1/2$ 的精确二项，`scipy.stats.binomtest`，无连续性校正）、给出两个研究里"一对"的定义、Wilson 区间、bootstrap 细节、软件版本、"$p$ 报两位有效数字并在 $10^{-4}$ 截断" |
| **CLM-16** | `sec4_evaluation.tex:27-33` | V3 的 p 值把**调参用的 development run 2070** 和两个前瞻 run 混在一起，2070 贡献 23 个失败中的 11 个 | 同句给出 prospective-only 拆分，或明说 V3 是探索性、V4 是确证性 |

### 4.4 声明范围与内部矛盾

| ID | 位置 | 问题 | 解决方案 |
|---|---|---|---|
| **CLM-02** | `sec4_evaluation.tex:84-87` | Table 3 前两块每行都标 Clean/Poisoned，**第三块全部去掉了限定词**，`Permanent raw release 19/71` 读起来像无条件或 clean 情形。核对 `cartpole_multiseed_release_contract_rows.csv`：三行全部是 poisoned 条件 | 第三块三行都加 "Poisoned"，块标题改 "Independent audit, poisoned snapshots only"；V4/V3 块的 "Resident predictive authority" 也加 "Poisoned"；caption 加一句"resident 臂只在 poisoned snapshot 上评估，未跑 clean resident 臂" |
| **CLM-03** | `sec1_introduction.tex:120-123` | 贡献 2 的状语 "without an adversary" 管辖整条，但其后每一个分离都是**在攻击下**测的（resident 0/120 是 poisoned；one-step 14/71 是 poisoned；commit admission 只出现在 poisoned 结果里；horizon sweep 明写 "holding attack … fixed"） | 拆成两句：无对抗只覆盖 2/120，其余明确置于 "under bounded reward-record poisoning" |
| **CLM-05** | `sec1_introduction.tex:128-132` | 贡献 4 的冒号让 disagreement marker 成为"across systems, learners, integrity controls, and deployment contracts"的内容。实际上 $D_{ret}$ **只在 Carr obstacle 域的 50 行上测过**，Safe-Control-Gym、任何 integrity control、§3.1 四个 contract 都没算过。Limitations 一页之后明确收回（"the marker is obstacle-scoped"）却无互指 | 把两个 claim 拆开，marker 明确限定在 third-party obstacle corpus，并指向 `\ref{sec:limits}` |
| **CLM-06 / ABS-01 / STAT-03** | `usenix_sec2027.tex:101-104` | 摘要报 3.6/1.6 **无分母、无 null、无边界**。正文三处都有（"in two of three"、"The fresh third pair was unchanged"、"PPO and SAC … without reliable success"），唯独摘要没有。另外 "with no training-time violation" 在 V3/V4 cohort 的正文里**从未给出证据**（只有 §2 把它当 shielding 的设计属性断言） | 摘要改成 `…raised violations at retirement in 2 of 3 paired runs of a published third-party lifecycle (factors 3.6 and 1.6), with the third pair unchanged and no reliable effect in the PPO or SAC pipelines.`（约 12 词代价）；training-time 那句要么在 §6.1 补上 adaptation-violation 计数（aggregate CSV 有 `all_adaptation_safe=True`），要么从摘要删掉 |
| **CLM-07** | `sec6_third_party_case_study.tex:59-63` | 排除脚注三处说不通：①理由"lacks a provenance-valid clean endpoint"与"该行现在有 clean endpoint (0.241)"字面冲突——真实原因据 `SERVER_VS_LOCAL_DIVERGENCE.md` 是新 clean 在 Linux server 生成而归档 poisoned 是本地 macOS；②**Table 2 因此是异构的**：行 1–2 本地、行 3 服务器，未披露，而论文自己坚持 host 是 material 的；③排除规则成文于 2026-08-17，晚于 08-14 的锁定协议，论文未注明日期 | 脚注扩成四点全说清（例行完整性扫描、行 1–2 已清、跨 host 配对才是排除理由、**保留它会变成 3/3 所以排除是保守方向**），Table 2 加 host 列或在 caption 说明 |
| **CLM-09 / JRG-02** | `sec6_third_party_case_study.tex:105-110, 135` | 正文只定义了**一种**投毒 scope（bootstrap-only），但 Escape 段用 "full-scope poisoning"、"the full-phase battery"，25 行后头条统计写 "Across 53 locked paired runs spanning **both scopes**"——读者从未被告知有两种 scope。`provenance-complete`（摘要邻近的 Intro 就在用）同样全文无定义 | §5 第 31 行后加两句定义 bootstrap-only / full-phase 两种 scope，并在 53-run 计数处给出拆分；`provenance-complete` 在第 33 行定义一次 |
| **CLM-08** | `sec1_introduction.tex:74-83` | 头条实验的**数值预算全文没写**。只有 "declared per-step $L_\infty$ budget"。实际 V3/V4 是 $|\delta_t|\le 2.0$，而 logged batch-mean reward 在 $[-3.27, -0.15]$，即每条编辑是均值幅度的 0.6×–13×（中位 5.1×）。"deliberately weak" 是 novelty 框架的承重词 | §6.1 补一句给出预算与 batch reward 尺度的对比，并把 "deliberately weak" 改成 "deliberately narrow in authority"（claim 是写权限范围，不是幅度） |

### 4.5 术语、可读性、图表

| ID | 位置 | 问题 | 解决方案 |
|---|---|---|---|
| **TRM-01 / TERM-01** | `sec3_methodology.tex:117-118` | **LifecycleGate 在正文里被命名一次，然后 13 页正文中再无出现**；它在附录 E/G 出现 15 次。同一个实验在正文叫 "the certificate-gated learner"/"the gate"，在附录叫 "LifecycleGate" | 统一用 LifecycleGate，并在命名处一句说明它的两个被评估实例（commit admission = 发布前应用一次；in-loop known-sign gate / benign-utility gate = 每 batch 应用），§6 里至少留一次提及 |
| **TRM-02** | `sec3_methodology.tex:89` vs `sec4_evaluation.tex:327` | "Release Gate" 命名两个无关对象，都是小节标题：§4.2 指参数空间半空间系统，§6.6 "Sizing a Release Gate" 实际在 size **horizon 和 guard margin** | §6.6 改名 "Sizing the Retained Check"，相应改 :348-349 和 :373 |
| **TRM-03** | `sec6_third_party_case_study.tex:95-97` | "**The same** contrast attack" 是 "contrast" 一词在全文的**首次出现**。同时 Intro 造的名字 "shield-retirement poisoning" 之后**全文再未使用**。同一对象另有 5 个别名。而两个研究实际用的是**不同规则**（Safe-Control-Gym 的 tanh target-shaping vs Carr 的加性 contrast） | 定一个伞名（建议 "bounded reward-record poisoning"），在各自首次出现处定义 "contrast" 和 "target-shaping" 两个实例 |
| **JRG-01** | `sec4_evaluation.tex:21-25,74,79` | **V3/V4 是内部实验版本号**，却承担 §6.1 的组织和 Table 3 的行组标题；全文唯一解释埋在 Table 3 的 caption（渲染在**首次使用的后一页**）。同段还暴露 seed 2070 / runs 2071-2072 / run indices 2040-2042 / pools 8040-8042 五个无意义五位整数 | 换成读者可懂的名字（"the sequential audit" / "the confirmation audit"，或 "72-pair development cohort" / "120-pair confirmation cohort"）。⚠️ **此改动会打断 `test_tdsc_submission_artifacts.py:261,265,279` 三条 claim-lock，需同一 commit 更新** |
| **ACR-01 / TAB-01** | `sec4_evaluation.tex:140-141, 67` | **SOCP** 首次使用在 p.9，首次展开在 p.18（附录 D）。**LQR** 首次使用在 **Table 3 的 caption**（p.9），全文唯一展开在 p.23（附录 G），且正文从未在正文散文里说过 Safe-Control-Gym 的可信基线是 LQR。**PID** 从未展开。**KPI** 只在 :33-34 拼写全称但未给缩写 | 在正文首次使用处展开（`a second-order cone program (SOCP) witness`、`the trusted linear-quadratic regulator (LQR) baseline`），并把基线在 §6.1 散文里点名一次 |
| **FIG-01** | `sec1_introduction.tex:32-53` | **Figure 1 不是图**：`\fbox` + minipage 的居中正文 + `$\rightarrow$` 箭头 + 手调 `\hspace{3.0em}`。400 dpi 下换行是坏的（"candidate" 单独居中成一行像独立节点），"↑ trusted baseline" 箭头指向空处，caption 承诺的 trust boundary 没画出来，**而且完全没有画出 authority transition**——没有时间轴、没有前后、没有 retirement 事件。label 字面写着 `fig:lifecycle-placeholder` | 换成真正的矢量图（TikZ 或 PDF）：一条时间轴左到右——(1) 屏蔽 bootstrap（raw policy 在虚线 runtime-assurance plane 里，shield 在策略与执行器之间，攻击者 bounded-write 箭头只进入另一个阴影 learning-data plane 的 reward record）→ (2) release check 作为一个 gate 图元，标注 "finite 5-step check, horizon τ_train, authority = shield" → (3) 竖虚线标 "shield retired" → (4) 释放后的 raw execution，shield 消失，同一份证据 E 被一条灰色 "reused" 箭头带过来，horizon 标 "τ_deploy ≫ τ_train"，在 reused 箭头上用红叉标出变了的两个前提（authority、horizon）。单栏宽、≤1.8in 高，label 改 `fig:authority-transition` |
| **FIG-02** | `appendix_thirdparty.tex:114-126` | **Figure 7 标题被截断**：300 dpi 裁切读出 `Headroom is bounded by clean divergence (Spearman -0.547, p = 3.9e - 05, n =` —— 句子停在 "n ="，样本量缺失，括号未闭合。另有点标注互相压成一团、legend 画在数据区内穿过 band 注记、最小字号约 4.7 pt | 重新生成：缩短 suptitle 并用 `bbox_inches='tight'`，把 Spearman/p 移进 LaTeX caption；删掉 per-point run-index 文字标注；legend 移出坐标区；最小字号 ≥ 8 |
| **FIG-03** | `appendix_thirdparty.tex:36-50` | **Figure 5 的图内标题印着 "REAL v1.5 data"**——内部 pipeline 版本号。同标题写 "paired seeds 101-110"，与 caption 刻意使用的 "run indices" 和论文用一整段辩护的 seed≠replicate 立场**直接冲突**。决策规则注记压在柱子上，且写作 ".15 pp"（百分点）而坐标轴是 0–1 分数 | 重生成：删 "REAL v1.5 data"，"paired seeds" 改 "paired run indices"，注记移出坐标区或删除（caption 已经写了规则），单位统一 |
| **FIG-04** | `appendix_thirdparty.tex:79-89` | Figure 6 面板 (b) 的 legend 画在坐标区内，直接压住 seed-1 柱组和 "76%" 数据标签；suptitle 含内部串 "paired within locked code version vA" | 两个面板共用一个 legend 放在下方；删 suptitle 里的内部串 |
| **FIG-05** | 同上两图 | 缩放后最小字号 **4.6 pt**（`fig6_ppo_isolation` 自然宽 648 bp 被要求成 430 pt；`fig7_dose_response` 756 bp → 504 pt；两图内容流各有 ~20 个 `/F1 7 Tf`）。正文 10 pt、caption 9 pt | 按目标宽度重新设 figsize 生成（而不是缩放），rcParams 字号保证最终 ≥ 7 pt |
| **FIG-06** | `sec6_third_party_case_study.tex:82-91` | 承担摘要 3.6/1.6 的 Figure 2：只有面板 (a) 有 y 轴标签，(b) 画的是**另一个量**（disagreement）却裸轴；(b) 量程 0–25% 而 (a)(c) 0–80%+ 无提示，导致 (b) 的 11.31% 柱看起来比 (c) 的 23.6% 高；柱值标签粘连成 "24.1%24.2%"；x 轴刻度写 "local s1 / local s2 / fresh s3"，而 "local"/"fresh" 在 caption 和正文里**都不存在**，Table 2 叫 "configured seed 1/2/3" | 补 (b)(c) 的 y 轴标签；柱值标签错开或删除；刻度改 "run 1 / run 2 / run 3 (fresh)"；caption 补 n 和量程说明 |
| **FIG-07** | `sec4_evaluation.tex:284-293` | Figure 4 面板 (a) 严重标注碰撞（"Poisoned commit" 被灰色误差棒和引线划穿、"Always-freeze" 半个掉出画框、"Permanent shield" 引线穿过别的标签）；面板 (b) 只编码 3 个数。**而它画的每个数字都已在前两段散文里给出、并在附录 Table 10 里精确列出**——正文恰好卡在 13 页，这是最不值当的 float | 移到 Appendix I 挨着 Table 10，腾出的 ~1/3 页给 FIG-01 的真图。若留在正文：legend 移出坐标区、删面板 (b)、caption 补 n=24 |
| **HYG-01 / PDF-01** | `sec4_evaluation.tex:286` | pdfTeX 把每个 `\includegraphics` 的源文件名嵌进 PDF：`/PTEX.FileName (./figures//tdsc_security_availability_frontier.pdf)` —— **TDSC = IEEE Transactions on Dependable and Secure Computing**。同一图的两个面板标题还渲染出字面双连字符 "(a) Security--performance" | 把该文件改名为 `fig4_frontier.pdf` 并更新引用，重新生成时面板标题用 en dash；最终上传前 `qpdf --deterministic-id --linearize` 或设 `SOURCE_DATE_EPOCH`。验证：`strings usenix_sec2027.pdf | grep -i tdsc` 必须为空 `【我已验证：当前确实泄漏】` |
| **DUP-01(format)** | `results/tdsc_artifact_checksums.csv:23` 等 | artifact checksum 清单里含 `ndss_submission_status.md`、`tdsc_internal_scientific_review.md`、`tdsc_evidence_map.md` 等；仓库另有 `paper_latex/bare_conf_compsoc.pdf`——同一工作的完整 IEEE-compsoc build，标题 "Protected While Learning, Unsafe When Released: Reward Poisoning Across Runtime-Assurance Contracts"，构建于 2026-07-31。正文对 prior/parallel version **零披露** | ①从 artifact 包里移除所有 `ndss_*.md` / `tdsc_*review*.md` / `bare_conf_compsoc.*` / `IEEEtran.*`，重生成 checksum；②确认该 IEEE 版本从未投稿或已完全撤回；若在审，按 CFP 在 §7 加一句第三人称说明并把非匿名引用邮件给 `sec27chairs@usenix.org` |
| **FMT-01** | `usenix_sec2027.tex:46-58` | `\textfloatsep` 20→10pt、`\floatsep`/`\intextsep` 12→8pt、`\abovedisplayskip`/`\belowdisplayskip` 10→5pt。正文 10 个 float + 9 个 display ≈ 回收 190pt ≈ 0.3 栏。而 p.13 两栏**都到 713.2/720pt，零余量**——撤销就会溢到 14 页 | CFP："Any attempts to remove whitespace … are forbidden and may result in rejection." 建议删掉 46-58 行（保留 35-44 的 float 计数与 `\topfraction`，那是放置策略不是空白压缩），从**内容**里省页：Table 5 或 Table 6 移入附录、压缩 §6.7（与 §8.1 Limitations 重复） |
| **DUP-01(lang)** | 多处 | 附录与正文的 9-gram 重叠扫描出 12 段 ≥9 词重复，最长 35 词（`appendix_thirdparty.tex:109-112` vs §5），另有多处整句逐字重复（`appendix_boundaries.tex:29-30` vs `sec4:359-360` 等），3 个图 caption 重复陈述同一 positivity 规则 | 让每个附录严格增量：删掉重复句，只保留正文没有的数字（0.196789、7.993864、4.598004、0.8208、2.61e-11 N 等）；positivity 规则只在 Fig.5 caption 定义一次 |
| **ETH-01** | `sec7_ethics_usenix.tex:20-22,35-36` | stakeholder 列表**漏掉了论文实际作用于的那一组**：被 instrument 并被报告为易感的第三方 artifact 的作者（正文点名 Carr et al. 八次）。而"无需 CVD"的论证前提（不是厂商产品）虽然为真但**答非所问**——审稿人问的是"发表前是否告知了被攻击 artifact 的作者" | stakeholder 句加上第三方 artifact 作者；把 35-36 行换成具体行动陈述（是否通知、是否共享了 instrumentation patch）。若没通知，就明说并用一句话说明理由，**不要留白** |
| **LANG-01** | `appendix_influence.tex:19-22,36-38` | 两段里 6 个未定义指代："the old premises"、"the new formulation"、"the old global gradient-clipping exclusion"、"the original exact-support audit"、"the earlier singularity criterion"、"the revised solver"。这些是作者自己分析的**内部开发史标签**，读者从未见过"早先版本" | 给两个 formulation 命名一次并只用这两个名字（"direct zonotope formulation" vs "homogenized second-order-cone formulation of Theorem 3"），或者删掉开发史句子只留当前结果 + 边界（6/20 和 22/36 vs 27/36），正文 `sec4:143-144` 同步 |

---

## 5. P2 —— 打磨项（按类分组）

### 5.1 语言与格式一致性

| ID | 类型 | 事实 | 修法 |
|---|---|---|---|
| TENSE-01 | 时态 | `sec4:27-43` 相邻两段用**同样的句型报同一个实验**，一段现在时（"pairs **pass**"、"**incurs** 0/72"）一段过去时（"pairs **passed**"、"**incurred** 0/120"） | 统一：已完成观测用过去时，只有表格/图/artifact 做什么用现在时。这五处均不受 claim-lock 约束 |
| TENSE-02 | 时态 | 4 处**句内**时态冲突：`sec4:361-363`（过去/过去/**现在**/过去）、`:267-268`、`:127-130`、`:99-101` | 同上。⚠️ `improves no paired rollout over freeze` 被 `test_tdsc_submission_artifacts.py:188` 钉住，改成 `improved` 需同 commit 更新该断言 |
| GRAM-01 | 悬垂修饰 | `sec4:193-199` 是全文最长句（62 词），开头分词短语没有逻辑主语——主句主语是 "poisoning"，字面上是"投毒替换了 baseline、投毒保留了 Monte Carlo return" | 拆两句并给出显式施事："We replaced … / Poisoning then caused 40/126 …" |
| PUNC-01 | 标点 | `sec3_threat_model.tex:105-109`：display 以逗号结尾，下一行以大写 "The" 起新句 → 逗号粘连。全文 9 个正文 display 只此一处有问题 | 逗号改句号，下句改 "Here the *subject* $s$ is …" |
| REF-01 | 交叉引用 | `Fig.~\ref` 用了 7 次、`Figure~\ref` 用了 1 次（`sec4:108`），而且**指的是同一张图**（`sec4:347` 用 `Fig.~`） | `sec4:108` 改 `Fig.~` |
| NUM-01 | 数字格式 | 三个头条计数两种写法并存：摘要/Intro 用 "2 of 120"、Table/结论用 "2/120"、§6 又混入散文计数 | 统一 "X/Y"（表格和 generated/*.tex 已是这个约定），per-run 拆分保留散文形式 |
| NUM-02 | 数字/单位 | 同句内数学模式与文本模式混用（`$1.000/0$` 挨着 `0.90`）；`3.6 and 1.6` 在摘要/Intro 是文本、在 §5/§9 是数学；单位空格 `0.026 ms` vs `8.49--9.32\,s`；六行之内 "all **11** positive" 与 "**eleven** of 18" | 裸小数一律文本模式；单位一律 `\,`；数字一律阿拉伯数字 |
| SLASH-01 | 记号重载 | `sec6:20-23` "shield retained **0/0** violations during/after training, smooth **326/675**, sudden **3277/3784**, and no-shield **3798/3784**" —— 全文别处 "X/Y" 都是"X 中的 Y"，这里静默切换成"训练中/训练后"。在主流读法下 "3798/3784" 算术上不可能 | 展开成散文："Violations during and after training were 0 and 0 with the shield retained, 326 and 675 under smooth removal, …" |
| MATH-01 | 数学排版 | `appendix_proofs.tex:29-33` 同样的逗号+大写粘连；`appendix_lift.tex:143-158` 两个 aligned display 无终止标点而同文件另 12 个有 | 定一条 house rule 后统一扫 |
| MATH-02 | 数学排版 | `\newtheorem{corollary}` 声明了但**从未使用**；30 个 numbered display 只有 7 个带 label，其中 3 个 label 从未被引用；`\eqref` 有 "Equation~\eqref" 和裸 `\eqref` 两种风格，且在相邻两句里同时出现 | 删 corollary 声明；未被引用的编号式改 `equation*`；`\eqref` 统一裸用 |
| XREF-01 | 交叉引用 | `sec8_appendix.tex:1-3` 同一节挂**两个 label**（`sec:appendix-coverage` 和 `sec:coverage-appendix`），且两个都被引用 | 删 `sec:coverage-appendix`，把 `appendix_lift.tex:96` 改指前者 |
| STR-01 | 结构 | **三种互不一致的 run-in 标题机制**并存且渲染不同：`\paragraph{}`（只在 §5，5 次）、`\emph{}`（§3/§6/§8/附录 E，16 次）、`\textbf{}`（只在 §7，4 次） | 统一 `\emph{}`（数量最多且不额外吃竖直空间） |
| STR-02 | 分类学 | §3 声明"四个 contract"并承诺 §6 测其 tradeoff，但 Table 3 只报**三个**（commit admission 静默缺席，后来在 Table 4 出现）；同时 always-freeze、permanent shield、official MPSC、in-loop known-sign gate 四个机制**未经宣告**陆续入场，读者到 p.12 要对着 p.3 的四项清单追踪七个机制 | §3 加一句区分 contract 与 comparison baseline；Table 3 补 commit admission 行或在 caption 指明它在哪测 |
| PAR-01 | 段落 | `sec4:353-375` 是**一个 27 行的段落**，装了四个互不相关的审计（anchor / PPO / benign bias / coverage）和 11 个数字，只有一句 "A fourth audit…" 在段中做过渡 | 拆成四个 `\emph{}` run-in 段，与附录 E 已有的四个标题对齐（零版面代价） |
| BAL-01 | 版面配比 | 实测页占比：§1 10.9%、§2 7.0%、§3 **14.0%**、§4 9.2%、§5 10.7%、§6 **33.8%**、§7 8.0%、§8 **4.9%**、§9 1.4%。§3 比 §8+§9 加起来还大；§8 里真正的 Discussion 只有约 0.3 页 | 从 §3 收回约半页（§3.6 与 §2.3 重复的度量清单可以合并，§3.5 的 TPR/FPR 数字 Table 5 已有）给 §8，用来写 operator-facing 结论：在什么 recomputation 假设下选哪个 contract |
| RDR-01 | 阅读负担 | §6 在 4.27 页里要求读者同时持有：6 个 cohort、12 个不同分母、7+ 个机制、3 个系统、外加未定义的 V3/V4，且**没有任何 legend** | §6 开头加一个 3 列 cohort legend 表（名称/规模/它变化的是什么），约 1/4 栏，配合 JRG-01 的重命名 |
| JRG-03 | 内部黑话 | `appendix_lift.tex:132` 的 "**The P3 anchor audit**" 是 "P3" 在全文的**唯一出现**，读者无从解析（且暗示还有 P1、P2） | 改成 "The trusted-state-anchor audit of Appendix~\ref{sec:appendix-boundaries}"；`sec6:154` 的 "50 disjoint namespaces" 改 "50 runs in the locked corpus"；`sec4:58-59` 删掉 pool 整数 |
| TRM-04 | 术语 | 同一张表里同一个 run 叫两个名字：列头 "configured seed"、脚注 "run-index-3"、图 2 caption 又是第三种。而 §5 的核心防御动作恰恰是"seed 不是 replicate" | 标识符一律用 "run index"；"fix-check record" 换成读者可懂的说法 |
| TRM-05 | 术语 | "authority" 带 9 种修饰语，其中 5 种指同一件事（action / runtime / protective / resident / physical authority），而 "resident authority" 与机制名 "resident predictive authority" **碰撞** | 收敛到三个：property 用 "action authority"、机制名永远写全 "resident predictive authority"、访问控制义用 "write authority"。**标题不动** |
| ACR-02 | 缩写 | MPSC / TPR/FPR / SAC **各展开两次**，且 MPSC 两次的连字符写法不同（p.11 "model predictive" vs p.12 "model-predictive"），两次在对开页上 | 保留阅读顺序上最早的一次，删后面的括注 |
| ACR-03 | 术语 | "**Storm**" 用了两次，**无展开、无解释、bib 里没有条目**（grep 确认）。"headroom" 作为技术词用了 3 次也从未定义 | 改成 "a belief-support shield synthesized with the Storm probabilistic model checker~\cite{…}" 并补 bib；"headroom" 在首次出现处一句话定义 |
| CLM-12 | 记号 | 产生所有头条数字的攻击规则**只在一处写下**（`sec4:21-25`），而它的三个符号 $\epsilon_t, \mu^\star_t, \mu_t$ **全文别处都不出现**；更糟的是 $\epsilon$ 在附录 C 绑定到另一个量（reward box 界） | 就地展开每个符号的含义并给出 $|\delta_t|\le 2.0$；把 gain 从 $\epsilon$ 改名以避开冲突 |
| CLM-13 | 记号碰撞 | $h$ 在第 1 式是传感器输出映射、第 2 式是 attacked history（相隔九行），附录里又是液位；$a$ 是 FDI 信号 / evidence tuple 的 authority / 半空间法向；$b$、$B$、$\delta$ 同样多义（$\delta$ 在 §5 是界、在附录 C 是扰动本身，**方向相反**）；$F$ 和 $\theta^+$ 首次使用在 `sec3_threat_model.tex:23`，定义分别在 §4.1 和附录 A；"always-freeze" 用了 8 次**从未定义** | 输出映射改 $g$；附录 C 半空间改 $(c,d)$、score 矩阵 $B$ 改 $\Phi$、barrier 改 $\mathcal B$；附录 C 的扰动改用 $\xi$ 以对齐 §5；§2 加一张单栏 notation 表可以一次吸收大部分 |
| CLM-14 | 由构造成立 | `sec6:106-110` 的 escape condition："retained shield 在三对 run 里 violations 全零"——Carr 的 shield 是 winning-region mask，**这是构造保证的，不是测量结果**，协议文件自己写了 | 改写成非平凡版本："零违规由 mask 保证；审计新增的是 bootstrap 投毒从未把 agent 逼进 mask 无安全动作的状态，因此 resident authority 保持 available 而不只是 sound" |
| STR-04 | 浮动体 | 附录 G 正文在 pp.20-24，但它的**四张图渲染在附录结束之后**（Fig.10/11 在 p.25 的附录 H 里、Fig.12 在 p.26、Fig.13 独占 p.27） | `[t]` 改 `[tbp]`/`[!htbp]`，或把 Fig.10+11 合成一张双栏图减少排队 |
| FIG-08/09 | 图 | `fig:mechanism`（Fig.7）**全文只被引用一次**，还是在 14 页之前的 §5；它所在的附录小节只提 Fig.8。同时读者在 p.7 先遇到 "Fig. 8" 再遇到 "Fig. 7" | 在 `appendix_thirdparty.tex:114` 前加一个小节和一句本地锚定；把两个 figure 环境对调顺序使编号与首次引用顺序一致 |
| TAB-02 | 排版 | Table 2 的脚注继承了 `\centering`，整个五行脚注**居中排版**，看起来像排版事故；而这恰是全文最敏感的一段文字（数据排除说明） | 用 `\begin{minipage}{\columnwidth}\raggedright\footnotesize …\end{minipage}` 包住 |
| TAB-03 | 排版 | 所有窄 `p{}` 列都是两端对齐，产生巨大词间距；37 个 Underfull 里有 **21 个**来自这些单元格 | 加 `array` 宏包并定义 `\newcolumntype{L}[1]{>{\raggedright\arraybackslash}p{#1}}`，把窄 `p{}` 换成 `L{}`（Underfull 会从 37 降到约 16） |
| TAB-04 | 浮动体 | Table 4 声明为 `table*` 但只用了 7.00in 中的约 5.25in，两边各空 0.9in；Table 10 同病。而 `table*` 强制占满跨栏带 —— 在零余量的 13 页里这是直接损失 | Table 4 改单栏 `table` + `\footnotesize`，去掉恒为 3 的 "Learner seeds" 列，System 列改成 `\multicolumn` 组标题（Table 3 已用这个模式） |
| TAB-05 | 表完整性 | Table 4 的 "Mean reward" **无单位、无归一化、无定义、无离散度**；"Violations" 的分母只能从上一页散文里反推；"Learner seeds" 列恒为 3 | caption 补一句说明分母关系与 reward 定义，并指向 Table 10 的 bootstrap 区间 |
| HYG-02 | PDF | 12 个 **Type 3 位图字体**，来自 9 个 matplotlib 图（3 个图是干净的，说明只是导出设置不一致）；图内文字不可搜索、不可复制、缩放呈位图。且所有图用 DejaVuSans 而正文是 Times | 重生成时设 `rcParams['pdf.fonttype']=42`（顺带 `font.family='serif'` 对齐正文）。验证 `pdffonts usenix_sec2027.pdf | grep 'Type 3'` 为空 |
| HYG-03 | artifact 卫生 | `figures/` 21 个文件只有 12 个被引用；未用的包括 `fig5_disagreement_curves.pdf`（就挨着论文的核心 disagreement 论点）、`safe_control_gym_paper_quick_summary.pdf`、`..._quick2_...`、`..._delayed_trigger_...`，外加 4 个过时 PNG 副本 | 打包前删除或移到有文档说明的 `figures/unused/` |
| APP-01 | 自足性 | 三处正文不自足：guard-margin 结论无数字（`sec4:371-373`）、§6.7 以 "Appendix E gives the full figures" 收尾、§6 开头把 filtering-vs-admission 分离整体推给附录 G | 各补一到两句具体数字；版面从 FMT-01 要求的内容裁剪里出 |
| TYP-01 | 排版 | `sec5_related_work.tex:20` 的 46 字符粗体 run-in 标题后接 10 字符的 "Konighofer"，一行放不下，产生全文**唯一一个正文级 Underfull**，渲染成整行拉伸 | 缩短为 "Shield retirement and attacked states." |
| ETH-02 | 套话 | Ethics 附录最后一句 "We follow the USENIX Security ethics guidelines and the principles of the Menlo Report" 是**全节唯一可以原封不动贴进任何论文的句子**，而且在终止位置 | 换成两条框架真正驱动的具体决定（beneficence → 报告规则形式与预算但不发布攻击生成脚本；respect for law and public interest → 被攻击方是研究 artifact 作者而非厂商，因此按此处理披露） |
| ETH-03 | 可读性 | Open Science 的枚举是**全文最长的句子（59 词）**；紧接一句是 garden-path：`Automated checks in the artifact audit table provenance…` 会先被读成名词短语 "the artifact audit table" | 在 (ii) 后断句；把动词前置改写 |
| TITLE-01 | 标题 | ①冒号两侧 "Runtime"/"Authority" 各出现两次，副标题几乎不增信息；②"Evidence Reuse" 在保障案例/认证实践里是**褒义**（DO-178C 的证据复用是工程目标），扫会议列表的读者可能读成"论文提出的技术"；③无 "shield"/"safe RL"/"poisoning"/"safety filter"/"retirement" 任一检索词，论文自己造的 "shield-retirement poisoning" 也不在；④"release **test**" 只出现在标题和结论各一次，正文一律 "release **check**"（5 次） | ⚠️ **标题在 2026-08-18 注册时已固定**。先做能做的：统一 "release check"/"release test" 之一（或首次出现处给个 gloss）；缺失的检索词前置到摘要前 25 词。若还能与 chairs 协商副标题：(a) `A Release Test Is Not Runtime Authority: Shield-Retirement Poisoning in Learning-Enabled Control`（保留已注册主句，最可能被接受）；(b) `Spent Evidence: Release Tests Do Not Transfer When Runtime Assurance Retires`；(c) `Trained Behind a Shield, Released Without One: …`（注：文件注释显示近似变体已被弃用） |
| HORIZON-01 | 结论表述 | 所谓"可用区间的上界"不是安全失效而是**可用性代价 + 测量局限**：horizon 20 admit 49/72 且**零失败**——这是观测到的最安全配置，却被描述成 "failed"。底层数据是单调的（horizon 越长 lead 越多、admission 越少），这正是 MPSC/shielding 文献里熟知的保守性权衡 | 改写成单调描述：安全随 horizon 上升、admission 随 horizon 下降；下界由 baseline 恢复 lead time 定，上界由 operator 的 admission 预算定；明说 horizon 20 是安全的、被排除只是因为没剩下失败可分离。贡献 2 从 "locating the lookahead" 软化为 "giving an attack-independent procedure for sizing the lookahead" |
| VENUE-01 | 场地 | 正反两面：**支持 USENIX** —— 有威胁模型、对手、信任边界、防御、ethics 附录，且有可接受的 CPS-security 血统（BADControl, USENIX Sec '26）；**反对** —— 真正扛得住审视的部分（release test ≠ runtime authority；从恢复动力学定 lookahead）是保障工程结论，**根本不需要对手**，在 EMSOFT/ICCPS/RV/HSCC 会被当作扎实贡献接收 | 二选一并彻底承诺。走 USENIX 必须同时修好 SEC-01（做出受约束仍有害的自适应攻击者）和 THR-03（点名一个真实存在该通道的系统）。这一轮做不到，就围绕 contract/horizon 结果重构、把攻击者降为次要节，投 ICCPS/EMSOFT/RV |

### 5.2 AI 写作痕迹（量化）

| 模式 | 计数 | 密度 | 最严重位置 | 建议 |
|---|---|---|---|---|
| 对比框架 `rather than`(19) / `whereas`(10) / `instead (of)`(4) / 同位 `, not `(10) / `not…but`(1) | **44** | 0.50 / 100 词，且**向结尾单调上升**（背景 0.16 → 摘要 1.02 → 结论 0.65） | `sec4:100-107` 八行内三个；`sec4_evaluation.tex` 单文件 9 个 `rather than` | 砍掉约一半，改成正面陈述。⚠️ 两个被 claim-lock 钉住不能动：`sec4:379` "sampled finite-horizon certificates, not continuous-state invariant-set proofs"（`test_…:189`） |
| 平行句骨架重复 | **10 句连续** | — | `sec3_threat_model.tex:109-129`：5 句 "The *TERM* $sym$ VERB OBJECT."，紧接 5 句 "NP does not VERB NP (*TERM*)." | 保留五分量映射（承重），但至少打破其中 3 句的骨架。这是全文**最强的机器写作信号**，而且正好落在核心抽象的定义处 |
| 格言式段首 | **34** 处 ≤13 词的独立宣告 | Intro **7 段全部**如此 | "The gap is measurable without an adversary." / "The attacker we evaluate is deliberately weak." / "Existing mechanisms address neighboring problems." | 只保留 2–4 条最强的（建议留 `sec6_conclusion.tex:4` 和 `sec1:18`），其余改成以内容开头的主题句 |
| 摘要↔Intro 同义词替换 | 3 组 | — | "The gap **does not require** an adversary" vs "The gap **is measurable without** an adversary"；"the **same** prediction" vs "the **identical** prediction"；"An upstream **attacker amplifies**" vs "An upstream **adversary widens**"。摘要**同一句内**还在 attacker/adversary 之间切换 | 定一个术语账本（attacker 21 次 vs adversary 6 次 → 统一 attacker；"the same" 而非 "identical"；"widens" 而非 "amplifies"），并让 Intro 那段**做与摘要不同的工作**而不是复述 |
| 结构性元句 | **11** | — | `sec4:92-93` 是一个独立成段的单句，全部内容只是指向紧挨其上的表；"makes X explicit" 重复两次 | `sec4:92-93` 直接删除，把引用挂到上一段末尾；`sec3_methodology.tex:4` 和 `sec6:4` 的开场公告换成实际内容 |
| 句首单调 | 356 句中 75 句(21%) 以 "The" 开头；冠词开头合计 28% | — | Limitations 四个 run-in 标题**全部**是 "The + NP + be/have"；`sec2:76,80,84,89` 连续四句 "Under *X*," | 改掉 Limitations 里两个标题、`sec2` 的第三句；目标：任何位置不超过连续两句同首词 |
| 长句 | 91/346 (26%) >30 词；27 句 (8%) >40 词 | — | **结论最糟**：5 句里 3 句 >30 词、2 句 >40 词（48 词 + 42 词）。最长 62 词在 `sec4:193-199` | 拆结论那两句（结论是审稿人打分前读的最后一段） |
| 装饰性枚举 | 43 个 ≥3 项并列 | — | `sec2:99-104` 与 `sec3:180-184` 是两份**近乎重复的度量清单**（"update fraction"/"accepted update fraction" 等）；信任边界被**三种不同方式**枚举了三遍（Intro 7 项、§3.3 9 项、Table 1 6 行）且**三个集合不相同** | 让 Table 1 成为写边界的唯一权威陈述，两处散文清单改成指针 |
| 附录模板化开场 | 9 个文件里 5 个用同一句型 | — | "This appendix expands/reports/states … summarized in …"，其中两个动词都相同；而 `appendix_proofs.tex` 和 `sec8_appendix.tex` **完全没有开场**，模板半应用 | 改成陈述"本附录增加了什么"而不是"正文说过什么"，并给缺开场的两个补上 |
| 收尾免责句鼓点 | 7 段同型 "X does not establish Y" | — | `appendix_lift.tex:96-97`、`appendix_influence.tex:40-41`、`appendix_boundaries.tex:22,29-30,38`、`sec8_appendix.tex:36-37`、`appendix_benchmarks.tex:218-219` | **全部保留**（这是承重的科学卫生），但把其中 3–4 句改成不同句法 |
| 附录时态漂移 | `appendix_benchmarks.tex` 内 "used…used…**uses**"，各节开场过去/现在混用 | — | :11/:62/:117/:148 过去 vs :156/:180 现在 | 统一过去时 |

**AI 写作总判**：**词汇层面异常干净，句法层面有明显机器节奏。**
零 `Moreover/Furthermore/Notably/Importantly/It is worth noting/delve/leverage/underscore/comprehensive/seamless`；
零 `conclusively/unprecedented/state-of-the-art/significantly` 类夸张词；
em dash 密度仅 0.07/100 词且基本都是成对同位语（合理使用）；
无缩写形式、无反问句；拼写一律美式无混用；`which/that` 全部 18 处正确；`only` 26 处全部位置正确；
复合修饰语连字符**零冲突**。这些都不像典型 LLM 输出。

真正的信号集中在**结构层**：§3.4 的 10 句模板、Intro 七段格言式开头、摘要与 Intro 的同义词替换、
11 个元句、44 个对比框架且密度向结尾上升、5 个雷同的附录开场。
按优先级修 §3.4 → Intro 段首 → 摘要/Intro 去重 → 元句 → 对比框架减半，即可把最强的四个信号消掉。

---

## 6. 已通过、不必再查的部分

- **模板完整性**：`usenix.sty` 与官方 Sec '27 模板 zip **字节一致**；documentclass 一致；无任何 geometry/字号/行距覆盖；无负 `\vspace`。
- **版心与字体实测**：612×792pt、7.03in×8.99in 文本块、baseline 11.96pt、10pt Times (NimbusRomNo9L)。
- **稿件本身的匿名性**：`\author{}` 空、无致谢/基金、全 `.tex`/`.bib` 无 github/gitlab/zenodo/路径/用户名/邮箱/机构；
  PDF `/Info` 全空、无 XMP；对 PDF 每个流做 zlib 解压后搜 `feihm`/`llm-fei`/`/home/`/`ndss` **零命中**；
  17 个图文件 `pdfinfo` 只有 matplotlib 的 Creator/Producer。（唯一例外是 `/PTEX.FileName` 的 tdsc，见 HYG-01。）
- **构建健康**：0 Overfull；37 Underfull 中 36 个在 8–9pt 窄表列或折行的 12pt 标题里，逐页核对**无可见缺陷**；
  无 undefined/multiply-defined label、无 undefined citation、无 "??"、无 "Float too large"。
- **交叉引用完整**：23 个 float label 全部至少被引用一次；A–I 每个附录都被正文引用；每张附录图都被引用过一次。
- **算术自洽**（logic agent 复算）：V4 poisoned 5+4+7+2+9=27、clean 2+0+0+0+0=2；V3 11+5+7=23、0+0+2=2；
  独立审计 6/24+3/23+10/24=19/71 且 24+23+24=71；horizon 72−57=15、72−49=23；
  第三方 0.777/0.216=3.60、0.763/0.484=1.58；
  语料划分 11 低带阳性（REINFORCE 7 + PPO 1 + SAC 3）+ 第二环境 1 = 53-run 交叉表的 12，18+32=50，20+33=53。
- **每个精确配对 p 值都是其 discordance 计数的正确双侧符号检验值**：
  2·0.5²¹=9.537e-7、2·0.5²⁵=5.960e-8、2·0.5³⁷=1.455e-11、2·0.5⁶⁸=6.776e-21、2·0.5³⁸=7.3e-12、2·0.5³⁹=3.6e-12。
- **正文数字与 `generated/*.tex` 一致**（抽验四张生成表；唯一发现的偏差见下面"未完成"一节）。
- **Theorem 2（margin-robust lift）、Proposition 3、Proposition 5、Theorem 3 的证明都真正 discharge 了各自陈述**；
  Theorem 2 的 cover 前提被诚实声明为未验证。
- **反空洞证书控制到位**：`sec8_appendix.tex` 预锁的 1728 对 CasADi–PyBullet 混淆审计，
  堵住了"你只在自己 gate 放行的状态上报零违规"这个标准反驳。
- **负面结果没有被藏**：PPO 1/10、SAC 3/10（3 protective / 4 unchanged）、7 个 ceiling realization、
  fresh 非阳性对、失败的 PPO 停止规则、benign-utility 停止判据、trusted recomputation 100% 拦截 —— 全在正文或附录里。
- **claim-lock 测试本身是防过度声明的**：`test_tdsc_submission_artifacts.py:227-247` 断言
  "two of the three provenance-complete pairs" 在场，且旧的更强措辞 "on all three seeds"/"on 3/3 paired seeds" 不得出现。
- **第三方协议是真的预注册**：`carr_victim_experiment/protocol.md:3` "locked 2026-08-14 (before any experiment run)"，
  13 个修订块全部带日期（08-14 至 08-17），含 "Locked before execution; no ad hoc expansion after results" 条款。
- **参考文献没有幻觉迹象**：18 个 URL 全部 HTTP 200；三条 2025/2026 高风险条目与出版页逐字核对相符。
- **HotCRP 自动格式检查会通过**；ML-work 附加要求（威胁模型四要素）满足。
- **图 3（horizon contract）和附录图 9 是全文做得最好的图**：形状+线型+颜色三重编码，灰度与色觉障碍下都可读，legend 在坐标区外——**可以直接当其他图的模板**。

---

## 7. 建议的修改顺序

### 第 0 优先（**8-25/8-28 截止，过期不可补**，纯工程，无需实验）
1. **建匿名 artifact 仓库并把 URL 写进 PDF** —— OSCI-01。必须在 8-25 定稿前完成，因为投稿后 PDF 不能改。
2. **artifact 全面去标识** —— ANON-01。manifest 路径 / CSV 绝对路径 / shell 脚本 / **不带 `.git`** / 打包后 grep 验零命中 / 重生成 checksum。
3. **移除 prior-venue 残留** —— DUP-01。`ndss_*.md`、`tdsc_*review*.md`、`bare_conf_compsoc.*`、`IEEEtran.*` 不进 artifact；
   图改名消掉 PDF 里的 `/PTEX.FileName … tdsc …`；确认 IEEE 版本从未投稿或已撤回。
4. **投稿时 topic 选 Cyber-physical systems security**（不要选 Security of ML）。
5. 撤销 FMT-01 的空白压缩，从内容里省页（Table 5/6 移附录、压缩 §6.7）。

### 第 1 优先（写作层，无需新实验，约 1–2 天）
6. 摘要重写：加分母与边界（CLM-06/STAT-03）、标清 cohort 与条件（CLM-01 选项②）、给 Könighofer 归属（NOV-01/CLM-15）、拆长句。
7. Table 3 重新标注（CLM-02）；贡献 2 与 4 收窄范围（CLM-03/CLM-05）。
8. 加 "Statistical analysis and pre-registration" 段（STAT-07/STAT-09）；
   全文 p 值截断在 $10^{-4}$、改报效应量+区间（STAT-01/STAT-11）；
   头条比例补 Wilson 区间（STAT-05）；AUC 补 CI 并写进 SAC 3/10（STAT-06）；
   主动报出 clean 对比的 p=0.50（STAT-04）；三个阈值时序全披露（STAT-08）。
9. Proposition 1 二选一处理（PROP-01）；Theorem 1 的定义移出证明（PRF-02）；
   补 `\label` 修 "the two inequalities above"（PRF-03）；Prop 5 证明搬进附录 C（PRF-04）。
10. 术语账本一次性收敛（TRM-01/02/03/05、JRG-01/02/03、ACR-01/02/03、CLM-12/13）。
    ⚠️ JRG-01 与 TENSE-02 会打断 `test_tdsc_submission_artifacts.py:188,261,265,279`，**同 commit 更新**。
11. AI 写作四项：§3.4 的 10 句模板、Intro 段首格言、摘要/Intro 去重、11 个元句。
12. §6 加 cohort legend 表（RDR-01）；`sec4:353-375` 拆四段（PAR-01）。
13. 图表：Fig.1 换真图（FIG-01）、Fig.7 标题截断（FIG-02）、Fig.5 删 "REAL v1.5 data"（FIG-03）、
    Fig.6 legend（FIG-04）、字号（FIG-05）、Fig.2 轴标与灰度（FIG-06/FIG-01-format）、
    Type 3 字体（HYG-02）、`\eqref` 与表格 raggedright（MATH-02/TAB-03）。

### 第 2 优先（**需要新实验**，决定这一轮投不投）
14. **补跑 clean resident predictive authority 臂**（120 对）—— CLM-01。这是最便宜也最必要的一条。
15. **clean-vs-clean null battery**（≥10 对）—— CONF-01。没有它，第三方章节挡不住"这是方差不是攻击"。
16. **语料级双边记账 + 符号/置换检验**（53 个 paired delta）—— EFF-01。
17. **受约束自适应攻击者**（sign/envelope/moment/recomputation 作为显式约束，跑全部 5 个 V4 run）—— SEC-01。
    **这一条决定它是不是一篇安全论文。**
18. **benign 场景下在线学习优于 always-freeze 的证据** —— UTIL-01。做不到就在 §8 明说并去掉 utility 框架。
19. adversary-free cohort（≥20 独立训练 run）估计 clean rate —— EVID-01。

### 战略判断
若 14–18 在本 cycle 做不完，务实的选择是 **VENUE-01 的第二条路**：
围绕 contract/horizon 结果重构，把攻击者降为动机性次要节，投 ICCPS / EMSOFT / RV。
在那些场地，Proposition 1 作为 definition、2/120 的 clean gap、以及"从 backup 恢复动力学给 lookahead 定尺寸"
各自都是可发表的，而缺一个强对手不构成缺陷。

---

## 8. 未完成 / 需要补跑的审查

1. **维度 3 `numeric-consistency` 未产出**。agent 完成了分析（transcript 最后一句："I have completed the
   exhaustive cross-check"）但在结构化输出前被中止。缓解：`logic-overclaim` 的 CLEAN CHECKS 已覆盖
   V3/V4 算术、全部精确 p 值的重算、horizon sweep、第三方倍数、语料划分的相互对账。
   **我自己另外抓到一条它们都没报的**：
   - `sec4_evaluation.tex:305` 写 "against **0.026** ms for raw snapshot evaluation"，
     而 `generated/tdsc_frontier_results.tex` 里 Clean REINFORCE 和 Poisoned raw 的延迟都是 **0.027**（0.026 是 commit/freeze）。
     图 4 caption 的 "overlap near 0.026 ms" 因为有 "near" 尚可辩护，但正文那句是直接不符。`【我已验证】`
2. **维度 6 `citations` 未产出**。Part A 的机械检查（cited vs defined key、log 警告、计数）已做完，
   Part B（缺失相关工作）在核对 Hsu et al. 时被中止。已知的部分结论在 `usenix-format` 的 clean check 里：
   18 个 URL 全 200、三条高风险条目核实无误。**仍未回答的问题**：
   - 42 条参考文献里有几条来自 USENIX Security / S&P / CCS / NDSS？（PC 会问为什么不引近三年顶会安全工作）
   - **safety case / assurance case 的 change-impact analysis 文献缺失**——论文的核心思想
     （部署契约改变时证据不转移）与 DO-178C/ARP4754 变更影响分析、UL 4600、ISO 21448 SOTIF、
     dynamic assurance case 高度重合，一条都没引。这可能是最大的相关工作缺口。
   - RL/CPS 后门攻击线（TrojDRL、BACKDOORL 等）只引了 BADControl。
   - safety filter / shielding 综述（Wabersich et al.、Brunke et al.）。
3. **Verify 阶段完全没跑**。上面 124 条都是单 agent 结论，未经对抗性核验。
   经验上这类审查有 15–25% 会被验证阶段判为 REFUTED（多数是"论文其实在下一段/脚注/Limitations 里已经处理了"）。
   **建议至少对 P0 的 8 条和 CLM-01 单独复核**——CLM-01 尤其依赖 agent 对 CSV 的读取。
4. **Completeness critic 未跑**，所以"整轮审查漏了什么"这个问题没有答案。

---

# 附录：执行结果（2026-08-19 第二轮）

## A. 已跑的新实验 / 新分析

| 问题 | 做法 | 结果 | 产物 |
|---|---|---|---|
| **CLM-01** clean resident 臂从未跑过 | 新写 `safe_control_gym_cartpole_v4_clean_resident_arm.py`，复用 training CSV 里记录的 clean snapshot 参数与同一批 120 个配对状态，不重训、不动任何已锁定产物 | **clean resident predictive authority = 0/120 violations，2 次 forward switch（step 7 和 6），对应 raw-release 失败在 step 11 和 10，两次都提前 4 步** | `results/cartpole_v4_clean_resident_arm_rollouts.csv`、`..._summary.csv` |
| 上一条的 harness 自校验 | 同脚本 `--snapshot fixed_target_tanh` 重放 poisoned 臂 | **复现已锁定的 27 switches / 0 violations**，逐项一致 | 同上 |
| **EFF-01** 语料只报阳性 | 新写 `carr_victim_experiment/analyze_two_sided_and_null.py` 做双边记账 | 54 个 contrast 配对：**14 positive / 19 protective / 21 unchanged**，双边符号检验 **p=0.33**；分家族均值 REINFORCE +0.128、SAC +0.034、**PPO −0.139**；分层后 sub-ceiling 21 个里 14 阳性，ceiling 33 个里 **0 阳性** | `carr_victim_experiment/results/two_sided_accounting.csv` |
| **CONF-01** 无 null battery | 同脚本：clean run 在两种 scope 标签下是同配置的独立复制，构成真正的 clean-vs-clean 对 | 21 对；**同代码版本 11 对里 1 对越过 0.15 阈值（\|Δ\|=0.540），中位 \|Δ\|=0.007**；跨版本 10 对里 3 对越过 | `carr_victim_experiment/results/clean_clean_null.csv` |

三条结论都已写进正文并加了 claim-lock（`test_clean_resident_arm_and_two_sided_corpus_are_reported`）。

## B. 已改的投稿/格式问题

- FMT-01：删掉 `\textfloatsep`/`\floatsep`/display-skip 的空白压缩（CFP 明令禁止），改从**内容**省页。
- FMT-02：删掉 bibliography 的 `\footnotesize`。
- HYG-01/PDF-01：`tdsc_security_availability_frontier.pdf` → `fig4_frontier.pdf`，同步改生成脚本；**PDF 里 `tdsc` 归零**。
- DUP-01：删掉 `bare_conf_compsoc.*`（IEEE 版完整 build）与未被引用的 `IEEEtran.cls`；`ndss_submission_status.md` 移出 artifact 清单。
- ANON-01：`generate_tdsc_reproducibility_manifest.py` 的解释器改 `python3`（原为 `/home/feihm/llm-fei/.llm/bin/python`）；`aggregate_table_v2.csv` 的 115 条绝对路径改 repo-relative；`server_scripts/*.sh` 的 `/home/feihm` 改 `${ARTIFACT_ROOT}`/`${CONDA_ROOT}`。**manifest 中 home 路径归零**。
- TAB-03：加 `array` 宏包与 raggedright 的 `L{}` 列，Underfull 从 37 降到 0。
- XREF-01 / MATH-02 / ACR-01 / ACR-02 / REF-01 / TAB-01：重复 label、未用的 `corollary`、SOCP/LQR/PID/KPI 首次展开、MPSC/TPR/SAC 重复展开、`Figure~`→`Fig.~` 全部修正。
- 版面：Fig.4（unified frontier）、Table 5（reward integrity）、Table 6（delta 表）移入附录，§4.2/§6.2/§6.6 按审稿建议压缩。正文 13 页，0 overfull。

## C. 已改的科学表述问题

- **CLM-01/CLM-02**：Table 3 每行标注 snapshot 条件，新增 clean resident 行；摘要/§1/§6/§9 全部改成正确的同臂对比。
- **STAT-04**：主动报出 clean 对比的 `p=0.50`。
- **STAT-02**：删掉 "sharper"，明说 $D_{\mathrm{ret}}$ 与 clean violation 近共线，排除结果等价于 ceiling effect。
- **STAT-06**：AUC 改 `0.95 (95% CI 0.73–0.99)`，并把此前被 claim-lock 禁止出现的 **SAC leave-one-family-out 3/10** 写进正文。
- **STAT-08 / CLM-04**：正文写明 bands 是 post hoc（46/50 行），附录补全三个阈值的完整时序。
- **CLM-06**：摘要补上 "two of three… the third unchanged"。
- **CLM-07**：Table 2 脚注补齐排除的四点事实，含 host 差异与"保留会变成 3/3"。
- **CLM-09/JRG-02**：定义 bootstrap-only / full-phase 两种 scope 与 provenance-complete。
- **THR-02**：Table 1 增加 read-access 列，正文与 Limitations 明说攻击者需要读 learner state。
- **CLM-14**：retained-shield 的零违规改写成"由 mask 构造保证"，并给出真正非平凡的结论。
- **PROP-01/PRF-01/PRF-02/PRF-03**：补 sound lifecycle certificate 的定义（移出证明）、修正证明里"conclusion is not preserved"这个假全称、给 halfspace 式加 label 修掉悬空指代、贡献 1 从 "show" 改 "derive obligations"。
- **B1/B2/B3**（相关工作缺口）：新增 assurance-case change-impact 段（Kelly & McDermid 2001、Denney et al. 2015）、backdoor-on-safe-RL 段（Jiang et al. TCAD 2024，并加进对比表）、safety-filter 综述（Brunke et al. 2022）。**四条文献均由我逐条网络核实过**；未核实的一律没加。
- **F2**：`0.026 ms` → `0.027 ms`（与 generated 表一致）。

## D. AI 写作处置（量化前后对比）

| 指标 | 改前 | 改后 |
|---|---|---|
| 破折号 `---` | 11（6 处散文 + 5 处表格） | **0** |
| adversary/attacker 混用 | 6 / 21 | **0 / 26**（统一 attacker） |
| 对比框架密度 | 0.50 / 100 词 | **0.42 / 100 词**；`rather than` 19 → **8** |
| §3.4 连续同骨架句 | 10 句 | 改写为两种句式 |
| Intro 格言式段首 | 7/7 段 | 3 段 |
| 结构性元句 "makes X explicit" | 2 | **0** |
| 时态混用（§6.1 相邻两段） | 有 | 统一为过去时 |
| 悬垂修饰（62 词长句） | 1 | 拆为两句，补显式施事 |
| display 后逗号+大写 | 2 | 0 |
| 附录开场模板句 | 5 处雷同 | 改写 |
| 空洞连接词 / 夸张词 | 0 | 0（本来就干净） |

## E. 仍未解决，需要你决定

| 问题 | 为什么没做 | 需要什么 |
|---|---|---|
| **SEC-01** 攻击被一行 sign 检查关掉 | 需要把 sign/envelope/moment/recomputation 作为**显式约束**写进投毒优化，在全部 5 个 V4 run 上跑。这是新方法+新实验，且结果可能是"不存在这样的攻击" | 你的决定：做，还是改成把"该通道可关闭"当正面结论重构论文 |
| **UTIL-01** 每个配置里 freeze 都优于学习 | 现有 benign 标定只扫了 0.0005–0.004 N，选中的 0.003 N 的 reward loss 仅 0.0152，12 个 batch 的学习率追不回来。需要设计更大/漂移的扰动 + 重新标定 + 多 seed | 你的决定：设计新 benign 场景，还是在 §8 明说"所研究部署无已证明的适应收益" |
| **EVID-01** clean rate 只有 n=2 且集中在 1 个 run | 需要 ≥20 个独立训练 run 的 adversary-free cohort。技术上可行（约 30–60 min），但要开新 seed namespace 并写新协议 | 你说跑，我就跑 |
| **NOV-01** 与 Könighofer 的 delta | 摘要已加归属（"That shielded policies are fragile… is known; we show…"），但真正的解法是做一个 Könighofer 设置做不出来的测量 | 你的判断 |
| Fig.1 仍是 `\fbox` 文字框 | 需要画一张真正的 TikZ 时间轴图（授权转移 + 证据复用箭头 + 变了的两个前提） | 我可以画，需要你确认要不要改 |
| 6 张附录图仍是 Type 3 位图字体 | 修需要重跑 `generate_benchmark_artifacts.py` 等实验生成器，有改动已锁定数值的风险 | 建议单独一次谨慎处理 |
| Open Science 链接 | 你说你自己更新 | — |
| `tdsc_*.md` 协议文档仍在 artifact 里 | 它们是论文依赖的预注册记录，删掉会削弱可复现性；只是文件名带 "tdsc" | 建议重命名而非删除，需要你确认 |
