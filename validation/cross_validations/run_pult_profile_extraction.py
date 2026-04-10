"""
OptumGX p_ult(z) depth profile extraction and validation.

Runs Hmax probe on a d/D=0.5 skirted foundation in homogeneous
Tresca clay, extracts plate pressures per depth slice, and computes
the normalized lateral bearing capacity factor Np(z) = p(z)/(su*D).

Reference profiles:
  - Bransby & Randolph (1998): Np ~ 2 at surface to 9-12 at depth
  - Martin & Randolph (2006): Np_base ~ 9.14 (rough) for deep flow
  - Vulpe (2015): integrated NcH = 4.17 for d/D=0.5

Usage:
    Run with OptumGX venv: .venv/Scripts/python.exe -u this_script.py
"""
import builtins
import sys
import json
import re
import time as _time

sys.path.insert(0, '.')
import numpy as np
import pandas as pd

from OptumGX import *

# Restore clobbered builtins
time = _time
float = builtins.float
int = builtins.int
abs = builtins.abs
print = builtins.print
round = builtins.round
str = builtins.str
range = builtins.range
len = builtins.len
type = builtins.type
max = builtins.max
min = builtins.min
sum = builtins.sum
list = builtins.list
sorted = builtins.sorted
any = builtins.any
hasattr = builtins.hasattr
getattr = builtins.getattr


def parse_val(attr):
    if attr is None:
        return None
    if isinstance(attr, (int, float)):
        return attr
    if isinstance(attr, np.ndarray):
        return attr.tolist()
    if isinstance(attr, (builtins.list, tuple)):
        return [float(x) if isinstance(x, (int, float, np.floating)) else x
                for x in attr]
    s = str(attr)
    m = re.search(r'value:\s*(.*)', s)
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
    return parse_val(getattr(obj, name, None))


def main():
    su = 50.0
    gamma = 0.01
    D = 10.0
    R = D / 2
    S = D * 0.5  # d/D = 0.5
    N_sectors = 12
    L_dom = 12 * R
    H_dom = 8 * R
    N_el = 10000
    N_el_start = 6000

    print("=" * 60, flush=True)
    print("p_ult(z) Depth Profile Extraction", flush=True)
    print(f"D={D}m, S={S}m, d/D=0.5, su={su}kPa", flush=True)
    print("=" * 60, flush=True)

    gx = GX()
    prj = gx.create_project('Pult_Profile')
    try:
        prj.get_model('Model A').delete()
    except Exception:
        pass

    Soil = prj.Tresca(name='Soil', cu=su, gamma_dry=gamma,
                       color=rgb(195, 165, 120))
    Fdn = prj.RigidPlate(name='Fdn', color=rgb(130, 160, 180))

    # Build via 2D revolve
    m2 = prj.create_model(name='AX', model_type='plane_strain')
    m2.add_rectangle([0, -H_dom], [L_dom / 2, 0])
    m2.add_line([0, 0], [R, 0])
    m2.add_line([R, 0], [R, -S])
    sel = m2.select([L_dom / 4, -H_dom / 2], types='face')
    m2.set_solid(sel, Soil)
    sel = m2.select([R / 2, 0], types='edge')
    m2.set_plate(sel, Fdn, strength_reduction_factor=1.0)
    sel = m2.select([R, -S / 2], types='edge')
    m2.set_plate(sel, Fdn, strength_reduction_factor=1.0)

    mod = m2.revolve_2d_to_3d(angle_deg=180, N=N_sectors, name='Hmax')
    m2.delete()

    try:
        sel = mod.select([0, 0, -H_dom / 2], types='edge')
        if sel:
            mod.delete_shapes(sel)
    except Exception:
        pass

    mod.add_vertex([0, 0, 0])
    sel_c = mod.select([0, 0, 0], types='vertex')
    mod.set_resultpoint(sel_c)

    # Hmax BCs
    sel_edge = mod.select([0, 0, 0], types='edge')
    mod.set_plate_bc(sel_edge, displacement_x='free', displacement_y='fixed',
                     displacement_z='fixed', displacement_rotation='fixed')
    for x_sign in [1, -1]:
        try:
            sel = mod.select([x_sign * R, 0, -S / 2], types='edge')
            mod.set_plate_bc(sel, displacement_x='free', displacement_y='fixed',
                             displacement_z='free', displacement_rotation='fixed')
        except Exception:
            pass

    mod.set_standard_fixities()
    mod.set_point_bc(
        shapes=sel_c,
        displacement_x='free', displacement_y='fixed',
        displacement_z='fixed',
        displacement_rotation_x='fixed',
        displacement_rotation_y='fixed',
        displacement_rotation_z='fixed',
    )

    for ang in np.linspace(0, 180, N_sectors + 1):
        try:
            sf = mod.select([
                R * np.cos(np.radians(ang)),
                R * np.sin(np.radians(ang)),
                -S,
            ], types='vertex')
            if sf:
                mod.set_mesh_fan(shapes=sf, fan_angle=30)
        except Exception:
            pass

    mod.set_analysis_properties(
        analysis_type='load_multiplier', element_type='mixed',
        no_of_elements=N_el, mesh_adaptivity='yes',
        adaptivity_iterations=3, start_elements=N_el_start,
        design_approach='unity',
    )
    mod.set_point_load(sel_c, 1, direction='x', option='multiplier')
    mod.zoom_all()

    print("Running Hmax analysis...", flush=True)
    t0 = time.time()
    prj.run_analysis()
    dt = time.time() - t0

    try:
        lm = float(mod.output.global_results.load_multiplier)
    except Exception:
        try:
            lm = float(mod.output.critical_results.load_multiplier)
        except Exception:
            lm = None

    if lm is None:
        print("ERROR: no load multiplier", flush=True)
        return 1

    H_full = abs(lm) * 2
    A = np.pi * R**2
    NcH = H_full / (A * su)
    print(f"H_ult = {H_full:.1f} kN, NcH = {NcH:.3f} (time={dt:.0f}s)",
          flush=True)

    # === Extract plate pressures ===
    print("\nExtracting plate pressures...", flush=True)
    rows = []
    for plate in mod.output.plate:
        row = {}
        if hasattr(plate, 'topology'):
            top = plate.topology
            for c in ['X', 'Y', 'Z']:
                v = gprop(top, c)
                if isinstance(v, builtins.list):
                    for j, val in enumerate(v, 1):
                        row[f'{c}_{j}'] = val
        if hasattr(plate, 'results'):
            res = plate.results
            for cat_name, props in [
                ('total_pressures',
                 ['sigma_plus', 'sigma_minus', 'tau_plus', 'tau_minus']),
            ]:
                cat = getattr(res, cat_name, None)
                if cat is None:
                    continue
                for prop in props:
                    v = gprop(cat, prop)
                    if isinstance(v, builtins.list):
                        for j, val in enumerate(v, 1):
                            row[f'{prop}_{j}'] = val
                    elif v is not None:
                        row[prop] = v
        rows.append(row)

    df = pd.DataFrame(rows)
    print(f"Plate elements: {len(df)}", flush=True)

    if 'X_1' not in df.columns:
        print("ERROR: no plate coordinates", flush=True)
        return 1

    # Geometry
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
    df['nz'] = cross[:, 2] / norms.flatten()
    df['Rc'] = np.sqrt(df['Xc']**2 + df['Yc']**2)

    # Classify
    df['part'] = 'soil'
    df.loc[df['Zc'] > -0.3, 'part'] = 'lid'
    df.loc[(df['Zc'] < -0.3) & (df['Zc'] > -(S - 0.3)) &
           (df['Rc'] > R * 0.8), 'part'] = 'skirt'
    df.loc[df['Zc'] < -(S - 0.3), 'part'] = 'tip'

    print(f"Parts: lid={sum(df['part']=='lid')}, "
          f"skirt={sum(df['part']=='skirt')}, "
          f"tip={sum(df['part']=='tip')}, "
          f"soil={sum(df['part']=='soil')}", flush=True)

    # Net pressure -> horizontal force
    sp = sorted([c for c in df.columns if c.startswith('sigma_plus_')])
    sm = sorted([c for c in df.columns if c.startswith('sigma_minus_')])
    tp = sorted([c for c in df.columns if c.startswith('tau_plus_')])
    tm = sorted([c for c in df.columns if c.startswith('tau_minus_')])

    df['sig_net'] = (df[sp].mean(axis=1) - df[sm].mean(axis=1)) if sp and sm else 0
    df['tau_net'] = (df[tp].mean(axis=1) + df[tm].mean(axis=1)) if tp and tm else 0
    df['dFx'] = df['sig_net'] * df['area'] * df['nx'] + \
                df['tau_net'] * df['area'] * abs(df['nz'])

    # Depth profile (skirt only)
    skirt = df[df['part'] == 'skirt'].copy()
    n_slices = 10
    bounds = np.linspace(0.0, -S, n_slices + 1)

    print(f"\n{'z/L':>6} {'z_mid':>8} {'p(kN/m)':>10} {'Np':>8}", flush=True)
    print("-" * 36, flush=True)

    profile = []
    for i in range(n_slices):
        zt, zb = bounds[i], bounds[i + 1]
        zm = (zt + zb) / 2
        dz = abs(zt - zb)
        mask = (skirt['Zc'] <= zt) & (skirt['Zc'] > zb)
        Hslice = skirt.loc[mask, 'dFx'].sum()
        p = Hslice / dz if dz > 0 else 0
        Np = p / (su * D) if (su * D) > 0 else 0
        z_L = abs(zm) / S
        profile.append({
            'z_mid': round(zm, 2),
            'z_L': round(z_L, 3),
            'p_kN_m': round(p, 1),
            'Np': round(Np, 3),
        })
        print(f"{z_L:>6.2f} {zm:>8.2f} {p:>10.1f} {Np:>8.3f}", flush=True)

    # Consistency check
    total_H_profile = sum(r['p_kN_m'] for r in profile) * (S / n_slices) * 2
    ratio = total_H_profile / H_full if H_full > 0 else 0
    print(f"\nIntegrated H from skirt profile: {total_H_profile:.1f} kN",
          flush=True)
    print(f"Global Hmax: {H_full:.1f} kN", flush=True)
    print(f"Skirt fraction: {ratio:.3f}", flush=True)
    print(f"(Remaining {1 - ratio:.1%} from lid and tip)", flush=True)

    # Published references
    print("\n--- Reference Np values ---", flush=True)
    print("Bransby & Randolph (1998): Np = 2 (surface) to 9-12 (deep)",
          flush=True)
    print("Martin & Randolph (2006): Np_base = 9.14 (rough, deep flow)",
          flush=True)
    print(f"Average Np from profile: "
          f"{np.mean([r['Np'] for r in profile]):.2f}", flush=True)

    # Save
    out_path = 'validation/cross_validations/pult_depth_profile.csv'
    pd.DataFrame(profile).to_csv(out_path, index=False)

    result = {
        'H_ult_kN': round(H_full, 1),
        'NcH': round(NcH, 3),
        'profile': profile,
        'skirt_fraction': round(ratio, 3),
        'time_s': round(dt, 0),
    }
    json_path = 'validation/cross_validations/pult_profile_results.json'
    with open(json_path, 'w') as f:
        json.dump(result, f, indent=2)
    print(f"\nSaved: {out_path}, {json_path}", flush=True)

    mod.delete()
    print("DONE", flush=True)
    return 0


if __name__ == '__main__':
    sys.exit(main())
