# -*- coding: utf-8 -*-
"""
BNWF Pipeline Step 2: Gmax(z) → Global Foundation Stiffness (Gazetas)
=====================================================================
Uses Efthymiou & Gazetas (2018) closed-form expressions specifically
calibrated for rigid suction caissons, plus the original Gazetas (1991)
surface stiffness formulae.

Supports both homogeneous and Gibson (linearly increasing G) soil.

Input:  results/gmax_profile.csv (from Step 1)
Output: results/gazetas_stiffness.json (Kv, Kh, Kr, Khr + metadata)
"""
import numpy as np
import pandas as pd
from pathlib import Path
import json

RESULTS_DIR = Path(__file__).parent / 'results'

# Foundation geometry
D = 8.0;  R = D / 2;  L = 9.3
NU = 0.3

# Stratum depth (depth to rigid base or very stiff layer)
# Estimate: typically 3-5x foundation depth for offshore clay/sand
H_STRATUM = 60.0  # m (conservative; adjust per site data)


# =============================================================================
# STIFFNESS FORMULAE
# =============================================================================
def surface_stiffness(G, nu, R):
    """Gazetas (1991) Table 15.1 — circular surface foundation."""
    Kv0 = 4 * G * R / (1 - nu)
    Kh0 = 8 * G * R / (2 - nu)
    Kr0 = 8 * G * R**3 / (3 * (1 - nu))
    return Kv0, Kh0, Kr0


def efthymiou_2018_homogeneous(G, nu, R, L, H):
    """
    Efthymiou & Gazetas (2018) — suction caisson in homogeneous soil.
    Reference point: center of lid (mudline).

    Parameters
    ----------
    G : float  — representative shear modulus [kPa or MPa, consistent units]
    nu : float — Poisson's ratio
    R : float  — caisson radius [m]
    L : float  — skirt length [m]
    H : float  — stratum depth [m]
    """
    Kv0, Kh0, Kr0 = surface_stiffness(G, nu, R)

    # Vertical
    Kv = Kv0 * (1 + 0.4 * (L/R)) * \
         (1 + 1.6 * (R/H)) * \
         (1 + (0.9 - 0.25 * (L/R)) * L / (H - L))

    # Horizontal
    Kh = Kh0 * (1 + 1.1 * (L/R)) * \
         (1 + 1.15 * (L/H))**0.65 * \
         (1 + 0.7 * (R/H))

    # Rocking
    Kr = Kr0 * (1 + L/R)**1.4 * \
         (1 + 0.15 * (R/H)) * \
         (1 + 0.95 * (L/R))

    # Cross-coupling (swaying-rocking)
    Khr = 0.6 * Kh * L

    return Kv, Kh, Kr, Khr


def efthymiou_2018_gibson(G_L, nu, R, L, H):
    """
    Efthymiou & Gazetas (2018) — suction caisson in Gibson soil.
    G(z) = lambda * z, so G_L = lambda * L at skirt tip.

    Parameters
    ----------
    G_L : float — shear modulus at skirt tip depth [kPa or MPa]
    """
    alpha = R / L  # heterogeneity parameter

    # Surface stiffness on Gibson soil (effective base modulus)
    Kv0 = 4 * G_L * R / (1 - nu) * (1 + 0.75 * alpha)
    Kh0 = 8 * G_L * R / (2 - nu) * (1 + 0.25 * alpha)
    Kr0 = 8 * G_L * R**3 / (3 * (1 - nu)) * (1 + 0.2 * alpha)

    # Embedment + stratum factors (Gibson-specific, Eqs. 11-14)
    Kv = Kv0 * (1 + 0.2 * (L/R)) * \
         (1 + 1.3 * (R/H)) * \
         (1 + (0.9 - 0.2 * (L/R)) * L / (H - L))

    Kh = Kh0 * (1 + 0.65 * (L/R)) * \
         (1 + 0.8 * (L/H))**0.7 * \
         (1 + 0.5 * (R/H))

    Kr = Kr0 * (1 + 0.75 * (L/R)) * \
         (1 + 0.5 * (L/H)) * \
         (1 + 0.1 * (R/H))**1.4

    Khr = 0.7 * L * Kh

    return Kv, Kh, Kr, Khr


# =============================================================================
# MAIN
# =============================================================================
if __name__ == "__main__":
    print("=" * 60)
    print("BNWF Pipeline Step 2: Gazetas/Efthymiou Stiffness")
    print("=" * 60)

    # Load Gmax profile from Step 1
    gmax_csv = RESULTS_DIR / 'gmax_profile.csv'
    if not gmax_csv.exists():
        raise FileNotFoundError(f"Run Step 1 first: {gmax_csv}")
    df = pd.read_csv(gmax_csv)

    G_surface = df.iloc[0]['G0_MPa']    # G at mudline
    G_tip = df.iloc[-1]['G0_MPa']       # G at skirt tip
    G_mid = df.loc[df['z_m'].sub(L/2).abs().idxmin(), 'G0_MPa']
    G_mean = df['G0_MPa'].mean()

    print(f"\n  Gmax from CPT:")
    print(f"    Surface: {G_surface:.1f} MPa")
    print(f"    Mid:     {G_mid:.1f} MPa")
    print(f"    Tip:     {G_tip:.1f} MPa")
    print(f"    Mean:    {G_mean:.1f} MPa")

    # --- Method A: Homogeneous soil (use weighted average G) ---
    # Weight towards deeper soil (more relevant for embedded foundation)
    weights = df['z_m'] + 0.5  # linear weight increasing with depth
    G_weighted = np.average(df['G0_MPa'], weights=weights)

    Kv_h, Kh_h, Kr_h, Khr_h = efthymiou_2018_homogeneous(
        G_weighted * 1000,  # MPa → kPa
        NU, R, L, H_STRATUM
    )

    print(f"\n  Method A: Homogeneous (G_weighted = {G_weighted:.1f} MPa)")
    print(f"    Kv  = {Kv_h/1000:.1f} MN/m")
    print(f"    Kh  = {Kh_h/1000:.1f} MN/m")
    print(f"    Kr  = {Kr_h/1000:.1f} MNm/rad")
    print(f"    Khr = {Khr_h/1000:.1f} MN")

    # --- Method B: Gibson soil (G increases linearly with depth) ---
    # Fit G(z) = lambda * z → lambda = G_tip / L
    # G_L = G at tip depth
    Kv_g, Kh_g, Kr_g, Khr_g = efthymiou_2018_gibson(
        G_tip * 1000,  # MPa → kPa
        NU, R, L, H_STRATUM
    )

    print(f"\n  Method B: Gibson (G_tip = {G_tip:.1f} MPa)")
    print(f"    Kv  = {Kv_g/1000:.1f} MN/m")
    print(f"    Kh  = {Kh_g/1000:.1f} MN/m")
    print(f"    Kr  = {Kr_g/1000:.1f} MNm/rad")
    print(f"    Khr = {Khr_g/1000:.1f} MN")

    # --- Select primary method ---
    # Check if Gibson is appropriate: G should increase with depth
    G_profile = df['G0_MPa'].values
    g_increasing = G_profile[-1] > G_profile[0]
    if g_increasing:
        primary = 'Gibson'
        Kv_p, Kh_p, Kr_p, Khr_p = Kv_g, Kh_g, Kr_g, Khr_g
    else:
        primary = 'Homogeneous (weighted)'
        Kv_p, Kh_p, Kr_p, Khr_p = Kv_h, Kh_h, Kr_h, Khr_h
        print(f"\n  NOTE: G0 does NOT increase with depth -> using Homogeneous")

    results = {
        'primary_method': f'{primary} (Efthymiou & Gazetas 2018)',
        'Kv_kN_m': round(Kv_p, 1),
        'Kh_kN_m': round(Kh_p, 1),
        'Kr_kNm_rad': round(Kr_p, 1),
        'Khr_kN': round(Khr_p, 1),
        'Kv_MN_m': round(Kv_p/1000, 2),
        'Kh_MN_m': round(Kh_p/1000, 2),
        'Kr_MNm_rad': round(Kr_p/1000, 2),
        'Khr_MN': round(Khr_p/1000, 2),
        'homogeneous': {
            'G_weighted_MPa': round(G_weighted, 2),
            'Kv_MN_m': round(Kv_h/1000, 2),
            'Kh_MN_m': round(Kh_h/1000, 2),
            'Kr_MNm_rad': round(Kr_h/1000, 2),
            'Khr_MN': round(Khr_h/1000, 2),
        },
        'gibson': {
            'G_tip_MPa': round(G_tip, 2),
            'Kv_MN_m': round(Kv_g/1000, 2),
            'Kh_MN_m': round(Kh_g/1000, 2),
            'Kr_MNm_rad': round(Kr_g/1000, 2),
            'Khr_MN': round(Khr_g/1000, 2),
        },
        'config': {
            'D': D, 'R': R, 'L': L, 'nu': NU,
            'H_stratum': H_STRATUM,
        },
    }

    json_path = RESULTS_DIR / 'gazetas_stiffness.json'
    with open(json_path, 'w') as f:
        json.dump(results, f, indent=2)

    print(f"\n  Saved: {json_path.name}")
    print("=" * 60)
