---
title: 'Op^3: an OptumGX-OpenSeesPy-OpenFAST integration framework for offshore wind turbine foundations'
tags:
  - Python
  - offshore wind
  - structural dynamics
  - geotechnical engineering
  - PISA
  - OpenFAST
  - SoilDyn
  - Bayesian calibration
authors:
  - name: Kyeong Sun Kim
    orcid: 0009-0000-0000-0000
    affiliation: 1
affiliations:
  - name: "Department of Civil and Environmental Engineering, Seoul National University, Republic of Korea"
    index: 1
date: 8 April 2026
bibliography: paper.bib
---

# Summary

`Op^3` (pronounced *O-p-cubed*) is an integrated numerical-modelling
framework for offshore wind turbine support structures. It provides a
single, V&V'd Python pipeline that bridges three otherwise-disconnected
codes used in offshore wind design: **OptumGX** (3D finite-element
limit analysis, commercial), **OpenSeesPy** (open-source structural
dynamics), and **OpenFAST v5** (open-source coupled aero-hydro-servo-
elastic simulation). The framework was developed alongside a doctoral
dissertation on prescriptive maintenance of offshore wind turbine
foundations and is calibrated against the entire NREL reference wind
turbine library plus a real-world site (SiteA 4 MW class, Republic of
Korea).

`Op^3` exposes four foundation idealisations forming a hierarchy of
fidelity from rigid base to a novel dissipation-weighted generalised
Beam-on-Nonlinear-Winkler-Foundation (BNWF). It implements the major
international design standards (DNVGL-ST-0126, ISO 19901-4, API RP
2GEO + Gazetas, Carbon Trust OWA, the PISA framework of Burd 2020 /
Byrne 2020, and the Hardening-Soil-with-small-strain-stiffness model
of Benz 2007), the Hardin-Drnevich / Vucetic-Dobry cyclic-degradation
machinery, and a Phase 5 uncertainty-quantification module containing
Monte Carlo soil propagation, Hermite polynomial-chaos expansion, and
grid-based Bayesian calibration. A direct bridge to the OpenFAST v5
SoilDyn module allows any `Op^3` foundation to be plugged into a
production-grade coupled wind turbine simulation.

# Statement of need

Designers and researchers working on offshore wind turbine foundations
routinely face a fragmentation problem. Geotechnical engineers run
finite-element packages (PLAXIS, OptumGX, ABAQUS) to characterise the
soil. Structural engineers run beam-on-Winkler models in OpenSees,
SACS, or proprietary in-house codes to assess the support structure.
Wind-energy specialists run OpenFAST or HAWC2 to evaluate
aero-hydro-servo-elastic loads. The hand-off between these three
worlds is typically a one-shot exchange of stiffness matrices via a
spreadsheet, with no formal verification that the same physical model
is being represented consistently.

`Op^3` closes this gap. The four foundation modes are
*algorithmically equivalent* in the limit of refined discretisation,
the standards-based stiffness matrices are byte-identical to the
hand-computed reference values, the calibration regression is pinned
against published natural frequencies with explicit citations, and
the entire pipeline is reproduced bit-for-bit by a SHA-256 snapshot
test. The Bayesian calibration of the NREL 5 MW OC3 monopile tower EI
yields a posterior of $1.014 \pm 0.076$ -- consistent with the
published value to within 1.4 % mean and a 13 % credible interval at
the 90 % level. The same harness can be retargeted to any of the 11
bundled examples or to user-supplied turbines.

To our knowledge `Op^3` is the first openly available framework that
combines:

1. The PISA monopile soil reactions of Burd et al. (2020) and Byrne
   et al. (2020), implemented as the canonical 4-parameter conic
   shape function with full lateral / moment / base-shear / base-moment
   decomposition.
2. The cyclic Hardin-Drnevich knockdown of Vucetic & Dobry (1991),
   layered onto PISA so that storm-loaded stiffness can be evaluated
   on demand.
3. A direct programmatic export to the OpenFAST v5 SoilDyn module via
   the CalcOption=1 (6x6 stiffness) format documented in the OC6 Phase
   II Joint Industry Project (Bergua et al. 2021).
4. A novel **dissipation-weighted Mode D** formulation that uses the
   energy-dissipation field from an OptumGX elasto-plastic analysis
   as a multiplicative weighting on the elastic Winkler springs,
   enabling fatigue- and scour-aware foundation modelling without
   re-solving the coupled elasto-plastic problem at every load step.

# Verification & validation

`Op^3` ships with 121 active V&V tests organised into 14 modules
covering analytical closed-form references, internal cross-path
consistency, sensitivity invariants, modal orthogonality, energy
conservation, reciprocity (Maxwell-Betti), coordinate-system
invariance, unit-system invariance, mesh-and-time-step convergence
(verified second-order spatial accuracy), per-module sub-system
checks, and end-to-end OpenFAST coupling. A pinned reproducibility
snapshot uses a SHA-256 hash of a deterministic SoilDyn export to
catch any byte-level drift in the pipeline. Continuous integration
runs the full suite on every push.

The published-source calibration regression establishes physical
trust: NREL 5 MW fixed-base lands within 2.5 % of Jonkman 2009, NREL
5 MW OC3 monopile within 0.4 % of Jonkman & Musial 2010, the SiteA
field site within 3.7 % of the dissertation's own operational modal
analysis, and IEA 15 MW within 10.6 % of Gaertner 2020 (the headroom
absorbed by the ongoing distributed-BNWF refinement). DNV-ST-0126
clauses 4.5.4 / 4.5.5 / 4.5.6 / 5.2.3 / 5.2.4 / 5.7 / 6.2.2 / 4.6 are
audited per example; the IEC 61400-3 §7.4 / §7.5 / §10.3 provisions
are similarly evaluated.

# Acknowledgements

This work was supported by the doctoral programme at Seoul National
University. The OpenFAST v5.0.0 binary and the v5.0.0 r-test
directory are used under Apache 2.0; the NREL reference wind turbine
inputs are used under their respective open licences with full
attribution preserved in the repository.

# References
