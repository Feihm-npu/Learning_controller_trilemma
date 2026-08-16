# 服务器 vs 本机环境分歧记录（critical, 2026-08-16）

**一句话**：服务器 conda env 与本机 venv 的 TF 栈**版本完全相同**，但同一 seed 在两端
训练出的策略**不同**（已知 TF 跨平台/跨硬件非确定性）。服务器 vC 代码的 clean
at-retirement 大多落在"不安全天花板"区间（~0.72–0.76），而本机 vC clean at-ret =
0.216/0.484/0.239。**因此服务器 fullvC/v16 结果不能直接与本机 vC 数字并表或替换论文。**

---

## 1. 环境对比（2026-08-16 实测）

| 项 | 服务器 NUSdgx（conda `carr`） | 本机 Mac（venv `venv/` per README） |
|---|---|---|
| 系统 | Linux x86-64 | macOS 14.4.1 arm64 (Apple Silicon) |
| Python | 3.11.15 | 3.10.12 |
| tensorflow | 2.15.1 | 2.15.1 |
| tf-agents | 0.19.0 | 0.19.0 |
| tensorflow-probability | 0.23.0 | 0.23.0 |
| stormpy | 1.11.3 | 1.11.3 |
| numpy | 1.26.4 | 1.26.4 |
| scipy | 1.17.1 | (vC 脚本所需) |

结论：**版本一致，硬件/平台/微小 Python 版本不同**。同一 seed 在两端不再代表同一策略。

## 2. 观测事实

### 本机 vC（论文当前 3/3 数字的来源，REINFORCE/obstacle/sudden）
| seed | clean @ret | poisoned @ret | 论文引用 |
|---|---|---|---|
| 1 | 0.216 | 0.777 | 3.6× |
| 2 | 0.484 | 0.763 | 1.6× |
| 3 | 0.239 | 0.748 | 3.1× |

### 服务器 fullvC（v1.4 full-phase, 15 runs，目前 5/15 有 summary）
| run | clean @ret | 备注 |
|---|---|---|
| none_s2 | 0.755 | 无 headroom |
| none_s3 | 0.749 | 无 headroom |
| contrast_d2_s2 | 0.755 | vs clean 0.755 → **无效应** |
| contrast_d2_s3 | 0.743 | vs clean 0.749 → **无效应** |
| risk_d2_s3 | 0.748 | 无效应 |

### 服务器 v16（REINFORCE 10-seed 隔离, 20 runs，目前 12/20 有 summary）
- clean @ret：s201=**0.24**（唯一 transfer-sensitive）、s203=0.744、s204=0.72、
  s206=0.754、s207=0.75、s208=0.733、s210=0.741
- poisoned @ret：s204=0.723、s205=0.744、s206=0.755、s207=0.749、s209=0.763
- → 除 s201 外，clean 已在 ~0.72–0.76 天花板，poisoned 无 +0.15 headroom。

## 3. 对判定规则的含义（locked rules 不变）

- **v16 fraction-only 判定**：positive = poisoned @ret ≥ clean @ret + 0.15 AND paired
  McNemar p<0.01。服务器大多无 headroom → 预期**大多 NOT positive**。这是诚实的
  天花板效应（ceiling），按锁定规则"报告全部 10 seeds"。**关键观察项（已由 §4 最终结果
  取代）**：`v3_d2_s201`（clean=0.24 的唯一 transfer-sensitive seed）的 poisoned run
  当时尚未完成；若其 @ret ≥ 0.39 且 p<0.01 → 1/10 positive。实际最终 3/10（s201/s205/s209
  全部 transfer-sensitive 阳性），恰好验证 heterogeneity 故事（effect 集中在
  low-clean-at-ret 的 seed），但不足以升级 3/3 → K/10。
- **fullvC 定性 guard**：锁定模式是 s2 clean 0.225 → poisoned 0.755（大效应）。
  服务器 s2 clean 已是 0.755（天花板）→ **零 headroom，vA→vC 数字替换无意义**。
  按 `PENDING_PAPER_INTEGRATION_WORDING.md`：定性变化 → 回 protocol 讨论，**不要**把
  fullvC/v16 数字替换进论文正文。
- **论文处理**：本机 3/3 数字（vC, 本地）保持为论文正文数字；服务器电池作为
  "更大 seed 规模 + 跨平台可复现性探索"报告，明确说明平台非确定性导致的 regime
  差异，不做 off-policy generality overclaim。

## 4. 行动项
1. 电池完成后：`bash carr_victim_experiment/sync_from_server.sh`（幂等）。
2. `analyze_fullvC.py`（已修 `num_violations` bug）/ `analyze_seed_heterogeneity.py` /
   `analyze_ppo_isolation.py` / `make_fig6.py` 在数据落地后重跑。
3. 服务器 s201 poisoned 落地后优先检查：positive? → 写入 v16 判定与 heterogeneity 句。
4. 论文改稿只按 `PENDING_PAPER_INTEGRATION_WORDING.md` 的明确情景走；默认保持本机
   vC 3/3 措辞 + ceiling/honesty 句。

---

## 4. v16 确认结果（2026-08-16 09:10，20/20 完成）

**v16（REINFORCE 10-seed 隔离，服务器，s201-210，v1.6）判定 = 3/10 PARTIAL**
- 3 个 transfer-sensitive seeds 全部 **POSITIVE**（at-ret trace 复核）：
  - **s201**：clean @ret 0.240 → poisoned 0.533（effect +0.293），paired McNemar p=8.25e-39
  - **s205**：clean @ret 0.234 → poisoned 0.744（+0.510），p=1.90e-103
  - **s209**：clean @ret 0.229 → poisoned 0.763（+0.534），p=6.83e-114
- 其余 7 seeds clean @ret 全部落在 0.72–0.755 天花板，无 headroom：5 无效应、
  s203（0.744→0.208, p=6e-113）与 s208（0.733→0.528, p=9e-21）为**保护性**（poisoned 更低）。
- Spearman(clean_atret, effect) = **−0.685（p=0.029）**，与 vC 本机 −1.0 方向一致。
- **2×2 跨平台一致性**（本机 vC 3 + 服务器 v16 10 = 13 seeds）：
  - clean@ret<0.5（transfer-sensitive）：**6/6 positive**（本机 s1,s2,s3 + 服务器 s201,s205,s209）
  - clean@ret≥0.5（ceiling）：**0/7 positive**（无额外伤害，个别保护性）
  - → heterogeneity 机制（effect 集中在 clean 可转移安全性的 seed、天花板 seed 饱和）在
    两个平台一致，但 v16 作为 10-seed 升级证据不成立（K=3 < 7 升级阈值，且 7/10 被
    天花板混淆）；按锁定规则 v1.5.4 为 **PARTIAL（3/10）**。
- **论文动作（已执行）**：保持本机 vC 3/3 数字；Reading 段已改为 "3 个
  transfer-sensitive seeds 全部复现（三组数字）+ Spearman −0.685 + 6/6 vs 0/7"。
  不做 "3/3 → K/10" 升级。

## 5. fullvC 确认结果（2026-08-16 09:10，15/15 完成）

**fullvC（v1.4 full-phase，服务器，3 seeds × 5 条件）**
- 服务器 s1 是 transfer-sensitive（clean at-ret 0.232）：
  - contrast δ=2：at-ret 0.501，after 1157→2451（p=4.63e-159）→ **复现**
  - contrast δ=10 饱和（2450）；risk 2455；constant 无效应（1177, p=0.655）
- 服务器 s2/s3 天花板（clean at-ret 0.755/0.749）：contrast δ=2 无效应（p=1）、
  δ=10 保护性（2450/2466 vs clean 3762/3720）、risk s3 无效应（p=0.982）。
- 定性模式：效应集中在 transfer-sensitive seed、天花板 seed 无 headroom —— 与论文
  本机 vA 故事一致，只是 transfer-sensitive 的 seed 号不同（本机 s2 ↔ 服务器 s1）。
- **论文动作（已执行）**：Attack budget 段跨平台注改写为完整 15-run 结果；本机 vA
  数字保持为论文正文（locked rule）。

## 6. fidelity_v2（服务器保真度电池，REINFORCE/obstacle/sudden, seed 1, vC-era FID 插桩）

**性质**：robustness 探索电池，**不进入论文正文表格**；本机论文 fidelity gate 数字
（vA 时代 3/3 复现顺序）保持不变。

### 6.1 已落地数据（2026-08-16 09:40 同步自服务器）

| 条件 | during | final eval | at-retirement | first_eval | wall(s) |
|---|---|---|---|---|---|
| noshield | 3896 | **1187 / 0.2374** | — | 0 | 2762 |
| smooth | 1223 | 2541 / 0.5082 | 0 / 0.0 | 1 | 2476 |
| sudden | 3385 | 3771 / 0.7542 | 768 / 0.768 | 1 | 1448 |
| retained | 训练中（step~4160, loss 恒定 16170） | — | — | — | — |

本机对照（论文 fidelity gate 段落引用，vA 时代 3/3 复现顺序）：
shield 0/0、smooth 326/675、sudden 3277/3784、no-shield 3798/3784。

### 6.2 Noshield 反转异常（平台特异性，不改变论文数字）

- **本机**：no-shield final 3784/5000 (0.757)，维持 `shield < smooth ≪ sudden ≤ noshield`。
- **服务器**：noshield final **0.2374**，低于 smooth (0.508) 与 sudden (0.754)，顺序反转。
- during 计数方向仍保持（noshield 3896 > sudden 3385 > smooth 1223 > shield 0），
  反转只出现在 final eval：服务器无盾 REINFORCE 在 5000 集后收敛到更安全的策略
  （23.7% 违例），本机无盾收敛到 75.7%。
- **解释**：与 v16 服务器 clean-at-ret ~0.24（s201）同族的平台异构——同一 seed 在两端
  训练出不同策略（TF 跨平台非确定性）。服务器 sudden 保持 0.75 天花板，说明
  sudden/shield 结构本身在两端一致；noshield 策略收敛点是平台敏感的。
- **结论**：保真度门"定性顺序复现"在**服务器自身**上仍成立（smooth ≪ sudden，sudden≈0.75），
  只是 noshield 收敛点不同；本机论文数字不动。若评审要求"保真度门在两端复现"，如实
  报告该平台差异即可（与 §1 结论一致：跨版本/跨平台绝对值不混用）。
- **待确认**：retained 完成后补表 + 检查 retained final 是否维持 0 违例（盾全程保留应
  ≈0）；若 retained 也异常（>0），则说明服务器 sudden 的 0.75 不是盾结构所致。
