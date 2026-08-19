> ⚠️ **场地与引用已过时（2026-08-19 标注）。** 本文件提及的 NDSS 与
> `ndss_submission_status.md` / `research_state.md` 均为历史；当前场地是 USENIX Security 2027。
> **当前权威状态请读 [`../usenix_direction_audit_0819.md`](../usenix_direction_audit_0819.md)。**
> 本目录的 `protocol.md`、`patches.md`、`SERVER_VS_LOCAL_DIVERGENCE.md` 与 `results/` 不过时。

# Carr et al. AAAI'23 victim experiment — reward poisoning across shield retirement

Third-party workflow demonstration for the USENIX Security paper's security claim
("assurance evidence's validity across an authority transition", see repo
`../usenix_direction_audit_0819.md`). Uses the *official* code of

> Carr, Jansen, Junges, Topcu, "Safe Reinforcement Learning via Shielding under
> Partial Observability", AAAI 2023 (DOI 10.1609/aaai.v37i12.26723)
> code: github.com/stevencarrau/safe_RL_POMDPs (Zenodo DOI 10.5281/zenodo.7320140)
> environments: github.com/stevencarrau/shield_rl_gridworlds

## Layout
- `protocol.md` — locked experiment protocol (before any run): lifecycle, attack
  plane, budgets, metrics, fidelity gate, stop rules, amendments v1.1–v1.5.
- `patches.md` — every deviation from upstream, with rationale.
- `RESULTS_ANALYSIS_AND_NEXT_STEPS.md` — 结果梳理 + 下一步规划（2026-08-16）：
  证据链 E0–E4、数据复核、数据卫生问题、服务器任务优先序、预注册纪律。
- `upstream/safe_RL_POMDPs/cfgs/` — official configurations at upstream commit
  `b01dbe8b40e2167bdc1d93dea7b43e96f1a835ee`.
- `upstream/carr_reward_poisoning.patch` — complete executable delta against that
  commit. It modifies `model_simulator.py` and `rl_simulator.py` and adds the
  actual `run_carr_victim.py` driver used by the reported experiments.
- `server_scripts/` — parameterized run and launch scripts. Set `ARTIFACT_ROOT`
  to the directory containing the patched checkout and `CONDA_ROOT` to the
  Conda installation root.
- `smoke_stormpy.py` — native-layer smoke (POMDP build, winning region, risk flags).
- `check_api_compat.py` — tf-agents API compatibility check.
- Analysis and figure scripts in this directory generate the result tables and
  figures; Python source is part of the reproducibility artifact.
- `results/` — per-run dirs with `*_summary.json` (provenance + metrics),
  `*_eval_trace.npy` (per-episode eval violations), G0 CSV (reward curves);
  `aggregate_table.csv` (full-phase vA) 与 `aggregate_table_v2.csv` (vA+vC 合并基座)。

## Data provenance & versioning (重要，2026-08-16)
- **代码版本**：vA = 无 at-retirement/disagreement 仪器化的早期全相位版；vC = 加
  仪器化 + 独立 belief tracker（amendment v1.4）后的当前版。**跨版本绝对值不可混用**；
  进论文前 vA full-phase 数字需用 vC 复核（protocol v1.4）。
- **run dirs 覆盖警告**：`results/obstacle_sudden_REINFORCE_v3_d2_s{1,2,3}` 目录**现存放
  shield-on（vC）隔离数据**（`poison_scope=shield-on`，含 at_retirement_stats）；
  这三个目录最初是 full-phase vA 运行，其 full-phase 数字只留存于
  `aggregate_table.csv` / `aggregate_table_v2.csv`（version=vA 行）。不要把这几个目录
  误读为 full-phase 原始数据。同样地，clean 基线目录
  `results/obstacle_sudden_REINFORCE_none_d2_s{1,2,3}` 也被 vC 仪器化版重跑覆盖，目录现
  为 vC 数据（含 at_retirement_stats），vA clean 数字（during=3277/1015/1981）只留存于
  汇总表。另有两个 smoke 运行（`obstacle_shield_REINFORCE_none_d2_s1_smoke`、
  `obstacle_sudden_REINFORCE_v3_d2_s2_smoke`）未保留独立目录，仅存于汇总表（runs=200 行）。
- **汇总表**：`results/aggregate_table_v2.csv` 是 paper-ready 合并基座 —— vA full-phase
  (24 行) + vC (7 行：clean 基线重跑 4 + shield-on 隔离 3)，repo 相对路径 +
  `version`/`scope`/`at_ret_*` 列，smoke 行（runs=200）已标注。
- **运行纪律**：新实验必须用**新目录名 / 新 seed 命名空间**，禁止覆盖已有 run dirs。

## Rebuild the instrumented upstream checkout

```sh
git clone https://github.com/stevencarrau/safe_RL_POMDPs.git safe_RL_POMDPs_patched
git -C safe_RL_POMDPs_patched checkout b01dbe8b40e2167bdc1d93dea7b43e96f1a835ee
git -C safe_RL_POMDPs_patched apply ../carr_victim_experiment/upstream/carr_reward_poisoning.patch
```

The patch is reviewable without executing TensorFlow or Storm and exposes the
exact shield-retirement switch, reward mutation, independent belief trackers,
at-retirement evaluation, and run provenance.  The original runs used Python
3.10.12, TensorFlow 2.15.1, TensorFlow Probability 0.23.0, TF-Agents 0.19.0,
stormpy 1.11.3, and NumPy 1.26.4.  See `server_scripts/` for the exact commands.

## Headline protocol (see protocol.md for the full text)
1. Train REINFORCE behind the Storm belief-support shield (obstacle N=6, 5000
   episodes, ≤100 steps; goal +1000, trap -1100, step +1).
2. Shield retired after episode 1000 (sudden HARD or smooth SOFT decay) or kept.
3. Attack: bounded reward-record mutation ONLY (`|ξ| ≤ δ`, δ=2.0) on the training
   env's reward log; eval and all other planes untouched. V1 constant bias,
   V2 risk-seeking (+δ on risk-adjacent records), V3 contrast (±δ).
4. Metrics: violations during training; violations after across 5000 eval episodes;
   time-to-first-violation; shield-disagreement fraction.
5. Fidelity gate: clean baseline must reproduce paper Tab. 1 ordering
   (shield 0/0 < smooth ≪ sudden < no-shield) before any poisoned run is reported.

## Headline results (2026-08-17, obstacle/REINFORCE/sudden, paired runs)
Fidelity gate passed (paper Tab. 1 ordering reproduced). V3 contrast poisoning
(full-phase) is effective in some low-clean-violation training realizations;
V1 bias / V2 risk are negative controls. In the provenance-complete P0 causal
isolation set (`poison_scope=shield-on`, at-retirement eval/freeze), two of
three paired runs show a 1.6–3.6× higher raw-policy violation rate at the
authority transition. The complete fresh configured-seed-3 pair is unchanged
(0.241→0.242) despite low clean disagreement. One positive effect persists
after 4000 fully clean post-retirement episodes. Physical violations remain
zero during shielded execution. PPO isolation is positive in 1/10 paired runs,
and SAC isolation is positive in 3/10 low-disagreement paired runs; these
batteries establish conditional rather than seed- or learner-wide
exploitability.
