"""
OptumGX → OpenSeesPy Spring Parameter Extraction
==================================================
Reads raw plate pressure Excel files (output of extract_all.py or OptumGX GUI)
and produces depth-resolved p-y and t-z spring profiles for direct use in
OpenSeesPy BNWF model.

Input:
  - plates_H_scour{X}m.xlsx: Lateral probe plate pressures per scour depth
  - plates_V_scour{X}m.xlsx: Vertical probe plate pressures per scour depth

Output:
  - optumgx_spring_profile_scour{X}m.csv: Depth-resolved spring parameters
    Columns: z_m, k_py_N_m, p_ult_N, y50_m, k_tz_N_m, t_ult_N, z50_m

Method:
  For each depth bin (0.5m intervals):
    1. Select plate elements within the bin
    2. Sum lateral pressure * area → p(z) per unit length [N/m]
    3. Sum displacement → u(z) [m]
    4. p_ult = pressure at collapse, k_ini = p_ult / u at small displacement
    5. y50 = displacement at 50% of p_ult

Author: Kyeong Sun Kim
Date: 2026-03-31
"""

import numpy as np
import pandas as pd
from pathlib import Path
from typing import Tuple, Optional
import re
import json


# ==============================================================================
# CONFIGURATION
# ==============================================================================

PLATES_DIR = Path(r"F:\TREE_OF_THOUGHT\PHD\data\optumgx\raw_plates")
OUTPUT_DIR = Path(r"F:\TREE_OF_THOUGHT\PHD\data\optumgx\spring_profiles")

BUCKET_DIAMETER = 8.0
BUCKET_RADIUS = 4.0
BUCKET_LENGTH = 9.3
DZ = 0.5  # depth bin size (m)
DEPTH_BINS = np.arange(0, BUCKET_LENGTH + DZ / 2, DZ)

# Small-strain modifier (dynamic/static ratio)
SMALL_STRAIN_MODIFIER = 3.0


# ==============================================================================
# CORE EXTRACTION
# ==============================================================================

def read_plate_file(filepath: Path) -> pd.DataFrame:
    """Read an OptumGX plate pressure Excel file."""
    df = pd.read_excel(filepath)

    # Compute element centroids
    for coord in ['X', 'Y', 'Z']:
        cols = [f'{coord}_{i}' for i in [1, 2, 3]]
        if all(c in df.columns for c in cols):
            df[f'{coord}c'] = df[cols].mean(axis=1)

    # Compute element area (triangle: 0.5 * |cross product|)
    if all(f'{c}_{i}' in df.columns for c in ['X','Y','Z'] for i in [1,2,3]):
        v1 = np.array([
            df['X_2'] - df['X_1'],
            df['Y_2'] - df['Y_1'],
            df['Z_2'] - df['Z_1']
        ]).T
        v2 = np.array([
            df['X_3'] - df['X_1'],
            df['Y_3'] - df['Y_1'],
            df['Z_3'] - df['Z_1']
        ]).T
        cross = np.cross(v1, v2)
        df['area'] = 0.5 * np.linalg.norm(cross, axis=1)

    return df


def extract_lateral_springs(df: pd.DataFrame, depth_bins: np.ndarray
                            ) -> pd.DataFrame:
    """
    Extract lateral (p-y) spring parameters from H-probe plate pressures.

    For each depth bin:
      - p_ult = sum of (sigma_plus * area) over plates in bin → force per unit depth [N/m]
      - k_ini estimated from pressure/displacement ratio at collapse
      - y50 = p_ult / (2 * k_ini)
    """
    results = []

    for i in range(len(depth_bins)):
        z = depth_bins[i]
        z_lo = z - DZ / 2 if i > 0 else 0
        z_hi = z + DZ / 2

        # Select elements in this depth band (Z is negative, depth is positive)
        mask = (df['Zc'] >= -z_hi) & (df['Zc'] < -z_lo)
        band = df[mask]

        if len(band) == 0:
            results.append({
                'z_m': z, 'k_py_N_m': 0, 'p_ult_N': 0, 'y50_m': 0.001
            })
            continue

        # Lateral pressure: sigma_plus (normal pressure on +face) and tau (shear)
        # For H-probe: lateral force = integral of horizontal pressure over plate area
        sigma_cols = [c for c in band.columns if 'sigma_plus' in c]
        tau_cols = [c for c in band.columns if 'tau_plus' in c]

        # Mean pressure per element
        if sigma_cols:
            sigma_mean = band[sigma_cols].mean(axis=1).abs()
        else:
            sigma_mean = pd.Series(0, index=band.index)

        if tau_cols:
            tau_mean = band[tau_cols].mean(axis=1).abs()
        else:
            tau_mean = pd.Series(0, index=band.index)

        # Total lateral force = sum(pressure * area) for plates in this depth band
        # This gives force in N. Divide by DZ to get N/m.
        total_force = ((sigma_mean + tau_mean) * band['area']).sum()
        p_ult = total_force / DZ if DZ > 0 else total_force

        # Displacement at collapse (from displacement columns)
        disp_cols = [c for c in band.columns if 'displacements_total_displacements_u_x' in c
                     or 'displacements_total_displacements_u_y' in c]
        if disp_cols:
            u_mean = band[disp_cols].abs().mean(axis=1).mean()
        else:
            u_mean = 0.01  # fallback 10mm

        # Initial stiffness estimate
        if u_mean > 1e-6:
            k_ini = p_ult / u_mean * SMALL_STRAIN_MODIFIER
        else:
            k_ini = p_ult * 100  # fallback

        # y50 = displacement at 50% mobilization
        y50 = max(0.5 * p_ult / k_ini, 1e-6) if k_ini > 0 else 0.001

        results.append({
            'z_m': z,
            'k_py_N_m': k_ini,
            'p_ult_N': p_ult,
            'y50_m': y50,
            'n_elements': len(band),
            'mean_sigma_kPa': sigma_mean.mean() / 1000,
            'mean_disp_mm': u_mean * 1000,
        })

    return pd.DataFrame(results)


def extract_vertical_springs(df: pd.DataFrame, depth_bins: np.ndarray
                             ) -> pd.DataFrame:
    """
    Extract vertical (t-z) spring parameters from V-probe plate pressures.

    Similar to lateral but using vertical pressure/displacement components.
    """
    results = []

    for i in range(len(depth_bins)):
        z = depth_bins[i]
        z_lo = z - DZ / 2 if i > 0 else 0
        z_hi = z + DZ / 2

        mask = (df['Zc'] >= -z_hi) & (df['Zc'] < -z_lo)
        band = df[mask]

        if len(band) == 0:
            results.append({
                'z_m': z, 'k_tz_N_m': 0, 't_ult_N': 0, 'z50_m': 0.001
            })
            continue

        # Vertical: use sigma for normal (bearing) and tau for friction
        sigma_cols = [c for c in band.columns if 'sigma_plus' in c]
        tau_cols = [c for c in band.columns if 'tau_plus' in c]

        if sigma_cols:
            sigma_mean = band[sigma_cols].mean(axis=1).abs()
        else:
            sigma_mean = pd.Series(0, index=band.index)

        if tau_cols:
            tau_mean = band[tau_cols].mean(axis=1).abs()
        else:
            tau_mean = pd.Series(0, index=band.index)

        # For vertical probe: friction + bearing on skirt plates
        total_force = ((sigma_mean + tau_mean) * band['area']).sum()
        t_ult = total_force / DZ if DZ > 0 else total_force

        # Vertical displacement
        disp_cols = [c for c in band.columns if 'displacements_total_displacements_u_z' in c]
        if disp_cols:
            w_mean = band[disp_cols].abs().mean(axis=1).mean()
        else:
            w_mean = 0.01

        if w_mean > 1e-6:
            k_ini = t_ult / w_mean * SMALL_STRAIN_MODIFIER
        else:
            k_ini = t_ult * 100

        z50 = max(0.5 * t_ult / k_ini, 1e-6) if k_ini > 0 else 0.001

        results.append({
            'z_m': z,
            'k_tz_N_m': k_ini,
            't_ult_N': t_ult,
            'z50_m': z50,
            'n_elements': len(band),
        })

    return pd.DataFrame(results)


def process_scour_depth(scour_m: float, plates_dir: Path) -> Optional[pd.DataFrame]:
    """
    Process one scour depth: read H and V plate files, extract springs.
    Returns merged DataFrame with lateral + vertical spring profiles.
    """
    # Find matching files
    scour_str = f"{scour_m}m" if scour_m == int(scour_m) else f"{scour_m}m"
    # Handle different naming: scour0m, scour0.5m, scour1.0m, etc
    h_pattern = f"plates_H_scour{scour_str}.xlsx"
    v_pattern = f"plates_V_scour{scour_str}.xlsx"

    # Try exact match first, then fuzzy
    h_file = plates_dir / h_pattern
    v_file = plates_dir / v_pattern

    if not h_file.exists():
        # Try alternative naming
        candidates = list(plates_dir.glob(f"plates_H_scour{scour_m}*.xlsx"))
        h_file = candidates[0] if candidates else None
    if not v_file.exists():
        candidates = list(plates_dir.glob(f"plates_V_scour{scour_m}*.xlsx"))
        v_file = candidates[0] if candidates else None

    if h_file is None or not h_file.exists():
        print(f"  WARNING: No H-probe file for scour={scour_m}m")
        return None

    print(f"  Reading H-probe: {h_file.name}")
    df_h = read_plate_file(h_file)
    lat = extract_lateral_springs(df_h, DEPTH_BINS)

    if v_file is not None and v_file.exists():
        print(f"  Reading V-probe: {v_file.name}")
        df_v = read_plate_file(v_file)
        vert = extract_vertical_springs(df_v, DEPTH_BINS)
        merged = lat.merge(vert[['z_m', 'k_tz_N_m', 't_ult_N', 'z50_m']],
                           on='z_m', how='left')
    else:
        print(f"  WARNING: No V-probe file for scour={scour_m}m, using lateral as proxy")
        merged = lat.copy()
        merged['k_tz_N_m'] = lat['k_py_N_m'] * 0.5
        merged['t_ult_N'] = lat['p_ult_N'] * 0.5
        merged['z50_m'] = lat['y50_m']

    merged['scour_m'] = scour_m
    merged['S_D'] = scour_m / BUCKET_DIAMETER

    return merged


# ==============================================================================
# MAIN
# ==============================================================================

def main():
    print("=" * 65)
    print("  OptumGX → OpenSeesPy Spring Parameter Extraction")
    print(f"  Plates dir: {PLATES_DIR}")
    print(f"  Output dir: {OUTPUT_DIR}")
    print("=" * 65)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Find all available scour depths from filenames
    h_files = sorted(PLATES_DIR.glob("plates_H_scour*.xlsx"))
    scour_depths = []
    for f in h_files:
        m = re.search(r'scour([\d.]+)m', f.name)
        if m:
            scour_depths.append(float(m.group(1)))

    scour_depths = sorted(set(scour_depths))
    print(f"\n  Found {len(scour_depths)} scour depths: {scour_depths[:5]}...{scour_depths[-3:]}")

    # Process zero-scour first as reference
    all_profiles = []

    for sd in scour_depths:
        print(f"\n  Processing scour = {sd}m (S/D = {sd/BUCKET_DIAMETER:.3f})")
        profile = process_scour_depth(sd, PLATES_DIR)
        if profile is not None:
            out_file = OUTPUT_DIR / f"spring_profile_scour{sd}m.csv"
            profile.to_csv(out_file, index=False)
            all_profiles.append(profile)
            print(f"    Saved: {out_file.name}")
            print(f"    k_py range: {profile['k_py_N_m'].min():.0f} - {profile['k_py_N_m'].max():.0f} N/m")
            print(f"    p_ult range: {profile['p_ult_N'].min():.0f} - {profile['p_ult_N'].max():.0f} N")

    # Combine all into master file
    if all_profiles:
        master = pd.concat(all_profiles, ignore_index=True)
        master_file = OUTPUT_DIR / "master_spring_profiles.csv"
        master.to_csv(master_file, index=False)
        print(f"\n  Master file: {master_file}")
        print(f"  Total rows: {len(master)} ({len(scour_depths)} scour depths x {len(DEPTH_BINS)} depth bins)")

    # Summary
    print(f"\n{'='*65}")
    print(f"  DONE: {len(all_profiles)} scour depths processed")
    print(f"  Output: {OUTPUT_DIR}")
    print(f"{'='*65}")


if __name__ == '__main__':
    main()
