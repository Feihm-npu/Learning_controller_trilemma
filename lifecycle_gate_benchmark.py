#!/usr/bin/env python3
"""Initial benchmark for certificate lifecycle gating.

The experiment separates two notions that are easy to conflate:
  1. filtering the action applied at the current step; and
  2. certifying the online update that changes the controller's future action.

System:
    x_{t+1} = LAMBDA * x_t + u_t, |u_t| <= U_MAX, S=[-1, 1]

The attacked history reports y=0 while the true state can be any x in
X_A(h)=[-rho, rho]. A learning-aware FDI attack pushes the learner's action
parameter toward +U_MAX. A certificate is sound only if the action is safe for
all x in X_A(h).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Iterable


LAMBDA = 1.2
U_MAX = 0.2
POISON_STEP = 0.08
STEPS = 5


Interval = tuple[float, float] | None


@dataclass
class StepResult:
    cert_accept: bool
    learn_allowed: bool
    unsafe_certified: bool
    stale_policy: bool
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
    stale_policy_steps: int
    interventions: int
    final_theta: float


def clamp(value: float, low: float, high: float) -> float:
    return min(max(value, low), high)


def safe_interval_for_state(x: float) -> Interval:
    low = max(-U_MAX, -1.0 - LAMBDA * x)
    high = min(U_MAX, 1.0 - LAMBDA * x)
    if low <= high:
        return low, high
    return None


def certified_kernel(rho: float) -> Interval:
    low_state = -rho
    high_state = rho
    low = max(-U_MAX, -1.0 - LAMBDA * low_state)
    high = min(U_MAX, 1.0 - LAMBDA * high_state)
    if low <= high:
        return low, high
    return None


def nominal_kernel(y: float = 0.0) -> Interval:
    return safe_interval_for_state(y)


def in_interval(value: float, interval: Interval, eps: float = 1e-12) -> bool:
    return interval is not None and interval[0] - eps <= value <= interval[1] + eps


def project(value: float, interval: Interval) -> float | None:
    if interval is None:
        return None
    return clamp(value, interval[0], interval[1])


def next_theta(theta: float) -> float:
    """Learning-aware FDI pushes the learner toward a destabilizing action."""
    return clamp(theta + POISON_STEP, -U_MAX, U_MAX)


def safe_for_all_plausible(action: float | None, rho: float) -> bool:
    if action is None:
        return False
    for x in (-rho, rho):
        if abs(LAMBDA * x + action) > 1.0 + 1e-12:
            return False
    return True


def policy_stale(theta: float, kernel: Interval) -> bool:
    return not in_interval(theta, kernel)


def ungated(theta: float, rho: float) -> StepResult:
    candidate = next_theta(theta)
    action = candidate
    cert_accept = True
    safe = safe_for_all_plausible(action, rho)
    return StepResult(
        cert_accept=cert_accept,
        learn_allowed=candidate != theta,
        unsafe_certified=cert_accept and not safe,
        stale_policy=cert_accept and policy_stale(candidate, certified_kernel(rho)),
        intervention=False,
        theta=candidate,
        action=action,
    )


def nominal_action_filter(theta: float, rho: float) -> StepResult:
    candidate = next_theta(theta)
    action = project(candidate, nominal_kernel(y=0.0))
    cert_accept = action is not None
    safe = safe_for_all_plausible(action, rho)
    return StepResult(
        cert_accept=cert_accept,
        learn_allowed=candidate != theta,
        unsafe_certified=cert_accept and not safe,
        stale_policy=cert_accept and policy_stale(candidate, certified_kernel(rho)),
        intervention=action != candidate,
        theta=candidate,
        action=action,
    )


def robust_action_filter_update_ungated(theta: float, rho: float) -> StepResult:
    candidate = next_theta(theta)
    kernel = certified_kernel(rho)
    action = project(candidate, kernel)
    cert_accept = action is not None
    safe = safe_for_all_plausible(action, rho)
    return StepResult(
        cert_accept=cert_accept,
        learn_allowed=candidate != theta,
        unsafe_certified=cert_accept and not safe,
        stale_policy=cert_accept and policy_stale(candidate, kernel),
        intervention=action != candidate,
        theta=candidate,
        action=action,
    )


def always_freeze(theta: float, rho: float) -> StepResult:
    action = theta
    kernel = certified_kernel(rho)
    cert_accept = in_interval(action, kernel)
    safe = safe_for_all_plausible(action, rho)
    return StepResult(
        cert_accept=cert_accept,
        learn_allowed=False,
        unsafe_certified=cert_accept and not safe,
        stale_policy=cert_accept and policy_stale(theta, kernel),
        intervention=False,
        theta=theta,
        action=action if cert_accept else None,
    )


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
    return StepResult(
        cert_accept=cert_accept,
        learn_allowed=cert_accept and new_theta != theta,
        unsafe_certified=cert_accept and not safe,
        stale_policy=cert_accept and policy_stale(new_theta, kernel),
        intervention=cert_accept and new_theta != candidate,
        theta=new_theta,
        action=action,
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
        uncertified_learning_steps=sum(r.learn_allowed and not r.cert_accept for r in results),
        unsafe_certified_steps=sum(r.unsafe_certified for r in results),
        stale_policy_steps=sum(r.stale_policy for r in results),
        interventions=sum(r.intervention for r in results),
        final_theta=theta,
    )


def format_interval(interval: Interval) -> str:
    if interval is None:
        return "empty"
    if abs(interval[0] - interval[1]) < 1e-9:
        return f"{{{interval[0]:.3f}}}"
    return f"[{interval[0]:.3f},{interval[1]:.3f}]"


def print_markdown_table(summaries: Iterable[Summary]) -> None:
    print("| rho | mechanism | K(rho) | cert_accepts | cert_rejects | learn_updates | uncertified_learning | unsafe_certified | stale_certified_policy | interventions | final_theta |")
    print("|---:|---|---|---:|---:|---:|---:|---:|---:|---:|---:|")
    for s in summaries:
        print(
            f"| {s.rho:.3f} | {s.mechanism} | {format_interval(s.kernel)} | "
            f"{s.cert_accepts} | {s.cert_rejects} | {s.learn_updates} | "
            f"{s.uncertified_learning_steps} | {s.unsafe_certified_steps} | "
            f"{s.stale_policy_steps} | "
            f"{s.interventions} | {s.final_theta:.3f} |"
        )


def main() -> None:
    rhos = [0.60, 0.80, 1.0 / LAMBDA, 0.90, 1.00]
    summaries = [
        run_mechanism(name, mechanism, rho)
        for rho in rhos
        for name, mechanism in MECHANISMS.items()
    ]
    print(f"lambda={LAMBDA}, u_max={U_MAX}, poison_step={POISON_STEP}, steps={STEPS}")
    print()
    print_markdown_table(summaries)


if __name__ == "__main__":
    main()
