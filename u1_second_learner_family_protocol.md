# U1 pre-registered protocol: second learner family (advantage actor--critic)

> Locked 2026-08-10 **before execution**. Purpose: test whether the reward-log-only
> lifecycle attack (paper claim C2) transfers to a **second on-policy learner
> family** distinct from the established residual REINFORCE, addressing the
> "single learner family" generality objection (mock-review R3, item U1). This
> document fixes the family, threat model, hyperparameters, seeds, and a stop
> rule before any confirmation seed is opened. Outcome (pass or fail) will be
> reported honestly; a failed canary is a negative learner-family boundary, not a
> reason to tune.

## Family under test

- **Advantage actor--critic (A2C), on-policy**, with a learned **linear
  per-state value baseline** `V(s)=w_v^\top \phi(s)`, `\phi(s)=[\theta/0.2, 1]`.
- Same Gaussian residual actor `u = u_{LQR}(s) + \phi(s)^\top\theta_a + \epsilon`,
  `\epsilon\sim\mathcal N(0,\sigma^2)`, as the REINFORCE study.
- Update per batch: returns-to-go `G_t` from **logged** rewards; advantage
  `A_t = G_t - V(s_t)`; scale-normalize `A_t \leftarrow A_t/\mathrm{std}(A_t)`
  (no second mean subtraction — the critic is the baseline); policy gradient
  `\bar{g} = \mathrm{mean}(A_t\,\epsilon_t\phi(s_t)/\sigma^2)`; critic regression
  `w_v \leftarrow w_v + \eta_v\,\mathrm{mean}((G_t-V(s_t))\phi(s_t))` for
  `\texttt{critic\_steps}` inner steps.
- **Distinction from REINFORCE:** REINFORCE uses a constant batch-mean baseline;
  A2C uses a learned state-dependent critic. This moves the family axis from
  Monte-Carlo policy gradient (REINFORCE, positive C2) toward baselined
  actor--critic, complementing the negative official-PPO boundary. **Off-policy
  DDPG/SAC is explicitly out of scope** here: it would poison the reward inside a
  TD target and therefore change the *attack channel*, not just the learner; it
  remains future work.

## Threat model (identical to C2 — unchanged)

- Attacker writes **only** the scalar reward log, bounded `\lVert b\rVert_\infty
  \le 2.0`, via the same `reward_poison` `\tanh` rule. It cannot write actions,
  gradients, actor or **critic** parameters, optimizer state, dynamics, or
  deployment states. The critic is trained by the trusted learner from logged
  rewards, so the poison reaches the critic only through the reward it already
  controls.
- Adaptation is protected by the same CasADi action-kernel filter; deployment
  audits the **raw** learned mean-policy snapshot under the four contracts:
  clean / poisoned-action-only / always-freeze / commit.

## Locked hyperparameters

- Reused from the locked cartpole REINFORCE study, unchanged: `batches=12`,
  `batch_steps=8`, `rho=0.005`, `sigma=0.8`, `actor_lr=1.0`, `gamma=0.97`,
  `max_gradient_norm=1.0`, `reward_poison_budget=2.0`, `poison_temperature=1.0`,
  `deployment_steps=120`, `action_grid_size=41`, `kernel_backend=casadi`,
  `admission_guard_margin=0.0075`, `commit_guard_margin=0.005`.
- **New, locked before execution:** `critic_lr=0.5`, `critic_steps=5`,
  `critic_params` initialized to zero. These are fixed a priori; they are **not**
  tuned against the outcome. If the canary fails, they are not changed.

## Seeds (new namespace, disjoint from all prior seeds)

- **Canary / development seed:** `2200`.
- **Confirmation seeds (opened only if the canary passes):** `2201`, `2202`.
- No seed in `2039--2104`, `3039--3052`, `4050--4052`, `5050--5052`,
  `6050--6052`, `7040--7042`, `8040--8042`, `9060--9102` is reused.

## Locked stop rule

**Canary (seed 2200) PASS iff all hold** on the standard deployment envelope:
1. poisoned-action-only deployment violations `\ge 5`;
2. clean deployment violations `\le 1`;
3. commit and always-freeze deployment violations both `= 0`;
4. maximum applied reward poison `\le 2.0` (budget respected).

- **PASS** → run confirmation seeds `2201`, `2202` with **no changes**, then
  report pooled clean vs poisoned violations, per-seed reproduction, paired
  poison-only vs clean-only discordance, and two-sided exact binomial `p`.
- **FAIL** → **STOP.** Report the canary as a negative second-family boundary
  ("reward-log-only poisoning does not transfer to the baselined actor--critic
  under the locked budget"). Do **not** tune critic hyperparameters, raise the
  budget, change the target, or open `2201/2202`.

## Claim mapping

- If the confirmation passes (poisoned `\gg` clean across 3/3 seeds, commit and
  freeze `0`): the paper may state that the lifecycle attack transfers to a
  second on-policy learner family (baselined actor--critic), widening C2 beyond
  Monte-Carlo REINFORCE while official PPO remains negative.
- If the canary fails: the paper gains a second negative boundary (a learned
  value baseline blunts the reward-log attack under this budget), which is also
  a legitimate and reportable result.

## Artifacts

- Implementation: `safe_control_gym_cartpole_a2c_reward_poisoning.py`
  (imports the locked REINFORCE harness; only the update rule differs).
- Outputs: `results/cartpole_a2c_reward_poisoning_{summary,rollouts,traces,decision}.csv`.
