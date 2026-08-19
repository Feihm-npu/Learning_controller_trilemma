#!/usr/bin/env python3
"""Minimal 1D certificate-gated learning demo.

This script prints the robust safe-action kernel for the toy system
    x_{t+1} = LAMBDA * x_t + u_t, |u_t| <= U_MAX, S=[-1, 1]
under an FDI-induced ambiguity set X(h)=[-rho, rho].
"""

LAMBDA = 1.2
U_MAX = 0.2


def safe_kernel(rho):
    """Return the common one-step safe action interval for X=[-rho, rho]."""
    return safe_kernel_for_interval(-rho, rho)


def safe_kernel_for_interval(low, high):
    """Return the common safe action interval for X=[low, high]."""
    lower = max(-U_MAX, -1.0 - LAMBDA * low)
    upper = min(U_MAX, 1.0 - LAMBDA * high)
    if lower <= upper:
        return lower, upper
    return None


def safe_interval_for_state(x):
    """Return one-step safe action interval for a single true state."""
    lower = max(-U_MAX, -1.0 - LAMBDA * x)
    upper = min(U_MAX, 1.0 - LAMBDA * x)
    if lower <= upper:
        return lower, upper
    return None


def next_state(x, u):
    return LAMBDA * x + u


def format_interval(interval):
    if interval is None:
        return "empty"
    return f"[{interval[0]:.3f}, {interval[1]:.3f}]"


def nominal_unsafe(rho):
    """Nominal learner sees y=0 and outputs u=0."""
    return abs(next_state(rho, 0.0)) > 1.0 or abs(next_state(-rho, 0.0)) > 1.0


def project_action(action, kernel):
    if kernel is None:
        return None
    return min(max(action, kernel[0]), kernel[1])


def print_frontier_table():
    rhos = [0.60, 0.80, 1.0 / LAMBDA, 0.90, 1.00]

    print(f"lambda={LAMBDA}, u_max={U_MAX}, threshold=1/lambda={1.0 / LAMBDA:.3f}")
    print()
    print("| rho | lambda*rho | K(rho) | cert_accept | learn_allowed | nominal_unsafe |")
    print("|---:|---:|---|---|---|---|")

    for rho in rhos:
        kernel = safe_kernel(rho)
        cert_accept = kernel is not None
        learn_allowed = cert_accept
        print(
            f"| {rho:.3f} | {LAMBDA * rho:.3f} | {format_interval(kernel)} | "
            f"{str(cert_accept).lower()} | {str(learn_allowed).lower()} | "
            f"{str(nominal_unsafe(rho)).lower()} |"
        )


def print_trusted_anchor_variant(rho):
    print()
    print(f"Trusted-anchor variant at rho={rho:.3f}:")
    print("| anchor | reduced ambiguity set | kernel | cert_accept | example action |")
    print("|---|---|---|---|---|")

    variants = [
        ("none", -rho, rho),
        ("trusted sign: x>=0", 0.0, rho),
        ("trusted sign: x<=0", -rho, 0.0),
    ]
    for label, low, high in variants:
        kernel = safe_kernel_for_interval(low, high)
        action = project_action(0.0, kernel)
        action_text = "n/a" if action is None else f"{action:.3f}"
        print(
            f"| {label} | [{low:.3f}, {high:.3f}] | {format_interval(kernel)} | "
            f"{str(kernel is not None).lower()} | {action_text} |"
        )


def print_learning_aware_variant():
    print()
    print("Learning-aware FDI variant: malicious data proposes u_candidate=0.100")
    print("| rho | K(rho) | raw update | gated action | gate decision |")
    print("|---:|---|---:|---|---|")

    raw_action = 0.1
    for rho in [0.60, 0.80, 0.90]:
        kernel = safe_kernel(rho)
        projected = project_action(raw_action, kernel)
        if kernel is None:
            decision = "freeze/reject"
            gated = "n/a"
        elif projected != raw_action:
            decision = "project/constrain"
            gated = f"{projected:.3f}"
        else:
            decision = "allow"
            gated = f"{projected:.3f}"
        print(f"| {rho:.3f} | {format_interval(kernel)} | {raw_action:.3f} | {gated} | {decision} |")


def main():
    print_frontier_table()

    print()
    r = 0.9
    print("At rho=r=0.9, the two individually safe intervals are:")
    print(f"  U_safe(+r) = {format_interval(safe_interval_for_state(r))}")
    print(f"  U_safe(-r) = {format_interval(safe_interval_for_state(-r))}")
    print("Their intersection is empty, so a sound certificate must reject or freeze learning.")

    print_trusted_anchor_variant(r)
    print_learning_aware_variant()


if __name__ == "__main__":
    main()
