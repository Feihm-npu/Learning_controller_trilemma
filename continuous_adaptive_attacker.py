#!/usr/bin/env python3
"""Reusable continuous adaptive-attacker objective and CEM optimizer.

This module is intentionally simulator-agnostic. A benchmark adapter supplies a
black-box evaluator for an attack vector, and this module handles the attacker
objective:

    stale-policy margin + unsafe-action margin + forced-freeze margin - cost.

The first Safe-Control-Gym implementation can use this with observation FDI
vectors. EPANET/PowerGym-style simulators can reuse the same optimizer when
gradients are unavailable.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

import numpy as np


@dataclass(frozen=True)
class AttackWeights:
    stale: float = 1.0
    unsafe: float = 1.0
    freeze: float = 0.5
    stealth: float = 1.0
    magnitude: float = 0.01


@dataclass(frozen=True)
class AttackMargins:
    stale: float
    unsafe: float
    freeze: float
    stealth_residual: float
    magnitude: float


@dataclass(frozen=True)
class CEMResult:
    attack: np.ndarray
    score: float
    margins: AttackMargins
    iterations: int


AttackEvaluator = Callable[[np.ndarray], AttackMargins]


def adaptive_attack_score(margins: AttackMargins, weights: AttackWeights) -> float:
    """Higher score means a more damaging admissible attack."""
    return (
        weights.stale * margins.stale
        + weights.unsafe * margins.unsafe
        + weights.freeze * margins.freeze
        - weights.stealth * margins.stealth_residual
        - weights.magnitude * margins.magnitude
    )


def project_box(values: np.ndarray, low: float | np.ndarray, high: float | np.ndarray) -> np.ndarray:
    return np.minimum(np.maximum(values, low), high)


def cem_optimize(
    evaluator: AttackEvaluator,
    dim: int,
    *,
    budget: float,
    weights: AttackWeights = AttackWeights(),
    iterations: int = 20,
    population: int = 96,
    elite_frac: float = 0.15,
    seed: int = 0,
    init_std: float | None = None,
) -> CEMResult:
    """Cross-entropy method for continuous bounded FDI vectors.

    The search domain is the box [-budget, budget]^dim. This is the default
    optimizer for nondifferentiable simulators and a baseline for PGD/CasADi
    attackers.
    """
    if dim <= 0:
        raise ValueError("dim must be positive")
    if budget < 0:
        raise ValueError("budget must be nonnegative")
    if population < 2:
        raise ValueError("population must be at least 2")
    elite_count = max(1, int(population * elite_frac))

    rng = np.random.default_rng(seed)
    mean = np.zeros(dim)
    std = np.full(dim, budget if init_std is None else init_std)

    best_attack = np.zeros(dim)
    best_margins = evaluator(best_attack)
    best_score = adaptive_attack_score(best_margins, weights)

    for _ in range(iterations):
        candidates = rng.normal(mean, std, size=(population, dim))
        candidates = project_box(candidates, -budget, budget)

        scored: list[tuple[float, np.ndarray, AttackMargins]] = []
        for candidate in candidates:
            margins = evaluator(candidate)
            score = adaptive_attack_score(margins, weights)
            scored.append((score, candidate, margins))

        scored.sort(key=lambda item: item[0], reverse=True)
        if scored[0][0] > best_score:
            best_score, best_attack, best_margins = scored[0]

        elites = np.stack([candidate for _, candidate, _ in scored[:elite_count]])
        mean = elites.mean(axis=0)
        std = np.maximum(elites.std(axis=0), 1e-6)

    return CEMResult(best_attack, best_score, best_margins, iterations)


def demo_quadratic_evaluator(target: np.ndarray, freeze_radius: float) -> AttackEvaluator:
    """Small deterministic demo used by the module smoke test."""

    def evaluator(attack: np.ndarray) -> AttackMargins:
        distance_to_target = np.linalg.norm(attack - target)
        stale = max(0.0, 1.0 - distance_to_target)
        unsafe = max(0.0, attack[0]) if attack.size else 0.0
        freeze = max(0.0, np.linalg.norm(attack) - freeze_radius)
        stealth = max(0.0, np.linalg.norm(attack) - 0.75 * freeze_radius)
        magnitude = float(np.dot(attack, attack))
        return AttackMargins(stale, unsafe, freeze, stealth, magnitude)

    return evaluator


def main() -> None:
    target = np.array([0.6, -0.2, 0.3])
    result = cem_optimize(
        demo_quadratic_evaluator(target, freeze_radius=0.5),
        dim=3,
        budget=1.0,
        iterations=8,
        population=48,
        seed=7,
    )
    print(f"score={result.score:.4f}")
    print("attack=" + ",".join(f"{value:.4f}" for value in result.attack))
    print(f"margins={result.margins}")


if __name__ == "__main__":
    main()
