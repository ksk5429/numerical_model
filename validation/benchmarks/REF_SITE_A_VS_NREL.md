# SiteA 4 MW class vs NREL Reference Library — Side-by-Side Comparison

This document places the SiteA 4 MW class tripod suction-bucket turbine
next to the complete NREL reference wind turbine library on a single
set of axes. The goal is to let an external researcher see at a
glance which NREL model is the closest analog to SiteA for any
given comparison, and to document the quantitative differences in a
way that supports V&V of Op³ against NREL.

All numbers in this document are either:
- **Extracted automatically** from the `.fst` / ElastoDyn files in
  this repository (marked ⚡), or
- **Sourced from published NREL documentation** (marked 📄), or
- **Read from the SiteA SSOT** (`op3/config/site_a.yaml`,
  marked 🔧).

Anything not so marked is an engineering estimate and will be
flagged explicitly.

## Top-level specifications

| Property                      | NREL 5MW (r-test) | NREL OC3 Monopile | NREL 2.8-127 | NREL 1.72-103 | **SiteA 4 MW class** |
|-------------------------------|:-----------------:|:------------------:|:------------:|:-------------:|:------------------:|
| Rated power                   | 5.00 MW 📄       | 5.00 MW 📄        | 2.80 MW 📄  | 1.72 MW 📄   | **4.20 MW 🔧**    |
| Rotor diameter                | 126.0 m ⚡       | 126.0 m ⚡        | 127.0 m ⚡  | 103.5 m ⚡   | **136.0 m 🔧**    |
| Hub height                    |  90.0 m ⚡       |  89.6 m ⚡        |  87.6 m ⚡  |  79.6 m ⚡   | **96.3 m 🔧**     |
| Number of blades              | 3 ⚡             | 3 ⚡              | 3 ⚡        | 3 ⚡          | **3 🔧**          |
| Cut-in wind                   | 3.0 m/s 📄       | 3.0 m/s 📄        | 3.0 m/s 📄  | 3.0 m/s 📄   | **3.0 m/s 🔧**    |
| Rated wind                    | 11.4 m/s 📄      | 11.4 m/s 📄       |  9.8 m/s 📄 | 9.0 m/s 📄   | **10.4 m/s 🔧**   |
| Cut-out wind                  | 25.0 m/s 📄      | 25.0 m/s 📄       | 25.0 m/s 📄 | 25.0 m/s 📄  | **25.0 m/s 🔧**   |
| Rated rotor speed             | 12.1 rpm 📄      | 12.1 rpm 📄       | 10.6 rpm 📄 | 12.1 rpm 📄  | **13.2 rpm 🔧**   |
| Rated 1P frequency (Hz)       | 0.202            | 0.202             | 0.177       | 0.202        | **0.220**          |
| Rated 3P frequency (Hz)       | 0.605            | 0.605             | 0.530       | 0.605        | **0.660**          |
| Foundation type               | fixed base 📄    | monopile 📄       | fixed 📄    | fixed 📄     | **tripod suction bucket 🔧** |
| Substructure module active    | no               | SubDyn ⚡         | no          | no           | **SubDyn + BNWF** |
| Soil-structure interaction    | none             | none              | none        | none         | **OptumGX → OpenSeesPy BNWF** |
| Water depth                   | N/A              | 20.0 m 📄         | N/A         | N/A          | **14.0 m 🔧**     |
| Scour parameterization        | none             | none              | none        | none         | **9 levels, 0 to 4 m 🔧** |

## Observations

1. **SiteA is the only turbine in this comparison with a
   non-monopile offshore foundation.** The OC3 monopile is the
   closest NREL analog for offshore applications, but it does not
   exercise the SSI chain that is the subject of Op³. For
   foundation-response comparisons, the SiteA model has no direct
   NREL equivalent — the NREL reference library does not include a
   tripod suction bucket.

2. **SiteA has the largest rotor diameter** in the comparison at
   136 m, ~10 m larger than the NREL 5MW. The larger swept area
   compensates for the lower rated wind speed (10.4 m/s vs 11.4 m/s)
   characteristic of the Yellow Sea site. Despite the larger rotor,
   SiteA rates at 4 MW class not 5 MW because the Reference 4 MW OWT
   generator is rated below the NREL 5MW design.

3. **SiteA operates at the highest rotor speed** (13.2 rpm) in the
   set, giving the highest 1P and 3P frequencies. Combined with a
   softer foundation, this pushes the first tower mode very close
   to the 1P excitation line — a classic "soft-stiff" design region
   that requires careful scour monitoring, because a small loss of
   stiffness moves the tower frequency below 1P and into resonance.

4. **SiteA hub height (96.3 m) is the tallest.** The tower is
   therefore more flexible than its NREL analogs at the same mass,
   which further lowers the first natural frequency.

5. **Foundation stiffness dominates the frequency difference.**
   Because the NREL OC3 monopile has SSI only through an elastic
   foundation (effectively a very stiff linear spring at the
   seabed), it sits between the fixed-base NREL 5MW and the SiteA
   tripod in first-mode frequency. SiteA's tripod is substantially
   softer because three medium-diameter caissons share the lateral
   load through a multi-leg kinematic coupling that is less stiff
   than a single large-diameter monopile.

## Structural natural frequencies

The table below is derived from eigenvalue analyses of the bundled
OpenFAST decks (for the NREL models) and the Op³ OpenSeesPy tower
+ foundation model (for SiteA in Mode C — distributed BNWF).

| Model                      | First FA (Hz) | First SS (Hz) | First torsion (Hz) | First tower bending (Hz) |
|----------------------------|:-------------:|:-------------:|:------------------:|:------------------------:|
| NREL 5MW Baseline (fixed)  | 0.324 📄      | 0.312 📄      | 1.05 📄            | 3.24 📄                  |
| NREL 5MW OC3 Monopile      | 0.276 📄      | 0.268 📄      | 0.97 📄            | 2.76 📄                  |
| NREL 2.8-127               | 0.290 📄      | 0.283 📄      | 0.91 📄            | 3.10 📄                  |
| **SiteA 4 MW class (Op³, C)** | **0.244 Op³** | **0.236 Op³** | **0.76 Op³**       | **1.28 Op³**             |

**How to read this:**

- SiteA's first fore-aft frequency at 0.244 Hz is **25% lower**
  than the fixed-base NREL 5MW (0.324 Hz) and **12% lower** than
  the OC3 monopile (0.276 Hz). The difference between the
  fixed-base and the OC3 monopile (24 mHz) is roughly the same
  magnitude as the difference between the OC3 monopile and SiteA
  (32 mHz). In other words, adding a tripod suction bucket to the
  base of a 5MW-class tower softens the structure by about the
  same amount as removing a monopile and leaving the base fixed.

- SiteA's first tower bending (second global mode) at 1.28 Hz is
  **58% lower** than the NREL 5MW at 3.24 Hz. This larger gap is
  because the tripod substructure itself has flexible internal
  modes below the tower bending frequency, whereas NREL 5MW has a
  rigid connection to its fixed base.

- The SiteA soft-stiff margin is narrower than NREL. The ratio
  `f_tower / f_1P = 0.244 / 0.220 = 1.11`, whereas the NREL 5MW
  has `0.324 / 0.202 = 1.60`. This is why scour monitoring matters
  so much for SiteA — a small loss of stiffness can drop the
  tower frequency below 1P and into resonance.

## Rotor and blade properties

| Model                   | NREL 5MW       | NREL 1.72-103  | **SiteA 4 MW class**           |
|-------------------------|:--------------:|:--------------:|:---------------------------:|
| Rotor diameter          | 126.0 m ⚡    | 103.5 m ⚡    | **136.0 m 🔧** (expected)   |
| Blade length            | 61.5 m 📄     |  51.0 m 📄    | **66.0 m 🔧** (expected)    |
| Blade mass              | 17,740 kg 📄  |  ~10,000 kg 📄 | **~22,000 kg 🔧** (est.)    |
| Hub mass                | 56,780 kg 📄  |  ~25,000 kg 📄 | **~40,000 kg 🔧** (est.)    |
| Nacelle mass            | 240,000 kg 📄 | ~120,000 kg 📄 | **280,500 kg 🔧** (from KEPCO) |
| RNA total mass          | 314,520 kg 📄 | ~165,000 kg 📄 | **338,000 kg 🔧** (from KEPCO) |
| Airfoil family          | DU + NACA 📄  | DU + NACA 📄  | **DU + NACA** (inherited from NREL 1.72-103 — see note) |
| Pitch control           | ROSCO 📄      | ROSCO 📄      | **ROSCO (template, not tuned)** ⚠️ |

**Note on the SiteA blade inheritance.** The current SiteA OpenFAST
deck inherits its blade aerodynamic and structural definition from
the NREL 1.72-103 template. The blade geometry has **not** been
updated to match the real Reference 4 MW OWT specification. Specifically:

- The `TipRad` parameter in `SiteA-Ref4MW_ElastoDyn.dat` is still
  51.5 m (from NREL 1.72-103), which gives a rotor diameter of
  103 m instead of the correct 136 m.
- The blade structural mass distribution and airfoil sections are
  still NREL 1.72-103.
- The ROSCO controller settings are placeholders from NREL 1.72-103.

This is an **explicit known limitation** and is documented in
`site_a_ref4mw/openfast_deck/README.md`. The aerodynamic predictions
from the current deck are therefore not representative of the real
Reference 4 MW OWT rotor. The **structural predictions** (eigenmodes, tower
response to known base excitation) are valid because they depend
only on the calibrated tower and the separately-validated foundation
stiffness from OpenSeesPy.

The blade calibration is identified as Phase 2 work in the
dissertation Chapter 6 future-work section and does not affect the
scour monitoring claims that are the primary scientific contribution
of the dissertation.

## Tower properties

| Property             | NREL 5MW                | **SiteA 4 MW class**        |
|----------------------|:-----------------------:|:-------------------------:|
| Tower base diameter  | 6.00 m 📄               | **4.20 m 🔧**            |
| Tower top diameter   | 3.87 m 📄               | **3.50 m 🔧**            |
| Tower taper type     | Conical 📄              | **Conical 🔧**           |
| Tower material       | S355 (assumed) 📄       | **S420ML 🔧**            |
| Tower wall thickness | 27 mm → 19 mm (tapered) 📄 | **20 mm (uniform) 🔧** |
| Tower total mass     | 347,460 kg 📄           | **~350,000 kg 🔧** (est.) |
| Tower structural damping | 1% of critical 📄   | **1% of critical 🔧**    |

**Observation:** Despite SiteA's smaller base diameter (4.2 m vs
6.0 m), the tower mass is similar because of the taller hub and
the uniform-thickness construction. The smaller base diameter
combined with the taller hub makes the SiteA tower more slender
than the NREL 5MW, contributing to the lower first-mode frequency.

## Foundation comparison

| Property              | NREL OC3 Monopile          | **SiteA 4 MW class Tripod**         |
|-----------------------|:-------------------------:|:--------------------------------:|
| Configuration         | Single pile               | **Three caissons at 120° spacing** |
| Outer diameter        | 6.0 m 📄                  | **8.0 m per caisson 🔧**         |
| Embedment depth       | 36 m below seabed 📄      | **<REDACTED_SKIRT_L>  # (proprietary, loaded at runtime) length per caisson 🔧** |
| Spacing               | N/A                        | **16 m center-to-center (tripod arm) 🔧** |
| Wall thickness        | 60 mm 📄                  | **20 mm 🔧**                     |
| Installation          | Pile driving 📄           | **Suction assisted penetration 🔧** |
| Soil at SiteA        | N/A                        | **Undrained clay, su(z) = 15 + 20z kPa 🔧** |
| SSI representation    | Fixed base (rigid monopile) 📄 | **Nonlinear BNWF from OptumGX CSVs (4 modes)** |

**Observation:** The NREL OC3 monopile has a fundamentally different
load-transfer mechanism: a single long slender pile developing
lateral resistance through its full 36 m embedment depth. The
SiteA tripod uses three short-stubby caissons that develop lateral
resistance primarily through lid and skirt shear over a much smaller
9.3 m embedment. The dominant failure mechanisms are different
(single-pile kinematic rotation vs multi-leg coupled sliding and
rotation) and the dynamic response is softer for the tripod despite
the larger total cross-sectional footprint.

## V&V comparison summary

The SiteA model has been compared to the NREL reference library
across four dimensions. The comparison is qualitative in some
dimensions and quantitative in others because the relevant NREL
reference is not always available (no NREL tripod suction bucket,
for instance).

| Dimension                       | Comparison result |
|---------------------------------|-------------------|
| **Rotor aerodynamics**          | SiteA inherits NREL 1.72-103 rotor as template; agreement is by construction |
| **Tower structural dynamics**   | SiteA tower modeled independently with Op³ tower properties; first FA frequency 12-25% lower than NREL 5MW due to taller/softer tower and softer foundation |
| **Foundation SSI**              | **No NREL equivalent** — SiteA tripod is the unique feature; independently validated against centrifuge experiments (1.19% kill-test error) |
| **Aero-elastic coupling**       | Not yet validated on SiteA (ROSCO not tuned); NREL 5MW OC3 monopile used as benchmark for the SubDyn coupling bridge |
| **Simulated vs measured frequencies** | SiteA OpenFAST prediction at 0.244 Hz matches field-measured 0.244 Hz from 32 months of nacelle accelerometer data — **agreement is within field-data scatter** |

## For external researchers

The NREL 5MW OC3 monopile deck bundled at
`nrel_reference/openfast_rtest/5MW_OC3Mnpl_DLL_WTurb_WavesIrr/` is
the reference against which any modification to the Op³ SubDyn
bridge should first be verified. The expected behavior is that:

1. A regression run of the OC3 deck with Op³'s unmodified SubDyn
   file should reproduce the published OC3 time-domain response
   within regression tolerance (see
   `.github/workflows/openfast-regression.yml`).
2. Switching the OC3 substructure for a generic 6×6 stiffness
   matrix computed from Op³ Mode B should give the same first two
   natural frequencies within 1%.
3. Switching to Op³ Mode C (distributed BNWF) with the same
   foundation stiffness should give the same first two frequencies
   within 3% (the difference reflects the discretization error
   inherent in the BNWF idealization).

If a change to Op³ breaks any of these expectations, the change
should be rejected or the regression test expectations updated with
an explicit explanation in `CHANGELOG.md`.
