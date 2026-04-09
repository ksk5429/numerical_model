# -*- coding: utf-8 -*-
"""
BNWF Pipeline Step 1: CPT Data → Gmax(z) Profile
=================================================
Reads CPT-3.xlsx, applies calibrated Vs-qt correlation from BH-3 SPS
logging, computes small-strain shear modulus G0(z) at 0.5m intervals
over the skirt depth.

Input:  CPT-3.xlsx (cone resistance qt vs depth)
Output: results/gmax_profile.csv
        results/gmax_profile.json (summary + metadata)
"""
import numpy as np
import pandas as pd
from scipy import interpolate
from pathlib import Path
import json

# =============================================================================
# CONFIGURATION
# =============================================================================
PROJECT_ROOT = Path(__file__).parent.parent.parent  # f:/FEM/OPTUM
RESULTS_DIR = Path(__file__).parent / 'results'
RESULTS_DIR.mkdir(exist_ok=True)

CPT_FILE = PROJECT_ROOT / 'site_data' / 'CPT-3.xlsx'

# Foundation geometry
D = 8.0         # diameter [m]
R = D / 2
L_SKIRT = <REDACTED_SKIRT_L>  # (proprietary, loaded at runtime) depth [m]
DZ = 0.5        # discretization [m]

# Water and soil constants
GAMMA_WATER = 10.25     # seawater [kN/m3]
GAMMA_SAT = 20.0        # saturated unit weight [kN/m3]  (approx)
GAMMA_SUB = GAMMA_SAT - GAMMA_WATER  # ~9.75 kN/m3

# Calibrated Vs-qt correlation from BH-3 SPS logging
# (from scripts/calibrate_soil_parameters.py)
VS_A = 85.0             # Vs = A * qt^B  [m/s, MPa]
VS_B = 0.25
RHO_SOIL = 1.85         # bulk density [g/cm3 = Mg/m3]
NU = 0.3                # Poisson's ratio

# Seabed depth (for sigma_v calculation)
WATER_DEPTH = 14.0      # m (SiteA site approximate)
MUDLINE_DEPTH = 0.0     # reference: mudline = 0


# =============================================================================
# FUNCTIONS
# =============================================================================
def load_cpt(filepath):
    """Load CPT data and return (depth_m, qt_MPa) arrays."""
    print(f"  Loading CPT: {filepath.name}")

    df = None
    for sheet in ['Data', 'data', 'Sheet1', 0]:
        for header_row in [4, 3, 5, 0, 1, 2]:
            try:
                df_try = pd.read_excel(filepath, sheet_name=sheet,
                                       header=header_row)
                cols = [str(c).lower() for c in df_try.columns]
                if any('depth' in c or 'deep' in c for c in cols):
                    df = df_try
                    break
            except Exception:
                continue
        if df is not None:
            break

    if df is None:
        raise ValueError(f"Could not parse CPT data from {filepath}")

    # Find depth and qt columns
    cols = df.columns
    depth_col = qt_col = None
    for c in cols:
        cl = str(c).lower()
        if 'depth' in cl or cl == 'm':
            depth_col = c
        if 'qt' in cl or 'qc' in cl or 'cone' in cl:
            qt_col = c

    # Fallback: assume first col = depth, second or third = qt
    if depth_col is None:
        depth_col = cols[0]
    if qt_col is None:
        for c in cols[1:]:
            vals = pd.to_numeric(df[c], errors='coerce').dropna()
            if len(vals) > 10 and vals.mean() > 0.1:
                qt_col = c
                break

    depth = pd.to_numeric(df[depth_col], errors='coerce').dropna().values
    qt = pd.to_numeric(df[qt_col], errors='coerce').reindex(
        df[depth_col].dropna().index).dropna().values

    # Align lengths
    n = min(len(depth), len(qt))
    depth, qt = depth[:n], qt[:n]

    # Remove invalid
    mask = (depth > 0) & (qt > 0) & np.isfinite(depth) & np.isfinite(qt)
    depth, qt = depth[mask], qt[mask]

    # Convert qt to MPa if needed (CPT files often in kPa or MPa)
    if qt.mean() > 100:  # likely in kPa
        qt = qt / 1000

    print(f"  Parsed {len(depth)} valid points, "
          f"depth=[{depth.min():.1f}, {depth.max():.1f}]m, "
          f"qt=[{qt.min():.2f}, {qt.max():.2f}] MPa")
    return depth, qt


def compute_gmax_profile(depth_cpt, qt_cpt):
    """
    Compute Gmax(z) profile at 0.5m intervals over the skirt depth.

    Pipeline:
      qt(z) → Vs = A * qt^B → G0 = rho * Vs^2

    Returns DataFrame with columns:
      z, qt_MPa, Vs_ms, G0_MPa, E0_MPa, sigma_v_kPa
    """
    # Interpolate CPT to regular grid
    # CRITICAL: CPT may not cover full skirt depth (e.g. data starts at 4.7m)
    # For depths ABOVE the shallowest CPT point: use constant (boundary value)
    # For depths BELOW the deepest CPT point: use constant (boundary value)
    # NEVER extrapolate trends outside measured range
    z_nodes = np.arange(0, L_SKIRT + DZ/2, DZ)

    z_min_cpt = depth_cpt.min()
    z_max_cpt = depth_cpt.max()
    qt_at_boundary_shallow = np.mean(qt_cpt[depth_cpt < z_min_cpt + 0.5])
    qt_at_boundary_deep = np.mean(qt_cpt[depth_cpt > z_max_cpt - 0.5])

    qt_interp_fn = interpolate.interp1d(
        depth_cpt, qt_cpt, kind='linear',
        fill_value=(qt_at_boundary_shallow, qt_at_boundary_deep),
        bounds_error=False
    )
    qt_z = np.maximum(qt_interp_fn(z_nodes), 0.1)  # floor at 0.1 MPa

    # Flag which nodes have real data vs extrapolated
    has_data = (z_nodes >= z_min_cpt) & (z_nodes <= z_max_cpt)
    n_extrap = (~has_data).sum()
    if n_extrap > 0:
        print(f"  WARNING: {n_extrap}/{len(z_nodes)} nodes outside CPT range "
              f"[{z_min_cpt:.1f}, {z_max_cpt:.1f}]m - using boundary values")

    # Vs from calibrated correlation
    Vs = VS_A * qt_z**VS_B  # m/s

    # G0 = rho * Vs^2  (rho in Mg/m3, Vs in m/s → G0 in MPa)
    G0 = RHO_SOIL * Vs**2 / 1000  # MPa

    # E0 = 2 * G0 * (1 + nu)
    E0 = 2 * G0 * (1 + NU)

    # Effective vertical stress
    sigma_v = GAMMA_SUB * z_nodes  # kPa

    df = pd.DataFrame({
        'z_m': z_nodes,
        'qt_MPa': qt_z,
        'Vs_ms': Vs,
        'G0_MPa': G0,
        'G0_kPa': G0 * 1000,
        'E0_MPa': E0,
        'sigma_v_kPa': sigma_v,
    })
    return df


# =============================================================================
# MAIN
# =============================================================================
if __name__ == "__main__":
    print("=" * 60)
    print("BNWF Pipeline Step 1: CPT -> Gmax Profile")
    print("=" * 60)

    depth_cpt, qt_cpt = load_cpt(CPT_FILE)
    df = compute_gmax_profile(depth_cpt, qt_cpt)

    # Representative values
    G0_mean = df['G0_MPa'].mean()
    G0_tip = df.iloc[-1]['G0_MPa']
    G0_mid = df.loc[df['z_m'].sub(L_SKIRT/2).abs().idxmin(), 'G0_MPa']

    print(f"\n  Gmax profile ({len(df)} points, dz={DZ}m):")
    print(f"  {'z [m]':>7s}  {'qt [MPa]':>9s}  {'Vs [m/s]':>9s}  "
          f"{'G0 [MPa]':>9s}  {'sigma_v':>8s}")
    print("-" * 55)
    for _, r in df.iterrows():
        print(f"  {r['z_m']:7.1f}  {r['qt_MPa']:9.2f}  {r['Vs_ms']:9.1f}  "
              f"{r['G0_MPa']:9.1f}  {r['sigma_v_kPa']:8.1f}")

    print(f"\n  Summary:")
    print(f"    G0 at surface:   {df.iloc[0]['G0_MPa']:.1f} MPa")
    print(f"    G0 at mid-skirt: {G0_mid:.1f} MPa")
    print(f"    G0 at tip:       {G0_tip:.1f} MPa")
    print(f"    G0 mean:         {G0_mean:.1f} MPa")

    # Save
    csv_path = RESULTS_DIR / 'gmax_profile.csv'
    df.to_csv(csv_path, index=False)

    meta = {
        'source': str(CPT_FILE.name),
        'correlation': f'Vs = {VS_A} * qt^{VS_B}',
        'rho_soil': RHO_SOIL,
        'nu': NU,
        'D': D, 'L_skirt': L_SKIRT, 'dz': DZ,
        'n_points': len(df),
        'G0_surface_MPa': round(df.iloc[0]['G0_MPa'], 2),
        'G0_mid_MPa': round(G0_mid, 2),
        'G0_tip_MPa': round(G0_tip, 2),
        'G0_mean_MPa': round(G0_mean, 2),
    }
    json_path = RESULTS_DIR / 'gmax_profile.json'
    with open(json_path, 'w') as f:
        json.dump(meta, f, indent=2)

    print(f"\n  Saved: {csv_path.name}, {json_path.name}")
    print("=" * 60)
