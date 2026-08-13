# U2 pre-registered protocol: joint observation-FDI + reward-log (non-singleton plausible set)

> Locked 2026-08-10 **before execution**. Purpose: close the formal-vs-empirical
> gap (novelty review item 3 / mock-review R2b) that the end-to-end attack keeps
> observations trusted, so the plausible-state set `X_A(h)` is effectively a
> singleton and the commit check reduces to finite-state post-training
> verification. U2 activates the **observation-FDI channel** alongside reward-log
> corruption, so the certificate genuinely ranges over a **non-singleton** box,
> and tests whether the contract separation persists off the singleton. Outcome
> (pass or fail) is reported honestly.

## What changes vs C2

- C2 uses observation-FDI radius `rho=0.005` (near-singleton box) with reward-log
  poison. U2 keeps the reward-log channel identical and **raises `rho`** so the
  attacked-history plausible box `X_A(h)=[\,\hat\theta-\rho,\hat\theta+\rho\,]`
  (pole-angle coordinate, `THETA_SCALE=0.2`) spans multiple physical states. The
  same CasADi safe-kernel / commit machinery already ranges over this box; U2
  exercises it in the genuinely non-singleton regime.
- Both attack channels of the general model are therefore active: observation FDI
  `a_t` enlarges `X_A(h)`; reward-log corruption `b_t` (unchanged, bounded
  `\lVert b\rVert_\infty\le2.0`) redirects the update. Learner = residual
  REINFORCE (the primary C2 family), so this directly extends C2.

## Locked design

- **Learner / harness:** the locked residual-REINFORCE study
  (`safe_control_gym_reinforce_reward_poisoning.train_reinforce`) is reused
  **without modification**; U2 only sets `rho` and the seed and records the
  plausible-box size. All other hyperparameters are the C2 locked values.
- **Locked `rho` grid (reported in full — characterization, not selection):**
  `{0.005, 0.02, 0.04}` — singleton reference, non-singleton, and
  approaching-frontier. Reporting every value makes this a freeze-frontier
  characterization, not a cherry-picked radius.
- **Non-singleton measure:** for each `rho`, record the mean number of distinct
  sampled plausible states the kernel ranges over and the mean kernel width, to
  demonstrate `X_A` is non-singleton for `rho>0.005`.
  *(Implementation deviation, disclosed: the released run uses the radius
  threshold `rho>0.005` as the non-singleton indicator and reports the physical
  box half-width $\pm\rho$ rather than logging the distinct-state count. The
  observation FDI is nonetheless real --- a $\pm\rho$ pole-angle box, about
  $\pm2.3^\circ$ at `rho=0.04` --- and the paper wording reflects exactly this.)*
- **Contracts:** clean / poisoned-action-only / always-freeze / commit, deployed
  on true physical states (deployment measures the snapshot's real safety), as
  in C2.

## Seeds (new namespace)

- Canary/development seed `2210`; confirmation seeds `2211`, `2212` (opened only
  if the canary passes). Disjoint from all prior seeds including U1's 2200--2202.

## Locked stop rule

**Canary (2210) PASS iff** there exists a **non-singleton** radius
`rho\in\{0.02,0.04\}` at which all hold:
1. the plausible box is genuinely non-singleton (mean distinct sampled states `>1`);
2. poisoned-action-only deployment violations `\ge 5`;
3. clean deployment violations `\le 1`;
4. commit and always-freeze deployment violations both `= 0`.

- **PASS** → run `2211`, `2212` unchanged at the full grid; report the frontier
  (kernel width and per-contract violations vs `rho`) and pooled separation at
  the passing non-singleton radius.
- **FAIL** → **STOP.** Report honestly: either the frontier lies below `0.02`
  (kernel empties / attack cannot act under non-singleton certification — a
  freeze-frontier boundary) or the separation does not persist. Do **not** add
  radii, change the budget, or open more seeds.

## Claim mapping

- PASS: the paper may state that the lifecycle contract separation persists when
  the certificate ranges over a non-singleton attacked-history plausible set
  (joint observation-FDI + reward-log), so the empirical result is not an
  artifact of a singleton plausible state.
- FAIL: the paper gains an explicit freeze-frontier boundary for the end-to-end
  attack under observation ambiguity.

## Artifacts

- `safe_control_gym_cartpole_joint_channel_poisoning.py` (imports the locked
  REINFORCE harness; adds the `rho` grid, non-singleton measurement, and
  decision).
- `results/cartpole_joint_channel_poisoning_multiseed_{frontier,rollouts,decision}.csv`.
