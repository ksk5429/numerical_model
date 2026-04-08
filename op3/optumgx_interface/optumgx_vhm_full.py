# -*- coding: utf-8 -*-
"""
OptumGX Full VHM Extraction: Vmax + Hmax + Mmax + Plate Pressures
==================================================================
Builds D=8m, L=9.3m skirted circular foundation, runs all three
uniaxial probes, extracts global capacities AND plate-element
pressure distributions for BNWF calibration.

Author : Claude (autonomous OptumGX scripting)
Date   : 2026-03-19
"""
from OptumGX import *
import numpy as np
import pandas as pd
import re
import os
import time
import json

# =============================================================================
# 1. CONFIGURATION
# =============================================================================
D = 8.0;  R = D / 2;  S = 9.3
N_SIDES = 24;  N_sectors = N_SIDES // 2
L_dom = 20 * R;  H_dom = 15 * R

su0 = 15.0;  k_su = 20.0;  gamma_eff = 10.0;  a_interface = 0.67
N_el = 15000;  N_el_start = 10000;  fan_angle = 30

output_dir = 'results_vhm_full'
os.makedirs(output_dir, exist_ok=True)


# =============================================================================
# 2. RESULT EXTRACTION (clean, efficient)
# =============================================================================
def parse_val(attr):
    """Parse any OptumGX output attribute to Python numeric."""
    if attr is None:
        return None
    if isinstance(attr, (int, float)):
        return attr
    if isinstance(attr, np.ndarray):
        return attr.tolist()
    if isinstance(attr, (list, tuple)):
        return [float(x) if isinstance(x, (int, float, np.floating)) else x
                for x in attr]
    s = str(attr)
    m = re.search(r"value:\s*(.*)", s)
    if m:
        nums = re.findall(r'[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?', m.group(1))
        if nums:
            floats = [float(n) for n in nums]
            return floats[0] if len(floats) == 1 else floats
    try:
        return float(s)
    except ValueError:
        return s


def gprop(obj, name):
    """Get and parse property."""
    return parse_val(getattr(obj, name, None))


def collect_plates(output):
    """Collect plate element data: coords, pressures, nodal forces."""
    rows = []
    for plate in output.plate:
        row = {}
        if hasattr(plate, 'general'):
            row['material'] = gprop(plate.general, 'material_name')
        if hasattr(plate, 'topology'):
            top = plate.topology
            for c in ['X', 'Y', 'Z']:
                v = gprop(top, c)
                if isinstance(v, list):
                    for j, val in enumerate(v, 1):
                        row[f'{c}_{j}'] = val
        if hasattr(plate, 'results'):
            res = plate.results
            for cat_name, props in [
                ('total_pressures', ['sigma_plus', 'sigma_minus',
                                     'tau_plus', 'tau_minus']),
                ('nodal_forces', ['q_x', 'q_y', 'q_z']),
                ('collapse_mechanism', ['u_x', 'u_y', 'u_z', 'u_norm']),
            ]:
                cat = getattr(res, cat_name, None)
                if cat is None:
                    continue
                for prop in props:
                    v = gprop(cat, prop)
                    prefix = prop if cat_name == 'total_pressures' else \
                             f'F_{prop}' if cat_name == 'nodal_forces' else \
                             f'cm_{prop}'
                    if isinstance(v, list):
                        for j, val in enumerate(v, 1):
                            row[f'{prefix}_{j}'] = val
                    elif v is not None:
                        row[prefix] = v
        rows.append(row)
    return pd.DataFrame(rows)


def add_geometry(df):
    """Add centroid, area, normal, radial coords to plate DataFrame."""
    if 'X_1' not in df.columns:
        return df
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
    df['Rc'] = np.sqrt(df['Xc']**2 + df['Yc']**2)
    df['theta'] = np.arctan2(df['Yc'], df['Xc'])
    # Classify: lid (Zc ~ 0), skirt_wall (Rc ~ R), tip (Zc ~ -S)
    df['part'] = 'unknown'
    df.loc[df['Zc'] > -0.3, 'part'] = 'lid'
    df.loc[(df['Zc'] < -0.3) & (df['Zc'] > -(S - 0.3)) &
           (df['Rc'] > R * 0.8), 'part'] = 'skirt_wall'
    df.loc[df['Zc'] < -(S - 0.3), 'part'] = 'tip_zone'
    return df


def depth_profile(df, n_slices=20, force_dir='x'):
    """
    Compute depth-wise reactions from plate nodal forces.
    Separates lid, skirt wall, and tip contributions.
    """
    z_min, z_max = df['Zc'].min(), df['Zc'].max()
    bounds = np.linspace(z_max, z_min, n_slices + 1)

    fx_cols = sorted([c for c in df.columns if c.startswith(f'F_q_{force_dir}_')])
    fz_cols = sorted([c for c in df.columns if c.startswith('F_q_z_')])

    rows = []
    for i in range(n_slices):
        zt, zb = bounds[i], bounds[i + 1]
        zm, dz = (zt + zb) / 2, abs(zt - zb)
        mask = (df['Zc'] <= zt) & (df['Zc'] > zb)
        sub = df[mask]

        F_dir = sub[fx_cols].sum().sum() if fx_cols else 0
        F_z = sub[fz_cols].sum().sum() if fz_cols else 0

        # Count by part
        n_lid = (sub['part'] == 'lid').sum()
        n_skirt = (sub['part'] == 'skirt_wall').sum()
        n_tip = (sub['part'] == 'tip_zone').sum()

        # Skirt-only reaction
        skirt_mask = mask & (df['part'] == 'skirt_wall')
        sub_skirt = df[skirt_mask]
        F_dir_skirt = sub_skirt[fx_cols].sum().sum() if fx_cols else 0
        F_z_skirt = sub_skirt[fz_cols].sum().sum() if fz_cols else 0

        rows.append({
            'z_mid': zm, 'z_top': zt, 'z_bot': zb, 'dz': dz,
            'n_total': len(sub), 'n_lid': n_lid,
            'n_skirt': n_skirt, 'n_tip': n_tip,
            'F_total_kN': F_dir, 'Fz_total_kN': F_z,
            'F_skirt_kN': F_dir_skirt, 'Fz_skirt_kN': F_z_skirt,
            'p_total_kN_m': F_dir / dz if dz > 0 else 0,
            'p_skirt_kN_m': F_dir_skirt / dz if dz > 0 else 0,
            't_skirt_kN_m': F_z_skirt / dz if dz > 0 else 0,
        })
    return pd.DataFrame(rows)


def net_pressure_profile(df, n_slices=20):
    """
    Compute soil reaction from net contact pressure (sigma_plus - sigma_minus).
    This is the physically correct method for BNWF calibration.
    """
    sp = [c for c in df.columns if c.startswith('sigma_plus_')]
    sm = [c for c in df.columns if c.startswith('sigma_minus_')]
    tp = [c for c in df.columns if c.startswith('tau_plus_')]
    tm = [c for c in df.columns if c.startswith('tau_minus_')]

    if sp and sm:
        df['sig_net'] = df[sp].mean(axis=1) - df[sm].mean(axis=1)
    else:
        df['sig_net'] = 0
    if tp and tm:
        df['tau_net'] = df[tp].mean(axis=1) + df[tm].mean(axis=1)
    else:
        df['tau_net'] = 0

    # Force contributions per element
    df['dFx'] = df['sig_net'] * df['area'] * df['nx'] + \
                df['tau_net'] * df['area'] * abs(df['nz'])
    df['dFz'] = df['sig_net'] * df['area'] * df['nz'] + \
                df['tau_net'] * df['area'] * (1 - abs(df['nz']))
    df['dMy'] = df['dFx'] * df['Zc']  # moment about y-axis at mudline

    z_min, z_max = df['Zc'].min(), df['Zc'].max()
    bounds = np.linspace(z_max, z_min, n_slices + 1)

    rows = []
    for i in range(n_slices):
        zt, zb = bounds[i], bounds[i + 1]
        zm, dz = (zt + zb) / 2, abs(zt - zb)
        mask = (df['Zc'] <= zt) & (df['Zc'] > zb)

        # Skirt wall only
        skirt_mask = mask & (df['part'] == 'skirt_wall')
        sub = df[skirt_mask]

        Hslice = sub['dFx'].sum()
        Vslice = sub['dFz'].sum()
        Mslice = sub['dMy'].sum()

        rows.append({
            'z_mid': zm, 'dz': dz, 'n_skirt': len(sub),
            'H_press_kN': Hslice, 'V_press_kN': Vslice,
            'M_press_kNm': Mslice,
            'p_press_kN_m': Hslice / dz if dz > 0 else 0,
            't_press_kN_m': Vslice / dz if dz > 0 else 0,
        })
    return pd.DataFrame(rows)


# =============================================================================
# 3. MODEL BUILDER
# =============================================================================
def build_model(prj, name):
    """Build 3D skirted foundation via 2D revolution. Returns (mod, sel_vertex)."""
    XYZ = np.array([
        [-L_dom, 0, 0], [L_dom, 0, 0],
        [L_dom, L_dom/2, 0], [-L_dom, L_dom/2, 0],
        [-L_dom, 0, -H_dom], [L_dom, 0, -H_dom],
        [L_dom, L_dom/2, -H_dom], [-L_dom, L_dom/2, -H_dom],
    ])
    su_vals = np.array([su0]*4 + [su0 + k_su * H_dom]*4)
    sumap = ParameterMap(np.column_stack([XYZ, su_vals]))

    Soil = prj.Tresca(name=f"Soil_{name}", cu=sumap,
                       gamma_dry=gamma_eff, color=rgb(195, 165, 120))
    Fdn = prj.RigidPlate(name=f"Fdn_{name}", color=rgb(130, 160, 180))

    # 2D cross-section
    m2 = prj.create_model(name=f"AX_{name}", model_type="plane_strain")
    m2.add_rectangle([0, -H_dom], [L_dom/2, 0])
    m2.add_line([0, 0], [R, 0])
    m2.add_line([R, 0], [R, -S])
    sel = m2.select([L_dom/4, -H_dom/2], types="face")
    m2.set_solid(sel, Soil)
    sel = m2.select([R/2, 0], types="edge")
    m2.set_plate(sel, Fdn, strength_reduction_factor=a_interface)
    sel = m2.select([R, -S/2], types="edge")
    m2.set_plate(sel, Fdn, strength_reduction_factor=a_interface)

    # Revolve
    mod = m2.revolve_2d_to_3d(angle_deg=180, N=N_sectors, name=name)
    m2.delete()

    # Clean axis edge
    try:
        sel = mod.select([0, 0, -H_dom/2], types="edge")
        if sel:
            mod.delete_shapes(sel)
    except Exception:
        pass

    # Center vertex
    mod.add_vertex([0, 0, 0])
    sel_c = mod.select([0, 0, 0], types="vertex")
    mod.set_resultpoint(sel_c)

    # Plate BCs
    sel = mod.select([0, 0, 0], types="edge")
    mod.set_plate_bc(sel, displacement_x="fixed", displacement_y="fixed",
                     displacement_z="free", displacement_rotation="fixed")
    sel = mod.select([R, 0, -S/2], types="edge")
    mod.set_plate_bc(sel, displacement_x="free", displacement_y="fixed",
                     displacement_z="free", displacement_rotation="fixed")
    sel = mod.select([-R, 0, -S/2], types="edge")
    mod.set_plate_bc(sel, displacement_x="free", displacement_y="fixed",
                     displacement_z="free", displacement_rotation="fixed")

    mod.set_standard_fixities()

    # Point BC at center
    mod.set_point_bc(shapes=sel_c,
                     displacement_x='fixed', displacement_y='fixed',
                     displacement_z='free',
                     displacement_rotation_x='fixed',
                     displacement_rotation_y='fixed',
                     displacement_rotation_z='fixed',
                     use_local_coord=False)

    # Mesh fans at skirt tip
    for ang in np.linspace(0, 180, N_sectors + 1):
        try:
            sf = mod.select([R*np.cos(np.radians(ang)),
                             R*np.sin(np.radians(ang)), -S], types="vertex")
            if sf:
                mod.set_mesh_fan(shapes=sf, fan_angle=fan_angle)
        except Exception:
            pass

    # Analysis
    mod.set_analysis_properties(
        analysis_type='load_multiplier', element_type="mixed",
        no_of_elements=N_el, mesh_adaptivity='yes',
        adaptivity_iterations=3, start_elements=N_el_start,
        design_approach='unity',
    )
    mod.zoom_all()
    return mod, sel_c


# =============================================================================
# 4. PROBE RUNNERS
# =============================================================================
def run_vmax(prj):
    """Pure vertical compression probe."""
    print("\n[PROBE] Vmax -- pure vertical compression")
    mod, sel = build_model(prj, "Vmax")
    mod.set_point_load(sel, -1, direction="z", option="multiplier")
    t0 = time.time()
    prj.run_analysis()
    dt = time.time() - t0
    lm = float(mod.output.global_results.load_multiplier)
    df = collect_plates(mod.output)
    print(f"  Vmax = {lm:.1f} kN (half), time = {dt:.0f}s, plates = {len(df)}")
    mod.delete()
    return lm, df, dt


def run_hmax(prj):
    """Pure horizontal probe (V=0, M=0)."""
    print("\n[PROBE] Hmax -- pure horizontal")
    mod, sel = build_model(prj, "Hmax")

    # Remove default center BCs, apply Hmax-specific BCs
    sel_edge = mod.select([0, 0, 0], types="edge")
    bcs = mod.get_features(sel_edge)
    mod.remove_features(bcs)
    mod.set_plate_bc(sel_edge, displacement_x="free", displacement_y="fixed",
                     displacement_z="fixed", displacement_rotation="fixed")

    # Horizontal multiplier load
    mod.set_point_load(sel, 1, direction="x", option="multiplier")

    t0 = time.time()
    prj.run_analysis()
    dt = time.time() - t0
    lm = float(mod.output.global_results.load_multiplier)
    df = collect_plates(mod.output)
    print(f"  Hmax = {lm:.1f} kN (half), time = {dt:.0f}s, plates = {len(df)}")
    mod.delete()
    return lm, df, dt


def run_mmax(prj):
    """
    Pure moment probe (V=0, H=0).
    Method: apply vertical multiplier load at edge (x=R) creating couple.
    Fix translations at center, free rotation.
    Mmax = load_multiplier * R.
    """
    print("\n[PROBE] Mmax -- pure moment")
    mod, sel = build_model(prj, "Mmax")

    # Remove default center BCs
    sel_edge = mod.select([0, 0, 0], types="edge")
    bcs = mod.get_features(sel_edge)
    mod.remove_features(bcs)
    mod.set_plate_bc(sel_edge, displacement_x="free", displacement_y="fixed",
                     displacement_z="free", displacement_rotation="fixed")

    # Remove default point BC
    pbc = mod.get_features(sel)
    mod.remove_features(pbc)

    # Apply vertical load at edge point (creates moment = F * R)
    mod.add_vertex([R, 0, 0])
    sel_edge_pt = mod.select([R, 0, 0], types="vertex")
    mod.set_point_load(sel_edge_pt, -1, direction="z", option="multiplier")
    mod.set_resultpoint(sel_edge_pt)

    # Constraint: add rigid arm from center to edge, fix center translations
    # Use a line + plate BC to create rigid constraint
    mod.add_line([0, 0, 0], [0, R, 0])
    sel_arm = mod.select([0, R/2, 0], types="edge")
    mod.set_plate_bc(sel_arm, displacement_x="fixed", displacement_y="fixed",
                     displacement_z="fixed", displacement_rotation="free")

    t0 = time.time()
    prj.run_analysis()
    dt = time.time() - t0
    lm = float(mod.output.global_results.load_multiplier)
    Mmax = lm * R  # Moment = Force * lever arm
    df = collect_plates(mod.output)
    print(f"  F_multiplier = {lm:.1f} kN, Mmax = F*R = {Mmax:.1f} kNm (half)")
    print(f"  time = {dt:.0f}s, plates = {len(df)}")
    mod.delete()
    return lm, Mmax, df, dt


# =============================================================================
# 5. MAIN
# =============================================================================
if __name__ == "__main__":
    print("=" * 70)
    print("OptumGX Full VHM: Vmax + Hmax + Mmax + Plate Pressures")
    print(f"D={D}m, L={S}m, su={su0}+{k_su}z, kappa={k_su*D/su0:.1f}")
    print("=" * 70)
    T0 = time.time()

    gx = GX()
    prj = gx.create_project("VHM_Full_Extraction")
    prj.get_model("Model A").delete()

    # --- Run all three probes ---
    Vmax, df_v, dt_v = run_vmax(prj)
    Hmax, df_h, dt_h = run_hmax(prj)
    F_mmax, Mmax, df_m, dt_m = run_mmax(prj)

    # --- Post-process all plate DataFrames ---
    for label, df in [('Vmax', df_v), ('Hmax', df_h), ('Mmax', df_m)]:
        if 'X_1' in df.columns:
            df = add_geometry(df)
            if label == 'Vmax':
                df_v = df
            elif label == 'Hmax':
                df_h = df
            else:
                df_m = df

    # --- Depth profiles ---
    prof_h = depth_profile(df_h, n_slices=20, force_dir='x')
    prof_v = depth_profile(df_v, n_slices=20, force_dir='z')
    prof_m = depth_profile(df_m, n_slices=20, force_dir='x')

    press_h = net_pressure_profile(df_h, n_slices=20)
    press_v = net_pressure_profile(df_v, n_slices=20)
    press_m = net_pressure_profile(df_m, n_slices=20)

    # --- Save everything ---
    df_v.to_excel(os.path.join(output_dir, 'plates_Vmax.xlsx'), index=False)
    df_h.to_excel(os.path.join(output_dir, 'plates_Hmax.xlsx'), index=False)
    df_m.to_excel(os.path.join(output_dir, 'plates_Mmax.xlsx'), index=False)

    prof_h.to_csv(os.path.join(output_dir, 'profile_Hmax_nodal.csv'), index=False)
    prof_v.to_csv(os.path.join(output_dir, 'profile_Vmax_nodal.csv'), index=False)
    prof_m.to_csv(os.path.join(output_dir, 'profile_Mmax_nodal.csv'), index=False)

    press_h.to_csv(os.path.join(output_dir, 'profile_Hmax_pressure.csv'), index=False)
    press_v.to_csv(os.path.join(output_dir, 'profile_Vmax_pressure.csv'), index=False)
    press_m.to_csv(os.path.join(output_dir, 'profile_Mmax_pressure.csv'), index=False)

    T_total = time.time() - T0

    # --- Summary JSON ---
    summary = {
        'capacities': {
            'Vmax_half_kN': Vmax, 'Vmax_full_kN': 2*Vmax,
            'Hmax_half_kN': Hmax, 'Hmax_full_kN': 2*Hmax,
            'Mmax_half_kNm': Mmax, 'Mmax_full_kNm': 2*Mmax,
            'F_mmax_kN': F_mmax,
        },
        'bearing_capacity_factors': {
            'NcV': Vmax / (np.pi/4 * D**2 * (su0 + k_su*S)),
            'NcH': Hmax / (np.pi/4 * D**2 * (su0 + k_su*S)),
            'NcM': Mmax / (np.pi/4 * D**2 * D * (su0 + k_su*S)),
        },
        'plate_counts': {
            'Vmax': len(df_v), 'Hmax': len(df_h), 'Mmax': len(df_m),
        },
        'times_s': {
            'Vmax': dt_v, 'Hmax': dt_h, 'Mmax': dt_m, 'total': T_total,
        },
        'config': {
            'D': D, 'R': R, 'S': S, 'L_D': S/D,
            'su0': su0, 'k_su': k_su, 'kappa': k_su*D/su0,
            'gamma': gamma_eff, 'a_interface': a_interface,
            'N_el': N_el, 'N_sectors': N_sectors,
        },
        'part_counts_Hmax': {
            'lid': int((df_h['part'] == 'lid').sum()),
            'skirt_wall': int((df_h['part'] == 'skirt_wall').sum()),
            'tip_zone': int((df_h['part'] == 'tip_zone').sum()),
        },
    }
    with open(os.path.join(output_dir, 'summary.json'), 'w') as f:
        json.dump(summary, f, indent=2, default=str)

    # =========================================================================
    # COMPREHENSIVE REPORT
    # =========================================================================
    su_tip = su0 + k_su * S
    A = np.pi / 4 * D**2

    print("\n" + "=" * 70)
    print("COMPREHENSIVE REPORT")
    print("=" * 70)

    print(f"""
1. FOUNDATION & SOIL
   Diameter D       = {D} m
   Skirt depth L    = {S} m
   L/D              = {S/D:.3f}
   su(z)            = {su0} + {k_su}z [kPa]
   su at tip        = {su_tip:.1f} kPa
   kappa = kD/su0   = {k_su*D/su0:.1f}
   gamma'           = {gamma_eff} kN/m3
   Interface alpha  = {a_interface}

2. GLOBAL CAPACITIES (half-model / full-model)
   Vmax = {Vmax:,.0f} / {2*Vmax:,.0f} kN
   Hmax = {Hmax:,.0f} / {2*Hmax:,.0f} kN
   Mmax = {Mmax:,.0f} / {2*Mmax:,.0f} kNm  (F={F_mmax:.0f} kN x R={R}m)

3. BEARING CAPACITY FACTORS (normalised by A*su_tip)
   A*su_tip = {A*su_tip:,.0f} kN
   NcV = Vmax / (A*su_tip) = {Vmax/(A*su_tip):.2f}
   NcH = Hmax / (A*su_tip) = {Hmax/(A*su_tip):.2f}
   NcM = Mmax / (A*D*su_tip) = {Mmax/(A*D*su_tip):.3f}

4. PLATE ELEMENTS EXTRACTED
   Vmax probe: {len(df_v)} plates
   Hmax probe: {len(df_h)} plates  (lid={summary['part_counts_Hmax']['lid']}, skirt={summary['part_counts_Hmax']['skirt_wall']}, tip={summary['part_counts_Hmax']['tip_zone']})
   Mmax probe: {len(df_m)} plates

5. DATA PER PLATE ELEMENT
   - Coordinates: X,Y,Z for 3 nodes (triangular elements)
   - Pressures: sigma_plus, sigma_minus, tau_plus, tau_minus [kPa]
   - Nodal forces: q_x, q_y, q_z [kN]
   - Collapse mechanism: u_x, u_y, u_z (displacement field at failure)
   - Computed: centroid, area, normal vector, part classification
""")

    # Print Hmax depth profile
    print("6. DEPTH PROFILE: LATERAL p(z) FROM Hmax PROBE")
    print("   (skirt wall elements only, net pressure method)")
    print("-" * 60)
    print(f"   {'z [m]':>7s}  {'p [kN/m]':>10s}  {'H_slice':>10s}  {'n_elem':>6s}")
    print("-" * 60)
    for _, r in press_h.iterrows():
        if r['n_skirt'] > 0:
            print(f"   {r['z_mid']:7.2f}  {r['p_press_kN_m']:10.1f}  "
                  f"{r['H_press_kN']:10.1f}  {int(r['n_skirt']):6d}")
    H_int = press_h['H_press_kN'].sum()
    print("-" * 60)
    print(f"   {'TOTAL':>7s}  {'':>10s}  {H_int:10.1f}")
    print(f"   Hmax global = {Hmax:.1f}, ratio = {H_int/Hmax:.3f}")

    # Print Mmax depth profile
    print(f"\n7. DEPTH PROFILE: LATERAL p(z) FROM Mmax PROBE")
    print("-" * 60)
    print(f"   {'z [m]':>7s}  {'p [kN/m]':>10s}  {'M_contrib':>10s}  {'n_elem':>6s}")
    print("-" * 60)
    for _, r in press_m.iterrows():
        if r['n_skirt'] > 0:
            print(f"   {r['z_mid']:7.2f}  {r['p_press_kN_m']:10.1f}  "
                  f"{r['M_press_kNm']:10.1f}  {int(r['n_skirt']):6d}")
    M_int = press_m['M_press_kNm'].sum()
    print("-" * 60)
    print(f"   M integrated (skirt) = {M_int:.1f} kNm")
    print(f"   Mmax global = {Mmax:.1f} kNm")

    # Print Vmax depth profile
    print(f"\n8. DEPTH PROFILE: VERTICAL t(z) FROM Vmax PROBE")
    print("-" * 60)
    print(f"   {'z [m]':>7s}  {'t [kN/m]':>10s}  {'V_slice':>10s}  {'n_elem':>6s}")
    print("-" * 60)
    for _, r in press_v.iterrows():
        if r['n_skirt'] > 0:
            print(f"   {r['z_mid']:7.2f}  {r['t_press_kN_m']:10.1f}  "
                  f"{r['V_press_kN']:10.1f}  {int(r['n_skirt']):6d}")
    V_int = press_v['V_press_kN'].sum()
    print("-" * 60)
    print(f"   V integrated (skirt) = {V_int:.1f} kN")

    print(f"""
9. OUTPUT FILES ({output_dir}/)
   plates_Vmax.xlsx              Raw plate data (V probe)
   plates_Hmax.xlsx              Raw plate data (H probe)
   plates_Mmax.xlsx              Raw plate data (M probe)
   profile_Hmax_nodal.csv        Lateral p(z) via nodal forces
   profile_Hmax_pressure.csv     Lateral p(z) via net pressure
   profile_Vmax_nodal.csv        Vertical t(z) via nodal forces
   profile_Vmax_pressure.csv     Vertical t(z) via net pressure
   profile_Mmax_nodal.csv        Moment p(z) via nodal forces
   profile_Mmax_pressure.csv     Moment p(z) via net pressure
   summary.json                  All capacities + metadata

10. COMPUTATION TIME
    Vmax: {dt_v:.0f}s  |  Hmax: {dt_h:.0f}s  |  Mmax: {dt_m:.0f}s
    Total: {T_total:.0f}s ({T_total/60:.1f} min)
""")
    print("=" * 70)
