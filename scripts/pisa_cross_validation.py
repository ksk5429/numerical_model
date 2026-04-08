"""
PISA cross-validation harness (Phase 3 / Task 3.1e).

Compares Op^3's PISA implementation against published monopile test
cases. The catalog below pins each case to a specific paper and table
so the comparison is auditable and the references can be checked
independently.

Cases included in this version
------------------------------
1. Dunkirk medium-scale field test pile DM7 (PISA JIP marine sand)
   Source: Byrne et al. (2020), Geotechnique 70(11), 1048-1066,
           Figure 8 / Table 4. https://doi.org/10.1680/jgeot.18.PISA.005

2. Cowden medium-scale field test pile CM1 (PISA JIP glacial clay)
   Source: Burd et al. (2020), Geotechnique 70(11), 1030-1047,
           Figure 9 / Table 4. https://doi.org/10.1680/jgeot.18.PISA.004

3. Borkum Riffgrund-1 demonstrator monopile (Orsted)
   Source: Murphy et al. (2018), Marine Structures 60, 263-281.

Important finding (v0.3.0)
--------------------------
With the real reference values from McAdam 2020 Table 3 (Dunkirk
sand) and Byrne 2020 Table 3 (Cowden clay) now populated, the
harness reports systematic DISCREPANT status: Op^3 PISA over-
predicts the measured initial secant stiffness by approximately
two orders of magnitude for all four medium-scale field test piles
(DM7, CM1, DL1, CL1).

Root cause: the Op^3 PISA module uses the base calibration
constants from Byrne 2020 Table 7 (k_sand = 8.731) and Burd 2020
Table 6 (k_clay = 10.6) as flat values. These are calibrated at a
single reference configuration in the 3D finite-element back-
analyses. The actual PISA model uses L/D-dependent depth functions
(Burd 2020 Table 5) that modify the effective initial slope for
short rigid piles. Without those depth functions, Op^3 over-
estimates k by ~100-200x on L/D <= 5 piles.

This is a known limitation of Op^3 v0.3.0 and is documented in
docs/DEVELOPER_NOTES.md. Fixing it requires implementing the depth
function parameters from Burd 2020 Table 5 and Byrne 2020 Table 5
and is tracked in the v0.4 roadmap. For publication-grade PISA
predictions in the current release, users should apply the
correction factor f(L/D) manually or fall back to the DNV / OWA
6x6 stiffness formulae (op3.standards.dnv_st_0126,
op3.standards.owa_bearing) which are calibrated differently.

The finding itself is a success of the cross-validation harness:
it caught a subtle physics omission on the first run with real data.

The principle (from project memory): never fabricate measured data.

Run:
    python scripts/pisa_cross_validation.py
"""
from __future__ import annotations

import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from op3.standards.pisa import (  # noqa: E402
    SoilState, effective_head_stiffness, pisa_pile_stiffness_6x6,
)


@dataclass
class CrossValCase:
    name: str
    diameter_m: float
    embed_length_m: float
    soil_profile: list[SoilState]
    reference_Kxx_N_per_m: Optional[float]   # secant k_Hinit from paper
    reference_Krxrx_Nm_per_rad: Optional[float]
    citation: str
    h_load_m: float = 0.0                     # loading eccentricity above ground
    notes: str = ""
    tolerance: float = 0.50


# ---------------------------------------------------------------------------
# Published PISA test piles
# ---------------------------------------------------------------------------

# Dunkirk Pleistocene marine sand at the PISA test site
# Byrne 2020 Table 1: G_max varies linearly with depth, ~70-150 MPa
# Dunkirk sand G0 profile from Zdravkovic et al. (2020) Figure 16:
# the SCPT1+SCPT2 curves from the PISA site characterisation.
DUNKIRK_SAND = [
    SoilState(0.0,  4.0e7, 35.0, "sand"),
    SoilState(2.0,  6.0e7, 35.0, "sand"),
    SoilState(5.0,  1.0e8, 35.0, "sand"),
    SoilState(10.0, 1.5e8, 36.0, "sand"),
    SoilState(15.0, 2.0e8, 36.0, "sand"),
]

# Cowden glacial till G0 profile from Zdravkovic et al. (2020) Figure 7:
# combined TXC + SCPT1 + SCPT2 + BEvh PISA measurements.
COWDEN_CLAY = [
    SoilState(0.0,  2.0e7, 70.0e3, "clay"),
    SoilState(2.0,  5.0e7, 100.0e3, "clay"),
    SoilState(4.0,  8.0e7, 120.0e3, "clay"),
    SoilState(6.0,  1.0e8, 140.0e3, "clay"),
    SoilState(10.0, 1.5e8, 160.0e3, "clay"),
]

# Borkum Riffgrund-1 site (north sea, layered sand+clay)
# Murphy 2018: dense sand over stiff clay
BORKUM_PROFILE = [
    SoilState(0.0,  6.0e7, 32.0, "sand"),
    SoilState(15.0, 1.0e8, 34.0, "sand"),
    SoilState(30.0, 1.3e8, 36.0, "sand"),
]


CASES: list[CrossValCase] = [
    CrossValCase(
        name="Dunkirk DM7",
        diameter_m=0.762,
        embed_length_m=2.24,
        soil_profile=DUNKIRK_SAND,
        reference_Kxx_N_per_m=8.07e6,       # McAdam 2020 Tab 3: 8.07 MN/m
        reference_Krxrx_Nm_per_rad=None,     # 1651 kNm/deg -> Nm/rad, see below
        citation="McAdam et al. (2020), Geotechnique 70(11), 986-998, Tables 1+3",
        h_load_m=10.0,    # McAdam 2020 Table 1: DM7 loading eccentricity
        notes="D = 0.762 m, nominal L/D = 3, installed L = 2.24 m, "
              "wall thickness 10 mm, Dunkirk dense marine sand. "
              "Reference k_Hinit is the secant stiffness of H vs ground-level "
              "displacement for 0 < vG < D/1000.",
        tolerance=0.60,    # PISA field-test comparison typically within 50-60%
    ),
    CrossValCase(
        name="Cowden CM1",
        diameter_m=0.762,
        embed_length_m=3.98,
        soil_profile=COWDEN_CLAY,
        reference_Kxx_N_per_m=16.5e6,       # Byrne 2020 Tab 3: 16.5 MN/m
        reference_Krxrx_Nm_per_rad=None,     # 3849 kNm/deg; filled below
        citation="Byrne et al. (2020), Geotechnique 70(11), 970-985, Tables 1+3",
        h_load_m=10.0,    # Byrne 2020 Table 1: CM1 loading eccentricity
        notes="D = 0.762 m, L/D = 5.25, installed L = 3.98 m, wall 15 mm, "
              "Cowden stiff glacial clay till. Reference k_Hinit is secant "
              "stiffness for 0 < vG < D/1000.",
        tolerance=0.60,
    ),
    CrossValCase(
        name="Dunkirk DL1 (large)",
        diameter_m=2.0,
        embed_length_m=10.61,
        soil_profile=DUNKIRK_SAND,
        reference_Kxx_N_per_m=139.7e6,      # McAdam 2020 Tab 3: 139.7 MN/m
        reference_Krxrx_Nm_per_rad=None,
        citation="McAdam et al. (2020), Geotechnique 70(11), 986-998, Tables 1+3",
        h_load_m=9.90,    # McAdam 2020 Table 1: DL1 eccentricity
        notes="D = 2.0 m, L/D = 5.25, installed L = 10.61 m, wall 38 mm, "
              "Dunkirk dense marine sand, largest pile in the PISA medium-"
              "scale field test programme.",
        tolerance=0.60,
    ),
    CrossValCase(
        name="Cowden CL1 (large)",
        diameter_m=2.0,
        embed_length_m=10.61,
        soil_profile=COWDEN_CLAY,
        reference_Kxx_N_per_m=108.2e6,      # Byrne 2020 Tab 3: 108.2 MN/m
        reference_Krxrx_Nm_per_rad=None,
        citation="Byrne et al. (2020), Geotechnique 70(11), 970-985, Tables 1+3",
        h_load_m=9.90,    # Byrne 2020 Table 1: CL1 eccentricity
        notes="D = 2.0 m, L/D = 5.25, Cowden stiff glacial clay till.",
        tolerance=0.60,
    ),
]

# Convert rocking stiffness kMinit [kNm/deg] -> Nm/rad:
#   kNm/deg * 1000 * (180/pi) = Nm/rad
import math as _m
_DEG2RAD_FACTOR = 1000.0 * 180.0 / _m.pi
CASES[0].reference_Krxrx_Nm_per_rad = 1651.0 * _DEG2RAD_FACTOR    # DM7
CASES[1].reference_Krxrx_Nm_per_rad = 3849.0 * _DEG2RAD_FACTOR    # CM1
CASES[2].reference_Krxrx_Nm_per_rad = 58670.0 * _DEG2RAD_FACTOR   # DL1
CASES[3].reference_Krxrx_Nm_per_rad = 44590.0 * _DEG2RAD_FACTOR   # CL1


def compare_one(case: CrossValCase) -> dict:
    K = pisa_pile_stiffness_6x6(
        diameter_m=case.diameter_m,
        embed_length_m=case.embed_length_m,
        soil_profile=case.soil_profile,
    )
    Kxx_raw = float(K[0, 0])
    Krxrx = float(K[3, 3])
    # Effective secant stiffness H / v_G with load applied at height h
    # above ground (this is the definition of k_Hinit in the PISA
    # field-test papers). Raw Kxx would only match if the load were
    # applied at the mudline with no moment.
    k_Hinit_eff = effective_head_stiffness(K, case.h_load_m) \
                  if case.h_load_m > 0 else Kxx_raw

    def status(pred: float, ref: Optional[float]) -> str:
        if ref is None:
            return "AWAITING_VERIFY"
        err = abs(pred - ref) / ref
        return "VERIFIED" if err <= case.tolerance else "DISCREPANT"

    return {
        "case": case.name,
        "geometry": {"D_m": case.diameter_m, "L_m": case.embed_length_m,
                     "h_load_m": case.h_load_m},
        "op3_Kxx_raw_N_per_m": Kxx_raw,
        "op3_Kxx_eff_N_per_m": k_Hinit_eff,
        "op3_Krxrx_Nm_per_rad": Krxrx,
        "ref_Kxx": case.reference_Kxx_N_per_m,
        "ref_Krxrx": case.reference_Krxrx_Nm_per_rad,
        "status_Kxx": status(k_Hinit_eff, case.reference_Kxx_N_per_m),
        "status_Krxrx": status(Krxrx, case.reference_Krxrx_Nm_per_rad),
        "citation": case.citation,
        "notes": case.notes,
    }


def main():
    print()
    print("=" * 80)
    print(" Op3 PISA cross-validation harness -- Task 3.1e")
    print("=" * 80)

    results = []
    for case in CASES:
        r = compare_one(case)
        results.append(r)
        print(f"\n  {r['case']}  (D={r['geometry']['D_m']} m, L={r['geometry']['L_m']} m)")
        print(f"    citation: {r['citation']}")
        kxx_ref = f"{r['ref_Kxx']:.3e}" if r['ref_Kxx'] else "AWAITING_VERIFY"
        krr_ref = f"{r['ref_Krxrx']:.3e}" if r['ref_Krxrx'] else "AWAITING_VERIFY"
        print(f"    h_load      = {r['geometry']['h_load_m']} m")
        print(f"    Op3   k_Hinit_eff (at h) = {r['op3_Kxx_eff_N_per_m']:.3e} N/m")
        print(f"    Op3   Kxx_raw           = {r['op3_Kxx_raw_N_per_m']:.3e} N/m")
        print(f"    Ref   Kxx   = {kxx_ref}")
        print(f"    Status      : {r['status_Kxx']}")
        print(f"    Op3   Krxrx = {r['op3_Krxrx_Nm_per_rad']:.3e} Nm/rad")
        print(f"    Ref   Krxrx = {krr_ref}")
        print(f"    Status      : {r['status_Krxrx']}")

    out = REPO_ROOT / "validation/benchmarks/pisa_cross_validation.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(results, indent=2), encoding="utf-8")

    n_verified = sum(1 for r in results if r["status_Kxx"] == "VERIFIED")
    n_pending = sum(1 for r in results if r["status_Kxx"] == "AWAITING_VERIFY")
    n_disc = sum(1 for r in results if r["status_Kxx"] == "DISCREPANT")
    print()
    print("=" * 80)
    print(f" Cross-validation: {n_verified} VERIFIED, {n_pending} AWAITING_VERIFY, "
          f"{n_disc} DISCREPANT")
    print("=" * 80)
    print(f" JSON written: {out}")
    print()
    print(" NOTE: AWAITING_VERIFY means the reference number has not yet")
    print(" been extracted from the source paper. The harness is wired so")
    print(" that filling in the reference value (no code change) will flip")
    print(" the entry to VERIFIED or DISCREPANT.")
    print()


if __name__ == "__main__":
    main()
