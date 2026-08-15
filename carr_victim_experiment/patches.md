# Patches vs upstream (Carr et al. AAAI'23 official code)

All deviations from `stevencarrau/safe_RL_POMDPs` (Zenodo badge commit, vendored
2026-08-14) and `stevencarrau/shield_rl_gridworlds` (POMDP package). Verified by
`git diff 62c515e` in this directory. No change touches the algorithm, the
shield semantics, the workflow, or the environment dynamics.

| File | Change | Why |
|---|---|---|
| model_simulator.py | `SimulationExecutor.__init__(model, shield, seed=10)` | Independent training seeds (upstream hardcoded Storm simulator seed 10) |
| rl_simulator.py | `TF_Environment` accepts `seed` + `poison_spec`; stores attack-plane hooks (`poison_fn`, `risky_flags`, `episode_violation_log`) | Reward-record attack surface + metric capture |
| rl_simulator.py | `step()`: after `cost_fn`, apply `poison_fn` if set | THE attack: mutates reward scalar between environment and learner; eval env never poisoned |
| rl_simulator.py | `simulate_deep_RL`: sets tf/np/random seeds from env seed before agent creation | Seed determinism per run |
| rl_simulator.py | final eval replaced by `evaluate_episodes` (same rollout loop, plus per-episode violation flags, first-violation, shield-disagreement fraction) | Required metrics (protocol §5); loop mechanics identical to `compute_avg_return` |
| rl_simulator.py | `set_poison`, `risk_at_current_state`, `reset_violation_log`, `compute_risk_flags` | Poison variants V1 bias / V2 risk / V3 contrast; risk flags from public model (one-step-to-trap) |
| shield.py | `np.random.seed(args.seed)` next to upstream `random.seed` | Seed determinism |
| shield.py | `output_dir` config → results dir (was None → broken "None/" paths) | Output hygiene |
| shield.py | pass `seed` to both TF_Environments; attach poison to learn env only | Attack wiring (protocol §3) |
| shield.py | per-run `*_summary.json` with cfg + during/after/first-violation | Provenance + metrics |
| shield.py | eval env gets an INDEPENDENT belief tracker (upstream shares one tracker) | The unmasked disagreement probe executes raw-policy actions; with a shared tracker those actions corrupt the training belief and the training trajectory (observed: clean seed-1 rerun changed 75.6% → 23.6% post-removal violations). Independent tracker keeps the probe observationally harmless to training. |

## Non-goals (unchanged upstream behavior)
- Shield computation (Storm belief-support winning region), action masking, HARD/SOFT
  switch mechanics (`shield_on`, `decay += 5e-3*alpha`), REINFORCE/PPO/SAC agents,
  hyperparameters, 5000-episode eval count: all untouched.
