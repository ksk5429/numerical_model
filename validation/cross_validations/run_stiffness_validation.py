"""
Analytical stiffness validation: Op³ Mode B vs published benchmarks.

Benchmarks:
  #16  Jalbi et al. (2018) — KL, KR for 5MW OWT (L=6m, D=12m, Es=40MPa)
  #17  Efthymiou & Gazetas (2018) — KH, KR (L=R=10m, G=5MPa)

These use the Op³ analytical stiffness functions (no OptumGX needed).

Usage:
    python validation/cross_validations/run_stiffness_validation.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from op3.standards.api_rp_2geo import gazetas_full_6x6
from op3.standards.owa_bearing import owa_suction_bucket_stiffness
from op3.optumgx_interface.step2_gazetas_stiffness import (
    efthymiou_2018_homogeneous,
)

OUT_DIR = Path(__file__).resolve().parent
RESULTS_FILE = OUT_DIR / "stiffness_validation_results.json"

results = {}


# ============================================================
# Benchmark #17: Gazetas (2018) closed-form stiffness
#   Design example: L = R = 10m, G = 5MPa, nu = 0.5
#   Published: KH = 955 MN/m, KR = 121,110 MNm/rad, KHR = 5,730 MN
# ============================================================
def run_gazetas_benchmark():
    """Compare Op³ Efthymiou & Gazetas (2018) against the published example."""
    print("\n[#17] Gazetas (2018) — closed-form stiffness")
    print("     L = R = 10m, G = 5 MPa, nu = 0.5, bedrock H = 30m")

    R = 10.0    # m (radius)
    L = 10.0    # m (skirt length = R)
    G = 5.0     # MPa
    nu = 0.5
    H = 30.0    # m (bedrock depth)

    # Op³ implementation
    Kv, Kh, Kr, Khr = efthymiou_2018_homogeneous(
        G * 1000,  # MPa -> kPa
        nu, R, L, H
    )

    # Convert from kN units to MN
    Kh_MN = Kh / 1000
    Kr_MNm = Kr / 1000
    Khr_MN = Khr / 1000

    # Published reference values
    ref_Kh = 955.0       # MN/m
    ref_Kr = 121110.0    # MNm/rad
    ref_Khr = 5730.0     # MN

    err_Kh = (Kh_MN - ref_Kh) / ref_Kh * 100
    err_Kr = (Kr_MNm - ref_Kr) / ref_Kr * 100
    err_Khr = (Khr_MN - ref_Khr) / ref_Khr * 100

    print(f"     KH:  Op³ = {Kh_MN:.1f} MN/m,  ref = {ref_Kh:.0f} MN/m,  error = {err_Kh:+.1f}%")
    print(f"     KR:  Op³ = {Kr_MNm:.1f} MNm/rad,  ref = {ref_Kr:.0f} MNm/rad,  error = {err_Kr:+.1f}%")
    print(f"     KHR: Op³ = {Khr_MN:.1f} MN,  ref = {ref_Khr:.0f} MN,  error = {err_Khr:+.1f}%")

    results["gazetas_2018"] = {
        "config": {"R_m": R, "L_m": L, "G_MPa": G, "nu": nu, "H_m": H},
        "KH": {"op3_MN_m": round(Kh_MN, 1), "ref_MN_m": ref_Kh,
                "error_pct": round(err_Kh, 1)},
        "KR": {"op3_MNm_rad": round(Kr_MNm, 1), "ref_MNm_rad": ref_Kr,
                "error_pct": round(err_Kr, 1)},
        "KHR": {"op3_MN": round(Khr_MN, 1), "ref_MN": ref_Khr,
                 "error_pct": round(err_Khr, 1)},
    }


# ============================================================
# Benchmark #16: Jalbi et al. (2018) impedance functions
#   5MW OWT: L = 6m, D = 12m, L/D = 0.5, Es = 40MPa (homogeneous)
#   Published: KL = 0.294 GN/m, KLR = 5.3 GN, KR = 44.0 GNm/rad
#   f_fixed = 0.26 Hz, f_flexible = 0.17 Hz
# ============================================================
def run_jalbi_benchmark():
    """Compare Op³ stiffness against Jalbi 2018 5MW example."""
    print("\n[#16] Jalbi (2018) — impedance functions")
    print("     L = 6m, D = 12m, L/D = 0.5, Es = 40 MPa")

    D = 12.0    # m
    R = D / 2   # m
    L = 6.0     # m (skirt length)
    Es = 40.0   # MPa (Young's modulus)
    nu = 0.3    # typical for sand/stiff clay
    G = Es / (2 * (1 + nu))  # shear modulus [MPa]
    H = 60.0    # stratum depth (conservative)

    # Jalbi published values
    ref_KL = 0.294   # GN/m
    ref_KR = 44.0    # GNm/rad
    ref_KLR = 5.3    # GN

    # --- Method 1: Efthymiou & Gazetas (2018) ---
    Kv, Kh, Kr, Khr = efthymiou_2018_homogeneous(
        G * 1000,  # MPa -> kPa
        nu, R, L, H
    )
    Kh_GN = Kh / 1e6       # kN -> GN
    Kr_GNm = Kr / 1e6      # kN.m -> GN.m
    Khr_GN = Khr / 1e6     # kN -> GN

    err_KL_e = (Kh_GN - ref_KL) / ref_KL * 100
    err_KR_e = (Kr_GNm - ref_KR) / ref_KR * 100

    print(f"\n  Method 1: Efthymiou & Gazetas (2018)")
    print(f"     KL:  Op³ = {Kh_GN:.4f} GN/m,  ref = {ref_KL} GN/m,  error = {err_KL_e:+.1f}%")
    print(f"     KR:  Op³ = {Kr_GNm:.2f} GNm/rad,  ref = {ref_KR} GNm/rad,  error = {err_KR_e:+.1f}%")
    print(f"     KLR: Op³ = {Khr_GN:.3f} GN,  ref = {ref_KLR} GN")

    # --- Method 2: Gazetas (1991) full 6x6 ---
    K66 = gazetas_full_6x6(
        radius_m=R,
        embedment_m=L,
        G=G * 1e6,  # MPa -> Pa
        nu=nu,
    )
    Kh_66 = K66[0, 0] / 1e9      # N/m -> GN/m
    Kr_66 = K66[3, 3] / 1e9      # Nm/rad -> GNm/rad
    Klr_66 = K66[0, 4] / 1e9     # N -> GN

    err_KL_g = (Kh_66 - ref_KL) / ref_KL * 100
    err_KR_g = (Kr_66 - ref_KR) / ref_KR * 100

    print(f"\n  Method 2: Gazetas (1991) full 6x6")
    print(f"     KL:  Op³ = {Kh_66:.4f} GN/m,  ref = {ref_KL} GN/m,  error = {err_KL_g:+.1f}%")
    print(f"     KR:  Op³ = {Kr_66:.2f} GNm/rad,  ref = {ref_KR} GNm/rad,  error = {err_KR_g:+.1f}%")
    print(f"     KLR: Op³ = {Klr_66:.3f} GN,  ref = {ref_KLR} GN")

    # --- Method 3: Houlsby & Byrne (OWA) ---
    K_owa = owa_suction_bucket_stiffness(
        diameter_m=D,
        skirt_length_m=L,
        G=G * 1e6,  # MPa -> Pa
        nu=nu,
    )
    Kh_owa = K_owa[0, 0] / 1e9
    Kr_owa = K_owa[3, 3] / 1e9

    err_KL_owa = (Kh_owa - ref_KL) / ref_KL * 100
    err_KR_owa = (Kr_owa - ref_KR) / ref_KR * 100

    print(f"\n  Method 3: Houlsby & Byrne (OWA)")
    print(f"     KL:  Op³ = {Kh_owa:.4f} GN/m,  ref = {ref_KL} GN/m,  error = {err_KL_owa:+.1f}%")
    print(f"     KR:  Op³ = {Kr_owa:.2f} GNm/rad,  ref = {ref_KR} GNm/rad,  error = {err_KR_owa:+.1f}%")

    results["jalbi_2018"] = {
        "config": {"D_m": D, "L_m": L, "L_D": L/D, "Es_MPa": Es,
                   "G_MPa": round(G, 2), "nu": nu, "H_m": H},
        "ref": {"KL_GN_m": ref_KL, "KR_GNm_rad": ref_KR, "KLR_GN": ref_KLR},
        "efthymiou_2018": {
            "KL_GN_m": round(Kh_GN, 4), "KR_GNm_rad": round(Kr_GNm, 2),
            "KLR_GN": round(Khr_GN, 3),
            "err_KL_pct": round(err_KL_e, 1), "err_KR_pct": round(err_KR_e, 1),
        },
        "gazetas_1991_6x6": {
            "KL_GN_m": round(Kh_66, 4), "KR_GNm_rad": round(Kr_66, 2),
            "KLR_GN": round(Klr_66, 3),
            "err_KL_pct": round(err_KL_g, 1), "err_KR_pct": round(err_KR_g, 1),
        },
        "houlsby_byrne_owa": {
            "KL_GN_m": round(Kh_owa, 4), "KR_GNm_rad": round(Kr_owa, 2),
            "err_KL_pct": round(err_KL_owa, 1), "err_KR_pct": round(err_KR_owa, 1),
        },
    }


# ============================================================
# Benchmark #16b: Jalbi vs Doherty (2005) validation table
#   Jalbi Table 3a: KL/(R*G_so) for L/D=0.5 and 2.0
# ============================================================
def run_jalbi_doherty_comparison():
    """Compare Op³ normalised stiffness against Jalbi Table 3a/3b."""
    print("\n[#16b] Jalbi (2018) Table 3 — normalised KL/(R·Gso)")

    cases = [
        {"L_D": 0.5, "nu": 0.2, "profile": "homogeneous",
         "doherty_KL_norm": 9.09, "jalbi_KL_norm": 9.08,
         "doherty_KR_norm": 16.77, "jalbi_KR_norm": 13.1},
        {"L_D": 2.0, "nu": 0.2, "profile": "homogeneous",
         "doherty_KL_norm": 18.04, "jalbi_KL_norm": 19.87,
         "doherty_KR_norm": 201.6, "jalbi_KR_norm": 187.41},
        {"L_D": 0.5, "nu": 0.4999, "profile": "homogeneous",
         "doherty_KL_norm": 10.95, "jalbi_KL_norm": 10.64,
         "doherty_KR_norm": 20.06, "jalbi_KR_norm": 15.21},
        {"L_D": 2.0, "nu": 0.4999, "profile": "homogeneous",
         "doherty_KL_norm": 22.61, "jalbi_KL_norm": 24.41,
         "doherty_KR_norm": 267.3, "jalbi_KR_norm": 227.64},
    ]

    # Use unit values for normalisation: G=1, R=1
    R = 1.0
    G = 1.0  # Pa (unit)

    table_rows = []
    for c in cases:
        L = c["L_D"] * 2 * R  # L = (L/D)*D = (L/D)*2R
        nu = c["nu"]

        # Op³ Gazetas 1991 (api_rp_2geo)
        K66 = gazetas_full_6x6(radius_m=R, embedment_m=L, G=G, nu=nu)
        KL_norm = K66[0, 0] / (R * G)
        KR_norm = K66[3, 3] / (R**3 * G)

        err_KL = (KL_norm - c["doherty_KL_norm"]) / c["doherty_KL_norm"] * 100

        print(f"  L/D={c['L_D']}, nu={nu}: "
              f"KL/(RG)={KL_norm:.2f} (Doherty={c['doherty_KL_norm']}, "
              f"Jalbi={c['jalbi_KL_norm']}), "
              f"err={err_KL:+.1f}%")

        table_rows.append({
            "L_D": c["L_D"], "nu": nu,
            "op3_KL_norm": round(KL_norm, 2),
            "doherty_KL_norm": c["doherty_KL_norm"],
            "jalbi_KL_norm": c["jalbi_KL_norm"],
            "op3_KR_norm": round(KR_norm, 2),
            "doherty_KR_norm": c["doherty_KR_norm"],
            "jalbi_KR_norm": c["jalbi_KR_norm"],
        })

    results["jalbi_doherty_table3"] = table_rows


def main():
    print("=" * 72)
    print(" Op³ Analytical Stiffness Validation")
    print("=" * 72)

    run_gazetas_benchmark()
    run_jalbi_benchmark()
    run_jalbi_doherty_comparison()

    # Save
    RESULTS_FILE.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(f"\nResults saved: {RESULTS_FILE}")
    print("=" * 72)
    return 0


if __name__ == "__main__":
    sys.exit(main())
