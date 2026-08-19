#!/usr/bin/env python3
"""Attacked-history plausible-set LifecycleGate on Safe-Control-Gym cartpole.

This runner removes the oracle-state assumption from
``safe_control_gym_continuous_observation_attack.py``.  The gate only sees the
attacked observation ``z`` and an L_inf attack radius ``rho``.  It builds the
plausible-state box X_A(z), computes a sampled robust safe-action kernel, and
certifies a low-dimensional residual update against a local future
attacked-observation grid.

The implementation is deliberately conservative and explicit.  The gate uses a
finite action/state grid.  The default kernel backend uses Safe-Control-Gym's
CasADi discrete dynamics; an official CBF sampled oracle is also available for
small runs.
"""

from __future__ import annotations

import argparse
import contextlib
import csv
import io
import os
from dataclasses import asdict, dataclass
from functools import partial
from itertools import product
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import yaml

from continuous_adaptive_attacker import AttackMargins, AttackWeights, cem_optimize


ROOT = Path(__file__).resolve().parent
SCG_ROOT = ROOT / "external" / "safe-control-gym"
RESULTS_DIR = ROOT / "results"

SAFE_LOW = np.asarray([-2.0, -2.0, -0.2, -2.0], dtype=float)
SAFE_HIGH = np.asarray([2.0, 2.0, 0.2, 2.0], dtype=float)
STATE_CLIP_LOW = np.asarray([-2.4, -20.0, -np.pi, -20.0], dtype=float)
STATE_CLIP_HIGH = np.asarray([2.4, 20.0, np.pi, 20.0], dtype=float)
THETA_LIMIT = 0.2
PARAM_LOW = np.asarray([-18.0, -5.0], dtype=float)
PARAM_HIGH = np.asarray([18.0, 5.0], dtype=float)


def configure_matplotlib() -> None:
    cache_dir = Path("/tmp/matplotlib-lifecycle-gate")
    cache_dir.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("MPLCONFIGDIR", str(cache_dir))


configure_matplotlib()

import safe_control_gym  # noqa: F401
from safe_control_gym.utils.registration import get_config, make


Params = np.ndarray
Interval = tuple[float, float] | None


@dataclass(frozen=True)
class CartpoleModel:
    dt: float
    pole_length: float
    pole_mass: float
    cart_mass: float
    gravity: float = 9.8


@dataclass(frozen=True)
class KernelResult:
    interval: Interval
    valid_actions: tuple[float, ...]
    width: float
    empty_reason: str


@dataclass(frozen=True)
class ParamConstraints:
    rows: np.ndarray
    bounds: np.ndarray
    min_kernel_width: float
    empty_count: int


@dataclass
class StepDiagnostics:
    learn_update: bool
    param_cert_accept: bool
    action_cert_accept: bool
    stale_certified_policy: bool
    uncertified_learning: bool
    intervention: bool
    empty_kernel: bool
    action_correction: float
    param_projection_norm: float
    kernel_width: float
    param_violation: float


@dataclass
class GateRunSummary:
    benchmark: str
    task: str
    controller: str
    mechanism: str
    kernel_backend: str
    attack_kernel_backend: str
    steps: int
    budget: float
    plausible_radius: float
    future_grid_points: int
    action_grid_size: int
    mean_reward: float
    constraint_violation_steps: int
    constraint_violation_step_rate: float
    unsafe_certified_steps: int
    unsafe_certified_rate: float
    stale_certified_policy_steps: int
    stale_certified_policy_rate: float
    uncertified_learning_steps: int
    uncertified_learning_rate: float
    learn_updates: int
    learn_update_rate: float
    interventions: int
    intervention_rate: float
    empty_kernel_steps: int
    empty_kernel_rate: float
    mean_kernel_width: float
    mean_action_correction: float
    mean_param_projection_norm: float
    mean_attack_linf: float
    mean_attacker_score: float
    final_theta_gain: float
    final_bias: float
    max_param_violation: float


def deep_merge(base: dict[str, Any], updates: dict[str, Any]) -> dict[str, Any]:
    for key, value in updates.items():
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            deep_merge(base[key], value)
        else:
            base[key] = value
    return base


def read_yaml(path: Path) -> dict[str, Any]:
    with path.open() as f:
        return yaml.safe_load(f) or {}


def build_configs(seed: int) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    task_config = dict(get_config("cartpole"))
    lqr_config = dict(get_config("lqr"))
    cbf_config = dict(get_config("cbf"))

    lqr_dir = SCG_ROOT / "examples" / "lqr" / "config_overrides" / "cartpole"
    cbf_dir = SCG_ROOT / "examples" / "cbf" / "config_overrides"
    for path in (lqr_dir / "cartpole_stab.yaml", lqr_dir / "lqr_cartpole_stab.yaml"):
        override = read_yaml(path)
        if "task_config" in override:
            deep_merge(task_config, override["task_config"])
        if "algo_config" in override:
            deep_merge(lqr_config, override["algo_config"])

    # Reuse the official CBF cartpole task because it gives tight, meaningful
    # state/input constraints for safety-filter evaluation.
    cbf_task_override = read_yaml(cbf_dir / "cartpole_config.yaml")
    cbf_filter_override = read_yaml(cbf_dir / "cbf_config.yaml")
    deep_merge(task_config, cbf_task_override["task_config"])
    deep_merge(cbf_config, cbf_filter_override["sf_config"])
    task_config["gui"] = False
    task_config["seed"] = seed
    lqr_config["seed"] = seed
    cbf_config["seed"] = seed
    return task_config, lqr_config, cbf_config


@contextlib.contextmanager
def silence():
    with contextlib.redirect_stdout(io.StringIO()):
        yield


def cartpole_step(model: CartpoleModel, x: np.ndarray, u: float) -> np.ndarray:
    x_pos, x_dot, theta, theta_dot = np.asarray(x, dtype=float)
    length = model.pole_length
    pole_mass = model.pole_mass
    cart_mass = model.cart_mass
    total_mass = pole_mass + cart_mass
    ml = pole_mass * length
    temp = (u + ml * theta_dot * theta_dot * np.sin(theta)) / total_mass
    denom = length * (4.0 / 3.0 - pole_mass * np.cos(theta) ** 2 / total_mass)
    theta_ddot = (model.gravity * np.sin(theta) - np.cos(theta) * temp) / denom
    x_ddot = temp - ml * theta_ddot * np.cos(theta) / total_mass
    x_dot_vec = np.asarray([x_dot, x_ddot, theta_dot, theta_ddot], dtype=float)
    return np.asarray(x, dtype=float) + model.dt * x_dot_vec


def cartpole_step_batch(model: CartpoleModel, samples: np.ndarray, actions: np.ndarray) -> np.ndarray:
    """Vectorized one-step prediction with shape (num_actions, num_samples, 4)."""
    x = samples[None, :, :]
    u = actions[:, None]
    x_dot = x[:, :, 1]
    theta = x[:, :, 2]
    theta_dot = x[:, :, 3]
    length = model.pole_length
    pole_mass = model.pole_mass
    cart_mass = model.cart_mass
    total_mass = pole_mass + cart_mass
    ml = pole_mass * length
    temp = (u + ml * theta_dot * theta_dot * np.sin(theta)) / total_mass
    denom = length * (4.0 / 3.0 - pole_mass * np.cos(theta) ** 2 / total_mass)
    theta_ddot = (model.gravity * np.sin(theta) - np.cos(theta) * temp) / denom
    x_ddot = temp - ml * theta_ddot * np.cos(theta) / total_mass
    x_dot_vec = np.stack(
        [
            np.broadcast_to(x_dot, temp.shape),
            x_ddot,
            np.broadcast_to(theta_dot, temp.shape),
            theta_ddot,
        ],
        axis=2,
    )
    return x + model.dt * x_dot_vec


def casadi_step_batch(fd_func: object, samples: np.ndarray, actions: np.ndarray) -> np.ndarray:
    """Evaluate Safe-Control-Gym's CasADi discrete dynamics on an action-state grid."""
    action_count = len(actions)
    sample_count = samples.shape[0]
    x0 = np.hstack([samples.T for _ in range(action_count)])
    p = np.repeat(np.asarray(actions, dtype=float), sample_count).reshape(1, -1)
    xf = np.asarray(fd_func(x0=x0, p=p)["xf"], dtype=float).T
    return xf.reshape(action_count, sample_count, samples.shape[1])


def cbf_accepts_action(
    cbf_filter: object,
    sample: np.ndarray,
    action: float,
    *,
    tolerance: float,
) -> bool:
    raw_action = np.asarray([action], dtype=float)
    lie = float(np.asarray(cbf_filter.lie_derivative(X=sample, u=raw_action)["LfV"]).reshape(-1)[0])
    barrier = cbf_filter.cbf(X=sample)["cbf"]
    alpha = float(np.asarray(cbf_filter.linear_func(x=barrier)["y"]).reshape(-1)[0])
    return bool(-alpha - lie <= tolerance)


def inside_safe_box(x: np.ndarray, margin: float = 0.0) -> bool:
    return bool(np.all(x >= SAFE_LOW + margin) and np.all(x <= SAFE_HIGH - margin))


def plausible_box(z: np.ndarray, rho: float) -> tuple[np.ndarray, np.ndarray]:
    low = np.maximum(np.asarray(z, dtype=float) - rho, STATE_CLIP_LOW)
    high = np.minimum(np.asarray(z, dtype=float) + rho, STATE_CLIP_HIGH)
    return low, high


def box_samples(low: np.ndarray, high: np.ndarray, include_center: bool = True) -> np.ndarray:
    samples = [np.asarray(values, dtype=float) for values in product(*zip(low, high))]
    if include_center:
        samples.append((low + high) / 2.0)
    return np.vstack(samples)


def safe_kernel_for_observation(
    z: np.ndarray,
    rho: float,
    model: CartpoleModel,
    action_grid: np.ndarray,
    *,
    guard_margin: float,
    kernel_backend: str,
    casadi_fd_func: object | None = None,
    cbf_filter: object | None = None,
    cbf_action_tolerance: float = 1e-5,
) -> KernelResult:
    low, high = plausible_box(z, rho)
    samples = box_samples(low, high)
    if not all(inside_safe_box(sample, margin=0.0) for sample in samples):
        return KernelResult(None, tuple(), 0.0, "plausible_state_not_safe")

    if kernel_backend == "euler":
        next_states = cartpole_step_batch(model, samples, np.asarray(action_grid, dtype=float))
        valid_mask = np.all(next_states >= SAFE_LOW[None, None, :] + guard_margin, axis=(1, 2))
        valid_mask &= np.all(next_states <= SAFE_HIGH[None, None, :] - guard_margin, axis=(1, 2))
        valid = [float(action) for action in action_grid[valid_mask]]
    elif kernel_backend == "casadi":
        if casadi_fd_func is None:
            raise ValueError("casadi kernel backend requires casadi_fd_func")
        next_states = casadi_step_batch(casadi_fd_func, samples, np.asarray(action_grid, dtype=float))
        valid_mask = np.all(next_states >= SAFE_LOW[None, None, :] + guard_margin, axis=(1, 2))
        valid_mask &= np.all(next_states <= SAFE_HIGH[None, None, :] - guard_margin, axis=(1, 2))
        valid = [float(action) for action in action_grid[valid_mask]]
    elif kernel_backend == "cbf_sampled":
        if cbf_filter is None:
            raise ValueError("cbf_sampled kernel backend requires cbf_filter")
        valid = []
        for action in action_grid:
            if all(cbf_accepts_action(cbf_filter, sample, float(action), tolerance=cbf_action_tolerance) for sample in samples):
                valid.append(float(action))
    elif kernel_backend == "mpsc_sampled":
        raise RuntimeError(
            "mpsc_sampled is not available in the current environment: "
            "Safe-Control-Gym linear_mpsc requires pytope/RPI artifacts."
        )
    else:
        raise ValueError(f"unknown kernel backend {kernel_backend}")

    if not valid:
        return KernelResult(None, tuple(), 0.0, "no_common_action")
    return KernelResult((min(valid), max(valid)), tuple(valid), max(valid) - min(valid), "")


def project_to_kernel(action: float, kernel: KernelResult) -> tuple[float, bool, float]:
    if kernel.interval is None:
        return action, False, 0.0
    valid_actions = np.asarray(kernel.valid_actions, dtype=float)
    if valid_actions.size == 0:
        return action, False, 0.0
    idx = int(np.argmin(np.abs(valid_actions - action)))
    projected = float(valid_actions[idx])
    return projected, True, abs(projected - action)


def future_observation_grid(z: np.ndarray, rho: float, span: float) -> list[np.ndarray]:
    """Local future attacked-observation grid used for parameter certification."""
    centers: list[np.ndarray] = []
    theta_min = SAFE_LOW[2] + rho
    theta_max = SAFE_HIGH[2] - rho
    theta_dot_min = SAFE_LOW[3] + rho
    theta_dot_max = SAFE_HIGH[3] - rho
    for d_theta, d_theta_dot in product((-span, 0.0, span), repeat=2):
        candidate = np.asarray(z, dtype=float).copy()
        candidate[2] = np.clip(candidate[2] + d_theta, theta_min, theta_max)
        candidate[3] = np.clip(candidate[3] + d_theta_dot, theta_dot_min, theta_dot_max)
        centers.append(candidate)

    deduped: list[np.ndarray] = []
    seen: set[tuple[float, ...]] = set()
    for candidate in centers:
        key = tuple(np.round(candidate, 6))
        if key not in seen:
            seen.add(key)
            deduped.append(candidate)
    return deduped


def residual_features(z: np.ndarray) -> np.ndarray:
    return np.asarray([float(z[2]), 1.0], dtype=float)


def residual_action(params: Params, z: np.ndarray) -> float:
    return float(residual_features(z) @ params)


def lqr_action(ctrl: object, z: np.ndarray, info: dict[str, Any]) -> float:
    return float(np.asarray(ctrl.select_action(z, info), dtype=float).reshape(-1)[0])


def total_policy_action(ctrl: object, z: np.ndarray, info: dict[str, Any], params: Params) -> float:
    return lqr_action(ctrl, z, info) + residual_action(params, z)


def poison_update(params: Params, attacked_obs: np.ndarray, *, gain_step: float, bias_step: float) -> Params:
    direction = np.sign(attacked_obs[2])
    if abs(direction) < 1e-12:
        direction = 1.0
    delta = np.asarray([gain_step, bias_step * direction], dtype=float)
    return np.minimum(np.maximum(params + delta, PARAM_LOW), PARAM_HIGH)


def parameter_constraints(
    ctrl: object,
    info: dict[str, Any],
    z: np.ndarray,
    rho: float,
    model: CartpoleModel,
    action_grid: np.ndarray,
    *,
    future_span: float,
    guard_margin: float,
    kernel_backend: str,
    casadi_fd_func: object | None,
    cbf_filter: object | None,
    cbf_action_tolerance: float,
) -> ParamConstraints | None:
    """Build the conjunction of all future-history policy constraints.

    Returning ``None`` means that the lifecycle-certified parameter set is
    infeasible.  In particular, a single empty future-history action kernel
    makes the universal lifecycle condition infeasible; it must not be
    dropped from the conjunction.
    """
    rows: list[np.ndarray] = []
    bounds: list[float] = []
    widths: list[float] = []
    for future_z in future_observation_grid(z, rho, future_span):
        kernel = safe_kernel_for_observation(
            future_z,
            rho,
            model,
            action_grid,
            guard_margin=guard_margin,
            kernel_backend=kernel_backend,
            casadi_fd_func=casadi_fd_func,
            cbf_filter=cbf_filter,
            cbf_action_tolerance=cbf_action_tolerance,
        )
        if kernel.interval is None:
            return None
        lower, upper = kernel.interval
        base = lqr_action(ctrl, future_z, info)
        phi = residual_features(future_z)
        rows.append(phi)
        bounds.append(upper - base)
        rows.append(-phi)
        bounds.append(base - lower)
        widths.append(kernel.width)

    if not rows:
        return None

    rows.extend(
        [
            np.asarray([1.0, 0.0]),
            np.asarray([-1.0, 0.0]),
            np.asarray([0.0, 1.0]),
            np.asarray([0.0, -1.0]),
        ]
    )
    bounds.extend([PARAM_HIGH[0], -PARAM_LOW[0], PARAM_HIGH[1], -PARAM_LOW[1]])
    return ParamConstraints(np.vstack(rows), np.asarray(bounds), min(widths), 0)


def max_param_violation(params: Params, constraints: ParamConstraints | None) -> float:
    if constraints is None:
        return float("inf")
    return float(max(np.max(constraints.rows @ params - constraints.bounds), 0.0))


def project_params(params: Params, constraints: ParamConstraints, max_iters: int = 1000) -> tuple[Params, bool]:
    projected = np.asarray(params, dtype=float).copy()
    for _ in range(max_iters):
        max_violation = 0.0
        for row, bound in zip(constraints.rows, constraints.bounds):
            violation = float(row @ projected - bound)
            if violation > 1e-10:
                norm_sq = float(row @ row)
                if norm_sq <= 1e-12:
                    continue
                projected -= violation * row / norm_sq
                max_violation = max(max_violation, violation)
        if max_violation < 1e-9:
            return projected, True
    return projected, max_param_violation(projected, constraints) < 1e-7


def params_changed(before: Params, after: Params, eps: float = 1e-8) -> bool:
    return bool(np.linalg.norm(before - after) > eps)


def make_model_from_env(env: object) -> CartpoleModel:
    return CartpoleModel(
        dt=float(env.CTRL_TIMESTEP),
        pole_length=float(env.EFFECTIVE_POLE_LENGTH),
        pole_mass=float(env.POLE_MASS),
        cart_mass=float(env.CART_MASS),
        gravity=float(env.GRAVITY_ACC),
    )


def action_grid_from_env(env: object, size: int) -> np.ndarray:
    low = float(np.asarray(env.action_space.low, dtype=float).reshape(-1)[0])
    high = float(np.asarray(env.action_space.high, dtype=float).reshape(-1)[0])
    return np.linspace(low, high, size)


def select_attack(
    *,
    ctrl: object,
    info: dict[str, Any],
    true_obs: np.ndarray,
    params: Params,
    rho: float,
    model: CartpoleModel,
    action_grid: np.ndarray,
    future_span: float,
    guard_margin: float,
    gain_step: float,
    bias_step: float,
    population: int,
    iterations: int,
    seed: int,
    attack_weights: AttackWeights,
    kernel_backend: str,
    casadi_fd_func: object | None,
    cbf_filter: object | None,
    cbf_action_tolerance: float,
) -> tuple[np.ndarray, float]:
    def evaluator(attack: np.ndarray) -> AttackMargins:
        attacked_obs = np.asarray(true_obs + attack, dtype=float)
        candidate_params = poison_update(params, attacked_obs, gain_step=gain_step, bias_step=bias_step)
        raw_action = total_policy_action(ctrl, attacked_obs, info, candidate_params)
        current_kernel = safe_kernel_for_observation(
            attacked_obs,
            rho,
            model,
            action_grid,
            guard_margin=guard_margin,
            kernel_backend=kernel_backend,
            casadi_fd_func=casadi_fd_func,
            cbf_filter=cbf_filter,
            cbf_action_tolerance=cbf_action_tolerance,
        )
        constraints = parameter_constraints(
            ctrl,
            info,
            attacked_obs,
            rho,
            model,
            action_grid,
            future_span=future_span,
            guard_margin=guard_margin,
            kernel_backend=kernel_backend,
            casadi_fd_func=casadi_fd_func,
            cbf_filter=cbf_filter,
            cbf_action_tolerance=cbf_action_tolerance,
        )

        if current_kernel.interval is None or constraints is None:
            correction = float(abs(raw_action))
            freeze = 1.0
        else:
            projected, _success, correction = project_to_kernel(raw_action, current_kernel)
            correction = abs(projected - raw_action)
            freeze = 0.0

        param_violation = max_param_violation(candidate_params, constraints)
        if not np.isfinite(param_violation):
            param_violation = 1.0
        theta_margin = max(0.0, abs(attacked_obs[2]) - (THETA_LIMIT - rho))
        stealth = max(0.0, float(np.linalg.norm(attack, ord=np.inf)) - 0.85 * rho)
        magnitude = float(attack @ attack)
        return AttackMargins(
            stale=param_violation,
            unsafe=correction + theta_margin,
            freeze=freeze,
            stealth_residual=stealth,
            magnitude=magnitude,
        )

    result = cem_optimize(
        evaluator,
        dim=true_obs.shape[0],
        budget=rho,
        weights=attack_weights,
        iterations=iterations,
        population=population,
        seed=seed,
    )
    return result.attack, result.score


def execute_mechanism_step(
    mechanism: str,
    ctrl: object,
    info: dict[str, Any],
    attacked_obs: np.ndarray,
    params: Params,
    rho: float,
    model: CartpoleModel,
    action_grid: np.ndarray,
    *,
    future_span: float,
    guard_margin: float,
    gain_step: float,
    bias_step: float,
    kernel_backend: str,
    casadi_fd_func: object | None,
    cbf_filter: object | None,
    cbf_action_tolerance: float,
) -> tuple[np.ndarray, float, StepDiagnostics]:
    current_kernel = safe_kernel_for_observation(
        attacked_obs,
        rho,
        model,
        action_grid,
        guard_margin=guard_margin,
        kernel_backend=kernel_backend,
        casadi_fd_func=casadi_fd_func,
        cbf_filter=cbf_filter,
        cbf_action_tolerance=cbf_action_tolerance,
    )
    constraints = parameter_constraints(
        ctrl,
        info,
        attacked_obs,
        rho,
        model,
        action_grid,
        future_span=future_span,
        guard_margin=guard_margin,
        kernel_backend=kernel_backend,
        casadi_fd_func=casadi_fd_func,
        cbf_filter=cbf_filter,
        cbf_action_tolerance=cbf_action_tolerance,
    )
    candidate = poison_update(params, attacked_obs, gain_step=gain_step, bias_step=bias_step)
    param_violation = max_param_violation(candidate, constraints)

    next_params = np.asarray(params, dtype=float).copy()
    param_cert_accept = False
    param_projection_norm = 0.0
    intervention = False

    if mechanism == "attacked_lqr_update_ungated":
        next_params = candidate
    elif mechanism == "plausible_action_filter_update_ungated":
        next_params = candidate
    elif mechanism == "always_freeze":
        next_params = params
        intervention = True
    elif mechanism == "lifecycle_gate_project":
        if current_kernel.interval is not None and constraints is not None:
            projected, feasible = project_params(candidate, constraints)
            if feasible:
                next_params = np.minimum(np.maximum(projected, PARAM_LOW), PARAM_HIGH)
                param_cert_accept = max_param_violation(next_params, constraints) <= 1e-7
                param_projection_norm = float(np.linalg.norm(next_params - candidate))
                intervention = param_projection_norm > 1e-8
            else:
                next_params = params
                intervention = True
        else:
            next_params = params
            intervention = True
    else:
        raise ValueError(f"unknown mechanism {mechanism}")

    if (
        mechanism in {"always_freeze", "lifecycle_gate_project"}
        and current_kernel.interval is not None
        and constraints is not None
    ):
        param_cert_accept = max_param_violation(next_params, constraints) <= 1e-7

    raw_action = total_policy_action(ctrl, attacked_obs, info, next_params)
    action = raw_action
    action_cert_accept = False
    action_correction = 0.0
    if mechanism in {"plausible_action_filter_update_ungated", "always_freeze", "lifecycle_gate_project"}:
        projected_action, success, correction = project_to_kernel(raw_action, current_kernel)
        if success:
            action = projected_action
            action_cert_accept = True
            action_correction = correction
            intervention = intervention or correction > 1e-8
    elif current_kernel.interval is not None:
        lower, upper = current_kernel.interval
        action_cert_accept = lower - 1e-9 <= raw_action <= upper + 1e-9

    next_violation = max_param_violation(next_params, constraints)
    learn_update = params_changed(params, next_params)
    # A stale-policy failure applies to mechanisms that treat current-action
    # acceptance as sufficient for the updated learner.  Always-freeze makes
    # no learner-certificate claim, while LifecycleGate rejects the lifecycle
    # certificate whenever the parameter condition is infeasible.
    claims_update_from_action_certificate = mechanism in {
        "attacked_lqr_update_ungated",
        "plausible_action_filter_update_ungated",
    }
    stale_certified = (
        claims_update_from_action_certificate
        and action_cert_accept
        and next_violation > 1e-7
    )
    uncertified_learning = learn_update and not param_cert_accept
    # ``empty_kernel`` is a lifecycle diagnostic: either the current action
    # kernel or at least one required future-history kernel is empty.
    empty_kernel = current_kernel.interval is None or constraints is None
    diagnostics = StepDiagnostics(
        learn_update=learn_update,
        param_cert_accept=param_cert_accept,
        action_cert_accept=action_cert_accept,
        stale_certified_policy=stale_certified,
        uncertified_learning=uncertified_learning,
        intervention=intervention,
        empty_kernel=empty_kernel,
        action_correction=action_correction,
        param_projection_norm=param_projection_norm,
        kernel_width=current_kernel.width,
        param_violation=next_violation,
    )
    return next_params, float(np.clip(action, action_grid[0], action_grid[-1])), diagnostics


def run_mechanism(
    mechanism: str,
    *,
    n_steps: int,
    rho: float,
    seed: int,
    population: int,
    iterations: int,
    action_grid_size: int,
    future_span: float,
    guard_margin: float,
    gain_step: float,
    bias_step: float,
    attack_weights: AttackWeights,
    kernel_backend: str,
    attack_kernel_backend: str,
    cbf_action_tolerance: float,
) -> GateRunSummary:
    if kernel_backend == "mpsc_sampled" or attack_kernel_backend == "mpsc_sampled":
        raise RuntimeError(
            "mpsc_sampled is not available in the current .llm environment: "
            "official Safe-Control-Gym linear_mpsc imports pytope and expects "
            "learned/loaded RPI artifacts."
        )

    task_config, lqr_config, cbf_config = build_configs(seed)
    env_func = partial(make, "cartpole", **task_config)
    env = env_func(gui=False)
    ctrl = make("lqr", env_func, **lqr_config)
    ctrl.reset()
    cbf_filter = None
    if kernel_backend == "cbf_sampled" or attack_kernel_backend == "cbf_sampled":
        with silence():
            cbf_filter = make("cbf", env_func, **cbf_config)
            cbf_filter.reset()

    obs, info = env.reset(seed=seed)
    ctrl.reset_before_run(obs, info, env=env)
    model = make_model_from_env(env)
    casadi_fd_func = env.symbolic.fd_func if kernel_backend == "casadi" or attack_kernel_backend == "casadi" else None
    action_grid = action_grid_from_env(env, action_grid_size)
    params = np.zeros(2, dtype=float)

    rewards: list[float] = []
    attack_linfs: list[float] = []
    attacker_scores: list[float] = []
    diagnostics: list[StepDiagnostics] = []
    violations = 0
    unsafe_certified = 0

    for step in range(n_steps):
        true_obs = np.asarray(obs, dtype=float)
        attack, score = select_attack(
            ctrl=ctrl,
            info=info,
            true_obs=true_obs,
            params=params,
            rho=rho,
            model=model,
            action_grid=action_grid,
            future_span=future_span,
            guard_margin=guard_margin,
            gain_step=gain_step,
            bias_step=bias_step,
            population=population,
            iterations=iterations,
            seed=seed + step,
            attack_weights=attack_weights,
            kernel_backend=attack_kernel_backend,
            casadi_fd_func=casadi_fd_func,
            cbf_filter=cbf_filter,
            cbf_action_tolerance=cbf_action_tolerance,
        )
        attacked_obs = true_obs + attack
        params, action, diag = execute_mechanism_step(
            mechanism,
            ctrl,
            info,
            attacked_obs,
            params,
            rho,
            model,
            action_grid,
            future_span=future_span,
            guard_margin=guard_margin,
            gain_step=gain_step,
            bias_step=bias_step,
            kernel_backend=kernel_backend,
            casadi_fd_func=casadi_fd_func,
            cbf_filter=cbf_filter,
            cbf_action_tolerance=cbf_action_tolerance,
        )

        obs, reward, done, info = env.step(np.asarray([action], dtype=float))
        violation = bool(info.get("constraint_violation", False))
        violations += int(violation)
        unsafe_certified += int(diag.action_cert_accept and violation)
        rewards.append(float(reward))
        attack_linfs.append(float(np.linalg.norm(attack, ord=np.inf)))
        attacker_scores.append(float(score))
        diagnostics.append(diag)

        if done:
            obs, info = env.reset()
            ctrl.reset_before_run(obs, info, env=env)

    if cbf_filter is not None:
        cbf_filter.close()
    ctrl.close()
    env.close()

    future_points = len(future_observation_grid(np.zeros(4), rho, future_span))
    count = len(diagnostics)
    return GateRunSummary(
        benchmark="safe_control_gym",
        task="cartpole",
        controller="lqr_plus_linear_residual",
        mechanism=mechanism,
        kernel_backend=kernel_backend,
        attack_kernel_backend=attack_kernel_backend,
        steps=n_steps,
        budget=rho,
        plausible_radius=rho,
        future_grid_points=future_points,
        action_grid_size=action_grid_size,
        mean_reward=float(np.mean(rewards)) if rewards else 0.0,
        constraint_violation_steps=violations,
        constraint_violation_step_rate=violations / n_steps if n_steps else 0.0,
        unsafe_certified_steps=unsafe_certified,
        unsafe_certified_rate=unsafe_certified / n_steps if n_steps else 0.0,
        stale_certified_policy_steps=sum(d.stale_certified_policy for d in diagnostics),
        stale_certified_policy_rate=sum(d.stale_certified_policy for d in diagnostics) / count if count else 0.0,
        uncertified_learning_steps=sum(d.uncertified_learning for d in diagnostics),
        uncertified_learning_rate=sum(d.uncertified_learning for d in diagnostics) / count if count else 0.0,
        learn_updates=sum(d.learn_update for d in diagnostics),
        learn_update_rate=sum(d.learn_update for d in diagnostics) / count if count else 0.0,
        interventions=sum(d.intervention for d in diagnostics),
        intervention_rate=sum(d.intervention for d in diagnostics) / count if count else 0.0,
        empty_kernel_steps=sum(d.empty_kernel for d in diagnostics),
        empty_kernel_rate=sum(d.empty_kernel for d in diagnostics) / count if count else 0.0,
        mean_kernel_width=float(np.mean([d.kernel_width for d in diagnostics])) if diagnostics else 0.0,
        mean_action_correction=float(np.mean([d.action_correction for d in diagnostics])) if diagnostics else 0.0,
        mean_param_projection_norm=float(np.mean([d.param_projection_norm for d in diagnostics])) if diagnostics else 0.0,
        mean_attack_linf=float(np.mean(attack_linfs)) if attack_linfs else 0.0,
        mean_attacker_score=float(np.mean(attacker_scores)) if attacker_scores else 0.0,
        final_theta_gain=float(params[0]),
        final_bias=float(params[1]),
        max_param_violation=max((d.param_violation for d in diagnostics if np.isfinite(d.param_violation)), default=0.0),
    )


def write_csv(path: Path, rows: list[GateRunSummary]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(asdict(rows[0]).keys()))
        writer.writeheader()
        writer.writerows(asdict(row) for row in rows)


def print_markdown_table(rows: Iterable[GateRunSummary]) -> None:
    print("| kernel | attack_kernel | mechanism | steps | viol_rate | unsafe_cert | stale_cert | uncert_learn | learn_rate | interventions | empty_kernel | mean_K_width | final(theta,bias) |")
    print("|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|")
    for row in rows:
        print(
            f"| {row.kernel_backend} | {row.attack_kernel_backend} | {row.mechanism} | {row.steps} | {row.constraint_violation_step_rate:.3f} | "
            f"{row.unsafe_certified_rate:.3f} | {row.stale_certified_policy_rate:.3f} | "
            f"{row.uncertified_learning_rate:.3f} | {row.learn_update_rate:.3f} | "
            f"{row.intervention_rate:.3f} | {row.empty_kernel_rate:.3f} | "
            f"{row.mean_kernel_width:.3f} | ({row.final_theta_gain:.3f},{row.final_bias:.3f}) |"
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Safe-Control-Gym plausible-set LifecycleGate experiment.")
    parser.add_argument("--n-steps", type=int, default=20)
    parser.add_argument("--rho", type=float, default=0.08)
    parser.add_argument("--rho-list", nargs="+", type=float, default=None)
    parser.add_argument("--seed", type=int, default=2026)
    parser.add_argument("--population", type=int, default=24)
    parser.add_argument("--iterations", type=int, default=4)
    parser.add_argument("--action-grid-size", type=int, default=81)
    parser.add_argument("--kernel-backend", choices=["euler", "casadi", "cbf_sampled", "mpsc_sampled"], default="casadi")
    parser.add_argument("--attack-kernel-backend", choices=["euler", "casadi", "cbf_sampled", "mpsc_sampled"], default="euler")
    parser.add_argument("--cbf-action-tolerance", type=float, default=1e-5)
    parser.add_argument("--future-span", type=float, default=0.03)
    parser.add_argument("--guard-margin", type=float, default=0.0)
    parser.add_argument("--gain-step", type=float, default=2.0)
    parser.add_argument("--bias-step", type=float, default=0.45)
    parser.add_argument("--stale-weight", type=float, default=1.4)
    parser.add_argument("--unsafe-weight", type=float, default=1.0)
    parser.add_argument("--freeze-weight", type=float, default=0.25)
    parser.add_argument("--stealth-weight", type=float, default=0.25)
    parser.add_argument("--magnitude-weight", type=float, default=0.02)
    parser.add_argument(
        "--mechanisms",
        nargs="+",
        default=[
            "attacked_lqr_update_ungated",
            "plausible_action_filter_update_ungated",
            "always_freeze",
            "lifecycle_gate_project",
        ],
    )
    parser.add_argument("--out", type=Path, default=RESULTS_DIR / "safe_control_gym_plausible_set_lifecycle_gate.csv")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    rhos = args.rho_list if args.rho_list is not None else [args.rho]
    attack_weights = AttackWeights(
        stale=args.stale_weight,
        unsafe=args.unsafe_weight,
        freeze=args.freeze_weight,
        stealth=args.stealth_weight,
        magnitude=args.magnitude_weight,
    )
    rows: list[GateRunSummary] = []
    for rho in rhos:
        for mechanism in args.mechanisms:
            rows.append(
                run_mechanism(
                    mechanism,
                    n_steps=args.n_steps,
                    rho=rho,
                    seed=args.seed,
                    population=args.population,
                    iterations=args.iterations,
                    action_grid_size=args.action_grid_size,
                    future_span=args.future_span,
                    guard_margin=args.guard_margin,
                    gain_step=args.gain_step,
                    bias_step=args.bias_step,
                    attack_weights=attack_weights,
                    kernel_backend=args.kernel_backend,
                    attack_kernel_backend=args.attack_kernel_backend,
                    cbf_action_tolerance=args.cbf_action_tolerance,
                )
            )
    write_csv(args.out, rows)
    print_markdown_table(rows)
    print(f"wrote {args.out}")


if __name__ == "__main__":
    main()
