> ⚠️ **过时的规划/形式化草稿（2026-08-19 标注）。** 早于 2026-08-19 的实验与审计。
> **当前权威状态与方向请读 [`usenix_direction_audit_0819.md`](usenix_direction_audit_0819.md)。**

# Safe-Control-Gym Mainline Experiment Plan

状态：执行中。SWaT/WaDi/iTrust 记录为 deferred track，当前不阻塞主线。

## Environment

Use the existing project Python environment:

```bash
source /home/feihm/llm-fei/.llm/bin/activate
```

Installed for this track:

- `safe-control-gym` editable from `external/safe-control-gym`
- `gymnasium`
- `casadi`
- `pybullet`
- `munch`, `dict-deep`, `scikit-optimize`

Validated smoke commands:

```bash
MPLCONFIGDIR=/tmp/matplotlib-lifecycle-gate \
/home/feihm/llm-fei/.llm/bin/python safe_control_gym_lifecycle_scaffold.py

/home/feihm/llm-fei/.llm/bin/python continuous_adaptive_attacker.py
```

Current smoke output:

- `results/safe_control_gym_smoke.csv`
- `results/safe_control_gym_controller_baselines.csv`
- `results/safe_control_gym_cbf_action_filter.csv`
- `results/safe_control_gym_continuous_observation_attack.csv`
- `results/safe_control_gym_plausible_set_lifecycle_gate.csv`
- `results/safe_control_gym_plausible_set_lifecycle_gate_casadi.csv`
- `results/safe_control_gym_freeze_frontier_casadi.csv`
- `results/safe_control_gym_freeze_frontier_casadi_highrho.csv`
- `results/safe_control_gym_paper_mini_raw.csv`
- `results/safe_control_gym_paper_mini_aggregate.csv`
- `paper_latex/figures/safe_control_gym_paper_mini_summary.pdf`

The smoke policies are only environment checks. They are not paper baselines.
The LQR, linear-MPC, and CBF rows are official Safe-Control-Gym controller/filter
adapters, but current runs are still short smoke runs rather than final paper
tables.

## Benchmark Scope

Primary benchmark sequence:

1. `cartpole` stabilization: fast iteration target for attacker/gate wiring.
2. `quadrotor_2d` stabilization: main standard control benchmark for paper evidence.
3. `quadrotor_2d` trajectory tracking: stronger follow-up if stabilization results are clean.

Deferred CPS/ICS sequence:

1. EPANET water distribution closed-loop pump/tank benchmark.
2. SWaT/WaDi/iTrust data or remote access, only after the mainline benchmark is stable.

## Strong Baseline Matrix

Required paper baselines:

| Class | Mechanism | Purpose |
|---|---|---|
| Fixed controller | LQR / iLQR | Classical stabilizing baseline |
| Optimization control | MPC / linear MPC | Strong model-based baseline |
| Safety filter | CBF / MPSC / Safety Layer | Current-action safety baseline |
| Robust learning | RARL / RAP | Adaptive adversarial training baseline |
| Freeze baseline | Always-freeze learner | Availability lower bound |
| Proposed | LifecycleGate project/reject | Update-level certificate gate |
| Oracle | Trusted-state learner | Upper bound when ambiguity is resolved |

First implementation target:

1. Done: run official LQR on cartpole and quadrotor_2d.
2. Done: run official linear MPC on cartpole and quadrotor_2d.
3. Done: run official cartpole CBF action-only filter on uncertified action policies.
4. Done: wrap LQR plus a linear residual learner with an attacked-history plausible-set action filter and LifecycleGate projection.
5. Done for official linear MPSC; Safety Layer/RARL/RAP remain next.

Current short-run baseline snapshot:

> 2026-07-22 consistency note: the earlier paper-mini rows below predate the
> universal empty-future-kernel fix and must not be cited as final results.
> The corrected smoke is in `results/safe_control_gym_lifecycle_gate_fixed_smoke.csv`.
> The first end-to-end NDSS-track result is the delayed snapshot-commit study
> in `results/safe_control_gym_delayed_trigger_summary.csv`; its poison-dose,
> held-out-state extension is in `results/safe_control_gym_delayed_trigger_sweep.csv`.

| task | controller/filter | key result |
|---|---|---|
| cartpole | LQR | 20-step smoke, zero constraint violations |
| quadrotor_2d | LQR | 20-step smoke, zero constraint violations |
| cartpole | linear-MPC | 20-step smoke, zero constraint violations |
| quadrotor_2d | linear-MPC | 20-step smoke, zero constraint violations |
| cartpole | CBF action filter | `theta_push` raw violation rate 0.867, CBF violation rate 0.033 over 30 steps |
| cartpole | continuous observation-FDI | attacked LQR violation rate 0.55, oracle-state CBF action filter violation rate 0.20 over 20 steps |
| cartpole | Euler plausible-set LifecycleGate | with `rho=0.04`, attacked LQR+residual violation rate 0.05; action-only plausible filter violation rate 0.00 but stale-certified rate 0.10; LifecycleGate violation/stale/uncertified rates 0.00 with learn update rate 0.95 over 20 steps |
| cartpole | CasADi robust LifecycleGate | with `rho=0.03`, attacked LQR+residual violation rate 0.10; action-only plausible filter violation rate 0.00 but stale-certified rate 0.40; LifecycleGate violation/stale/uncertified rates 0.00 with learn update rate 1.00 over 10 steps |
| cartpole | official CBF sampled kernel | with `rho=0.015`, action-only CBF kernel stale-certified rate 0.50; LifecycleGate stale/uncertified rates 0.00, learn update rate 0.667 over 6 steps |
| cartpole | CasADi freeze frontier | `rho=0.01 -> 0.05` increases action-only empty-kernel rate from 0.333 to 1.000; high-rho `0.06/0.08` keeps action-only empty-kernel rate 1.000 |
| cartpole | paper mini sweep | 2 seeds, CasADi robust kernel, `rho=0.03`: attacked learner violation rate 0.167; action-only filter stale-certified rate 0.333 and uncertified-learning rate 1.000; LifecycleGate stale/uncertified rates 0.000 and learn-update rate 1.000 |
| cartpole | delayed snapshot-commit attack | White-box update search selects delta `(2,-0.5)` over 12 protected adaptation steps. Action-only committed snapshot violates in 42/42 clean deployment-envelope rollouts; one-step LifecycleGate violates in 1/42; margin-aware multi-step CasADi commit LifecycleGate projects pending `(18,-5)` to nontrivial `(1.8,-0.5)` and violates in 0/42; always-freeze also has 0/42 but no update |
| cartpole | delayed poison-dose + held-out sweep | Commit certificate uses 160 deterministic/sample states, admits 150 with trusted-baseline recovery margin `0.0075`, and requires commit margin `0.005`. On disjoint seeds 2030--2032 it admits 191/192 clean states. Commit LifecycleGate has 0/191 violations at every dose while retaining 10%--35% parameter displacement; action-only rises from 1/191 at dose 8 and 6/191 at dose 9 to 191/191 at doses 10/12. The retained displacement measures update availability under attack, not beneficial learning. |
| cartpole | REINFORCE reward-log poisoning | The actor samples a Gaussian linear residual, receives real PyBullet transitions, and computes reward-to-go REINFORCE gradients; the attacker changes only logged rewards with `L_inf <= 2.0`. Across learner seeds 2040--2042 and disjoint evaluation seeds, clean learning causes 1/188 delayed violations, poisoned action-only causes 38/188 in 3/3 seeds, and commit gate/freeze cause 0/188. Paired discordance is 37 poison-only versus 0 clean-only (`p=1.46e-11`). Commit retains a nonzero 5% interpolation of each poisoned pending snapshot and has better mean deployment reward than freeze (`-0.102` versus `-0.117`). |
| quadrotor_2d | lifecycle scaffold | A state-dependent antisymmetric thrust residual passes the delayed-trigger screen and causes 12/12 delayed PyBullet failures (median first step 18), while clipped LQR, always-freeze, a 35% commit interpolation, and a permanent 5-step robust backup shield cause 0/12. A one-step robust projector remains unsafe (4/4), so only the backup-recoverability version is treated as an empirical escape condition. |
| quadrotor_2d | REINFORCE reward-log poisoning smoke | A 2-output Gaussian residual actor uses real PyBullet transitions and reward-to-go REINFORCE. A batch-aware white-box attacker changes only rewards with `L_inf <= 0.5`. At seed 2040, clean is 0/8, poisoned action-only is 8/8 delayed failures (median first step 52), and 55% commit, freeze, and permanent 5-step backup filtering are each 0/8. Adaptation has zero constraint violations and the permanent filter has 149 interventions with zero rejection. This is a provisional one-seed smoke, not the final multi-seed estimate. |
| quadrotor_2d | locked multi-seed REINFORCE audit | Target and hyperparameters are locked on seed 2040. Learner seeds 2040--2042 use disjoint training, certificate, and deployment states. Clean is 0/72, poisoned action-only is 68/72 in 3/3 seeds (all delayed; median first 58.5), commit/freeze are 0/72, and paired discordance is 68 poison-only versus 0 clean-only (two-sided exact `p=6.78e-21`). Commit retains 55%/40%/70% of the three pending updates. |
| quadrotor_2d | official linear MPSC | The upstream registered `linear_mpsc` filter and pretrained quadrotor RPI artifact certify the three learned poisoned snapshots with 0/12 violations and zero infeasible solves. It intervenes on 1200/1200 steps and has mean reward `-0.357`, versus `-0.060` for commit on the broader audit, exposing a large availability/performance cost. |
| quadrotor_2d | official PPO fine-tuning probe | Upstream pretrained PPO is 0/72 on the held-out domain; the normalized malicious target is 72/72 unsafe (median first 30). With paired proposal noise, official MPSC-protected adaptation, upstream PPO updates, and reward-only budget `L_inf <= 0.5`, an exact parameter-space attack moves the 8-batch poisoned actor closer to target than clean (MSE 0.926 vs 1.343) and reduces reward (0.705 vs 0.800), but clean/poison/freeze remain 0/8 safety violations. This is a negative safety result at the fixed budget, not attack success. |

Delayed-trigger robustness command:

```bash
MPLCONFIGDIR=/tmp/matplotlib-lifecycle-gate \
/home/feihm/llm-fei/.llm/bin/python safe_control_gym_delayed_trigger_sweep.py
```

Scope condition: snapshot deployment is admitted only when the trusted baseline
has at least `0.0075` finite-horizon recovery margin. States outside this core
remain on the baseline/fail-safe path. The certificate is finite-horizon and
sampled; it is not a continuous-state invariant-set proof.

Real-learner reward-poisoning command:

```bash
MPLCONFIGDIR=/tmp/matplotlib-lifecycle-gate \
/home/feihm/llm-fei/.llm/bin/python \
  safe_control_gym_reinforce_reward_poisoning_sweep.py
```

This closes the direct-gradient artifact in the first delayed-trigger smoke,
but it is still a low-dimensional canonical REINFORCE actor rather than an
official deep PPO/DDPG policy.

Quadrotor learner-smoke command:

```bash
MPLCONFIGDIR=/tmp/matplotlib-lifecycle-gate \
/home/feihm/llm-fei/.llm/bin/python \
  safe_control_gym_quadrotor_reinforce_reward_poisoning.py
```

The second-system smoke now passes, including a permanent 5-step backup-shield
escape condition. The next hard gate is multi-seed/held-out replication and
comparison with official MPSC/Safety Layer plus an official PPO/DDPG or
adaptive-MPC learner family.

Paper-sweep mini command that generated the current standalone figure:

```bash
MPLCONFIGDIR=/tmp/matplotlib-lifecycle-gate \
/home/feihm/llm-fei/.llm/bin/python safe_control_gym_paper_sweep.py \
  --profile quick \
  --seeds 2026,2027 \
  --rhos 0.03 \
  --frontier-rhos 0.02,0.04,0.06 \
  --cbf-rhos 0.015 \
  --n-steps 6 \
  --population 8 \
  --iterations 2 \
  --action-grid-size 41 \
  --out-prefix safe_control_gym_paper_mini
```

Full paper-sweep command, not yet run to completion:

```bash
MPLCONFIGDIR=/tmp/matplotlib-lifecycle-gate \
/home/feihm/llm-fei/.llm/bin/python safe_control_gym_paper_sweep.py \
  --profile paper \
  --out-prefix safe_control_gym_paper
```

Plausible-set LifecycleGate command:

```bash
MPLCONFIGDIR=/tmp/matplotlib-lifecycle-gate \
/home/feihm/llm-fei/.llm/bin/python safe_control_gym_plausible_set_lifecycle_gate.py \
  --kernel-backend casadi \
  --attack-kernel-backend euler \
  --n-steps 10 \
  --rho 0.03 \
  --population 12 \
  --iterations 3 \
  --action-grid-size 61 \
  --freeze-weight 0.0 \
  --gain-step 3.0 \
  --bias-step 0.7 \
  --out results/safe_control_gym_plausible_set_lifecycle_gate_casadi.csv
```

Freeze-frontier command:

```bash
MPLCONFIGDIR=/tmp/matplotlib-lifecycle-gate \
/home/feihm/llm-fei/.llm/bin/python safe_control_gym_plausible_set_lifecycle_gate.py \
  --kernel-backend casadi \
  --attack-kernel-backend euler \
  --n-steps 6 \
  --rho-list 0.01 0.02 0.03 0.04 0.05 \
  --population 8 \
  --iterations 2 \
  --action-grid-size 41 \
  --stale-weight 0.2 \
  --unsafe-weight 0.2 \
  --freeze-weight 2.0 \
  --gain-step 3.0 \
  --bias-step 0.7 \
  --mechanisms plausible_action_filter_update_ungated always_freeze lifecycle_gate_project \
  --out results/safe_control_gym_freeze_frontier_casadi.csv
```

Current limitation: the default gate now uses Safe-Control-Gym's CasADi
discrete dynamics and is non-oracle because it never inspects the true state
during certification. The official CBF sampled backend is implemented and
smoke-tested, but is conservative near the cartpole boundary. Official linear
MPSC is now runnable after installing `pytope`, `pycddlib`, and `cvxpy`; the
upstream pretrained quadrotor RPI artifact loads successfully. Its current
audit is safe but intervenes at every evaluated step.

## Continuous Adaptive Attacker

The attacker optimizes a continuous FDI vector over a horizon:

```text
max_a
    w_s * stale_margin(theta+, H_A)
  + w_u * unsafe_margin(u_applied, X_A)
  + w_f * freeze_margin(K_Gamma)
  - w_r * stealth_residual(a)
  - w_m * ||a||^2

subject to
    ||a_t||_inf <= rho
    residual(a_t) <= tau
    theta+ = U(theta, poisoned_history)
```

Implementation route:

1. Use `continuous_adaptive_attacker.py` CEM optimizer for black-box attacks.
2. Add a PGD/CasADi variant after the stale/unsafe/freeze margins are wired into Safe-Control-Gym.
3. Use CEM for EPANET/PowerGym-style nondifferentiable simulators.

## Next Engineering Steps

1. Done: add a Safe-Control-Gym controller adapter that runs official LQR/linear-MPC controllers and writes CSV summaries.
2. Define Safe-Control-Gym lifecycle metrics:
   - `unsafe_certified_rate`
   - `stale_certified_policy_rate`
   - `uncertified_learning_rate`
   - `learn_update_rate`
   - `tracking_cost`
   - `freeze_duration`
3. Done: implement the first continuous observation-FDI attacker on cartpole using CEM.
4. Done: replace the oracle-state CBF comparison with an attacked-history plausible-set kernel and LifecycleGate update gate for LQR+linear residual learning.
5. Done: add CasADi robust kernel backend and official CBF sampled kernel backend.
6. Done: run a separate CasADi freeze-frontier sweep.
7. Done: add `safe_control_gym_paper_sweep.py` for multi-seed aggregation and a standalone Safe-Control-Gym figure.
8. Next: run the full `--profile paper` sweep when ready to spend the longer CasADi runtime.
9. Done: make official linear MPSC runnable with the upstream pretrained quadrotor RPI artifact.
10. Done (provisional smoke): move the successful reward-only attacker/commit gate to `quadrotor_2d`, including independent PyBullet deployment and a permanent 5-step backup shield.
11. Done: run locked multi-seed/disjoint held-out quadrotor replication and official MPSC audit. Safety Layer/RARL/RAP remain open.
12. Done/STOP under the locked `ppo_b_lite_protocol.md`: at 16 batches clean is 0/24 and poison is 1/24, but the marginal poison-only failure disappears at 24 batches (clean/poison both 0/24). Neither the pre-specified physical nor two-checkpoint margin condition passes, so no confirmatory PPO multi-seed sweep is started and the threat model is not expanded.
13. Done/STOP under `benign_utility_protocol.md`: locked calibration selected a `0.003 N` differential actuator bias. The development smoke was safe but failed utility: freeze/clean/gate rewards were `-0.03617/-0.04714/-0.08097`; LifecycleGate accepted updates in 11/12 batches with mean fraction `0.8208` but improved 0/12 paired rollouts. No formal utility sweep was launched. This triggers the predeclared TDSC pivot.
