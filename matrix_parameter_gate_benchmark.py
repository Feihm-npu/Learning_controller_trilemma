#!/usr/bin/env python3
"""Multidimensional parameter-level update gate for a linear tank policy.

This benchmark lifts the parameter gate from a scalar policy u=kz+b to a
two-dimensional linear policy

    u = k1 * z1 + k2 * z2 + b

on the linearized two-tank dynamics used elsewhere in this artifact. For each
future attacked observation z in a grid, the attack model induces a plausible
state box around z. The one-step invariant certificate produces a safe-action
interval for that box. Requiring the raw policy action to lie in every interval
creates linear halfspace constraints over (k1, k2, b).
"""

from __future__ import annotations

from dataclasses import dataclass
from itertools import product
from typing import Callable, Iterable


A = ((1.08, 0.04), (0.02, 1.03))
B = (1.0, 0.1)
U_MAX = 0.15
SAFE_LOW = -1.0
SAFE_HIGH = 1.0
OBS_MAX = 0.35
OBS_GRID = tuple((z1, z2) for z1, z2 in product((-OBS_MAX, 0.0, OBS_MAX), repeat=2))
CURRENT_OBS = (0.0, 0.0)
INITIAL_PARAMS = (0.0, 0.0, 0.0)
POISON_STEP = (0.28, 0.22, 0.04)
PARAM_LOW = (-2.0, -2.0, -U_MAX)
PARAM_HIGH = (2.0, 2.0, U_MAX)
STEPS = 5


Interval = tuple[float, float] | None
State = tuple[float, float]
Params = tuple[float, float, float]
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


def matvec(row: State, x: State) -> float:
    return row[0] * x[0] + row[1] * x[1]


def box_corners(low: State, high: State) -> Iterable[State]:
    for x1, x2 in product((low[0], high[0]), (low[1], high[1])):
        yield x1, x2


def plausible_box(z: State, rho: float) -> tuple[State, State]:
    low = (max(SAFE_LOW, z[0] - rho), max(SAFE_LOW, z[1] - rho))
    high = (min(SAFE_HIGH, z[0] + rho), min(SAFE_HIGH, z[1] + rho))
    return low, high


def safe_kernel_for_observation(z: State, rho: float) -> Interval:
    low_state, high_state = plausible_box(z, rho)
    lower = -U_MAX
    upper = U_MAX
    for row, b_i in zip(A, B):
        values = [matvec(row, x) for x in box_corners(low_state, high_state)]
        min_ax = min(values)
        max_ax = max(values)
        if abs(b_i) < 1e-12:
            if min_ax < SAFE_LOW or max_ax > SAFE_HIGH:
                return None
            continue
        if b_i > 0:
            lower = max(lower, (SAFE_LOW - min_ax) / b_i)
            upper = min(upper, (SAFE_HIGH - max_ax) / b_i)
        else:
            lower = max(lower, (SAFE_HIGH - max_ax) / b_i)
            upper = min(upper, (SAFE_LOW - min_ax) / b_i)
    if lower <= upper:
        return lower, upper
    return None


def parameter_box_constraints() -> list[Constraint]:
    return [
        ((1.0, 0.0, 0.0), PARAM_HIGH[0]),
        ((-1.0, 0.0, 0.0), -PARAM_LOW[0]),
        ((0.0, 1.0, 0.0), PARAM_HIGH[1]),
        ((0.0, -1.0, 0.0), -PARAM_LOW[1]),
        ((0.0, 0.0, 1.0), PARAM_HIGH[2]),
        ((0.0, 0.0, -1.0), -PARAM_LOW[2]),
    ]


def certified_constraints(rho: float) -> tuple[list[Constraint], float] | None:
    constraints: list[Constraint] = []
    widths: list[float] = []
    for z in OBS_GRID:
        kernel = safe_kernel_for_observation(z, rho)
        if kernel is None:
            return None
        lower, upper = kernel
        widths.append(upper - lower)
        phi = (z[0], z[1], 1.0)
        constraints.append((phi, upper))
        constraints.append(((-phi[0], -phi[1], -phi[2]), -lower))
    constraints.extend(parameter_box_constraints())
    return constraints, min(widths)


def policy_action(params: Params, z: State) -> float:
    return params[0] * z[0] + params[1] * z[1] + params[2]


def next_params(params: Params) -> Params:
    return tuple(
        clamp(params[i] + POISON_STEP[i], PARAM_LOW[i], PARAM_HIGH[i])
        for i in range(3)
    )


def in_interval(value: float, interval: Interval, eps: float = 1e-12) -> bool:
    return interval is not None and interval[0] - eps <= value <= interval[1] + eps


def project_action(action: float, kernel: Interval) -> float | None:
    if kernel is None:
        return None
    return clamp(action, kernel[0], kernel[1])


def max_constraint_violation(params: Params, constraints: Iterable[Constraint]) -> float:
    return max(
        [sum(row[i] * params[i] for i in range(3)) - bound for row, bound in constraints]
        + [0.0]
    )


def project_params(params: Params, constraints: list[Constraint], max_iters: int = 10000) -> tuple[Params, bool]:
    projected = [params[0], params[1], params[2]]
    for _ in range(max_iters):
        max_violation = 0.0
        for row, bound in constraints:
            violation = sum(row[i] * projected[i] for i in range(3)) - bound
            if violation > 1e-11:
                norm_sq = sum(value * value for value in row)
                for i, value in enumerate(row):
                    projected[i] -= violation * value / norm_sq
                max_violation = max(max_violation, violation)
        if max_violation < 1e-10:
            result = (projected[0], projected[1], projected[2])
            return result, True
    result = (projected[0], projected[1], projected[2])
    return result, max_constraint_violation(result, constraints) < 1e-7


def safe_current_action(action: float | None, rho: float) -> bool:
    if action is None:
        return False
    return in_interval(action, safe_kernel_for_observation(CURRENT_OBS, rho))


def params_changed(before: Params, after: Params, eps: float = 1e-9) -> bool:
    return any(abs(before[i] - after[i]) > eps for i in range(3))


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
    return f"({params[0]:.3f},{params[1]:.3f},{params[2]:.3f})"


def print_markdown_table(summaries: Iterable[Summary]) -> None:
    print("| rho | mechanism | current K(0) | min grid width | cert_accepts | cert_rejects | learn_updates | uncertified_learning | unsafe_certified | stale_certified_policy | interventions | final (k1,k2,b) |")
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
    rhos = [0.05, 0.20, 0.35, 0.45, 0.50]
    summaries = [
        run_mechanism(name, mechanism, rho)
        for rho in rhos
        for name, mechanism in MECHANISMS.items()
    ]
    print(
        f"A={A}, B={B}, u_max={U_MAX}, obs_grid_size={len(OBS_GRID)}, "
        f"initial=(k1,k2,b)={INITIAL_PARAMS}, poison_step={POISON_STEP}, steps={STEPS}"
    )
    print()
    print_markdown_table(summaries)


if __name__ == "__main__":
    main()
