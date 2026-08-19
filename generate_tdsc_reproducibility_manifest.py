#!/usr/bin/env python3
"""Generate the locked USENIX research-track manifest and SHA-256 inventory."""

from __future__ import annotations

import csv
import hashlib
import importlib.metadata
import platform
import subprocess
import sys
from pathlib import Path
from typing import Iterable


ROOT = Path(__file__).resolve().parent
RESULTS = ROOT / "results"
PAPER = ROOT / "paper_latex"
# Relative interpreter: the manifest ships to anonymous review, so no
# absolute home path may appear in it.
PYTHON = "python3"
LOCK_DATE = "2026-08-19"


def run_first_line(command: list[str]) -> str:
    completed = subprocess.run(
        command,
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    text = completed.stdout.strip() or completed.stderr.strip()
    return text.splitlines()[0] if text else "unavailable"


def distribution_version(name: str) -> str:
    try:
        return importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:
        return "unavailable"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def add_files(
    inventory: list[tuple[str, Path]],
    role: str,
    relative_paths: Iterable[str],
) -> None:
    inventory.extend((role, ROOT / relative) for relative in relative_paths)


def artifact_inventory() -> list[tuple[str, Path]]:
    inventory: list[tuple[str, Path]] = []
    add_files(
        inventory,
        "protocol",
        (
            "tdsc_evidence_map.md",
            "tdsc_internal_scientific_review.md",
            "tdsc_subagent_novelty_review.md",
            "tdsc_certificate_evasion_pivot_results.md",
            "tdsc_certificate_coverage_protocol.md",
            "tdsc_security_availability_frontier_protocol.md",
            "tdsc_trusted_anchor_protocol.md",
            "ppo_b_lite_protocol.md",
            "benign_utility_protocol.md",
            "cartpole_release_contract_smoke_protocol.md",
            "cartpole_predictive_simplex_smoke_protocol.md",
            "cartpole_certificate_evasion_smoke_protocol.md",
            "cartpole_reward_geometry_smoke_protocol.md",
            "cartpole_multiseed_release_contract_protocol.md",
            "cartpole_prospective_gate_aware_attack_protocol.md",
            "cartpole_v3_fixed_target_tanh_protocol.md",
            "reviewer_uplift_experiment_protocol.md",
            "stealth_temporal_reward_wp_brainstorm.md",
            "stealth_temporal_reward_wp_stage1_protocol.md",
            "stealth_temporal_reward_wp_s2_protocol.md",
            "clipped_reward_influence_theory_wp.md",
            "theory_optimization_literature_route.md",
            "threat_model_realism_review.md",
            "homogenized_gate_aware_poststop_protocol.md",
            "usenix_submission_plan.md",
            "usenix_submission_status.md",
            "usenix_direction_audit_0819.md",
            "carr_victim_experiment/README.md",
            "carr_victim_experiment/patches.md",
            "carr_victim_experiment/protocol.md",
            "u1_second_learner_family_protocol.md",
            "u2_joint_channel_protocol.md",
            "u3_inloop_defense_protocol.md",
        ),
    )
    add_files(
        inventory,
        "experiment_source",
        (
            "lifecycle_gate_benchmark.py",
            "two_tank_lifecycle_benchmark.py",
            "nonlinear_tank_lifecycle_benchmark.py",
            "parameter_update_gate_benchmark.py",
            "matrix_parameter_gate_benchmark.py",
            "adaptive_attack_benchmark.py",
            "safe_control_gym_paper_sweep.py",
            "safe_control_gym_reinforce_reward_poisoning.py",
            "safe_control_gym_reinforce_reward_poisoning_sweep.py",
            "safe_control_gym_quadrotor_reinforce_reward_poisoning.py",
            "safe_control_gym_quadrotor_reinforce_reward_poisoning_sweep.py",
            "safe_control_gym_quadrotor_ppo_baseline.py",
            "safe_control_gym_quadrotor_ppo_reward_poisoning.py",
            "safe_control_gym_quadrotor_benign_utility.py",
            "safe_control_gym_quadrotor_certificate_coverage.py",
            "safe_control_gym_quadrotor_security_availability_frontier.py",
            "safe_control_gym_quadrotor_trusted_anchor_audit.py",
            "safe_control_gym_quadrotor_mpsc_baseline.py",
            "reward_certificate_geometry.py",
            "safe_control_gym_cartpole_release_contract_smoke.py",
            "safe_control_gym_cartpole_predictive_simplex_smoke.py",
            "safe_control_gym_cartpole_certificate_evasion_smoke.py",
            "safe_control_gym_cartpole_reward_geometry_smoke.py",
            "safe_control_gym_cartpole_multiseed_release_contract.py",
            "safe_control_gym_cartpole_prospective_gate_aware_attack.py",
            "safe_control_gym_cartpole_reward_direction_diagnostic.py",
            "safe_control_gym_cartpole_gate_aware_v2_exploration.py",
            "safe_control_gym_cartpole_v3_fixed_target_tanh.py",
            "safe_control_gym_cartpole_horizon_contract_sweep.py",
            "make_fig_horizon_contract.py",
            "safe_control_gym_cartpole_trajectory_influence_audit.py",
            "safe_control_gym_cartpole_clipped_influence_audit.py",
            "safe_control_gym_cartpole_homogenized_gate_aware_diagnostic.py",
            "safe_control_gym_reward_log_detectability.py",
            "safe_control_gym_cartpole_v4_reviewer_confirmation.py",
            "safe_control_gym_cartpole_v4_clean_resident_arm.py",
            "safe_control_gym_cartpole_v5_clean_cohort.py",
            "analyze_v5_clean_cohort.py",
            "safe_control_gym_cartpole_v6_duration_stealth_attack.py",
            "carr_victim_experiment/analyze_disagreement_marker.py",
            "carr_victim_experiment/analyze_two_sided_and_null.py",
            "carr_victim_experiment/susceptibility_corpus.py",
            "safe_control_gym_cartpole_sparse_reward_permutation.py",
            "safe_control_gym_cartpole_moment_preserving_reward.py",
            "safe_control_gym_cartpole_a2c_reward_poisoning.py",
            "safe_control_gym_cartpole_joint_channel_poisoning.py",
            "safe_control_gym_cartpole_inloop_defense.py",
            "test_lifecycle_gate_semantics.py",
            "test_moment_preserving_reward.py",
            "test_reward_certificate_geometry.py",
            "test_reviewer_uplift_experiments.py",
            "test_sparse_reward_permutation.py",
            "test_tdsc_submission_artifacts.py",
        ),
    )
    add_files(
        inventory,
        "third_party_driver_patch",
        ("carr_victim_experiment/upstream/carr_reward_poisoning.patch",),
    )
    inventory.extend(
        ("third_party_run_script", path)
        for path in sorted((ROOT / "carr_victim_experiment/server_scripts").glob("*.sh"))
    )
    add_files(
        inventory,
        "artifact_generator",
        (
            "generate_benchmark_artifacts.py",
            "generate_tdsc_result_table.py",
            "generate_tdsc_frontier_artifacts.py",
            "generate_tdsc_anchor_artifacts.py",
            "generate_tdsc_reproducibility_manifest.py",
        ),
    )
    add_files(
        inventory,
        "expository_result",
        (
            "results/lifecycle_gate_1d.csv",
            "results/lifecycle_gate_two_tank.csv",
            "results/lifecycle_gate_nonlinear_tank.csv",
            "results/parameter_update_gate.csv",
            "results/matrix_parameter_update_gate.csv",
            "results/adaptive_attack_gate.csv",
            "results/lifecycle_gate_all.csv",
            "results/safe_control_gym_paper_mini_raw.csv",
            "results/safe_control_gym_paper_mini_aggregate.csv",
        ),
    )
    add_files(
        inventory,
        "primary_cartpole_result",
        (
            "results/safe_control_gym_reinforce_reward_poisoning_sweep.csv",
            "results/safe_control_gym_reinforce_reward_poisoning_aggregate.csv",
            "results/safe_control_gym_reinforce_reward_poisoning_sweep_rollouts.csv",
            "results/safe_control_gym_reinforce_reward_poisoning_traces.csv",
        ),
    )
    add_files(
        inventory,
        "primary_quadrotor_result",
        (
            "results/safe_control_gym_quadrotor_reinforce_reward_poisoning_sweep.csv",
            "results/safe_control_gym_quadrotor_reinforce_reward_poisoning_aggregate.csv",
            "results/safe_control_gym_quadrotor_reinforce_reward_poisoning_sweep_rollouts.csv",
            "results/safe_control_gym_quadrotor_reinforce_reward_poisoning_sweep_traces.csv",
            "results/safe_control_gym_quadrotor_reinforce_reward_poisoning_gate.csv",
        ),
    )
    add_files(
        inventory,
        "ppo_boundary_result",
        (
            "results/safe_control_gym_quadrotor_ppo_baseline.csv",
            "results/safe_control_gym_quadrotor_ppo_baseline_summary.csv",
            "results/safe_control_gym_quadrotor_ppo_b_lite_summary.csv",
            "results/safe_control_gym_quadrotor_ppo_b_lite_rollouts.csv",
            "results/safe_control_gym_quadrotor_ppo_b_lite_traces.csv",
            "results/safe_control_gym_quadrotor_ppo_b_lite_gate.csv",
        ),
    )
    add_files(
        inventory,
        "benign_utility_boundary_result",
        (
            "results/safe_control_gym_quadrotor_benign_utility_calibration.csv",
            "results/safe_control_gym_quadrotor_benign_utility_smoke_training.csv",
            "results/safe_control_gym_quadrotor_benign_utility_smoke_traces.csv",
            "results/safe_control_gym_quadrotor_benign_utility_smoke_rollouts.csv",
            "results/safe_control_gym_quadrotor_benign_utility_smoke_aggregate.csv",
            "results/safe_control_gym_quadrotor_benign_utility_smoke_decision.csv",
        ),
    )
    add_files(
        inventory,
        "coverage_result",
        (
            "results/safe_control_gym_quadrotor_certificate_coverage_physical.csv",
            "results/safe_control_gym_quadrotor_certificate_coverage_pairs.csv",
            "results/safe_control_gym_quadrotor_certificate_coverage_aggregate.csv",
            "results/safe_control_gym_quadrotor_certificate_coverage_decision.csv",
        ),
    )
    add_files(
        inventory,
        "unified_frontier_result",
        tuple(
            "results/safe_control_gym_quadrotor_security_availability_frontier_"
            + suffix
            + ".csv"
            for suffix in (
                "admission",
                "admission_summary",
                "offline_commit_timing",
                "steps",
                "rollouts",
                "summary",
                "validity",
            )
        ),
    )
    add_files(
        inventory,
        "trusted_anchor_result",
        tuple(
            "results/safe_control_gym_quadrotor_trusted_anchor_"
            + suffix
            + ".csv"
            for suffix in (
                "reference",
                "certificates",
                "deployment_states",
                "physical",
                "summary",
                "validity",
            )
        ),
    )
    anchor_caches = sorted(
        (RESULTS / "trusted_anchor_certificate_cache").glob(
            "seed_*_fractions_*.npz"
        )
    )
    if len(anchor_caches) != 9:
        raise RuntimeError(
            f"expected nine trusted-anchor cache chunks, found {len(anchor_caches)}"
        )
    inventory.extend(("trusted_anchor_cache", path) for path in anchor_caches)
    add_files(
        inventory,
        "generated_result",
        (
            "results/tdsc_core_results.csv",
            "results/tdsc_coverage_results.csv",
            "results/tdsc_frontier_results.csv",
            "results/tdsc_frontier_admission.csv",
            "results/tdsc_frontier_paired_reward_deltas.csv",
            "results/tdsc_anchor_results.csv",
            "results/tdsc_anchor_paired_reward_deltas.csv",
        ),
    )
    add_files(
        inventory,
        "release_contract_result",
        (
            "results/cartpole_release_contract_smoke_rollouts.csv",
            "results/cartpole_release_contract_smoke_summary.csv",
            "results/cartpole_predictive_simplex_smoke_rollouts.csv",
            "results/cartpole_predictive_simplex_smoke_summary.csv",
            "results/cartpole_certificate_evasion_target_candidates.csv",
            "results/cartpole_certificate_evasion_smoke_decision.csv",
            "results/cartpole_reward_geometry_smoke_rows.csv",
            "results/cartpole_reward_geometry_smoke_decision.csv",
            "results/cartpole_multiseed_release_contract_rows.csv",
            "results/cartpole_multiseed_release_contract_summary.csv",
            "results/cartpole_multiseed_release_contract_decision.csv",
            "results/cartpole_prospective_gate_aware_batches.csv",
            "results/cartpole_prospective_gate_aware_training.csv",
            "results/cartpole_prospective_gate_aware_rollouts.csv",
            "results/cartpole_prospective_gate_aware_decision.csv",
            "results/cartpole_reward_direction_diagnostic.csv",
            "results/cartpole_gate_aware_v2_exploratory_batches.csv",
            "results/cartpole_gate_aware_v2_exploratory_training.csv",
            "results/cartpole_gate_aware_v2_exploratory_rollouts.csv",
            "results/cartpole_gate_aware_v2_exploratory_decision.csv",
            "results/cartpole_v3_fixed_target_development_batches.csv",
            "results/cartpole_v3_fixed_target_development_training.csv",
            "results/cartpole_v3_fixed_target_development_rollouts.csv",
            "results/cartpole_v3_fixed_target_development_decision.csv",
            "results/cartpole_v3_fixed_target_development_aggregate.csv",
            "results/cartpole_v3_fixed_target_multiseed_batches.csv",
            "results/cartpole_v3_fixed_target_multiseed_training.csv",
            "results/cartpole_v3_fixed_target_multiseed_rollouts.csv",
            "results/cartpole_v3_fixed_target_multiseed_decision.csv",
            "results/cartpole_v3_fixed_target_multiseed_aggregate.csv",
            "results/cartpole_horizon_contract_sweep_rows.csv",
            "results/cartpole_horizon_contract_sweep_summary.csv",
            "results/cartpole_horizon_contract_sweep_decision.csv",
            "results/cartpole_v3_trajectory_influence_steps.csv",
            "results/cartpole_v3_trajectory_influence_batches.csv",
            "results/cartpole_v3_trajectory_influence_release_path.csv",
            "results/cartpole_v3_trajectory_influence_decision.csv",
            "results/cartpole_v3_clipped_influence_batches.csv",
            "results/cartpole_v3_clipped_influence_decision.csv",
            "results/cartpole_homogenized_gate_aware_2060_batches.csv",
            "results/cartpole_homogenized_gate_aware_2060_training.csv",
            "results/cartpole_homogenized_gate_aware_2060_rollouts.csv",
            "results/cartpole_homogenized_gate_aware_2060_decision.csv",
            "results/cartpole_reward_detectability_calibration.csv",
            "results/cartpole_reward_detectability_freeze.csv",
            "results/cartpole_reward_detectability_known_v3_metrics.csv",
            "results/cartpole_reward_detectability_known_v3_decision.csv",
            "results/cartpole_reward_detectability_final_metrics.csv",
            "results/cartpole_reward_detectability_final_decision.csv",
            "results/cartpole_v4_untouched_confirmation_opened.csv",
            "results/cartpole_v4_untouched_confirmation_batches.csv",
            "results/cartpole_v4_untouched_confirmation_training.csv",
            "results/cartpole_v4_untouched_confirmation_rollouts.csv",
            "results/cartpole_v4_clean_resident_arm_rollouts.csv",
            "results/cartpole_v4_clean_resident_arm_summary.csv",
            "results/cartpole_v5_clean_cohort_rollouts.csv",
            "results/cartpole_v5_clean_cohort_summary.csv",
            "results/cartpole_v6_duration_rollouts.csv",
            "results/cartpole_v6_duration_batches.csv",
            "results/cartpole_v6_duration_summary.csv",
            "carr_victim_experiment/results/disagreement_marker.csv",
            "carr_victim_experiment/results/two_sided_accounting.csv",
            "carr_victim_experiment/results/clean_clean_null.csv",
            "carr_victim_experiment/results/aggregate_table_v2.csv",
            "results/cartpole_v4_untouched_confirmation_decision.csv",
            "results/cartpole_v4_untouched_confirmation_aggregate.csv",
            "results/cartpole_v4_untouched_confirmation_steps.csv",
            "results/cartpole_stealth_s1_offline_batches.csv",
            "results/cartpole_stealth_s1_offline_decision.csv",
            "results/cartpole_stealth_s1_2070_permutation_batches.csv",
            "results/cartpole_stealth_s1_2070_steps.csv",
            "results/cartpole_stealth_s1_2070_training.csv",
            "results/cartpole_stealth_s1_2070_rollouts.csv",
            "results/cartpole_stealth_s1_2070_base_decision.csv",
            "results/cartpole_stealth_s1_2070_decision.csv",
            "results/cartpole_stealth_s2_2070_projection_batches.csv",
            "results/cartpole_stealth_s2_2070_steps.csv",
            "results/cartpole_stealth_s2_2070_training.csv",
            "results/cartpole_stealth_s2_2070_rollouts.csv",
            "results/cartpole_stealth_s2_2070_base_decision.csv",
            "results/cartpole_stealth_s2_2070_decision.csv",
            "results/cartpole_stealth_wp_decision.csv",
        ),
    )
    add_files(
        inventory,
        "second_family_result",
        (
            "results/cartpole_a2c_reward_poisoning_multiseed_summary.csv",
            "results/cartpole_a2c_reward_poisoning_multiseed_rollouts.csv",
            "results/cartpole_a2c_reward_poisoning_multiseed_traces.csv",
            "results/cartpole_a2c_reward_poisoning_multiseed_decision.csv",
            "results/cartpole_a2c_reward_poisoning_multiseed_per_seed.csv",
        ),
    )
    add_files(
        inventory,
        "uplift_result",
        (
            "results/cartpole_joint_channel_poisoning_multiseed_frontier.csv",
            "results/cartpole_joint_channel_poisoning_multiseed_rollouts.csv",
            "results/cartpole_joint_channel_poisoning_multiseed_decision.csv",
            "results/cartpole_inloop_defense_multiseed_per_seed.csv",
            "results/cartpole_inloop_defense_multiseed_decision.csv",
        ),
    )
    inventory.extend(
        ("paper_source", path)
        for path in (
            PAPER / "usenix_sec2027.tex",
            PAPER / "usenix.sty",
            PAPER / "reference.bib",
            PAPER / "IEEEtran.bst",
            *sorted((PAPER / "sections").glob("*.tex")),
            *sorted((PAPER / "generated").glob("*.tex")),
        )
    )
    add_files(
        inventory,
        "paper_figure",
        (
            "paper_latex/figures/lifecycle_gate_summary.pdf",
            "paper_latex/figures/parameter_gate_summary.pdf",
            "paper_latex/figures/matrix_parameter_gate_summary.pdf",
            "paper_latex/figures/adaptive_attack_summary.pdf",
            "paper_latex/figures/safe_control_gym_paper_mini_summary.pdf",
            "paper_latex/figures/fig4_frontier.pdf",
            "paper_latex/figures/fig5_disagreement_curves.pdf",
            "paper_latex/figures/fig6_retirement_isolation_summary.pdf",
            "paper_latex/figures/fig7_dose_response.pdf",
            "paper_latex/figures/fig8_2x2_susceptibility.pdf",
            "paper_latex/figures/fig6_ppo_isolation.pdf",
            "paper_latex/figures/fig9_mechanism_divergence.pdf",
            "paper_latex/figures/fig10_horizon_contract.pdf",
        ),
    )
    add_files(
        inventory,
        "upstream_model",
        (
            "external/safe-control-gym/examples/mpsc/models/linear_mpsc_quadrotor_2D.pkl",
            "external/safe-control-gym/examples/rl/models/ppo/ppo_model_quadrotor_2D_stab.pt",
        ),
    )
    add_files(
        inventory,
        "submission_pdf",
        ("paper_latex/usenix_sec2027.pdf",),
    )

    unique: dict[Path, str] = {}
    for role, path in inventory:
        unique.setdefault(path, role)
    missing = [path.relative_to(ROOT) for path in unique if not path.is_file()]
    if missing:
        raise FileNotFoundError(
            "missing required artifacts: " + ", ".join(map(str, missing))
        )
    return [(role, path) for path, role in unique.items()]


def environment_rows() -> list[dict[str, str]]:
    git_sha = run_first_line(
        ["git", "-C", str(ROOT / "external/safe-control-gym"), "rev-parse", "HEAD"]
    )
    rows = [
        {
            "component": "manifest_lock_date",
            "version": LOCK_DATE,
            "source": "usenix_direction_audit_0819.md",
        },
        {
            "component": "python",
            "version": sys.version.replace("\n", " "),
            "source": Path(sys.executable).name,
        },
        {
            "component": "platform",
            "version": platform.platform(),
            "source": "platform.platform()",
        },
        {
            "component": "safe-control-gym_git",
            "version": git_sha,
            "source": "external/safe-control-gym",
        },
        {
            "component": "latexmk",
            "version": run_first_line(["latexmk", "-version"]),
            "source": "PATH",
        },
        {
            "component": "pdfTeX",
            "version": run_first_line(["pdflatex", "--version"]),
            "source": "PATH",
        },
    ]
    for distribution in (
        "safe-control-gym",
        "numpy",
        "scipy",
        "casadi",
        "torch",
        "gymnasium",
        "pybullet",
        "matplotlib",
        "pandas",
        "pytest",
    ):
        rows.append(
            {
                "component": distribution,
                "version": distribution_version(distribution),
                "source": "importlib.metadata",
            }
        )
    return rows


def commands() -> list[tuple[str, str]]:
    return [
        ("Expository artifacts", f"{PYTHON} generate_benchmark_artifacts.py"),
        (
            "Cartpole confirmatory learner audit",
            f"{PYTHON} safe_control_gym_reinforce_reward_poisoning_sweep.py",
        ),
        (
            "Quadrotor confirmatory learner audit",
            f"{PYTHON} safe_control_gym_quadrotor_reinforce_reward_poisoning_sweep.py",
        ),
        (
            "Official PPO baseline and constructed target diagnostic",
            f"{PYTHON} safe_control_gym_quadrotor_ppo_baseline.py --include-target",
        ),
        (
            "Locked PPO B-lite checkpoints",
            (
                f"{PYTHON} safe_control_gym_quadrotor_ppo_reward_poisoning.py "
                "--batches 24 --checkpoint-batches 16 24 "
                "--training-state-count 8 --deployment-rollouts 24 "
                "--summary-out results/safe_control_gym_quadrotor_ppo_b_lite_summary.csv "
                "--rollouts-out results/safe_control_gym_quadrotor_ppo_b_lite_rollouts.csv "
                "--traces-out results/safe_control_gym_quadrotor_ppo_b_lite_traces.csv "
                "--gate-out results/safe_control_gym_quadrotor_ppo_b_lite_gate.csv"
            ),
        ),
        (
            "Locked benign-utility calibration and smoke",
            f"{PYTHON} safe_control_gym_quadrotor_benign_utility.py --mode all",
        ),
        (
            "P1 certificate-coverage audit",
            f"{PYTHON} safe_control_gym_quadrotor_certificate_coverage.py",
        ),
        (
            "P2 common-state security-availability frontier",
            f"{PYTHON} safe_control_gym_quadrotor_security_availability_frontier.py",
        ),
        (
            "P2 table and figure derivation",
            f"{PYTHON} generate_tdsc_frontier_artifacts.py",
        ),
        (
            "P3 cache seed 2040, fractions 00:07",
            f"{PYTHON} safe_control_gym_quadrotor_trusted_anchor_audit.py "
            "--precompute-seed 2040 --fraction-start 0 --fraction-stop 7",
        ),
        (
            "P3 cache seed 2040, fractions 07:14",
            f"{PYTHON} safe_control_gym_quadrotor_trusted_anchor_audit.py "
            "--precompute-seed 2040 --fraction-start 7 --fraction-stop 14",
        ),
        (
            "P3 cache seed 2040, fractions 14:21",
            f"{PYTHON} safe_control_gym_quadrotor_trusted_anchor_audit.py "
            "--precompute-seed 2040 --fraction-start 14 --fraction-stop 21",
        ),
        (
            "P3 cache seed 2041, fractions 00:07",
            f"{PYTHON} safe_control_gym_quadrotor_trusted_anchor_audit.py "
            "--precompute-seed 2041 --fraction-start 0 --fraction-stop 7",
        ),
        (
            "P3 cache seed 2041, fractions 07:14",
            f"{PYTHON} safe_control_gym_quadrotor_trusted_anchor_audit.py "
            "--precompute-seed 2041 --fraction-start 7 --fraction-stop 14",
        ),
        (
            "P3 cache seed 2041, fractions 14:21",
            f"{PYTHON} safe_control_gym_quadrotor_trusted_anchor_audit.py "
            "--precompute-seed 2041 --fraction-start 14 --fraction-stop 21",
        ),
        (
            "P3 cache seed 2042, fractions 00:07",
            f"{PYTHON} safe_control_gym_quadrotor_trusted_anchor_audit.py "
            "--precompute-seed 2042 --fraction-start 0 --fraction-stop 7",
        ),
        (
            "P3 cache seed 2042, fractions 07:14",
            f"{PYTHON} safe_control_gym_quadrotor_trusted_anchor_audit.py "
            "--precompute-seed 2042 --fraction-start 7 --fraction-stop 14",
        ),
        (
            "P3 cache seed 2042, fractions 14:21",
            f"{PYTHON} safe_control_gym_quadrotor_trusted_anchor_audit.py "
            "--precompute-seed 2042 --fraction-start 14 --fraction-stop 21",
        ),
        (
            "P3 trusted-anchor audit from verified caches",
            f"{PYTHON} safe_control_gym_quadrotor_trusted_anchor_audit.py",
        ),
        (
            "P3 table derivation",
            f"{PYTHON} generate_tdsc_anchor_artifacts.py",
        ),
        (
            "Core and coverage table derivation",
            f"{PYTHON} generate_tdsc_result_table.py",
        ),
        (
            "Cartpole one-step resident-kernel smoke",
            f"{PYTHON} safe_control_gym_cartpole_release_contract_smoke.py",
        ),
        (
            "Cartpole resident predictive authority smoke",
            f"{PYTHON} safe_control_gym_cartpole_predictive_simplex_smoke.py",
        ),
        (
            "Retrospective gate-aware target audit",
            f"{PYTHON} safe_control_gym_cartpole_certificate_evasion_smoke.py",
        ),
        (
            "Unclipped reward-influence geometry audit",
            f"{PYTHON} safe_control_gym_cartpole_reward_geometry_smoke.py",
        ),
        (
            "Three-seed resident-versus-release hard gate",
            f"{PYTHON} safe_control_gym_cartpole_multiseed_release_contract.py",
        ),
        (
            "Failed prospective exact-support development smoke",
            f"{PYTHON} safe_control_gym_cartpole_prospective_gate_aware_attack.py",
        ),
        (
            "Burned-seed reward-direction diagnostic",
            f"{PYTHON} safe_control_gym_cartpole_reward_direction_diagnostic.py",
        ),
        (
            "Burned-seed V2 exploratory diagnostic",
            f"{PYTHON} safe_control_gym_cartpole_gate_aware_v2_exploration.py",
        ),
        (
            "V3 prospective fixed-target development smoke",
            f"{PYTHON} safe_control_gym_cartpole_v3_fixed_target_tanh.py",
        ),
        (
            "V3 prospective fixed-target three-seed audit",
            f"{PYTHON} safe_control_gym_cartpole_v3_fixed_target_tanh.py "
            "--learner-seeds 2070,2071,2072 "
            "--evaluation-seeds 9070,9071,9072 --confirmatory "
            "--output-prefix results/cartpole_v3_fixed_target_multiseed",
        ),
        (
            "V3 successful-trajectory influence replay",
            f"{PYTHON} safe_control_gym_cartpole_trajectory_influence_audit.py",
        ),
        (
            "V3 homogenized clipped-influence audit",
            f"{PYTHON} safe_control_gym_cartpole_clipped_influence_audit.py",
        ),
        (
            "Burned-seed homogenized gate-aware post-stop diagnostic",
            f"{PYTHON} safe_control_gym_cartpole_homogenized_gate_aware_diagnostic.py",
        ),
        (
            "V3 monitor-horizon contract sweep",
            f"{PYTHON} safe_control_gym_cartpole_horizon_contract_sweep.py",
        ),
        (
            "Reward-log detector calibration before new seeds",
            f"{PYTHON} safe_control_gym_reward_log_detectability.py --calibrate",
        ),
        (
            "V4 one-shot untouched five-seed confirmation (fresh artifact only)",
            f"{PYTHON} safe_control_gym_cartpole_v4_reviewer_confirmation.py",
        ),
        (
            "V4 clean resident paired arm",
            f"{PYTHON} safe_control_gym_cartpole_v4_clean_resident_arm.py",
        ),
        (
            "V5 adversary-free clean cohort",
            f"{PYTHON} safe_control_gym_cartpole_v5_clean_cohort.py",
        ),
        (
            "V5 clean-cohort statistical analysis",
            f"{PYTHON} analyze_v5_clean_cohort.py",
        ),
        (
            "V6 detection-constrained duration stress test",
            f"{PYTHON} safe_control_gym_cartpole_v6_duration_stealth_attack.py",
        ),
        (
            "Frozen reward-log detector evaluation",
            f"{PYTHON} safe_control_gym_reward_log_detectability.py --evaluate",
        ),
        (
            "S1 sparse reward-permutation offline verification",
            f"{PYTHON} safe_control_gym_cartpole_sparse_reward_permutation.py "
            "--stage offline_check",
        ),
        (
            "S1 burned-seed 2070 smoke",
            f"{PYTHON} safe_control_gym_cartpole_sparse_reward_permutation.py "
            "--stage s1_2070_smoke",
        ),
        (
            "S2 moment-preserving burned-seed 2070 fallback",
            f"{PYTHON} safe_control_gym_cartpole_moment_preserving_reward.py "
            "--stage s2_2070_smoke",
        ),
        (
            "Finalize stealth temporal-reward work package",
            f"{PYTHON} safe_control_gym_cartpole_moment_preserving_reward.py "
            "--stage finalize_wp",
        ),
        (
            "U1 second learner family (A2C) confirmation",
            f"{PYTHON} safe_control_gym_cartpole_a2c_reward_poisoning.py "
            "--seeds 2200,2201,2202 --canary-seed 2200 "
            "--prefix results/cartpole_a2c_reward_poisoning_multiseed",
        ),
        (
            "U2 joint observation-FDI + reward-log confirmation",
            f"{PYTHON} safe_control_gym_cartpole_joint_channel_poisoning.py "
            "--seeds 2210,2211,2212 --canary-seed 2210 "
            "--prefix results/cartpole_joint_channel_poisoning_multiseed",
        ),
        (
            "U3 in-loop reward-integrity defense confirmation",
            f"{PYTHON} safe_control_gym_cartpole_inloop_defense.py "
            "--seeds 2220,2221,2222 --canary-seed 2220 "
            "--prefix results/cartpole_inloop_defense_multiseed",
        ),
        (
            "Carr instrumented-upstream reconstruction",
            "git clone https://github.com/stevencarrau/safe_RL_POMDPs.git "
            "carr_upstream && "
            "git -C carr_upstream checkout "
            "b01dbe8b40e2167bdc1d93dea7b43e96f1a835ee && "
            "git -C carr_upstream apply --check "
            "../carr_victim_experiment/upstream/carr_reward_poisoning.patch && "
            "git -C carr_upstream apply "
            "../carr_victim_experiment/upstream/carr_reward_poisoning.patch",
        ),
        ("Regression tests", "pytest -q"),
        (
            "Research-track draft PDF",
            "cd paper_latex && latexmk -pdf -interaction=nonstopmode "
            "-halt-on-error usenix_sec2027.tex",
        ),
        (
            "Manifest and checksums (run last)",
            f"{PYTHON} generate_tdsc_reproducibility_manifest.py",
        ),
    ]


def seed_rows() -> list[tuple[str, str, str]]:
    return [
        ("Primary learner seeds", "2040, 2041, 2042", "cartpole and quadrotor"),
        ("Primary evaluation seeds", "3040, 3041, 3042", "held-out physical states"),
        ("Commit certificate seeds", "7040, 7041, 7042", "learner seed + 5000"),
        ("P1 coverage-state seeds", "4050, 4051, 4052", "144 unadmitted states"),
        ("P2 candidate-state seeds", "5050, 5051, 5052", "common paired frontier"),
        ("P3 deployment-state seeds", "6050, 6051, 6052", "new paired states"),
        (
            "Release-contract evaluation seeds",
            "8040, 8041, 8042",
            "disjoint states for learner seeds 2040--2042",
        ),
        (
            "Prospective exact-support development seed",
            "2060; evaluation 9060",
            "failed stop rule; diagnostic reuse only",
        ),
        (
            "Reserved prospective confirmation seeds",
            "2061, 2062; evaluation 9061, 9062",
            "not run",
        ),
        (
            "V3 fixed-target learner seeds",
            "2070, 2071, 2072",
            "development 2070, then locked confirmation 2071--2072",
        ),
        (
            "V3 fixed-target evaluation seeds",
            "9070, 9071, 9072",
            "disjoint paired state pools",
        ),
        (
            "V4 untouched fixed-target learner seeds",
            "2100, 2101, 2102, 2103, 2104",
            "one-shot extension; detector frozen before opening",
        ),
        (
            "V4 untouched fixed-target evaluation seeds",
            "9100, 9101, 9102, 9103, 9104",
            "disjoint paired state pools",
        ),
        (
            "V5 clean-cohort learner seeds",
            "2300--2319",
            "20 new independent training runs",
        ),
        (
            "V5 clean-cohort evaluation seeds",
            "9300--9319",
            "24 clean-accepted states per training run",
        ),
        (
            "V6 duration-stress learner seeds",
            "2400--2404",
            "paired clean, constrained, and unconstrained conditions",
        ),
        (
            "V6 duration-stress evaluation seeds",
            "9400--9404",
            "durations 12, 24, and 48 batches",
        ),
        (
            "Stealth temporal-reward development reuse",
            "2070/9070 only",
            "S1 and S2 stopped for zero raw-release effect",
        ),
        (
            "Stealth temporal-reward confirmation seeds",
            "none",
            "namespace not opened after burned-seed stop",
        ),
        ("PPO B-lite development seed", "2040", "formal sweep not run"),
        ("Benign-utility development seeds", "2039; evaluation 3039", "smoke only"),
        (
            "Benign-utility reserved formal seeds",
            "2050--2052; evaluation 3050--3052",
            "not run after smoke stop",
        ),
        (
            "U1 second-family (A2C) learner seeds",
            "2200; confirmation 2201, 2202",
            "canary 2200, then locked confirmation 2201--2202",
        ),
        (
            "U2 joint-channel (obs-FDI + reward-log) seeds",
            "2210; confirmation 2211, 2212",
            "locked rho grid 0.005/0.02/0.04",
        ),
        (
            "U3 in-loop reward-defense seeds",
            "2220; confirmation 2221, 2222",
            "frozen known-sign in-loop batch gate",
        ),
    ]


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as output:
        writer = csv.DictWriter(
            output, fieldnames=list(rows[0]), lineterminator="\n"
        )
        writer.writeheader()
        writer.writerows(rows)


def write_markdown(
    path: Path,
    environments: list[dict[str, str]],
    checksum_rows: list[dict[str, object]],
) -> None:
    lines = [
        "# USENIX Security 2027 research-track reproducibility manifest",
        "",
        f"> Locked {LOCK_DATE}. Run all commands from the project root. "
        "The resident-versus-release hard gate and its prerequisite smokes are "
        "included; the benign-utility development smoke is retained as "
        "negative evidence.",
        "",
        "## Environment",
        "",
        "| Component | Version | Source |",
        "|---|---|---|",
    ]
    lines.extend(
        f"| {row['component']} | `{row['version']}` | `{row['source']}` |"
        for row in environments
    )
    lines.extend(
        [
            "",
            "The online latency values in the paper are single-process host "
            "wall-clock measurements, not worst-case execution-time guarantees.",
            "",
            "## Seed registry",
            "",
            "| Purpose | Seeds | Separation/status |",
            "|---|---|---|",
        ]
    )
    lines.extend(
        f"| {purpose} | `{seeds}` | {status} |"
        for purpose, seeds, status in seed_rows()
    )
    lines.extend(["", "## Exact commands", ""])
    for title, command in commands():
        lines.extend([f"### {title}", "", "```sh", command, "```", ""])
    lines.extend(
        [
            "## Integrity inventory",
            "",
            f"`results/tdsc_artifact_checksums.csv` contains SHA-256 digests "
            f"for {len(checksum_rows)} locked source, raw-result, generated, "
            "upstream-model, figure, and submission files. "
            "`results/tdsc_environment_versions.csv` is the machine-readable "
            "environment table.",
            "",
            "The invalid pre-clip benign calibration is intentionally retained "
            "as an audit narrative in `benign_utility_protocol.md`; it is not "
            "included as confirmatory result data.",
        ]
    )
    path.write_text("\n".join(lines) + "\n")


def main() -> None:
    inventory = artifact_inventory()
    checksum_rows: list[dict[str, object]] = []
    for role, path in sorted(inventory, key=lambda item: str(item[1])):
        checksum_rows.append(
            {
                "role": role,
                "path": str(path.relative_to(ROOT)),
                "bytes": path.stat().st_size,
                "sha256": sha256(path),
            }
        )
    environment = environment_rows()
    checksum_path = RESULTS / "tdsc_artifact_checksums.csv"
    environment_path = RESULTS / "tdsc_environment_versions.csv"
    manifest_path = ROOT / "usenix_reproducibility_manifest.md"
    write_csv(checksum_path, checksum_rows)
    write_csv(environment_path, environment)
    write_markdown(manifest_path, environment, checksum_rows)
    for legacy_name in (
        "tdsc_reproducibility_manifest.md",
        "ndss_reproducibility_manifest.md",
    ):
        legacy_path = ROOT / legacy_name
        legacy_path.write_text(
            "# Superseded reproducibility manifest\n\n"
            "The active research-track manifest is "
            "`usenix_reproducibility_manifest.md`.\n"
        )
        print(f"wrote compatibility pointer {legacy_path}")
    print(f"wrote {manifest_path}")
    print(f"wrote {environment_path}")
    print(f"wrote {checksum_path} ({len(checksum_rows)} files)")


if __name__ == "__main__":
    main()
