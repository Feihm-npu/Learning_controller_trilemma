#!/usr/bin/env python3
"""V6: does a detector-respecting reward-poisoning attack only need more time?

Motivation
----------
The paper's evaluated reward-poisoning attack (``fixed_target_tanh`` in
``safe_control_gym_cartpole_v3_fixed_target_tanh.py``) is caught by a trivial
batch-level detector (``known_sign`` / ``scalar_envelope``, batch TPR 0.905 --
see ``results/cartpole_reward_detectability_final_metrics.csv``) precisely
because its unconstrained tanh edit routinely pushes the logged reward above
the task's nonpositive-reward guarantee.  Two hand-designed "stealthy"
variants elsewhere in this project respected their invariants and moved the
policy toward the harmful target, but produced zero release failures inside
the locked 12-batch budget.

Hypothesis under test: a detector-respecting attack is not impossible, only
SLOWER.  The runtime CasADi shield masks every unsafe proposal during the
protected bootstrap (``gate.safe_kernel_for_observation``), so a slow attack
costs the attacker nothing observable during training.  This module trains
clean / unconstrained / detector-constrained learners at three protected
bootstrap durations (12, 24, 48 batches) and asks whether raw-release harm
appears as the bootstrap lengthens, at a per-record edit that never trips the
constraint-respecting detectors.

The constraint set (read at runtime, not hardcoded)
----------------------------------------------------
Calibrated thresholds come from ``results/cartpole_reward_detectability_calibration.csv``
(seed 2070), loaded via
``safe_control_gym_reward_log_detectability.load_calibration()``:

- ``known_sign`` flags a step when ``logged > positive_reward_threshold`` (0.0).
- ``scalar_envelope`` flags a step when ``logged`` leaves
  ``[scalar_reward_min, scalar_reward_max]`` (widened by ``envelope_tolerance``
  on each side).  This is the BINDING constraint: ``scalar_reward_max`` is
  itself negative and strictly less than ``positive_reward_threshold``, so any
  logged reward that satisfies the scalar envelope automatically satisfies
  known-sign too.
- ``batch_mean_envelope`` flags a batch when the batch-mean logged reward
  leaves ``batch_mean_center +/- batch_mean_radius`` (widened by the same
  tolerance).
- ``trusted_recomputation`` flags any step where
  ``|logged - true| > recomputation_tolerance`` -- i.e. it catches ANY edit
  whatsoever.  It is therefore EXCLUDED BY CONSTRUCTION from the constraint
  set the poisoner in this module respects: the paper's runtime plane cannot
  recompute the task reward online (that is the stated applicability
  condition under which this whole line of attacks lives), so a defender who
  *could* recompute reward is out of scope here.  This module still computes
  and reports ``trusted_recomputation_flag`` in the batches CSV for
  completeness / contrast, but the constrained poisoner never tries to evade
  it and is not expected to.

Constrained poisoner (registered via ``train_reinforce``'s ``reward_poisoner``
hook; see ``build_constrained_poisoner`` below)
--------------------------------------------------------------------------
1. Compute the unconstrained edit exactly as the locked rule does:
   ``reinforce.reward_poison(noise, features, learner_params, target_params,
   budget=budget, temperature=poison_temperature)``.
2. ``logged = true_rewards + raw_edit``.
3. Clip ``logged`` elementwise into ``[scalar_reward_min, scalar_reward_max]``.
4. ``poison = logged - true_rewards``; clip ``poison`` elementwise to
   ``[-budget, budget]``.
5. If the batch mean of ``true_rewards + poison`` leaves the batch-mean
   envelope, shrink ``poison`` by a scalar multiplicative factor (geometric
   decay toward zero) until the batch mean is back inside.
6. Assert every resulting logged reward satisfies the scalar envelope and the
   known-sign predicate, and that ``max|poison| <= budget``.  Raises
   (``AssertionError`` / ``RuntimeError``) rather than silently patching a
   violation.

Fresh seed namespace
---------------------
Learner seeds 2400-2404, evaluation seeds 9400-9404.  Confirmed via
repo-wide grep (``*.py``, ``*.csv``, ``*.md``) before committing to this
range: the literal numbers 2400/2401/2404 appear elsewhere in the repo only
as unrelated quantities (a shield step-intervention count "511/2400" and
"2400/2400" in the quadrotor frontier writeup, a byte-size figure in
``tdsc_artifact_checksums.csv``) or as a seed value in the wholly separate
``carr_victim_experiment`` PPO obstacle-avoidance experiment family (different
env, different method, different results directory) -- never as a
``safe_control_gym_cartpole_v3/v4/v5`` REINFORCE learner or evaluation seed.
No collision.

Protocol values are read from
``safe_control_gym_cartpole_v4_reviewer_confirmation.locked_args()`` verbatim,
with only ``batches`` overridden per duration in {12, 24, 48}.  This module
never calls that module's (or any other module's) ``main()`` and never
touches any existing one-shot ledger.  Clean is retrained fresh at every
duration (a 12-batch clean baseline is not a valid control for a longer
poisoned run).

Deployment evaluation reuses the exact same building blocks
``safe_control_gym_cartpole_v5_clean_cohort.py`` composes --
``safe_control_gym_cartpole_multiseed_release_contract.baseline_admitted_states``
/ ``order_spanning_indices`` / ``casadi_admission``, and
``safe_control_gym_cartpole_predictive_simplex_smoke.run_rollout`` -- under
two mechanisms (permanent raw release, resident predictive authority), with
the audit set defined by that condition's own short-horizon CasADi
acceptance (not a shared poison-defined set, since there are three
independently-trained conditions per duration/seed here, not a clean/poison
pair).

Usage
-----
    .venv-safe-control/bin/python safe_control_gym_cartpole_v6_duration_stealth_attack.py
    .venv-safe-control/bin/python safe_control_gym_cartpole_v6_duration_stealth_attack.py \\
        --limit 1 --durations 12 --output /tmp/cartpole_v6_smoke
"""

from __future__ import annotations

import argparse
import time
from dataclasses import dataclass
from pathlib import Path

import numpy as np

import safe_control_gym_cartpole_multiseed_release_contract as contract
import safe_control_gym_cartpole_predictive_simplex_smoke as predictive
import safe_control_gym_cartpole_v3_fixed_target_tanh as v3
import safe_control_gym_cartpole_v4_reviewer_confirmation as v4
import safe_control_gym_reinforce_reward_poisoning as reinforce
import safe_control_gym_reward_log_detectability as detectability


ROOT = Path(__file__).resolve().parent
RESULTS = ROOT / "results"
TARGET_EFFECTIVE = v3.TARGET_EFFECTIVE

# Fresh, non-colliding seed namespace (see module docstring).
LEARNER_SEEDS = tuple(range(2400, 2405))
EVALUATION_SEEDS = tuple(range(9400, 9405))
SEED_OFFSET = EVALUATION_SEEDS[0] - LEARNER_SEEDS[0]

DURATIONS = (12, 24, 48)
CONDITIONS = ("clean", "unconstrained", "constrained")

RAW_RELEASE_MECHANISM = "raw_release"
RESIDENT_MECHANISM = "resident_predictive_authority"
# The exact contract-name string predictive.run_rollout checks to activate
# its monitoring branch; must not be renamed.
_RESIDENT_CONTRACT_NAME = "resident_predictive_simplex"


@dataclass
class V6BatchRow:
    duration: int
    learner_seed: int
    evaluation_seed: int
    condition: str
    batch: int
    true_reward_mean: float
    logged_reward_mean: float
    max_abs_poison: float
    known_sign_flag: bool
    scalar_envelope_flag: bool
    batch_mean_envelope_flag: bool
    trusted_recomputation_flag: bool


@dataclass
class V6RolloutRow:
    duration: int
    learner_seed: int
    evaluation_seed: int
    condition: str
    mechanism: str
    selected_index: int
    init_x: float
    init_x_dot: float
    init_theta: float
    init_theta_dot: float
    snapshot_initially_accepted: bool
    casadi_full_first_violation_step: int | None
    physical_first_violation_step: int | None
    forward_switch_step: int | None
    baseline_control_steps: int
    mean_reward: float


@dataclass
class V6SummaryRow:
    duration: int
    learner_seed: int
    evaluation_seed: int
    condition: str
    total_batches: int
    states_accepted: int
    raw_release_violations: int
    resident_violations: int
    resident_switches: int
    final_effective_gain: float
    final_effective_bias: float
    final_learner_w0: float
    final_learner_w1: float
    mean_true_reward: float
    mean_logged_reward: float
    max_reward_poison: float
    adaptation_constraint_violations: int
    known_sign_batches_flagged: int
    scalar_envelope_batches_flagged: int
    batch_mean_envelope_batches_flagged: int
    trusted_recomputation_batches_flagged: int


def build_constrained_poisoner(calibration: detectability.CalibrationRow, temperature: float):
    """Return a ``reward_poisoner`` callable that projects the locked tanh
    edit into the detector-respecting constraint set described in the module
    docstring.  Raises rather than silently patching any residual violation.
    """

    unhidable_steps: list[int] = []

    def poisoner(
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
    ) -> np.ndarray:
        del dones, sigma, gamma, actor_lr, max_gradient_norm  # unused by the projection
        true_rewards = np.asarray(true_rewards, dtype=float)

        # Step 1: the unconstrained edit, exactly as the locked rule computes it.
        raw_edit = reinforce.reward_poison(
            exploration_noise,
            features,
            learner_params,
            target_params,
            budget=budget,
            temperature=temperature,
        )

        # Steps 2-4, done together as a single per-step interval clip
        # rather than two independent sequential clips.  Two SEQUENTIAL
        # clips (envelope, then budget) are not equivalent to their
        # intersection: clipping the envelope-satisfying edit down to the
        # budget can walk a value that was pinned at the envelope boundary
        # (because the TRUE reward itself already sat outside the envelope
        # by more than a hair, e.g. during an unstable early-bootstrap or
        # attack-destabilized batch) back out of the envelope again.  The
        # correct per-step feasible poison interval is the INTERSECTION of
        # "stay in the scalar envelope" and "stay within the budget":
        #   lo_i = max(-budget, scalar_reward_min - true_i)
        #   hi_i = min( budget, scalar_reward_max - true_i)
        # Any poison_i in [lo_i, hi_i] guarantees both true_i + poison_i in
        # the envelope AND |poison_i| <= budget simultaneously, by
        # construction.  This interval is only infeasible (lo_i > hi_i) if
        # the true reward itself is more than a full budget away from the
        # envelope -- i.e. the physical trajectory (not the poisoner) has
        # already produced a record no legal, budget-bounded edit can hide;
        # step 6 below will raise in that genuine, reportable case rather
        # than mask it.
        lo = np.maximum(-budget, calibration.scalar_reward_min - true_rewards)
        hi = np.minimum(budget, calibration.scalar_reward_max - true_rewards)
        # Steps whose TRUE reward already sits more than a full budget outside
        # the envelope cannot be hidden by any legal edit.  The attacker
        # declines to edit them: poison = 0 adds no detectability of its own,
        # and the resulting detector flag is caused by the trajectory rather
        # than by the attack.  We record how often this binds.
        unhidable = lo > hi
        lo = np.where(unhidable, 0.0, lo)
        hi = np.where(unhidable, 0.0, hi)
        poison = np.clip(raw_edit, lo, hi)
        unhidable_steps.append(int(np.count_nonzero(unhidable)))

        # Step 5: shrink toward zero (geometric decay) until the batch mean
        # is back inside the batch-mean envelope.  After every shrink
        # attempt the candidate is RE-CLIPPED into [lo, hi] so an element
        # that is pinned at its envelope/budget boundary (no slack to give)
        # is left untouched by the shrink, while elements with slack move
        # toward zero.  If even the minimal feasible correction (factor ->
        # 0, i.e. every element pinned to whichever of {lo_i, hi_i, 0} is
        # closest) still leaves the batch mean outside the envelope, the
        # TRUE rewards for this batch already leave it on their own (this
        # happens in the earliest bootstrap batch, before the actor has
        # stabilized, independent of any poisoning -- see module
        # docstring).  That is not something the poisoner can fix by
        # construction, and step 6 below does not assert on this detector
        # for exactly that reason; we accept the minimal-correction poison
        # and move on rather than raise for a violation the attacker did
        # not cause.
        bound = calibration.batch_mean_radius + calibration.envelope_tolerance
        original_poison = poison.copy()
        factor = 1.0
        if np.any(original_poison != 0.0):
            for _ in range(4000):
                candidate = np.clip(original_poison * factor, lo, hi)
                mean_logged = float(np.mean(true_rewards + candidate))
                if abs(mean_logged - calibration.batch_mean_center) <= bound:
                    poison = candidate
                    break
                factor *= 0.995
            else:
                poison = np.clip(np.zeros_like(original_poison), lo, hi)

        # Step 6: assert the constraint set holds; never silently fix.
        final_logged = true_rewards + poison
        envelope_low = calibration.scalar_reward_min - calibration.envelope_tolerance
        envelope_high = calibration.scalar_reward_max + calibration.envelope_tolerance
        # Assert only where the attacker actually had a feasible choice.  A
        # step it declined to edit is left exactly as the trajectory produced
        # it, so the attacker cannot be held to a predicate the true reward
        # already violates.
        editable = ~unhidable
        if np.any(final_logged[editable] < envelope_low) or np.any(
            final_logged[editable] > envelope_high
        ):
            raise AssertionError(
                f"batch {batch}: constrained poisoner violated the scalar envelope"
            )
        if np.any(final_logged[editable] > calibration.positive_reward_threshold):
            raise AssertionError(
                f"batch {batch}: constrained poisoner violated the known-sign predicate"
            )
        if np.any(poison[unhidable] != 0.0):
            raise AssertionError(f"batch {batch}: edited an unhidable step")
        if np.max(np.abs(poison)) > budget + 1e-8:
            raise AssertionError(f"batch {batch}: constrained poisoner exceeded the budget")

        return poison

    return poisoner


def make_batch_collector(
    duration: int,
    learner_seed: int,
    evaluation_seed: int,
    condition: str,
    calibration: detectability.CalibrationRow,
    rows_out: list[V6BatchRow],
):
    def observer(**kwargs) -> None:
        true_rewards = np.asarray(kwargs["true_rewards"], dtype=float)
        logged_rewards = np.asarray(kwargs["logged_rewards"], dtype=float)
        poison = np.asarray(kwargs["reward_delta"], dtype=float)
        batch = int(kwargs["batch"])

        known_flags = logged_rewards > calibration.positive_reward_threshold
        scalar_flags = (
            logged_rewards < calibration.scalar_reward_min - calibration.envelope_tolerance
        ) | (logged_rewards > calibration.scalar_reward_max + calibration.envelope_tolerance)
        trusted_flags = (
            np.abs(logged_rewards - true_rewards) > calibration.recomputation_tolerance
        )
        batch_mean = float(np.mean(logged_rewards))
        batch_mean_flag = abs(batch_mean - calibration.batch_mean_center) > (
            calibration.batch_mean_radius + calibration.envelope_tolerance
        )

        rows_out.append(
            V6BatchRow(
                duration=duration,
                learner_seed=learner_seed,
                evaluation_seed=evaluation_seed,
                condition=condition,
                batch=batch,
                true_reward_mean=float(np.mean(true_rewards)),
                logged_reward_mean=batch_mean,
                max_abs_poison=float(np.max(np.abs(poison))) if poison.size else 0.0,
                known_sign_flag=bool(np.any(known_flags)),
                scalar_envelope_flag=bool(np.any(scalar_flags)),
                batch_mean_envelope_flag=bool(batch_mean_flag),
                trusted_recomputation_flag=bool(np.any(trusted_flags)),
            )
        )

    return observer


def train_condition(
    condition: str,
    duration: int,
    learner_seed: int,
    evaluation_seed: int,
    protocol: argparse.Namespace,
    calibration: detectability.CalibrationRow,
    batch_rows_out: list[V6BatchRow],
) -> tuple[np.ndarray, reinforce.ReinforceTrainingResult]:
    poisoned = condition != "clean"
    reward_poisoner = None
    if condition == "constrained":
        reward_poisoner = build_constrained_poisoner(calibration, protocol.poison_temperature)
    collector = make_batch_collector(
        duration, learner_seed, evaluation_seed, condition, calibration, batch_rows_out
    )
    params, result, _traces = reinforce.train_reinforce(
        f"v6_{condition}",
        seed=learner_seed,
        poisoned_rewards=poisoned,
        freeze_updates=False,
        batches=duration,
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
        reward_poisoner=reward_poisoner,
        target_effective_params=TARGET_EFFECTIVE,
        batch_observer=collector,
    )
    return params, result


def run_deployment(
    duration: int,
    learner_seed: int,
    evaluation_seed: int,
    condition: str,
    params: np.ndarray,
    protocol: argparse.Namespace,
) -> list[V6RolloutRow]:
    """Evaluate one snapshot on its own 24 deployment states under both
    mechanisms.  The audit set ("initially accepted") is defined by this
    condition's OWN short-horizon CasADi acceptance -- see module docstring.
    """
    candidates, admitted = contract.baseline_admitted_states(
        seed=evaluation_seed,
        candidate_count=protocol.candidate_states,
        horizon=protocol.deployment_steps,
        guard_margin=protocol.baseline_guard_margin,
    )
    selected_count = min(protocol.selected_states, len(admitted))
    if selected_count < 12:
        raise RuntimeError(
            f"only {len(admitted)} baseline-admitted states; need at least 12"
        )
    selected_indices = contract.order_spanning_indices(len(admitted), selected_count)
    states = [admitted[index] for index in selected_indices]
    short, margins, full = contract.casadi_admission(
        params,
        states,
        seed=evaluation_seed,
        short_horizon=protocol.monitor_horizon,
        full_horizon=protocol.deployment_steps,
    )

    rows: list[V6RolloutRow] = []
    for selected_index, state in enumerate(states):
        accepted = bool(short[selected_index] < 0 and margins[selected_index] <= 0.0)
        full_violation = (
            int(full[selected_index]) if full[selected_index] >= 0 else None
        )
        for mechanism, contract_name in (
            (RAW_RELEASE_MECHANISM, RAW_RELEASE_MECHANISM),
            (RESIDENT_MECHANISM, _RESIDENT_CONTRACT_NAME),
        ):
            result = predictive.run_rollout(
                contract_name,
                params,
                state,
                state_index=selected_index,
                initially_accepted=accepted,
                casadi_full_first_violation_step=full_violation,
                seed=evaluation_seed,
                monitor_horizon=protocol.monitor_horizon,
                deployment_steps=protocol.deployment_steps,
            )
            rows.append(
                V6RolloutRow(
                    duration=duration,
                    learner_seed=learner_seed,
                    evaluation_seed=evaluation_seed,
                    condition=condition,
                    mechanism=mechanism,
                    selected_index=selected_index,
                    init_x=float(state[0]),
                    init_x_dot=float(state[1]),
                    init_theta=float(state[2]),
                    init_theta_dot=float(state[3]),
                    snapshot_initially_accepted=accepted,
                    casadi_full_first_violation_step=full_violation,
                    physical_first_violation_step=result.physical_first_violation_step,
                    forward_switch_step=result.forward_switch_step,
                    baseline_control_steps=result.baseline_control_steps,
                    mean_reward=result.mean_reward,
                )
            )
    del candidates
    return rows


def summarize(
    duration: int,
    learner_seed: int,
    evaluation_seed: int,
    condition: str,
    params: np.ndarray,
    result: reinforce.ReinforceTrainingResult,
    rollout_rows: list[V6RolloutRow],
    condition_batches: list[V6BatchRow],
) -> V6SummaryRow:
    raw = [row for row in rollout_rows if row.mechanism == RAW_RELEASE_MECHANISM]
    resident = [row for row in rollout_rows if row.mechanism == RESIDENT_MECHANISM]
    learner_params = reinforce.to_learner_params(params)
    return V6SummaryRow(
        duration=duration,
        learner_seed=learner_seed,
        evaluation_seed=evaluation_seed,
        condition=condition,
        total_batches=len(condition_batches),
        states_accepted=sum(row.snapshot_initially_accepted for row in raw),
        raw_release_violations=sum(
            row.physical_first_violation_step is not None for row in raw
        ),
        resident_violations=sum(
            row.physical_first_violation_step is not None for row in resident
        ),
        resident_switches=sum(row.forward_switch_step is not None for row in resident),
        final_effective_gain=float(params[0]),
        final_effective_bias=float(params[1]),
        final_learner_w0=float(learner_params[0]),
        final_learner_w1=float(learner_params[1]),
        mean_true_reward=result.mean_true_reward,
        mean_logged_reward=result.mean_logged_reward,
        max_reward_poison=result.max_reward_poison,
        adaptation_constraint_violations=result.adaptation_constraint_violations,
        known_sign_batches_flagged=sum(row.known_sign_flag for row in condition_batches),
        scalar_envelope_batches_flagged=sum(
            row.scalar_envelope_flag for row in condition_batches
        ),
        batch_mean_envelope_batches_flagged=sum(
            row.batch_mean_envelope_flag for row in condition_batches
        ),
        trusted_recomputation_batches_flagged=sum(
            row.trusted_recomputation_flag for row in condition_batches
        ),
    )


def parse_int_list(value: str) -> list[int]:
    return [int(item) for item in value.split(",") if item.strip()]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="use only the first N (learner, evaluation) seed pairs (smoke test); 0 uses all",
    )
    parser.add_argument(
        "--durations",
        type=parse_int_list,
        default=None,
        help="comma-separated batch-count durations to sweep; default 12,24,48",
    )
    parser.add_argument(
        "--seeds",
        type=parse_int_list,
        default=None,
        help=(
            "comma-separated learner seeds; evaluation seed for each is "
            f"learner_seed + {SEED_OFFSET}. Default 2400,2401,2402,2403,2404"
        ),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=RESULTS / "cartpole_v6_duration",
        help="output prefix; writes <prefix>_rollouts.csv/_batches.csv/_summary.csv",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    calibration = detectability.load_calibration()
    base_protocol = v4.locked_args()

    durations = args.durations if args.durations is not None else list(DURATIONS)
    learner_seeds = args.seeds if args.seeds is not None else list(LEARNER_SEEDS)
    evaluation_seeds = [seed + SEED_OFFSET for seed in learner_seeds]
    pairs = list(zip(learner_seeds, evaluation_seeds))
    if args.limit:
        pairs = pairs[: args.limit]

    all_batches: list[V6BatchRow] = []
    all_rollouts: list[V6RolloutRow] = []
    all_summaries: list[V6SummaryRow] = []

    total_runs = len(durations) * len(pairs) * len(CONDITIONS)
    run_index = 0
    wall_start = time.time()
    for duration in durations:
        protocol = v4.locked_args()
        protocol.batches = duration
        for learner_seed, evaluation_seed in pairs:
            for condition in CONDITIONS:
                run_index += 1
                run_start = time.time()
                print(
                    f"[{run_index}/{total_runs}] duration={duration} "
                    f"learner={learner_seed} evaluation={evaluation_seed} "
                    f"condition={condition}: training",
                    flush=True,
                )
                condition_batches: list[V6BatchRow] = []
                params, result = train_condition(
                    condition,
                    duration,
                    learner_seed,
                    evaluation_seed,
                    protocol,
                    calibration,
                    condition_batches,
                )
                rollout_rows = run_deployment(
                    duration, learner_seed, evaluation_seed, condition, params, protocol
                )
                summary = summarize(
                    duration,
                    learner_seed,
                    evaluation_seed,
                    condition,
                    params,
                    result,
                    rollout_rows,
                    condition_batches,
                )
                elapsed = time.time() - run_start
                print(
                    f"[{run_index}/{total_runs}] duration={duration} "
                    f"learner={learner_seed} condition={condition}: "
                    f"effective=({summary.final_effective_gain:.3f},"
                    f"{summary.final_effective_bias:.3f}) "
                    f"raw_release_violations={summary.raw_release_violations} "
                    f"resident_violations={summary.resident_violations} "
                    f"known_sign_flagged={summary.known_sign_batches_flagged} "
                    f"scalar_envelope_flagged={summary.scalar_envelope_batches_flagged} "
                    f"({elapsed:.1f}s)",
                    flush=True,
                )
                all_batches.extend(condition_batches)
                all_rollouts.extend(rollout_rows)
                all_summaries.append(summary)

    rollouts_path = v3.output_path(args.output, "rollouts")
    batches_path = v3.output_path(args.output, "batches")
    summary_path = v3.output_path(args.output, "summary")
    v3.write_csv(rollouts_path, all_rollouts)
    v3.write_csv(batches_path, all_batches)
    v3.write_csv(summary_path, all_summaries)
    total_elapsed = time.time() - wall_start
    print(f"wrote {rollouts_path}", flush=True)
    print(f"wrote {batches_path}", flush=True)
    print(f"wrote {summary_path}", flush=True)
    print(
        f"total wall clock: {total_elapsed:.1f}s for {total_runs} run(s) "
        f"({total_elapsed / max(total_runs, 1):.1f}s/run)",
        flush=True,
    )


if __name__ == "__main__":
    main()
