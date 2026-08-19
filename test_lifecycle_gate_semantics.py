from __future__ import annotations

from unittest.mock import patch

import numpy as np

import safe_control_gym_plausible_set_lifecycle_gate as gate
import safe_control_gym_delayed_trigger_attack as delayed
import safe_control_gym_reinforce_reward_poisoning as reinforce
import safe_control_gym_quadrotor_lifecycle_scaffold as quad
import safe_control_gym_quadrotor_benign_utility as quad_utility
import safe_control_gym_quadrotor_ppo_reward_poisoning as quad_ppo_poison
import safe_control_gym_quadrotor_reinforce_reward_poisoning as quad_reinforce
import generate_tdsc_result_table as tdsc_table
import safe_control_gym_quadrotor_certificate_coverage as coverage


class DummyController:
    def select_action(self, observation, info):
        return np.asarray([0.0])


def kernel(lower: float = -1.0, upper: float = 1.0) -> gate.KernelResult:
    return gate.KernelResult(
        interval=(lower, upper),
        valid_actions=(lower, 0.0, upper),
        width=upper - lower,
        empty_reason="",
    )


def empty_kernel() -> gate.KernelResult:
    return gate.KernelResult(
        interval=None,
        valid_actions=(),
        width=0.0,
        empty_reason="no_common_action",
    )


def execute(
    mechanism: str,
    *,
    current_kernel: gate.KernelResult | None = None,
    constraints: gate.ParamConstraints | None = None,
):
    current_kernel = current_kernel or kernel()
    with (
        patch.object(gate, "safe_kernel_for_observation", return_value=current_kernel),
        patch.object(gate, "parameter_constraints", return_value=constraints),
        patch.object(gate, "poison_update", return_value=np.asarray([1.0, 0.5])),
        patch.object(gate, "total_policy_action", return_value=0.0),
    ):
        return gate.execute_mechanism_step(
            mechanism,
            DummyController(),
            {},
            np.zeros(4),
            np.zeros(2),
            0.1,
            gate.CartpoleModel(0.02, 0.5, 0.1, 1.0),
            np.asarray([-1.0, 0.0, 1.0]),
            future_span=0.03,
            guard_margin=0.0,
            gain_step=1.0,
            bias_step=0.5,
            kernel_backend="euler",
            casadi_fd_func=None,
            cbf_filter=None,
            cbf_action_tolerance=1e-5,
        )


def test_any_empty_future_kernel_makes_parameter_set_infeasible():
    observations = [np.zeros(4), np.ones(4)]
    kernels = [kernel(), empty_kernel()]
    with (
        patch.object(gate, "future_observation_grid", return_value=observations),
        patch.object(gate, "safe_kernel_for_observation", side_effect=kernels),
    ):
        constraints = gate.parameter_constraints(
            DummyController(),
            {},
            np.zeros(4),
            0.1,
            gate.CartpoleModel(0.02, 0.5, 0.1, 1.0),
            np.asarray([-1.0, 0.0, 1.0]),
            future_span=0.03,
            guard_margin=0.0,
            kernel_backend="euler",
            casadi_fd_func=None,
            cbf_filter=None,
            cbf_action_tolerance=1e-5,
        )

    assert constraints is None


def test_lifecycle_gate_freezes_when_a_future_kernel_is_empty():
    next_params, _action, diagnostics = execute("lifecycle_gate_project")

    np.testing.assert_allclose(next_params, np.zeros(2))
    assert not diagnostics.learn_update
    assert not diagnostics.param_cert_accept
    assert diagnostics.empty_kernel
    assert diagnostics.intervention
    assert not diagnostics.uncertified_learning
    assert not diagnostics.stale_certified_policy


def test_lifecycle_gate_freezes_when_current_kernel_is_empty():
    feasible_constraints = gate.ParamConstraints(
        rows=np.asarray([[1.0, 0.0], [-1.0, 0.0]]),
        bounds=np.asarray([10.0, 10.0]),
        min_kernel_width=1.0,
        empty_count=0,
    )
    next_params, _action, diagnostics = execute(
        "lifecycle_gate_project",
        current_kernel=empty_kernel(),
        constraints=feasible_constraints,
    )

    np.testing.assert_allclose(next_params, np.zeros(2))
    assert not diagnostics.learn_update
    assert not diagnostics.param_cert_accept
    assert diagnostics.empty_kernel
    assert diagnostics.intervention
    assert not diagnostics.stale_certified_policy


def test_action_only_filter_exposes_uncertified_update_on_empty_future_kernel():
    next_params, _action, diagnostics = execute("plausible_action_filter_update_ungated")

    np.testing.assert_allclose(next_params, np.asarray([1.0, 0.5]))
    assert diagnostics.learn_update
    assert diagnostics.action_cert_accept
    assert diagnostics.empty_kernel
    assert diagnostics.stale_certified_policy
    assert diagnostics.uncertified_learning


def test_delayed_attack_poison_update_is_incremental_and_clipped():
    updated = delayed.poisoned_candidate(
        np.asarray([17.5, -4.8]),
        gain_step=2.0,
        bias_step=-0.5,
    )

    np.testing.assert_allclose(updated, np.asarray([18.0, -5.0]))


def test_delayed_attack_deployment_envelope_is_interior_and_reproducible():
    states = delayed.deployment_envelope()

    assert len(states) == 42
    assert len({tuple(state) for state in states}) == 42
    assert all(gate.inside_safe_box(state) for state in states)


def test_delayed_attack_certification_envelope_is_deterministic_and_interior():
    first = delayed.certification_envelope()
    second = delayed.certification_envelope()

    assert len(first) == 160
    assert len({tuple(state) for state in first}) == 160
    assert all(gate.inside_safe_box(state) for state in first)
    np.testing.assert_allclose(first, second)


def test_commit_gate_stops_before_certificate_guard_margin_is_lost():
    states = [np.zeros(4)]
    with (
        patch.object(delayed, "baseline_viable_states", return_value=states),
        patch.object(
            delayed,
            "casadi_deployment_score",
            side_effect=[
                (0, -0.10, 0),  # Trusted baseline.
                (0, -0.01, 0),  # Fraction 0.05 is accepted.
                (0, -0.004, 0),  # Fraction 0.10 loses the 0.005 guard.
            ],
        ),
    ):
        committed = delayed.commit_backtracked_snapshot(
            np.zeros(2),
            np.asarray([10.0, 0.0]),
            DummyController(),
            {},
            object(),
            action_low=-10.0,
            action_high=10.0,
            deployment_steps=10,
            certificate_states=states,
            certificate_guard_margin=0.005,
        )

    np.testing.assert_allclose(committed, np.asarray([0.5, 0.0]))


def test_repeated_poison_snapshot_reaches_parameter_bounds():
    snapshot = delayed.repeated_poison_snapshot(
        np.asarray([2.0, -0.5]),
        poison_steps=12,
    )

    np.testing.assert_allclose(snapshot, np.asarray([18.0, -5.0]))


def test_reward_poisoning_changes_only_rewards_and_respects_budget():
    noise = np.asarray([-2.0, -0.5, 0.5, 2.0])
    features = np.asarray(
        [[-0.5, 1.0], [-0.1, 1.0], [0.1, 1.0], [0.5, 1.0]]
    )
    learner = np.zeros(2)
    target = np.asarray([3.6, -5.0])

    poisoned = reinforce.reward_poison(
        noise,
        features,
        learner,
        target,
        budget=2.0,
        temperature=1.0,
    )

    assert poisoned.shape == (4,)
    assert np.max(np.abs(poisoned)) <= 2.0
    assert np.any(np.abs(poisoned) > 0.0)


def test_reinforce_gradient_is_zero_for_constant_logged_return():
    gradient = reinforce.reinforce_gradient(
        np.asarray([[0.0, 1.0]]),
        np.asarray([0.5]),
        np.asarray([1.0]),
        np.asarray([1.0]),
        sigma=0.8,
        gamma=0.97,
    )

    np.testing.assert_allclose(gradient, np.zeros(2))


def test_reinforce_parameterization_round_trip():
    effective = np.asarray([12.0, -3.0])

    np.testing.assert_allclose(
        reinforce.to_effective_params(reinforce.to_learner_params(effective)),
        effective,
    )


def test_quadrotor_actor_features_use_declared_pitch_scales():
    states = np.asarray(
        [
            [0.0, 0.0, 1.0, 0.0, 0.1, -0.5],
            [0.0, 0.0, 1.0, 0.0, -0.2, 1.0],
        ]
    )

    np.testing.assert_allclose(
        quad.actor_features(states),
        np.asarray([[0.5, -0.5], [-1.0, 1.0]]),
    )


def test_quadrotor_policy_clips_before_environment_interface():
    class Bundle:
        goal = np.zeros(6)
        gain = np.zeros((2, 6))
        equilibrium_action = np.asarray([0.13, 0.13])
        action_low = np.asarray([0.05, 0.05])
        action_high = np.asarray([0.30, 0.30])

    snapshot = np.asarray([[10.0, 10.0], [-10.0, -10.0]])
    actions = quad.policy_actions(
        Bundle(),
        np.asarray([[0.0, 0.0, 1.0, 0.0, 0.2, 1.0]]),
        snapshot,
    )

    np.testing.assert_allclose(actions, np.asarray([[0.30, 0.05]]))


def test_quadrotor_reward_poison_is_bounded_and_target_aligned():
    features = np.asarray(
        [[0.5, 0.2], [-0.3, 0.4], [0.2, -0.6], [-0.4, -0.2]]
    )
    noise = np.asarray(
        [[0.01, -0.005], [-0.007, 0.008], [0.006, 0.009], [-0.01, -0.004]]
    )
    learner = np.zeros((2, 2))
    target = np.asarray([[-0.04, 0.008], [0.04, -0.008]])
    dones = np.asarray([0.0, 0.0, 0.0, 1.0])

    poison = quad_reinforce.reward_poison(
        noise,
        features,
        learner,
        target,
        budget=0.5,
        temperature=0.5,
        sigma=0.01,
        gamma=0.97,
        dones=dones,
    )
    gradient = quad_reinforce.reinforce_gradient(
        features,
        noise,
        poison,
        dones,
        sigma=0.01,
        gamma=0.97,
    )

    assert poison.shape == (4,)
    assert np.max(np.abs(poison)) <= 0.5
    assert float(np.sum(gradient * target)) > 0.0


def test_quadrotor_commit_stops_at_first_failed_fraction():
    pending = np.asarray([[-0.04, 0.008], [0.04, -0.008]])
    first = np.full((21, 1), -1, dtype=int)
    margins = np.full((21, 1), -0.1, dtype=float)
    margins[1, 0] = -0.01
    margins[2, 0] = -0.001  # Fraction 0.10 fails the 0.005 guard.
    margins[3:, 0] = -0.02  # A disconnected safe island must be ignored.
    with patch.object(
        quad,
        "casadi_snapshot_outcomes",
        return_value=(first, margins),
    ):
        committed, fraction = quad.commit_backtracked_snapshot(
            object(),
            pending,
            [np.zeros(6)],
            steps=10,
            guard_margin=0.005,
        )

    assert fraction == 0.05
    np.testing.assert_allclose(committed, 0.05 * pending)


def test_quadrotor_spread_subset_is_deterministic_and_not_prefix_only():
    states = [np.full(6, value, dtype=float) for value in range(10)]

    selected = quad.spread_subset(states, 4)

    np.testing.assert_allclose(
        np.asarray(selected)[:, 0], np.asarray([0.0, 3.0, 6.0, 9.0])
    )


def test_ppo_parameter_alignment_poison_is_bounded_and_nonzero():
    alignment = np.asarray([-2.0, -1.0, 1.0, 2.0])
    dones = np.asarray([0.0, 0.0, 0.0, 1.0])

    poison = quad_ppo_poison.poison_from_score_alignment(
        alignment,
        dones,
        budget=0.5,
        temperature=1.0,
        gamma=0.99,
    )

    assert poison.shape == alignment.shape
    assert np.max(np.abs(poison)) <= 0.5
    assert np.any(np.abs(poison) > 0.0)


def test_ppo_normalized_state_margin_is_signed_and_scale_free():
    center = 0.5 * (quad.SAFE_LOW + quad.SAFE_HIGH)
    span = quad.SAFE_HIGH - quad.SAFE_LOW

    assert quad_ppo_poison.normalized_state_margin(center) == -0.5
    assert quad_ppo_poison.normalized_state_margin(quad.SAFE_HIGH) == 0.0
    np.testing.assert_allclose(
        quad_ppo_poison.normalized_state_margin(quad.SAFE_HIGH + 0.1 * span),
        0.1,
    )


def test_benign_utility_actual_action_applies_bias_before_clipping():
    class Bundle:
        action_low = np.asarray([0.05, 0.05])
        action_high = np.asarray([0.30, 0.30])

    commands = np.asarray([[0.2995, 0.0505], [0.13, 0.13]])
    bias = quad_utility.bias_vector(0.001)

    np.testing.assert_allclose(
        quad_utility.actual_actions(Bundle(), commands, bias),
        np.asarray([[0.30, 0.05], [0.131, 0.129]]),
    )


def test_benign_utility_shift_config_matches_trusted_bias_vector():
    class Bundle:
        task_config = {"disturbances": None}

    config = quad_utility.task_config_with_bias(Bundle(), 0.002)
    disturbance = config["disturbances"]["action"][0]

    assert disturbance["disturbance_func"] == "step"
    assert disturbance["magnitude"] == 0.002
    assert disturbance["mask"] == [1.0, -1.0]
    assert disturbance["step_offset"] == 0


def test_benign_utility_separates_realized_state_violation_from_saturation():
    class Env:
        state = 0.5 * (quad.SAFE_LOW + quad.SAFE_HIGH)
        current_noisy_physical_action = np.asarray([0.055, 0.13])
        current_clipped_action = np.asarray([0.056, 0.13])

    assert not quad_utility.physical_state_violation(Env())
    assert quad_utility.actuator_saturated(Env())


def test_benign_utility_gate_stops_before_disconnected_safe_island():
    current = np.zeros((2, 2))
    candidate = np.ones((2, 2))
    first = np.full((21, 1), -1, dtype=int)
    margins = np.full((21, 1), -0.1, dtype=float)
    margins[2, 0] = 0.01
    margins[3:, 0] = -0.1
    with patch.object(
        quad_utility,
        "biased_snapshot_outcomes",
        return_value=(first, margins),
    ):
        projected, fraction, current_certified, _runtime = (
            quad_utility.project_lifecycle_update(
                object(),
                current,
                candidate,
                [np.zeros(6)],
                np.zeros(2),
                steps=100,
                guard_margin=0.003,
            )
        )

    assert current_certified
    assert fraction == 0.05
    np.testing.assert_allclose(projected, 0.05 * candidate)


def test_tdsc_core_table_is_derived_from_locked_aggregate_artifacts():
    rows = tdsc_table.locked_rows()
    lookup = {(row.system, row.mechanism): row for row in rows}

    assert len(rows) == 8
    assert lookup[("Cartpole", "Poisoned action-only")].violations == 38
    assert lookup[("Cartpole", "Poisoned action-only")].rollouts == 188
    assert lookup[("Quadrotor", "Poisoned action-only")].violations == 68
    assert lookup[("Quadrotor", "Poisoned action-only")].rollouts == 72
    assert ("Quadrotor", "Permanent backup shield") not in lookup
    assert ("Quadrotor", "Official linear MPSC") not in lookup

    coverage_rows = tdsc_table.locked_coverage_rows()
    coverage_lookup = {row.mechanism: row for row in coverage_rows}
    assert len(coverage_rows) == 4
    assert coverage_lookup["Clean REINFORCE"].false_acceptances == 0
    assert coverage_lookup["Poisoned action-only"].pybullet_violations == 403
    assert coverage_lookup["Poisoned commit"].certified_pairs == 408
    assert coverage_lookup["Poisoned commit"].false_rejections == 3
    assert coverage_lookup["Always-freeze"].certificate_coverage == 1.0


def test_coverage_audit_reconstructs_locked_snapshots_without_retraining():
    snapshots = coverage.load_locked_snapshots(
        coverage.SNAPSHOT_SOURCE,
        coverage.TRACE_SOURCE,
        [2040, 2041, 2042],
    )
    lookup = {
        (row.learner_seed, row.mechanism): row.snapshot for row in snapshots
    }

    assert len(snapshots) == 12
    np.testing.assert_allclose(
        lookup[(2040, "poisoned_always_freeze_snapshot")],
        np.zeros((2, 2)),
    )
    np.testing.assert_allclose(
        lookup[(2040, "poisoned_commit_gate_snapshot")],
        0.55 * lookup[(2040, "poisoned_action_only_snapshot")],
    )
    np.testing.assert_allclose(
        lookup[(2041, "poisoned_commit_gate_snapshot")],
        0.40 * lookup[(2041, "poisoned_action_only_snapshot")],
    )
    np.testing.assert_allclose(
        lookup[(2042, "poisoned_commit_gate_snapshot")],
        0.70 * lookup[(2042, "poisoned_action_only_snapshot")],
    )


def test_coverage_confusion_labels_are_explicit():
    assert coverage.classify(True, True) == "true_acceptance"
    assert coverage.classify(True, False) == "false_acceptance"
    assert coverage.classify(False, True) == "false_rejection"
    assert coverage.classify(False, False) == "true_rejection"
