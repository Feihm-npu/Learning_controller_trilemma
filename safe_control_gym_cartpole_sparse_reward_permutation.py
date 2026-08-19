#!/usr/bin/env python3
"""Exact sparse reward-permutation attack and burned-seed S1 smoke."""

from __future__ import annotations

import argparse
import csv
import itertools
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import numpy as np

import reward_certificate_geometry as geometry
import safe_control_gym_cartpole_v3_fixed_target_tanh as v3
import safe_control_gym_reinforce_reward_poisoning as reinforce


ROOT = Path(__file__).resolve().parent
RESULTS = ROOT / "results"
V3_STEPS = RESULTS / "cartpole_v3_trajectory_influence_steps.csv"
V4_STEPS = RESULTS / "cartpole_v4_untouched_confirmation_steps.csv"
V3_TRAINING = RESULTS / "cartpole_v3_fixed_target_multiseed_training.csv"
OFFLINE_PREFIX = RESULTS / "cartpole_stealth_s1_offline"
SMOKE_PREFIX = RESULTS / "cartpole_stealth_s1_2070"
TARGET_EFFECTIVE = np.asarray([-2.3625524160241205, -5.0], dtype=float)
REWARD_BUDGET = 2.0
MAX_MOVED = 4
BATCH_STEPS = 8
SIGMA = 0.8
GAMMA = 0.97
ACTOR_LR = 1.0
GRADIENT_CAP = 1.0
PERMUTATIONS = np.asarray(
    list(itertools.permutations(range(BATCH_STEPS))), dtype=np.int16
)
MOVED_COUNTS = np.sum(PERMUTATIONS != np.arange(BATCH_STEPS), axis=1)


@dataclass
class PermutationAudit:
    learner_seed: int
    batch: int
    feasible_permutations: int
    feasible_nonidentity_permutations: int
    selected_global_permutation_index: int
    selected_permutation: str
    selected_moved_positions: int
    selected_changed_values: int
    maximum_reward_edit: float
    multiset_max_error: float
    reward_sum_error: float
    reward_mean_error: float
    reward_variance_error: float
    reward_min_error: float
    reward_max_error: float
    positive_count_difference: int
    current_target_distance: float
    identity_next_target_distance: float
    selected_next_target_distance: float
    improvement_over_identity: float
    selected_raw_gradient_w0: float
    selected_raw_gradient_w1: float
    selected_applied_gradient_w0: float
    selected_applied_gradient_w1: float
    selected_next_gain: float
    selected_next_bias: float
    selection_latency_ms: float
    exact_first_argmin: bool


@dataclass
class VerifiedPermutationBatch:
    learner_seed: int
    batch: int
    feasible_permutations: int
    feasible_nonidentity_permutations: int
    selected_global_permutation_index: int
    selected_permutation: str
    selected_moved_positions: int
    selected_changed_values: int
    maximum_reward_edit: float
    multiset_max_error: float
    reward_sum_error: float
    reward_mean_error: float
    reward_variance_error: float
    reward_min_error: float
    reward_max_error: float
    positive_count_difference: int
    current_target_distance: float
    identity_next_target_distance: float
    selected_next_target_distance: float
    improvement_over_identity: float
    selected_raw_gradient_w0: float
    selected_raw_gradient_w1: float
    selected_applied_gradient_w0: float
    selected_applied_gradient_w1: float
    selected_next_gain: float
    selected_next_bias: float
    selection_latency_ms: float
    exact_first_argmin: bool
    learner_raw_gradient_error: float
    learner_applied_gradient_error: float
    learner_next_parameter_error: float
    all_invariants_pass: bool


@dataclass
class S1StepRow:
    learner_seed: int
    batch: int
    step: int
    source_reward_step: int
    true_reward: float
    logged_reward: float
    reward_delta: float
    feature_gain_coordinate: float
    feature_bias_coordinate: float
    exploration_noise: float
    done: float


@dataclass
class OfflineDecision:
    audited_seeds: int
    audited_batches: int
    every_batch_has_nonidentity_feasible: bool
    batches_selecting_nonidentity: int
    batches_improving_over_identity: int
    all_invariants_pass: bool
    minimum_feasible_permutations: int
    median_feasible_permutations: float
    maximum_feasible_permutations: int
    median_selection_latency_ms: float
    maximum_selection_latency_ms: float
    median_selected_moved_positions: float
    median_maximum_reward_edit: float
    offline_gate_pass: bool


@dataclass
class S1SmokeDecision:
    learner_seed: int
    evaluation_seed: int
    audited_batches: int
    batches_selecting_nonidentity: int
    all_permutation_invariants_pass: bool
    max_learner_raw_gradient_error: float
    max_learner_applied_gradient_error: float
    max_learner_next_parameter_error: float
    adaptation_constraint_violations: int
    reward_budget_integrity: bool
    pair_keys_valid: bool
    poison_initially_accepted: int
    clean_release_violations: int
    poisoned_release_violations: int
    resident_predictive_violations: int
    poison_only_discordant: int
    clean_only_discordant: int
    paired_release_failures_with_timely_switch: int
    paired_release_failures: int
    initial_target_distance: float
    final_target_distance: float
    target_progress: float
    target_progress_pass: bool
    raw_release_effect_pass: bool
    s1_2070_smoke_pass: bool
    next_action: str


def write_csv(path: Path, rows: list[object]) -> None:
    dictionaries = [asdict(row) for row in rows]
    if not dictionaries:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=list(dictionaries[0]))
        writer.writeheader()
        writer.writerows(dictionaries)


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as source:
        return list(csv.DictReader(source))


def locked_args() -> SimpleNamespace:
    return SimpleNamespace(
        batches=12,
        batch_steps=BATCH_STEPS,
        rho=0.005,
        sigma=SIGMA,
        actor_lr=ACTOR_LR,
        gamma=GAMMA,
        max_gradient_norm=GRADIENT_CAP,
        reward_poison_budget=REWARD_BUDGET,
        poison_temperature=1.0,
        candidate_states=32,
        selected_states=24,
        monitor_horizon=5,
        deployment_steps=120,
        baseline_guard_margin=0.0075,
        action_grid_size=41,
    )


def vectorized_gradients(
    candidate_rewards: np.ndarray,
    *,
    features: np.ndarray,
    exploration_noise: np.ndarray,
    dones: np.ndarray,
    sigma: float,
    gamma: float,
) -> np.ndarray:
    operator = geometry.centered_return_operator(dones, gamma)
    centered_returns = candidate_rewards @ operator.T
    scales = np.std(centered_returns, axis=1)
    advantages = centered_returns.copy()
    active = scales > 1e-8
    advantages[active] /= scales[active, None]
    scores = geometry.gaussian_score_matrix(
        features, exploration_noise, sigma
    )
    return advantages @ scores / float(candidate_rewards.shape[1])


def apply_update(
    current: np.ndarray,
    raw_gradients: np.ndarray,
    *,
    actor_lr: float,
    max_gradient_norm: float,
) -> tuple[np.ndarray, np.ndarray]:
    gradients = np.asarray(raw_gradients, dtype=float).copy()
    one_dimensional = gradients.ndim == 1
    if one_dimensional:
        gradients = gradients[None, :]
    norms = np.linalg.norm(gradients, axis=1)
    active = norms > max_gradient_norm
    gradients[active] *= (
        max_gradient_norm / norms[active]
    )[:, None]
    candidates = np.minimum(
        np.maximum(
            np.asarray(current, dtype=float)[None, :] + actor_lr * gradients,
            reinforce.LEARNER_LOW,
        ),
        reinforce.LEARNER_HIGH,
    )
    if one_dimensional:
        return gradients[0], candidates[0]
    return gradients, candidates


class SparseRewardPermutationAttack:
    def __init__(self, learner_seed: int) -> None:
        self.learner_seed = learner_seed
        self.audits: list[PermutationAudit] = []
        self.logged_rewards: list[np.ndarray] = []

    def select(
        self,
        *,
        batch: int,
        exploration_noise: np.ndarray,
        features: np.ndarray,
        true_rewards: np.ndarray,
        dones: np.ndarray,
        learner_params: np.ndarray,
        target_params: np.ndarray,
        sigma: float,
        gamma: float,
        actor_lr: float,
        max_gradient_norm: float,
        budget: float,
    ) -> tuple[np.ndarray, PermutationAudit]:
        start = time.perf_counter()
        rewards = np.asarray(true_rewards, dtype=float)
        if rewards.shape != (BATCH_STEPS,):
            raise ValueError("S1 is locked to eight-step batches")
        if not np.allclose(
            reinforce.to_effective_params(target_params),
            TARGET_EFFECTIVE,
            atol=1e-12,
            rtol=0.0,
        ):
            raise ValueError("S1 received the wrong fixed target")
        if not np.isclose(budget, REWARD_BUDGET):
            raise ValueError("S1 received the wrong reward budget")

        all_candidates = rewards[PERMUTATIONS]
        feasible_mask = np.logical_and(
            np.max(np.abs(all_candidates - rewards), axis=1) <= budget + 1e-12,
            MOVED_COUNTS <= MAX_MOVED,
        )
        feasible_global = np.flatnonzero(feasible_mask)
        if len(feasible_global) == 0 or feasible_global[0] != 0:
            raise RuntimeError("identity permutation must be the first feasible candidate")
        candidates = all_candidates[feasible_mask]
        raw_gradients = vectorized_gradients(
            candidates,
            features=np.asarray(features, dtype=float),
            exploration_noise=np.asarray(exploration_noise, dtype=float),
            dones=np.asarray(dones, dtype=float),
            sigma=sigma,
            gamma=gamma,
        )
        applied_gradients, next_params = apply_update(
            learner_params,
            raw_gradients,
            actor_lr=actor_lr,
            max_gradient_norm=max_gradient_norm,
        )
        next_effective = np.column_stack(
            [
                next_params[:, 0] / reinforce.THETA_SCALE,
                next_params[:, 1],
            ]
        )
        distances = np.linalg.norm(next_effective - TARGET_EFFECTIVE, axis=1)
        selected_local = int(np.argmin(distances))
        selected_global = int(feasible_global[selected_local])
        permutation = PERMUTATIONS[selected_global]
        logged = candidates[selected_local].copy()
        delta = logged - rewards
        current_effective = reinforce.to_effective_params(learner_params)
        identity_local = int(np.flatnonzero(feasible_global == 0)[0])
        latency_ms = 1000.0 * (time.perf_counter() - start)
        audit = PermutationAudit(
            learner_seed=self.learner_seed,
            batch=batch,
            feasible_permutations=len(candidates),
            feasible_nonidentity_permutations=int(
                np.sum(feasible_global != 0)
            ),
            selected_global_permutation_index=selected_global,
            selected_permutation=";".join(str(int(value)) for value in permutation),
            selected_moved_positions=int(MOVED_COUNTS[selected_global]),
            selected_changed_values=int(np.sum(np.abs(delta) > 1e-12)),
            maximum_reward_edit=float(np.max(np.abs(delta))),
            multiset_max_error=float(
                np.max(np.abs(np.sort(logged) - np.sort(rewards)))
            ),
            reward_sum_error=float(abs(np.sum(logged) - np.sum(rewards))),
            reward_mean_error=float(abs(np.mean(logged) - np.mean(rewards))),
            reward_variance_error=float(abs(np.var(logged) - np.var(rewards))),
            reward_min_error=float(abs(np.min(logged) - np.min(rewards))),
            reward_max_error=float(abs(np.max(logged) - np.max(rewards))),
            positive_count_difference=int(
                abs(np.sum(logged > 0.0) - np.sum(rewards > 0.0))
            ),
            current_target_distance=float(
                np.linalg.norm(current_effective - TARGET_EFFECTIVE)
            ),
            identity_next_target_distance=float(distances[identity_local]),
            selected_next_target_distance=float(distances[selected_local]),
            improvement_over_identity=float(
                distances[identity_local] - distances[selected_local]
            ),
            selected_raw_gradient_w0=float(raw_gradients[selected_local, 0]),
            selected_raw_gradient_w1=float(raw_gradients[selected_local, 1]),
            selected_applied_gradient_w0=float(
                applied_gradients[selected_local, 0]
            ),
            selected_applied_gradient_w1=float(
                applied_gradients[selected_local, 1]
            ),
            selected_next_gain=float(next_effective[selected_local, 0]),
            selected_next_bias=float(next_effective[selected_local, 1]),
            selection_latency_ms=latency_ms,
            exact_first_argmin=selected_local == int(np.argmin(distances)),
        )
        return delta, audit

    def __call__(self, **kwargs: Any) -> np.ndarray:
        delta, audit = self.select(**kwargs)
        self.audits.append(audit)
        self.logged_rewards.append(
            np.asarray(kwargs["true_rewards"], dtype=float) + delta
        )
        return delta


def load_trace_batches() -> list[tuple[int, int, dict[str, np.ndarray]]]:
    rows: list[dict[str, str]] = []
    for path in (V3_STEPS, V4_STEPS):
        rows.extend(read_rows(path))
    rows = [row for row in rows if row["mechanism"] == "clean"]
    output: list[tuple[int, int, dict[str, np.ndarray]]] = []
    for seed in sorted({int(row["learner_seed"]) for row in rows}):
        for batch in range(12):
            selected = sorted(
                [
                    row
                    for row in rows
                    if int(row["learner_seed"]) == seed
                    and int(row["batch"]) == batch
                ],
                key=lambda row: int(row["step"]),
            )
            if len(selected) != BATCH_STEPS:
                raise RuntimeError(f"missing trace rows for seed={seed}, batch={batch}")
            output.append(
                (
                    seed,
                    batch,
                    {
                        "features": np.asarray(
                            [
                                [
                                    float(row["feature_gain_coordinate"]),
                                    float(row["feature_bias_coordinate"]),
                                ]
                                for row in selected
                            ]
                        ),
                        "exploration_noise": np.asarray(
                            [float(row["exploration_noise"]) for row in selected]
                        ),
                        "true_rewards": np.asarray(
                            [float(row["true_reward"]) for row in selected]
                        ),
                        "dones": np.asarray([float(row["done"]) for row in selected]),
                    },
                )
            )
    return output


def invariant_pass(audit: PermutationAudit) -> bool:
    return bool(
        audit.selected_moved_positions <= MAX_MOVED
        and audit.maximum_reward_edit <= REWARD_BUDGET + 1e-12
        and audit.multiset_max_error <= 1e-12
        and audit.reward_sum_error <= 1e-12
        and audit.reward_mean_error <= 1e-12
        and audit.reward_variance_error <= 1e-12
        and audit.reward_min_error <= 1e-12
        and audit.reward_max_error <= 1e-12
        and audit.positive_count_difference == 0
        and audit.exact_first_argmin
    )


def run_offline_check() -> OfflineDecision:
    audits: list[PermutationAudit] = []
    current_seed: int | None = None
    current = np.zeros(2, dtype=float)
    target = reinforce.to_learner_params(TARGET_EFFECTIVE)
    for seed, batch, trace in load_trace_batches():
        if seed != current_seed:
            current_seed = seed
            current = np.zeros(2, dtype=float)
        attack = SparseRewardPermutationAttack(seed)
        _delta, audit = attack.select(
            batch=batch,
            learner_params=current,
            target_params=target,
            sigma=SIGMA,
            gamma=GAMMA,
            actor_lr=ACTOR_LR,
            max_gradient_norm=GRADIENT_CAP,
            budget=REWARD_BUDGET,
            **trace,
        )
        current = reinforce.to_learner_params(
            np.asarray([audit.selected_next_gain, audit.selected_next_bias])
        )
        audits.append(audit)
    latencies = [row.selection_latency_ms for row in audits]
    feasible = [row.feasible_permutations for row in audits]
    decision = OfflineDecision(
        audited_seeds=len({row.learner_seed for row in audits}),
        audited_batches=len(audits),
        every_batch_has_nonidentity_feasible=all(
            row.feasible_nonidentity_permutations > 0 for row in audits
        ),
        batches_selecting_nonidentity=sum(
            row.selected_global_permutation_index != 0 for row in audits
        ),
        batches_improving_over_identity=sum(
            row.improvement_over_identity > 1e-12 for row in audits
        ),
        all_invariants_pass=all(invariant_pass(row) for row in audits),
        minimum_feasible_permutations=min(feasible),
        median_feasible_permutations=float(np.median(feasible)),
        maximum_feasible_permutations=max(feasible),
        median_selection_latency_ms=float(np.median(latencies)),
        maximum_selection_latency_ms=max(latencies),
        median_selected_moved_positions=float(
            np.median([row.selected_moved_positions for row in audits])
        ),
        median_maximum_reward_edit=float(
            np.median([row.maximum_reward_edit for row in audits])
        ),
        offline_gate_pass=bool(
            len(audits) == 96
            and all(row.feasible_nonidentity_permutations > 0 for row in audits)
            and all(invariant_pass(row) for row in audits)
        ),
    )
    write_csv(Path(f"{OFFLINE_PREFIX}_batches.csv"), audits)
    write_csv(Path(f"{OFFLINE_PREFIX}_decision.csv"), [decision])
    print(decision)
    return decision


def locked_clean_params(seed: int) -> np.ndarray:
    matching = [
        row
        for row in read_rows(V3_TRAINING)
        if int(row["learner_seed"]) == seed and row["mechanism"] == "clean"
    ]
    if len(matching) != 1:
        raise RuntimeError(f"missing locked clean snapshot for {seed}")
    return np.asarray(
        [float(matching[0]["final_gain"]), float(matching[0]["final_bias"])],
        dtype=float,
    )


def capture(store: list[dict[str, Any]]):
    def observer(**kwargs: Any) -> None:
        store.append(kwargs)

    return observer


def verify_online_batches(
    attack: SparseRewardPermutationAttack,
    records: list[dict[str, Any]],
) -> list[VerifiedPermutationBatch]:
    if len(attack.audits) != len(records):
        raise RuntimeError("attack and learner observer batch counts disagree")
    output: list[VerifiedPermutationBatch] = []
    for audit, record in zip(attack.audits, records):
        raw_error = float(
            np.linalg.norm(
                np.asarray(record["raw_gradient"])
                - np.asarray(
                    [audit.selected_raw_gradient_w0, audit.selected_raw_gradient_w1]
                )
            )
        )
        applied_error = float(
            np.linalg.norm(
                np.asarray(record["applied_gradient"])
                - np.asarray(
                    [
                        audit.selected_applied_gradient_w0,
                        audit.selected_applied_gradient_w1,
                    ]
                )
            )
        )
        next_error = float(
            np.linalg.norm(
                np.asarray(record["effective_params_after"])
                - np.asarray([audit.selected_next_gain, audit.selected_next_bias])
            )
        )
        output.append(
            VerifiedPermutationBatch(
                **asdict(audit),
                learner_raw_gradient_error=raw_error,
                learner_applied_gradient_error=applied_error,
                learner_next_parameter_error=next_error,
                all_invariants_pass=bool(
                    invariant_pass(audit)
                    and raw_error <= 1e-10
                    and applied_error <= 1e-10
                    and next_error <= 1e-10
                ),
            )
        )
    return output


def online_step_rows(
    learner_seed: int,
    audits: list[PermutationAudit],
    records: list[dict[str, Any]],
) -> list[S1StepRow]:
    output: list[S1StepRow] = []
    for audit, record in zip(audits, records):
        permutation = [int(value) for value in audit.selected_permutation.split(";")]
        for step in range(BATCH_STEPS):
            output.append(
                S1StepRow(
                    learner_seed=learner_seed,
                    batch=int(record["batch"]),
                    step=step,
                    source_reward_step=permutation[step],
                    true_reward=float(record["true_rewards"][step]),
                    logged_reward=float(record["logged_rewards"][step]),
                    reward_delta=float(record["reward_delta"][step]),
                    feature_gain_coordinate=float(record["features"][step, 0]),
                    feature_bias_coordinate=float(record["features"][step, 1]),
                    exploration_noise=float(record["exploration_noise"][step]),
                    done=float(record["dones"][step]),
                )
            )
    return output


def run_s1_2070_smoke() -> S1SmokeDecision:
    offline = read_rows(Path(f"{OFFLINE_PREFIX}_decision.csv"))
    if len(offline) != 1 or offline[0]["offline_gate_pass"] != "True":
        raise RuntimeError("offline S1 gate did not authorize the online smoke")
    learner_seed, evaluation_seed = 2070, 9070
    protocol = locked_args()
    attack = SparseRewardPermutationAttack(learner_seed)
    records: list[dict[str, Any]] = []
    effective, training, traces = reinforce.train_reinforce(
        "s1_sparse_reward_permutation_k4",
        seed=learner_seed,
        poisoned_rewards=True,
        freeze_updates=False,
        batches=protocol.batches,
        batch_steps=protocol.batch_steps,
        rho=protocol.rho,
        sigma=protocol.sigma,
        actor_lr=protocol.actor_lr,
        gamma=protocol.gamma,
        max_gradient_norm=protocol.max_gradient_norm,
        reward_poison_budget=protocol.reward_poison_budget,
        poison_temperature=protocol.poison_temperature,
        deployment_steps=protocol.deployment_steps,
        action_grid_size=protocol.action_grid_size,
        kernel_backend="casadi",
        reward_poisoner=attack,
        target_effective_params=TARGET_EFFECTIVE,
        batch_observer=capture(records),
    )
    verified = verify_online_batches(attack, records)
    clean = locked_clean_params(learner_seed)
    rollout_rows = v3.run_contracts(
        learner_seed,
        evaluation_seed,
        clean,
        effective,
        protocol,
    )
    base_decision = v3.decide_seed(
        learner_seed,
        evaluation_seed,
        training,
        v3.batch_rows(learner_seed, "s1_k4", traces),
        rollout_rows,
        protocol,
    )
    initial_distance = float(np.linalg.norm(TARGET_EFFECTIVE))
    final_distance = float(np.linalg.norm(effective - TARGET_EFFECTIVE))
    invariants = all(row.all_invariants_pass for row in verified)
    target_pass = final_distance < initial_distance - 1e-12
    raw_effect = base_decision.poison_only_discordant >= 1
    smoke_pass = bool(
        invariants
        and training.adaptation_constraint_violations == 0
        and base_decision.budget_integrity
        and base_decision.pair_keys_valid
        and target_pass
        and base_decision.poison_initially_accepted >= 12
        and raw_effect
        and base_decision.resident_predictive_violations == 0
        and base_decision.paired_release_failures_with_timely_switch
        == base_decision.paired_release_failures
    )
    if not invariants or training.adaptation_constraint_violations != 0 or not target_pass:
        next_action = "diagnose_implementation_or_integrity"
    elif not raw_effect:
        next_action = "close_s1_and_run_s2_2070_once"
    elif smoke_pass:
        next_action = "run_s1_burned_extension_2071_2072"
    else:
        next_action = "close_s1_without_new_seeds"
    decision = S1SmokeDecision(
        learner_seed=learner_seed,
        evaluation_seed=evaluation_seed,
        audited_batches=len(verified),
        batches_selecting_nonidentity=sum(
            row.selected_global_permutation_index != 0 for row in verified
        ),
        all_permutation_invariants_pass=invariants,
        max_learner_raw_gradient_error=max(
            row.learner_raw_gradient_error for row in verified
        ),
        max_learner_applied_gradient_error=max(
            row.learner_applied_gradient_error for row in verified
        ),
        max_learner_next_parameter_error=max(
            row.learner_next_parameter_error for row in verified
        ),
        adaptation_constraint_violations=training.adaptation_constraint_violations,
        reward_budget_integrity=base_decision.budget_integrity,
        pair_keys_valid=base_decision.pair_keys_valid,
        poison_initially_accepted=base_decision.poison_initially_accepted,
        clean_release_violations=base_decision.clean_release_violations,
        poisoned_release_violations=base_decision.poisoned_release_violations,
        resident_predictive_violations=base_decision.resident_predictive_violations,
        poison_only_discordant=base_decision.poison_only_discordant,
        clean_only_discordant=base_decision.clean_only_discordant,
        paired_release_failures_with_timely_switch=(
            base_decision.paired_release_failures_with_timely_switch
        ),
        paired_release_failures=base_decision.paired_release_failures,
        initial_target_distance=initial_distance,
        final_target_distance=final_distance,
        target_progress=initial_distance - final_distance,
        target_progress_pass=target_pass,
        raw_release_effect_pass=raw_effect,
        s1_2070_smoke_pass=smoke_pass,
        next_action=next_action,
    )
    write_csv(Path(f"{SMOKE_PREFIX}_permutation_batches.csv"), verified)
    write_csv(Path(f"{SMOKE_PREFIX}_steps.csv"), online_step_rows(learner_seed, attack.audits, records))
    write_csv(Path(f"{SMOKE_PREFIX}_training.csv"), [training])
    v3.write_csv(Path(f"{SMOKE_PREFIX}_rollouts.csv"), rollout_rows)
    v3.write_csv(Path(f"{SMOKE_PREFIX}_base_decision.csv"), [base_decision])
    write_csv(Path(f"{SMOKE_PREFIX}_decision.csv"), [decision])
    print(decision)
    return decision


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--stage",
        required=True,
        choices=("offline_check", "s1_2070_smoke"),
    )
    return parser.parse_args()


def main() -> None:
    options = parse_args()
    if options.stage == "offline_check":
        run_offline_check()
    else:
        run_s1_2070_smoke()


if __name__ == "__main__":
    main()
