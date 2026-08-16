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
  天花板效应（ceiling），按锁定规则"报告全部 10 seeds"。**关键观察项**：
  `v3_d2_s201`（clean=0.24 的唯一 transfer-sensitive seed）的 poisoned run 尚未完成。
  若其 @ret ≥ 0.39 且 p<0.01 → 1/10 positive，恰好验证 heterogeneity 故事（effect
  集中在 low-clean-at-ret 的 seed），但不足以升级 3/3 → K/10。
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

## 4. v16 确认结果（2026-08-16 08:40，18/20 落地，s201 poisoned 已回）

**v16（REINFORCE 10-seed 隔离，服务器，s201-210，v1.6）判定 = 1/10 positive**
- 唯一 transfer-sensitive seed **s201（clean @ret 0.240）→ poisoned @ret 0.533**，
  effect +0.293 ≥ +0.15，paired McNemar p=8.25e-39 → **POSITIVE**（at-ret trace 复核）。
- 其余 9 seeds clean @ret 全部落在 0.72–0.755 天花板，无 headroom：7 无效应、
  s203（0.744→0.208, p=6e-113）与 s208（0.733→0.528, p=9e-21）为**保护性**（poisoned 更低）。
- **2×2 跨平台一致性**（本机 vC 3 + 服务器 v16 8-10）：
  - clean@ret<0.5（transfer-sensitive）：**4/4 positive**（本机 s1,s2,s3 + 服务器 s201）
  - clean@ret≥0.5（ceiling）：**0/7 positive**（无额外伤害，个别保护性）
  - → heterogeneity 机制（effect 集中在 clean 可转移安全性的 seed、天花板 seed 饱和）在
    两个平台一致，但 v16 作为 10-seed 升级证据不成立（K=1 < 7 升级阈值，且 9/10 被
    天花板混淆）。
- **论文动作**：保持本机 vC 3/3 数字；可在 learner-boundary / attack-budget 段加
  heterogeneity 句（vC Spearman -1.0 + 服务器 s201 0.24→0.53 数据点 + 天花板诚实句）。
  不做 "3/3 → K/10" 升级。
