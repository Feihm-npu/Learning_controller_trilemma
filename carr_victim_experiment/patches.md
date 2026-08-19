# Patches vs upstream (Carr et al. AAAI'23 official code)

All deviations from `stevencarrau/safe_RL_POMDPs` commit
`b01dbe8b40e2167bdc1d93dea7b43e96f1a835ee` are stored in
`upstream/carr_reward_poisoning.patch`.  Applying that file to a clean checkout
reconstructs the instrumented code and the actual `run_carr_victim.py` driver.
No change touches the learning algorithm, shield semantics, or environment
dynamics.

| File | Change | Why |
|---|---|---|
| model_simulator.py | `SimulationExecutor.__init__(model, shield, seed=10)` | Independent training seeds (upstream hardcoded Storm simulator seed 10) |
| rl_simulator.py | `TF_Environment` accepts `seed` + `poison_spec`; stores attack-plane hooks (`poison_fn`, `risky_flags`, `episode_violation_log`) | Reward-record attack surface + metric capture |
| rl_simulator.py | `step()`: after `cost_fn`, apply `poison_fn` if set | THE attack: mutates reward scalar between environment and learner; eval env never poisoned |
| rl_simulator.py | `simulate_deep_RL`: sets tf/np/random seeds from env seed before agent creation | Seed determinism per run |
| rl_simulator.py | final eval replaced by `evaluate_episodes` (same rollout loop, plus per-episode violation flags, first-violation, shield-disagreement fraction) | Required metrics (protocol §5); loop mechanics identical to `compute_avg_return` |
| rl_simulator.py | `set_poison`, `risk_at_current_state`, `reset_violation_log`, `compute_risk_flags` | Poison variants V1 bias / V2 risk / V3 contrast; risk flags from public model (one-step-to-trap) |
| run_carr_victim.py | Standalone CLI wires separate training/evaluation models and belief trackers, poisoning only the learning environment | Executable experiment driver and observationally harmless disagreement probe |
| run_carr_victim.py | Writes configuration, at-retirement trace, final evaluation, disagreement, poison statistics, and file provenance | Reproducible row-level evidence |

## Non-goals (unchanged upstream behavior)
- Shield computation (Storm belief-support winning region), action masking, HARD/SOFT
  switch mechanics (`shield_on`, `decay += 5e-3*alpha`), REINFORCE/PPO/SAC agents,
  hyperparameters, 5000-episode eval count: all untouched.
