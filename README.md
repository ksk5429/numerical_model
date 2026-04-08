# Op³: OptumGX ↔ OpenSeesPy ↔ OpenFAST Integrated Numerical Modeling Framework for Offshore Wind Turbines

[![License: Apache-2.0](https://img.shields.io/badge/License-Apache_2.0-yellow.svg)](LICENSE)
[![Python 3.12](https://img.shields.io/badge/python-3.12-blue.svg)](https://www.python.org/downloads/release/python-3120/)
[![OpenFAST](https://img.shields.io/badge/OpenFAST-v5.0.0-orange.svg)](https://github.com/OpenFAST/openfast/releases/tag/v5.0.0)
[![OpenSeesPy](https://img.shields.io/badge/OpenSeesPy-3.7+-green.svg)](https://github.com/zhuminjie/OpenSeesPy)
[![V&V](https://img.shields.io/badge/V%26V-121%2F121-brightgreen.svg)](docs/DEVELOPER_NOTES.md)
[![Version](https://img.shields.io/badge/version-0.3.0-blue.svg)](CHANGELOG.md)

## v0.3.0 release highlights

- **121 / 121 active V&V tests pass** (15 modules: code verification,
  consistency, sensitivity, extended invariants, PISA, cyclic
  degradation, HSsmall, Mode D, UQ, reproducibility snapshot, ...)
- **4 / 4 calibration regression** against published references
  (Jonkman 2009, Jonkman & Musial 2010, Gaertner 2020, PhD field OMA)
- **OpenFAST v5.0.0 end-to-end** — Gunsan tripod + SoilDyn with
  Op³ PISA-derived 6×6 stiffness, 8-module coupled simulation
- **DLC 1.1 partial sweep 3 / 3 PASS** at U = {8, 12, 18} m/s
- **35 / 36 DNV-ST-0126 conformance** (1 real Gunsan 1P resonance
  finding — see developer notes)
- **End-to-end Bayesian calibration** of NREL 5 MW OC3 tower EI:
  posterior mean 1.014 ± 0.076, 5%-95% credible interval [0.888, 1.145]

See [CHANGELOG.md](CHANGELOG.md) and [docs/DEVELOPER_NOTES.md](docs/DEVELOPER_NOTES.md)
for the complete implementation journal of Track C phases 1 through 8.

---


**Op³** (pronounced "O-p-cubed") is an integrated numerical modeling
framework for offshore wind turbines that connects three industry-standard
analysis codes — **OptumGX**, **OpenSeesPy**, and **OpenFAST** — into a
single, verifiable pipeline. The framework is developed around the
Gunsan 4.2 MW tripod suction-bucket offshore wind turbine and benchmarked
against the complete NREL reference wind turbine library bundled in
this repository.

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
properties from [`op3/config/gunsan_site.yaml`](op3/config/gunsan_site.yaml).
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
[`op3/openfast_coupling/build_gunsan_subdyn.py`](op3/openfast_coupling/build_gunsan_subdyn.py).
Both scripts are driven by the single-source-of-truth YAML at
[`op3/config/gunsan_site.yaml`](op3/config/gunsan_site.yaml).

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
| **Gunsan 4.2 MW (subject under test)** | **4.2 MW** | **136 m** | **Tripod suction bucket** | [`gunsan_4p2mw/openfast_deck/`](gunsan_4p2mw/openfast_deck/) | **tested** |

## Gunsan vs NREL side-by-side

See [`validation/benchmarks/GUNSAN_VS_NREL.md`](validation/benchmarks/GUNSAN_VS_NREL.md)
for the full side-by-side comparison of rotor properties, tower
properties, structural natural frequencies, and steady-state
performance. The short version is in the table below.

| Property | NREL 5MW r-test | NREL OC3 Monopile | NREL 2.8-127 | **Gunsan 4.2 MW** |
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
│       └── gunsan_site.yaml
│
├── data/                              OptumGX persisted outputs
│   ├── integrated_database_1794.csv   master Monte Carlo database
│   ├── fem_results/                   small result CSVs
│   └── blade_data_U136.csv
│
├── gunsan_4p2mw/                      Gunsan 4.2 MW specific
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
│       ├── GUNSAN_VS_NREL.md          side-by-side comparison
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
  version= {1.0},
}
```

A Zenodo DOI will be issued from the v1.0 release.

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
Seoul National University · `ksk5429@snu.ac.kr`

Report reproduction issues via
[GitHub Issues](https://github.com/ksk5429/numerical_model/issues).
The author commits to maintaining this repository in working order
for at least three years after the dissertation defense.

## Acknowledgments

This work was funded by the Korea Electric Power Corporation (KEPCO)
under the project *"Natural frequency-based scour monitoring for
offshore wind turbine foundations"*. The framework was developed at
Seoul National University. The NREL reference wind turbine library
is maintained by the National Renewable Energy Laboratory; this
repository bundles redistributed copies under their original licenses
and gratefully acknowledges NREL's open-science commitment that made
this comparison possible.
