# OptumGX: The Commercial / Open Boundary

Op³ integrates one commercial solver (OptumGX) with two open-source
solvers (OpenSeesPy, OpenFAST). This document explains exactly where
the boundary lives, what the commercial solver produces, and how a
reader without an OptumGX license can still reproduce 100% of the
framework's published numerical results.

## The licenses, plainly stated

| Solver     | License                              | What this means for you                                   |
|------------|--------------------------------------|------------------------------------------------------------|
| OpenSeesPy | BSD 3-Clause (fully open)            | `pip install openseespy` and run it                       |
| OpenFAST   | Apache 2.0 (fully open)              | Download the Windows or Linux binary from NREL and run it |
| OptumGX    | Commercial, academic license available from [OptumCE](https://optumce.com/) | You need to purchase or arrange an academic license to run the OptumGX binary or the Python API |

OpenSeesPy and OpenFAST are the dominant open-source codes in their
respective niches: OpenSeesPy for 1D structural dynamics with
nonlinear soil-structure interaction, OpenFAST for aero-hydro-servo-
elastic whole-turbine simulation. They have wide research community
adoption and are the natural baseline for any offshore wind turbine
modeling work.

OptumGX is commercial software in the 3D finite-element limit
analysis niche. Its strength is rigorous upper- and lower-bound
solutions of the collapse load for arbitrary 3D foundation
geometries under general loading. Alternative open-source tools in
this niche (OpenSees in 3D mode, FEniCSx, deal.II) exist but none
matches OptumGX's limit-analysis engine for the specific problem of
a skirted suction caisson under combined V-H-M loading. This is why
OptumGX sits in the upstream position of Op³ despite the license
inconvenience.

## The workflow Op³ implements

```
┌──────────────────────┐
│ OptumGX (commercial) │   [commercial boundary]
│ ──────────────────── │   -----------------------
│ 3D FE limit analysis │
│ VHM capacity envelope│
│ contact pressures    │
│ dissipation fields   │
└──────────┬───────────┘
           │
           │  Persisted as CSV files committed to data/
           │  fem_results/ and data/integrated_database_1794.csv
           │
           ▼  ================== OPEN-SOURCE FROM HERE DOWN ==================
┌──────────────────────┐
│ OpenSeesPy (BSD)     │
│ ──────────────────── │
│ BNWF spring model    │
│ eigenvalue, pushover │
│ transient response   │
│ six-DOF impedance    │
└──────────┬───────────┘
           │
           │  Writes SubDyn input file with extracted 6×6 K_SSI
           │
           ▼
┌──────────────────────┐
│ OpenFAST (Apache 2)  │
│ ──────────────────── │
│ aero-hydro-servo-    │
│ elastic simulation   │
│ tower + rotor        │
│ full time domain     │
└──────────────────────┘
```

The commercial boundary is **entirely upstream**. Once the OptumGX
output CSVs have been persisted into the repository, everything
downstream is fully open-source.

## What is committed to the repository

### OptumGX outputs (CSV format, ready to use)

| File | Size | Purpose |
|------|-----:|---------|
| `data/integrated_database_1794.csv`       | 288 KB | 1,794 Monte Carlo samples, one row per (soil, scour) combination, with capacity and frequency prediction from a full OptumGX+OpenSeesPy run. **This is the master database for Chapters 6, 7, and 8 of the dissertation.** |
| `data/fem_results/power_law_parameters.csv` | small | Fitted power-law capacity degradation coefficients |
| `data/fem_results/Scour_Stiffness_Matrix_Master.csv` | small | Depth-resolved spring stiffness profiles |
| `data/fem_results/opensees_spring_stiffness.csv` | small | Calibrated OpenSeesPy `p_ult` and `k_ini` per depth |
| `data/fem_results/alpha_lookup_table.csv` | small | Capacity degradation factor vs scour depth |

These CSVs were generated **once** by the author running OptumGX in
batch mode over the Latin Hypercube parameter envelope described in
Chapter 6 of the dissertation (1,794 samples drawn from the Gunsan
CPT profile distribution × 9 scour levels, with ~0.4% failed runs).
The generation process is not reproducible without an OptumGX
license, but the outputs are committed directly to the repository so
the downstream analysis is fully reproducible.

### OptumGX interface scripts (read-only without a license)

| File | Purpose | Runnable without OptumGX? |
|------|---------|:-------------------------:|
| `op3/optumgx_interface/optumgx_vhm_full.py`       | Full VHM envelope generation | ❌ imports `optumgx` |
| `op3/optumgx_interface/extract_all.py`            | Batch result extractor       | ❌ imports `optumgx` |
| `op3/optumgx_interface/step4_optumgx_capacity.py` | Capacity post-processing     | ❌ imports `optumgx` |
| `op3/optumgx_interface/claude_plate_pressure.py`  | Contact pressure extraction  | ❌ imports `optumgx` |

These scripts are provided **as reference for license holders** who
wish to extend the parameter envelope beyond what is committed in
`data/`. A user without a license can still read these scripts to
understand exactly how the committed CSVs were generated, but cannot
execute them.

If you attempt to import the commercial `optumgx` Python package on
a machine without the license, the import will fail with a clear
error message and the script will terminate before doing anything.
This is intentional: the scripts do not silently degrade, they fail
loudly and tell you what you need.

## How an external researcher reproduces the framework

A researcher at NREL, DTU, or anywhere else in the offshore wind
community who wants to verify or extend Op³ does the following:

### Step 1 — Install the two open-source solvers

```bash
# OpenSeesPy
pip install openseespy numpy scipy pandas pyyaml

# OpenFAST — download the Windows or Linux binary
# from https://github.com/OpenFAST/openfast/releases/tag/v4.0.2
# and set OPENFAST_EXE to its path
export OPENFAST_EXE=/path/to/openfast_x64
```

No OptumGX license is required. No OptumGX binary is needed.

### Step 2 — Clone this repository

```bash
git clone https://github.com/ksk5429/numerical_model.git
cd numerical_model
```

All OptumGX outputs are already committed as CSVs in `data/`.

### Step 3 — Run the OpenSeesPy foundation analysis

```bash
# Fixed-base reference
python examples/01_compare_foundation_modes.py --mode fixed

# 6×6 lumped stiffness
python examples/01_compare_foundation_modes.py --mode stiffness_6x6

# Distributed BNWF springs (reads data/fem_results/opensees_spring_stiffness.csv)
python examples/01_compare_foundation_modes.py --mode distributed_bnwf

# Dissipation-weighted generalized BNWF (reads data/fem_results/power_law_parameters.csv)
python examples/01_compare_foundation_modes.py --mode dissipation_weighted
```

All four modes run without OptumGX, without internet access, and
without any large dataset download. Each mode prints the first
natural frequency and the mode shape.

### Step 4 — Run the OpenFAST coupling

```bash
# Extract the 6×6 stiffness matrix from the OpenSeesPy model
python op3/openfast_coupling/opensees_stiffness_extractor.py

# Build the SubDyn input file for OpenFAST
python op3/openfast_coupling/build_gunsan_subdyn.py --scour 0.0

# Run OpenFAST for 60 s of simulated time
$OPENFAST_EXE gunsan_4p2mw/openfast_deck/Gunsan-4p2MW.fst
```

Same — no OptumGX license required, because the stiffness matrix
was extracted from OpenSeesPy which was in turn fed by the committed
CSV files.

### Step 5 — Verify the headline numerical results

```bash
python scripts/verify_nrel_models.py   # benchmark all NREL reference models
pytest tests/                           # scientific claim assertions
```

## What an OptumGX license holder can do in addition

If you have an OptumGX academic license and the `optumgx` Python API:

1. **Extend the parameter envelope.** Add new scour depths, new soil
   profiles, or new bucket geometries to the Monte Carlo sampling
   and re-run the OptumGX batch. The scripts in
   `op3/optumgx_interface/` are the entry points.
2. **Change the soil constitutive model.** The committed database
   uses undrained Tresca clay with a linear `s_u(z) = 15 + 20z kPa`
   profile. A license holder can swap in a different constitutive
   model (Mohr-Coulomb, Hoek-Brown, user-defined) and regenerate
   the capacity envelope.
3. **Apply to a different site.** Replace `config/gunsan_site.yaml`
   with a different site's geometry and soil, rerun OptumGX, and
   the downstream OpenSeesPy and OpenFAST pipelines pick up the new
   CSVs automatically.

The repository is designed so that all three extensions touch only
the `op3/optumgx_interface/` and `data/fem_results/` directories.
Everything else is agnostic to where the stiffness and capacity data
came from.

## Why not just use OpenSees for the 3D limit analysis too?

This is the natural question every reviewer asks. The answer is a
combination of technical and practical factors:

1. **OpenSees has solid 3D FE capability** but its implementation of
   rigorous upper-bound and lower-bound limit analysis (with the
   associated nonlinear optimization solver) is incomplete. OptumGX
   uses the FELA (Finite Element Limit Analysis) formulation of
   Krabbenhoft et al., which gives true mathematical bounds on the
   collapse load, not just a collapse load estimate from a pushover
   analysis.

2. **Adaptive mesh refinement at the bucket skirt tip** is critical
   for accurate capacity predictions, and OptumGX's adaptive mesher
   is purpose-built for limit analysis. Replicating this in OpenSees
   would require substantial development effort.

3. **Practical engineering workflow.** The Gunsan project started
   with an existing OptumGX workflow from the design phase. Rebuilding
   the capacity database in a different solver was not a scientifically
   productive use of dissertation time. The decision was to accept
   the commercial-solver constraint on the upstream step and
   mitigate it by committing the outputs.

If an external user needs to avoid OptumGX entirely, the options are:

- **Use one of the committed power-law capacity functions** from
  `data/fem_results/power_law_parameters.csv`. These are published,
  have an analytical form, and can be evaluated by a free Python
  one-liner without any solver.
- **Replace OptumGX with OpenSees in 3D mode or with FEniCSx** and
  compute your own capacity database. The interface to Op³ is a CSV
  with a documented schema; any tool that produces that CSV can
  feed Op³.
- **Use published capacity power laws from the PISA research
  programme** ([@burd2020pisasand], [@byrne2020pisaclay]) which are
  validated against full-scale field tests at Cowden and Dunkirk.
  The Op³ framework accepts PISA-style inputs and produces identical
  downstream results within a small calibration tolerance.

## Summary

- The commercial boundary is at a single upstream step: OptumGX 3D
  limit analysis.
- The outputs of that step are **committed as CSVs** in `data/`.
- Everything downstream (OpenSeesPy, OpenFAST, Bayesian fusion,
  digital twin encoder) is fully open-source reproducible.
- License holders can re-run or extend the OptumGX step via the
  reference scripts in `op3/optumgx_interface/`.
- Non-license holders have three escape hatches: use the committed
  CSVs, use the PISA capacity functions, or replace OptumGX with a
  free alternative that produces the same CSV schema.

This repository is designed to make the commercial constraint as
small as possible. If you find a case where the constraint blocks
your reproduction, please open a GitHub issue and the author will
help you work around it.
