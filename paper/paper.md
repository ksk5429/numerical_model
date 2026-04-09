---
title: 'Op^3: An integrated numerical and digital-twin framework for scour assessment of offshore wind turbine tripod suction-bucket foundations'
tags:
  - Python
  - offshore wind
  - geotechnical engineering
  - scour
  - digital twin
  - Bayesian decision analysis
  - OpenSees
  - OpenFAST
authors:
  - name: Kyeong Sun Kim
    orcid: 0000-0000-0000-0000
    affiliation: 1
affiliations:
  - name: Department of Civil and Environmental Engineering, Seoul National University, Republic of Korea
    index: 1
date: 9 April 2026
bibliography: paper.bib
---

# Summary

**Op^3** is an open-source Python framework that combines three-dimensional
geotechnical limit analysis (via OptumGX), one-dimensional structural
dynamics (via OpenSeesPy), and aero-hydro-servo-elastic simulation
(via OpenFAST) into a single pipeline for assessing the health and
remaining capacity of offshore wind turbine foundations under
progressive scour. The framework is accompanied by a standalone web
application (`op3_viz`) that wraps every component in a six-tab
interactive interface suitable for engineer-facing deployment.

Op^3 is specifically designed for *multi-footing* foundations — tripods
with three suction caissons — where the non-linear cyclic load-sharing
between footings makes conventional `p-y`/`t-z` spring models
inadequate. It provides four foundation-mode abstractions (fixed base,
6x6 stiffness matrix, distributed BNWF, and a new dissipation-weighted
formulation), each with uniform `.eigen()`, `.pushover()`, and
`.transient()` APIs. A Bayesian multi-evidence fusion layer produces
posterior distributions over scour depth conditioned on field sensor
observations, and a value-of-information analysis prescribes the
maintenance action that minimises expected cost.

# Statement of need

Offshore wind foundations are typically assessed using commercial
design codes (BLADED, SACS) or open-source reference solvers
(OpenFAST, OpenSees), none of which combine three-dimensional
geotechnical capacity, multi-mode foundation abstractions, a decision
layer, and a digital-twin user interface in a single package. The gap
is most acute for tripod suction-bucket foundations, where published
`p-y` correlations — calibrated for slender monopiles — systematically
overpredict stiffness and underpredict capacity.

Op^3 fills this gap with an open-source, pip-installable,
Zenodo-archived framework that ships with:

1. A 177-run OptumGX 3D limit-analysis database covering
   D = 6–10 m, L/D = 0.5–2.0, and S = 0–3 m
2. A validated OpenSeesPy 1D Winkler model calibrated against
   22 centrifuge test cases spanning five soil conditions
3. An OpenFAST coupling via SoilDyn for DLC 1.1 / 6.1 design
   load cases
4. A Bayesian decision layer with explicit value-of-information
   analysis
5. A neural digital-twin encoder trained on 1,794 real Monte Carlo
   simulations
6. A `op3_viz` six-tab web application
7. Continuous integration, 83 % test coverage, and a release
   validation report with 21 verification stages

The framework has been validated end-to-end against the 4 MW-class
Gunsan demonstration wind farm, including 32 months of continuous
operational modal analysis data (15,580 processing windows, zero
false alarms).

# Architecture

Op^3 is layered into seven components:

- `op3.foundations` — four foundation-mode abstractions with a
  uniform API
- `op3.composer` — assembles a rotor + tower + foundation model
- `op3.opensees_foundations` — 1D structural dynamics
- `op3.optumgx_interface` — 3D limit analysis and stiffness
  extraction
- `op3.openfast_coupling` — SubDyn 6x6 export + OpenFAST runner
- `op3.uq` — Monte Carlo, polynomial chaos expansion, and
  Bayesian importance sampling
- `op3_viz` — the Dash web application (six tabs: 3D Viewer,
  Bayesian Scour, Mode D, PCE Surrogate, DLC 1.1 Time-series,
  Compliance & Actions)

A private-data resolver (`op3.data_sources`) separates the public
framework from site-specific proprietary data. When the private
data tree is unavailable, the framework raises a clear
`FileNotFoundError` rather than substituting synthetic values.

# Validation

The framework ships with a `scripts/release_validation_report.py`
command that runs 21 verification stages and emits a consolidated
JSON + Markdown report. As of `v1.0.0-rc1`: code verification,
consistency, sensitivity, extended V&V, PISA module, cyclic
degradation, HSsmall, Mode D, reproducibility snapshot, calibration
regression, and the three-analysis smoke test all pass. The NREL
5 MW on OC3 monopile is calibrated within 0.4 % of the published
reference frequency. OC6 Phase II and PISA cross-validation are
in `AWAITING_VERIFY` state with scaffold scripts; full verification
is scheduled for the `v1.0` final release.

# Acknowledgements

The Op^3 framework was developed under the Korea Electric Power
Corporation (KEPCO) research agreement *"Natural frequency-based
scour monitoring for offshore wind turbine foundations"*. The
Gunsan 4.2 MW case-study data were provided by KEPCO Research
Institute (KEPRI), Hyundai E&C / Mirae & Company (MMB), and
Unison Co., Ltd. under academic-use terms. The author thanks the
NREL OpenFAST team for the reference turbine library and r-test
regression suite.

# References
