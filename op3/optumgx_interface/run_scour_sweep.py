# -*- coding: utf-8 -*-
"""
Phase A3: VHM Capacity at Multiple Scour Depths
================================================
Runs Vmax and Hmax probes at scour = 0, 1, 2, 3, 4, 5m using
virtual scour (ParameterMap with su~0 in scoured zone).

Same mesh for all scour depths -> faster and more consistent.
Results saved incrementally to results_scour_sweep/.
"""
from OptumGX import *
import numpy as np
import pandas as pd
import time
import json
import os
from pathlib import Path

# =============================================================================
# CONFIGURATION
# =============================================================================
D = 8.0; R = D / 2; S = float('nan')  # <REDACTED>
N_SIDES = 24; N_sectors = N_SIDES // 2
L_dom = 20 * R; H_dom = 15 * R

su0 = 15.0; k_su = 20.0; gamma_eff = 10.0; a_interface = 0.67
N_el = 6000; N_el_start = 3000; fan_angle = 30

SCOUR_DEPTHS = [0.0, 1.0, 2.0, 3.0, 4.0, 5.0]

OUTPUT_DIR = Path(__file__).parent / 'results_scour_sweep'
OUTPUT_DIR.mkdir(exist_ok=True)


# =============================================================================
# MODEL BUILDER WITH VIRTUAL SCOUR
# =============================================================================
def build_model_with_scour(prj, scour_depth, probe_type, run_name):
    """
    Build 3D skirted foundation with virtual scour via ParameterMap.
    The soil above the scour surface has su ~ 0 and gamma ~ 0.

    Returns (load_multiplier, time_s)
    """
    name = f"{run_name}_S{scour_depth:.0f}m_{probe_type}"

    # ParameterMap: su and gamma vary with position
    # Below scour: normal su = su0 + k*|z|
    # Above scour (z > -scour_depth): su ~ 0 (virtual air)
    su_min = 0.01  # kPa (virtual zero)
    gamma_min = 0.01  # kN/m3

    # Build ParameterMap grid (cylindrical)
    r_pts = np.array([0, R*0.5, R-0.3, R+0.3, R*1.5, R*3, L_dom/4, L_dom/2])
    theta_pts = np.linspace(0, np.pi, N_sectors * 2 + 1)

    if scour_depth > 0:
        z_scour = np.linspace(0, -scour_depth - 1, 10)
        z_normal = np.linspace(-scour_depth - 1, -H_dom, 12)
        z_pts = np.sort(np.unique(np.concatenate([z_scour, z_normal])))[::-1]
    else:
        z_pts = np.linspace(0, -H_dom, 15)[::-1]

    su_data = []
    gm_data = []

    for r in r_pts:
        # At r=0, all theta map to (0,0,z) — use only theta=0 to avoid duplicates
        thetas = [0.0] if r < 1e-6 else theta_pts
        for theta in thetas:
            x = r * np.cos(theta)
            y = r * np.sin(theta)
            for z in z_pts:
                if scour_depth > 0 and z > -scour_depth and r >= R:
                    # Above scour surface, outside foundation -> virtual air
                    su_data.append([x, y, z, su_min])
                    gm_data.append([x, y, z, gamma_min])
                else:
                    su_val = su0 + k_su * abs(z)
                    su_data.append([x, y, z, su_val])
                    gm_data.append([x, y, z, gamma_eff])

    # Far-field corners
    for xc in [-L_dom, L_dom]:
        for yc in [0, L_dom/2]:
            for zc in [0, -H_dom]:
                su_data.append([xc, yc, zc, su0 + k_su * abs(zc)])
                gm_data.append([xc, yc, zc, gamma_eff])

    sumap = ParameterMap(np.array(su_data))
    gamma_map = ParameterMap(np.array(gm_data))

    Soil = prj.Tresca(name=f"Soil_{name}", cu=sumap,
                       gamma_dry=gamma_map, color=rgb(195, 165, 120))
    Fdn = prj.RigidPlate(name=f"Fdn_{name}", color=rgb(130, 160, 180))

    # 2D cross-section (same geometry for all scour depths)
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

    try:
        sel = mod.select([0, 0, -H_dom/2], types="edge")
        if sel: mod.delete_shapes(sel)
    except: pass

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
    mod.set_point_bc(shapes=sel_c,
                     displacement_x='fixed', displacement_y='fixed',
                     displacement_z='free',
                     displacement_rotation_x='fixed',
                     displacement_rotation_y='fixed',
                     displacement_rotation_z='fixed',
                     use_local_coord=False)

    for ang in np.linspace(0, 180, N_sectors + 1):
        try:
            sf = mod.select([R*np.cos(np.radians(ang)),
                             R*np.sin(np.radians(ang)), -S], types="vertex")
            if sf: mod.set_mesh_fan(shapes=sf, fan_angle=fan_angle)
        except: pass

    mod.set_analysis_properties(
        analysis_type='load_multiplier', element_type="mixed",
        no_of_elements=N_el, mesh_adaptivity='yes',
        adaptivity_iterations=3, start_elements=N_el_start,
        design_approach='unity',
    )
    mod.zoom_all()

    # Apply load
    if probe_type == 'Vmax':
        mod.set_point_load(sel_c, -1, direction="z", option="multiplier")
    elif probe_type == 'Hmax':
        sel_edge = mod.select([0, 0, 0], types="edge")
        bcs = mod.get_features(sel_edge)
        mod.remove_features(bcs)
        mod.set_plate_bc(sel_edge, displacement_x="free",
                         displacement_y="fixed",
                         displacement_z="fixed",
                         displacement_rotation="fixed")
        mod.set_point_load(sel_c, 1, direction="x", option="multiplier")

    t0 = time.time()
    prj.run_analysis()
    dt = time.time() - t0

    try:
        lm = float(mod.output.global_results.load_multiplier)
    except:
        try:
            lm = float(mod.output.critical_results.load_multiplier)
        except:
            lm = None

    mod.delete()
    return lm, dt


# =============================================================================
# MAIN
# =============================================================================
if __name__ == "__main__":
    import math
    if math.isnan(S):
        raise RuntimeError(
            "Proprietary dimension S (skirt length) not configured. "
            "Set OP3_SKIRT_LENGTH env var or replace float('nan') with actual value."
        )
    print("=" * 70)
    print("Phase A3: VHM Capacity vs Scour Depth")
    print(f"D={D}m, L={S}m, su={su0}+{k_su}z, N_el={N_el}")
    print(f"Scour depths: {SCOUR_DEPTHS}")
    print("=" * 70)

    T0 = time.time()
    gx = GX()
    prj = gx.create_project("Scour_Sweep_VHM")
    prj.get_model("Model A").delete()

    results = []

    for scour in SCOUR_DEPTHS:
        print(f"\n--- Scour = {scour:.1f} m (S/D = {scour/D:.3f}) ---")

        for probe in ['Vmax', 'Hmax']:
            print(f"  {probe}...", end="", flush=True)
            try:
                lm, dt = build_model_with_scour(prj, scour, probe, f"A3")
                print(f" {lm:.0f} kN ({dt:.0f}s)" if lm else " FAILED")
            except Exception as e:
                lm, dt = None, 0
                print(f" ERROR: {str(e)[:50]}")

            results.append({
                'scour_m': scour,
                'S_over_D': scour / D,
                'probe': probe,
                'capacity_half_kN': lm,
                'capacity_full_kN': 2 * lm if lm else None,
                'time_s': dt,
            })

            # Save incrementally
            df = pd.DataFrame(results)
            df.to_csv(OUTPUT_DIR / 'scour_sweep_results.csv', index=False)

    T_total = time.time() - T0

    # Post-process: normalised degradation
    df = pd.DataFrame(results)
    for probe in ['Vmax', 'Hmax']:
        sub = df[df['probe'] == probe]
        ref = sub[sub['scour_m'] == 0]['capacity_half_kN'].values
        if len(ref) > 0 and ref[0]:
            df.loc[df['probe'] == probe, 'normalised'] = \
                df.loc[df['probe'] == probe, 'capacity_half_kN'] / ref[0]

    df.to_csv(OUTPUT_DIR / 'scour_sweep_results.csv', index=False)

    # Summary JSON
    summary = {'total_time_s': T_total}
    for probe in ['Vmax', 'Hmax']:
        sub = df[df['probe'] == probe].dropna(subset=['capacity_half_kN'])
        if len(sub) > 0:
            summary[probe] = {
                'scour': sub['scour_m'].tolist(),
                'capacity_half': sub['capacity_half_kN'].tolist(),
                'normalised': sub['normalised'].tolist() if 'normalised' in sub else [],
            }

    with open(OUTPUT_DIR / 'scour_sweep_summary.json', 'w') as f:
        json.dump(summary, f, indent=2, default=str)

    # Print report
    print("\n" + "=" * 70)
    print("SCOUR SWEEP RESULTS")
    print("=" * 70)
    print(f"\n{'Scour':>7s}  {'S/D':>6s}  {'Vmax [kN]':>10s}  {'V/V0':>6s}  "
          f"{'Hmax [kN]':>10s}  {'H/H0':>6s}")
    print("-" * 55)

    for scour in SCOUR_DEPTHS:
        v_row = df[(df['scour_m'] == scour) & (df['probe'] == 'Vmax')]
        h_row = df[(df['scour_m'] == scour) & (df['probe'] == 'Hmax')]
        v = v_row['capacity_half_kN'].values[0] if len(v_row) else None
        vn = v_row['normalised'].values[0] if len(v_row) and 'normalised' in v_row else None
        h = h_row['capacity_half_kN'].values[0] if len(h_row) else None
        hn = h_row['normalised'].values[0] if len(h_row) and 'normalised' in h_row else None
        print(f"{scour:7.1f}  {scour/D:6.3f}  "
              f"{v:10.0f}  {vn:6.3f}  {h:10.0f}  {hn:6.3f}"
              if v and h and vn and hn else f"{scour:7.1f}  INCOMPLETE")

    print(f"\nTotal time: {T_total:.0f}s ({T_total/3600:.1f} hours)")
    print(f"Output: {OUTPUT_DIR}")
    print("=" * 70)
