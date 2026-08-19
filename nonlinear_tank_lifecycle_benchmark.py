#!/usr/bin/env python3
"""Nonlinear two-tank benchmark for certificate lifecycle gating.

The benchmark uses a simple nonlinear tank-level model with square-root
inter-tank and drain flows. Sensor deception reports the nominal level vector,
while an interval observer returns a plausible-state box around that nominal
history. The certified kernel is computed by checking a grid over that box.

The goal is not to provide a high-fidelity hydraulic simulator. It is to test
whether the action-filtering versus update-gating separation persists once the
one-step safety kernel is produced by a nonlinear CPS model rather than by the
linearized examples.
"""

from __future__ import annotations

from dataclasses import dataclass
from itertools import product
from math import sqrt
from typing import Callable, Iterable


DT = 0.8
BASE_INFLOW = 0.18
COUPLING = 0.25
DRAIN_1 = 0.05
DRAIN_2 = 0.08
U_MAX = 0.18
SAFE_LOW = 0.25
SAFE_HIGH = 1.0
NOMINAL_STATE = (0.70, 0.60)
POISON_STEP = 0.07
STEPS = 5
GRID_POINTS = 21


Interval = tuple[float, float] | None
State = tuple[float, float]


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


def tank_flow(h1: float, h2: float) -> float:
    return COUPLING * sqrt(max(h1 - h2, 0.0))


def drain(level: float, coefficient: float) -> float:
    return coefficient * sqrt(max(level, 0.0))


def next_state(x: State, u: float) -> State:
    h1, h2 = x
    q12 = tank_flow(h1, h2)
    h1_next = h1 + DT * (BASE_INFLOW + u - q12 - drain(h1, DRAIN_1))
    h2_next = h2 + DT * (q12 - drain(h2, DRAIN_2))
    return h1_next, h2_next


def plausible_box(rho: float) -> tuple[State, State]:
    low = (
        max(SAFE_LOW, NOMINAL_STATE[0] - rho),
        max(SAFE_LOW, NOMINAL_STATE[1] - rho),
    )
    high = (
        min(SAFE_HIGH, NOMINAL_STATE[0] + rho),
        min(SAFE_HIGH, NOMINAL_STATE[1] + rho),
    )
    return low, high


def plausible_grid(rho: float, points: int = GRID_POINTS) -> Iterable[State]:
    low, high = plausible_box(rho)
    for i, j in product(range(points), repeat=2):
        h1 = low[0] + (high[0] - low[0]) * i / (points - 1)
        h2 = low[1] + (high[1] - low[1]) * j / (points - 1)
        yield h1, h2


def safe_for_all_plausible(action: float | None, rho: float) -> bool:
    if action is None:
        return False
    for x in plausible_grid(rho):
        h_next = next_state(x, action)
        if any(level < SAFE_LOW - 1e-12 or level > SAFE_HIGH + 1e-12 for level in h_next):
            return False
    return True


def one_step_kernel_for_states(states: Iterable[State]) -> Interval:
    low = -U_MAX
    high = U_MAX
    for h1, h2 in states:
        q12 = tank_flow(h1, h2)
        h1_without_control = h1 + DT * (BASE_INFLOW - q12 - drain(h1, DRAIN_1))
        h2_next = h2 + DT * (q12 - drain(h2, DRAIN_2))
        if h2_next < SAFE_LOW - 1e-12 or h2_next > SAFE_HIGH + 1e-12:
            return None
        low = max(low, (SAFE_LOW - h1_without_control) / DT)
        high = min(high, (SAFE_HIGH - h1_without_control) / DT)
    if low <= high:
        return low, high
    return None


def certified_kernel(rho: float) -> Interval:
    return one_step_kernel_for_states(plausible_grid(rho))


def nominal_kernel() -> Interval:
    return one_step_kernel_for_states([NOMINAL_STATE])


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
    learn_allowed = candidate != theta
    stale = cert_accept and policy_outside_kernel(candidate, kernel)
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
    rhos = [0.10, 0.20, 0.30, 0.40, 0.45]
    summaries = [
        run_mechanism(name, mechanism, rho)
        for rho in rhos
        for name, mechanism in MECHANISMS.items()
    ]
    print(
        f"dt={DT}, nominal={NOMINAL_STATE}, u_max={U_MAX}, "
        f"poison_step={POISON_STEP}, grid={GRID_POINTS}x{GRID_POINTS}, steps={STEPS}"
    )
    print()
    print_markdown_table(summaries)


if __name__ == "__main__":
    main()
