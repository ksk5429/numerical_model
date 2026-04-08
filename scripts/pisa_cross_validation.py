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

Important
---------
The reference small-strain stiffness values listed below are
PLACEHOLDERS marked AWAITING_VERIFY where the maintainer has not yet
opened the source paper to extract the precise number. Op^3 prints its
own prediction alongside, and the harness FLAGS each case as either
VERIFIED, AWAITING_VERIFY, or DISCREPANT. This is the honest state of
PISA cross-validation today: the framework runs end-to-end, but the
numerical comparison to published measurements is a backlog item that
must be completed before publication-grade claims are made.

The principle (from project memory): never fabricate measured data.
Print "AWAITING_VERIFY" rather than a guessed number.

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

from op3.standards.pisa import SoilState, pisa_pile_stiffness_6x6  # noqa: E402


@dataclass
class CrossValCase:
    name: str
    diameter_m: float
    embed_length_m: float
    soil_profile: list[SoilState]
    reference_Kxx_N_per_m: Optional[float]   # None = AWAITING_VERIFY
    reference_Krxrx_Nm_per_rad: Optional[float]
    citation: str
    notes: str = ""
    tolerance: float = 0.30   # 30% band on first cross-validation


# ---------------------------------------------------------------------------
# Published PISA test piles
# ---------------------------------------------------------------------------

# Dunkirk Pleistocene marine sand at the PISA test site
# Byrne 2020 Table 1: G_max varies linearly with depth, ~70-150 MPa
DUNKIRK_SAND = [
    SoilState(0.0,  7.0e7, 35.0, "sand"),
    SoilState(5.0,  9.0e7, 35.0, "sand"),
    SoilState(10.0, 1.2e8, 35.0, "sand"),
    SoilState(11.0, 1.4e8, 35.0, "sand"),
]

# Cowden glacial till
# Burd 2020 Table 1: su ~ 80-150 kPa, G_max ~ 30-80 MPa
COWDEN_CLAY = [
    SoilState(0.0,  3.0e7, 80.0e3, "clay"),
    SoilState(5.0,  5.0e7, 110.0e3, "clay"),
    SoilState(10.0, 7.0e7, 140.0e3, "clay"),
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
        diameter_m=2.0,
        embed_length_m=10.6,
        soil_profile=DUNKIRK_SAND,
        reference_Kxx_N_per_m=None,
        reference_Krxrx_Nm_per_rad=None,
        citation="Byrne et al. (2020), Geotechnique 70(11), 1048-1066",
        notes="Medium-scale PISA JIP test pile in dense Dunkirk marine sand. "
              "Reference K_ini values pending extraction from Figure 8 / Table 4.",
    ),
    CrossValCase(
        name="Cowden CM1",
        diameter_m=0.762,
        embed_length_m=2.27,
        soil_profile=COWDEN_CLAY,
        reference_Kxx_N_per_m=None,
        reference_Krxrx_Nm_per_rad=None,
        citation="Burd et al. (2020), Geotechnique 70(11), 1030-1047",
        notes="Medium-scale PISA JIP test pile in Cowden glacial till. "
              "Reference K_ini values pending extraction from Figure 9 / Table 4.",
    ),
    CrossValCase(
        name="Borkum Riffgrund-1 demonstrator",
        diameter_m=8.0,
        embed_length_m=30.0,
        soil_profile=BORKUM_PROFILE,
        reference_Kxx_N_per_m=None,
        reference_Krxrx_Nm_per_rad=None,
        citation="Murphy et al. (2018), Marine Structures 60, 263-281",
        notes="Full-scale demonstrator monopile, layered north sea profile. "
              "Reference K_ini values pending extraction.",
    ),
]


def compare_one(case: CrossValCase) -> dict:
    K = pisa_pile_stiffness_6x6(
        diameter_m=case.diameter_m,
        embed_length_m=case.embed_length_m,
        soil_profile=case.soil_profile,
    )
    Kxx = float(K[0, 0])
    Krxrx = float(K[3, 3])

    def status(pred: float, ref: Optional[float]) -> str:
        if ref is None:
            return "AWAITING_VERIFY"
        err = abs(pred - ref) / ref
        return "VERIFIED" if err <= case.tolerance else "DISCREPANT"

    return {
        "case": case.name,
        "geometry": {"D_m": case.diameter_m, "L_m": case.embed_length_m},
        "op3_Kxx_N_per_m": Kxx,
        "op3_Krxrx_Nm_per_rad": Krxrx,
        "ref_Kxx": case.reference_Kxx_N_per_m,
        "ref_Krxrx": case.reference_Krxrx_Nm_per_rad,
        "status_Kxx": status(Kxx, case.reference_Kxx_N_per_m),
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
        print(f"    Op3   Kxx   = {r['op3_Kxx_N_per_m']:.3e} N/m")
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
