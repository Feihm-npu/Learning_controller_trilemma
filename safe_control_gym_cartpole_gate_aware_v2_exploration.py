#!/usr/bin/env python3
"""Exploratory V2 on the already burned seed 2060.

V1 showed that the nominal target direction (18, -5) has no non-negative
normalized reward influence in the first fresh batch.  This diagnostic uses
the previously observed harmful and five-step-accepted snapshot as a fixed
parameter-space prototype.  It does not consume or authorize untouched seeds.
"""

from __future__ import annotations

from argparse import Namespace
from pathlib import Path

import numpy as np

import safe_control_gym_cartpole_prospective_gate_aware_attack as prospective


ROOT = Path(__file__).resolve().parent
RESULTS = ROOT / "results"
PROTOTYPE = np.asarray([-2.3625524160241205, -5.0], dtype=float)


def main() -> None:
    args = Namespace(
        batches=12,
        batch_steps=8,
        rho=0.005,
        sigma=0.8,
        actor_lr=1.0,
        gamma=0.97,
        max_gradient_norm=1.0,
        reward_poison_budget=2.0,
        bisection_steps=40,
        candidate_states=32,
        selected_states=24,
        monitor_horizon=5,
        deployment_steps=120,
        baseline_guard_margin=0.0075,
        action_grid_size=41,
    )
    (
        clean_params,
        poisoned_params,
        support_rows,
        training_rows,
        poisoned_training,
    ) = prospective.train_seed(
        2060,
        9060,
        args,
        target_effective=PROTOTYPE,
    )
    rollout_rows, decision = prospective.audit_seed(
        2060,
        9060,
        clean_params,
        poisoned_params,
        support_rows,
        poisoned_training,
        args,
    )
    prospective.write_csv(
        RESULTS / "cartpole_gate_aware_v2_exploratory_batches.csv",
        support_rows,
    )
    prospective.write_csv(
        RESULTS / "cartpole_gate_aware_v2_exploratory_training.csv",
        training_rows,
    )
    prospective.write_csv(
        RESULTS / "cartpole_gate_aware_v2_exploratory_rollouts.csv",
        rollout_rows,
    )
    prospective.write_csv(
        RESULTS / "cartpole_gate_aware_v2_exploratory_decision.csv",
        [decision],
    )
    print(f"target={PROTOTYPE.tolist()}")
    print(f"clean={clean_params.tolist()}")
    print(f"poisoned={poisoned_params.tolist()}")
    print(decision)


if __name__ == "__main__":
    main()
