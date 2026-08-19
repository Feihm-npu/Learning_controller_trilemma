#!/usr/bin/env python3
"""Paper-oriented Safe-Control-Gym sweep and figure generation.

This script turns the single-run Safe-Control-Gym LifecycleGate experiment into
paper evidence:

* multi-rho / multi-seed CasADi robust-kernel sweep,
* small official CBF sampled-kernel reference sweep,
* freeze-frontier sweep, and
* a dedicated Safe-Control-Gym figure.

The default profile is intentionally quick for local verification. Use
``--profile paper`` for a larger table once the parameters are frozen.
"""

from __future__ import annotations

import argparse
import csv
import os
from dataclasses import asdict
from pathlib import Path
from typing import Any, Iterable

import numpy as np

from continuous_adaptive_attacker import AttackWeights
from safe_control_gym_plausible_set_lifecycle_gate import GateRunSummary, run_mechanism


ROOT = Path(__file__).resolve().parent
RESULTS_DIR = ROOT / "results"
FIGURES_DIR = ROOT / "paper_latex" / "figures"

PRIMARY_MECHANISMS = [
    "attacked_lqr_update_ungated",
    "plausible_action_filter_update_ungated",
    "always_freeze",
    "lifecycle_gate_project",
]
FRONTIER_MECHANISMS = [
    "plausible_action_filter_update_ungated",
    "always_freeze",
    "lifecycle_gate_project",
]

METRIC_KEYS = [
    "constraint_violation_step_rate",
    "stale_certified_policy_rate",
    "uncertified_learning_rate",
    "learn_update_rate",
    "intervention_rate",
    "empty_kernel_rate",
    "mean_kernel_width",
    "mean_reward",
]


def configure_matplotlib() -> None:
    cache_dir = Path("/tmp/matplotlib-lifecycle-gate")
    cache_dir.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("MPLCONFIGDIR", str(cache_dir))


configure_matplotlib()

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt


def profile_defaults(profile: str) -> dict[str, Any]:
    if profile == "paper":
        return {
            "seeds": [2026, 2027, 2028, 2029, 2030],
            "rhos": [0.01, 0.02, 0.03, 0.04, 0.05],
            "cbf_rhos": [0.01, 0.015],
            "frontier_rhos": [0.01, 0.02, 0.03, 0.04, 0.05, 0.06, 0.08],
            "n_steps": 10,
            "population": 12,
            "iterations": 3,
            "action_grid_size": 61,
        }
    return {
        "seeds": [2026, 2027],
        "rhos": [0.02, 0.03],
        "cbf_rhos": [0.015],
        "frontier_rhos": [0.02, 0.04, 0.06],
        "n_steps": 4,
        "population": 8,
        "iterations": 2,
        "action_grid_size": 41,
    }


def parse_csv_floats(values: str | None, fallback: list[float]) -> list[float]:
    if not values:
        return fallback
    return [float(part.strip()) for part in values.split(",") if part.strip()]


def parse_csv_ints(values: str | None, fallback: list[int]) -> list[int]:
    if not values:
        return fallback
    return [int(part.strip()) for part in values.split(",") if part.strip()]


def run_rows(
    *,
    label: str,
    mechanisms: list[str],
    seeds: list[int],
    rhos: list[float],
    kernel_backend: str,
    attack_weights: AttackWeights,
    n_steps: int,
    population: int,
    iterations: int,
    action_grid_size: int,
    gain_step: float,
    bias_step: float,
    future_span: float,
    guard_margin: float,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    total = len(seeds) * len(rhos) * len(mechanisms)
    done = 0
    for seed in seeds:
        for rho in rhos:
            for mechanism in mechanisms:
                done += 1
                print(f"[{label}] {done}/{total}: seed={seed} rho={rho:.3f} mechanism={mechanism}")
                summary = run_mechanism(
                    mechanism,
                    n_steps=n_steps,
                    rho=rho,
                    seed=seed,
                    population=population,
                    iterations=iterations,
                    action_grid_size=action_grid_size,
                    future_span=future_span,
                    guard_margin=guard_margin,
                    gain_step=gain_step,
                    bias_step=bias_step,
                    attack_weights=attack_weights,
                    kernel_backend=kernel_backend,
                    attack_kernel_backend="euler",
                    cbf_action_tolerance=1e-5,
                )
                row = asdict(summary)
                row["sweep_label"] = label
                row["seed"] = seed
                rows.append(row)
    return rows


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(rows[0].keys())
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def group_key(row: dict[str, Any]) -> tuple[str, float]:
    return row["mechanism"], float(row["budget"])


def aggregate_rows(rows: Iterable[dict[str, Any]], label: str) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, float], list[dict[str, Any]]] = {}
    for row in rows:
        grouped.setdefault(group_key(row), []).append(row)

    aggregated: list[dict[str, Any]] = []
    for (mechanism, rho), group in sorted(grouped.items(), key=lambda item: (item[0][1], item[0][0])):
        out: dict[str, Any] = {
            "sweep_label": label,
            "mechanism": mechanism,
            "budget": rho,
            "kernel_backend": group[0]["kernel_backend"],
            "attack_kernel_backend": group[0]["attack_kernel_backend"],
            "seeds": len({row["seed"] for row in group}),
            "steps": group[0]["steps"],
            "action_grid_size": group[0]["action_grid_size"],
        }
        for key in METRIC_KEYS:
            values = np.asarray([float(row[key]) for row in group], dtype=float)
            out[f"{key}_mean"] = float(values.mean())
            out[f"{key}_std"] = float(values.std(ddof=0))
        aggregated.append(out)
    return aggregated


def rows_for(rows: list[dict[str, Any]], mechanism: str) -> list[dict[str, Any]]:
    return [row for row in rows if row["mechanism"] == mechanism]


def metric_series(rows: list[dict[str, Any]], key: str) -> tuple[list[float], list[float], list[float]]:
    ordered = sorted(rows, key=lambda row: float(row["budget"]))
    xs = [float(row["budget"]) for row in ordered]
    means = [float(row[f"{key}_mean"]) for row in ordered]
    stds = [float(row[f"{key}_std"]) for row in ordered]
    return xs, means, stds


def plot_with_band(ax: Any, rows: list[dict[str, Any]], key: str, *, color: str, marker: str, label: str) -> None:
    xs, means, stds = metric_series(rows, key)
    ax.plot(xs, means, color=color, marker=marker, linewidth=1.4, label=label)
    lower = np.maximum(np.asarray(means) - np.asarray(stds), 0.0)
    upper = np.minimum(np.asarray(means) + np.asarray(stds), 1.0 if key.endswith("_rate") else np.inf)
    ax.fill_between(xs, lower, upper, color=color, alpha=0.12, linewidth=0)


def write_safe_control_gym_figure(path: Path, primary: list[dict[str, Any]], frontier: list[dict[str, Any]], cbf: list[dict[str, Any]]) -> None:
    fig, axes = plt.subplots(2, 2, figsize=(7.1, 4.8), sharex=False)
    ax_failure, ax_updates, ax_frontier, ax_cbf = axes.flatten()

    action_filter = rows_for(primary, "plausible_action_filter_update_ungated")
    gated = rows_for(primary, "lifecycle_gate_project")
    ungated = rows_for(primary, "attacked_lqr_update_ungated")
    freeze = rows_for(primary, "always_freeze")

    plot_with_band(ax_failure, ungated, "constraint_violation_step_rate", color="#C0392B", marker="s", label="ungated violation")
    plot_with_band(ax_failure, action_filter, "stale_certified_policy_rate", color="#2E86AB", marker="^", label="action-filter stale")
    plot_with_band(ax_failure, gated, "stale_certified_policy_rate", color="#218C5A", marker="o", label="LifecycleGate stale")
    ax_failure.set_title("Lifecycle failure under CasADi kernel", fontsize=9)
    ax_failure.set_ylabel("Rate", fontsize=8)
    ax_failure.set_ylim(-0.03, 1.03)

    plot_with_band(ax_updates, action_filter, "uncertified_learning_rate", color="#2E86AB", marker="^", label="action-filter uncertified")
    plot_with_band(ax_updates, gated, "learn_update_rate", color="#218C5A", marker="o", label="LifecycleGate updates")
    plot_with_band(ax_updates, freeze, "learn_update_rate", color="#555555", marker="x", label="always-freeze updates")
    ax_updates.set_title("Update availability and certification", fontsize=9)
    ax_updates.set_ylabel("Rate", fontsize=8)
    ax_updates.set_ylim(-0.03, 1.03)

    frontier_action = rows_for(frontier, "plausible_action_filter_update_ungated")
    frontier_gated = rows_for(frontier, "lifecycle_gate_project")
    plot_with_band(ax_frontier, frontier_action, "empty_kernel_rate", color="#2E86AB", marker="^", label="action-filter empty")
    plot_with_band(ax_frontier, frontier_gated, "empty_kernel_rate", color="#218C5A", marker="o", label="LifecycleGate empty")
    plot_with_band(ax_frontier, frontier_gated, "learn_update_rate", color="#555555", marker="x", label="LifecycleGate updates")
    ax_frontier.set_title("Freeze frontier", fontsize=9)
    ax_frontier.set_xlabel("Ambiguity radius", fontsize=8)
    ax_frontier.set_ylabel("Rate", fontsize=8)
    ax_frontier.set_ylim(-0.03, 1.03)

    if cbf:
        cbf_action = rows_for(cbf, "plausible_action_filter_update_ungated")
        cbf_gated = rows_for(cbf, "lifecycle_gate_project")
        plot_with_band(ax_cbf, cbf_action, "stale_certified_policy_rate", color="#2E86AB", marker="^", label="CBF action-filter stale")
        plot_with_band(ax_cbf, cbf_gated, "stale_certified_policy_rate", color="#218C5A", marker="o", label="CBF LifecycleGate stale")
        plot_with_band(ax_cbf, cbf_gated, "learn_update_rate", color="#555555", marker="x", label="CBF LifecycleGate updates")
    ax_cbf.set_title("Official CBF sampled reference", fontsize=9)
    ax_cbf.set_xlabel("Ambiguity radius", fontsize=8)
    ax_cbf.set_ylabel("Rate", fontsize=8)
    ax_cbf.set_ylim(-0.03, 1.03)

    for ax in axes.flatten():
        ax.grid(True, color="#D8D8D8", linewidth=0.5, alpha=0.8)
        ax.tick_params(axis="both", labelsize=7)
        ax.set_xlabel("Ambiguity radius", fontsize=8)

    handles: list[Any] = []
    labels: list[str] = []
    for ax in axes.flatten():
        h, l = ax.get_legend_handles_labels()
        for handle, label in zip(h, l):
            if label not in labels:
                handles.append(handle)
                labels.append(label)
    fig.legend(handles, labels, loc="upper center", ncol=3, fontsize=6.5, frameon=False, bbox_to_anchor=(0.5, 0.995))
    fig.tight_layout(rect=(0.02, 0.02, 0.98, 0.90), h_pad=1.0, w_pad=0.85)
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path)
    plt.close(fig)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run paper-oriented Safe-Control-Gym LifecycleGate sweeps.")
    parser.add_argument("--profile", choices=["quick", "paper"], default="quick")
    parser.add_argument("--seeds", default=None, help="Comma-separated seed override.")
    parser.add_argument("--rhos", default=None, help="Comma-separated primary rho override.")
    parser.add_argument("--cbf-rhos", default=None, help="Comma-separated CBF rho override.")
    parser.add_argument("--frontier-rhos", default=None, help="Comma-separated freeze-frontier rho override.")
    parser.add_argument("--out-prefix", default="safe_control_gym_paper")
    parser.add_argument("--n-steps", type=int, default=None)
    parser.add_argument("--population", type=int, default=None)
    parser.add_argument("--iterations", type=int, default=None)
    parser.add_argument("--action-grid-size", type=int, default=None)
    parser.add_argument("--skip-cbf", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    defaults = profile_defaults(args.profile)
    seeds = parse_csv_ints(args.seeds, defaults["seeds"])
    rhos = parse_csv_floats(args.rhos, defaults["rhos"])
    cbf_rhos = parse_csv_floats(args.cbf_rhos, defaults["cbf_rhos"])
    frontier_rhos = parse_csv_floats(args.frontier_rhos, defaults["frontier_rhos"])
    n_steps = args.n_steps if args.n_steps is not None else defaults["n_steps"]
    population = args.population if args.population is not None else defaults["population"]
    iterations = args.iterations if args.iterations is not None else defaults["iterations"]
    action_grid_size = args.action_grid_size if args.action_grid_size is not None else defaults["action_grid_size"]

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)

    stale_weights = AttackWeights(stale=1.4, unsafe=1.0, freeze=0.0, stealth=0.25, magnitude=0.02)
    freeze_weights = AttackWeights(stale=0.2, unsafe=0.2, freeze=2.0, stealth=0.25, magnitude=0.02)

    primary = run_rows(
        label="primary_casadi",
        mechanisms=PRIMARY_MECHANISMS,
        seeds=seeds,
        rhos=rhos,
        kernel_backend="casadi",
        attack_weights=stale_weights,
        n_steps=n_steps,
        population=population,
        iterations=iterations,
        action_grid_size=action_grid_size,
        gain_step=3.0,
        bias_step=0.7,
        future_span=0.03,
        guard_margin=0.0,
    )
    frontier = run_rows(
        label="freeze_frontier_casadi",
        mechanisms=FRONTIER_MECHANISMS,
        seeds=seeds,
        rhos=frontier_rhos,
        kernel_backend="casadi",
        attack_weights=freeze_weights,
        n_steps=n_steps,
        population=population,
        iterations=iterations,
        action_grid_size=action_grid_size,
        gain_step=3.0,
        bias_step=0.7,
        future_span=0.03,
        guard_margin=0.0,
    )
    cbf: list[dict[str, Any]] = []
    if not args.skip_cbf:
        cbf = run_rows(
            label="cbf_sampled_reference",
            mechanisms=PRIMARY_MECHANISMS,
            seeds=seeds,
            rhos=cbf_rhos,
            kernel_backend="cbf_sampled",
            attack_weights=stale_weights,
            n_steps=n_steps,
            population=population,
            iterations=iterations,
            action_grid_size=action_grid_size,
            gain_step=3.0,
            bias_step=0.7,
            future_span=0.03,
            guard_margin=0.0,
        )

    raw_rows = primary + frontier + cbf
    primary_agg = aggregate_rows(primary, "primary_casadi")
    frontier_agg = aggregate_rows(frontier, "freeze_frontier_casadi")
    cbf_agg = aggregate_rows(cbf, "cbf_sampled_reference") if cbf else []
    aggregate = primary_agg + frontier_agg + cbf_agg

    raw_path = RESULTS_DIR / f"{args.out_prefix}_raw.csv"
    agg_path = RESULTS_DIR / f"{args.out_prefix}_aggregate.csv"
    figure_path = FIGURES_DIR / f"{args.out_prefix}_summary.pdf"
    write_csv(raw_path, raw_rows)
    write_csv(agg_path, aggregate)
    write_safe_control_gym_figure(figure_path, primary_agg, frontier_agg, cbf_agg)

    print(f"wrote {raw_path}")
    print(f"wrote {agg_path}")
    print(f"wrote {figure_path}")


if __name__ == "__main__":
    main()
