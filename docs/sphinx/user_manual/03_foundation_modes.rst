Foundation Modes
================

Op^3 provides four foundation-mode abstractions through a uniform
``op3.foundations`` API. Each mode trades off fidelity, cost, and
downstream simulator compatibility.

Mode A - Fixed base
-------------------

- **API:** ``build_foundation(mode="fixed")``
- **Use case:** upper-bound reference; what the tower looks like if
  the foundation were infinitely stiff
- **Cost:** trivial (no soil computation)

Mode B - 6x6 stiffness matrix
------------------------------

- **API:** ``build_foundation(mode="stiffness_6x6")``
- **Use case:** compact SSI representation for OpenFAST SoilDyn
  coupling
- **Cost:** O(1) per stiffness query

Mode C - Distributed BNWF
--------------------------

- **API:** ``build_foundation(mode="distributed_bnwf", spring_profile=...)``
- **Use case:** full non-linear Winkler model with depth-resolved
  p-y / t-z / base / lid springs
- **Cost:** moderate; scales with number of springs

Mode D - Dissipation-weighted
------------------------------

- **API:** ``build_foundation(mode="dissipation_weighted",
  mode_d_alpha=..., mode_d_beta=...)``
- **Use case:** the new formulation introduced by this thesis
- **Weight function:** ``w(z) = beta + (1 - beta) * (1 - D(z)/D_max)^alpha``

Choosing a mode
---------------

All four modes expose the same ``.eigen()``, ``.pushover()``, and
``.transient()`` methods, so switching modes in an existing analysis
is a one-line change.
