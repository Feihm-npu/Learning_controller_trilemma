from __future__ import annotations

import numpy as np

import safe_control_gym_cartpole_sparse_reward_permutation as s1
import safe_control_gym_reinforce_reward_poisoning as reinforce


def example_batch() -> dict[str, np.ndarray]:
    return {
        "features": np.asarray(
            [
                [-0.8, 1.0],
                [-0.5, 1.0],
                [-0.2, 1.0],
                [0.0, 1.0],
                [0.2, 1.0],
                [0.4, 1.0],
                [0.7, 1.0],
                [0.9, 1.0],
            ]
        ),
        "exploration_noise": np.asarray(
            [0.4, -0.7, 0.3, 0.8, -0.2, -0.9, 0.5, -0.1]
        ),
        "true_rewards": np.asarray(
            [-2.4, -1.8, -1.4, -1.0, -0.7, -0.5, -0.3, -0.1]
        ),
        "dones": np.zeros(8),
    }


def select(batch: dict[str, np.ndarray]):
    attack = s1.SparseRewardPermutationAttack(2070)
    delta, audit = attack.select(
        batch=0,
        learner_params=np.zeros(2),
        target_params=reinforce.to_learner_params(s1.TARGET_EFFECTIVE),
        sigma=s1.SIGMA,
        gamma=s1.GAMMA,
        actor_lr=s1.ACTOR_LR,
        max_gradient_norm=s1.GRADIENT_CAP,
        budget=s1.REWARD_BUDGET,
        **batch,
    )
    return delta, audit


def test_sparse_permutation_preserves_full_reward_multiset() -> None:
    batch = example_batch()
    delta, audit = select(batch)
    logged = batch["true_rewards"] + delta
    assert np.allclose(
        np.sort(logged),
        np.sort(batch["true_rewards"]),
        atol=1e-12,
        rtol=0.0,
    )
    assert audit.multiset_max_error <= 1e-12
    assert audit.reward_sum_error <= 1e-12
    assert audit.reward_mean_error <= 1e-12
    assert audit.reward_variance_error <= 1e-12
    assert audit.selected_moved_positions <= 4
    assert np.max(np.abs(delta)) <= 2.0 + 1e-12
    assert s1.invariant_pass(audit)


def test_selected_gradient_matches_scalar_learner_implementation() -> None:
    batch = example_batch()
    delta, audit = select(batch)
    logged = batch["true_rewards"] + delta
    raw = reinforce.reinforce_gradient(
        batch["features"],
        batch["exploration_noise"],
        logged,
        batch["dones"],
        sigma=s1.SIGMA,
        gamma=s1.GAMMA,
    )
    assert np.allclose(
        raw,
        [audit.selected_raw_gradient_w0, audit.selected_raw_gradient_w1],
        atol=1e-12,
        rtol=0.0,
    )


def test_selected_permutation_is_independent_first_argmin() -> None:
    batch = example_batch()
    _delta, audit = select(batch)
    rewards = batch["true_rewards"]
    best_distance = float("inf")
    best_global = -1
    target = s1.TARGET_EFFECTIVE
    for global_index, permutation in enumerate(s1.PERMUTATIONS):
        if s1.MOVED_COUNTS[global_index] > s1.MAX_MOVED:
            continue
        logged = rewards[permutation]
        if np.max(np.abs(logged - rewards)) > s1.REWARD_BUDGET + 1e-12:
            continue
        raw = reinforce.reinforce_gradient(
            batch["features"],
            batch["exploration_noise"],
            logged,
            batch["dones"],
            sigma=s1.SIGMA,
            gamma=s1.GAMMA,
        )
        _applied, next_params = s1.apply_update(
            np.zeros(2),
            raw,
            actor_lr=s1.ACTOR_LR,
            max_gradient_norm=s1.GRADIENT_CAP,
        )
        distance = float(
            np.linalg.norm(reinforce.to_effective_params(next_params) - target)
        )
        if distance < best_distance:
            best_distance = distance
            best_global = global_index
    assert best_global == audit.selected_global_permutation_index
    assert np.isclose(best_distance, audit.selected_next_target_distance)


def test_constant_reward_batch_selects_identity() -> None:
    batch = example_batch()
    batch["true_rewards"] = np.full(8, -0.5)
    delta, audit = select(batch)
    assert np.array_equal(delta, np.zeros(8))
    assert audit.selected_global_permutation_index == 0
    assert audit.selected_moved_positions == 0


def test_stage1_constants_match_locked_protocol() -> None:
    assert tuple(s1.TARGET_EFFECTIVE) == (-2.3625524160241205, -5.0)
    assert s1.REWARD_BUDGET == 2.0
    assert s1.MAX_MOVED == 4
    assert s1.BATCH_STEPS == 8
    assert len(s1.PERMUTATIONS) == 40_320


def test_locked_offline_and_s1_smoke_decisions() -> None:
    offline = s1.read_rows(s1.RESULTS / "cartpole_stealth_s1_offline_decision.csv")
    smoke = s1.read_rows(s1.RESULTS / "cartpole_stealth_s1_2070_decision.csv")
    assert offline[0]["offline_gate_pass"] == "True"
    assert int(offline[0]["audited_batches"]) == 96
    assert smoke[0]["all_permutation_invariants_pass"] == "True"
    assert smoke[0]["target_progress_pass"] == "True"
    assert smoke[0]["raw_release_effect_pass"] == "False"
    assert smoke[0]["next_action"] == "close_s1_and_run_s2_2070_once"
