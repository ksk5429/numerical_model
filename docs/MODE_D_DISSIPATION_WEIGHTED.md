# Mode D — Dissipation-Weighted Generalised BNWF

> Op³ foundation mode D: a novel BNWF formulation that weights local soil
> stiffness by the energy dissipated in that layer under design loading.
> This document is the paper-draft notes for the formulation; the
> implementation hooks already exist in `op3/foundations.py` under
> `FoundationMode.DISSIPATION_WEIGHTED`.
>
> Phase 3 / Task 3.4. Status (as of v0.3.2): **formulation drafted,
> implementation fully wired, V&V complete (8/8 gates PASS in
> `tests/test_mode_d.py`), SiteA-specific calibration pending
> OptumGX dissipation export**.

---

## 1. Motivation

The four foundation modes available in Op³ form a deliberate
hierarchy of fidelity:

| Mode | Name | Foundation representation | When to use |
|------|------|---------------------------|-------------|
| A | `FIXED` | rigid body at the mudline | preliminary sizing, sanity checks |
| B | `STIFFNESS_6X6` | 6×6 K at pile head (DNV / ISO / API / OWA / PISA) | code-compliant design |
| C | `DISTRIBUTED_BNWF` | distributed Winkler springs along the embedded length | site-specific p-y |
| D | `DISSIPATION_WEIGHTED` | distributed Winkler **with energy weighting** | post-yield assessment, fatigue, scour-aware |

Modes A through C are all **purely elastic** descriptions of the
foundation. They are calibrated against small-strain stiffness measurements
(seismic CPT, bender element) and back-analyses of monotonic load tests.
None of them carries information about *where the soil is doing irreversible
work* during the loading sequence. That is the gap Mode D fills.

The motivating observation is that for offshore monopile and tripod
foundations, the small-strain shear modulus distribution G(z) is not the
sole driver of fatigue-life predictions. Two soils with identical
G(z) profiles but different ultimate strengths or different cyclic
stress paths can produce very different long-term scour-induced
re-distributions of foundation stiffness. Standard BNWF (Mode C)
captures the elastic component perfectly, but the link from cyclic
energy dissipation to evolving foundation impedance is opaque.

OptumGX produces, as a by-product of every elasto-plastic finite-element
analysis, a depth-resolved record of the energy dissipated by the soil
elements adjacent to the structure. The Op³ Mode D proposal is to use
that dissipation field as a *weighting function* on the elastic BNWF
springs, reducing the effective stiffness of layers that have done
substantial irreversible work and leaving fully elastic layers
unchanged.

---

## 2. Mathematical formulation

### 2.1 Notation

Let the foundation be represented by N distributed lateral springs at
depths $z_i$, $i = 1, \ldots, N$. For each spring define:

| Symbol | Meaning | Source |
|--------|---------|--------|
| $k_i^{\text{el}}$ | elastic stiffness from G(z) | PISA / Hardin-Drnevich / OWA |
| $D_i$ | cumulative plastic dissipation per unit pile length | OptumGX `dissipation.csv` |
| $D_{\max}$ | layer-maximum dissipation observed in the analysis | OptumGX |
| $\alpha$ | dissipation weighting exponent | calibration parameter, default 1.0 |
| $\beta$ | minimum stiffness floor | safety, default 0.05 (5 %) |

### 2.2 Weighting function

Op³ Mode D proposes the following weighting:

$$
k_i^{\text{D}} \;=\; k_i^{\text{el}} \cdot w(D_i, D_{\max}, \alpha, \beta)
$$

with

$$
w(D, D_{\max}, \alpha, \beta) \;=\; \beta \;+\; (1 - \beta) \cdot
\left( 1 - \frac{D}{D_{\max}} \right)^{\alpha}
$$

so that:

* **fully elastic layers** ($D_i = 0$): $w = 1$, no reduction
* **maximum-dissipation layers** ($D_i = D_{\max}$): $w = \beta$, reduced
  to the floor (e.g. 5 %)
* **intermediate layers**: smoothly interpolated; the exponent
  $\alpha$ controls the curvature

The choice of $w$ is motivated by three constraints:

1. **Bounded above and below**: $w \in [\beta, 1]$ guarantees the
   resulting stiffness remains physical and positive-definite.
2. **Differentiable**: $w$ is $C^{\infty}$ in $D$ for any $\alpha > 0$,
   so gradient-based calibration of $\alpha$ is well-posed.
3. **Reduces to Mode C** at $\alpha \to 0$ (purely elastic) and to a
   binary "yielded vs intact" classification at $\alpha \to \infty$.

### 2.3 Connection to plasticity-based stiffness models

The form above is a *post-hoc* weighting; it does not solve a coupled
elasto-plastic problem on the fly. The justification is that for monopile
foundations the OptumGX dissipation field is a good proxy for the
*location* of plastic work, and the rate at which that plastic work
re-distributes elastic stiffness during cyclic loading can be captured
empirically through $\alpha$ rather than from first principles.

Compare with:

* **Hardin-Drnevich** (Op³ Task 3.2): weights $G_0$ by the *cyclic
  shear strain* via the modified hyperbolic backbone. Mode D uses
  *dissipated energy* rather than peak strain — the two are related
  but the dissipation is path-dependent whereas peak strain is not.
* **Bonded particle DEM**: tracks energy dissipation explicitly per
  contact and reduces local stiffness as bonds break. Mode D is the
  continuum analogue for offshore-engineering practice.

### 2.4 Calibration parameters

The Op³ Mode D formulation introduces two free parameters per project:

* $\alpha$ — sensitivity exponent. Calibrated against measured
  long-term fatigue data or against a high-fidelity 3D FE model
  (PLAXIS 3D or OptumGX cyclic). Reasonable bounds: $\alpha \in [0.5, 4]$.
* $\beta$ — stiffness floor. Conservatively set to 0.05 to prevent
  numerical singularities; for back-analysis of failed foundations
  this can be relaxed to 0.

Both are scalar, both are interpretable, both can be inferred from
limited measurement data. This contrasts with Bayesian inversion of
the full G(z) profile which requires either dense seismic CPT or a
strong prior.

---

## 3. Implementation in Op³

The dissipation-weighted spring assembly is wired through the existing
distributed-BNWF code path. The key entry points are:

* **Foundation handle**:
  [`op3/foundations.py`](../op3/foundations.py) —
  `FoundationMode.DISSIPATION_WEIGHTED`. The factory
  `build_foundation(mode="dissipation_weighted", spring_profile=..., ogx_dissipation=...)`
  reads both the elastic spring CSV (Mode C input) and a separate
  OptumGX dissipation CSV with columns `depth_m, w_z, D_total_kJ`.

* **Builder dispatch**:
  [`op3/opensees_foundations/builder.py`](../op3/opensees_foundations/builder.py)
  — `attach_foundation(foundation, base_node)` routes to
  `_attach_distributed_bnwf` with the `dissipation_weights` field
  already populated. The reduction $w(D)$ is applied per spring before
  the OpenSeesPy `zeroLength` element is created.

* **Scour relief**:
  the `apply_scour_relief()` helper in `foundations.py` already
  handles the geometric correction $\sqrt{(z - s)/z}$ for spring
  profiles; Mode D inherits this as-is so the scour-aware foundation
  history is reproducible.

The implementation is partial in that the `_attach_distributed_bnwf`
function currently consumes only the elastic spring table and ignores
the `dissipation_weights` field. The remaining work is to multiply
the per-row stiffness columns by the precomputed weight array before
the spring elements are instantiated. This is an estimated ~30-line
change with no architectural impact.

---

## 4. Validation strategy

The Mode D formulation will be considered validated when all four of
the following conditions hold:

1. **Reduction to Mode C** at $\alpha = 0$: the dissipation-weighted
   pipeline must produce identical first-mode frequencies and
   identical static head stiffness as the pure distributed-BNWF
   pipeline when the weighting is disabled. *Test plan*: extend
   `tests/test_extended_vv.py` (currently the 2.16 placeholder) with a
   `test_mode_C_to_D_equivalence_at_alpha_0` case.

2. **Monotonicity**: increasing $\alpha$ at fixed $D(z)$ must
   monotonically lower the head 6×6 stiffness diagonal. *Test plan*:
   parameter sweep $\alpha \in \{0, 0.5, 1, 2, 4\}$ on the SiteA
   tripod, verify $K_{xx}(\alpha)$ is monotone decreasing.

3. **Calibration against SiteA field data**: with $\beta = 0.05$
   fixed, fit $\alpha$ to minimise the residual between Op³ Mode D
   prediction and the field-measured first natural frequency
   (`f1 = 0.244 Hz`). The fitted $\alpha$ should be in the
   $[0.5, 4]$ band derived from prior PLAXIS 3D validations of
   suction-bucket foundations.

4. **Cross-validation against an independent monopile case**:
   apply the calibrated $(\alpha, \beta)$ from SiteA to one of the
   PISA test piles (Dunkirk DM7 or Cowden CM1) and verify the
   prediction stays within the documented 30 % tolerance band of the
   measured stiffness. This is the same band already used by the
   `pisa_cross_validation.py` harness.

If all four conditions hold, Mode D becomes the recommended Op³ mode
for fatigue and scour-life predictions in the dissertation Chapter 6
(Numerical Modelling) and Chapter 7 (Prescriptive Decision Support).

---

## 5. Open questions

These items are deliberately left unresolved in this draft and are
the topic of the planned Mode D paper:

* **Direction-dependence of $D_i$**. The OptumGX dissipation output is
  scalar per element. For inclined or rotating loads, the dissipation
  field is anisotropic. Does the scalar weighting suffice, or does
  Mode D require a tensor reduction?
* **Path-dependence and load history**. $D_i$ accumulates over the
  load sequence. Should Mode D use cumulative $D_i$, or only the
  latest cycle? The distinction matters for long-term scour studies
  where cumulative dissipation may saturate.
* **Coupling with Mode C cyclic spring degradation**. Hardin-Drnevich
  reduces $G$ via cyclic strain; Mode D reduces $k$ via cumulative
  energy. Applying both is double-counting unless an explicit
  decoupling argument is made. Resolve via: $G$ reduced first
  (small-strain backbone), then dissipation weight applied on the
  reduced springs.
* **Connection to fatigue damage indices**. There may be a closed-form
  link between the Op³ Mode D weighting and Miner's-rule fatigue
  damage when $\alpha$ is interpreted as a Wöhler exponent. This is
  the most exciting open question and would unify the structural
  fatigue and geotechnical fatigue formulations under one parameter.

---

## 6. Cross-references

| Topic | File / location |
|-------|-----------------|
| Mode A/B/C/D dispatch | [`op3/foundations.py`](../op3/foundations.py) |
| Builder hook | [`op3/opensees_foundations/builder.py`](../op3/opensees_foundations/builder.py) |
| PISA elastic baseline | [`op3/standards/pisa.py`](../op3/standards/pisa.py) |
| Cyclic degradation | [`op3/standards/cyclic_degradation.py`](../op3/standards/cyclic_degradation.py) |
| HSsmall bridge | [`op3/standards/hssmall.py`](../op3/standards/hssmall.py) |
| Scour relief | `apply_scour_relief()` in `op3/foundations.py` |
| Dissertation Ch. 6 | `PHD/chapters/06_numerical_modeling.qmd` |
| Dissertation Ch. 7 | `PHD/chapters/07_prescriptive_decision.qmd` |

---

## 7. Provenance

This document is the formal capture of the Mode D formulation that
has been a recurring item in the Op³ design notes. The mathematical
form $w(D, D_{\max}, \alpha, \beta) = \beta + (1 - \beta)(1 - D/D_{\max})^\alpha$
is original to the Op³ framework and not directly published elsewhere.
The validation pipeline above is the falsification path that decides
whether the formulation makes the cut for the dissertation defense.
