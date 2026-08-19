#!/usr/bin/env python3
"""Reward-to-parameter geometry for normalized REINFORCE updates.

The residual REINFORCE learners in this artifact center and standardize
reward-to-go advantages before applying the score-function gradient.  Hence a
bounded reward box does *not* map to a parameter zonotope.  Before gradient and
parameter clipping, it maps as

    delta -> y(delta) / ||y(delta)|| -> theta_next(delta),

where ``y`` is the centered reward-to-go vector.  This module reconstructs
that map exactly and computes the worst positive support of a parameter
halfspace by second-order-cone feasibility and bisection.
"""

from __future__ import annotations

from dataclasses import dataclass

import cvxpy as cp
import numpy as np


Array = np.ndarray


@dataclass(frozen=True)
class HalfspaceSupport:
    """Worst reachable value for one halfspace in gate coordinates."""

    support: float
    clean_value: float
    ratio_support: float
    reward_delta: Array
    minimum_centered_return_norm: float
    solver_status: str


@dataclass(frozen=True)
class ClippedHalfspaceSupport:
    """Positive support with exact global Euclidean gradient clipping."""

    support: float
    clean_value: float
    ratio_support: float
    reward_delta: Array
    witness_value: float
    witness_support_error: float
    witness_centered_return_norm: float
    witness_raw_gradient_norm: float
    witness_gradient_clipped: bool
    solver_status: str


def reward_to_go_operator(dones: Array, gamma: float) -> Array:
    """Return ``H`` such that reward-to-go equals ``H @ rewards``.

    A terminal marker at index ``j`` prevents reward ``j + 1`` from
    contributing to any return at or before ``j``.
    """

    dones = np.asarray(dones, dtype=float).reshape(-1)
    horizon = len(dones)
    operator = np.zeros((horizon, horizon), dtype=float)
    for start in range(horizon):
        alive = 1.0
        for end in range(start, horizon):
            if end > start:
                alive *= 1.0 - dones[end - 1]
            operator[start, end] = (float(gamma) ** (end - start)) * alive
    return operator


def centered_return_operator(dones: Array, gamma: float) -> Array:
    """Return the linear operator for mean-centered reward-to-go."""

    horizon = len(np.asarray(dones).reshape(-1))
    centering = np.eye(horizon) - np.ones((horizon, horizon)) / float(horizon)
    return centering @ reward_to_go_operator(dones, gamma)


def gaussian_score_matrix(features: Array, noise: Array, sigma: float) -> Array:
    """Return per-step Gaussian-mean score rows for a scalar action."""

    features = np.asarray(features, dtype=float)
    noise = np.asarray(noise, dtype=float).reshape(-1)
    if features.ndim != 2 or features.shape[0] != len(noise):
        raise ValueError("features must have shape (T, d) and match noise")
    return noise[:, None] * features / float(sigma**2)


def normalized_reinforce_gradient(
    score_matrix: Array,
    rewards: Array,
    centered_operator: Array,
    *,
    normalization_tolerance: float = 1e-8,
) -> Array:
    """Reconstruct the artifact's centered/standardized REINFORCE gradient."""

    scores = np.asarray(score_matrix, dtype=float)
    centered_returns = np.asarray(centered_operator, dtype=float) @ np.asarray(
        rewards, dtype=float
    )
    scale = float(np.linalg.norm(centered_returns) / np.sqrt(len(centered_returns)))
    advantages = centered_returns
    if scale > normalization_tolerance:
        advantages = advantages / scale
    return np.mean(advantages[:, None] * scores, axis=0)


def _solve(
    problem: cp.Problem,
    *,
    solver: str,
    inaccurate_ok: bool = True,
) -> str:
    """Solve with a deterministic primary solver and an SCS fallback."""

    try:
        problem.solve(solver=solver)
    except cp.error.SolverError:
        problem.solve(solver="SCS", eps=1e-7, max_iters=100_000)
    accepted = {"optimal"}
    if inaccurate_ok:
        accepted.add("optimal_inaccurate")
    return str(problem.status) if problem.status in accepted else ""


def minimum_centered_return_norm(
    rewards: Array,
    centered_operator: Array,
    reward_budget: float,
    *,
    solver: str = "CLARABEL",
) -> float:
    """Compute the minimum denominator over the bounded reward-attack box."""

    rewards = np.asarray(rewards, dtype=float).reshape(-1)
    operator = np.asarray(centered_operator, dtype=float)
    delta = cp.Variable(len(rewards))
    centered = operator @ (rewards + delta)
    problem = cp.Problem(
        cp.Minimize(cp.norm(centered, 2)),
        [delta <= reward_budget, delta >= -reward_budget],
    )
    status = _solve(problem, solver=solver)
    if not status or problem.value is None:
        raise RuntimeError("failed to minimize centered-return norm")
    return float(problem.value)


def worst_positive_halfspace_support(
    *,
    current_params: Array,
    rewards: Array,
    centered_operator: Array,
    score_matrix: Array,
    reward_budget: float,
    actor_lr: float,
    coordinate_map: Array,
    halfspace_row: Array,
    bisection_steps: int = 45,
    denominator_tolerance: float = 1e-7,
    solver: str = "CLARABEL",
) -> HalfspaceSupport:
    """Compute the exact worst positive halfspace support before clipping.

    ``coordinate_map`` maps learner parameters to the coordinates used by the
    certificate gate.  The result assumes:

    1. advantage standardization is active for every reward vector in the
       attack box;
    2. neither gradient-norm clipping nor parameter clipping activates; and
    3. the maximum normalized reward influence on the requested row is
       non-negative.

    Under these assumptions, feasibility of a candidate ratio ``t`` is the
    second-order-cone constraint ``q^T y >= t ||y||_2``.
    """

    current = np.asarray(current_params, dtype=float).reshape(-1)
    rewards = np.asarray(rewards, dtype=float).reshape(-1)
    operator = np.asarray(centered_operator, dtype=float)
    scores = np.asarray(score_matrix, dtype=float)
    transform = np.asarray(coordinate_map, dtype=float)
    row = np.asarray(halfspace_row, dtype=float).reshape(-1)
    horizon = len(rewards)
    if operator.shape != (horizon, horizon):
        raise ValueError("centered_operator must have shape (T, T)")
    if scores.shape[0] != horizon or scores.shape[1] != len(current):
        raise ValueError("score_matrix must have shape (T, parameter_dim)")
    if transform.shape[1] != len(current) or transform.shape[0] != len(row):
        raise ValueError("coordinate_map or halfspace_row has incompatible shape")

    minimum_norm = minimum_centered_return_norm(
        rewards, operator, reward_budget, solver=solver
    )
    if minimum_norm <= denominator_tolerance:
        raise ValueError(
            "advantage normalization can become singular inside the reward box"
        )

    current_gate_params = transform @ current
    clean_gradient = normalized_reinforce_gradient(scores, rewards, operator)
    clean_next = transform @ (current + float(actor_lr) * clean_gradient)
    clean_value = float(row @ clean_next)

    q = (
        float(actor_lr)
        * scores
        @ (transform.T @ row)
        / np.sqrt(float(horizon))
    )
    upper = float(np.linalg.norm(q))
    lower = 0.0
    best_delta: Array | None = None
    best_status = ""
    if upper > 1e-14:
        for _ in range(bisection_steps):
            candidate = 0.5 * (lower + upper)
            delta = cp.Variable(horizon)
            centered = operator @ (rewards + delta)
            problem = cp.Problem(
                cp.Minimize(0),
                [
                    delta <= reward_budget,
                    delta >= -reward_budget,
                    candidate * cp.norm(centered, 2) <= q @ centered,
                ],
            )
            status = _solve(problem, solver=solver)
            if status:
                lower = candidate
                best_delta = np.asarray(delta.value, dtype=float).reshape(-1)
                best_status = status
            else:
                upper = candidate

    if best_delta is None:
        best_delta = np.zeros(horizon, dtype=float)
        centered = operator @ rewards
        ratio = float(q @ centered / np.linalg.norm(centered))
        if ratio < -1e-10:
            # Feasibility of q^T y >= t ||y|| is convex only for t >= 0.
            # If no non-negative ratio is reachable, zero is a sound (but
            # potentially unattainable) upper bound for robust containment.
            # Keep this case explicit so callers do not treat it as an exact
            # witness.
            lower = 0.0
            best_status = "nonpositive_conservative_zero"
        else:
            lower = max(ratio, 0.0)
            best_status = "clean_nonnegative"

    support = float(row @ current_gate_params + lower)
    return HalfspaceSupport(
        support=support,
        clean_value=clean_value,
        ratio_support=float(lower),
        reward_delta=best_delta,
        minimum_centered_return_norm=minimum_norm,
        solver_status=best_status,
    )


def worst_positive_halfspace_support_with_gradient_clipping(
    *,
    current_params: Array,
    rewards: Array,
    centered_operator: Array,
    score_matrix: Array,
    reward_budget: float,
    actor_lr: float,
    coordinate_map: Array,
    halfspace_row: Array,
    gradient_cap: float,
    bisection_steps: int = 45,
    normalization_tolerance: float = 1e-8,
    solver: str = "CLARABEL",
) -> ClippedHalfspaceSupport:
    """Compute exact positive support across normalization zeros and grad clipping.

    For a nonzero centered-return vector ``y``, let ``B = S.T / sqrt(T)``.
    Global Euclidean gradient clipping maps the standardized raw gradient to

        B y / max(||y||, ||B y|| / gradient_cap).

    This ratio is positively homogeneous.  We therefore optimize over the
    conic hull of the centered-return zonotope and impose a unit positive
    numerator.  For a fixed candidate support ``t``, the two denominator
    branches become second-order-cone constraints.  Unlike the direct
    formulation, the unit-numerator equality excludes the zero-vector
    degeneracy when the reward box contains a normalization singularity.

    The result remains conditional on coordinatewise parameter clipping being
    inactive over the complete reward box.  Callers must establish that
    separately before treating this support as an exact next-parameter bound.
    """

    current = np.asarray(current_params, dtype=float).reshape(-1)
    rewards = np.asarray(rewards, dtype=float).reshape(-1)
    operator = np.asarray(centered_operator, dtype=float)
    scores = np.asarray(score_matrix, dtype=float)
    transform = np.asarray(coordinate_map, dtype=float)
    row = np.asarray(halfspace_row, dtype=float).reshape(-1)
    horizon = len(rewards)
    if operator.shape != (horizon, horizon):
        raise ValueError("centered_operator must have shape (T, T)")
    if scores.shape != (horizon, len(current)):
        raise ValueError("score_matrix must have shape (T, parameter_dim)")
    if transform.shape != (len(row), len(current)):
        raise ValueError("coordinate_map or halfspace_row has incompatible shape")
    if reward_budget < 0.0:
        raise ValueError("reward_budget must be non-negative")
    if gradient_cap <= 0.0:
        raise ValueError("gradient_cap must be positive")

    root_horizon = np.sqrt(float(horizon))
    gradient_map = scores.T / root_horizon
    learner_direction = transform.T @ row
    numerator = float(actor_lr) * gradient_map.T @ learner_direction
    centered_clean = operator @ rewards

    clean_gradient = normalized_reinforce_gradient(
        scores,
        rewards,
        operator,
        normalization_tolerance=normalization_tolerance,
    )
    clean_norm = float(np.linalg.norm(clean_gradient))
    if clean_norm > gradient_cap:
        clean_gradient = clean_gradient * (float(gradient_cap) / clean_norm)
    clean_next = transform @ (current + float(actor_lr) * clean_gradient)
    clean_value = float(row @ clean_next)
    current_value = float(row @ (transform @ current))

    # The maximum numerator over the original reward box is analytic.  If it
    # is nonpositive, no positive-support conic normalization exists.
    numerator_center = float(numerator @ centered_clean)
    numerator_radius = float(
        reward_budget * np.linalg.norm(operator.T @ numerator, ord=1)
    )
    if numerator_center + numerator_radius <= 1e-12:
        zero_delta = np.zeros(horizon, dtype=float)
        return ClippedHalfspaceSupport(
            support=current_value,
            clean_value=clean_value,
            ratio_support=0.0,
            reward_delta=zero_delta,
            witness_value=current_value,
            witness_support_error=0.0,
            witness_centered_return_norm=float(np.linalg.norm(centered_clean)),
            witness_raw_gradient_norm=float(clean_norm),
            witness_gradient_clipped=clean_norm > gradient_cap,
            solver_status="nonpositive_conservative_zero",
        )

    # Cauchy--Schwarz bounds the standardized branch; the cap supplies a
    # second independent upper bound in learner-parameter coordinates.
    upper = min(
        float(np.linalg.norm(numerator)),
        float(actor_lr) * float(gradient_cap) * float(np.linalg.norm(learner_direction)),
    )
    lower = 0.0
    best_y: Array | None = None
    best_cone_scale: float | None = None
    best_scaled_delta: Array | None = None
    best_status = ""
    for _ in range(bisection_steps):
        candidate = 0.5 * (lower + upper)
        cone_scale = cp.Variable(nonneg=True)
        scaled_delta = cp.Variable(horizon)
        cone_y = cone_scale * centered_clean + operator @ scaled_delta
        problem = cp.Problem(
            cp.Minimize(0),
            [
                scaled_delta <= reward_budget * cone_scale,
                scaled_delta >= -reward_budget * cone_scale,
                numerator @ cone_y == 1.0,
                candidate * cp.norm(cone_y, 2) <= 1.0,
                (candidate / float(gradient_cap))
                * cp.norm(gradient_map @ cone_y, 2)
                <= 1.0,
            ],
        )
        status = _solve(problem, solver=solver)
        if status:
            lower = candidate
            best_y = np.asarray(cone_y.value, dtype=float).reshape(-1)
            best_cone_scale = float(cone_scale.value)
            best_scaled_delta = np.asarray(
                scaled_delta.value, dtype=float
            ).reshape(-1)
            best_status = status
        else:
            upper = candidate

    if best_y is None or best_cone_scale is None or best_scaled_delta is None:
        raise RuntimeError("positive numerator exists but conic support solve failed")

    # Recover a reward-box witness by maximizing its positive numerator under
    # the two SOC inequalities at a negligibly relaxed support value.  Direct
    # fixed-t feasibility would admit y=0; the linear maximization selects a
    # nonzero point whenever the homogenized problem has positive support.
    delta = cp.Variable(horizon)
    centered = operator @ (rewards + delta)
    recovery_support = max(0.0, lower * (1.0 - 1e-7) - 1e-9)
    recovery = cp.Problem(
        cp.Maximize(numerator @ centered),
        [
            delta <= reward_budget,
            delta >= -reward_budget,
            recovery_support * cp.norm(centered, 2) <= numerator @ centered,
            (recovery_support / float(gradient_cap))
            * cp.norm(gradient_map @ centered, 2)
            <= numerator @ centered,
        ],
    )
    recovery_status = _solve(recovery, solver=solver)
    if recovery_status and delta.value is not None:
        reward_delta = np.clip(
            np.asarray(delta.value, dtype=float).reshape(-1),
            -reward_budget,
            reward_budget,
        )
        witness_recovery = f"direct_{recovery_status}"
    else:
        # Numerical cone solutions can describe a ray that misses the compact
        # reward box by solver tolerance when imposed again as an exact vector
        # equality.  The homogenized variables themselves always provide a
        # witness: w/lambda is the corresponding reward perturbation.
        if best_cone_scale <= 1e-12:
            raise RuntimeError("homogenized witness has zero cone scale")
        reward_delta = best_scaled_delta / best_cone_scale
        if np.max(np.abs(reward_delta)) > reward_budget + 1e-3:
            raise RuntimeError("homogenized witness exceeds reward budget")
        reward_delta = np.clip(reward_delta, -reward_budget, reward_budget)
        witness_recovery = "homogenized_fallback"
    witness_y = operator @ (rewards + reward_delta)
    witness_norm = float(np.linalg.norm(witness_y))
    active_threshold = float(normalization_tolerance) * root_horizon
    if witness_norm <= active_threshold:
        raise RuntimeError(
            "conic support ray has no witness above normalization tolerance"
        )

    raw_gradient = gradient_map @ witness_y / witness_norm
    raw_gradient_norm = float(np.linalg.norm(raw_gradient))
    applied_gradient = raw_gradient.copy()
    gradient_clipped = raw_gradient_norm > gradient_cap
    if gradient_clipped:
        applied_gradient *= float(gradient_cap) / raw_gradient_norm
    witness_increment = float(
        actor_lr * learner_direction @ applied_gradient
    )
    witness_value = current_value + witness_increment
    support = current_value + lower
    return ClippedHalfspaceSupport(
        support=float(support),
        clean_value=clean_value,
        ratio_support=float(lower),
        reward_delta=reward_delta,
        witness_value=float(witness_value),
        witness_support_error=float(abs(witness_value - support)),
        witness_centered_return_norm=witness_norm,
        witness_raw_gradient_norm=raw_gradient_norm,
        witness_gradient_clipped=gradient_clipped,
        solver_status=f"{best_status};recovery_{witness_recovery}",
    )
