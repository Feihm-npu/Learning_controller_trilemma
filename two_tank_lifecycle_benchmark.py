#!/usr/bin/env python3
"""Two-tank-style benchmark for certificate lifecycle gating.

This benchmark is a small CPS step beyond the one-dimensional frontier example.
The state is a two-dimensional tank-level deviation vector and the input is a
single pump/drain command. Sensor deception reports the nominal history y=(0,0),
while the true state can be anywhere in X_A(h)=[-rho,rho]^2.

The experiment compares current-action filtering against update gating. A robust
action filter can make the applied action safe at the current step, yet still let
the learner's parameter drift outside the certified kernel. LifecycleGate gates
the update itself.
"""

from __future__ import annotations

from dataclasses import dataclass
from itertools import product
from typing import Callable, Iterable


# Linearized two-tank deviation dynamics:
#   x_{t+1} = A x_t + B u_t
# The first level is directly actuated; the second is weakly affected through
# coupling. Coefficients are chosen so that ambiguity in x creates a nontrivial
# safety-kernel frontier.
A = ((1.08, 0.04), (0.02, 1.03))
B = (1.0, 0.1)
U_MAX = 0.15
SAFE_LOW = -1.0
SAFE_HIGH = 1.0
POISON_STEP = 0.06
STEPS = 5


Interval = tuple[float, float] | None


@dataclass
class StepResult:
    cert_accept: bool
    learn_allowed: bool
    uncertified_learning: bool
    unsafe_certified: bool
    stale_certified_policy: bool
    intervention: bool
    theta: float
    action: float | None


@dataclass
class Summary:
    mechanism: str
    rho: float
    kernel: Interval
    cert_accepts: int
    cert_rejects: int
    learn_updates: int
    uncertified_learning_steps: int
    unsafe_certified_steps: int
    stale_certified_policy_steps: int
    interventions: int
    final_theta: float


def clamp(value: float, low: float, high: float) -> float:
    return min(max(value, low), high)


def box_corners(rho: float) -> Iterable[tuple[float, float]]:
    for x1, x2 in product((-rho, rho), repeat=2):
        yield x1, x2


def matvec(row: tuple[float, float], x: tuple[float, float]) -> float:
    return row[0] * x[0] + row[1] * x[1]


def next_state(x: tuple[float, float], u: float) -> tuple[float, float]:
    return (matvec(A[0], x) + B[0] * u, matvec(A[1], x) + B[1] * u)


def safe_for_all_plausible(action: float | None, rho: float) -> bool:
    if action is None:
        return False
    for x in box_corners(rho):
        x_next = next_state(x, action)
        if any(v < SAFE_LOW - 1e-12 or v > SAFE_HIGH + 1e-12 for v in x_next):
            return False
    return True


def certified_kernel(rho: float) -> Interval:
    low = -U_MAX
    high = U_MAX
    for row, b_i in zip(A, B):
        values = [matvec(row, x) for x in box_corners(rho)]
        min_ax = min(values)
        max_ax = max(values)
        if abs(b_i) < 1e-12:
            if min_ax < SAFE_LOW or max_ax > SAFE_HIGH:
                return None
            continue
        if b_i > 0:
            low = max(low, (SAFE_LOW - min_ax) / b_i)
            high = min(high, (SAFE_HIGH - max_ax) / b_i)
        else:
            low = max(low, (SAFE_HIGH - max_ax) / b_i)
            high = min(high, (SAFE_LOW - min_ax) / b_i)
    if low <= high:
        return low, high
    return None


def nominal_kernel() -> Interval:
    low = -U_MAX
    high = U_MAX
    y = (0.0, 0.0)
    for row, b_i in zip(A, B):
        ax = matvec(row, y)
        if abs(b_i) < 1e-12:
            if ax < SAFE_LOW or ax > SAFE_HIGH:
                return None
            continue
        if b_i > 0:
            low = max(low, (SAFE_LOW - ax) / b_i)
            high = min(high, (SAFE_HIGH - ax) / b_i)
        else:
            low = max(low, (SAFE_HIGH - ax) / b_i)
            high = min(high, (SAFE_LOW - ax) / b_i)
    if low <= high:
        return low, high
    return None


def in_interval(value: float, interval: Interval, eps: float = 1e-12) -> bool:
    return interval is not None and interval[0] - eps <= value <= interval[1] + eps


def project(value: float, interval: Interval) -> float | None:
    if interval is None:
        return None
    return clamp(value, interval[0], interval[1])


def format_interval(interval: Interval) -> str:
    if interval is None:
        return "empty"
    if abs(interval[0] - interval[1]) < 1e-9:
        return f"{{{interval[0]:.3f}}}"
    return f"[{interval[0]:.3f},{interval[1]:.3f}]"


def next_theta(theta: float) -> float:
    """Learning-aware FDI pushes the pump command upward."""
    return clamp(theta + POISON_STEP, -U_MAX, U_MAX)


def policy_outside_kernel(theta: float, kernel: Interval) -> bool:
    return not in_interval(theta, kernel)


def ungated(theta: float, rho: float) -> StepResult:
    candidate = next_theta(theta)
    action = candidate
    cert_accept = True
    safe = safe_for_all_plausible(action, rho)
    stale = cert_accept and policy_outside_kernel(candidate, certified_kernel(rho))
    return StepResult(cert_accept, candidate != theta, False, cert_accept and not safe, stale, False, candidate, action)


def nominal_action_filter(theta: float, rho: float) -> StepResult:
    candidate = next_theta(theta)
    action = project(candidate, nominal_kernel())
    cert_accept = action is not None
    safe = safe_for_all_plausible(action, rho)
    stale = cert_accept and policy_outside_kernel(candidate, certified_kernel(rho))
    return StepResult(cert_accept, candidate != theta, False, cert_accept and not safe, stale, action != candidate, candidate, action)


def robust_action_filter_update_ungated(theta: float, rho: float) -> StepResult:
    candidate = next_theta(theta)
    kernel = certified_kernel(rho)
    action = project(candidate, kernel)
    cert_accept = action is not None
    safe = safe_for_all_plausible(action, rho)
    stale = cert_accept and policy_outside_kernel(candidate, kernel)
    learn_allowed = candidate != theta
    return StepResult(
        cert_accept,
        learn_allowed,
        learn_allowed and not cert_accept,
        cert_accept and not safe,
        stale,
        action != candidate,
        candidate,
        action,
    )


def always_freeze(theta: float, rho: float) -> StepResult:
    kernel = certified_kernel(rho)
    cert_accept = in_interval(theta, kernel)
    action = theta if cert_accept else None
    safe = safe_for_all_plausible(action, rho)
    stale = cert_accept and policy_outside_kernel(theta, kernel)
    return StepResult(cert_accept, False, False, cert_accept and not safe, stale, False, theta, action)


def lifecycle_gate_project(theta: float, rho: float) -> StepResult:
    candidate = next_theta(theta)
    kernel = certified_kernel(rho)
    gated = project(candidate, kernel)
    cert_accept = gated is not None
    if cert_accept:
        new_theta = gated
        action = gated
    else:
        new_theta = theta
        action = None
    safe = safe_for_all_plausible(action, rho)
    stale = cert_accept and policy_outside_kernel(new_theta, kernel)
    return StepResult(
        cert_accept,
        cert_accept and new_theta != theta,
        False,
        cert_accept and not safe,
        stale,
        cert_accept and new_theta != candidate,
        new_theta,
        action,
    )


MECHANISMS: dict[str, Callable[[float, float], StepResult]] = {
    "ungated": ungated,
    "nominal_action_filter": nominal_action_filter,
    "robust_action_filter_update_ungated": robust_action_filter_update_ungated,
    "always_freeze": always_freeze,
    "lifecycle_gate_project": lifecycle_gate_project,
}


def run_mechanism(name: str, mechanism: Callable[[float, float], StepResult], rho: float) -> Summary:
    theta = 0.0
    results: list[StepResult] = []
    for _ in range(STEPS):
        result = mechanism(theta, rho)
        theta = result.theta
        results.append(result)
    return Summary(
        mechanism=name,
        rho=rho,
        kernel=certified_kernel(rho),
        cert_accepts=sum(r.cert_accept for r in results),
        cert_rejects=sum(not r.cert_accept for r in results),
        learn_updates=sum(r.learn_allowed for r in results),
        uncertified_learning_steps=sum(r.uncertified_learning for r in results),
        unsafe_certified_steps=sum(r.unsafe_certified for r in results),
        stale_certified_policy_steps=sum(r.stale_certified_policy for r in results),
        interventions=sum(r.intervention for r in results),
        final_theta=theta,
    )


def print_markdown_table(summaries: Iterable[Summary]) -> None:
    print("| rho | mechanism | K(rho) | cert_accepts | cert_rejects | learn_updates | uncertified_learning | unsafe_certified | stale_certified_policy | interventions | final_theta |")
    print("|---:|---|---|---:|---:|---:|---:|---:|---:|---:|---:|")
    for s in summaries:
        print(
            f"| {s.rho:.3f} | {s.mechanism} | {format_interval(s.kernel)} | "
            f"{s.cert_accepts} | {s.cert_rejects} | {s.learn_updates} | "
            f"{s.uncertified_learning_steps} | {s.unsafe_certified_steps} | "
            f"{s.stale_certified_policy_steps} | {s.interventions} | {s.final_theta:.3f} |"
        )


def main() -> None:
    frontier = 1.0 / (abs(A[0][0]) + abs(A[0][1]))
    rhos = [0.70, 0.80, 0.85, frontier, 0.92]
    summaries = [
        run_mechanism(name, mechanism, rho)
        for rho in rhos
        for name, mechanism in MECHANISMS.items()
    ]
    print(f"A={A}, B={B}, u_max={U_MAX}, poison_step={POISON_STEP}, steps={STEPS}")
    print(f"frontier=1/(|A11|+|A12|)={frontier:.3f}")
    print()
    print_markdown_table(summaries)


if __name__ == "__main__":
    main()
