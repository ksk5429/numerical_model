# -*- coding: utf-8 -*-
"""Generate PC1-PC4 production scripts: hybrid scour method."""
from pathlib import Path

TEMPLATE = '''# -*- coding: utf-8 -*-
"""
MC Production — %%PC%%: Scour %%SCOUR_STR%%
Hybrid method: physical extrude-delete + ParameterMap (soil + local scour excess)
Copy 2 files to this PC: this script + extract_all.py
Output: results_%%PC%%/
"""
from OptumGX import *
import numpy as np
import pandas as pd
import time, sys
from pathlib import Path as P
from scipy import stats
from scipy.linalg import cholesky

sys.path.insert(0, str(P(__file__).parent))
try:
    from extract_all import extract_full_output
    HAS_EXTRACT = True; print("  extract_all loaded.")
except ImportError:
    HAS_EXTRACT = False; print("  WARN: extract_all.py not found.")

PC = '%%PC%%'
SCOUR_DEPTHS = %%SCOUR_LIST%%
N_RUNS = 200
SEED = 42

D = 8.0; R = 4.0; S = float('nan'); N_sectors = 12
L_dom = 20 * R; H_dom = 15 * R
N_el = 6000; N_el_start = 3000; fan_angle = 30

# Random variables: 4 soil + 3 scour shape = 7 total
RV_su0   = dict(m=15.0, cov=0.25)
RV_ksu   = dict(m=20.0, cov=0.30)
RV_gamma = dict(m=10.0, cov=0.07, lb=6, ub=14)
RV_alpha = dict(m=0.67, cov=0.15, lb=0.3, ub=1.0)
RV_dmax  = dict(m=2.38, std=0.39)            # Kim et al. N(2.38, 0.39)
RV_asym  = dict(m=0.5, cov=0.30, lb=0.1, ub=1.0)
RV_theta = dict(lb=0, ub=np.pi)              # Uniform[0, pi] for half-model
R_EXT = 2 * D                                 # fixed scour extent
RHO_SU0_KSU = 0.5

OUTPUT_DIR = P(__file__).parent / f'results_{PC}'
OUTPUT_DIR.mkdir(exist_ok=True)
DATA_DIR = OUTPUT_DIR / 'data'
DATA_DIR.mkdir(exist_ok=True)

# ---------------------------------------------------------------------------
# Sampler
# ---------------------------------------------------------------------------
def ln_p(m, c):
    s = np.sqrt(np.log(1 + c**2))
    return np.log(m) - 0.5 * s**2, s

def beta_p(m, c, lb, ub):
    mu = (m - lb) / (ub - lb)
    v = ((m * c) / (ub - lb))**2
    if v >= mu * (1 - mu): return 2.0, 2.0
    t = mu * (1 - mu) / v - 1
    return mu * t, (1 - mu) * t

def gen_samples(n, seed):
    rng = np.random.default_rng(seed)
    # 7 LHS dims: su0, k_su, gamma, alpha_int, d_max, asym, theta_0
    u = np.zeros((n, 7))
    for j in range(7):
        p = rng.permutation(n)
        u[:, j] = (p + rng.uniform(size=n)) / n
    # Correlation su0-k_su only (dims 0,1)
    C = np.eye(7); C[0, 1] = C[1, 0] = RHO_SU0_KSU
    z = stats.norm.ppf(np.clip(u, 1e-10, 1 - 1e-10))
    try:
        Lt = cholesky(C, lower=True)
        Lc = cholesky(np.corrcoef(z.T), lower=True)
        z = z @ np.linalg.inv(Lc).T @ Lt.T
    except (np.linalg.LinAlgError, ValueError): pass  # correlation matrix not PD
    u = stats.norm.cdf(z)
    S = {}
    ml, sl = ln_p(RV_su0['m'], RV_su0['cov'])
    S['su0'] = stats.lognorm.ppf(u[:, 0], s=sl, scale=np.exp(ml))
    ml, sl = ln_p(RV_ksu['m'], RV_ksu['cov'])
    S['k_su'] = stats.lognorm.ppf(u[:, 1], s=sl, scale=np.exp(ml))
    sig = RV_gamma['m'] * RV_gamma['cov']
    S['gamma'] = np.clip(stats.norm.ppf(u[:, 2], loc=RV_gamma['m'], scale=sig),
                         RV_gamma['lb'], RV_gamma['ub'])
    a, b = beta_p(RV_alpha['m'], RV_alpha['cov'], RV_alpha['lb'], RV_alpha['ub'])
    S['alpha_int'] = RV_alpha['lb'] + stats.beta.ppf(u[:, 3], a, b) * (RV_alpha['ub'] - RV_alpha['lb'])
    S['d_max'] = np.maximum(stats.norm.ppf(u[:, 4], loc=RV_dmax['m'], scale=RV_dmax['std']), 0.01)
    a2, b2 = beta_p(RV_asym['m'], RV_asym['cov'], RV_asym['lb'], RV_asym['ub'])
    S['alpha_scour'] = RV_asym['lb'] + stats.beta.ppf(u[:, 5], a2, b2) * (RV_asym['ub'] - RV_asym['lb'])
    S['theta_0'] = RV_theta['lb'] + u[:, 6] * (RV_theta['ub'] - RV_theta['lb'])
    return S

# ---------------------------------------------------------------------------
# Hybrid ParameterMap builder
# ---------------------------------------------------------------------------
def build_hybrid_parametermap(su0, k_su, gamma_eff, scour_base, d_max,
                               alpha_scour, theta_0):
    """
    ParameterMap encoding:
      - Random soil profile: su = su0 + k_su*|z|
      - Local asymmetric scour EXCESS beyond physical scour_base
    Points above scour_base outside R: set to 0.001 (physically removed,
    but ParameterMap needs values for interpolation stability)
    """
    r_pts = np.array([0, R*0.5, R-0.3, R+0.3, R+R_EXT*0.1,
                      R+R_EXT*0.25, R+R_EXT*0.5, R+R_EXT, L_dom/4, L_dom/2])
    theta_pts = np.linspace(0, np.pi, N_sectors * 2 + 1)

    d_max_eff = max(d_max, scour_base + 0.1)
    z_above = np.linspace(0, -scour_base, 5) if scour_base > 0 else [0]
    z_excess = np.linspace(-scour_base, -d_max_eff - 1, 10)
    z_deep = np.linspace(-d_max_eff - 1, -H_dom, 10)
    z_pts = np.sort(np.unique(np.concatenate([z_above, z_excess, z_deep])))[::-1]

    sd, gd = [], []
    for r in r_pts:
        thetas = [0.0] if r < 1e-6 else theta_pts
        for th in thetas:
            x, y = r * np.cos(th), r * np.sin(th)
            # Local scour depth
            if r < R:
                d_local = 0
            else:
                d_edge = d_max * (alpha_scour +
                         (1 - alpha_scour) * np.cos((th - theta_0) / 2)**2)
                d_local = d_edge * np.exp(-2 * (r - R) / R_EXT)

            for z in z_pts:
                if r >= R and z > -scour_base:
                    # Above physical cut (removed by extrude-delete)
                    sd.append([x, y, z, 0.001])
                    gd.append([x, y, z, 0.001])
                elif r >= R and d_local > scour_base and z > -d_local:
                    # Local excess beyond physical cut
                    sd.append([x, y, z, 0.001])
                    gd.append([x, y, z, 0.001])
                else:
                    # Intact soil
                    sd.append([x, y, z, su0 + k_su * abs(z)])
                    gd.append([x, y, z, gamma_eff])

    for xc in [-L_dom, L_dom]:
        for yc in [0, L_dom / 2]:
            for zc in [0, -H_dom]:
                sd.append([xc, yc, zc, su0 + k_su * abs(zc)])
                gd.append([xc, yc, zc, gamma_eff])

    return np.array(sd), np.array(gd)

# ---------------------------------------------------------------------------
# Model builder
# ---------------------------------------------------------------------------
def run_probe(prj, su0, k_su, gamma, alpha_int, scour_base,
              d_max, alpha_scour, theta_0, probe, rid):
    name = f"{PC}_R{rid}_{probe}"

    su_arr, gm_arr = build_hybrid_parametermap(
        su0, k_su, gamma, scour_base, d_max, alpha_scour, theta_0)
    sumap = ParameterMap(su_arr)
    gmap = ParameterMap(gm_arr)

    Soil = prj.Tresca(name=f"S_{name}", cu=sumap, gamma_dry=gmap,
                       color=rgb(195, 165, 120))
    Fdn = prj.RigidPlate(name=f"F_{name}", color=rgb(130, 160, 180))

    m2 = prj.create_model(name=f"AX_{name}", model_type="plane_strain")
    m2.add_rectangle([0, -H_dom], [L_dom / 2, 0])
    m2.add_line([0, 0], [R, 0])
    m2.add_line([R, 0], [R, -S])
    sel = m2.select([L_dom / 4, -H_dom / 2], types="face")
    m2.set_solid(sel, Soil)
    sel = m2.select([R / 2, 0], types="edge")
    m2.set_plate(sel, Fdn, strength_reduction_factor=alpha_int)
    sel = m2.select([R, -S / 2], types="edge")
    m2.set_plate(sel, Fdn, strength_reduction_factor=alpha_int)

    mod = m2.revolve_2d_to_3d(angle_deg=180, N=N_sectors, name=name)
    m2.delete()
    try:
        sel = mod.select([0, 0, -H_dom / 2], types="edge")
        if sel: mod.delete_shapes(sel)
    except Exception: pass  # edge may not exist after revolution

    # Physical scour
    if scour_base > 0:
        sel = mod.select([R + 5, R + 5, 0], types="face")
        mod.extrude(sel, [0, 0, -scour_base])
        sel = mod.select([R + 5, R + 5, -scour_base / 2], types="volume")
        mod.delete_shapes(sel)

    mod.add_vertex([0, 0, 0])
    sel_c = mod.select([0, 0, 0], types="vertex")
    mod.set_resultpoint(sel_c)

    sel = mod.select([0, 0, 0], types="edge")
    mod.set_plate_bc(sel, displacement_x="fixed", displacement_y="fixed",
                     displacement_z="free", displacement_rotation="fixed")
    sel = mod.select([R, 0, -S / 2], types="edge")
    mod.set_plate_bc(sel, displacement_x="free", displacement_y="fixed",
                     displacement_z="free", displacement_rotation="fixed")
    sel = mod.select([-R, 0, -S / 2], types="edge")
    mod.set_plate_bc(sel, displacement_x="free", displacement_y="fixed",
                     displacement_z="free", displacement_rotation="fixed")
    mod.set_standard_fixities()
    mod.set_point_bc(shapes=sel_c,
                     displacement_x='fixed', displacement_y='fixed',
                     displacement_z='free', displacement_rotation_x='fixed',
                     displacement_rotation_y='fixed', displacement_rotation_z='fixed',
                     use_local_coord=False)

    for ang in np.linspace(0, 180, N_sectors + 1):
        try:
            sf = mod.select([R * np.cos(np.radians(ang)),
                             R * np.sin(np.radians(ang)), -S], types="vertex")
            if sf: mod.set_mesh_fan(shapes=sf, fan_angle=fan_angle)
        except Exception: pass  # vertex may not exist at this angle

    mod.set_analysis_properties(
        analysis_type='load_multiplier', element_type="mixed",
        no_of_elements=N_el, mesh_adaptivity='yes',
        adaptivity_iterations=3, start_elements=N_el_start,
        design_approach='unity')
    mod.zoom_all()

    if probe == 'Vmax':
        mod.set_point_load(sel_c, -1, direction="z", option="multiplier")
    elif probe == 'Hmax':
        se = mod.select([0, 0, 0], types="edge")
        bc = mod.get_features(se); mod.remove_features(bc)
        mod.set_plate_bc(se, displacement_x="free", displacement_y="fixed",
                         displacement_z="fixed", displacement_rotation="fixed")
        mod.set_point_load(sel_c, 1, direction="x", option="multiplier")
    elif probe == 'Mmax':
        se = mod.select([0, 0, 0], types="edge")
        bc = mod.get_features(se); mod.remove_features(bc)
        mod.set_plate_bc(se, displacement_x="free", displacement_y="fixed",
                         displacement_z="free", displacement_rotation="fixed")
        pc = mod.get_features(sel_c); mod.remove_features(pc)
        mod.add_vertex([R, 0, 0])
        sep = mod.select([R, 0, 0], types="vertex")
        mod.set_point_load(sep, -1, direction="z", option="multiplier")
        mod.add_line([0, 0, 0], [0, R, 0])
        sa = mod.select([0, R / 2, 0], types="edge")
        mod.set_plate_bc(sa, displacement_x="fixed", displacement_y="fixed",
                         displacement_z="fixed", displacement_rotation="free")

    t0 = time.time()
    prj.run_analysis()
    dt = time.time() - t0

    try: lm = float(mod.output.global_results.load_multiplier)
    except (AttributeError, TypeError, ValueError):
        try: lm = float(mod.output.critical_results.load_multiplier)
        except (AttributeError, TypeError, ValueError): lm = None

    if probe == 'Mmax' and lm is not None:
        lm = lm * R

    extras = {}
    if HAS_EXTRACT and lm is not None:
        try:
            ftag = f'run{rid}_S{int(scour_base)}_{probe}'
            _, _, extras = extract_full_output(mod.output, save_dir=DATA_DIR, tag=ftag)
        except Exception: pass  # non-critical extraction failure

    mod.delete()
    return lm, dt, extras

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    print("=" * 65)
    print(f"{PC}: MC PRODUCTION (Hybrid Scour)")
    print(f"Physical extrude-delete + ParameterMap (soil + local excess)")
    print(f"Scour depths: {SCOUR_DEPTHS} | N = {N_RUNS}")
    print(f"RVs: su0, k_su, gamma, alpha, d_max, asym, theta_0 (7 total)")
    print("=" * 65)

    samples = gen_samples(N_RUNS, SEED)
    csv_path = OUTPUT_DIR / f'mc_{PC}.csv'
    results = []; completed = set()
    if csv_path.exists():
        df = pd.read_csv(csv_path); results = df.to_dict('records')
        completed = set(zip(df['run'].astype(int), df['scour_base'].astype(float)))
        print(f"  Resume: {len(completed)} done.")

    gx = GX()
    prj = gx.create_project(f"MC_{PC}")
    prj.get_model("Model A").delete()
    T0 = time.time(); nf = 0

    for scour_base in SCOUR_DEPTHS:
        print(f"\\n{'=' * 50}")
        print(f"Scour base = {scour_base} m (S/D = {scour_base / D:.3f})")
        print(f"{'=' * 50}")

        for i in range(N_RUNS):
            rid = i + 1
            if (rid, scour_base) in completed: continue

            su0_i = samples['su0'][i]
            k_i   = samples['k_su'][i]
            g_i   = samples['gamma'][i]
            a_i   = samples['alpha_int'][i]
            dm_i  = samples['d_max'][i]
            as_i  = samples['alpha_scour'][i]
            th_i  = samples['theta_0'][i]

            # Scale d_max by scour_base ratio so local scour
            # varies AROUND the base depth
            dm_scaled = dm_i * (scour_base / RV_dmax['m']) if scour_base > 0 else 0.0

            row = dict(
                run=rid, scour_base=scour_base, S_D=scour_base / D,
                su0=su0_i, k_su=k_i, gamma=g_i, alpha_int=a_i,
                d_max=dm_scaled, d_max_raw=dm_i,
                alpha_scour=as_i, theta_0_deg=np.degrees(th_i), pc=PC)

            print(f"  [{rid}/{N_RUNS}] su0={su0_i:.1f} k={k_i:.1f} "
                  f"dm={dm_scaled:.2f} as={as_i:.2f} th={np.degrees(th_i):.0f}",
                  end="")

            for probe in ['Vmax', 'Hmax', 'Mmax']:
                try:
                    lm, dt, ex = run_probe(
                        prj, su0_i, k_i, g_i, a_i,
                        scour_base, dm_scaled, as_i, th_i,
                        probe, f"{rid}_S{int(scour_base)}")
                    row[f'{probe}_kN'] = lm
                    row[f'{probe}_time'] = dt
                    row.update({f'{probe}_{k}': v for k, v in ex.items()})
                    print(f" | {probe}={'%.0f' % lm if lm else 'FAIL'}", end="")
                    if lm is None: nf += 1
                except Exception as e:
                    row[f'{probe}_kN'] = None; row[f'{probe}_time'] = 0; nf += 1
                    print(f" | {probe}=ERR", end="")

            print()
            results.append(row)
            pd.DataFrame(results).to_csv(csv_path, index=False)

            nd = len(results)
            if nd >= 10 and nf / nd > 0.1:
                print(f"  WARN: {nf}/{nd} failures ({nf / nd * 100:.0f}%)")
            if rid % 20 == 0:
                df_t = pd.DataFrame(results)
                sc = df_t[df_t['scour_base'] == scour_base]
                for p in ['Vmax', 'Hmax', 'Mmax']:
                    v = sc[f'{p}_kN'].dropna()
                    if len(v) >= 20:
                        print(f"    [{p}] n={len(v)} mean={v.mean():.0f} "
                              f"COV={v.std() / v.mean():.4f}")

    Tt = time.time() - T0
    print(f"\\n{'=' * 65}")
    print(f"{PC} DONE. {len(results)} entries. {Tt / 3600:.1f} hours.")
    print(f"Data: {len(list(DATA_DIR.glob('*.csv')))} CSVs")
    print(f"{'=' * 65}")
'''

assignments = {
    'PC1': [0.0, 1.0],
    'PC2': [2.0],
    'PC3': [3.0, 4.0],
    'PC4': [5.0],
}

out = Path(__file__).parent
for pc, scours in assignments.items():
    code = TEMPLATE.replace('%%PC%%', pc)
    code = code.replace('%%SCOUR_LIST%%', str(scours))
    code = code.replace('%%SCOUR_STR%%', ', '.join(f'{s}m' for s in scours))
    fp = out / f'run_{pc}.py'
    fp.write_text(code, encoding='utf-8')
    n = 200 * len(scours) * 3
    d = n * 8 / 60 / 24
    print(f'{pc}: scour {scours} -> {n} analyses -> ~{d:.1f} days')

print('\\nAll scripts generated. Copy run_PCx.py + extract_all.py to each PC.')
