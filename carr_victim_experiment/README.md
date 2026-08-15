# Carr et al. AAAI'23 victim experiment — reward poisoning across shield retirement

Third-party workflow demonstration for the NDSS paper's security claim
("assurance evidence's validity across an authority transition", see repo
`ndss_submission_status.md` / `research_state.md`). Uses the *official* code of

> Carr, Jansen, Junges, Topcu, "Safe Reinforcement Learning via Shielding under
> Partial Observability", AAAI 2023 (DOI 10.1609/aaai.v37i12.26723)
> code: github.com/stevencarrau/safe_RL_POMDPs (Zenodo DOI 10.5281/zenodo.7320140)
> environments: github.com/stevencarrau/shield_rl_gridworlds

## Layout
- `protocol.md` — locked experiment protocol (before any run): lifecycle, attack
  plane, budgets, metrics, fidelity gate, stop rules.
- `patches.md` — every deviation from upstream, with rationale (git diff 62c515e).
- `upstream/` — vendored official code (pristine in commit 62c515e; patches since).
- `run_carr.py` — runner: `--env {obstacle,avoid,rocks,...} --condition
  {none,shield,sudden,smooth} --method REINFORCE/PPO/SAC --runs N --seed S
  --poison {none,v1,v2,v3} --delta D`.
- `smoke_stormpy.py` — native-layer smoke (POMDP build, winning region, risk flags).
- `check_api_compat.py` — tf-agents API compatibility check.
- `aggregate_results.py` — results table + figures.
- `results/` — per-run dirs with `*_summary.json` (provenance + metrics),
  `*_eval_trace.npy` (per-episode eval violations), G0 CSV (reward curves).

## Environment (this Mac)
macOS 14.4.1 arm64, venv at `venv/` (Python 3.10.12 from pyenv):
tensorflow 2.15.1, tensorflow-probability 0.23.0, tf-agents 0.19.0, stormpy 1.11.3,
numpy 1.26.4. `wheels_cache/` holds the downloaded wheels for offline rebuilds.

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
