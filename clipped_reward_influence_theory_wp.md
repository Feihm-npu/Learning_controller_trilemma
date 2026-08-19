> ⚠️ **过时的规划/形式化草稿（2026-08-19 标注）。** 早于 2026-08-19 的实验与审计。
> **当前权威状态与方向请读 [`usenix_direction_audit_0819.md`](usenix_direction_audit_0819.md)。**

# Clipped reward-influence theory work package

> Opened on 2026-08-03 after the V3 trajectory audit had already established
> that the current unclipped theorem was eligible on `0/36` poisoned batches.
> This is a theory/diagnostic work package over already observed batches.  It
> does not open a new learner-seed namespace and is not confirmatory evidence
> for a stronger physical attack.

## Question

Can the exact one-batch positive-support calculation be extended across the
two boundaries that excluded most V3 batches:

1. the centered-return zonotope contains the origin; and
2. global Euclidean gradient clipping may activate?

Coordinatewise parameter clipping remains outside the proposed theorem.  A
batch may use the extension only when parameter clipping is excluded over the
entire reward box by a separately checked bound.

## Mathematical route

Let

\[
  Z=\{y_0+M\delta:\|\delta\|_\infty\le\epsilon\},\qquad
  B=S^\top/\sqrt T,
\]

so the standardized raw gradient is `B y / ||y||`.  With global gradient cap
`G`, the applied gradient is

\[
  g_G(y)=\frac{By}{\max\{\|y\|,\|By\|/G\}}.
\]

For a gate direction `c` and learning rate `alpha`, define
`q = alpha B^T c`.  Positive support at least `t` is equivalent, for nonzero
`y`, to both

\[
  t\|y\|\le q^\top y,
  \qquad
  (t/G)\|By\|\le q^\top y.
\]

The old formulation optimized directly over `Z`; when `0 in Z`, the zero
vector made every fixed-`t` feasibility problem spuriously feasible.  The
ratio is positively homogeneous, so instead use the conic hull

\[
  \operatorname{cone}(Z)=\{\lambda y_0+Mw:
       \lambda\ge0,\ -\epsilon\lambda\le w\le\epsilon\lambda\}.
\]

For `t > 0`, normalize the positive numerator with `q^T y = 1`.  Fixed-`t`
feasibility then consists only of affine and second-order-cone constraints:

\[
\begin{aligned}
 y&=\lambda y_0+Mw,\\
 \lambda&\ge0,\quad -\epsilon\lambda\le w\le\epsilon\lambda,\\
 q^\top y&=1,\\
 t\|y\|&\le1,\\
 (t/G)\|By\|&\le1.
\end{aligned}
\]

Bisection therefore remains exact for positive support under global gradient
clipping.  A reward-box witness is recovered by maximizing distance along the
returned cone ray; the recovered centered-return norm must exceed the
learner's normalization tolerance before it is treated as an implementation
witness.

This construction is a conic homogenization/Charnes--Cooper-style removal of
scale, combined with the second-order feasibility cone.  Relevant theory
anchors are:

- Schaible, *Operations Research* 1976, “Duality in Fractional Programming: A
  Unified Approach,” DOI `10.1287/opre.24.3.452`;
- Belloni and Freund, *SIAM Journal on Optimization* 2008, “On the
  Second-Order Feasibility Cone,” DOI `10.1137/06067198X`;
- Agrawal and Boyd, *Optimization Letters* 2020, “Disciplined Quasiconvex
  Programming,” DOI `10.1007/s11590-020-01561-8`;
- Bauschke, Bendit, and Wang, *Set-Valued and Variational Analysis* 2023,
  “The Homogenization Cone: Polar Cone and Projection,” DOI
  `10.1007/s11228-023-00687-y`.

These references supply standard optimization machinery; novelty, if any,
must be claimed only for its application to standardized policy-gradient
reward influence and the explicit clipping formula.

## Validation order

1. Unit tests on analytic and brute-force small cases:
   - agreement with the old solver when its premises hold;
   - a reward box containing a centered-return zero;
   - a cap-active example;
   - recovered-witness budget and numerical support error.
2. Re-audit the already locked V3 poisoned batches without retraining.
3. Report how many batches are covered after separately excluding
   coordinatewise parameter clipping, plus support gaps and witness errors.
4. Only if the implementation and witness checks pass, revise the theorem.

## Claim and stop rules

- A pass supports an exact **one-batch positive-support audit** under global
  gradient clipping and across normalization singularities.
- It does not establish multi-batch optimality, produce the successful V3
  attack, or cover coordinatewise parameter clipping.
- If cone witnesses cannot be recovered above the learner normalization
  tolerance, or any brute-force lower bound exceeds computed support beyond
  numerical tolerance, stop and retain the current unclipped theorem.
