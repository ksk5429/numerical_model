Web Application - the six tabs
================================

The ``op3_viz`` Dash application is the main user-facing interface.
It ships with six tabs; each is described below.

Tab 1 - 3D Viewer
-----------------

Interactive Plotly Mesh3d of the selected turbine + foundation + RNA.
Four live field overlays selectable via radio button: eigenmode 1,
eigenmode 2, bending stress, and dissipation weight. A scour slider
visualises mudline progression cosmetically (v1.1 will wire it to
rebuild the foundation springs).

Tab 2 - Bayesian Scour
----------------------

Displays the posterior distribution over scour depth produced by
importance-sampling Bayesian inference on the 1,794-row Monte Carlo
database. Shows posterior mean, 90 % credible interval, and
effective sample size.

Tab 3 - Mode D (alpha, beta)
-----------------------------

Two-dimensional heat-map of the joint posterior over the Mode D
dissipation-weighting parameters.

Tab 4 - PCE Surrogate
---------------------

Bar chart of the Hermite polynomial chaos coefficients from the
order-6 surrogate.

Tab 5 - DLC 1.1 Time-series
----------------------------

Dropdown-selectable OpenFAST ``.outb`` time-series viewer. Auto-
discovers runs under ``validation/dlc11_partial/<latest>/``.

Tab 6 - Compliance and Actions
-------------------------------

Three operator action buttons: run DNV-ST-0126 audit, run
IEC 61400-3 audit, dispatch DLC 1.1 sweep. Each returns a JSON
panel with the result.
