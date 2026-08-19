#!/usr/bin/env python3
"""Adaptive learning-aware FDI benchmark for the parameter-level gate.

The scalar parameter-gate benchmark uses a fixed poisoned update direction. This
script gives the attacker a finite white-box search over update directions and,
for forced-freeze attempts, over ambiguity radii inside a declared attack
budget. The plant, policy class, and certified halfspace set are inherited from
``parameter_update_gate_benchmark.py`` so the results isolate the effect of
adaptive attack selection rather than changing the control problem.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Iterable

import parameter_update_gate_benchmark as base


Params = base.Params
Interval = base.Interval

ATTACK_DIRECTIONS: tuple[Params, ...] = (
    (0.45, 0.10),
    (0.45, -0.10),
    (-0.45, 0.10),
    (-0.45, -0.10),
    (0.75, 0.00),
    (-0.75, 0.00),
    (0.10, 0.25),
    (-0.10, 0.25),
    (0.10, -0.25),
    (-0.10, -0.25),
)
RHO_CHOICES = (0.10, 0.30, 0.50, 0.70, 0.80, 0.84, 0.85, 0.90)
ATTACK_GOALS = ("stale", "unsafe", "freeze")
STEPS = base.STEPS


@dataclass
class AdaptiveScenario:
    attack_goal: str
    rho_budget: float
    selected_rho: float


@dataclass
class AdaptiveSummary:
    attack_goal: str
    rho_budget: float
    selected_rho: float
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


AdaptiveMechanism = Callable[[Params, AdaptiveScenario], base.StepResult]


def add_direction(params: Params, direction: Params) -> Params:
    return (
        base.clamp(params[0] + direction[0], base.PARAM_LOW[0], base.PARAM_HIGH[0]),
        base.clamp(params[1] + direction[1], base.PARAM_LOW[1], base.PARAM_HIGH[1]),
    )


def params_changed(before: Params, after: Params, eps: float = 1e-9) -> bool:
    return abs(before[0] - after[0]) > eps or abs(before[1] - after[1]) > eps


def constraint_violation(params: Params, rho: float) -> float:
    result = base.certified_constraints(rho)
    if result is None:
        return float("inf")
    return base.max_constraint_violation(params, result[0])


def current_action_violation(params: Params, rho: float) -> float:
    action = base.policy_action(params, base.CURRENT_OBS)
    kernel = base.safe_kernel_for_observation(base.CURRENT_OBS, rho)
    if kernel is None:
        return float("inf")
    return max(kernel[0] - action, action - kernel[1], 0.0)


def learning_magnitude(before: Params, after: Params) -> float:
    return abs(after[0] - before[0]) + abs(after[1] - before[1])


def select_attack_rho(goal: str, rho_budget: float) -> float:
    if goal != "freeze":
        return rho_budget

    candidates = sorted({rho for rho in RHO_CHOICES if rho <= rho_budget + 1e-12} | {rho_budget})

    def freeze_score(rho: float) -> tuple[int, float, float]:
        result = base.certified_constraints(rho)
        if result is None:
            return 1, 0.0, rho
        _, min_width = result
        return 0, -min_width, rho

    return max(candidates, key=freeze_score)


def select_candidate(params: Params, scenario: AdaptiveScenario) -> Params:
    candidates = [add_direction(params, direction) for direction in ATTACK_DIRECTIONS]

    def score(candidate: Params) -> tuple[float, float, float]:
        stale_score = constraint_violation(candidate, scenario.selected_rho)
        unsafe_score = current_action_violation(candidate, scenario.selected_rho)
        learn_score = learning_magnitude(params, candidate)
        if scenario.attack_goal == "unsafe":
            return unsafe_score, stale_score, learn_score
        if scenario.attack_goal == "freeze":
            return stale_score, learn_score, unsafe_score
        return stale_score, unsafe_score, learn_score

    return max(candidates, key=score)


def safe_current_action(action: float | None, rho: float) -> bool:
    if action is None:
        return False
    return base.in_interval(action, base.safe_kernel_for_observation(base.CURRENT_OBS, rho))


def ungated(params: Params, scenario: AdaptiveScenario) -> base.StepResult:
    rho = scenario.selected_rho
    candidate = select_candidate(params, scenario)
    action = base.policy_action(candidate, base.CURRENT_OBS)
    violation = constraint_violation(candidate, rho)
    return base.StepResult(
        True,
        params_changed(candidate, params),
        False,
        not safe_current_action(action, rho),
        violation > 1e-8,
        False,
        candidate,
        action,
        violation,
    )


def robust_action_filter_update_ungated(params: Params, scenario: AdaptiveScenario) -> base.StepResult:
    rho = scenario.selected_rho
    candidate = select_candidate(params, scenario)
    raw_action = base.policy_action(candidate, base.CURRENT_OBS)
    action = base.project_action(raw_action, base.safe_kernel_for_observation(base.CURRENT_OBS, rho))
    cert_accept = action is not None
    violation = constraint_violation(candidate, rho)
    learn_allowed = params_changed(candidate, params)
    return base.StepResult(
        cert_accept,
        learn_allowed,
        learn_allowed and not cert_accept,
        cert_accept and not safe_current_action(action, rho),
        cert_accept and violation > 1e-8,
        action != raw_action,
        candidate,
        action,
        violation,
    )


def always_freeze(params: Params, scenario: AdaptiveScenario) -> base.StepResult:
    rho = scenario.selected_rho
    action = base.policy_action(params, base.CURRENT_OBS)
    result = base.certified_constraints(rho)
    cert_accept = result is not None and base.max_constraint_violation(params, result[0]) <= 1e-8
    violation = float("inf") if result is None else base.max_constraint_violation(params, result[0])
    return base.StepResult(
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


def lifecycle_gate_project(params: Params, scenario: AdaptiveScenario) -> base.StepResult:
    rho = scenario.selected_rho
    candidate = select_candidate(params, scenario)
    result = base.certified_constraints(rho)
    if result is None:
        return base.StepResult(False, False, False, False, False, False, params, None, float("inf"))

    constraints, _ = result
    projected, feasible = base.project_params(candidate, constraints)
    if not feasible:
        return base.StepResult(False, False, False, False, False, False, params, None, float("inf"))

    action = base.policy_action(projected, base.CURRENT_OBS)
    violation = base.max_constraint_violation(projected, constraints)
    return base.StepResult(
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


MECHANISMS: dict[str, AdaptiveMechanism] = {
    "ungated": ungated,
    "robust_action_filter_update_ungated": robust_action_filter_update_ungated,
    "always_freeze": always_freeze,
    "lifecycle_gate_project": lifecycle_gate_project,
}


def make_scenario(attack_goal: str, rho_budget: float) -> AdaptiveScenario:
    return AdaptiveScenario(
        attack_goal=attack_goal,
        rho_budget=rho_budget,
        selected_rho=select_attack_rho(attack_goal, rho_budget),
    )


def run_mechanism(
    name: str,
    mechanism: AdaptiveMechanism,
    attack_goal: str,
    rho_budget: float,
) -> AdaptiveSummary:
    scenario = make_scenario(attack_goal, rho_budget)
    params = base.INITIAL_PARAMS
    results: list[base.StepResult] = []
    for _ in range(STEPS):
        result = mechanism(params, scenario)
        params = result.theta
        results.append(result)

    constraints_result = base.certified_constraints(scenario.selected_rho)
    min_width = 0.0 if constraints_result is None else constraints_result[1]
    return AdaptiveSummary(
        attack_goal=attack_goal,
        rho_budget=rho_budget,
        selected_rho=scenario.selected_rho,
        mechanism=name,
        rho=rho_budget,
        kernel=base.safe_kernel_for_observation(base.CURRENT_OBS, scenario.selected_rho),
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


def print_markdown_table(summaries: Iterable[AdaptiveSummary]) -> None:
    print("| goal | rho budget | selected rho | mechanism | current K(0) | min grid width | cert_accepts | cert_rejects | learn_updates | uncertified_learning | unsafe_certified | stale_certified_policy | interventions | final (k,b) |")
    print("|---|---:|---:|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|")
    for s in summaries:
        print(
            f"| {s.attack_goal} | {s.rho_budget:.3f} | {s.selected_rho:.3f} | "
            f"{s.mechanism} | {format_interval(s.kernel)} | {s.min_kernel_width:.3f} | "
            f"{s.cert_accepts} | {s.cert_rejects} | {s.learn_updates} | "
            f"{s.uncertified_learning_steps} | {s.unsafe_certified_steps} | "
            f"{s.stale_certified_policy_steps} | {s.interventions} | "
            f"{format_params(s.final_theta)} |"
        )


def main() -> None:
    rho_budgets = {
        "stale": [0.10, 0.30, 0.50, 0.70, 0.80],
        "unsafe": [0.10, 0.30, 0.50, 0.70, 0.80],
        "freeze": [0.70, 0.80, 0.84, 0.85, 0.90],
    }
    summaries = [
        run_mechanism(name, mechanism, goal, rho_budget)
        for goal in ATTACK_GOALS
        for rho_budget in rho_budgets[goal]
        for name, mechanism in MECHANISMS.items()
    ]
    print(
        f"adaptive finite-search attacker, directions={len(ATTACK_DIRECTIONS)}, "
        f"rho_choices={RHO_CHOICES}, initial=(k,b)={base.INITIAL_PARAMS}, steps={STEPS}"
    )
    print()
    print_markdown_table(summaries)


if __name__ == "__main__":
    main()
