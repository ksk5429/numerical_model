#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Cross-Validation Benchmarks: Field Trials + OxCaisson Head-to-Head
==================================================================

Benchmark A: Houlsby 2005/2006 field stiffness prediction
  - Bothkennar clay (Houlsby 2005): D=3m, L=1.5m, soft clay
  - Luce Bay sand (Houlsby 2006): D=3m, L=1.5m, dense sand

Benchmark B: Op3 Gazetas vs Doherty (2005) normalised coefficients
  - Compare Gazetas (1991) and OWA against Doherty's published values
  - Jalbi 2018 Table 3a reference data

Author: Op3 validation pipeline
"""
import sys
import json
import numpy as np
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from op3.optumgx_interface.step2_gazetas_stiffness import (
    efthymiou_2018_homogeneous,
    efthymiou_2018_gibson,
    surface_stiffness,
)
from op3.standards.api_rp_2geo import gazetas_full_6x6
from op3.standards.owa_bearing import owa_suction_bucket_stiffness


SEPARATOR = "=" * 72


def pct_diff(predicted, measured):
    """Percentage difference: (predicted - measured) / measured * 100."""
    return (predicted - measured) / measured * 100.0


# =====================================================================
# BENCHMARK A: Field Trial Stiffness Prediction
# =====================================================================
def benchmark_a():
    print(f"\n{SEPARATOR}")
    print("BENCHMARK A: Field Trial Stiffness Prediction")
    print(SEPARATOR)

    results = {}

    # -----------------------------------------------------------------
    # A1: Bothkennar Clay (Houlsby 2005)
    # -----------------------------------------------------------------
    print("\n--- A1: Bothkennar Clay (Houlsby et al. 2005) ---")
    print("  Site: Bothkennar, Scotland (soft clay)")
    print("  Foundation: D = 3.0 m, L = 1.5 m, L/D = 0.5")

    D = 3.0
    R = D / 2.0
    L = 1.5
    H = 20.0   # stratum depth (conservative)
    nu = 0.5   # undrained

    # su profile: su = 15 + 1.9*z kPa
    # G0 ~ 250 * su (typical soft clay correlation)
    # Representative depths for homogeneous model: mid-depth z = L/2 = 0.75m
    z_mid = L / 2.0
    z_tip = L
    su_mid = 15.0 + 1.9 * z_mid   # kPa
    su_tip = 15.0 + 1.9 * z_tip   # kPa
    su_surface = 15.0              # kPa
    G_mid = 250.0 * su_mid         # kPa
    G_tip = 250.0 * su_tip         # kPa
    G_surface = 250.0 * su_surface # kPa

    # Weighted average G (simple trapezoidal over [0, L])
    nz = 50
    z_arr = np.linspace(0, L, nz)
    su_arr = 15.0 + 1.9 * z_arr
    G_arr = 250.0 * su_arr
    G_mean = np.mean(G_arr)

    print(f"\n  Soil profile: su = 15 + 1.9*z kPa")
    print(f"  G0 = 250 * su")
    print(f"  G at surface:  {G_surface:.0f} kPa ({G_surface/1000:.1f} MPa)")
    print(f"  G at mid-depth: {G_mid:.0f} kPa ({G_mid/1000:.1f} MPa)")
    print(f"  G at tip:      {G_tip:.0f} kPa ({G_tip/1000:.1f} MPa)")
    print(f"  G mean [0,L]:  {G_mean:.0f} kPa ({G_mean/1000:.1f} MPa)")
    print(f"  nu = {nu}, H = {H} m")

    # Published measured rotational stiffness
    Kr_measured = 225.0  # MNm/rad

    # Method 1: Homogeneous (mean G)
    Kv_hom, Kh_hom, Kr_hom, Khr_hom = efthymiou_2018_homogeneous(
        G_mean, nu, R, L, H
    )
    print(f"\n  [Efthymiou Homogeneous, G_mean = {G_mean:.0f} kPa]")
    print(f"    Kv  = {Kv_hom/1000:.2f} MN/m")
    print(f"    Kh  = {Kh_hom/1000:.2f} MN/m")
    print(f"    Kr  = {Kr_hom/1000:.2f} MNm/rad")
    print(f"    Khr = {Khr_hom/1000:.2f} MN")
    print(f"    Kr vs measured: {pct_diff(Kr_hom/1000, Kr_measured):+.1f}%")

    # Method 2: Gibson (linearly increasing G)
    # G(z) = lambda*z, so G_L = G at tip depth
    # But Bothkennar has su = 15 + 1.9*z, so G(0) != 0
    # Gibson model assumes G(0) = 0. Use G_tip as G_L anyway.
    Kv_gib, Kh_gib, Kr_gib, Khr_gib = efthymiou_2018_gibson(
        G_tip, nu, R, L, H
    )
    print(f"\n  [Efthymiou Gibson, G_tip = {G_tip:.0f} kPa]")
    print(f"    Kv  = {Kv_gib/1000:.2f} MN/m")
    print(f"    Kh  = {Kh_gib/1000:.2f} MN/m")
    print(f"    Kr  = {Kr_gib/1000:.2f} MNm/rad")
    print(f"    Khr = {Khr_gib/1000:.2f} MN")
    print(f"    Kr vs measured: {pct_diff(Kr_gib/1000, Kr_measured):+.1f}%")
    print(f"    NOTE: Gibson assumes G(0)=0; Bothkennar has su(0)=15 kPa")

    # Method 3: OWA Houlsby & Byrne (2005)
    K_owa = owa_suction_bucket_stiffness(
        diameter_m=D, skirt_length_m=L, n_buckets=1,
        G=G_mean, nu=nu
    )
    Kr_owa = K_owa[3, 3]
    Kh_owa = K_owa[0, 0]
    Kv_owa = K_owa[2, 2]
    print(f"\n  [OWA / Houlsby & Byrne 2005, G_mean = {G_mean:.0f} kPa]")
    print(f"    Kv  = {Kv_owa/1000:.2f} MN/m")
    print(f"    Kh  = {Kh_owa/1000:.2f} MN/m")
    print(f"    Kr  = {Kr_owa/1000:.2f} MNm/rad")
    print(f"    Kr vs measured: {pct_diff(Kr_owa/1000, Kr_measured):+.1f}%")

    results["A1_bothkennar"] = {
        "site": "Bothkennar clay",
        "D_m": D, "L_m": L, "L_over_D": L / D,
        "G_mean_kPa": round(G_mean, 1),
        "nu": nu,
        "measured_Kr_MNm_rad": Kr_measured,
        "efthymiou_homogeneous": {
            "Kr_MNm_rad": round(Kr_hom / 1000, 2),
            "pct_diff": round(pct_diff(Kr_hom / 1000, Kr_measured), 1),
        },
        "efthymiou_gibson": {
            "Kr_MNm_rad": round(Kr_gib / 1000, 2),
            "pct_diff": round(pct_diff(Kr_gib / 1000, Kr_measured), 1),
        },
        "owa_houlsby_byrne": {
            "Kr_MNm_rad": round(Kr_owa / 1000, 2),
            "pct_diff": round(pct_diff(Kr_owa / 1000, Kr_measured), 1),
        },
    }

    # -----------------------------------------------------------------
    # A2: Luce Bay Sand (Houlsby 2006)
    # -----------------------------------------------------------------
    print(f"\n--- A2: Luce Bay Sand (Houlsby et al. 2006) ---")
    print("  Site: Luce Bay, Scotland (dense sand)")
    print("  Foundation: D = 3.0 m, L = 1.5 m, L/D = 0.5")

    D = 3.0
    R = D / 2.0
    L = 1.5
    H = 20.0
    nu = 0.3

    # Dense sand: Dr = 80-85%, phi = 45 deg
    # G/pa = 2500*sqrt(p'/pa), pa = 101 kPa
    # At mid-depth z = 0.75 m:
    #   gamma' ~ 10.3 kN/m3, sigma'_v = 10.3 * 0.75 = 7.725 kPa
    #   K0 ~ 1 - sin(45) = 0.293, p' = sigma'_v*(1+2*K0)/3
    pa = 101.0  # kPa
    gamma_prime = 10.3  # kN/m3
    phi = 45.0  # degrees
    K0 = 1.0 - np.sin(np.radians(phi))

    z_mid = 0.75
    sigma_v_mid = gamma_prime * z_mid
    p_prime_mid = sigma_v_mid * (1.0 + 2.0 * K0) / 3.0
    G_mid_sand = 2500.0 * pa * np.sqrt(p_prime_mid / pa)

    z_tip = 1.5
    sigma_v_tip = gamma_prime * z_tip
    p_prime_tip = sigma_v_tip * (1.0 + 2.0 * K0) / 3.0
    G_tip_sand = 2500.0 * pa * np.sqrt(p_prime_tip / pa)

    # Mean G over [0, L]
    nz = 100
    z_arr = np.linspace(0.01, L, nz)  # avoid z=0 singularity
    sigma_v_arr = gamma_prime * z_arr
    p_prime_arr = sigma_v_arr * (1.0 + 2.0 * K0) / 3.0
    G_arr = 2500.0 * pa * np.sqrt(p_prime_arr / pa)
    G_mean_sand = np.mean(G_arr)

    print(f"\n  Soil: Dr = 80-85%, phi = {phi} deg")
    print(f"  gamma' = {gamma_prime} kN/m3, K0 = {K0:.3f}")
    print(f"  G/pa = 2500*sqrt(p'/pa)")
    print(f"  G at mid-depth (z=0.75m): {G_mid_sand/1000:.1f} MPa")
    print(f"  G at tip (z=1.5m):        {G_tip_sand/1000:.1f} MPa")
    print(f"  G mean [0.01,L]:          {G_mean_sand/1000:.1f} MPa")
    print(f"  nu = {nu}, H = {H} m")

    # Method 1: Homogeneous (mean G)
    Kv_hom, Kh_hom, Kr_hom, Khr_hom = efthymiou_2018_homogeneous(
        G_mean_sand, nu, R, L, H
    )
    print(f"\n  [Efthymiou Homogeneous, G_mean = {G_mean_sand/1000:.1f} MPa]")
    print(f"    Kv  = {Kv_hom/1000:.2f} MN/m")
    print(f"    Kh  = {Kh_hom/1000:.2f} MN/m")
    print(f"    Kr  = {Kr_hom/1000:.2f} MNm/rad")
    print(f"    Khr = {Khr_hom/1000:.2f} MN")

    # Method 2: OWA
    K_owa = owa_suction_bucket_stiffness(
        diameter_m=D, skirt_length_m=L, n_buckets=1,
        G=G_mean_sand, nu=nu
    )
    Kr_owa_sand = K_owa[3, 3]
    Kh_owa_sand = K_owa[0, 0]
    Kv_owa_sand = K_owa[2, 2]
    print(f"\n  [OWA / Houlsby & Byrne 2005, G_mean = {G_mean_sand/1000:.1f} MPa]")
    print(f"    Kv  = {Kv_owa_sand/1000:.2f} MN/m")
    print(f"    Kh  = {Kh_owa_sand/1000:.2f} MN/m")
    print(f"    Kr  = {Kr_owa_sand/1000:.2f} MNm/rad")

    # Note: published Luce Bay stiffness from SEMV tests is harder to pin
    # to a single number; report predictions for comparison
    print(f"\n  NOTE: Luce Bay SEMV stiffness varies with load level.")
    print(f"  Reported range: Kr ~ 200-600 MNm/rad (load-dependent)")

    results["A2_luce_bay"] = {
        "site": "Luce Bay sand",
        "D_m": D, "L_m": L, "L_over_D": L / D,
        "G_mean_kPa": round(G_mean_sand, 1),
        "nu": nu,
        "efthymiou_homogeneous": {
            "Kv_MN_m": round(Kv_hom / 1000, 2),
            "Kh_MN_m": round(Kh_hom / 1000, 2),
            "Kr_MNm_rad": round(Kr_hom / 1000, 2),
        },
        "owa_houlsby_byrne": {
            "Kv_MN_m": round(Kv_owa_sand / 1000, 2),
            "Kh_MN_m": round(Kh_owa_sand / 1000, 2),
            "Kr_MNm_rad": round(Kr_owa_sand / 1000, 2),
        },
    }

    return results


# =====================================================================
# BENCHMARK B: OxCaisson Head-to-Head (Doherty 2005 vs Gazetas 1991)
# =====================================================================
def benchmark_b():
    print(f"\n{SEPARATOR}")
    print("BENCHMARK B: OxCaisson Head-to-Head Comparison")
    print("  Doherty (2005) vs Op3 Gazetas (1991) vs OWA")
    print(SEPARATOR)

    results = {}

    # Doherty (2005) normalised values from Jalbi 2018 Table 3a
    doherty_data = {
        "L/D=0.5": {
            "nu_0.2": {"KL_RG": 9.09, "KR_R3G": 16.77},
            "nu_0.5": {"KL_RG": 10.95, "KR_R3G": 20.06},
        },
        "L/D=1.0": {
            "nu_0.2": {"KL_RG": 12.5, "KR_R3G": 50.0},
        },
    }

    # Use unit values: R = 1 m, G = 1 kPa
    R_unit = 1.0  # m
    G_unit = 1.0  # kPa (unit value for normalisation)

    for ld_label, nu_cases in doherty_data.items():
        ld_ratio = float(ld_label.split("=")[1])
        D_unit = 2.0 * R_unit
        L_unit = ld_ratio * D_unit

        print(f"\n--- {ld_label} (D = {D_unit} m, L = {L_unit} m) ---")

        case_results = {}

        for nu_label, doh_vals in nu_cases.items():
            nu_val = float(nu_label.split("_")[1])
            if nu_val == 0.5:
                nu_val = 0.4999  # avoid division by zero in (1-nu)

            print(f"\n  nu = {nu_val}")
            print(f"  Doherty (2005):  KL/(R*G) = {doh_vals['KL_RG']:.2f}"
                  f"   KR/(R^3*G) = {doh_vals['KR_R3G']:.2f}")

            # --- Op3 Gazetas (1991) via gazetas_full_6x6 ---
            K_gaz = gazetas_full_6x6(
                radius_m=R_unit,
                embedment_m=L_unit,
                G=G_unit,
                nu=nu_val,
            )
            KL_gaz = K_gaz[0, 0]  # Kxx (lateral)
            KR_gaz = K_gaz[3, 3]  # Krxx (rocking)

            # Normalise
            KL_norm_gaz = KL_gaz / (R_unit * G_unit)
            KR_norm_gaz = KR_gaz / (R_unit**3 * G_unit)

            print(f"  Gazetas (1991):  KL/(R*G) = {KL_norm_gaz:.2f}"
                  f"   KR/(R^3*G) = {KR_norm_gaz:.2f}")
            print(f"    diff vs Doherty:  KL: {pct_diff(KL_norm_gaz, doh_vals['KL_RG']):+.1f}%"
                  f"   KR: {pct_diff(KR_norm_gaz, doh_vals['KR_R3G']):+.1f}%")

            # --- Op3 OWA / Houlsby & Byrne (2005) ---
            K_owa = owa_suction_bucket_stiffness(
                diameter_m=D_unit,
                skirt_length_m=L_unit,
                n_buckets=1,
                G=G_unit,
                nu=nu_val,
            )
            KL_owa = K_owa[0, 0]
            KR_owa = K_owa[3, 3]
            KL_norm_owa = KL_owa / (R_unit * G_unit)
            KR_norm_owa = KR_owa / (R_unit**3 * G_unit)

            print(f"  OWA (H&B 2005):  KL/(R*G) = {KL_norm_owa:.2f}"
                  f"   KR/(R^3*G) = {KR_norm_owa:.2f}")
            print(f"    diff vs Doherty:  KL: {pct_diff(KL_norm_owa, doh_vals['KL_RG']):+.1f}%"
                  f"   KR: {pct_diff(KR_norm_owa, doh_vals['KR_R3G']):+.1f}%")

            # --- Efthymiou homogeneous for comparison ---
            H_unit = 20.0  # arbitrary large stratum
            Kv_ef, Kh_ef, Kr_ef, Khr_ef = efthymiou_2018_homogeneous(
                G_unit, nu_val, R_unit, L_unit, H_unit
            )
            KL_norm_ef = Kh_ef / (R_unit * G_unit)
            KR_norm_ef = Kr_ef / (R_unit**3 * G_unit)

            print(f"  Efthymiou (2018): KL/(R*G) = {KL_norm_ef:.2f}"
                  f"   KR/(R^3*G) = {KR_norm_ef:.2f}")
            print(f"    diff vs Doherty:  KL: {pct_diff(KL_norm_ef, doh_vals['KL_RG']):+.1f}%"
                  f"   KR: {pct_diff(KR_norm_ef, doh_vals['KR_R3G']):+.1f}%")

            case_results[nu_label] = {
                "nu": nu_val,
                "doherty": doh_vals,
                "gazetas_1991": {
                    "KL_norm": round(KL_norm_gaz, 2),
                    "KR_norm": round(KR_norm_gaz, 2),
                    "KL_pct_diff": round(pct_diff(KL_norm_gaz, doh_vals["KL_RG"]), 1),
                    "KR_pct_diff": round(pct_diff(KR_norm_gaz, doh_vals["KR_R3G"]), 1),
                },
                "owa_houlsby_byrne": {
                    "KL_norm": round(KL_norm_owa, 2),
                    "KR_norm": round(KR_norm_owa, 2),
                    "KL_pct_diff": round(pct_diff(KL_norm_owa, doh_vals["KL_RG"]), 1),
                    "KR_pct_diff": round(pct_diff(KR_norm_owa, doh_vals["KR_R3G"]), 1),
                },
                "efthymiou_2018": {
                    "KL_norm": round(KL_norm_ef, 2),
                    "KR_norm": round(KR_norm_ef, 2),
                    "KL_pct_diff": round(pct_diff(KL_norm_ef, doh_vals["KL_RG"]), 1),
                    "KR_pct_diff": round(pct_diff(KR_norm_ef, doh_vals["KR_R3G"]), 1),
                },
            }

        results[ld_label] = case_results

    return results


# =====================================================================
# SUMMARY TABLE
# =====================================================================
def print_summary(results_a, results_b):
    print(f"\n{SEPARATOR}")
    print("SUMMARY")
    print(SEPARATOR)

    print("\n--- Benchmark A: Field Trial Prediction ---")
    print(f"{'Method':<28} {'Kr (MNm/rad)':>14} {'vs Measured':>12}")
    print("-" * 56)

    a1 = results_a["A1_bothkennar"]
    measured = a1["measured_Kr_MNm_rad"]
    print(f"{'Measured (Houlsby 2005)':<28} {measured:>14.1f} {'---':>12}")
    for method, key in [
        ("Efthymiou Homogeneous", "efthymiou_homogeneous"),
        ("Efthymiou Gibson", "efthymiou_gibson"),
        ("OWA (H&B 2005)", "owa_houlsby_byrne"),
    ]:
        kr = a1[key]["Kr_MNm_rad"]
        pct = a1[key]["pct_diff"]
        print(f"{method:<28} {kr:>14.1f} {pct:>+11.1f}%")

    print(f"\n--- Benchmark B: Normalised Stiffness Coefficients ---")
    print(f"{'Case':<22} {'Method':<20} {'KL/(RG)':>10} {'KR/(R3G)':>10} "
          f"{'dKL%':>8} {'dKR%':>8}")
    print("-" * 80)
    for ld_label, cases in results_b.items():
        for nu_label, data in cases.items():
            case_str = f"{ld_label}, {nu_label}"
            d = data["doherty"]
            print(f"{case_str:<22} {'Doherty (2005)':<20} "
                  f"{d['KL_RG']:>10.2f} {d['KR_R3G']:>10.2f} "
                  f"{'ref':>8} {'ref':>8}")
            for method, key in [
                ("Gazetas (1991)", "gazetas_1991"),
                ("OWA (H&B 2005)", "owa_houlsby_byrne"),
                ("Efthymiou (2018)", "efthymiou_2018"),
            ]:
                m = data[key]
                print(f"{'':<22} {method:<20} "
                      f"{m['KL_norm']:>10.2f} {m['KR_norm']:>10.2f} "
                      f"{m['KL_pct_diff']:>+7.1f}% {m['KR_pct_diff']:>+7.1f}%")
            print()


# =====================================================================
# MAIN
# =====================================================================
if __name__ == "__main__":
    print(SEPARATOR)
    print("Op3 CROSS-VALIDATION: Field Trials + OxCaisson Benchmark")
    print(SEPARATOR)

    results_a = benchmark_a()
    results_b = benchmark_b()
    print_summary(results_a, results_b)

    # Save results
    all_results = {
        "benchmark_a_field_trials": results_a,
        "benchmark_b_oxcaisson": results_b,
    }
    out_path = Path(__file__).parent / "field_oxcaisson_results.json"
    with open(out_path, "w") as f:
        json.dump(all_results, f, indent=2)
    print(f"\nResults saved to: {out_path.name}")
    print(SEPARATOR)
