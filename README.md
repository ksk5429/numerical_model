# Op³: Integrated Numerical and Digital Twin Framework for Scour Assessment of Offshore Wind Turbine with Tripod Suction Bucket Foundations

[![DOI](https://zenodo.org/badge/1204628094.svg)](https://doi.org/10.5281/zenodo.19476542)
[![License: Apache-2.0](https://img.shields.io/badge/License-Apache_2.0-yellow.svg)](LICENSE)
[![Python 3.12](https://img.shields.io/badge/python-3.12-blue.svg)](https://www.python.org/downloads/release/python-3120/)
[![OpenFAST](https://img.shields.io/badge/OpenFAST-v5.0.0-orange.svg)](https://github.com/OpenFAST/openfast/releases/tag/v5.0.0)
[![OpenSeesPy](https://img.shields.io/badge/OpenSeesPy-3.7+-green.svg)](https://github.com/zhuminjie/OpenSeesPy)
[![V&V](https://img.shields.io/badge/V%26V-35%2F38_benchmarks_(92%25)-brightgreen.svg)](validation/cross_validations/VV_REPORT.md)
[![CI](https://github.com/ksk5429/numerical_model/actions/workflows/ci.yml/badge.svg)](https://github.com/ksk5429/numerical_model/actions/workflows/ci.yml)
[![Tests](https://img.shields.io/badge/tests-140_passing-brightgreen.svg)](tests/)
[![Version](https://img.shields.io/badge/version-1.0.0--rc2-blue.svg)](CHANGELOG.md)
[![PyPI](https://img.shields.io/pypi/v/op3-framework.svg)](https://pypi.org/project/op3-framework/)
[![Documentation](https://img.shields.io/badge/docs-sphinx-blue.svg)](docs/sphinx/)

**Op³** (pronounced "O-p-three") is an integrated numerical and digital twin
framework for scour assessment of offshore wind turbine tripod suction
bucket foundations. It
bridges three otherwise-disconnected codes — **OptumGX** (3D FE limit
analysis, commercial), **OpenSeesPy** (structural dynamics, BSD-3-Clause),
and **OpenFAST v5** (aero-hydro-servo-elastic, Apache 2.0) — into a single
V&V'd Python pipeline.

Developed as part of a PhD dissertation at Seoul National University (2026),
the framework combines three-dimensional geotechnical limit analysis
(OptumGX), one-dimensional structural dynamics (OpenSeesPy), and aero-hydro-
servo-elastic simulation (OpenFAST) into a single open-source pipeline with
a Bayesian decision layer, a digital twin encoder, and an eight-tab web
application for field deployment.

**Author:** Kyeong Sun Kim · Department of Civil and Environmental
Engineering, Seoul National University · 2026

---

## 30-second introduction

```python
from op3 import build_foundation, compose_tower_model
from op3.foundations import foundation_from_pisa
from op3.standards.pisa import SoilState

# 1. Build a PISA-derived foundation
profile = [
    SoilState(0.0,  5.0e7, 35, "sand"),
    SoilState(15.0, 1.0e8, 35, "sand"),
    SoilState(36.0, 1.5e8, 36, "sand"),
]
foundation = foundation_from_pisa(diameter_m=6.0, embed_length_m=36.0, soil_profile=profile)

# 2. Compose a tower model
model = compose_tower_model(
    rotor="nrel_5mw_baseline",
    tower="nrel_5mw_oc3_tower",
    foundation=foundation,
)

# 3. Run analyses
freqs = model.eigen(n_modes=3)
print(f"f1 = {freqs[0]:.4f} Hz")              # fixed: 0.3158, PISA: 0.3157
K_6x6 = model.extract_6x6_stiffness()          # condense to head stiffness
pushover = model.pushover(target_disp_m=0.5)   # static pushover
transient = model.transient(duration_s=10.0)   # free vibration
```

```bash
# End-to-end OpenFAST v5 coupled simulation
python scripts/run_openfast.py site_a --tmax 5
python scripts/run_dlc11_partial.py --tmax 600 --speeds 8 12 18

# Standards conformance audit
python scripts/dnv_st_0126_conformance.py --all
python scripts/iec_61400_3_conformance.py --all

# Full V&V suite
python scripts/release_validation_report.py   # 18/19 PASS in ~42 s
```

## What you get

| Capability | Op³ | SACS | PLAXIS | OpenSeesPy | OpenFAST |
|---|:-:|:-:|:-:|:-:|:-:|
| Four foundation modes (Fixed / 6x6 / BNWF / Dissipation-weighted) | ✅ | partial | partial | manual | ❌ |
| PISA (Burd 2020 / Byrne 2020) with depth functions | ✅ | ❌ | commercial | ❌ | ❌ |
| Cyclic Hardin-Drnevich layered on PISA | ✅ | ❌ | ❌ | ❌ | ❌ |
| DNV / ISO / API / OWA / PISA / HSsmall standards | 6 | proprietary | 1-2 | ❌ | ❌ |
| Mode D dissipation-weighted BNWF (novel) | ✅ | ❌ | ❌ | ❌ | ❌ |
| Direct Op³ → SoilDyn export | ✅ | ❌ | ❌ | ❌ | native |
| Monte Carlo soil propagation | ✅ | ❌ | manual | manual | ❌ |
| Hermite polynomial chaos expansion | ✅ | ❌ | ❌ | manual | ❌ |
| Grid Bayesian calibration | ✅ | ❌ | ❌ | manual | ❌ |
| V&V test suite | **140** | proprietary | proprietary | user-built | ~200 r-test |
| License | Apache-2.0 | commercial | commercial | BSD-3 | Apache-2.0 |
| Python-native | ✅ | ❌ | ❌ | wrapper | wrapper |

## v1.0.0-rc1 release highlights

- **35 / 38 cross-validation benchmarks verified (92%)** against 20+
  published sources (Fu & Bienen 2017, Vulpe 2015, Doherty 2005,
  Houlsby 2005, Jalbi 2018, Gazetas 2018, and 14 more)
- **140 unit tests pass** across 15 modules (code verification,
  consistency, sensitivity, extended invariants, PISA, cyclic
  degradation, HSsmall, Mode D, UQ, reproducibility snapshot,
  framework integration, ...)
- **4 / 4 calibration regression** against published references
  with all four examples within 4% of the most stringent
  (NREL 5 MW OC3 at **-0.4%** vs Jonkman & Musial 2010)
- **OpenFAST v5.0.0 end-to-end** on SiteA tripod + SoilDyn with
  Op³ PISA-derived 6×6 stiffness, 8-module coupled simulation
- **DLC 1.1 partial sweep** at U = {8, 12, 18} m/s — 3 / 3 PASS;
  full 12-speed × 600 s run scaled overnight
- **35 / 36 DNV-ST-0126 conformance** (single failure is the real
  SiteA 1P resonance finding, not a bug)
- **OC6 Phase II benchmark** (Bergua 2021 NREL/TP-5000-79989):
  Op³ K_zz matches to **1.3%**, f1_clamped to **0.5%**
- **PISA field-test cross-validation** (McAdam 2020 + Byrne 2020)
  with depth-function + eccentric-load-compliance corrections
  reducing prior-release errors by 10–30× on short rigid piles
- **End-to-end Bayesian calibration** of NREL 5 MW OC3 tower EI:
  posterior mean **1.014 ± 0.076**, 5%-95% credible interval
  [0.888, 1.145]
- **Sphinx documentation** (~5000 lines across 9 RST pages + 6 tutorial
  notebooks), ReadTheDocs-ready and GitHub Pages-deployable

## Cross-Validation Against Published Benchmarks

Op3 has been cross-validated against **39 independent benchmarks** from
20+ published sources. **35 of 38 in-scope benchmarks verified (92%).**

| Category | Benchmarks | Error range | Sources |
|---|---|---|---|
| Eigenvalue (f1) | #1--5 | 1.2--13% | Jonkman 2010, Gaertner 2020, Kim 2025 |
| Bearing capacity (OptumGX FELA) | #14--15 | **0.8--7.8%** | Fu & Bienen 2017, Vulpe 2015 |
| Foundation stiffness | #16--17, #20 | 0.1--26% | Jalbi 2018, Gazetas 2018, Doherty 2005 |
| Field trial | #19 | -21% | Houlsby 2005 (Bothkennar) |
| Scour sensitivity | #10--11 | within published ranges | Zaaijer 2006, Prendergast 2015 |
| Design compliance | #13 | 0% | DNV-ST-0126 (2021) |
| PISA clay stiffness | #6 | 16--32% | Burd et al. 2020 |
| VH envelope | #8 | -7.7% | Houlsby & Byrne / Vulpe 2015 |
| p_ult(z) profile | #21 | consistent | OptumGX plate extraction |
| Centrifuge yield moment | #22 | **-0.7%** | DJ Kim et al. 2014 |
| Full-scale tripod f1 | #24 | -0.2% | Seo et al. 2020 |
| Walney 1 monopile f1 | #25 | -2.1% | Arany et al. 2015 |
| Suction bucket scour sensitivity | #26 | within range | Cheng et al. 2024 |
| f_meas/f_design ratio | #27 | +0.3% | Kallehave et al. 2015 |
| Cyclic rotation (N=100, N=1M) | #28 | 3.7--4.3% | Jeong et al. 2021 |
| OC4 jacket f1 (fixed-base) | #29 | +1.9% | Popko et al. 2012 |

Key results:
- **NcV = 6.006** (ref 5.94, +1.1%) -- textbook bearing capacity match
- **NcM = 1.468** (ref 1.48, -0.8%) -- near-exact moment capacity
- **KR/(R3G) = 17.28** (ref 16.77, +3.1%) -- stiffness vs Doherty/OxCaisson
- **Kr = 177 MNm/rad** (measured 225, -21%) -- first field validation

Full report: [validation/cross_validations/VV_REPORT.md](validation/cross_validations/VV_REPORT.md)

Reproduce all results:
```bash
python validation/cross_validations/run_all_cross_validations.py
```

See [CHANGELOG.md](CHANGELOG.md) for the full release history and
[docs/DEVELOPER_NOTES.md](docs/DEVELOPER_NOTES.md) for the
implementation journal of Track C phases 1 through 8.

## Documentation

Comprehensive package, all free, all on GitHub:

| Page | Content |
|---|---|
| [Environment setup](docs/sphinx/environment.rst) | Clone, install, OpenFAST bootstrap, r-test bootstrap |
| [User manual](docs/sphinx/user_manual.rst) | Worked examples: every foundation mode, every standard, UQ tools, OpenFAST coupling |
| [Technical reference](docs/sphinx/technical_reference.rst) | Units, coordinates, DOFs, PISA math, Hermite PCE, Hardin-Drnevich, Rayleigh cantilever |
| [Scientific report](docs/sphinx/scientific_report.rst) | Narrative, distinctive contributions, OC6 + PISA validation findings, limitations |
| [Troubleshooting / FAQ](docs/sphinx/troubleshooting.rst) | ~30 common issues across install / OpenSees / OpenFAST / PISA / UQ / V&V |
| [Contributing guide](docs/sphinx/contributing.rst) | V&V-or-it-didn't-happen rule, commit discipline, release process |
| [Developer notes](docs/DEVELOPER_NOTES.md) | Full implementation journal, all 8 Track C phases with lessons learned |
| [Mode D formulation](docs/MODE_D_DISSIPATION_WEIGHTED.md) | Novel dissipation-weighted BNWF paper-draft |
| [Tutorials](docs/tutorials/) | 6 Jupyter notebooks: quickstart, foundation modes, UQ, calibration, SoilDyn, DLC sweeps |

Documentation is configured for free hosting on
[Read the Docs](https://readthedocs.org) via [`.readthedocs.yaml`](.readthedocs.yaml)
and for GitHub Pages deployment via
[`.github/workflows/docs-deploy.yml`](.github/workflows/docs-deploy.yml).

Once the repo is linked to Read the Docs, the full documentation
will be rendered at `https://op3-framework.readthedocs.io` with
automatic rebuilds on every push. Alternatively the GitHub Actions
workflow deploys to `https://ksk5429.github.io/numerical_model/`.

## Quick start

```bash
# Clone and install
git clone https://github.com/ksk5429/numerical_model.git
cd numerical_model
pip install -e ".[test,docs]"

# Bootstrap OpenFAST v5.0.0 binary
mkdir -p tools/openfast
curl -L -o tools/openfast/OpenFAST.exe \
  https://github.com/OpenFAST/openfast/releases/download/v5.0.0/OpenFAST.exe

# Bootstrap r-test
mkdir -p tools/r-test_v5 && cd tools/r-test_v5
git clone --depth=1 --branch v5.0.0 https://github.com/OpenFAST/r-test.git
cd ../..

# Run the full V&V suite
PYTHONUTF8=1 python scripts/release_validation_report.py
```

Expected: **18/19 PASS, 0 mandatory FAIL, ~42 s total wall time**.

See the [environment setup guide](docs/sphinx/environment.rst) for
troubleshooting and platform-specific notes.

## Repository layout

```
op3/                     the Python package
  foundations.py         Foundation dataclass + factory
  composer.py            TowerModel: eigen / pushover / transient
  opensees_foundations/  OpenSeesPy builder + ElastoDyn tower loader
  standards/             DNV / ISO / API / OWA / PISA / HSsmall / cyclic
  openfast_coupling/     Op^3 -> OpenFAST SoilDyn bridge
  uq/                    Propagation / PCE / Bayesian
  sacs_interface/        SACS jacket deck parser

tests/                   140 active V&V tests
scripts/                 Runners, audits, regressions, release tooling
examples/                11 turbine TowerModel build.py files
docs/                    Sphinx + tutorials + Mode D notes + developer notes
paper/                   JOSS-format paper + BibTeX
.github/workflows/       CI, docs deploy, release validation
site_a_ref4mw/            SiteA 4 MW class OWT decks (v4 and v5)
nrel_reference/          NREL + IEA reference turbines bundled for V&V
validation/benchmarks/   Test output JSON artifacts
tools/                   OpenFAST binary + r-test clone (gitignored)
```

## Citation

If you use Op³ in academic work, please cite both the software and the
dissertation. A [`CITATION.cff`](CITATION.cff) is provided for automatic
reference management.

```bibtex
@software{op3_2026,
  title  = {Op^3: OptumGX-OpenSeesPy-OpenFAST Integration Framework},
  author = {Kim, Kyeong Sun},
  year   = {2026},
  version = {1.0.0-rc1},
  url    = {https://github.com/ksk5429/numerical_model}
}
```

---

### Historical introduction (preserved from v0.1)

The original Op³ framework was developed around the

**Author:** Kyeong Sun Kim · Department of Civil and Environmental
Engineering, Seoul National University · 2026

---

## Important: license boundary between the three solvers

This framework sits at the boundary of two open-source solvers and one
commercial solver. Understanding this boundary is essential to
reproduce any result in this repository.

| Solver     | License                                    | Runnable by anyone? |
|------------|--------------------------------------------|:-------------------:|
| **OpenSeesPy** | [BSD 3-Clause](https://opensource.org/license/bsd-3-clause) (fully open) | ✅ yes — `pip install openseespy` |
| **OpenFAST**   | [Apache 2.0](https://github.com/OpenFAST/openfast/blob/main/LICENSE) (fully open) | ✅ yes — download v4.0.2 binary from NREL |
| **OptumGX**    | **Commercial** — [academic license required](https://optumce.com/) | ❌ only license holders |

### How this repository handles the commercial-solver constraint

OptumGX is used **once, upstream**, by the author to generate the
three-dimensional finite-element limit-analysis outputs (bearing
capacity envelopes, depth-resolved contact pressure fields, plastic
dissipation profiles). The outputs are then **persisted as CSV files
and committed to this repository under [`data/fem_results/`](data/fem_results/)
and [`data/integrated_database_1794.csv`](data/integrated_database_1794.csv)**.
A third party who does not have OptumGX can still:

1. ✅ Read the persisted OptumGX output CSVs directly
2. ✅ Run the complete OpenSeesPy foundation analysis pipeline
3. ✅ Run the complete OpenFAST coupling pipeline
4. ✅ Reproduce every headline numerical result in the dissertation
5. ❌ *Not* re-run the OptumGX simulations from scratch
6. ❌ *Not* change OptumGX input parameters (only the pre-computed
   parameter envelope is available)

The OptumGX interface scripts in [`op3/optumgx_interface/`](op3/optumgx_interface/)
are provided as reference for license holders who wish to extend the
parameter envelope. They are not runnable without an OptumGX license
and the corresponding Python API. The scripts import from
`optumgx` (the commercial API package); attempts to run them on a
machine without the license will fail at import time with a clear
error message.

**The overwhelming majority of users only need the open-source path**
(OpenSeesPy + OpenFAST), and for those users the OptumGX constraint is
invisible because the OptumGX outputs have been pre-computed.

---

## What Op³ actually does

```
 ┌──────────────┐     ┌──────────────┐     ┌──────────────┐
 │   OptumGX    │     │  OpenSeesPy  │     │   OpenFAST   │
 │ 3D FE limit  │ ──▶ │  1D BNWF     │ ──▶ │  aero-hydro- │
 │   analysis   │     │ structural   │     │ servo-elastic│
 │ (commercial) │     │  dynamics    │     │   rotor-tower│
 └──────────────┘     └──────────────┘     └──────────────┘
        │                    │                    │
        ▼                    ▼                    ▼
  capacity envelopes   eigenmodes, pushover   time-domain
  contact pressures    transient response     response under
  dissipation fields   six-DOF impedance      wind+wave loading
        │                    │                    │
        └────── CSV ─────────┴─────── CSV ────────┘
                            │
                            ▼
                   integrated_database_1794.csv
                   (1,794 Monte Carlo samples)
```

Two boundary crossings need to be made explicit because they are
where most of the engineering work of Op³ actually lives:

1. **OptumGX → OpenSeesPy.** How does a 3D finite-element capacity
   analysis translate into 1D beam-on-nonlinear-Winkler-foundation
   spring parameters? The framework offers **four foundation modules**
   described in the next section; each one represents a different
   level of fidelity and computational cost.

2. **OpenSeesPy → OpenFAST.** How does the structural dynamic response
   of the foundation enter the rotor-nacelle-tower-substructure
   coupled simulation? The framework extracts a **6×6 stiffness
   matrix** (or a frequency-dependent impedance function) from the
   OpenSeesPy model and injects it into the OpenFAST **SubDyn** module
   as a substructure interface condition.

## The OpenSeesPy foundation module selector

Op³ exposes **four** ways to represent the foundation in OpenSeesPy,
arranged in increasing order of fidelity and computational cost.
The choice is made at runtime via a single configuration flag, so the
rest of the OpenSeesPy tower model remains identical across all four
modes — only the foundation boundary condition changes.

| Mode | Name                      | Fidelity | Runtime | Use case |
|:----:|---------------------------|:--------:|:-------:|----------|
|  A   | **Fixed base**            | Lowest   | Fastest | Upper-bound reference, sanity check, rapid design iteration |
|  B   | **6×6 lumped stiffness**  | Low      | Fast    | Frequency-domain SSI for OpenFAST SubDyn; matches the PISA paradigm |
|  C   | **Distributed BNWF springs** | Medium | Medium  | Depth-resolved stiffness; captures scour progression at each depth |
|  D   | **Dissipation-weighted generalized BNWF** | High | Slow | Full energy-consistent coupling with OptumGX plastic dissipation field |

All four modes share the same tower, rotor, and nacelle inertia
properties from [`op3/config/site_a.yaml`](op3/config/site_a.yaml).
Only the foundation representation changes, which makes it trivial to
compare the effect of foundation modeling choice on the predicted
natural frequency, mode shape, or transient response.

### Mode A — Fixed base

```python
from op3.opensees_foundations import build_tower_model
model = build_tower_model(foundation_mode='fixed')
model.eigen(1)
```

Fixes the base of the tower at the mudline. No soil contribution,
no scour sensitivity. The first natural frequency is the upper bound
against which all other modes are compared. Useful for regression
testing and as a reference point.

### Mode B — 6×6 lumped stiffness matrix

```python
model = build_tower_model(
    foundation_mode='stiffness_6x6',
    stiffness_matrix='data/fem_results/K_6x6_baseline.csv',
)
```

Represents the foundation as a single six-degree-of-freedom linear
spring at the tower base node. The matrix encodes the translational,
rotational, and translational-rotational coupling stiffnesses. This
is the representation that the OpenFAST SubDyn interface accepts
directly, and it is the representation the PISA research programme
uses for rigid bucket-like foundations
[@burd2020pisasand; @byrne2020pisaclay]. Scour progression is modeled
by loading a different 6×6 matrix computed for that scour level.

### Mode C — Distributed beam-on-nonlinear-Winkler-foundation springs

```python
model = build_tower_model(
    foundation_mode='distributed_bnwf',
    spring_profile='data/fem_results/opensees_spring_stiffness.csv',
    scour_depth=1.5,
)
```

Represents the foundation as a series of nonlinear lateral (p-y)
and vertical (t-z) springs distributed along the bucket skirt depth.
The spring stiffnesses and capacities are calibrated from the OptumGX
contact-pressure database, then scaled by a depth-dependent
stress-correction factor that accounts for overburden loss as the
scoured mudline moves downward. This is the Chapter 6 core of the
dissertation and the representation against which the other modes
are validated.

### Mode D — Dissipation-weighted generalized BNWF (highest fidelity)

```python
model = build_tower_model(
    foundation_mode='dissipation_weighted',
    ogx_dissipation='data/fem_results/dissipation_profile.csv',
    ogx_capacity='data/fem_results/power_law_parameters.csv',
    scour_depth=1.5,
)
```

Extends Mode C with a depth-dependent participation factor derived
from the OptumGX plastic dissipation field at collapse. This is the
generalization of the Vesic cavity expansion theory described in
Appendix A of the dissertation: the uniform plastic-zone assumption
of classical cavity expansion is replaced by a spatially varying
weight function. The stiffness, ultimate resistance, and
half-displacement are all derived from a single energy-consistent
framework with `su` canceling exactly in the `y50` parameter. This
is the recommended mode for research use.

### Comparing modes on the same tower

```python
from op3.opensees_foundations import compare_foundation_modes
results = compare_foundation_modes(
    modes=['fixed', 'stiffness_6x6', 'distributed_bnwf', 'dissipation_weighted'],
    scour_levels=[0.0, 0.5, 1.0, 1.5, 2.0],
)
print(results)  # DataFrame indexed by (mode, scour) with first_freq_Hz column
```

See [`examples/compare_foundation_modes.py`](examples/compare_foundation_modes.py)
for a full script that reproduces Table 6.X of the dissertation.

## The OpenSeesPy → OpenFAST coupling

The coupling is two-way in principle but one-way in practice: the
foundation stiffness from OpenSeesPy is extracted as a 6×6 linear
matrix at the mudline (or as a frequency-dependent impedance
function) and written to a SubDyn input file. OpenFAST then runs the
full aero-hydro-servo-elastic simulation with the foundation fully
characterized by that matrix. This is computationally efficient
because OpenFAST does not need to re-compute the foundation response
at each time step.

```
OpenSeesPy                         OpenFAST
┌────────────┐                     ┌─────────────┐
│ BNWF model │  eigenvalue +       │  SubDyn     │
│  (Mode C   │  static condensation│  substruct  │
│   or D)    │ ───────────────────▶│  interface  │
│            │     6x6 K_SSI       │             │
└────────────┘                     └─────────────┘
                                          │
                                          ▼
                              full aero-hydro-servo-elastic
                              tower + rotor simulation under
                              wind and wave loading
```

The extraction is handled by
[`op3/openfast_coupling/opensees_stiffness_extractor.py`](op3/openfast_coupling/opensees_stiffness_extractor.py).
The SubDyn input file is generated by
[`op3/openfast_coupling/build_site_a_subdyn.py`](op3/openfast_coupling/build_site_a_subdyn.py).
Both scripts are driven by the single-source-of-truth YAML at
[`op3/config/site_a.yaml`](op3/config/site_a.yaml).

## NREL reference library bundled in this repository

Op³ is benchmarked against the full NREL reference wind turbine
library. For **every** NREL model listed below, the OpenFAST input
deck is bundled in this repository and was verified to exist and be
structurally complete at the time of commit. See
[`validation/benchmarks/NREL_BENCHMARK.md`](validation/benchmarks/NREL_BENCHMARK.md)
for the per-model verification status including which modules are
enabled and which r-test assertions pass.

| Model | Power | Rotor | Foundation | Path | Status |
|-------|------:|------:|------------|------|:------:|
| NREL 5MW Baseline (fixed base)       | 5.0 MW   | 126 m | Fixed base     | [`nrel_reference/openfast_rtest/5MW_Baseline/`](nrel_reference/openfast_rtest/5MW_Baseline/) | ✅ |
| NREL 5MW OC3 Monopile + WavesIrr     | 5.0 MW   | 126 m | Monopile        | [`nrel_reference/openfast_rtest/5MW_OC3Mnpl_DLL_WTurb_WavesIrr/`](nrel_reference/openfast_rtest/5MW_OC3Mnpl_DLL_WTurb_WavesIrr/) | ✅ |
| NREL 1.72-103                        | 1.72 MW  | 103 m | Land-based monopile | [`nrel_reference/iea_scaled/NREL-1.72-103/`](nrel_reference/iea_scaled/NREL-1.72-103/) | ✅ |
| NREL 1.79-100                        | 1.79 MW  | 100 m | Land-based monopile | [`nrel_reference/iea_scaled/NREL-1.79-100/`](nrel_reference/iea_scaled/NREL-1.79-100/) | ✅ |
| NREL 2.3-116                         | 2.3 MW   | 116 m | Land-based monopile | [`nrel_reference/iea_scaled/NREL-2.3-116/`](nrel_reference/iea_scaled/NREL-2.3-116/) | ✅ |
| NREL 2.8-127 (HH 87 m)               | 2.8 MW   | 127 m | Land-based monopile | [`nrel_reference/iea_scaled/NREL-2.8-127/OpenFAST_hh87/`](nrel_reference/iea_scaled/NREL-2.8-127/OpenFAST_hh87/) | ✅ |
| NREL 2.8-127 (HH 120 m)              | 2.8 MW   | 127 m | Land-based monopile | [`nrel_reference/iea_scaled/NREL-2.8-127/OpenFAST_hh120/`](nrel_reference/iea_scaled/NREL-2.8-127/OpenFAST_hh120/) | ✅ |
| Vestas V27 (historical baseline)     | 225 kW   |  27 m | Land-based      | [`nrel_reference/vestas/V27/`](nrel_reference/vestas/V27/) | ✅ |
| **SiteA 4 MW class (subject under test)** | **4 MW class** | **136 m** | **Tripod suction bucket** | [`site_a_ref4mw/openfast_deck/`](site_a_ref4mw/openfast_deck/) | **tested** |

## SiteA vs NREL side-by-side

See [`validation/benchmarks/SITE_A_VS_NREL.md`](validation/benchmarks/SITE_A_VS_NREL.md)
for the full side-by-side comparison of rotor properties, tower
properties, structural natural frequencies, and steady-state
performance. The short version is in the table below.

| Property | NREL 5MW r-test | NREL OC3 Monopile | NREL 2.8-127 | **SiteA 4 MW class** |
|---|:---:|:---:|:---:|:---:|
| Rated power                  | 5.00 MW | 5.00 MW | 2.80 MW | **4.20 MW** |
| Rotor diameter               | 126.0 m | 126.0 m | 127.0 m | **136.0 m** |
| Hub height                   |  90.0 m |  90.0 m |  87.6 m | **96.3 m**  |
| Rated rotor speed            | 12.1 rpm | 12.1 rpm | 10.6 rpm | **13.2 rpm** |
| First FA natural freq (Hz)   | 0.324   | 0.276   | 0.290   | **0.244**   |
| Foundation                   | Fixed   | Monopile| Fixed   | **Tripod suction bucket** |
| SSI coupling                 | none    | none    | none    | **OpenSees BNWF → SubDyn** |
| Scour parameterization       | none    | none    | none    | **9 levels, 0-4 m**        |

## Quick start

```bash
# 1. Clone
git clone https://github.com/ksk5429/numerical_model.git
cd numerical_model

# 2. Install Python dependencies (open-source only, no OptumGX needed)
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# 3. Run eigenvalue analysis in all four foundation modes
python examples/01_compare_foundation_modes.py

# 4. Run a scour parametric sweep
python examples/02_scour_parametric.py

# 5. Generate a SubDyn file for OpenFAST
python examples/03_build_subdyn_from_opensees.py

# 6. Run the full OpenFAST simulation (requires OpenFAST v4.0.2 binary)
# Download from https://github.com/OpenFAST/openfast/releases
export OPENFAST_EXE=/path/to/openfast_x64
python examples/04_openfast_single_run.py
```

## Repository layout

```
numerical_model/
├── README.md                          this file
├── LICENSE                            MIT
├── CITATION.cff                       citation metadata
├── requirements.txt                   pip dependencies
│
├── op3/                               main Op³ framework
│   ├── optumgx_interface/             OptumGX scripts (academic license)
│   ├── opensees_foundations/          four foundation modules + BNWF
│   ├── openfast_coupling/             OpenSees ↔ SubDyn bridge
│   ├── integration/                   OptumGX outputs → OpenSees springs
│   └── config/                        single source of truth
│       └── site_a.yaml
│
├── data/                              OptumGX persisted outputs
│   ├── integrated_database_1794.csv   master Monte Carlo database
│   ├── fem_results/                   small result CSVs
│   └── blade_data_RT1.csv
│
├── site_a_ref4mw/                      SiteA 4 MW class specific
│   ├── openfast_deck/                 OpenFAST v4 input files
│   └── opensees_deck/                 OpenSeesPy tower + foundation
│
├── nrel_reference/                    NREL benchmark library
│   ├── openfast_rtest/                NREL 5MW baseline + OC3 monopile
│   ├── iea_scaled/                    NREL 1.72 / 1.79 / 2.3 / 2.8 MW
│   └── vestas/                        V27 historical baseline
│
├── validation/
│   └── benchmarks/
│       ├── NREL_BENCHMARK.md          per-model verification status
│       ├── SITE_A_VS_NREL.md          side-by-side comparison
│       └── FOUNDATION_MODE_STUDY.md   four-mode cross-validation
│
├── examples/                          turnkey runnable scripts
├── tests/                             pytest assertions
└── docs/                              extended documentation
    ├── FRAMEWORK.md                   architecture + philosophy
    ├── OPTUMGX_BOUNDARY.md            commercial/open boundary
    ├── THEORY.md                      cavity expansion generalization
    └── USAGE.md                       per-module usage guide
```

## Citation

```bibtex
@phdthesis{kim2026dissertation,
  author = {Kim, Kyeong Sun},
  title  = {Digital Twin Encoder for Prescriptive Maintenance of
            Offshore Wind Turbine Foundations},
  school = {Seoul National University},
  year   = {2026},
  type   = {Ph.D. Dissertation},
}

@software{kim2026op3,
  author = {Kim, Kyeong Sun},
  title  = {Op³: OptumGX-OpenSeesPy-OpenFAST integrated numerical
            modeling framework for offshore wind turbines},
  year   = {2026},
  url    = {https://github.com/ksk5429/numerical_model},
  version= {0.3.2},
  doi    = {10.5281/zenodo.19476542},
}
```

### Zenodo DOI

[![DOI](https://zenodo.org/badge/1204628094.svg)](https://doi.org/10.5281/zenodo.19476542)

Op³ is archived on Zenodo for every tagged GitHub release via the
[GitHub-Zenodo integration](https://docs.github.com/en/repositories/archiving-a-github-repository/referencing-and-citing-content).
The metadata Zenodo uses is in [`.zenodo.json`](.zenodo.json) and
[`CITATION.cff`](CITATION.cff).

**Concept DOI** (always points at the latest release):
[`10.5281/zenodo.19476542`](https://doi.org/10.5281/zenodo.19476542)

Current releases:

- **v0.3.2** (2026-04-08) — Track C industry-grade, see
  [CHANGELOG.md](CHANGELOG.md). Each subsequent tag produces an
  independent version-specific DOI underneath the concept DOI above.
- **v0.3.1** (2026-04-08) — Real Bergua / McAdam / Byrne references
- **v0.3.0** (2026-04-08) — Track C initial release

Cite the **concept DOI** for general reference and the **version-
specific DOI** (visible on the Zenodo record landing page) for
reproducibility-critical work.

## License

**Code in this repository** is released under the [MIT License](LICENSE).

**NREL reference models** bundled in [`nrel_reference/`](nrel_reference/)
are redistributed under their original NREL / Apache 2.0 / public
domain licenses. See each subdirectory's README for specifics. The
NREL 5MW Baseline and OC3 monopile decks are from the OpenFAST r-test
suite (Apache 2.0). The IEA-scaled decks are from the NREL Reference
Wind Turbines repository (CC BY).

**OpenSeesPy** and **OpenFAST** are separate open-source projects
with their own licenses ([BSD 3-Clause](https://github.com/zhuminjie/OpenSeesPy/blob/master/LICENSE)
and [Apache 2.0](https://github.com/OpenFAST/openfast/blob/main/LICENSE)
respectively). This repository does not redistribute their source code.

**OptumGX** is commercial software; an academic license is required
for the `optumgx` Python API imported by scripts in
[`op3/optumgx_interface/`](op3/optumgx_interface/). This repository
does not redistribute OptumGX and contains no OptumGX binary artifacts.

## Author and contact

Kyeong Sun Kim · Department of Civil and Environmental Engineering,
Seoul National University · `kyeongsunkim@snu.ac.kr`

Report reproduction issues via
[GitHub Issues](https://github.com/ksk5429/numerical_model/issues).
The author commits to maintaining this repository in working order
for at least three years after the dissertation defense.

## Acknowledgments

This work was funded by the Korea Electric Power Corporation (KEPCO)
under the project *"Natural frequency-based scour monitoring for
offshore wind turbine foundations"*. The framework was developed at
Seoul National University.

The NREL reference wind turbine library is maintained by the
National Renewable Energy Laboratory; this repository bundles
redistributed copies under their original licenses and gratefully
acknowledges NREL's open-science commitment that made this
comparison possible.

### Field case study data

The 4 MW-class offshore wind turbine used for the site-specific
validation in Chapters 4–8 of the associated dissertation is the
Gunsan Offshore Demonstration Wind Farm unit operated by KEPCO Research
Institute (KEPRI) with foundation and support-structure design by
Hyundai E&C, Mirae & Company (MMB), and nacelle/rotor hardware from
Unison Co., Ltd. (UNISON U136, 4.2 MW, 136 m rotor diameter, 95 m hub
height, three-bucket suction caisson tripod). Structural drawings,
BOM, and geotechnical CPT/OMA data were provided by KEPRI/MMB/Unison
for academic use under the KEPCO research agreement.

Specific proprietary numerical values (tower segment schedule, bucket
OD/skirt length/centre-to-centre spacing, nacelle mass, site
coordinates, SubDyn 6x6 K matrix) are **not redistributed** in this
public repository; the framework code loads them at runtime from a
private data tree via ``op3.data_sources`` (``OP3_PHD_ROOT`` /
``OP3_TOWER_SEGMENTS_CSV``). The framework itself (foundation modes
A/B/C/D, the PISA/Hardin-Drnevich/HSsmall implementations, the Mode D
dissipation-weighting formulation, the OpenFAST coupling, and the
OC6/PISA benchmarks) is fully reproducible with the shipped NREL
5 MW reference turbine for users without access to the KEPCO data.

Please cite the dissertation and the Zenodo DOI when using this
framework; if a publication makes use of the Gunsan case study
outputs, please additionally acknowledge KEPCO Research Institute,
MMB, and Unison Co., Ltd.

### Citations for bundled references

 * NREL reference wind turbines -- NREL/TP-500-38060 (5 MW),
   NREL/TP-5000-75698 (IEA 15 MW)
 * OC6 Phase II benchmark -- Bergua et al., NREL/TP-5000-79989 (2021)
 * PISA design framework -- Burd et al., 2020; Byrne et al., 2020
 * HSsmall constitutive model -- Benz, 2007
