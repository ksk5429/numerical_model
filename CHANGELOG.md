# Changelog

All notable changes to Op^3 are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and this
project uses [Semantic Versioning](https://semver.org/).

## [1.0.0-rc2] - 2026-04-10

Comprehensive V&V upgrade, visualization, and repository hardening.

### Added

- **39 cross-validation benchmarks** against 25+ published sources
  (35/38 in-scope verified, 92%)
- **Fatigue DEL module** (`op3/fatigue.py`): rainflow counting +
  damage-equivalent loads per DNV-RP-C203
- **Visualization stack** (6 modules, 23 figures):
  - `op3/visualization.py`: opsvis (OpenSeesPy model, modes, pushover)
  - `op3/viz_optumgx.py`: PyVista 3D bucket pressure, collapse mechanism
  - `op3/viz_openfast.py`: welib PSD, pCrunch DLC stats, DEL
  - `op3/viz_tier1.py`: VHM envelope, cross-pipeline, scour sweep, Mode C/D
  - `op3/viz_tier2.py`: foundation profile, rainflow, Campbell, M-theta
  - `op3/viz_tier3.py`: interactive 3D (Plotly HTML), Bayesian sensor overlay
- **Nonlinear BNWF** in production builder: `_attach_distributed_bnwf_nonlinear()`,
  `run_pushover_moment_rotation()`, `run_cyclic_analysis()`
- **OpenFAST load validation**: OC3 GenPwr -0.2%, RotSpeed -0.6%
- **64 new unit tests** (fatigue, foundations, composer, visualization)
- **Sphinx gallery page** with 17 embedded figures
- **Developer tools**: Makefile, .editorconfig, .pre-commit-config.yaml
- **Governance**: CODE_OF_CONDUCT.md, SECURITY.md

### Fixed

- LICENSE: MIT -> Apache-2.0 (matches pyproject.toml)
- 3 SyntaxError files from bare `<REDACTED>` patterns
- 55 bare `except:` -> typed exceptions
- 25 `np.trapz` -> `np.trapezoid` (deprecated)
- 16 stale config filename references (`site_a_site.yaml`)
- 5 duplicate pipeline files -> re-export shims (-1,353 lines)
- Sphinx build now zero-warning locally

### Changed

- CI: pytest with coverage replaces individual unittest runs
- V&V test count: 140 across 15 modules (was 121/14)
- Intersphinx: added OpenFAST + pandas cross-references

---

## [1.0.0-rc1] - 2026-04-09

First release candidate of the integrated tool. Ships all Tier-1
deliverables of the Option C2 industrial-release plan.

### Added

- **op3_viz web application**: six-tab Dash + Plotly 3D viewer
  (3D Viewer, Bayesian Scour, Mode D, PCE Surrogate, DLC 1.1
  Time-series, **Compliance & Actions**).
- **.op3proj project file format** (): YAML
  schema v1.0 with round-trip save/load, schema-version validation,
  and dataclass-based  /  /  / 
  /  /  /  subrecords.
- **Sample project library**: three committed samples under
   covering Gunsan 4.2 MW (private), NREL 5 MW
  on OC3 monopile (public), and IEA 15 MW on monopile (public).
- **Report generator** (): Quarto-backed DOCX +
  PDF export from any  state, with provenance footer.
- **Compliance tab wiring** (): in-UI
  buttons that dispatch the existing DNV-ST-0126 and IEC 61400-3
  conformance scripts and the DLC 1.1 overnight runner.
- **PyInstaller standalone build** (): onedir
  Windows build of the full application; does not bundle the
  private data tree, which stays behind the 
  environment variable.
- **Test coverage**: suite grew from 15 to 20 passing tests with
  the addition of .

### Changed

- Version bump  in  and
  .
- README and CITATION.cff reference the new integrated framework
  title and the  tag.

### Removed

- **Korean-language UI locale scope** was dropped from Phase 2 at
  user direction. The application is English-only for the rc1
  milestone; a separate i18n layer is not part of v1.0.

### Fixed

- IP-scrub follow-up: removed seven residual proprietary CSVs
  (, ,
  , ,
  ) that had survived the Phase A
  rename-only pass. The framework now raises a clear
   on public clones without the private data
  tree instead of falling back to synthetic values.

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

- 140 active V&V tests (all PASS)
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
