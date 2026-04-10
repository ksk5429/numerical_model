# -*- coding: utf-8 -*-
"""
OptumGX VHM Capacity + Plate Pressure Extraction
=================================================
Builds a 3D skirted circular foundation (dimensions redacted), runs Vmax, Hmax,
Mmax limit-analysis probes, extracts plate-element pressures at failure,
and computes depth-wise distributed capacity profiles p_ult(z) and t_ult(z).

The depth profiles are the BRIDGE between OptumGX global bearing capacity
(VHM) and distributed BNWF spring parameters for OpenSeesPy.

Verification: integral of distributed reactions equals global capacity.

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
# Foundation geometry
D = 8.0             # diameter [m]
R = D / 2           # radius [m]
S = float('nan')  # <REDACTED> proprietary skirt depth [m]
N_SIDES = 24        # polygon sides (full circle)
N_sectors = N_SIDES // 2  # half-model sectors

# Domain
L_dom = 20 * R      # half-width [m]
H_dom = 15 * R      # depth [m]

# Soil (Tresca, linearly increasing su)
su0 = 15.0          # su at mudline [kPa]
k_su = 20.0         # su gradient [kPa/m]
gamma_eff = 10.0    # effective unit weight [kN/m3]
a_interface = 0.67  # interface adhesion factor

# Mesh
N_el = 15000
N_el_start = 10000
fan_angle = 30

# Output
output_dir = 'results_vhm_plate_extraction'
os.makedirs(output_dir, exist_ok=True)


# =============================================================================
# 2. EFFICIENT RESULT EXTRACTION FUNCTIONS
# =============================================================================
def parse_optum_value(attr):
    """
    Parse any OptumGX output attribute into a Python numeric value or list.
    Handles: raw numerics, numpy arrays, 'unit: ..., value: ...' strings.
    """
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
    # Pattern: "unit: 'kPa', value: [1.23 4.56 7.89]"
    m = re.search(r"value:\s*(.*)", s)
    if m:
        nums = re.findall(r'[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?', m.group(1))
        if nums:
            floats = [float(n) for n in nums]
            return floats[0] if len(floats) == 1 else floats
    # Try direct float
    try:
        return float(s)
    except ValueError:
        return s


def get_prop(obj, name):
    """Safely get and parse a property from an OptumGX output object."""
    if not hasattr(obj, name):
        return None
    return parse_optum_value(getattr(obj, name))


def collect_plates_fast(output):
    """
    Collect plate element data into a DataFrame.
    Extracts: coordinates (3 nodes), pressures (sigma/tau), nodal forces.
    Much faster than the generic approach -- targets only needed columns.
    """
    rows = []
    for plate in output.plate:
        row = {}

        # Material
        if hasattr(plate, 'general'):
            row['material'] = get_prop(plate.general, 'material_name')

        # Topology: node coordinates
        if hasattr(plate, 'topology'):
            top = plate.topology
            for coord in ['X', 'Y', 'Z']:
                val = get_prop(top, coord)
                if isinstance(val, list):
                    for j, v in enumerate(val, 1):
                        row[f'{coord}_{j}'] = v
                elif val is not None:
                    row[coord] = val

        # Results: pressures and forces
        if hasattr(plate, 'results'):
            res = plate.results
            # Total pressures (sigma_plus, sigma_minus, tau_plus, tau_minus)
            if hasattr(res, 'total_pressures'):
                tp = res.total_pressures
                for prop in ['sigma_plus', 'sigma_minus',
                             'tau_plus', 'tau_minus']:
                    val = get_prop(tp, prop)
                    if isinstance(val, list):
                        for j, v in enumerate(val, 1):
                            row[f'{prop}_{j}'] = v
                    elif val is not None:
                        row[prop] = val

            # Nodal forces
            if hasattr(res, 'nodal_forces'):
                nf = res.nodal_forces
                for prop in ['q_x', 'q_y', 'q_z']:
                    val = get_prop(nf, prop)
                    if isinstance(val, list):
                        for j, v in enumerate(val, 1):
                            row[f'F_{prop}_{j}'] = v
                    elif val is not None:
                        row[f'F_{prop}'] = val

            # Collapse mechanism (displacements at failure)
            if hasattr(res, 'collapse_mechanism'):
                cm = res.collapse_mechanism
                for prop in ['u_x', 'u_y', 'u_z']:
                    val = get_prop(cm, prop)
                    if isinstance(val, list):
                        for j, v in enumerate(val, 1):
                            row[f'cm_{prop}_{j}'] = v

        rows.append(row)
    return pd.DataFrame(rows)


def compute_element_geometry(df):
    """
    Compute element centroid, area, and outward normal for triangular plates.
    Adds columns: Xc, Yc, Zc, area, nx, ny, nz.
    """
    # Node coordinates
    p1 = df[['X_1', 'Y_1', 'Z_1']].values
    p2 = df[['X_2', 'Y_2', 'Z_2']].values
    p3 = df[['X_3', 'Y_3', 'Z_3']].values

    # Centroid
    df['Xc'] = (p1[:, 0] + p2[:, 0] + p3[:, 0]) / 3
    df['Yc'] = (p1[:, 1] + p2[:, 1] + p3[:, 1]) / 3
    df['Zc'] = (p1[:, 2] + p2[:, 2] + p3[:, 2]) / 3

    # Vectors along two edges
    v1 = p2 - p1  # shape (N, 3)
    v2 = p3 - p1

    # Cross product -> normal * 2*area
    cross = np.cross(v1, v2)
    norms = np.linalg.norm(cross, axis=1, keepdims=True)
    norms = np.maximum(norms, 1e-20)  # avoid division by zero

    df['area'] = (norms.flatten() / 2)
    df['nx'] = cross[:, 0] / norms.flatten()
    df['ny'] = cross[:, 1] / norms.flatten()
    df['nz'] = cross[:, 2] / norms.flatten()

    # Radial distance and circumferential angle
    df['R_c'] = np.sqrt(df['Xc']**2 + df['Yc']**2)
    df['theta'] = np.arctan2(df['Yc'], df['Xc'])

    return df


def compute_depth_reactions(df, n_slices=20):
    """
    Integrate plate element nodal forces by depth slice.

    For each depth band [z_top, z_bot]:
      H(z) = sum of F_q_x  (horizontal nodal forces in the slice)
      V(z) = sum of F_q_z  (vertical nodal forces in the slice)

    Returns DataFrame with columns: z_mid, z_top, z_bot, H_slice, V_slice,
                                     n_elements, dz
    """
    z_min = df['Zc'].min()
    z_max = df['Zc'].max()
    boundaries = np.linspace(z_max, z_min, n_slices + 1)

    results = []
    for i in range(n_slices):
        z_top = boundaries[i]
        z_bot = boundaries[i + 1]
        z_mid = (z_top + z_bot) / 2
        dz = abs(z_top - z_bot)

        mask = (df['Zc'] <= z_top) & (df['Zc'] > z_bot)
        subset = df[mask]
        n_elem = len(subset)

        if n_elem == 0:
            results.append({
                'z_mid': z_mid, 'z_top': z_top, 'z_bot': z_bot,
                'dz': dz, 'n_elements': 0,
                'H_slice_kN': 0, 'V_slice_kN': 0, 'M_slice_kNm': 0,
            })
            continue

        # Sum nodal forces in slice (all 3 nodes per element, 2 per node
        # in the OptumGX convention: 6 force values per DOF per element)
        # Nodal forces columns: F_q_x_1..F_q_x_N, F_q_z_1..F_q_z_N
        fx_cols = [c for c in subset.columns if c.startswith('F_q_x_')]
        fz_cols = [c for c in subset.columns if c.startswith('F_q_z_')]

        # Sum all nodal force contributions in this slice
        H_slice = subset[fx_cols].sum().sum() if fx_cols else 0.0
        V_slice = subset[fz_cols].sum().sum() if fz_cols else 0.0

        # Moment about mudline (z=0): M = sum(Fx * z_node)
        M_slice = 0.0
        for col_fx in fx_cols:
            idx = col_fx.split('_')[-1]  # node index
            z_col = f'Z_{idx}'
            if z_col in subset.columns:
                M_slice += (subset[col_fx] * subset[z_col]).sum()

        results.append({
            'z_mid': z_mid, 'z_top': z_top, 'z_bot': z_bot,
            'dz': dz, 'n_elements': n_elem,
            'H_slice_kN': H_slice, 'V_slice_kN': V_slice,
            'M_slice_kNm': M_slice,
        })

    df_slices = pd.DataFrame(results)

    # Convert force-per-slice to force-per-unit-depth
    df_slices['p_kN_per_m'] = df_slices['H_slice_kN'] / df_slices['dz']
    df_slices['t_kN_per_m'] = df_slices['V_slice_kN'] / df_slices['dz']

    return df_slices


def compute_pressure_reactions(df, n_slices=20):
    """
    Alternative: integrate net pressure * area * normal to get soil reaction.

    Net normal pressure: sigma_net = sigma_plus - sigma_minus [kPa]
    Net shear: tau_net = tau_plus + tau_minus [kPa]

    Horizontal reaction per element:
      dH = sigma_net * A * |nx| + tau_net * A * |nz|  (simplified)
    """
    z_min = df['Zc'].min()
    z_max = df['Zc'].max()
    boundaries = np.linspace(z_max, z_min, n_slices + 1)

    # Compute element-level net pressures (average over 3 nodes)
    sp_cols = [c for c in df.columns if c.startswith('sigma_plus_')]
    sm_cols = [c for c in df.columns if c.startswith('sigma_minus_')]
    tp_cols = [c for c in df.columns if c.startswith('tau_plus_')]
    tm_cols = [c for c in df.columns if c.startswith('tau_minus_')]

    if sp_cols and sm_cols:
        df['sigma_net'] = df[sp_cols].mean(axis=1) - df[sm_cols].mean(axis=1)
    else:
        df['sigma_net'] = 0.0

    if tp_cols and tm_cols:
        df['tau_net'] = df[tp_cols].mean(axis=1) + df[tm_cols].mean(axis=1)
    else:
        df['tau_net'] = 0.0

    # Element-level force contributions
    df['dFx_sigma'] = df['sigma_net'] * df['area'] * df['nx']  # normal -> horizontal
    df['dFz_sigma'] = df['sigma_net'] * df['area'] * df['nz']  # normal -> vertical
    df['dFx_tau'] = df['tau_net'] * df['area'] * abs(df['nz'])  # shear on horiz surfaces
    df['dFz_tau'] = df['tau_net'] * df['area'] * (1 - abs(df['nz']))  # shear on vert surfaces

    results = []
    for i in range(n_slices):
        z_top = boundaries[i]
        z_bot = boundaries[i + 1]
        z_mid = (z_top + z_bot) / 2
        dz = abs(z_top - z_bot)

        mask = (df['Zc'] <= z_top) & (df['Zc'] > z_bot)
        subset = df[mask]

        H_press = (subset['dFx_sigma'] + subset['dFx_tau']).sum()
        V_press = (subset['dFz_sigma'] + subset['dFz_tau']).sum()

        results.append({
            'z_mid': z_mid, 'dz': dz, 'n_elements': len(subset),
            'H_pressure_kN': H_press, 'V_pressure_kN': V_press,
            'p_pressure_kN_m': H_press / dz if dz > 0 else 0,
            't_pressure_kN_m': V_press / dz if dz > 0 else 0,
        })

    return pd.DataFrame(results)


# =============================================================================
# 3. MODEL BUILDER (2D revolve to 3D, following proven pattern)
# =============================================================================
def build_skirted_foundation(prj, model_name):
    """Build the 3D skirted circular foundation via 2D revolution."""

    # Materials (unique names per probe to avoid gRPC conflict)
    XYZ = np.array([
        [-L_dom, 0, 0],    [L_dom, 0, 0],
        [L_dom, L_dom/2, 0], [-L_dom, L_dom/2, 0],
        [-L_dom, 0, -H_dom], [L_dom, 0, -H_dom],
        [L_dom, L_dom/2, -H_dom], [-L_dom, L_dom/2, -H_dom],
    ])
    su_vals = np.array([su0]*4 + [su0 + k_su*H_dom]*4)
    sumap = ParameterMap(np.column_stack([XYZ, su_vals]))

    Soil = prj.Tresca(name=f"Soil_{model_name}", cu=sumap,
                       gamma_dry=gamma_eff, color=rgb(195, 165, 120))
    Foundation = prj.RigidPlate(name=f"Foundation_{model_name}",
                                 color=rgb(130, 160, 180))

    # 2D cross-section (plane strain)
    mod2d = prj.create_model(name=f"AX_{model_name}",
                              model_type="plane_strain")
    mod2d.add_rectangle([0, -H_dom], [L_dom/2, 0])
    mod2d.add_line([0, 0], [R, 0])         # lid
    mod2d.add_line([R, 0], [R, -S])        # skirt wall

    # Assign soil
    sel = mod2d.select([L_dom/4, -H_dom/2], types="face")
    mod2d.set_solid(sel, Soil)

    # Assign foundation plates
    sel = mod2d.select([R/2, 0], types="edge")
    mod2d.set_plate(sel, Foundation, strength_reduction_factor=a_interface)
    sel = mod2d.select([R, -S/2], types="edge")
    mod2d.set_plate(sel, Foundation, strength_reduction_factor=a_interface)

    # Revolve to 3D half-model
    mod = mod2d.revolve_2d_to_3d(angle_deg=180, N=N_sectors,
                                  name=model_name)
    mod2d.delete()

    # Clean axis edge artifact
    try:
        sel = mod.select([0, 0, -H_dom/2], types="edge")
        if sel:
            mod.delete_shapes(sel)
    except Exception:
        pass

    # Center vertex + result point
    mod.add_vertex([0, 0, 0])
    sel_center = mod.select([0, 0, 0], types="vertex")
    mod.set_resultpoint(sel_center)

    # Plate BCs (symmetry: y fixed on y=0 plane)
    sel = mod.select([0, 0, 0], types="edge")
    mod.set_plate_bc(sel, displacement_x="fixed", displacement_y="fixed",
                     displacement_z="free", displacement_rotation="fixed")
    sel = mod.select([R, 0, -S/2], types="edge")
    mod.set_plate_bc(sel, displacement_x="free", displacement_y="fixed",
                     displacement_z="free", displacement_rotation="fixed")
    sel = mod.select([-R, 0, -S/2], types="edge")
    mod.set_plate_bc(sel, displacement_x="free", displacement_y="fixed",
                     displacement_z="free", displacement_rotation="fixed")

    # Standard fixities
    mod.set_standard_fixities()

    # Point BC at center
    sel = mod.select([0, 0, 0], types="vertex")
    mod.set_point_bc(shapes=sel,
                     displacement_x='fixed', displacement_y='fixed',
                     displacement_z='free',
                     displacement_rotation_x='fixed',
                     displacement_rotation_y='fixed',
                     displacement_rotation_z='fixed',
                     use_local_coord=False)

    # Mesh fans at skirt tip
    angles = np.linspace(0, 180, N_sectors + 1)
    for ang in angles:
        rad = np.radians(ang)
        try:
            sel_fan = mod.select([R*np.cos(rad), R*np.sin(rad), -S],
                                 types="vertex")
            if sel_fan:
                mod.set_mesh_fan(shapes=sel_fan, fan_angle=fan_angle)
        except Exception:
            pass

    # Analysis properties
    mod.set_analysis_properties(
        analysis_type='load_multiplier',
        element_type="mixed",
        no_of_elements=N_el,
        mesh_adaptivity='yes',
        adaptivity_iterations=3,
        start_elements=N_el_start,
        design_approach='unity',
    )
    mod.zoom_all()

    return mod, sel_center


def run_probe(prj, mod, sel_center, probe_type):
    """
    Run a uniaxial probe (Vmax, Hmax, or Mmax) and extract results.

    Returns: (load_multiplier, df_plates)
    """
    # Apply load based on probe type
    if probe_type == 'Vmax':
        mod.set_point_load(sel_center, -1, direction="z", option="multiplier")
    elif probe_type == 'Hmax':
        mod.set_point_load(sel_center, 1, direction="x", option="multiplier")
        # For pure H: fix vertical displacement
        sel_edge = mod.select([0, 0, 0], types="edge")
        bcs = mod.get_features(sel_edge)
        mod.remove_features(bcs)
        mod.set_plate_bc(sel_edge, displacement_x="free",
                         displacement_y="fixed",
                         displacement_z="fixed",
                         displacement_rotation="fixed")
    elif probe_type == 'Mmax':
        # Moment via eccentric vertical load (e = large)
        # Apply H at elevation offset for moment
        mod.set_point_load(sel_center, 1, direction="x", option="multiplier")
        # Fix both V and H displacement, free rotation
        sel_edge = mod.select([0, 0, 0], types="edge")
        bcs = mod.get_features(sel_edge)
        mod.remove_features(bcs)
        mod.set_plate_bc(sel_edge, displacement_x="fixed",
                         displacement_y="fixed",
                         displacement_z="fixed",
                         displacement_rotation="free")

    # Run analysis
    t0 = time.time()
    prj.run_analysis()
    dt = time.time() - t0

    # Get global result
    try:
        lm = mod.output.global_results.load_multiplier
    except Exception:
        try:
            lm = mod.output.critical_results.load_multiplier
        except Exception:
            lm = None

    # Collect plate data
    df_plates = collect_plates_fast(mod.output)

    return float(lm) if lm is not None else None, df_plates, dt


# =============================================================================
# 4. MAIN EXECUTION
# =============================================================================
if __name__ == "__main__":
    print("=" * 70)
    print("OptumGX VHM Capacity + Plate Pressure Extraction")
    print(f"Foundation: D={D}m, L={S}m, su={su0}+{k_su}z kPa")
    print("=" * 70)

    t_start = time.time()

    # Connect
    gx = GX()
    prj = gx.create_project("VHM_Plate_Extraction")
    prj.get_model("Model A").delete()

    all_results = {}

    # -------------------------------------------------------------------------
    # PROBE 1: Vmax
    # -------------------------------------------------------------------------
    print("\n[PROBE 1] Vmax (pure vertical compression)...")
    mod_v, sel_v = build_skirted_foundation(prj, "Vmax")
    Vmax, df_plates_v, dt_v = run_probe(prj, mod_v, sel_v, 'Vmax')
    print(f"  Vmax = {Vmax:.2f} kN (half-model), time = {dt_v:.0f}s")

    # Compute geometry and depth reactions
    if 'X_1' in df_plates_v.columns:
        df_plates_v = compute_element_geometry(df_plates_v)
        slices_v_force = compute_depth_reactions(df_plates_v, n_slices=20)
        slices_v_press = compute_pressure_reactions(df_plates_v, n_slices=20)
        V_integrated = slices_v_force['V_slice_kN'].sum()
        print(f"  Plate elements: {len(df_plates_v)}")
        print(f"  V integrated from nodal forces: {V_integrated:.2f} kN")
        print(f"  Consistency ratio: {V_integrated/Vmax:.3f}"
              if Vmax and Vmax != 0 else "")
    else:
        slices_v_force = slices_v_press = pd.DataFrame()
        print("  WARNING: No coordinate data in plate output")

    all_results['Vmax'] = {
        'load_multiplier': Vmax,
        'time_s': dt_v,
        'n_plates': len(df_plates_v),
    }
    mod_v.delete()

    # -------------------------------------------------------------------------
    # PROBE 2: Hmax
    # -------------------------------------------------------------------------
    print("\n[PROBE 2] Hmax (pure horizontal)...")
    mod_h, sel_h = build_skirted_foundation(prj, "Hmax")
    Hmax, df_plates_h, dt_h = run_probe(prj, mod_h, sel_h, 'Hmax')
    print(f"  Hmax = {Hmax:.2f} kN (half-model), time = {dt_h:.0f}s")

    if 'X_1' in df_plates_h.columns:
        df_plates_h = compute_element_geometry(df_plates_h)
        slices_h_force = compute_depth_reactions(df_plates_h, n_slices=20)
        slices_h_press = compute_pressure_reactions(df_plates_h, n_slices=20)
        H_integrated = slices_h_force['H_slice_kN'].sum()
        print(f"  Plate elements: {len(df_plates_h)}")
        print(f"  H integrated from nodal forces: {H_integrated:.2f} kN")
        print(f"  Consistency ratio: {H_integrated/Hmax:.3f}"
              if Hmax and Hmax != 0 else "")

        # Show depth profile
        print(f"\n  Depth-wise lateral reaction p(z) [kN/m]:")
        print(f"  {'z_mid':>8s}  {'p(z)':>10s}  {'n_elem':>7s}")
        for _, row in slices_h_force.iterrows():
            if row['n_elements'] > 0:
                print(f"  {row['z_mid']:8.2f}  "
                      f"{row['p_kN_per_m']:10.2f}  "
                      f"{int(row['n_elements']):7d}")
    else:
        slices_h_force = slices_h_press = pd.DataFrame()

    all_results['Hmax'] = {
        'load_multiplier': Hmax,
        'time_s': dt_h,
        'n_plates': len(df_plates_h),
    }
    mod_h.delete()

    # -------------------------------------------------------------------------
    # SAVE ALL DATA
    # -------------------------------------------------------------------------
    print("\n[SAVE] Writing results...")

    # Raw plate data
    df_plates_v.to_excel(os.path.join(output_dir, 'plates_Vmax.xlsx'),
                         index=False)
    df_plates_h.to_excel(os.path.join(output_dir, 'plates_Hmax.xlsx'),
                         index=False)

    # Depth profiles
    if len(slices_h_force) > 0:
        slices_h_force.to_csv(os.path.join(output_dir, 'p_ult_z_Hmax.csv'),
                              index=False)
    if len(slices_v_force) > 0:
        slices_v_force.to_csv(os.path.join(output_dir, 't_ult_z_Vmax.csv'),
                              index=False)
    if len(slices_h_press) > 0:
        slices_h_press.to_csv(
            os.path.join(output_dir, 'p_pressure_z_Hmax.csv'), index=False)
    if len(slices_v_press) > 0:
        slices_v_press.to_csv(
            os.path.join(output_dir, 't_pressure_z_Vmax.csv'), index=False)

    # Summary JSON
    total_time = time.time() - t_start
    all_results['total_time_s'] = total_time
    all_results['config'] = {
        'D': D, 'R': R, 'S': S, 'su0': su0, 'k_su': k_su,
        'gamma': gamma_eff, 'a_interface': a_interface,
        'N_el': N_el, 'N_sectors': N_sectors,
    }

    # Consistency verification
    if Hmax and len(slices_h_force) > 0:
        H_int = slices_h_force['H_slice_kN'].sum()
        all_results['verification'] = {
            'Hmax_global': Hmax,
            'H_integrated_nodal_forces': H_int,
            'ratio': H_int / Hmax if Hmax != 0 else None,
        }
    if Vmax and len(slices_v_force) > 0:
        V_int = slices_v_force['V_slice_kN'].sum()
        all_results['verification_V'] = {
            'Vmax_global': Vmax,
            'V_integrated_nodal_forces': V_int,
            'ratio': V_int / Vmax if Vmax != 0 else None,
        }

    with open(os.path.join(output_dir, 'summary.json'), 'w') as f:
        json.dump(all_results, f, indent=2, default=str)

    # =========================================================================
    # REPORT
    # =========================================================================
    print("\n" + "=" * 70)
    print("REPORT: OptumGX VHM Capacity + Plate Pressure Extraction")
    print("=" * 70)

    print(f"""
FOUNDATION GEOMETRY
  Diameter D       = {D} m
  Skirt depth L    = {S} m
  L/D ratio        = {S/D:.3f}
  Interface factor = {a_interface}

SOIL PROPERTIES
  su(z)    = {su0} + {k_su}*z [kPa]  (Tresca)
  gamma'   = {gamma_eff} kN/m3
  kappa    = k*D/su0 = {k_su*D/su0:.1f}

MESH
  Target elements  = {N_el}
  Start elements   = {N_el_start}
  Half-model       = {N_sectors} sectors (180 deg)

GLOBAL CAPACITIES (half-model)
  Vmax = {Vmax:.2f} kN  (full: {2*Vmax:.2f} kN)
  Hmax = {Hmax:.2f} kN  (full: {2*Hmax:.2f} kN)
""")

    if Hmax and len(slices_h_force) > 0:
        H_int = slices_h_force['H_slice_kN'].sum()
        print(f"""VERIFICATION: DISTRIBUTED vs GLOBAL CAPACITY
  H from plate nodal forces = {H_int:.2f} kN
  H from load multiplier    = {Hmax:.2f} kN
  Ratio (should be ~1.0)    = {H_int/Hmax:.4f}
""")

    if Vmax and len(slices_v_force) > 0:
        V_int = slices_v_force['V_slice_kN'].sum()
        print(f"""  V from plate nodal forces = {V_int:.2f} kN
  V from load multiplier    = {Vmax:.2f} kN
  Ratio (should be ~1.0)    = {V_int/Vmax:.4f}
""")

    if len(slices_h_force) > 0:
        print("DEPTH PROFILE: LATERAL REACTION p_ult(z) [kN/m]")
        print("-" * 55)
        print(f"  {'z [m]':>8s}  {'p_ult':>10s}  {'H_slice':>10s}  {'n_elem':>7s}")
        print("-" * 55)
        for _, row in slices_h_force.iterrows():
            if row['n_elements'] > 0:
                print(f"  {row['z_mid']:8.2f}  "
                      f"{row['p_kN_per_m']:10.2f}  "
                      f"{row['H_slice_kN']:10.2f}  "
                      f"{int(row['n_elements']):7d}")
        print("-" * 55)
        print(f"  {'TOTAL':>8s}  {'':>10s}  "
              f"{slices_h_force['H_slice_kN'].sum():10.2f}")

    if len(slices_v_force) > 0:
        print(f"\nDEPTH PROFILE: VERTICAL REACTION t_ult(z) [kN/m]")
        print("-" * 55)
        print(f"  {'z [m]':>8s}  {'t_ult':>10s}  {'V_slice':>10s}  {'n_elem':>7s}")
        print("-" * 55)
        for _, row in slices_v_force.iterrows():
            if row['n_elements'] > 0:
                print(f"  {row['z_mid']:8.2f}  "
                      f"{row['t_kN_per_m']:10.2f}  "
                      f"{row['V_slice_kN']:10.2f}  "
                      f"{int(row['n_elements']):7d}")
        print("-" * 55)
        print(f"  {'TOTAL':>8s}  {'':>10s}  "
              f"{slices_v_force['V_slice_kN'].sum():10.2f}")

    print(f"""
OUTPUT FILES
  {output_dir}/plates_Vmax.xlsx     - Raw plate data (Vmax probe)
  {output_dir}/plates_Hmax.xlsx     - Raw plate data (Hmax probe)
  {output_dir}/p_ult_z_Hmax.csv    - Lateral p_ult(z) from nodal forces
  {output_dir}/t_ult_z_Vmax.csv    - Vertical t_ult(z) from nodal forces
  {output_dir}/summary.json        - All results + verification

COMPUTATION TIME
  Vmax probe: {dt_v:.0f}s
  Hmax probe: {dt_h:.0f}s
  Total:      {total_time:.0f}s
""")
    print("=" * 70)
