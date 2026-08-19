#!/usr/bin/env python3
"""Parameter-level update gate for a linear policy.

This benchmark upgrades the action-level gate to a policy-parameter gate. The
plant is the one-dimensional system

    x_{t+1} = LAMBDA * x_t + u_t, |u_t| <= U_MAX, S=[-1, 1].

The policy is a linear map from the attacked observation to the action:

    u = k * z + b.

For every admissible attacked observation z in a small future-history grid, the
attack model induces a plausible-state interval [z-rho, z+rho]. A certified
policy update must make k*z+b lie inside the corresponding safe-action kernel
for every grid point. These conditions are linear inequalities in (k, b). The
parameter gate projects a poisoned candidate update onto that halfspace system.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Iterable


LAMBDA = 1.2
U_MAX = 0.8
SAFE_LOW = -1.0
SAFE_HIGH = 1.0
OBS_GRID = (-0.50, -0.25, 0.0, 0.25, 0.50)
CURRENT_OBS = 0.0
INITIAL_PARAMS = (-LAMBDA, 0.0)
POISON_STEP = (0.45, 0.10)
PARAM_LOW = (-2.0, -U_MAX)
PARAM_HIGH = (2.0, U_MAX)
STEPS = 5


Interval = tuple[float, float] | None
Params = tuple[float, float]
Constraint = tuple[Params, float]


@dataclass
class StepResult:
    cert_accept: bool
    learn_allowed: bool
    uncertified_learning: bool
    unsafe_certified: bool
    stale_certified_policy: bool
    intervention: bool
    theta: Params
    action: float | None
    max_violation: float


@dataclass
class Summary:
    mechanism: str
    rho: float
    kernel: Interval
    min_kernel_width: float
    cert_accepts: int
    cert_rejects: int
    learn_updates: int
    uncertified_learning_steps: int
    unsafe_certified_steps: int
    stale_certified_policy_steps: int
    interventions: int
    final_theta: Params
    max_violation: float


def clamp(value: float, low: float, high: float) -> float:
    return min(max(value, low), high)


def safe_kernel_for_observation(z: float, rho: float) -> Interval:
    """Return the robust one-step action kernel for X_A(z)=[z-rho,z+rho]."""
    low_state = max(SAFE_LOW, z - rho)
    high_state = min(SAFE_HIGH, z + rho)
    lower = max(-U_MAX, SAFE_LOW - LAMBDA * low_state)
    upper = min(U_MAX, SAFE_HIGH - LAMBDA * high_state)
    if lower <= upper:
        return lower, upper
    return None


def certified_constraints(rho: float) -> tuple[list[Constraint], float] | None:
    """Build halfspaces a*k+c*b <= d for all future observation kernels."""
    constraints: list[Constraint] = []
    widths: list[float] = []
    for z in OBS_GRID:
        kernel = safe_kernel_for_observation(z, rho)
        if kernel is None:
            return None
        lower, upper = kernel
        widths.append(upper - lower)
        phi = (z, 1.0)
        constraints.append((phi, upper))
        constraints.append(((-z, -1.0), -lower))

    constraints.extend(parameter_box_constraints())
    return constraints, min(widths)


def parameter_box_constraints() -> list[Constraint]:
    return [
        ((1.0, 0.0), PARAM_HIGH[0]),
        ((-1.0, 0.0), -PARAM_LOW[0]),
        ((0.0, 1.0), PARAM_HIGH[1]),
        ((0.0, -1.0), -PARAM_LOW[1]),
    ]


def policy_action(params: Params, z: float) -> float:
    k, b = params
    return k * z + b


def next_params(params: Params) -> Params:
    """Learning-aware FDI pushes gain and bias toward unsafe future actions."""
    return (
        clamp(params[0] + POISON_STEP[0], PARAM_LOW[0], PARAM_HIGH[0]),
        clamp(params[1] + POISON_STEP[1], PARAM_LOW[1], PARAM_HIGH[1]),
    )


def in_interval(value: float, interval: Interval, eps: float = 1e-12) -> bool:
    return interval is not None and interval[0] - eps <= value <= interval[1] + eps


def project_action(action: float, kernel: Interval) -> float | None:
    if kernel is None:
        return None
    return clamp(action, kernel[0], kernel[1])


def max_constraint_violation(params: Params, constraints: Iterable[Constraint]) -> float:
    return max(
        [row[0] * params[0] + row[1] * params[1] - bound for row, bound in constraints]
        + [0.0]
    )


def project_params(params: Params, constraints: list[Constraint], max_iters: int = 5000) -> tuple[Params, bool]:
    """Project onto a small halfspace system with cyclic Euclidean projections."""
    projected = [params[0], params[1]]
    for _ in range(max_iters):
        max_violation = 0.0
        for row, bound in constraints:
            violation = row[0] * projected[0] + row[1] * projected[1] - bound
            if violation > 1e-11:
                norm_sq = row[0] * row[0] + row[1] * row[1]
                projected[0] -= violation * row[0] / norm_sq
                projected[1] -= violation * row[1] / norm_sq
                max_violation = max(max_violation, violation)
        if max_violation < 1e-10:
            result = (projected[0], projected[1])
            return result, True

    result = (projected[0], projected[1])
    return result, max_constraint_violation(result, constraints) < 1e-7


def safe_current_action(action: float | None, rho: float) -> bool:
    if action is None:
        return False
    return in_interval(action, safe_kernel_for_observation(CURRENT_OBS, rho))


def policy_stale(params: Params, rho: float) -> bool:
    result = certified_constraints(rho)
    if result is None:
        return True
    constraints, _ = result
    return max_constraint_violation(params, constraints) > 1e-8


def params_changed(before: Params, after: Params, eps: float = 1e-9) -> bool:
    return abs(before[0] - after[0]) > eps or abs(before[1] - after[1]) > eps


def ungated(params: Params, rho: float) -> StepResult:
    candidate = next_params(params)
    action = policy_action(candidate, CURRENT_OBS)
    cert_accept = True
    result = certified_constraints(rho)
    violation = float("inf") if result is None else max_constraint_violation(candidate, result[0])
    stale = result is None or violation > 1e-8
    return StepResult(
        cert_accept,
        params_changed(candidate, params),
        False,
        cert_accept and not safe_current_action(action, rho),
        stale,
        False,
        candidate,
        action,
        violation,
    )


def robust_action_filter_update_ungated(params: Params, rho: float) -> StepResult:
    candidate = next_params(params)
    raw_action = policy_action(candidate, CURRENT_OBS)
    action = project_action(raw_action, safe_kernel_for_observation(CURRENT_OBS, rho))
    cert_accept = action is not None
    result = certified_constraints(rho)
    violation = float("inf") if result is None else max_constraint_violation(candidate, result[0])
    stale = cert_accept and (result is None or violation > 1e-8)
    learn_allowed = params_changed(candidate, params)
    return StepResult(
        cert_accept,
        learn_allowed,
        learn_allowed and not cert_accept,
        cert_accept and not safe_current_action(action, rho),
        stale,
        action != raw_action,
        candidate,
        action,
        violation,
    )


def always_freeze(params: Params, rho: float) -> StepResult:
    action = policy_action(params, CURRENT_OBS)
    result = certified_constraints(rho)
    cert_accept = result is not None and max_constraint_violation(params, result[0]) <= 1e-8
    violation = float("inf") if result is None else max_constraint_violation(params, result[0])
    return StepResult(
        cert_accept,
        False,
        False,
        cert_accept and not safe_current_action(action, rho),
        cert_accept and violation > 1e-8,
        False,
        params,
        action if cert_accept else None,
        violation,
    )


def lifecycle_gate_project(params: Params, rho: float) -> StepResult:
    candidate = next_params(params)
    result = certified_constraints(rho)
    if result is None:
        return StepResult(False, False, False, False, False, False, params, None, float("inf"))

    constraints, _ = result
    projected, feasible = project_params(candidate, constraints)
    if not feasible:
        return StepResult(False, False, False, False, False, False, params, None, float("inf"))

    action = policy_action(projected, CURRENT_OBS)
    violation = max_constraint_violation(projected, constraints)
    return StepResult(
        True,
        params_changed(projected, params),
        False,
        not safe_current_action(action, rho),
        violation > 1e-8,
        params_changed(projected, candidate),
        projected,
        action,
        violation,
    )


MECHANISMS: dict[str, Callable[[Params, float], StepResult]] = {
    "ungated": ungated,
    "robust_action_filter_update_ungated": robust_action_filter_update_ungated,
    "always_freeze": always_freeze,
    "lifecycle_gate_project": lifecycle_gate_project,
}


def run_mechanism(name: str, mechanism: Callable[[Params, float], StepResult], rho: float) -> Summary:
    params = INITIAL_PARAMS
    results: list[StepResult] = []
    for _ in range(STEPS):
        result = mechanism(params, rho)
        params = result.theta
        results.append(result)

    constraints_result = certified_constraints(rho)
    min_width = 0.0 if constraints_result is None else constraints_result[1]
    return Summary(
        mechanism=name,
        rho=rho,
        kernel=safe_kernel_for_observation(CURRENT_OBS, rho),
        min_kernel_width=min_width,
        cert_accepts=sum(r.cert_accept for r in results),
        cert_rejects=sum(not r.cert_accept for r in results),
        learn_updates=sum(r.learn_allowed for r in results),
        uncertified_learning_steps=sum(r.uncertified_learning for r in results),
        unsafe_certified_steps=sum(r.unsafe_certified for r in results),
        stale_certified_policy_steps=sum(r.stale_certified_policy for r in results),
        interventions=sum(r.intervention for r in results),
        final_theta=params,
        max_violation=max(r.max_violation for r in results),
    )


def format_interval(interval: Interval) -> str:
    if interval is None:
        return "empty"
    if abs(interval[0] - interval[1]) < 1e-9:
        return f"{{{interval[0]:.3f}}}"
    return f"[{interval[0]:.3f},{interval[1]:.3f}]"


def format_params(params: Params) -> str:
    return f"({params[0]:.3f},{params[1]:.3f})"


def print_markdown_table(summaries: Iterable[Summary]) -> None:
    print("| rho | mechanism | current K(0) | min grid width | cert_accepts | cert_rejects | learn_updates | uncertified_learning | unsafe_certified | stale_certified_policy | interventions | final (k,b) |")
    print("|---:|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|")
    for s in summaries:
        print(
            f"| {s.rho:.3f} | {s.mechanism} | {format_interval(s.kernel)} | "
            f"{s.min_kernel_width:.3f} | {s.cert_accepts} | {s.cert_rejects} | "
            f"{s.learn_updates} | {s.uncertified_learning_steps} | "
            f"{s.unsafe_certified_steps} | {s.stale_certified_policy_steps} | "
            f"{s.interventions} | {format_params(s.final_theta)} |"
        )


def main() -> None:
    rhos = [0.10, 0.30, 0.50, 0.70, 0.80, 0.85]
    summaries = [
        run_mechanism(name, mechanism, rho)
        for rho in rhos
        for name, mechanism in MECHANISMS.items()
    ]
    print(
        f"lambda={LAMBDA}, u_max={U_MAX}, obs_grid={OBS_GRID}, "
        f"initial=(k,b)={INITIAL_PARAMS}, poison_step={POISON_STEP}, steps={STEPS}"
    )
    print()
    print_markdown_table(summaries)


if __name__ == "__main__":
    main()
