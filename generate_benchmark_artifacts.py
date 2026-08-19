#!/usr/bin/env python3
"""Generate CSV summaries and paper figures for lifecycle-gate benchmarks."""

from __future__ import annotations

import csv
import os
from dataclasses import asdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent
RESULTS_DIR = ROOT / "results"
FIGURES_DIR = ROOT / "paper_latex" / "figures"


def configure_matplotlib() -> None:
    cache_dir = Path("/tmp/matplotlib-lifecycle-gate")
    cache_dir.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("MPLCONFIGDIR", str(cache_dir))


configure_matplotlib()

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

import adaptive_attack_benchmark as bench_adaptive
import lifecycle_gate_benchmark as bench_1d
import matrix_parameter_gate_benchmark as bench_matrix_parameter
import nonlinear_tank_lifecycle_benchmark as bench_nonlinear
import parameter_update_gate_benchmark as bench_parameter
import two_tank_lifecycle_benchmark as bench_tank


BenchmarkRow = dict[str, Any]


def interval_parts(interval: tuple[float, float] | None) -> tuple[str, str, float, str]:
    if interval is None:
        return "", "", 0.0, "empty"
    low, high = interval
    if abs(high - low) < 1e-9:
        text = f"{{{low:.3f}}}"
    else:
        text = f"[{low:.3f},{high:.3f}]"
    return f"{low:.6f}", f"{high:.6f}", max(0.0, high - low), text


def normalize_summary(benchmark: str, steps: int, summary: Any) -> BenchmarkRow:
    data = asdict(summary)
    stale_steps = data.get("stale_policy_steps", data.get("stale_certified_policy_steps", 0))
    kernel_low, kernel_high, kernel_width, kernel_text = interval_parts(data["kernel"])
    plotted_width = data.get("min_kernel_width", kernel_width)
    final_theta = data["final_theta"]
    if isinstance(final_theta, (tuple, list)):
        final_theta_text = "(" + ",".join(f"{float(value):.6f}" for value in final_theta) + ")"
    else:
        final_theta_text = f"{float(final_theta):.6f}"
    row: BenchmarkRow = {
        "benchmark": benchmark,
        "rho": f"{data['rho']:.6f}",
        "mechanism": data["mechanism"],
        "kernel": kernel_text,
        "kernel_low": kernel_low,
        "kernel_high": kernel_high,
        "kernel_width": f"{plotted_width:.6f}",
        "current_kernel_width": f"{kernel_width:.6f}",
        "cert_accepts": data["cert_accepts"],
        "cert_rejects": data["cert_rejects"],
        "learn_updates": data["learn_updates"],
        "learn_update_rate": f"{data['learn_updates'] / steps:.6f}",
        "uncertified_learning": data["uncertified_learning_steps"],
        "uncertified_learning_rate": f"{data['uncertified_learning_steps'] / steps:.6f}",
        "unsafe_certified": data["unsafe_certified_steps"],
        "unsafe_certified_rate": f"{data['unsafe_certified_steps'] / steps:.6f}",
        "stale_certified_policy": stale_steps,
        "stale_certified_policy_rate": f"{stale_steps / steps:.6f}",
        "interventions": data["interventions"],
        "intervention_rate": f"{data['interventions'] / steps:.6f}",
        "final_theta": final_theta_text,
        "max_violation": f"{float(data.get('max_violation', 0.0)):.6f}",
    }
    return row


def run_1d() -> list[BenchmarkRow]:
    rhos = [0.60, 0.80, 1.0 / bench_1d.LAMBDA, 0.90, 1.00]
    rows: list[BenchmarkRow] = []
    for rho in rhos:
        for name, mechanism in bench_1d.MECHANISMS.items():
            summary = bench_1d.run_mechanism(name, mechanism, rho)
            rows.append(normalize_summary("one_dimensional", bench_1d.STEPS, summary))
    return rows


def run_tank() -> list[BenchmarkRow]:
    frontier = 1.0 / (abs(bench_tank.A[0][0]) + abs(bench_tank.A[0][1]))
    rhos = [0.70, 0.80, 0.85, frontier, 0.92]
    rows: list[BenchmarkRow] = []
    for rho in rhos:
        for name, mechanism in bench_tank.MECHANISMS.items():
            summary = bench_tank.run_mechanism(name, mechanism, rho)
            rows.append(normalize_summary("two_tank_linearized", bench_tank.STEPS, summary))
    return rows


def run_nonlinear_tank() -> list[BenchmarkRow]:
    rhos = [0.10, 0.20, 0.30, 0.40, 0.45]
    rows: list[BenchmarkRow] = []
    for rho in rhos:
        for name, mechanism in bench_nonlinear.MECHANISMS.items():
            summary = bench_nonlinear.run_mechanism(name, mechanism, rho)
            rows.append(normalize_summary("two_tank_nonlinear", bench_nonlinear.STEPS, summary))
    return rows


def run_parameter_gate() -> list[BenchmarkRow]:
    rhos = [0.10, 0.30, 0.50, 0.70, 0.80, 0.85]
    rows: list[BenchmarkRow] = []
    for rho in rhos:
        for name, mechanism in bench_parameter.MECHANISMS.items():
            summary = bench_parameter.run_mechanism(name, mechanism, rho)
            rows.append(normalize_summary("parameter_linear_policy", bench_parameter.STEPS, summary))
    return rows


def run_matrix_parameter_gate() -> list[BenchmarkRow]:
    rhos = [0.05, 0.20, 0.35, 0.45, 0.50]
    rows: list[BenchmarkRow] = []
    for rho in rhos:
        for name, mechanism in bench_matrix_parameter.MECHANISMS.items():
            summary = bench_matrix_parameter.run_mechanism(name, mechanism, rho)
            rows.append(normalize_summary("parameter_matrix_policy", bench_matrix_parameter.STEPS, summary))
    return rows


def normalize_adaptive_summary(summary: bench_adaptive.AdaptiveSummary) -> BenchmarkRow:
    row = normalize_summary(
        f"adaptive_{summary.attack_goal}",
        bench_adaptive.STEPS,
        summary,
    )
    row["attack_goal"] = summary.attack_goal
    row["rho_budget"] = f"{summary.rho_budget:.6f}"
    row["selected_rho"] = f"{summary.selected_rho:.6f}"
    return row


def run_adaptive_attacks() -> list[BenchmarkRow]:
    rho_budgets = {
        "stale": [0.10, 0.30, 0.50, 0.70, 0.80],
        "unsafe": [0.10, 0.30, 0.50, 0.70, 0.80],
        "freeze": [0.70, 0.80, 0.84, 0.85, 0.90],
    }
    rows: list[BenchmarkRow] = []
    for goal in bench_adaptive.ATTACK_GOALS:
        for rho_budget in rho_budgets[goal]:
            for name, mechanism in bench_adaptive.MECHANISMS.items():
                summary = bench_adaptive.run_mechanism(name, mechanism, goal, rho_budget)
                rows.append(normalize_adaptive_summary(summary))
    return rows


def write_csv(path: Path, rows: list[BenchmarkRow]) -> None:
    if not rows:
        return
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def by_mechanism(rows: list[BenchmarkRow], mechanism: str) -> list[BenchmarkRow]:
    return [row for row in rows if row["mechanism"] == mechanism]


def x_values(rows: list[BenchmarkRow]) -> list[float]:
    return [float(row["rho"]) for row in rows]


def y_values(rows: list[BenchmarkRow], key: str) -> list[float]:
    return [float(row[key]) for row in rows]


def plot_benchmark_column(axes: list[Any], rows: list[BenchmarkRow], title: str) -> None:
    kernel_rows = by_mechanism(rows, "lifecycle_gate_project")
    xs = x_values(kernel_rows)

    axes[0].plot(xs, y_values(kernel_rows, "kernel_width"), color="#111111", marker="o", linewidth=1.6)
    axes[0].set_title(title, fontsize=9, pad=4)
    axes[0].set_ylabel("Kernel width", fontsize=8)

    nominal = by_mechanism(rows, "nominal_action_filter")
    robust = by_mechanism(rows, "robust_action_filter_update_ungated")
    gated = by_mechanism(rows, "lifecycle_gate_project")
    axes[1].plot(xs, y_values(nominal, "unsafe_certified_rate"), color="#C0392B", marker="s", linewidth=1.4, label="nominal unsafe")
    axes[1].plot(xs, y_values(robust, "stale_certified_policy_rate"), color="#2E86AB", marker="^", linewidth=1.4, label="action-filter stale")
    axes[1].plot(xs, y_values(gated, "stale_certified_policy_rate"), color="#218C5A", marker="o", linewidth=1.4, label="LifecycleGate stale")
    axes[1].set_ylabel("Failure rate", fontsize=8)

    always = by_mechanism(rows, "always_freeze")
    axes[2].plot(xs, y_values(robust, "learn_update_rate"), color="#2E86AB", marker="^", linewidth=1.4, label="action filter")
    axes[2].plot(xs, y_values(gated, "learn_update_rate"), color="#218C5A", marker="o", linewidth=1.4, label="LifecycleGate")
    axes[2].plot(xs, y_values(always, "learn_update_rate"), color="#555555", marker="x", linewidth=1.2, label="always freeze")
    axes[2].set_ylabel("Update rate", fontsize=8)
    axes[2].set_xlabel("Ambiguity radius", fontsize=8)

    for ax in axes:
        ax.grid(True, color="#D8D8D8", linewidth=0.5, alpha=0.8)
        ax.tick_params(axis="both", labelsize=7)
        ax.set_ylim(bottom=-0.03)
    axes[1].set_ylim(-0.03, 1.03)
    axes[2].set_ylim(-0.03, 1.03)


def write_summary_figure(
    path: Path,
    rows_1d: list[BenchmarkRow],
    rows_tank: list[BenchmarkRow],
    rows_nonlinear: list[BenchmarkRow],
) -> None:
    fig, axes = plt.subplots(3, 3, figsize=(7.1, 4.8), sharex="col")
    plot_benchmark_column([axes[0][0], axes[1][0], axes[2][0]], rows_1d, "1D lifecycle benchmark")
    plot_benchmark_column([axes[0][1], axes[1][1], axes[2][1]], rows_tank, "Linear tank benchmark")
    plot_benchmark_column([axes[0][2], axes[1][2], axes[2][2]], rows_nonlinear, "Nonlinear tank benchmark")

    handles, labels = axes[1][0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="upper center", ncol=3, fontsize=7, frameon=False, bbox_to_anchor=(0.5, 0.995))
    handles, labels = axes[2][0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="lower center", ncol=3, fontsize=7, frameon=False, bbox_to_anchor=(0.5, 0.005))

    fig.tight_layout(rect=(0.02, 0.06, 0.98, 0.94), h_pad=0.85, w_pad=0.75)
    fig.savefig(path)
    plt.close(fig)


def write_parameter_figure(
    path: Path,
    rows: list[BenchmarkRow],
    title: str = "Parameter-level linear-policy gate",
) -> None:
    fig, axes = plt.subplots(3, 1, figsize=(3.55, 4.45), sharex=True)

    gated = by_mechanism(rows, "lifecycle_gate_project")
    action_filter = by_mechanism(rows, "robust_action_filter_update_ungated")
    always = by_mechanism(rows, "always_freeze")
    ungated = by_mechanism(rows, "ungated")
    xs = x_values(gated)

    axes[0].plot(xs, y_values(gated, "kernel_width"), color="#111111", marker="o", linewidth=1.5)
    axes[0].set_ylabel("Min grid\nkernel width", fontsize=8)
    axes[0].set_title(title, fontsize=9, pad=4)

    axes[1].plot(xs, y_values(ungated, "unsafe_certified_rate"), color="#C0392B", marker="s", linewidth=1.3, label="ungated unsafe")
    axes[1].plot(xs, y_values(action_filter, "stale_certified_policy_rate"), color="#2E86AB", marker="^", linewidth=1.3, label="action-filter stale")
    axes[1].plot(xs, y_values(gated, "stale_certified_policy_rate"), color="#218C5A", marker="o", linewidth=1.3, label="parameter-gate stale")
    axes[1].set_ylabel("Failure rate", fontsize=8)

    axes[2].plot(xs, y_values(action_filter, "learn_update_rate"), color="#2E86AB", marker="^", linewidth=1.3, label="action filter")
    axes[2].plot(xs, y_values(gated, "learn_update_rate"), color="#218C5A", marker="o", linewidth=1.3, label="parameter gate")
    axes[2].plot(xs, y_values(always, "learn_update_rate"), color="#555555", marker="x", linewidth=1.2, label="always freeze")
    axes[2].set_ylabel("Update rate", fontsize=8)
    axes[2].set_xlabel("Ambiguity radius", fontsize=8)

    for ax in axes:
        ax.grid(True, color="#D8D8D8", linewidth=0.5, alpha=0.8)
        ax.tick_params(axis="both", labelsize=7)
        ax.set_ylim(bottom=-0.03)
    axes[1].set_ylim(-0.03, 1.03)
    axes[2].set_ylim(-0.03, 1.03)

    axes[1].legend(loc="upper left", fontsize=6.2, frameon=False)
    axes[2].legend(loc="upper right", fontsize=6.2, frameon=False)

    fig.tight_layout(rect=(0.02, 0.02, 0.98, 0.98), h_pad=0.75)
    fig.savefig(path)
    plt.close(fig)


def row_failure_rate(row: BenchmarkRow) -> float:
    return max(
        float(row["unsafe_certified_rate"]),
        float(row["stale_certified_policy_rate"]),
        float(row["uncertified_learning_rate"]),
    )


def write_adaptive_figure(path: Path, rows: list[BenchmarkRow]) -> None:
    fig, axes = plt.subplots(3, 1, figsize=(3.55, 5.0), sharex=False)
    goals = ["stale", "unsafe", "freeze"]
    titles = {
        "stale": "Adaptive stale-policy objective",
        "unsafe": "Adaptive unsafe-action objective",
        "freeze": "Adaptive forced-freeze objective",
    }

    for ax, goal in zip(axes, goals):
        goal_rows = [row for row in rows if row["attack_goal"] == goal]
        ungated = by_mechanism(goal_rows, "ungated")
        action_filter = by_mechanism(goal_rows, "robust_action_filter_update_ungated")
        gated = by_mechanism(goal_rows, "lifecycle_gate_project")
        xs = [float(row["rho_budget"]) for row in gated]
        ax.plot(xs, [row_failure_rate(row) for row in ungated], color="#C0392B", marker="s", linewidth=1.25, label="ungated failure")
        ax.plot(xs, [row_failure_rate(row) for row in action_filter], color="#2E86AB", marker="^", linewidth=1.25, label="action-filter failure")
        ax.plot(xs, [row_failure_rate(row) for row in gated], color="#218C5A", marker="o", linewidth=1.25, label="LifecycleGate failure")
        ax.plot(xs, y_values(gated, "learn_update_rate"), color="#555555", marker="x", linewidth=1.05, label="LifecycleGate updates")
        ax.set_title(titles[goal], fontsize=8.5, pad=3)
        ax.set_ylabel("Rate", fontsize=8)
        ax.grid(True, color="#D8D8D8", linewidth=0.5, alpha=0.8)
        ax.tick_params(axis="both", labelsize=7)
        ax.set_ylim(-0.03, 1.03)
        ax.set_xlabel("Attack budget", fontsize=8)

    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="upper center", ncol=2, fontsize=6.5, frameon=False, bbox_to_anchor=(0.5, 0.995))
    fig.tight_layout(rect=(0.02, 0.02, 0.98, 0.93), h_pad=0.8)
    fig.savefig(path)
    plt.close(fig)


def main() -> None:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)

    rows_1d = run_1d()
    rows_tank = run_tank()
    rows_nonlinear = run_nonlinear_tank()
    rows_parameter = run_parameter_gate()
    rows_matrix_parameter = run_matrix_parameter_gate()
    rows_adaptive = run_adaptive_attacks()
    rows_all = rows_1d + rows_tank + rows_nonlinear + rows_parameter + rows_matrix_parameter

    write_csv(RESULTS_DIR / "lifecycle_gate_1d.csv", rows_1d)
    write_csv(RESULTS_DIR / "lifecycle_gate_two_tank.csv", rows_tank)
    write_csv(RESULTS_DIR / "lifecycle_gate_nonlinear_tank.csv", rows_nonlinear)
    write_csv(RESULTS_DIR / "parameter_update_gate.csv", rows_parameter)
    write_csv(RESULTS_DIR / "matrix_parameter_update_gate.csv", rows_matrix_parameter)
    write_csv(RESULTS_DIR / "adaptive_attack_gate.csv", rows_adaptive)
    write_csv(RESULTS_DIR / "lifecycle_gate_all.csv", rows_all)
    write_summary_figure(FIGURES_DIR / "lifecycle_gate_summary.pdf", rows_1d, rows_tank, rows_nonlinear)
    write_parameter_figure(FIGURES_DIR / "parameter_gate_summary.pdf", rows_parameter)
    write_parameter_figure(
        FIGURES_DIR / "matrix_parameter_gate_summary.pdf",
        rows_matrix_parameter,
        "2D linear-policy parameter gate",
    )
    write_adaptive_figure(FIGURES_DIR / "adaptive_attack_summary.pdf", rows_adaptive)

    print(f"wrote {RESULTS_DIR / 'lifecycle_gate_1d.csv'}")
    print(f"wrote {RESULTS_DIR / 'lifecycle_gate_two_tank.csv'}")
    print(f"wrote {RESULTS_DIR / 'lifecycle_gate_nonlinear_tank.csv'}")
    print(f"wrote {RESULTS_DIR / 'parameter_update_gate.csv'}")
    print(f"wrote {RESULTS_DIR / 'matrix_parameter_update_gate.csv'}")
    print(f"wrote {RESULTS_DIR / 'adaptive_attack_gate.csv'}")
    print(f"wrote {RESULTS_DIR / 'lifecycle_gate_all.csv'}")
    print(f"wrote {FIGURES_DIR / 'lifecycle_gate_summary.pdf'}")
    print(f"wrote {FIGURES_DIR / 'parameter_gate_summary.pdf'}")
    print(f"wrote {FIGURES_DIR / 'matrix_parameter_gate_summary.pdf'}")
    print(f"wrote {FIGURES_DIR / 'adaptive_attack_summary.pdf'}")


if __name__ == "__main__":
    main()
