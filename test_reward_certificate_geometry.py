from __future__ import annotations

import numpy as np

import reward_certificate_geometry as geometry
import safe_control_gym_reinforce_reward_poisoning as cartpole_reinforce


def test_reward_to_go_operator_respects_episode_boundaries():
    rewards = np.asarray([1.0, 2.0, 3.0, 4.0])
    dones = np.asarray([0.0, 1.0, 0.0, 1.0])
    operator = geometry.reward_to_go_operator(dones, gamma=0.5)

    np.testing.assert_allclose(
        operator @ rewards,
        cartpole_reinforce.reward_to_go(rewards, dones, gamma=0.5),
    )


def test_normalized_geometry_matches_artifact_gradient():
    features = np.asarray(
        [[-0.5, 1.0], [-0.1, 1.0], [0.2, 1.0], [0.6, 1.0]]
    )
    noise = np.asarray([-0.7, 0.2, 0.9, -0.3])
    rewards = np.asarray([-0.4, 0.3, -0.1, 0.8])
    dones = np.asarray([0.0, 0.0, 0.0, 1.0])
    sigma = 0.8
    gamma = 0.97
    scores = geometry.gaussian_score_matrix(features, noise, sigma)
    operator = geometry.centered_return_operator(dones, gamma)

    reconstructed = geometry.normalized_reinforce_gradient(
        scores, rewards, operator
    )
    artifact = cartpole_reinforce.reinforce_gradient(
        features,
        noise,
        rewards,
        dones,
        sigma=sigma,
        gamma=gamma,
    )

    np.testing.assert_allclose(reconstructed, artifact, atol=1e-12, rtol=1e-12)


def test_halfspace_support_matches_random_attack_lower_bound():
    features = np.asarray(
        [
            [-0.5, 1.0],
            [-0.2, 1.0],
            [0.0, 1.0],
            [0.25, 1.0],
            [0.55, 1.0],
        ]
    )
    noise = np.asarray([-0.9, 0.4, 0.8, -0.5, 0.3])
    rewards = np.asarray([-1.2, 0.4, -0.6, 0.7, 1.1])
    dones = np.asarray([0.0, 0.0, 0.0, 0.0, 1.0])
    budget = 0.1
    scores = geometry.gaussian_score_matrix(features, noise, sigma=0.8)
    operator = geometry.centered_return_operator(dones, gamma=0.97)
    transform = np.diag([5.0, 1.0])
    row = np.asarray([0.2, 1.0])
    result = geometry.worst_positive_halfspace_support(
        current_params=np.zeros(2),
        rewards=rewards,
        centered_operator=operator,
        score_matrix=scores,
        reward_budget=budget,
        actor_lr=0.2,
        coordinate_map=transform,
        halfspace_row=row,
        bisection_steps=35,
    )

    rng = np.random.default_rng(7)
    sampled_values = []
    for _ in range(10_000):
        attacked_rewards = rewards + rng.uniform(-budget, budget, len(rewards))
        gradient = geometry.normalized_reinforce_gradient(
            scores, attacked_rewards, operator
        )
        next_params = transform @ (0.2 * gradient)
        sampled_values.append(float(row @ next_params))

    assert result.support + 1e-6 >= max(sampled_values)
    assert result.support - max(sampled_values) < 5e-3
    assert np.max(np.abs(result.reward_delta)) <= budget + 1e-6


def test_homogenized_support_matches_old_solver_when_unclipped():
    features = np.asarray(
        [[-0.5, 1.0], [-0.2, 1.0], [0.0, 1.0], [0.25, 1.0], [0.55, 1.0]]
    )
    noise = np.asarray([-0.9, 0.4, 0.8, -0.5, 0.3])
    rewards = np.asarray([-1.2, 0.4, -0.6, 0.7, 1.1])
    dones = np.asarray([0.0, 0.0, 0.0, 0.0, 1.0])
    scores = geometry.gaussian_score_matrix(features, noise, sigma=0.8)
    operator = geometry.centered_return_operator(dones, gamma=0.97)
    transform = np.diag([5.0, 1.0])
    row = np.asarray([0.2, 1.0])
    common = dict(
        current_params=np.zeros(2),
        rewards=rewards,
        centered_operator=operator,
        score_matrix=scores,
        reward_budget=0.1,
        actor_lr=0.2,
        coordinate_map=transform,
        halfspace_row=row,
        bisection_steps=35,
    )
    old = geometry.worst_positive_halfspace_support(**common)
    homogenized = geometry.worst_positive_halfspace_support_with_gradient_clipping(
        **common,
        gradient_cap=100.0,
    )

    assert abs(homogenized.support - old.support) < 2e-5
    assert homogenized.witness_support_error < 2e-5
    assert np.max(np.abs(homogenized.reward_delta)) <= 0.1 + 1e-6
    assert not homogenized.witness_gradient_clipped


def test_homogenized_support_excludes_zero_vector_degeneracy():
    root_two = np.sqrt(2.0)
    result = geometry.worst_positive_halfspace_support_with_gradient_clipping(
        current_params=np.zeros(2),
        rewards=np.zeros(2),
        centered_operator=np.eye(2),
        score_matrix=root_two * np.eye(2),
        reward_budget=1.0,
        actor_lr=1.0,
        coordinate_map=np.eye(2),
        halfspace_row=np.asarray([1.0, 0.0]),
        gradient_cap=100.0,
        bisection_steps=35,
    )

    assert abs(result.support - 1.0) < 2e-5
    assert result.witness_centered_return_norm > 1e-6
    assert result.witness_support_error < 2e-5
    assert np.max(np.abs(result.reward_delta)) <= 1.0 + 1e-6


def test_homogenized_support_is_exact_when_gradient_cap_activates():
    root_two = np.sqrt(2.0)
    result = geometry.worst_positive_halfspace_support_with_gradient_clipping(
        current_params=np.zeros(2),
        rewards=np.zeros(2),
        centered_operator=np.eye(2),
        score_matrix=root_two * np.diag([2.0, 1.0]),
        reward_budget=1.0,
        actor_lr=1.0,
        coordinate_map=np.eye(2),
        halfspace_row=np.asarray([1.0, 0.0]),
        gradient_cap=0.5,
        bisection_steps=35,
    )

    assert abs(result.support - 0.5) < 2e-5
    assert result.witness_gradient_clipped
    assert abs(result.witness_raw_gradient_norm - 2.0) < 2e-5
    assert result.witness_support_error < 2e-5
