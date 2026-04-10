# -*- coding: utf-8 -*-
"""
BNWF Pipeline Step 4: OptumGX Plate Pressures → p_ult(z), t_ult(z)
===================================================================
Reads the plate pressure Excel files from OptumGX VHM probes and
computes distributed capacity profiles for BNWF springs.

Uses net contact pressure method (sigma_plus - sigma_minus) on skirt
wall elements only, with lid/skirt/tip classification.

Input:  results_vhm_full/plates_Hmax.xlsx (from optumgx_vhm_full.py)
        results_vhm_full/plates_Vmax.xlsx
        results_vhm_full/plates_Mmax.xlsx
        results_vhm_full/summary.json
Output: results/capacity_profile.csv
        results/capacity_profile.json
"""
import numpy as np
import pandas as pd
from pathlib import Path
import json

RESULTS_DIR = Path(__file__).parent / 'results'
VHM_DIR = Path(__file__).parent.parent.parent / 'pipeline' / 'optumgx_probes' / 'results_vhm_full'

D = 8.0;  R = D / 2;  L = 9.3;  DZ = 0.5


def classify_parts(df):
    """Tag each plate element as lid, skirt_wall, or tip_zone."""
    df['Rc'] = np.sqrt(df['Xc']**2 + df['Yc']**2)
    df['part'] = 'unknown'
    df.loc[df['Zc'] > -0.3, 'part'] = 'lid'
    df.loc[(df['Zc'] < -0.3) & (df['Zc'] > -(L - 0.3)) &
           (df['Rc'] > R * 0.8), 'part'] = 'skirt_wall'
    df.loc[df['Zc'] < -(L - 0.3), 'part'] = 'tip_zone'
    return df


def add_geometry(df):
    """Compute centroid, area, and normal for triangular plate elements."""
    p1 = df[['X_1', 'Y_1', 'Z_1']].values
    p2 = df[['X_2', 'Y_2', 'Z_2']].values
    p3 = df[['X_3', 'Y_3', 'Z_3']].values
    df['Xc'] = (p1[:, 0] + p2[:, 0] + p3[:, 0]) / 3
    df['Yc'] = (p1[:, 1] + p2[:, 1] + p3[:, 1]) / 3
    df['Zc'] = (p1[:, 2] + p2[:, 2] + p3[:, 2]) / 3
    v1, v2 = p2 - p1, p3 - p1
    cross = np.cross(v1, v2)
    norms = np.maximum(np.linalg.norm(cross, axis=1, keepdims=True), 1e-20)
    df['area'] = norms.flatten() / 2
    df['nx'] = cross[:, 0] / norms.flatten()
    df['ny'] = cross[:, 1] / norms.flatten()
    df['nz'] = cross[:, 2] / norms.flatten()
    return classify_parts(df)


def pressure_profile(df, n_slices=20, part_filter='skirt_wall'):
    """
    Integrate net contact pressure on specified foundation part.

    sigma_net = sigma_plus - sigma_minus  (net normal pressure)
    tau_net = tau_plus + tau_minus         (net shear)

    dH = sigma_net * A * nx + tau_net * A * |nz|
    dV = sigma_net * A * nz + tau_net * A * (1 - |nz|)
    """
    sp = [c for c in df.columns if c.startswith('sigma_plus_')]
    sm = [c for c in df.columns if c.startswith('sigma_minus_')]
    tp = [c for c in df.columns if c.startswith('tau_plus_')]
    tm = [c for c in df.columns if c.startswith('tau_minus_')]

    df['sig_net'] = df[sp].mean(axis=1) - df[sm].mean(axis=1) if sp and sm else 0
    df['tau_net'] = df[tp].mean(axis=1) + df[tm].mean(axis=1) if tp and tm else 0

    df['dFx'] = df['sig_net'] * df['area'] * df['nx'] + \
                df['tau_net'] * df['area'] * abs(df['nz'])
    df['dFz'] = df['sig_net'] * df['area'] * df['nz'] + \
                df['tau_net'] * df['area'] * (1 - abs(df['nz']))

    # Filter to specified part
    df_part = df[df['part'] == part_filter] if part_filter else df

    z_min = df_part['Zc'].min() if len(df_part) > 0 else -L
    z_max = df_part['Zc'].max() if len(df_part) > 0 else 0
    bounds = np.linspace(z_max, z_min, n_slices + 1)

    rows = []
    for i in range(n_slices):
        zt, zb = bounds[i], bounds[i + 1]
        zm, dz = (zt + zb) / 2, abs(zt - zb)
        mask = (df_part['Zc'] <= zt) & (df_part['Zc'] > zb)
        sub = df_part[mask]

        H = sub['dFx'].sum()
        V = sub['dFz'].sum()

        rows.append({
            'z_mid': zm, 'dz': dz, 'n_elem': len(sub),
            'H_kN': H, 'V_kN': V,
            'p_kN_m': H / dz if dz > 0 else 0,
            't_kN_m': V / dz if dz > 0 else 0,
        })
    return pd.DataFrame(rows)


# =============================================================================
# MAIN
# =============================================================================
if __name__ == "__main__":
    print("=" * 60)
    print("BNWF Pipeline Step 4: OptumGX Capacity Profiles")
    print("=" * 60)

    # Load VHM summary
    with open(VHM_DIR / 'summary.json') as f:
        vhm = json.load(f)

    Vmax = vhm['capacities']['Vmax_half_kN']
    Hmax = vhm['capacities']['Hmax_half_kN']
    Mmax = vhm['capacities']['Mmax_half_kNm']

    print(f"\n  Global capacities (half-model):")
    print(f"    Vmax = {Vmax:,.0f} kN")
    print(f"    Hmax = {Hmax:,.0f} kN")
    print(f"    Mmax = {Mmax:,.0f} kNm")

    # Load and process each probe's plate data
    profiles = {}
    for probe, fname in [('Hmax', 'plates_Hmax.xlsx'),
                          ('Vmax', 'plates_Vmax.xlsx'),
                          ('Mmax', 'plates_Mmax.xlsx')]:
        fpath = VHM_DIR / fname
        if not fpath.exists():
            print(f"\n  WARNING: {fpath} not found, skipping {probe}")
            continue

        print(f"\n  Processing {probe} plates...")
        df = pd.read_excel(fpath)
        if 'X_1' not in df.columns:
            print(f"    No coordinate data, skipping")
            continue

        df = add_geometry(df)
        n_lid = (df['part'] == 'lid').sum()
        n_skirt = (df['part'] == 'skirt_wall').sum()
        n_tip = (df['part'] == 'tip_zone').sum()
        print(f"    {len(df)} elements: lid={n_lid}, skirt={n_skirt}, tip={n_tip}")

        prof = pressure_profile(df, n_slices=19, part_filter='skirt_wall')
        profiles[probe] = prof

        H_int = prof['H_kN'].sum()
        V_int = prof['V_kN'].sum()
        print(f"    H_skirt = {H_int:.0f} kN, V_skirt = {V_int:.0f} kN")

    # --- Build unified capacity profile at DZ=0.5m nodes ---
    z_nodes = np.arange(0, L + DZ/2, DZ)

    # Interpolate profiles to regular grid
    # OptumGX z_mid is negative (e.g., -0.5, -3.0, -9.0)
    # z_nodes is positive depth below mudline (0, 0.5, 1.0, ..., 9.0)
    def interp_profile(prof, col, z_target):
        """Interpolate profile to target depths. Handles sign flip."""
        z_src = (-prof['z_mid'].values)  # flip to positive depth
        v_src = abs(prof[col].values)    # absolute values
        # Sort by depth
        order = np.argsort(z_src)
        z_src, v_src = z_src[order], v_src[order]
        # Remove duplicates
        _, idx = np.unique(z_src, return_index=True)
        z_src, v_src = z_src[idx], v_src[idx]
        if len(z_src) < 2:
            return np.zeros_like(z_target)
        return np.interp(z_target, z_src, v_src, left=0, right=0)

    if 'Hmax' in profiles:
        p_ult_interp = interp_profile(profiles['Hmax'], 'p_kN_m', z_nodes)
    else:
        p_ult_interp = np.zeros_like(z_nodes)

    if 'Vmax' in profiles:
        t_ult_interp = interp_profile(profiles['Vmax'], 't_kN_m', z_nodes)
    else:
        t_ult_interp = np.zeros_like(z_nodes)

    if 'Mmax' in profiles:
        p_mom_interp = interp_profile(profiles['Mmax'], 'p_kN_m', z_nodes)
    else:
        p_mom_interp = np.zeros_like(z_nodes)

    # --- Smooth noisy profiles ---
    # OptumGX plate elements are mesh-dependent; depth slices with few elements
    # produce noisy reactions. Apply robust smoothing then scale to match global.
    from scipy.ndimage import uniform_filter1d

    def smooth_and_scale(raw, z, global_target, window=3):
        """Smooth with moving average, then scale so integral = target."""
        if raw.max() == 0:
            return raw
        smoothed = uniform_filter1d(raw.astype(float), size=window, mode='nearest')
        smoothed = np.maximum(smoothed, 0)  # no negative capacity
        integral = np.trapezoid(smoothed, z)
        if integral > 0:
            scale = global_target / integral
            smoothed *= scale
        return smoothed

    # Scale p_ult so integral = H_skirt from OptumGX (not full Hmax)
    H_skirt_raw = profiles['Hmax']['H_kN'].sum() if 'Hmax' in profiles else 0
    H_skirt_target = abs(H_skirt_raw)  # use the actual skirt contribution

    p_ult_smooth = smooth_and_scale(p_ult_interp, z_nodes, H_skirt_target, window=3)
    t_ult_smooth = smooth_and_scale(t_ult_interp, z_nodes,
                                     abs(profiles['Vmax']['V_kN'].sum()) if 'Vmax' in profiles else 0,
                                     window=3)
    p_mom_smooth = smooth_and_scale(p_mom_interp, z_nodes,
                                     abs(profiles['Mmax']['H_kN'].sum()) if 'Mmax' in profiles else 0,
                                     window=3)

    # Compute base capacities
    H_skirt = np.trapezoid(p_ult_smooth, z_nodes) if p_ult_smooth.max() > 0 else 0
    V_skirt = np.trapezoid(t_ult_smooth * np.pi * D, z_nodes)
    H_base = max(Hmax - H_skirt, 0)
    V_base = max(Vmax - V_skirt, 0)

    print(f"\n  After smoothing + scaling:")
    print(f"    H_skirt = {H_skirt:.0f} kN ({H_skirt/Hmax*100:.0f}% of Hmax)")
    print(f"    H_base  = {H_base:.0f} kN ({H_base/Hmax*100:.0f}% of Hmax)")

    df_cap = pd.DataFrame({
        'z_m': z_nodes,
        'p_ult_raw_kN_m': p_ult_interp,       # raw (noisy)
        'p_ult_kN_m': p_ult_smooth,            # smoothed + scaled
        't_ult_raw_kN_m': t_ult_interp,
        't_ult_kN_m': t_ult_smooth,
        'p_moment_kN_m': p_mom_smooth,
        'p_ult_node_kN': p_ult_smooth * DZ,
        't_ult_node_kN': t_ult_smooth * np.pi * D * DZ,
    })

    csv_path = RESULTS_DIR / 'capacity_profile.csv'
    df_cap.to_csv(csv_path, index=False)

    meta = {
        'Vmax_half_kN': Vmax,
        'Hmax_half_kN': Hmax,
        'Mmax_half_kNm': Mmax,
        'H_skirt_kN': round(H_skirt, 1),
        'H_base_kN': round(H_base, 1),
        'H_skirt_fraction': round(H_skirt / Hmax, 3) if Hmax > 0 else 0,
        'V_skirt_kN': round(V_skirt, 1),
        'V_base_kN': round(V_base, 1),
        'n_nodes': len(z_nodes),
        'dz': DZ, 'D': D, 'L': L,
    }
    json_path = RESULTS_DIR / 'capacity_profile.json'
    with open(json_path, 'w') as f:
        json.dump(meta, f, indent=2)

    print(f"\n  Capacity profile ({len(z_nodes)} nodes):")
    print(f"  {'z':>6s}  {'p_ult':>10s}  {'t_ult':>10s}  {'p_mom':>10s}")
    print(f"  {'[m]':>6s}  {'[kN/m]':>10s}  {'[kN/m]':>10s}  {'[kN/m]':>10s}")
    print("-" * 45)
    for _, r in df_cap.iterrows():
        print(f"  {r['z_m']:6.1f}  {r['p_ult_kN_m']:10.1f}  "
              f"{r['t_ult_kN_m']:10.1f}  {r['p_moment_kN_m']:10.1f}")

    print(f"\n  Base capacities:")
    print(f"    H_base = {H_base:.0f} kN ({H_base/Hmax*100:.0f}% of Hmax)")
    print(f"    V_base = {V_base:.0f} kN ({V_base/Vmax*100:.0f}% of Vmax)")

    print(f"\n  Saved: {csv_path.name}, {json_path.name}")
    print("=" * 60)
