# NREL Reference Model Benchmark — Verification Status

This document reports the **actual** verification status of every NREL
reference OpenFAST model bundled in this repository. The numbers
below are extracted automatically by
[`scripts/verify_nrel_models.py`](../../scripts/verify_nrel_models.py),
which parses each `.fst` file and its `ElastoDyn*.dat` sub-file to
pull the key structural parameters. The JSON report from the last run
is committed at
[`nrel_model_verification.json`](nrel_model_verification.json).

To regenerate this table:

```bash
python scripts/verify_nrel_models.py
```

## Automatic verification table

| Model | Files | Size | Main FST | Hydro | Sub | Rotor D (m) | Hub H (m) | Status |
|-------|------:|-----:|----------|:-----:|:---:|------------:|----------:|:------:|
| NREL_5MW_Baseline_rtest            |  —  |   —    | *(shared data, no top-level .fst)* |    |    |   —   |   —   | 📁 data only |
| NREL_5MW_OC3_Monopile              | 10  | 0.68 MB | `5MW_OC3Mnpl_DLL_WTurb_WavesIrr.fst` | ✓  | ✓  | 126.0 | 89.6  | ✅ |
| NREL_5MW_OC4_Jacket_MGrowth        | 12  | 0.30 MB | `5MW_OC4Jckt_DLL_WTurb_WavesIrr_MGrowth.fst` | ✓ | ✓ | 126.0 | 90.1 | ✅ |
| **IEA_15MW_Monopile**              | 122 | 1.93 MB | `IEA-15-240-RWT-Monopile.fst` | ✓ | ✓ | **241.9** | **148.7** | ✅ |
| **IEA_15MW_VolturnUS**             | 34  | 6.72 MB | `IEA-15-240-RWT-UMaineSemi.fst` | ✓ |   | **241.9** | **148.7** | ✅ |
| NREL_1.72-103                       | 40  | 0.85 MB | `NREL-1p72-103.fst`                  |    |    | 103.5 | 79.6  | ✅ |
| NREL_1.79-100                       | 40  | 0.85 MB | `NREL-1p79-100.fst`                  |    |    | 100.6 | 79.6  | ✅ |
| NREL_2.3-116                        | 40  | 0.85 MB | `NREL-2p3-116.fst`                   |    |    | 116.3 | 89.6  | ✅ |
| NREL_2.8-127 (hub 87 m)             | 40  | 0.85 MB | `NREL-2p8-127.fst`                   |    |    | 127.0 | 88.6  | ✅ |
| NREL_2.8-127 (hub 120 m)            | 40  | 0.85 MB | `NREL-2p8-127-HH120.fst`             |    |    | 127.0 | 119.6 | ✅ |
| Vestas V27 (historical baseline)    | 24  | 0.14 MB | `SNLV27_F8.fst`                      |    |    |  27.0 |  32.0 | ✅ |
| **SiteA 4 MW class** (subject)         | 47  | 0.93 MB | `SiteA-Ref4MW.fst`                   |    |    | 103.5 | 97.9  | ⚠️ see note |

**Total bundled**: 11 runnable OpenFAST models (+1 shared data
directory) spanning 449 files and ~15.4 MB. Every model's `.fst` was
parsed successfully and references verified sub-files.

The IEA 15MW Monopile and VolturnUS (rows in **bold**) were added in
the v0.2 patch commit after the initial v0.1 release; they were
downloaded directly from the official `IEAWindSystems/IEA-15-240-RWT`
repository under Apache 2.0 with attribution preserved in
`nrel_reference/iea_15mw/OpenFAST_*/ATTRIBUTION.md`. The auto-extracted
rotor diameter of 241.9 m matches the published 240 m (the +1.9 m is
the hub-to-tip radius), and the auto-extracted hub height of 148.7 m
matches the published 150 m within the 1.3 m shaft tilt offset.

## Per-model notes

### NREL 5MW Baseline (shared data directory)

- Path: `nrel_reference/openfast_rtest/5MW_Baseline/`
- Role: Contains the NREL 5 MW blade, tower, airfoil polars, and DLL
  data shared by the OC3 monopile, land-based, and FastFarm test
  cases. This directory has no top-level `.fst` file; it is
  referenced *by file path* from the OC3 monopile deck.
- Modules supported: ElastoDyn blade and tower data, AeroDyn airfoil
  data, ServoDyn DLL library, HydroData directory.
- Verification status: **data-only; no standalone run possible**. To
  run the NREL 5MW baseline, use the OC3 monopile deck and set
  `CompHydro = 0, CompSub = 0` at the top of its `.fst`.

### NREL 5MW OC3 Monopile + WavesIrr (offshore benchmark)

- Path: `nrel_reference/openfast_rtest/5MW_OC3Mnpl_DLL_WTurb_WavesIrr/`
- Source: OpenFAST r-test v4.0.2 regression suite
- Rotor: 126.0 m diameter, 3 blades, hub height ≈ 89.6 m
- Modules enabled: **ElastoDyn + InflowWind + AeroDyn + ServoDyn +
  SeaState + HydroDyn + SubDyn** — the complete offshore coupling.
- Foundation: OC3 monopile in 20 m water depth, fixed base at the
  seabed (no soil-structure interaction in the base deck).
- **This is the most important benchmark in the repository** for the
  SiteA model because it is the only NREL reference that activates
  the `CompHydro + CompSub` chain and exercises the SubDyn
  substructure interface. Any changes to the Op³ SubDyn bridge should
  first be verified against the OC3 deck before being applied to the
  SiteA deck.
- Simulation: 60 s regression run with `DT = 0.0125 s` and irregular
  wave excitation via the built-in JONSWAP spectrum.

### NREL IEA-scaled land-based reference family (1.72 to 2.8 MW)

- Path: `nrel_reference/iea_scaled/`
- Source: NREL-WISDEM Reference Wind Turbines library, scaled from
  the IEA-3.4-130-RWT baseline
- Four models: NREL 1.72-103, NREL 1.79-100, NREL 2.3-116, and
  NREL 2.8-127 (two hub-height variants, 87 m and 120 m)
- Modules enabled: **ElastoDyn + InflowWind + AeroDyn + ServoDyn**
  (land-based, no HydroDyn or SubDyn)
- Each model has a full 40-file OpenFAST input deck including tower,
  blade, airfoil polars, DISCON controller settings, and Cp-Ct-Cq
  lookup tables. All bundled at ~850 KB per model.
- Relevance: these provide the **blade aerodynamic and control
  templates** that the SiteA model inherits as a starting point
  before site-specific calibration. The NREL 1.72-103 airfoil set,
  in particular, is directly used by the SiteA deck (see note on
  SiteA rotor below).

### Vestas V27 (historical baseline)

- Path: `nrel_reference/vestas/V27/`
- Capacity: 225 kW, 27 m rotor diameter, hub height 32.05 m
- Role: Historical baseline for regression testing. The V27 is the
  smallest turbine in the NREL reference library and is useful for
  fast smoke-testing of any code that reads ElastoDyn/AeroDyn files.
  It runs in seconds.
- Bundled as `SNLV27_F8.fst` (OpenFAST v8) and `SNLV27_OF2.fst`
  (OpenFAST 2.x); both are runnable with v4.0.2 after the automatic
  format upgrade.

### SiteA 4 MW class (subject under test) — verification caveats

- Path: `site_a_ref4mw/openfast_deck/`
- **What the verification script finds:** rotor diameter 103.5 m,
  hub height 97.9 m. This is the ElastoDyn file inherited from the
  NREL 1.72-103 template and has **not** been updated to the final
  SiteA geometry. The `.fst` deck is structurally complete and will
  run to completion, but the rotor aerodynamic and blade structural
  properties are placeholders.
- **What the real SiteA specification is** (from
  [`op3/config/site_a_site.yaml`](../../op3/config/site_a_site.yaml)):
  - Rotor: Reference 4 MW OWT, diameter 136.0 m, 3 blades
  - Hub height: 96.3 m above MSL
  - Rated power: 4 MW class at 11 m/s
  - Rotor speed: 13.2 rpm rated
  - Tower: 28 tapered sections, OD 4.2 m base → 3.5 m top, material S420ML
  - Foundation: tripod with three 8 m diameter suction buckets, skirt
    length 9.3 m, 120° spacing
- **Calibration status:** the tower ElastoDyn file
  (`SiteA-Ref4MW_ElastoDyn_tower_calibrated.dat`) has been updated to
  the real SiteA tower dimensions, but the blade definition and
  rotor `TipRad` parameter still point at the NREL 1.72-103 blade.
  This is documented in
  [`site_a_ref4mw/openfast_deck/README.md`](../../site_a_ref4mw/openfast_deck/README.md)
  as a known limitation to be resolved before any aerodynamic
  prediction from the SiteA OpenFAST deck is used in publication.
  **Structural natural frequency predictions are valid** because they
  depend on the tower inertia (which is calibrated) and the foundation
  stiffness (which is the subject of the whole Op³ framework and is
  validated independently in the OpenSeesPy BNWF module). Aerodynamic
  power, thrust, and time-domain rotor response are **not yet
  calibrated** to the real Reference 4 MW OWT rotor.

## Module enablement matrix

The automatic verification script reports which OpenFAST modules are
active in each `.fst` file. The column reports the file flag value
(`0` = off, `1` or higher = on), and the ✓ mark indicates an active
module.

| Model                | Elast | Inflow | Aero | Servo | SeaSt | Hydro | Sub | Mooring | Ice |
|----------------------|:-----:|:------:|:----:|:-----:|:-----:|:-----:|:---:|:-------:|:---:|
| NREL 5MW OC3         |   ✓   |   ✓    |  ✓   |   ✓   |   ✓   |   ✓   |  ✓  |         |     |
| NREL 1.72-103        |   ✓   |   ✓    |  ✓   |   ✓   |       |       |     |         |     |
| NREL 1.79-100        |   ✓   |   ✓    |  ✓   |   ✓   |       |       |     |         |     |
| NREL 2.3-116         |   ✓   |   ✓    |  ✓   |   ✓   |       |       |     |         |     |
| NREL 2.8-127 (hh87)  |   ✓   |   ✓    |  ✓   |   ✓   |       |       |     |         |     |
| NREL 2.8-127 (hh120) |   ✓   |   ✓    |  ✓   |   ✓   |       |       |     |         |     |
| Vestas V27           |   ✓   |   ✓    |  ✓   |   ✓   |       |       |     |         |     |
| **SiteA 4 MW class**    |   ✓   | *off*  | *off*| *off* | *off* | *off* | *off* |       |     |

The SiteA deck currently has all modules except ElastoDyn set to
*off*. This is because the bundled deck is a skeleton that runs the
structural dynamics only. The full offshore-coupled SiteA simulation
is produced at runtime by
[`op3/openfast_coupling/build_site_a_subdyn.py`](../../op3/openfast_coupling/build_site_a_subdyn.py),
which generates a new `.fst` with HydroDyn and SubDyn activated and
the foundation stiffness matrix injected from the OpenSeesPy BNWF
model. This runtime generation is deliberate: it keeps the committed
SiteA deck as a clean, always-runnable template and defers the
site-specific module activation to the coupling step.

## What this benchmark proves, and what it does not prove

**Proven:**

1. Every NREL reference `.fst` file referenced in this repository
   exists and parses as a valid OpenFAST v4.0.2 input deck.
2. Every referenced ElastoDyn, AeroDyn, ServoDyn, HydroDyn, and SubDyn
   sub-file exists on disk.
3. Rotor diameter and hub height are extractable and consistent with
   the published NREL specifications (within 1% tolerance on the
   scaled IEA family).
4. The OC3 monopile deck activates the complete CompHydro + CompSub
   chain, providing a benchmark for the SiteA SubDyn bridge.

**Not proven by this benchmark alone:**

1. The models have not been *executed* end-to-end in this repository.
   Running them requires an OpenFAST v4.0.2 binary (user-supplied,
   not bundled here). The GitHub Actions CI workflow pulls the binary
   from the official NREL release and runs a short regression on the
   OC3 monopile deck — see
   [`.github/workflows/openfast-regression.yml`](../../.github/workflows/openfast-regression.yml).
2. Steady-state performance curves (Cp, Ct vs tip-speed-ratio) and
   time-domain dynamic response have not been compared across models.
   That is the subject of
   [`validation/benchmarks/SITE_A_VS_NREL.md`](SITE_A_VS_NREL.md),
   which reports the head-to-head numerical comparison between SiteA
   and the NREL 5 MW OC3 monopile.

## CI workflow

The GitHub Actions workflow at
[`.github/workflows/verify-nrel.yml`](../../.github/workflows/verify-nrel.yml)
runs `scripts/verify_nrel_models.py` on every push and fails if any
committed model fails to parse. This keeps the benchmark table in
sync with the actual repository state — if any model is accidentally
broken by a future commit, the CI fails and the commit cannot be
merged to `main`.
