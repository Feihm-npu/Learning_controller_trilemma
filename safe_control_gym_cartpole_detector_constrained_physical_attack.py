#!/usr/bin/env python3
"""One burned-seed detector-constrained physical-objective reward attack."""

from __future__ import annotations

import csv
import hashlib
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass
from functools import partial
from itertools import product
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Iterable

import numpy as np

from safe_control_gym.utils.registration import make

import reward_certificate_geometry as geometry
import safe_control_gym_cartpole_multiseed_release_contract as contract
import safe_control_gym_cartpole_v3_fixed_target_tanh as v3
import safe_control_gym_delayed_trigger_attack as delayed
import safe_control_gym_plausible_set_lifecycle_gate as gate
import safe_control_gym_reinforce_reward_poisoning as reinforce
import safe_control_gym_reward_log_detectability as detector


ROOT = Path(__file__).resolve().parent
RESULTS = ROOT / "results"
PROTOCOL = ROOT / "cartpole_detector_constrained_physical_attack_protocol.md"
R1_DECISION = RESULTS / "cartpole_reward_ingestion_end_to_end_decision.csv"
CALIBRATION = RESULTS / "cartpole_reward_detectability_calibration.csv"
FROZEN_DETECTOR_DECISION = RESULTS / "cartpole_reward_detectability_final_decision.csv"
LOCKED_TRAINING = RESULTS / "cartpole_v3_fixed_target_multiseed_training.csv"
S2_DECISION = RESULTS / "cartpole_stealth_s2_2070_decision.csv"
OUTPUT_PREFIX = RESULTS / "cartpole_detector_constrained_physical_attack"

LEARNER_SEED = 2070
EVALUATION_SEED = 9070
ATTACK_SCORING_SEED = 6070
ATTACK_STATE_COUNT = 14
MIN_ATTACK_ACCEPTED_STATES = 12
RANDOM_CANDIDATES = 768
RANDOM_SEED_BASE = 42070
BISECTION_STEPS = 100
SCORING_CHUNK_SIZE = 64
SCORING_WORKERS = 17
REWARD_BUDGET = 2.0
TOLERANCE = 1e-10
EDIT_TOLERANCE = 1e-12
S2_TARGET_EFFECTIVE = np.asarray([-2.3625524160241205, -5.0], dtype=float)


@dataclass
class CandidateScore:
    gate_eligible: bool
    short_accepted: int
    long_violations: int
    worst_long_margin: float
    early_violation_score: int


@dataclass
class AttackBatch:
    learner_seed: int
    batch: int
    candidate_reward_vectors: int
    unique_next_snapshots: int
    attack_scoring_states: int
    selected_candidate_index: int
    selected_max_absolute_edit: float
    selected_edit_l2_norm: float
    changed_reward_steps: int
    logged_reward_min: float
    logged_reward_max: float
    logged_reward_mean: float
    positive_logged_rewards: int
    scalar_lower_violation: float
    scalar_upper_violation: float
    batch_mean_lower_violation: float
    batch_mean_upper_violation: float
    reward_budget_violation: float
    public_short_accepted: int
    public_long_violations: int
    public_worst_long_margin: float
    public_early_violation_score: int
    selected_next_gain: float
    selected_next_bias: float
    selection_latency_ms: float


@dataclass
class VerifiedAttackBatch:
    learner_seed: int
    batch: int
    candidate_reward_vectors: int
    unique_next_snapshots: int
    attack_scoring_states: int
    selected_candidate_index: int
    selected_max_absolute_edit: float
    selected_edit_l2_norm: float
    changed_reward_steps: int
    logged_reward_min: float
    logged_reward_max: float
    logged_reward_mean: float
    positive_logged_rewards: int
    scalar_lower_violation: float
    scalar_upper_violation: float
    batch_mean_lower_violation: float
    batch_mean_upper_violation: float
    reward_budget_violation: float
    public_short_accepted: int
    public_long_violations: int
    public_worst_long_margin: float
    public_early_violation_score: int
    selected_next_gain: float
    selected_next_bias: float
    selection_latency_ms: float
    learner_reward_delta_error: float
    learner_raw_gradient_error: float
    learner_next_parameter_error: float
    all_invariants_pass: bool


@dataclass
class StepRow:
    learner_seed: int
    batch: int
    step: int
    true_reward: float
    logged_reward: float
    reward_delta: float
    feature_gain_coordinate: float
    feature_bias_coordinate: float
    exploration_noise: float
    done: float


@dataclass
class DetectorRow:
    detector: str
    clean_false_positive_rate: float
    poisoned_batches: int
    flagged_poisoned_batches: int
    poisoned_true_positive_rate: float
    hard_constrained: bool


@dataclass
class AttackDecision:
    learner_seed: int
    evaluation_seed: int
    protocol_sha256: str
    harness_sha256: str
    r1_decision_sha256: str
    calibration_sha256: str
    frozen_detector_decision_sha256: str
    locked_training_sha256: str
    s2_decision_sha256: str
    r1_prerequisite_pass: bool
    audited_batches: int
    candidate_reward_vectors_total: int
    all_invariants_pass: bool
    max_learner_reward_delta_error: float
    max_learner_raw_gradient_error: float
    max_learner_next_parameter_error: float
    adaptation_constraint_violations: int
    reward_budget_integrity: bool
    nonzero_edit_batches: int
    attack_scoring_states: int
    final_gain: float
    final_bias: float
    known_sign_batch_tpr: float
    scalar_envelope_batch_tpr: float
    batch_mean_envelope_tpr: float
    trusted_recomputation_batch_tpr: float
    log_only_stealthy_under_frozen_scalar_checks: bool
    poison_initially_accepted: int
    clean_release_violations: int
    poisoned_release_violations: int
    resident_predictive_violations: int
    poison_only_discordant: int
    clean_only_discordant: int
    paired_release_failures_with_timely_switch: int
    paired_release_failures: int
    pair_keys_valid: bool
    detector_constrained_physical_smoke_pass: bool
    new_seed_namespace_opened: bool
    next_action: str


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as source:
        return list(csv.DictReader(source))


def write_rows(path: Path, rows: Iterable[object]) -> None:
    dictionaries = [asdict(row) for row in rows]
    if not dictionaries:
        raise RuntimeError(f"refusing to write empty result: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=list(dictionaries[0]))
        writer.writeheader()
        writer.writerows(dictionaries)


def output_path(suffix: str) -> Path:
    return Path(f"{OUTPUT_PREFIX}_{suffix}.csv")


def locked_args() -> SimpleNamespace:
    return SimpleNamespace(
        batches=12,
        batch_steps=8,
        rho=0.005,
        sigma=0.8,
        actor_lr=1.0,
        gamma=0.97,
        max_gradient_norm=1.0,
        reward_poison_budget=REWARD_BUDGET,
        poison_temperature=1.0,
        candidate_states=32,
        selected_states=24,
        monitor_horizon=5,
        deployment_steps=120,
        baseline_guard_margin=0.0075,
        action_grid_size=41,
    )


def project_box_sum_interval(
    desired: np.ndarray,
    lower: np.ndarray,
    upper: np.ndarray,
    allowed_sum_lower: float,
    allowed_sum_upper: float,
) -> np.ndarray:
    desired = np.asarray(desired, dtype=float)
    lower = np.asarray(lower, dtype=float)
    upper = np.asarray(upper, dtype=float)
    if np.any(lower > upper + 1e-12):
        raise ValueError("empty pointwise detector-constrained reward box")
    feasible_lower = max(float(np.sum(lower)), allowed_sum_lower)
    feasible_upper = min(float(np.sum(upper)), allowed_sum_upper)
    if feasible_lower > feasible_upper + 1e-12:
        raise ValueError("pointwise reward box misses batch-mean envelope")
    projected = np.clip(desired, lower, upper)
    total = float(np.sum(projected))
    if feasible_lower - 1e-12 <= total <= feasible_upper + 1e-12:
        return projected
    target = feasible_lower if total < feasible_lower else feasible_upper
    left = float(np.min(desired - upper) - 1.0)
    right = float(np.max(desired - lower) + 1.0)
    for _ in range(BISECTION_STEPS):
        middle = 0.5 * (left + right)
        candidate = np.clip(desired - middle, lower, upper)
        if float(np.sum(candidate)) > target:
            left = middle
        else:
            right = middle
    projected = np.clip(desired - 0.5 * (left + right), lower, upper)
    residual = float(np.sum(projected) - target)
    if abs(residual) > 1e-12:
        free = np.flatnonzero(
            np.logical_and(projected > lower + 1e-11, projected < upper - 1e-11)
        )
        if len(free) == 0:
            raise RuntimeError("no free coordinate for batch-sum residual repair")
        projected[free[0]] -= residual
    return projected


def batch_next_parameters(
    learner_params: np.ndarray,
    deltas: np.ndarray,
    *,
    features: np.ndarray,
    exploration_noise: np.ndarray,
    true_rewards: np.ndarray,
    dones: np.ndarray,
    sigma: float,
    gamma: float,
    actor_lr: float,
    max_gradient_norm: float,
) -> np.ndarray:
    score_matrix = geometry.gaussian_score_matrix(features, exploration_noise, sigma)
    operator = geometry.centered_return_operator(dones, gamma)
    logged = true_rewards.reshape(1, -1) + deltas
    centered = logged @ operator.T
    scales = np.linalg.norm(centered, axis=1) / np.sqrt(centered.shape[1])
    advantages = centered.copy()
    active = scales > 1e-8
    advantages[active] /= scales[active, None]
    gradients = advantages @ score_matrix / centered.shape[1]
    norms = np.linalg.norm(gradients, axis=1)
    clipped = norms > max_gradient_norm
    gradients[clipped] *= max_gradient_norm / norms[clipped, None]
    candidates = learner_params.reshape(1, -1) + actor_lr * gradients
    return np.minimum(np.maximum(candidates, reinforce.LEARNER_LOW), reinforce.LEARNER_HIGH)


class _LocalPhysicalScorer:
    def __init__(
        self, args: SimpleNamespace, states: list[np.ndarray] | None = None
    ) -> None:
        task_config, lqr_config, _cbf_config = gate.build_configs(ATTACK_SCORING_SEED)
        env_func = partial(make, "cartpole", **task_config)
        self.env = env_func(gui=False)
        self.ctrl = make("lqr", env_func, **lqr_config)
        self.ctrl.reset()
        observation, self.info = self.env.reset(seed=ATTACK_SCORING_SEED)
        self.ctrl.reset_before_run(observation, self.info, env=self.env)
        self.casadi_fd_func = self.env.symbolic.fd_func
        self.action_low = float(np.asarray(self.env.action_space.low).reshape(-1)[0])
        self.action_high = float(np.asarray(self.env.action_space.high).reshape(-1)[0])
        if states is None:
            viable = delayed.baseline_viable_states(
                self.ctrl,
                self.info,
                self.casadi_fd_func,
                delayed.deployment_envelope(),
                baseline_params=np.zeros(2),
                action_low=self.action_low,
                action_high=self.action_high,
                deployment_steps=args.deployment_steps,
                guard_margin=args.baseline_guard_margin,
            )
            if len(viable) < ATTACK_STATE_COUNT:
                raise RuntimeError(
                    f"only {len(viable)} attacker-owned baseline-viable states; "
                    f"need {ATTACK_STATE_COUNT}"
                )
            indices = contract.order_spanning_indices(len(viable), ATTACK_STATE_COUNT)
            self.states = [viable[index] for index in indices]
        else:
            self.states = [np.asarray(state, dtype=float).copy() for state in states]
        self.args = args

    def close(self) -> None:
        self.ctrl.close()
        self.env.close()

    def score_effective_chunk(self, chunk: np.ndarray) -> list[CandidateScore]:
        states = np.vstack(self.states)
        repeated_states = np.vstack([states for _ in chunk])
        repeated_params = np.repeat(chunk, len(states), axis=0)
        short_first, short_margins = delayed.casadi_deployment_outcomes(
            self.ctrl,
            self.info,
            self.casadi_fd_func,
            repeated_params,
            repeated_states,
            action_low=self.action_low,
            action_high=self.action_high,
            deployment_steps=self.args.monitor_horizon,
        )
        long_first, long_margins = delayed.casadi_deployment_outcomes(
            self.ctrl,
            self.info,
            self.casadi_fd_func,
            repeated_params,
            repeated_states,
            action_low=self.action_low,
            action_high=self.action_high,
            deployment_steps=self.args.deployment_steps,
        )
        count = len(chunk)
        short_first = short_first.reshape(count, len(states))
        short_margins = short_margins.reshape(count, len(states))
        long_first = long_first.reshape(count, len(states))
        long_margins = long_margins.reshape(count, len(states))
        output: list[CandidateScore] = []
        for (
            candidate_short,
            candidate_short_margin,
            candidate_long,
            candidate_margin,
        ) in zip(short_first, short_margins, long_first, long_margins):
            accepted = np.logical_and(
                candidate_short < 0, candidate_short_margin <= 0.0
            )
            violated = np.logical_and(accepted, candidate_long >= 0)
            accepted_margins = candidate_margin[accepted]
            worst = (
                float(np.max(accepted_margins))
                if len(accepted_margins)
                else -1e30
            )
            output.append(
                CandidateScore(
                    gate_eligible=(
                        int(np.sum(accepted)) >= MIN_ATTACK_ACCEPTED_STATES
                    ),
                    short_accepted=int(np.sum(accepted)),
                    long_violations=int(np.sum(violated)),
                    worst_long_margin=worst,
                    early_violation_score=int(
                        np.sum(
                            self.args.deployment_steps
                            - candidate_long[violated]
                        )
                    ),
                )
            )
        return output

class PhysicalScorer:
    """Exact parallel scorer with one independent CVODES function per worker."""

    def __init__(self, args: SimpleNamespace) -> None:
        first = _LocalPhysicalScorer(args)
        self.states = [state.copy() for state in first.states]
        self.workers = [first]
        self.workers.extend(
            _LocalPhysicalScorer(args, self.states)
            for _ in range(SCORING_WORKERS - 1)
        )
        self.executor = ThreadPoolExecutor(max_workers=SCORING_WORKERS)

    def close(self) -> None:
        self.executor.shutdown(wait=True)
        for worker in self.workers:
            worker.close()

    def score(self, learner_candidates: np.ndarray) -> list[CandidateScore]:
        effective = np.column_stack(
            (
                learner_candidates[:, 0] / reinforce.THETA_SCALE,
                learner_candidates[:, 1],
            )
        )
        chunks = [
            effective[start : start + SCORING_CHUNK_SIZE]
            for start in range(0, len(effective), SCORING_CHUNK_SIZE)
        ]
        if len(chunks) > len(self.workers):
            raise RuntimeError("candidate pool exceeds the locked scoring worker capacity")
        futures = [
            self.executor.submit(worker.score_effective_chunk, chunk)
            for worker, chunk in zip(self.workers, chunks)
        ]
        chunk_scores = [future.result() for future in futures]
        return [score for rows in chunk_scores for score in rows]


class DetectorConstrainedPhysicalAttack:
    def __init__(self, args: SimpleNamespace, calibration: detector.CalibrationRow):
        self.args = args
        self.calibration = calibration
        self.scorer = PhysicalScorer(args)
        self.audits: list[AttackBatch] = []
        self.deltas: list[np.ndarray] = []

    def close(self) -> None:
        self.scorer.close()

    def candidate_pool(self, **kwargs: Any) -> np.ndarray:
        batch = int(kwargs["batch"])
        rewards = np.asarray(kwargs["true_rewards"], dtype=float)
        features = np.asarray(kwargs["features"], dtype=float)
        noise = np.asarray(kwargs["exploration_noise"], dtype=float)
        current = np.asarray(kwargs["learner_params"], dtype=float)
        target = np.asarray(kwargs["target_params"], dtype=float)
        lower = np.maximum(-REWARD_BUDGET, self.calibration.scalar_reward_min - rewards)
        upper = np.minimum(
            REWARD_BUDGET,
            self.calibration.scalar_reward_max - rewards,
        )
        mean_lower = self.calibration.batch_mean_center - self.calibration.batch_mean_radius
        mean_upper = self.calibration.batch_mean_center + self.calibration.batch_mean_radius
        allowed_sum_lower = len(rewards) * mean_lower - float(np.sum(rewards))
        allowed_sum_upper = len(rewards) * mean_upper - float(np.sum(rewards))

        desired: list[np.ndarray] = []
        for corner in product((0.0, 1.0), repeat=len(rewards)):
            weights = np.asarray(corner, dtype=float)
            desired.append(lower + weights * (upper - lower))
        rng = np.random.default_rng(RANDOM_SEED_BASE + batch)
        random_weights = rng.random((RANDOM_CANDIDATES, len(rewards)))
        desired.extend(lower + random_weights * (upper - lower))
        desired.append(np.zeros_like(rewards))
        desired.append(
            reinforce.reward_poison(
                noise,
                features,
                current,
                target,
                budget=REWARD_BUDGET,
                temperature=1.0,
            )
        )
        s2_target = reinforce.to_learner_params(S2_TARGET_EFFECTIVE)
        desired.append(
            reinforce.reward_poison(
                noise,
                features,
                current,
                s2_target,
                budget=REWARD_BUDGET,
                temperature=1.0,
            )
        )
        projected = [
            project_box_sum_interval(
                row,
                lower,
                upper,
                allowed_sum_lower,
                allowed_sum_upper,
            )
            for row in desired
        ]
        unique: list[np.ndarray] = []
        seen: set[tuple[float, ...]] = set()
        for row in projected:
            key = tuple(np.round(row, 12))
            if key not in seen:
                seen.add(key)
                unique.append(row)
        return np.vstack(unique)

    def __call__(self, **kwargs: Any) -> np.ndarray:
        started = time.perf_counter()
        batch = int(kwargs["batch"])
        current = np.asarray(kwargs["learner_params"], dtype=float)
        rewards = np.asarray(kwargs["true_rewards"], dtype=float)
        deltas = self.candidate_pool(**kwargs)
        next_params = batch_next_parameters(
            current,
            deltas,
            features=np.asarray(kwargs["features"], dtype=float),
            exploration_noise=np.asarray(kwargs["exploration_noise"], dtype=float),
            true_rewards=rewards,
            dones=np.asarray(kwargs["dones"], dtype=float),
            sigma=float(kwargs["sigma"]),
            gamma=float(kwargs["gamma"]),
            actor_lr=float(kwargs["actor_lr"]),
            max_gradient_norm=float(kwargs["max_gradient_norm"]),
        )
        scores = self.scorer.score(next_params)
        selection = max(
            range(len(deltas)),
            key=lambda index: (
                int(scores[index].gate_eligible),
                scores[index].long_violations,
                scores[index].worst_long_margin,
                scores[index].early_violation_score,
                scores[index].short_accepted,
                -float(np.linalg.norm(deltas[index])),
                -index,
            ),
        )
        delta = deltas[selection].copy()
        score = scores[selection]
        logged = rewards + delta
        mean_lower = self.calibration.batch_mean_center - self.calibration.batch_mean_radius
        mean_upper = self.calibration.batch_mean_center + self.calibration.batch_mean_radius
        effective = reinforce.to_effective_params(next_params[selection])
        audit = AttackBatch(
            learner_seed=LEARNER_SEED,
            batch=batch,
            candidate_reward_vectors=len(deltas),
            unique_next_snapshots=len(
                {tuple(np.round(row, 10)) for row in next_params}
            ),
            attack_scoring_states=len(self.scorer.states),
            selected_candidate_index=selection,
            selected_max_absolute_edit=float(np.max(np.abs(delta))),
            selected_edit_l2_norm=float(np.linalg.norm(delta)),
            changed_reward_steps=int(np.sum(np.abs(delta) > EDIT_TOLERANCE)),
            logged_reward_min=float(np.min(logged)),
            logged_reward_max=float(np.max(logged)),
            logged_reward_mean=float(np.mean(logged)),
            positive_logged_rewards=int(np.sum(logged > 0.0)),
            scalar_lower_violation=float(
                max(0.0, self.calibration.scalar_reward_min - float(np.min(logged)))
            ),
            scalar_upper_violation=float(
                max(0.0, float(np.max(logged)) - self.calibration.scalar_reward_max)
            ),
            batch_mean_lower_violation=float(max(0.0, mean_lower - float(np.mean(logged)))),
            batch_mean_upper_violation=float(max(0.0, float(np.mean(logged)) - mean_upper)),
            reward_budget_violation=float(max(0.0, float(np.max(np.abs(delta))) - REWARD_BUDGET)),
            public_short_accepted=score.short_accepted,
            public_long_violations=score.long_violations,
            public_worst_long_margin=score.worst_long_margin,
            public_early_violation_score=score.early_violation_score,
            selected_next_gain=float(effective[0]),
            selected_next_bias=float(effective[1]),
            selection_latency_ms=1000.0 * (time.perf_counter() - started),
        )
        self.audits.append(audit)
        self.deltas.append(delta.copy())
        print(
            f"batch={batch} candidates={len(deltas)} accepted={score.short_accepted} "
            f"long_failures={score.long_violations} margin={score.worst_long_margin:.6f} "
            f"next=({effective[0]:.4f},{effective[1]:.4f})",
            flush=True,
        )
        return delta


def verify_batches(
    attack: DetectorConstrainedPhysicalAttack,
    records: list[dict[str, Any]],
) -> list[VerifiedAttackBatch]:
    if len(attack.audits) != len(records) or len(attack.deltas) != len(records):
        raise RuntimeError("attack audit and learner observer counts disagree")
    output: list[VerifiedAttackBatch] = []
    for audit, delta, record in zip(attack.audits, attack.deltas, records):
        reconstructed = reinforce.reinforce_gradient(
            record["features"],
            record["exploration_noise"],
            record["logged_rewards"],
            record["dones"],
            sigma=attack.args.sigma,
            gamma=attack.args.gamma,
        )
        gradient = reconstructed.copy()
        norm = float(np.linalg.norm(gradient))
        if norm > attack.args.max_gradient_norm:
            gradient *= attack.args.max_gradient_norm / norm
        expected_next = np.minimum(
            np.maximum(
                np.asarray(record["learner_params_before"], dtype=float)
                + attack.args.actor_lr * gradient,
                reinforce.LEARNER_LOW,
            ),
            reinforce.LEARNER_HIGH,
        )
        delta_error = float(
            np.linalg.norm(np.asarray(record["reward_delta"], dtype=float) - delta)
        )
        gradient_error = float(
            np.linalg.norm(np.asarray(record["raw_gradient"], dtype=float) - reconstructed)
        )
        next_error = float(
            np.linalg.norm(np.asarray(record["learner_params_after"], dtype=float) - expected_next)
        )
        invariant = bool(
            audit.positive_logged_rewards == 0
            and audit.scalar_lower_violation <= TOLERANCE
            and audit.scalar_upper_violation <= TOLERANCE
            and audit.batch_mean_lower_violation <= TOLERANCE
            and audit.batch_mean_upper_violation <= TOLERANCE
            and audit.reward_budget_violation <= TOLERANCE
            and delta_error <= TOLERANCE
            and gradient_error <= TOLERANCE
            and next_error <= TOLERANCE
        )
        output.append(
            VerifiedAttackBatch(
                **asdict(audit),
                learner_reward_delta_error=delta_error,
                learner_raw_gradient_error=gradient_error,
                learner_next_parameter_error=next_error,
                all_invariants_pass=invariant,
            )
        )
    return output


def step_rows(records: list[dict[str, Any]]) -> list[StepRow]:
    output: list[StepRow] = []
    for record in records:
        for step in range(len(record["true_rewards"])):
            output.append(
                StepRow(
                    learner_seed=LEARNER_SEED,
                    batch=int(record["batch"]),
                    step=step,
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


def detector_rows(
    records: list[dict[str, Any]], calibration: detector.CalibrationRow
) -> list[DetectorRow]:
    frozen_rows = read_rows(FROZEN_DETECTOR_DECISION)
    if len(frozen_rows) != 1:
        raise RuntimeError("expected one frozen detector decision")
    frozen = frozen_rows[0]
    flags = {
        "trusted_recomputation": [],
        "known_sign": [],
        "scalar_envelope": [],
        "batch_mean_envelope": [],
    }
    for record in records:
        logged = np.asarray(record["logged_rewards"], dtype=float)
        true = np.asarray(record["true_rewards"], dtype=float)
        flags["trusted_recomputation"].append(
            bool(np.any(np.abs(logged - true) > calibration.recomputation_tolerance))
        )
        flags["known_sign"].append(
            bool(np.any(logged > calibration.positive_reward_threshold))
        )
        flags["scalar_envelope"].append(
            bool(
                np.any(logged < calibration.scalar_reward_min - calibration.envelope_tolerance)
                or np.any(logged > calibration.scalar_reward_max + calibration.envelope_tolerance)
            )
        )
        flags["batch_mean_envelope"].append(
            abs(float(np.mean(logged)) - calibration.batch_mean_center)
            > calibration.batch_mean_radius + calibration.envelope_tolerance
        )
    false_positive = {
        "trusted_recomputation": float(frozen["trusted_recomputation_batch_fpr"]),
        "known_sign": float(frozen["known_sign_batch_fpr"]),
        "scalar_envelope": float(frozen["scalar_envelope_batch_fpr"]),
        "batch_mean_envelope": float(frozen["batch_mean_envelope_fpr"]),
    }
    return [
        DetectorRow(
            detector=name,
            clean_false_positive_rate=false_positive[name],
            poisoned_batches=len(values),
            flagged_poisoned_batches=sum(values),
            poisoned_true_positive_rate=float(np.mean(values)),
            hard_constrained=name
            in ("known_sign", "scalar_envelope", "batch_mean_envelope"),
        )
        for name, values in flags.items()
    ]


def locked_clean_params() -> np.ndarray:
    matching = [
        row
        for row in read_rows(LOCKED_TRAINING)
        if int(row["learner_seed"]) == LEARNER_SEED and row["mechanism"] == "clean"
    ]
    if len(matching) != 1:
        raise RuntimeError("missing locked clean 2070 snapshot")
    return np.asarray(
        [float(matching[0]["final_gain"]), float(matching[0]["final_bias"])],
        dtype=float,
    )


def main() -> None:
    r1_rows = read_rows(R1_DECISION)
    if len(r1_rows) != 1 or r1_rows[0]["systems_bridge_pass"] != "True":
        raise RuntimeError("R1 systems bridge did not authorize feasibility assessment")
    args = locked_args()
    calibration = detector.load_calibration()
    attack = DetectorConstrainedPhysicalAttack(args, calibration)
    records: list[dict[str, Any]] = []
    try:
        effective, training, traces = reinforce.train_reinforce(
            "detector_constrained_physical_objective",
            seed=LEARNER_SEED,
            poisoned_rewards=True,
            freeze_updates=False,
            batches=args.batches,
            batch_steps=args.batch_steps,
            rho=args.rho,
            sigma=args.sigma,
            actor_lr=args.actor_lr,
            gamma=args.gamma,
            max_gradient_norm=args.max_gradient_norm,
            reward_poison_budget=args.reward_poison_budget,
            poison_temperature=args.poison_temperature,
            deployment_steps=args.deployment_steps,
            action_grid_size=args.action_grid_size,
            kernel_backend="casadi",
            reward_poisoner=attack,
            target_effective_params=v3.TARGET_EFFECTIVE,
            batch_observer=lambda **kwargs: records.append(kwargs),
        )
    finally:
        attack.close()

    verified = verify_batches(attack, records)
    clean = locked_clean_params()
    rollouts = v3.run_contracts(
        LEARNER_SEED, EVALUATION_SEED, clean, effective, args
    )
    base_decision = v3.decide_seed(
        LEARNER_SEED,
        EVALUATION_SEED,
        training,
        v3.batch_rows(LEARNER_SEED, "detector_constrained_physical_objective", traces),
        rollouts,
        args,
    )
    detection = detector_rows(records, calibration)
    detection_lookup = {row.detector: row for row in detection}
    all_invariants = all(row.all_invariants_pass for row in verified)
    budget_integrity = bool(
        base_decision.budget_integrity
        and all(row.selected_max_absolute_edit <= REWARD_BUDGET + TOLERANCE for row in verified)
    )
    nonzero_batches = sum(row.changed_reward_steps > 0 for row in verified)
    scalar_stealth = bool(
        detection_lookup["known_sign"].poisoned_true_positive_rate < 0.5
        and detection_lookup["known_sign"].clean_false_positive_rate <= 0.05
        and detection_lookup["scalar_envelope"].poisoned_true_positive_rate < 0.5
        and detection_lookup["scalar_envelope"].clean_false_positive_rate <= 0.05
    )
    detector_constraints_pass = all(
        detection_lookup[name].poisoned_true_positive_rate == 0.0
        for name in ("known_sign", "scalar_envelope", "batch_mean_envelope")
    )
    effect_pass = base_decision.poison_only_discordant >= 1
    resident_pass = bool(
        base_decision.resident_predictive_violations == 0
        and base_decision.paired_release_failures_with_timely_switch
        == base_decision.paired_release_failures
    )
    smoke_pass = bool(
        all_invariants
        and training.adaptation_constraint_violations == 0
        and budget_integrity
        and nonzero_batches > 0
        and detector_constraints_pass
        and base_decision.poison_initially_accepted >= 12
        and effect_pass
        and resident_pass
        and base_decision.pair_keys_valid
    )
    if not all_invariants or not budget_integrity or not base_decision.pair_keys_valid:
        next_action = "diagnose_implementation_without_changing_attack"
    elif smoke_pass:
        next_action = "positive_burned_smoke_requires_separate_confirmation_decision"
    else:
        next_action = "close_r2_insufficient_physical_effect_no_new_seeds"
    decision = AttackDecision(
        learner_seed=LEARNER_SEED,
        evaluation_seed=EVALUATION_SEED,
        protocol_sha256=digest(PROTOCOL),
        harness_sha256=digest(Path(__file__)),
        r1_decision_sha256=digest(R1_DECISION),
        calibration_sha256=digest(CALIBRATION),
        frozen_detector_decision_sha256=digest(FROZEN_DETECTOR_DECISION),
        locked_training_sha256=digest(LOCKED_TRAINING),
        s2_decision_sha256=digest(S2_DECISION),
        r1_prerequisite_pass=True,
        audited_batches=len(verified),
        candidate_reward_vectors_total=sum(row.candidate_reward_vectors for row in verified),
        all_invariants_pass=all_invariants,
        max_learner_reward_delta_error=max(row.learner_reward_delta_error for row in verified),
        max_learner_raw_gradient_error=max(row.learner_raw_gradient_error for row in verified),
        max_learner_next_parameter_error=max(row.learner_next_parameter_error for row in verified),
        adaptation_constraint_violations=training.adaptation_constraint_violations,
        reward_budget_integrity=budget_integrity,
        nonzero_edit_batches=nonzero_batches,
        attack_scoring_states=len(attack.scorer.states),
        final_gain=float(effective[0]),
        final_bias=float(effective[1]),
        known_sign_batch_tpr=detection_lookup["known_sign"].poisoned_true_positive_rate,
        scalar_envelope_batch_tpr=detection_lookup[
            "scalar_envelope"
        ].poisoned_true_positive_rate,
        batch_mean_envelope_tpr=detection_lookup[
            "batch_mean_envelope"
        ].poisoned_true_positive_rate,
        trusted_recomputation_batch_tpr=detection_lookup[
            "trusted_recomputation"
        ].poisoned_true_positive_rate,
        log_only_stealthy_under_frozen_scalar_checks=scalar_stealth,
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
        pair_keys_valid=base_decision.pair_keys_valid,
        detector_constrained_physical_smoke_pass=smoke_pass,
        new_seed_namespace_opened=False,
        next_action=next_action,
    )
    write_rows(output_path("batches"), verified)
    write_rows(output_path("steps"), step_rows(records))
    write_rows(output_path("training"), [training])
    v3.write_csv(output_path("rollouts"), rollouts)
    v3.write_csv(output_path("base_decision"), [base_decision])
    write_rows(output_path("detectors"), detection)
    write_rows(output_path("decision"), [decision])
    print(decision)


if __name__ == "__main__":
    main()
