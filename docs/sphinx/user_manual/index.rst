Op³ User Manual
===============

Welcome to the user manual for **Op³ Studio v1.0.0-rc1**, the
integrated numerical and digital-twin framework for offshore wind
turbine foundation assessment.

.. toctree::
    :maxdepth: 2
    :caption: Contents:

    01_installation
    02_first_project
    03_foundation_modes
    04_decision_layer
    05_web_application
    06_gunsan_case_study
    07_compliance_audits
    08_report_generator
    09_troubleshooting
    10_api_reference


What Op³ is
-----------

Op³ is an open-source framework that combines four capabilities in a
single package:

1. **3D geotechnical limit-analysis** (via OptumGX) for load-bearing
   capacity and cyclic degradation of suction caisson foundations.
2. **1D structural dynamics** (via OpenSeesPy) for eigenvalue,
   pushover, and transient response of wind turbine tower + rotor
   assemblies.
3. **Aero-hydro-servo-elastic simulation** (via OpenFAST coupling)
   for DLC 1.1 and DLC 6.1 design load cases.
4. **Digital-twin decision layer** (via a neural forward model,
   Bayesian fusion, and VoI analysis) for prescriptive maintenance.

All four capabilities are exposed through a single local-first web
application, ``op3_viz``, which runs on the engineer's laptop with no
cloud dependency.

What Op³ is **not**
-------------------

- A replacement for certified commercial design software (BLADED,
  SACS). Op³ is positioned as a research-grade reference
  implementation and engineering analysis tool, not a certification
  package.
- A cloud service. No data ever leaves the engineer's workstation
  unless the user explicitly exports a report or commits to a git
  repository.
- A black-box ML system. Every numerical result can be traced to a
  specific OpenSeesPy or OptumGX invocation, and every neural
  prediction comes with the underlying training data and residuals.


Citation
--------

If you use Op³ in a publication, please cite::

    @software{op3_v1_0_0_rc1,
        author = "Kim, Kyeong Sun",
        title = "Op^3: Integrated Numerical and Digital-Twin Framework
                  for Scour Assessment of Offshore Wind Turbine Tripod
                  Suction-Bucket Foundations",
        version = "1.0.0-rc1",
        year = "2026",
        doi = "10.5281/zenodo.19476542",
        url = "https://github.com/ksk5429/numerical_model"
    }
