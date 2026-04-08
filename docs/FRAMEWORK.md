# Op³ Framework Architecture

This document describes the conceptual architecture of the Op³
framework and the internal data flow between its three solver
layers. It is the document a researcher at NREL, DTU, or any other
institution should read before attempting to extend the framework or
port it to a new turbine.

## High-level data flow

```
     input                         solver                   output
 ┌───────────┐             ┌───────────────────┐       ┌─────────────┐
 │ CPT       │             │ OptumGX           │       │ VHM envelope│
 │ profile   │ ──────────▶ │ 3D FE limit       │ ────▶ │ contact     │
 │ geometry  │             │ analysis          │       │ pressure    │
 │ YAML      │             │                   │       │ dissipation │
 └───────────┘             └───────────────────┘       └──────┬──────┘
                                                              │
                                                              ▼
                                                          CSV files
                                                       (data/fem_results/)
                                                              │
 ┌───────────┐             ┌───────────────────┐       ┌──────┴──────┐
 │ spring    │             │ OpenSeesPy        │       │ eigen modes │
 │ profile   │ ──────────▶ │ 1D BNWF           │ ────▶ │ pushover    │
 │ CSV       │             │ (4 modes)         │       │ transient   │
 │ YAML      │             │                   │       │ 6x6 K_SSI   │
 └───────────┘             └───────────────────┘       └──────┬──────┘
                                                              │
                                                              ▼
                                                        SubDyn .dat
                                                              │
 ┌───────────┐             ┌───────────────────┐       ┌──────┴──────┐
 │ rotor     │             │ OpenFAST          │       │ time-domain │
 │ tower     │ ──────────▶ │ aero-hydro-       │ ────▶ │ structural  │
 │ wave/wind │             │ servo-elastic     │       │ response    │
 │ input     │             │                   │       │             │
 └───────────┘             └───────────────────┘       └─────────────┘
```

## Three integration surfaces

The framework has three integration surfaces, each with a clearly
defined file-based interface. This design choice (files rather than
in-memory objects) is deliberate: it makes each solver independently
testable, allows any component to be swapped for a compatible
alternative, and makes the coupling scripts runnable from the command
line as well as from Python.

### Surface 1: OptumGX → OpenSeesPy

**Interface:** CSV files in `data/fem_results/`

**Direction:** one-way, upstream to downstream

**What crosses the boundary:**

- **Capacity functions.** OptumGX computes the VHM capacity envelope
  of the suction bucket under combined vertical, horizontal, and
  moment loading at various scour depths. The envelopes are fitted
  to a power-law model
  $$H_{\text{ratio}}(S/D) = 1 - \gamma \, (S/D)^{\delta}$$
  with $(\gamma, \delta)$ written to `power_law_parameters.csv`.
  The OpenSeesPy BNWF springs use this function to set their
  ultimate resistance `p_ult` at each depth.

- **Stiffness profiles.** OptumGX computes the load-deformation
  response of the bucket under small lateral displacements and
  writes the initial stiffness `k_ini(z)` at each depth to
  `Scour_Stiffness_Matrix_Master.csv`. OpenSeesPy BNWF springs use
  this as their elastic stiffness.

- **Plastic dissipation field (advanced mode only).** OptumGX writes
  the depth-resolved plastic dissipation at collapse to
  `dissipation_profile.csv`. This is used by the dissipation-weighted
  generalized BNWF (Mode D) to compute the depth-dependent
  participation factor `w(z)` in the generalized Vesic cavity
  expansion formulation described in Appendix A of the dissertation.

**Schema:**

All CSVs have a consistent schema documented in `data/README.md`.
A third-party tool that produces these CSVs in the correct format
can replace OptumGX without changing anything downstream.

### Surface 2: OpenSeesPy foundation module selector

**Interface:** Python class constructor flag `foundation_mode`

**Direction:** in-process, Python to Python

The OpenSeesPy tower model is identical across all four modes —
only the foundation boundary condition changes. This is implemented
by a factory function in `op3/opensees_foundations/bnwf_model.py`:

```python
def build_tower_model(foundation_mode: str, **kwargs):
    """Build an OpenSeesPy tower model with a selectable foundation.

    Parameters
    ----------
    foundation_mode : str
        One of 'fixed', 'stiffness_6x6', 'distributed_bnwf',
        'dissipation_weighted'.
    **kwargs :
        Mode-specific parameters. See each mode's docstring below.

    Returns
    -------
    model : OpenSeesPyTowerModel
        A model object ready for .eigen(), .pushover(), or .transient()
    """
```

The four modes are implemented as:

#### Mode A — `foundation_mode='fixed'`

Fixes the base of the tower at the mudline with a single `fix` command
on all six DOFs. Zero kwargs needed. Zero inputs from OptumGX.

Use case: upper-bound reference for tower flexibility only, sanity
check that the tower model itself is correct before any soil
interaction is added.

#### Mode B — `foundation_mode='stiffness_6x6'`

Attaches a single `zeroLength` element with a full 6×6 stiffness
matrix at the mudline. The matrix can be loaded from a CSV file or
passed as a NumPy array.

```python
model = build_tower_model(
    foundation_mode='stiffness_6x6',
    stiffness_matrix='data/fem_results/K_6x6_baseline.csv',
)
```

The 6×6 matrix encodes translational stiffness `(Kxx, Kyy, Kzz)`,
rotational stiffness `(Krx, Kry, Krz)`, and translational-rotational
coupling terms. For the Gunsan tripod, all three foundation nodes
are condensed into a single equivalent matrix at the tower base
using the **static condensation** procedure in
`op3/openfast_coupling/opensees_stiffness_extractor.py`.

Use case: fast eigenvalue analysis for parametric sweeps; the
matrix that is injected into OpenFAST's SubDyn module (see
Surface 3 below); the representation used by the PISA research
programme for rigid bucket-like foundations.

#### Mode C — `foundation_mode='distributed_bnwf'`

Builds a depth-discretized tower-foundation coupled model with
lateral `p-y` springs and vertical `t-z` springs at each depth
point along the bucket skirt. The spring properties are loaded
from a CSV file that has the schema:

```
depth_m, k_ini_kN_per_m, p_ult_kN_per_m, spring_type
0.5,     1.20e+07,       150,            p_y
1.0,     1.85e+07,       310,            p_y
...
```

A scour correction is applied at runtime: for nodes above the
scoured mudline (`z < S`), the springs are disabled; for nodes
near the scour front, a smooth transition factor
`relief(z) = sqrt((z - S) / z)` is applied to account for
stress relief.

```python
model = build_tower_model(
    foundation_mode='distributed_bnwf',
    spring_profile='data/fem_results/opensees_spring_stiffness.csv',
    scour_depth=1.5,
)
```

Use case: Chapter 6 core of the dissertation, and the recommended
mode for scour sensitivity studies because it captures the
depth-dependent loss of stiffness as the scoured mudline moves down.

#### Mode D — `foundation_mode='dissipation_weighted'`

The highest-fidelity mode. Extends Mode C with a depth-dependent
participation factor derived from the OptumGX plastic dissipation
field at collapse. This is the generalized cavity expansion
framework described in Appendix A of the dissertation. The key
point is that the participation factor `w(z)` is not assumed
uniform (as in classical Vesic cavity expansion) but is read
directly from an OptumGX energy field:

```
w(z) = D_total(z) / max(D_total)
```

where `D_total(z)` is the integrated plastic dissipation across
all elements at depth `z` within the zone of influence of the
collapse mechanism. The spring stiffness, ultimate resistance, and
half-displacement are all derived from a single energy-consistent
formulation with `s_u` canceling exactly in the `y50` parameter.

```python
model = build_tower_model(
    foundation_mode='dissipation_weighted',
    ogx_dissipation='data/fem_results/dissipation_profile.csv',
    ogx_capacity='data/fem_results/power_law_parameters.csv',
    scour_depth=1.5,
)
```

Use case: publication-grade research use, validation against
independent experiments, and the mode against which Modes A-C
are cross-validated.

### Cross-mode comparison function

```python
from op3.opensees_foundations import compare_foundation_modes
results = compare_foundation_modes(
    modes=['fixed', 'stiffness_6x6', 'distributed_bnwf', 'dissipation_weighted'],
    scour_levels=[0.0, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0],
)
```

Returns a pandas DataFrame indexed by `(mode, scour)` with the
first natural frequency and mode shape for each combination. This
is the reproduction of Figure 6.X (Foundation mode comparison) in
the dissertation. See `examples/01_compare_foundation_modes.py`
for a runnable version.

### Surface 3: OpenSeesPy → OpenFAST

**Interface:** SubDyn `.dat` file + the main OpenFAST `.fst` file

**Direction:** one-way, OpenSeesPy to OpenFAST

**What crosses the boundary:**

- A 6×6 stiffness matrix at the tower base. Extracted from the
  OpenSeesPy model by static condensation of the BNWF foundation
  degrees of freedom onto the single tower base node. The matrix
  is a full stiffness matrix including coupling terms.

- Optionally, a 6×6 mass matrix at the same node for added mass
  effects from the bucket plug and soil.

- Optionally, a frequency-dependent impedance function $K(ω)$ for
  applications where the static condensation is too approximate
  (e.g., soil damping in transient analysis). This mode uses the
  Wolf cone model + Gazetas dashpot formulation from Appendix A of
  the dissertation.

**How the stiffness is extracted:**

```python
# op3/openfast_coupling/opensees_stiffness_extractor.py
from op3.opensees_foundations import build_tower_model

model = build_tower_model(
    foundation_mode='distributed_bnwf',
    spring_profile='data/fem_results/opensees_spring_stiffness.csv',
    scour_depth=0.0,
)

# Static condensation of foundation DOFs onto tower base node
K_ssi = model.extract_6x6_stiffness(condense_to_node='tower_base')

# Write SubDyn input file
write_subdyn_file(
    'gunsan_4p2mw/openfast_deck/Gunsan-4p2MW_SubDyn.dat',
    K_ssi=K_ssi,
    scour_depth=0.0,
)
```

The `write_subdyn_file` function generates a valid OpenFAST v4.0.2
SubDyn input file with the `Reactions` block populated by the K_SSI
matrix. This file is referenced by the main `.fst` via the `SubFile`
parameter, and OpenFAST picks it up at simulation startup.

**Why one-way and not two-way?**

A two-way coupling (where OpenFAST feeds tower-base forces back into
OpenSeesPy at each time step, and OpenSeesPy updates its nonlinear
soil springs in response) would be more physically correct but is
computationally expensive (roughly 10x slower) and introduces
complicated synchronization issues between the two codes.

For the scour monitoring application of the dissertation, the
linearization of the soil springs around the static operating point
is a reasonable approximation because:

1. The operational wind loading causes tower base moments well below
   the static design moment, so the springs stay in their linear
   elastic range 95% of the time.
2. The infrequent high-wind events are beyond the scope of the
   monitoring framework (which is designed for normal operation).
3. The static 6×6 stiffness captures the mean-level tower response
   adequately, and the small deviations from linearity are
   absorbed into the structural damping.

A two-way coupling mode is identified as future work in Chapter 6
of the dissertation.

## Single Source of Truth configuration

Every physical parameter in the framework — turbine geometry, soil
profile, material properties, environmental conditions — lives in
exactly one file:

```
op3/config/gunsan_site.yaml
```

This is a strict convention. No constants are hardcoded in any
Python script. Any script that needs a parameter loads it from the
SSOT YAML via:

```python
from op3.config import load_site_config
cfg = load_site_config('op3/config/gunsan_site.yaml')
D = cfg['foundation']['bucket_diameter_m']
L = cfg['foundation']['skirt_length_m']
```

The SSOT is version-controlled. Changes to it automatically flow to
every downstream script. Applying the framework to a different site
means editing this single file and regenerating the OptumGX CSVs;
nothing else needs to change.

## Verification chain

The framework has four independent verification levels:

1. **Solver verification.** OpenSeesPy, OpenFAST, and OptumGX each
   have their own verified and validated codebases. Op³ does not
   re-verify the solvers.

2. **Interface verification.** Each of the three integration surfaces
   is tested by a dedicated pytest assertion in `tests/`:
   - `test_optumgx_csv_schema.py` — verifies that the committed CSVs
     have the expected columns, units, and value ranges
   - `test_opensees_foundation_modes.py` — verifies that all four
     modes produce sensible first-mode frequencies for a simple
     tower
   - `test_opensees_to_subdyn.py` — verifies that the extracted
     6×6 matrix is symmetric, positive-definite, and has physically
     reasonable magnitudes

3. **Cross-mode cross-validation.** The four OpenSeesPy foundation
   modes are run on the same tower and scour level, and the
   predicted first natural frequencies are compared in
   `validation/benchmarks/FOUNDATION_MODE_STUDY.md`. Modes B, C, and
   D should agree within ~5% for the same input data; Mode A (fixed)
   provides the upper bound.

4. **NREL benchmark comparison.** The Gunsan model is benchmarked
   against the NREL 5MW OC3 monopile deck in
   `validation/benchmarks/GUNSAN_VS_NREL.md`. The Gunsan model's
   tower + rotor structural dynamics should behave qualitatively
   like the OC3 model's in any mode where both models share the
   same physical setup.

## How to port Op³ to a different turbine

The framework is designed so that porting to a new turbine touches
only the SSOT configuration and the OptumGX upstream step. Specific
steps:

1. Create a new YAML file modeled on `op3/config/gunsan_site.yaml`
   with the new turbine's geometry, soil profile, rotor mass, tower
   properties, and water depth.
2. Run OptumGX over the new parameter envelope (requires a license)
   and write the output CSVs to `data/fem_results/` with the same
   schema as the committed Gunsan CSVs.
3. Run the OpenSeesPy foundation module of choice (A-D) with the
   new SSOT YAML. The OpenSeesPy code itself does not need to
   change.
4. Run the SubDyn bridge to generate the OpenFAST deck, pointing at
   the new SSOT YAML. The OpenFAST deck files (ElastoDyn, AeroDyn,
   HydroDyn, ServoDyn) need to be updated with the new rotor and
   tower properties; the SubDyn file is generated automatically.
5. Run OpenFAST as usual.

The separation is clean enough that the OptumGX step can be replaced
entirely (e.g., with an analytical power-law capacity function for a
well-understood bucket geometry, or with published PISA capacity
values) without touching the OpenSeesPy or OpenFAST steps.

## What the framework does not do

To avoid overclaiming, here is what Op³ explicitly **does not**
attempt:

- Multi-bucket differential scour. The current framework assumes
  symmetric scour at all three buckets. Asymmetric scour would
  require per-bucket foundation modeling and is identified as
  future work in Chapter 9 of the dissertation.

- Nonlinear transient soil-structure interaction. The coupling to
  OpenFAST is linear (via a 6×6 K matrix). Under extreme loading,
  soil springs become nonlinear and hysteretic; the current
  framework does not capture this.

- Three-dimensional wave-current-soil coupling. HydroDyn accounts
  for wave and current loading on the structure; the soil response
  to those loads is handled through the linearized K matrix. A
  fully coupled 3D wave-soil interaction problem is beyond the
  framework's scope.

- Probabilistic rotor blade failure. Aerodynamic loads are
  deterministic in OpenFAST (given an inflow realization). Rotor
  blade damage and fatigue are outside the scour monitoring scope.

## References

- Vesic, A. S. (1972). Expansion of cavities in infinite soil
  masses. *Journal of the Soil Mechanics and Foundations Division*,
  98(3), 265-290.
- Wolf, J. P. (1985). *Dynamic soil-structure interaction*.
  Prentice-Hall.
- Gazetas, G. (1991). Formulas and charts for impedances of surface
  and embedded foundations. *Journal of Geotechnical Engineering*,
  117(9), 1363-1381.
- Burd, H. J. et al. (2020). PISA design model for monopiles in
  sand. *Géotechnique*, 70(11), 970-985.
- Byrne, B. W. et al. (2020). PISA design model for monopiles in
  clay. *Géotechnique*, 70(11), 986-998.
- Jonkman, J. M. et al. (2009). Definition of a 5-MW reference wind
  turbine for offshore system development. NREL TP-500-38060.
- Krabbenhoft, K. et al. (2007). Formulation and solution of some
  plasticity problems as conic programs. *International Journal of
  Solids and Structures*, 44(5), 1533-1549.
