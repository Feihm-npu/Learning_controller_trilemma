from __future__ import annotations

import csv

import numpy as np

import safe_control_gym_cartpole_moment_preserving_reward as s2
import safe_control_gym_reinforce_reward_poisoning as reinforce


def test_box_zero_sum_projection_satisfies_kkt_form() -> None:
    desired = np.asarray([1.8, -1.2, 0.7, -0.1, 1.1, -1.7, 0.4, -0.8])
    lower = np.asarray([-0.4, -1.5, -0.6, -0.8, -0.2, -1.8, -0.5, -1.0])
    upper = np.asarray([1.2, 0.3, 0.8, 0.4, 0.7, -0.1, 0.6, 0.2])
    projected, multiplier = s2.project_box_zero_sum(desired, lower, upper)
    assert abs(float(np.sum(projected))) <= 1e-12
    assert np.all(projected >= lower - 1e-12)
    assert np.all(projected <= upper + 1e-12)
    assert np.allclose(
        projected,
        np.clip(desired - multiplier, lower, upper),
        atol=1e-12,
        rtol=0.0,
    )


def test_projection_rejects_infeasible_zero_sum_box() -> None:
    with np.testing.assert_raises(ValueError):
        s2.project_box_zero_sum(
            np.zeros(3), np.ones(3), np.full(3, 2.0)
        )


def test_s2_attack_preserves_mean_sign_range_and_budget() -> None:
    rewards = np.asarray([-2.4, -1.8, -1.4, -1.0, -0.7, -0.5, -0.3, -0.1])
    features = np.column_stack([np.linspace(-0.8, 0.9, 8), np.ones(8)])
    noise = np.asarray([0.4, -0.7, 0.3, 0.8, -0.2, -0.9, 0.5, -0.1])
    attack = s2.MomentPreservingRewardAttack(2070)
    delta, audit = attack.select(
        batch=0,
        exploration_noise=noise,
        features=features,
        true_rewards=rewards,
        dones=np.zeros(8),
        learner_params=np.zeros(2),
        target_params=reinforce.to_learner_params(s2.TARGET_EFFECTIVE),
        sigma=0.8,
        gamma=0.97,
        actor_lr=1.0,
        max_gradient_norm=1.0,
        budget=2.0,
    )
    logged = rewards + delta
    assert abs(float(np.sum(delta))) <= 1e-10
    assert np.isclose(np.mean(logged), np.mean(rewards), atol=1e-10)
    assert np.min(logged) >= s2.SCALAR_LOWER - 1e-10
    assert np.max(logged) <= s2.SCALAR_UPPER + 1e-10
    assert np.max(np.abs(delta)) <= 2.0 + 1e-10
    assert np.all(logged <= 0.0)
    assert s2.invariant_pass(audit)


def test_s2_envelope_matches_preexisting_frozen_calibration() -> None:
    with (s2.RESULTS / "cartpole_reward_detectability_calibration.csv").open(
        newline=""
    ) as source:
        row = list(csv.DictReader(source))[0]
    assert s2.SCALAR_LOWER == float(row["scalar_reward_min"])
    assert s2.SCALAR_UPPER == float(row["scalar_reward_max"])
    assert tuple(s2.TARGET_EFFECTIVE) == (-2.3625524160241205, -5.0)


def test_s2_negative_result_closes_wp_before_new_seeds() -> None:
    smoke = s2.s1.read_rows(
        s2.RESULTS / "cartpole_stealth_s2_2070_decision.csv"
    )[0]
    final = s2.s1.read_rows(s2.RESULTS / "cartpole_stealth_wp_decision.csv")[0]
    assert smoke["all_projection_invariants_pass"] == "True"
    assert smoke["target_progress_pass"] == "True"
    assert smoke["raw_release_effect_pass"] == "False"
    assert smoke["next_action"] == "close_wp_without_new_seeds"
    assert final["burned_extension_run"] == "False"
    assert final["new_confirmation_namespace_opened"] == "False"
    assert final["work_package_status"] == "closed_insufficient_deployment_effect"
