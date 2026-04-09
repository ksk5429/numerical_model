# Changelog

All notable changes to Op^3 are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and this
project uses [Semantic Versioning](https://semver.org/).

## [0.3.0] - 2026-04-08

The "Track C industry-grade" release. Closes Phases 1-7 of the Op^3
development plan.

### Added

- **Phase 1 Calibration**: tower template loader, RNA mass + inertia
  loader, rigid CM offset, calibration regression harness, sensitivity
  tornado, mode-shape MAC. 4/4 calibrated examples land within 4% of
  published references; NREL 5 MW OC3 monopile within 0.4%.
- **Phase 2 V&V**: 60+ falsification gates across analytical references,
  consistency, sensitivity invariants, energy/reciprocity/units/coords/
  orthogonality, plus mesh + dt convergence orders.
- **Phase 3 Geotechnical integration**: PISA module
  (`op3/standards/pisa.py`), cyclic degradation
  (`op3/standards/cyclic_degradation.py`), HSsmall constitutive wrapper
  (`op3/standards/hssmall.py`), and Mode D dissipation-weighted
  formulation wired through `_attach_distributed_bnwf`.
- **Phase 4 OpenFAST**: end-to-end runner with binary discovery,
  v5.0.0 SiteA deck built from the OC3 Tripod r-test, SoilDyn export
  bridge (`op3/openfast_coupling/soildyn_export.py`), DLC 1.1 partial
  sweep, DLC 6.1 parked extreme runner, DNV-ST-0126 + IEC 61400-3
  conformance audits.
- **Phase 5 UQ**: Monte Carlo soil propagation, Hermite polynomial
  chaos expansion, grid-based Bayesian calibration. 13/13 tests pass;
  end-to-end Bayesian EI calibration of NREL 5 MW OC3 yields posterior
  mean 1.014 +/- 0.076.
- **Phase 6 Reproducibility**: pinned snapshot test with SHA-256 hash
  of canonical SoilDyn export.
- **Phase 7 Documentation**: Sphinx scaffold (8 RST documents covering
  the entire op3 package), Mode D paper-draft notes, paper-extraction
  backlog tracker.

### Test totals

- 121 active V&V tests (all PASS)
- 33 example smoke tests across 11 turbines
- 4 calibration regression tests against published references
- 35/36 DNV-ST-0126 conformance checks
- IEC 61400-3 structural + foundation provisions all PASS

### Verified

- OpenFAST v5.0.0 SiteA tripod end-to-end
- OpenFAST v5.0.0 SiteA + SoilDyn with Op^3 PISA-derived 6x6 stiffness
- DLC 1.1 partial sweep at U = {8, 12, 18} m/s

### Backlog (tracked, not blocking)

- PISA cross-validation reference numbers from Byrne 2020 / Burd 2020 /
  Murphy 2018 (see `validation/benchmarks/PAPER_EXTRACTION_BACKLOG.md`)
- OC6 Phase II reference numbers from Bergua 2021
- Full DLC 1.1 coverage (12 speeds x 6 seeds x 600 s)
- Multi-point SoilDyn coupling for tripod via custom DLL

## [0.2.0] - 2026-04-02

Initial public release: 11 NREL reference turbines, four foundation
modes, three analyses (eigen/pushover/transient), 33/33 smoke tests.

## [0.1.0] - 2026-03-30

Internal proof-of-concept.
