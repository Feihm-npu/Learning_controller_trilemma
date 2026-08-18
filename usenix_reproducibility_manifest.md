# USENIX Security 2027 research-track reproducibility manifest

> Locked 2026-08-03. Run all commands from the project root. The resident-versus-release hard gate and its prerequisite smokes are included; the benign-utility development smoke is retained as negative evidence.

## Environment

| Component | Version | Source |
|---|---|---|
| manifest_lock_date | `2026-08-03` | `reviewer_uplift_experiment_protocol.md` |
| python | `3.10.12 (main, Nov 20 2023, 15:14:05) [GCC 11.4.0]` | `/home/feihm/llm-fei/.llm/bin/python3` |
| platform | `Linux-5.15.0-1101-nvidia-x86_64-with-glibc2.35` | `platform.platform()` |
| safe-control-gym_git | `6b5391d014f36fdfa0f9d22d92c77387e5274308` | `external/safe-control-gym` |
| latexmk | `Latexmk, John Collins, 20 November 2021. Version 4.76` | `PATH` |
| pdfTeX | `pdfTeX 3.141592653-2.6-1.40.22 (TeX Live 2022/dev/Debian)` | `PATH` |
| safe-control-gym | `unavailable` | `importlib.metadata` |
| numpy | `1.26.4` | `importlib.metadata` |
| scipy | `1.12.0` | `importlib.metadata` |
| casadi | `unavailable` | `importlib.metadata` |
| torch | `2.9.0` | `importlib.metadata` |
| gymnasium | `unavailable` | `importlib.metadata` |
| pybullet | `unavailable` | `importlib.metadata` |
| matplotlib | `3.10.1` | `importlib.metadata` |
| pandas | `2.2.3` | `importlib.metadata` |
| pytest | `8.3.4` | `importlib.metadata` |

The online latency values in the paper are single-process host wall-clock measurements, not worst-case execution-time guarantees.

## Seed registry

| Purpose | Seeds | Separation/status |
|---|---|---|
| Primary learner seeds | `2040, 2041, 2042` | cartpole and quadrotor |
| Primary evaluation seeds | `3040, 3041, 3042` | held-out physical states |
| Commit certificate seeds | `7040, 7041, 7042` | learner seed + 5000 |
| P1 coverage-state seeds | `4050, 4051, 4052` | 144 unadmitted states |
| P2 candidate-state seeds | `5050, 5051, 5052` | common paired frontier |
| P3 deployment-state seeds | `6050, 6051, 6052` | new paired states |
| Release-contract evaluation seeds | `8040, 8041, 8042` | disjoint states for learner seeds 2040--2042 |
| Prospective exact-support development seed | `2060; evaluation 9060` | failed stop rule; diagnostic reuse only |
| Reserved prospective confirmation seeds | `2061, 2062; evaluation 9061, 9062` | not run |
| V3 fixed-target learner seeds | `2070, 2071, 2072` | development 2070, then locked confirmation 2071--2072 |
| V3 fixed-target evaluation seeds | `9070, 9071, 9072` | disjoint paired state pools |
| V4 untouched fixed-target learner seeds | `2100, 2101, 2102, 2103, 2104` | one-shot extension; detector frozen before opening |
| V4 untouched fixed-target evaluation seeds | `9100, 9101, 9102, 9103, 9104` | disjoint paired state pools |
| Stealth temporal-reward development reuse | `2070/9070 only` | S1 and S2 stopped for zero raw-release effect |
| Stealth temporal-reward confirmation seeds | `none` | namespace not opened after burned-seed stop |
| PPO B-lite development seed | `2040` | formal sweep not run |
| Benign-utility development seeds | `2039; evaluation 3039` | smoke only |
| Benign-utility reserved formal seeds | `2050--2052; evaluation 3050--3052` | not run after smoke stop |
| U1 second-family (A2C) learner seeds | `2200; confirmation 2201, 2202` | canary 2200, then locked confirmation 2201--2202 |
| U2 joint-channel (obs-FDI + reward-log) seeds | `2210; confirmation 2211, 2212` | locked rho grid 0.005/0.02/0.04 |
| U3 in-loop reward-defense seeds | `2220; confirmation 2221, 2222` | frozen known-sign in-loop batch gate |

## Exact commands

### Expository artifacts

```sh
/home/feihm/llm-fei/.llm/bin/python generate_benchmark_artifacts.py
```

### Cartpole confirmatory learner audit

```sh
/home/feihm/llm-fei/.llm/bin/python safe_control_gym_reinforce_reward_poisoning_sweep.py
```

### Quadrotor confirmatory learner audit

```sh
/home/feihm/llm-fei/.llm/bin/python safe_control_gym_quadrotor_reinforce_reward_poisoning_sweep.py
```

### Official PPO baseline and constructed target diagnostic

```sh
/home/feihm/llm-fei/.llm/bin/python safe_control_gym_quadrotor_ppo_baseline.py --include-target
```

### Locked PPO B-lite checkpoints

```sh
/home/feihm/llm-fei/.llm/bin/python safe_control_gym_quadrotor_ppo_reward_poisoning.py --batches 24 --checkpoint-batches 16 24 --training-state-count 8 --deployment-rollouts 24 --summary-out results/safe_control_gym_quadrotor_ppo_b_lite_summary.csv --rollouts-out results/safe_control_gym_quadrotor_ppo_b_lite_rollouts.csv --traces-out results/safe_control_gym_quadrotor_ppo_b_lite_traces.csv --gate-out results/safe_control_gym_quadrotor_ppo_b_lite_gate.csv
```

### Locked benign-utility calibration and smoke

```sh
/home/feihm/llm-fei/.llm/bin/python safe_control_gym_quadrotor_benign_utility.py --mode all
```

### P1 certificate-coverage audit

```sh
/home/feihm/llm-fei/.llm/bin/python safe_control_gym_quadrotor_certificate_coverage.py
```

### P2 common-state security-availability frontier

```sh
/home/feihm/llm-fei/.llm/bin/python safe_control_gym_quadrotor_security_availability_frontier.py
```

### P2 table and figure derivation

```sh
/home/feihm/llm-fei/.llm/bin/python generate_tdsc_frontier_artifacts.py
```

### P3 cache seed 2040, fractions 00:07

```sh
/home/feihm/llm-fei/.llm/bin/python safe_control_gym_quadrotor_trusted_anchor_audit.py --precompute-seed 2040 --fraction-start 0 --fraction-stop 7
```

### P3 cache seed 2040, fractions 07:14

```sh
/home/feihm/llm-fei/.llm/bin/python safe_control_gym_quadrotor_trusted_anchor_audit.py --precompute-seed 2040 --fraction-start 7 --fraction-stop 14
```

### P3 cache seed 2040, fractions 14:21

```sh
/home/feihm/llm-fei/.llm/bin/python safe_control_gym_quadrotor_trusted_anchor_audit.py --precompute-seed 2040 --fraction-start 14 --fraction-stop 21
```

### P3 cache seed 2041, fractions 00:07

```sh
/home/feihm/llm-fei/.llm/bin/python safe_control_gym_quadrotor_trusted_anchor_audit.py --precompute-seed 2041 --fraction-start 0 --fraction-stop 7
```

### P3 cache seed 2041, fractions 07:14

```sh
/home/feihm/llm-fei/.llm/bin/python safe_control_gym_quadrotor_trusted_anchor_audit.py --precompute-seed 2041 --fraction-start 7 --fraction-stop 14
```

### P3 cache seed 2041, fractions 14:21

```sh
/home/feihm/llm-fei/.llm/bin/python safe_control_gym_quadrotor_trusted_anchor_audit.py --precompute-seed 2041 --fraction-start 14 --fraction-stop 21
```

### P3 cache seed 2042, fractions 00:07

```sh
/home/feihm/llm-fei/.llm/bin/python safe_control_gym_quadrotor_trusted_anchor_audit.py --precompute-seed 2042 --fraction-start 0 --fraction-stop 7
```

### P3 cache seed 2042, fractions 07:14

```sh
/home/feihm/llm-fei/.llm/bin/python safe_control_gym_quadrotor_trusted_anchor_audit.py --precompute-seed 2042 --fraction-start 7 --fraction-stop 14
```

### P3 cache seed 2042, fractions 14:21

```sh
/home/feihm/llm-fei/.llm/bin/python safe_control_gym_quadrotor_trusted_anchor_audit.py --precompute-seed 2042 --fraction-start 14 --fraction-stop 21
```

### P3 trusted-anchor audit from verified caches

```sh
/home/feihm/llm-fei/.llm/bin/python safe_control_gym_quadrotor_trusted_anchor_audit.py
```

### P3 table derivation

```sh
/home/feihm/llm-fei/.llm/bin/python generate_tdsc_anchor_artifacts.py
```

### Core and coverage table derivation

```sh
/home/feihm/llm-fei/.llm/bin/python generate_tdsc_result_table.py
```

### Cartpole one-step resident-kernel smoke

```sh
/home/feihm/llm-fei/.llm/bin/python safe_control_gym_cartpole_release_contract_smoke.py
```

### Cartpole resident predictive authority smoke

```sh
/home/feihm/llm-fei/.llm/bin/python safe_control_gym_cartpole_predictive_simplex_smoke.py
```

### Retrospective gate-aware target audit

```sh
/home/feihm/llm-fei/.llm/bin/python safe_control_gym_cartpole_certificate_evasion_smoke.py
```

### Unclipped reward-influence geometry audit

```sh
/home/feihm/llm-fei/.llm/bin/python safe_control_gym_cartpole_reward_geometry_smoke.py
```

### Three-seed resident-versus-release hard gate

```sh
/home/feihm/llm-fei/.llm/bin/python safe_control_gym_cartpole_multiseed_release_contract.py
```

### Failed prospective exact-support development smoke

```sh
/home/feihm/llm-fei/.llm/bin/python safe_control_gym_cartpole_prospective_gate_aware_attack.py
```

### Burned-seed reward-direction diagnostic

```sh
/home/feihm/llm-fei/.llm/bin/python safe_control_gym_cartpole_reward_direction_diagnostic.py
```

### Burned-seed V2 exploratory diagnostic

```sh
/home/feihm/llm-fei/.llm/bin/python safe_control_gym_cartpole_gate_aware_v2_exploration.py
```

### V3 prospective fixed-target development smoke

```sh
/home/feihm/llm-fei/.llm/bin/python safe_control_gym_cartpole_v3_fixed_target_tanh.py
```

### V3 prospective fixed-target three-seed audit

```sh
/home/feihm/llm-fei/.llm/bin/python safe_control_gym_cartpole_v3_fixed_target_tanh.py --learner-seeds 2070,2071,2072 --evaluation-seeds 9070,9071,9072 --confirmatory --output-prefix results/cartpole_v3_fixed_target_multiseed
```

### V3 successful-trajectory influence replay

```sh
/home/feihm/llm-fei/.llm/bin/python safe_control_gym_cartpole_trajectory_influence_audit.py
```

### V3 homogenized clipped-influence audit

```sh
/home/feihm/llm-fei/.llm/bin/python safe_control_gym_cartpole_clipped_influence_audit.py
```

### Burned-seed homogenized gate-aware post-stop diagnostic

```sh
/home/feihm/llm-fei/.llm/bin/python safe_control_gym_cartpole_homogenized_gate_aware_diagnostic.py
```

### V3 monitor-horizon contract sweep

```sh
/home/feihm/llm-fei/.llm/bin/python safe_control_gym_cartpole_horizon_contract_sweep.py
```

### Reward-log detector calibration before new seeds

```sh
/home/feihm/llm-fei/.llm/bin/python safe_control_gym_reward_log_detectability.py --calibrate
```

### V4 one-shot untouched five-seed confirmation (fresh artifact only)

```sh
/home/feihm/llm-fei/.llm/bin/python safe_control_gym_cartpole_v4_reviewer_confirmation.py
```

### Frozen reward-log detector evaluation

```sh
/home/feihm/llm-fei/.llm/bin/python safe_control_gym_reward_log_detectability.py --evaluate
```

### S1 sparse reward-permutation offline verification

```sh
/home/feihm/llm-fei/.llm/bin/python safe_control_gym_cartpole_sparse_reward_permutation.py --stage offline_check
```

### S1 burned-seed 2070 smoke

```sh
/home/feihm/llm-fei/.llm/bin/python safe_control_gym_cartpole_sparse_reward_permutation.py --stage s1_2070_smoke
```

### S2 moment-preserving burned-seed 2070 fallback

```sh
/home/feihm/llm-fei/.llm/bin/python safe_control_gym_cartpole_moment_preserving_reward.py --stage s2_2070_smoke
```

### Finalize stealth temporal-reward work package

```sh
/home/feihm/llm-fei/.llm/bin/python safe_control_gym_cartpole_moment_preserving_reward.py --stage finalize_wp
```

### U1 second learner family (A2C) confirmation

```sh
/home/feihm/llm-fei/.llm/bin/python safe_control_gym_cartpole_a2c_reward_poisoning.py --seeds 2200,2201,2202 --canary-seed 2200 --prefix results/cartpole_a2c_reward_poisoning_multiseed
```

### U2 joint observation-FDI + reward-log confirmation

```sh
/home/feihm/llm-fei/.llm/bin/python safe_control_gym_cartpole_joint_channel_poisoning.py --seeds 2210,2211,2212 --canary-seed 2210 --prefix results/cartpole_joint_channel_poisoning_multiseed
```

### U3 in-loop reward-integrity defense confirmation

```sh
/home/feihm/llm-fei/.llm/bin/python safe_control_gym_cartpole_inloop_defense.py --seeds 2220,2221,2222 --canary-seed 2220 --prefix results/cartpole_inloop_defense_multiseed
```

### Regression tests

```sh
pytest -q
```

### Research-track draft PDF

```sh
cd paper_latex && latexmk -pdf -interaction=nonstopmode -halt-on-error usenix_sec2027.tex
```

### Manifest and checksums (run last)

```sh
/home/feihm/llm-fei/.llm/bin/python generate_tdsc_reproducibility_manifest.py
```

## Integrity inventory

`results/tdsc_artifact_checksums.csv` contains SHA-256 digests for 267 locked source, raw-result, generated, upstream-model, figure, and submission files. `results/tdsc_environment_versions.csv` is the machine-readable environment table.

The invalid pre-clip benign calibration is intentionally retained as an audit narrative in `benign_utility_protocol.md`; it is not included as confirmatory result data.
