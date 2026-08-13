# Optimization-theory route for reward-influence certificates

> Decision note, 2026-08-03. This document records which mathematical
> machinery closes a current paper gap, which machinery only suggests a
> future route, and where the NDSS work package should stop.

## The part that is now solved

The standardized REINFORCE update with a global Euclidean gradient cap is a
positively homogeneous fractional map. Four theory anchors give the required
construction:

| Ingredient | Theory anchor | Use here |
|---|---|---|
| Fractional scale removal | Schaible, *Operations Research* 24(3), 1976, DOI `10.1287/opre.24.3.452` | Normalize a positive halfspace numerator instead of the possibly zero denominator. |
| Second-order feasibility | Belloni and Freund, *SIAM Journal on Optimization* 19(3), 2008, DOI `10.1137/06067198X` | Express each denominator branch as an SOC constraint. |
| Quasiconvex bisection | Agrawal and Boyd, *Optimization Letters* 14(7), 2020, DOI `10.1007/s11590-020-01561-8` | Justify fixed-level conic feasibility plus bisection. |
| Homogenization cone | Bauschke, Bendit, and Wang, *Set-Valued and Variational Analysis* 31(3), 2023, DOI `10.1007/s11228-023-00687-y` | Represent all nonzero rays of the centered-return zonotope without admitting the zero-vector false witness. |

Their combination yields the exact positive one-batch support theorem in
`clipped_reward_influence_theory_wp.md`. The novelty claim must remain the
application and explicit clipping formula, not the underlying optimization
machinery.

## Why coordinatewise parameter clipping is different

Let the post-gradient-cap update be `z(y)` and let the learner apply the box
projection

\[
  \theta^+(y)=\Pi_{[\ell,u]}(\theta+\alpha z(y)).
\]

Each coordinate has three regimes: lower-saturated, unsaturated, and
upper-saturated. For parameter dimension `d`, an exact formulation therefore
has up to `3^d` disjuncts. The objective is affine inside a fixed regime, but
the regime boundaries contain ratios of linear forms and the maximum of two
norms. Filling the normalized-gradient surface by its conic interior gives a
sound relaxation, not an exact reformulation: along a ray, clipping can make a
weighted objective peak at an interior saturation kink.

The relevant mathematical-programming routes are:

| Route | Theory anchor | What it could provide | Limitation here |
|---|---|---|---|
| Perspective formulation | Günlük and Linderoth, *Mathematical Programming* 124, 2010, DOI `10.1007/s10107-010-0360-z` | Strong convex-hull descriptions for indicator-controlled convex sets. | Our normalization boundary is nonconvex, so the result is not directly an exact SOCP. |
| Disjunctive conic cuts | Belotti et al., *Discrete Optimization* 24, 2017, DOI `10.1016/j.disopt.2016.10.001` | Branch-and-cut treatment of mixed-integer SOC disjunctions. | Requires a valid conic description of each clipping regime and a global mixed-integer solve. |
| Bi-perspective fractional formulation | Letchford, Ni, and Zhong, *Mathematical Programming* 190, 2021, DOI `10.1007/s10107-020-01519-9` | Tight bounds for mixed-integer fractional programs with indicators. | Promising analogue, but our denominator is a max of norms and saturation induces the indicator. |
| Split convex-hull hierarchy | Kronqvist, Misener, and Tsay, *Mathematical Programming*, 2025, DOI `10.1007/s10107-025-02232-1` | A tunable hierarchy between big-M and full convex-hull formulations. | Produces increasingly strong bounds, not an immediate exact certificate. |

## Low-cost bound and why it is not a paper contribution

For `d=P^T a`, projection non-expansiveness gives the universally valid bound

\[
 a^T P(\theta^+-\theta) \le \alpha G\|d\|_2.
\]

It can be intersected with the directional distance to the parameter box. On
the 36 locked V3 batches this bound is about `4.83--5.00`, whereas the largest
observed target-direction increment is `0.605`; it is sound but too loose to
explain or exclude any relevant behavior. It should not be promoted as a
contribution.

## Go/no-go decision

Do not add a mixed-integer clipping theorem to the current NDSS submission.
The existing continuous extension already changes exact implementation
coverage from `0/36` to `22/36`. The remaining ten parameter-boundary batches
include nine observed clipping activations, but covering them would still not
close the failed causal bridge: the theorem-generated burned-seed attack makes
nonzero edits in `9/12` batches and causes `0/24` release failures.

Reopen this route only if there is a materially new objective beyond batch
coverage. A disciplined future experiment would enumerate the nine regimes
for the current two-parameter learner, compute certified upper/lower gaps with
a global solver, and stop unless the formulation either (i) changes a release
gate decision or (ii) yields a multi-batch attack that passes a preregistered
burned-seed smoke. Do not open untouched learner seeds for a formulation-only
gain.
