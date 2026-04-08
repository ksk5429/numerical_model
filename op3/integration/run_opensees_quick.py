"""
Quick OpenSees run: original params then new params.
Directly uses the ScourAnalysisModel class (copied inline to avoid import issues).
"""
import pandas as pd
import numpy as np
import os, sys, shutil, math

sys.stdout.reconfigure(line_buffering=True)

BASE = r'F:\GITHUB3\docs\manuscripts\current\ch4_1_optumgx_opensees_revised'
MODEL_DIR = os.path.join(BASE, '2_opensees_models')
POST_DIR = os.path.join(BASE, '3_postprocessing')
REF_DIR = os.path.join(BASE, '7_reference_data')
OUT_DIR = os.path.join(POST_DIR, 'processed_results_v2')

os.chdir(MODEL_DIR)

# Ensure SSOT is available
ssot_src = os.path.join(REF_DIR, 'SSOT_REAL_FINAL.txt')
if not os.path.exists('SSOT_REAL_FINAL.txt'):
    shutil.copy2(ssot_src, 'SSOT_REAL_FINAL.txt')

SCOUR_RANGE = np.arange(0.0, 5.1, 0.5)

def run_sweep(params_file, label, per_scour_file=None):
    """Run full scour sweep with given parameters file.

    If per_scour_file is given, uses per-scour parameters directly (no stress correction).
    Otherwise uses scour=0 reference + stress correction (original approach).
    """
    # Copy to expected name
    shutil.copy2(params_file, 'OpenSees_Master_Parameters_Global.xlsx')

    # Import inline to avoid triggering main()
    import openseespy.opensees as ops
    import re as re_mod

    SSOT_FILE = "SSOT_REAL_FINAL.txt"
    NUM_RIBS = 4
    BUCKET_RADIUS = 4.0
    BUCKET_DIAMETER = 8.0
    BUCKET_LENGTH = 9.3
    SMALL_STRAIN_MODIFIER = 3.0
    SOIL_PLUG_DENSITY = 2000.0
    MARINE_GROWTH_THICK = 0.05
    MARINE_GROWTH_RHO = 1400.0
    WATER_RHO = 1025.0
    ADDED_MASS_COEFF = 1.0
    E_steel = 2.1e11
    G_steel = 8.1e10
    rho_steel = 7850.0 * 1.05

    # Parse SSOT
    nodes = {}
    elements = []
    lumped_masses = {}

    with open(SSOT_FILE, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    section = None
    for line in lines:
        line = line.strip()
        if not line or line.startswith('#'):
            if '1. GLOBAL' in line: section = 'MAT'
            elif '2. NODAL' in line: section = 'MASS'
            elif '4. NODAL' in line: section = 'NODES'
            elif '5. ELEMENT' in line: section = 'TOWER'
            elif '6. ELEMENT' in line: section = 'TRIPOD'
            elif '8. SECONDARY' in line: section = 'SEC_MASS'
            continue

        if section == 'NODES':
            p = line.split('#')[0].split()
            if len(p) >= 4 and p[0].isdigit():
                nodes[int(p[0])] = (float(p[1]), float(p[2]), float(p[3]))
        elif section in ['MASS', 'SEC_MASS']:
            m = re_mod.search(r'NODE_MASS_(\d+):\s*([\d.E+\-]+)', line)
            if m:
                nid = int(m.group(1))
                lumped_masses[nid] = lumped_masses.get(nid, 0.0) + float(m.group(2))
        elif section in ['TOWER', 'TRIPOD']:
            p = line.split('#')[0].split()
            if len(p) >= 6:
                try:
                    elements.append({
                        'n1': int(p[1]), 'n2': int(p[2]),
                        'D_top': float(p[3]), 'D_bot': float(p[4]), 'thk': float(p[5]),
                    })
                except: pass

    # Load soil parameters
    raw_soil = pd.read_excel('OpenSees_Master_Parameters_Global.xlsx', sheet_name='OpenSees_Parameters')
    tip_params = pd.read_excel('OpenSees_Master_Parameters_Global.xlsx', sheet_name='Tip_Parameters')

    # Per-scour parameter lookup (for new pipeline)
    per_scour_springs = None
    if per_scour_file:
        per_scour_springs = pd.read_excel(per_scour_file, sheet_name='All_Springs')

    avail_scours = sorted(raw_soil['Scour_Depth'].unique())
    df_ref = raw_soil[raw_soil['Scour_Depth'] == avail_scours[0]].copy()
    df_h = df_ref[df_ref['Direction'] == 'H'].set_index('Node_Depth_Local').add_prefix('H_')
    df_v = df_ref[df_ref['Direction'] == 'V'].set_index('Node_Depth_Local').add_prefix('V_')
    soil_layers = df_h.join(df_v, how='outer').reset_index().sort_values('Node_Depth_Local')
    soil_layers = soil_layers.dropna(subset=['Node_Depth_Local'])
    soil_layers = soil_layers[soil_layers['Node_Depth_Local'] <= BUCKET_LENGTH]

    def calc_props(D, t):
        Di = D - 2*t
        A = (math.pi/4)*(D**2 - Di**2)
        I = (math.pi/64)*(D**4 - Di**4)
        return A, I, I, 2*I

    results = []
    base_freq = 0.0

    print(f"\n  {label}:")
    print(f"  {'Scour':>6} {'f1 (Hz)':>10} {'f/f0':>8}")
    print(f"  {'-'*28}")

    for i_scour, scour_depth in enumerate(SCOUR_RANGE):
        ops.wipe()
        ops.model('basic', '-ndm', 3, '-ndf', 6)

        node_id = 10000
        ele_id = 10000
        mat_id = 10000
        sec_id = 10000
        transf_id = 100
        rib_node_list = []

        # Build structural nodes
        for nid, (x, y, z) in nodes.items():
            ops.node(nid, x, y, z)

        # Build beams
        t_cnt = 1
        for ele in elements:
            n1, n2 = ele['n1'], ele['n2']
            if n1 not in nodes or n2 not in nodes: continue
            c1, c2 = nodes[n1], nodes[n2]
            dz = abs(c2[2] - c1[2])
            L = math.sqrt((c2[0]-c1[0])**2 + (c2[1]-c1[1])**2 + (c2[2]-c1[2])**2)
            if L < 1e-6: continue
            if dz/L > 0.99:
                ops.geomTransf('Linear', t_cnt, 0, 1, 0)
            else:
                ops.geomTransf('Linear', t_cnt, 0, 0, 1)

            D_avg = (ele['D_top'] + ele['D_bot']) / 2.0
            A, Iy, Iz, J = calc_props(D_avg, ele['thk'])
            s_tag = sec_id; sec_id += 1
            ops.section('Elastic', s_tag, E_steel, A, Iz, Iy, G_steel, J)
            ops.beamIntegration('Lobatto', ele_id, s_tag, 5)
            ops.element('forceBeamColumn', ele_id, n1, n2, t_cnt, ele_id, '-mass', A * rho_steel)
            ele_id += 1
            t_cnt += 1

        # Foundation
        t_vert = transf_id; transf_id += 1
        t_horz = transf_id; transf_id += 1
        ops.geomTransf('Linear', t_vert, 0, 1, 0)
        ops.geomTransf('Linear', t_horz, 0, 0, 1)

        A_rib = (2*math.pi*BUCKET_RADIUS*0.05)/NUM_RIBS

        for center in [215, 225, 235]:
            if center not in nodes: continue
            cx, cy, cz = nodes[center]

            for i_rib in range(NUM_RIBS):
                angle = 2*math.pi*i_rib/NUM_RIBS
                rx = cx + BUCKET_RADIUS*math.cos(angle)
                ry = cy + BUCKET_RADIUS*math.sin(angle)

                top = node_id; node_id += 1
                ops.node(top, rx, ry, cz)
                ops.element('elasticBeamColumn', ele_id, center, top, 100.0, 1e14, 1e14, 100.0, 100.0, 100.0, t_horz, '-mass', 1.0)
                ele_id += 1

                prev = top
                for _, row in soil_layers.iterrows():
                    depth = row['Node_Depth_Local']
                    if depth <= 0.01: continue

                    curr = node_id; node_id += 1
                    ops.node(curr, rx, ry, cz - depth)
                    rib_node_list.append(curr)

                    ops.element('elasticBeamColumn', ele_id, prev, curr, A_rib, E_steel, G_steel, 1.0, 1.0, 1.0, t_vert, '-mass', A_rib * rho_steel)
                    ele_id += 1

                    if depth > scour_depth:
                        if per_scour_springs is not None:
                            # Per-scour approach: use actual parameters for this scour depth
                            # Find closest scour in the per-scour data
                            avail_sc = sorted(per_scour_springs['scour_m'].unique())
                            closest_sc = min(avail_sc, key=lambda s: abs(s - scour_depth))

                            h_row = per_scour_springs[
                                (per_scour_springs['mode'] == 'H') &
                                (per_scour_springs['scour_m'] == closest_sc) &
                                (abs(per_scour_springs['depth_local_m'] - depth) < 0.3)
                            ]
                            v_row = per_scour_springs[
                                (per_scour_springs['mode'] == 'V') &
                                (per_scour_springs['scour_m'] == closest_sc) &
                                (abs(per_scour_springs['depth_local_m'] - depth) < 0.3)
                            ]

                            if len(h_row) == 0:
                                prev = curr
                                continue

                            h_row = h_row.iloc[0]
                            v_row = v_row.iloc[0] if len(v_row) > 0 else h_row

                            # Already includes dynamic modifier and per-scour VH capacity
                            p_mod = h_row['p_ult_kNm'] * 1000 / NUM_RIBS  # N/m
                            k_mod = h_row['k_ini_dynamic_kNm2'] * 1000 / NUM_RIBS  # N/m/m
                            t_mod = v_row['p_ult_kNm'] * 1000 / NUM_RIBS
                            kt_mod = v_row['k_ini_dynamic_kNm2'] * 1000 / NUM_RIBS

                            if k_mod < 1 or p_mod < 1:
                                prev = curr
                                continue

                            y50 = 0.5 * p_mod / k_mod
                            z50 = 0.5 * t_mod / kt_mod
                        else:
                            # Original approach: scour=0 reference + stress correction
                            sigma_old = depth * 10000.0
                            sigma_new = (depth - scour_depth) * 10000.0
                            if sigma_old <= 0 or sigma_new <= 0:
                                prev = curr
                                continue
                            sf = math.sqrt(sigma_new / sigma_old)

                            k_py = row.get('H_py_k_ini_Nm', 0)/NUM_RIBS
                            p_ult = row.get('H_py_p_ult_N', 0)/NUM_RIBS
                            k_tz = row.get('V_py_k_ini_Nm', k_py)/NUM_RIBS
                            t_ult = row.get('V_py_p_ult_N', p_ult*0.1)/NUM_RIBS

                            if k_py < 1:
                                prev = curr
                                continue

                            p_mod = p_ult * sf**2
                            k_mod = k_py * sf
                            t_mod = t_ult * sf**2
                            kt_mod = k_tz * sf

                            y50 = (0.5 * p_mod / k_mod) / SMALL_STRAIN_MODIFIER
                            z50 = (0.5 * t_mod / kt_mod) / SMALL_STRAIN_MODIFIER

                        mp = mat_id; mat_id += 1
                        mt = mat_id; mat_id += 1
                        ops.uniaxialMaterial('PySimple1', mp, 2, p_mod, y50, 0.0)
                        ops.uniaxialMaterial('TzSimple1', mt, 2, t_mod, z50, 0.0)

                        anc = node_id; node_id += 1
                        ops.node(anc, rx, ry, cz - depth)
                        ops.fix(anc, 1, 1, 1, 1, 1, 1)
                        ops.element('zeroLength', ele_id, anc, curr, '-mat', mp, mp, mt, '-dir', 1, 2, 3)
                        ele_id += 1

                    prev = curr

                # Tip spring
                if BUCKET_LENGTH > scour_depth and not tip_params.empty:
                    sigma_old = BUCKET_LENGTH * 10000.0
                    sigma_new = (BUCKET_LENGTH - scour_depth) * 10000.0
                    if sigma_new > 0:
                        sf = math.sqrt(sigma_new / sigma_old)
                        k_tip = tip_params.iloc[0]['Q_tip_stiffness_N'] / NUM_RIBS * 0.5
                        q_ult = tip_params.iloc[0]['Q_tip_capacity_N'] / NUM_RIBS
                        k_mod = k_tip * sf
                        q_mod = q_ult * sf**2
                        if k_mod >= 1000:
                            z50 = (0.5 * q_mod / k_mod) / SMALL_STRAIN_MODIFIER
                            mq = mat_id; mat_id += 1
                            ops.uniaxialMaterial('QzSimple1', mq, 2, q_mod, z50)
                            anc = node_id; node_id += 1
                            c = ops.nodeCoord(prev)
                            ops.node(anc, *c)
                            ops.fix(anc, 1, 1, 1, 1, 1, 1)
                            ops.element('zeroLength', ele_id, anc, prev, '-mat', mq, '-dir', 3)
                            ele_id += 1

        # Masses
        for n, m in lumped_masses.items():
            if n in nodes:
                ops.mass(n, m, m, m, 0, 0, 0)

        # Hydrodynamic mass
        for ele in elements:
            n1, n2 = ele['n1'], ele['n2']
            if n1 not in nodes or n2 not in nodes: continue
            z1, z2 = nodes[n1][2], nodes[n2][2]
            if z1 > 0 and z2 > 0: continue
            c1, c2 = nodes[n1], nodes[n2]
            L = math.sqrt((c2[0]-c1[0])**2 + (c2[1]-c1[1])**2 + (c2[2]-c1[2])**2)
            if L < 0.01: continue
            z_top, z_bot = max(z1, z2), min(z1, z2)
            L_sub = L if z_top <= 0 else L * ((0 - z_bot)/(z_top - z_bot)) if z_top > z_bot else 0
            if L_sub <= 0: continue
            D = (ele['D_top']+ele['D_bot'])/2
            De = D + 2*MARINE_GROWTH_THICK
            M_bio = (math.pi/4)*(De**2 - D**2) * MARINE_GROWTH_RHO * L_sub
            M_hyd = ADDED_MASS_COEFF * WATER_RHO * (math.pi/4)*(De**2) * L_sub
            M = M_bio + M_hyd
            ops.mass(n1, M/2, M/2, M/2, 0, 0, 0)
            ops.mass(n2, M/2, M/2, M/2, 0, 0, 0)

        # Soil plug mass
        mudline_z = -8.2
        scour_limit_z = mudline_z - scour_depth
        area_plug = (math.pi * BUCKET_RADIUS**2) / NUM_RIBS
        for nid in rib_node_list:
            z = ops.nodeCoord(nid)[2]
            if z < scour_limit_z:
                m_plug = area_plug * 0.5 * SOIL_PLUG_DENSITY
                ops.mass(nid, m_plug, m_plug, 0.0, 0, 0, 0)

        # Ghost stiffness
        mat_ghost = mat_id; mat_id += 1
        ops.uniaxialMaterial('Elastic', mat_ghost, 1.0)
        for nid in ops.getNodeTags():
            anc = node_id; node_id += 1
            ops.node(anc, *ops.nodeCoord(nid))
            ops.fix(anc, 1, 1, 1, 1, 1, 1)
            ops.element('zeroLength', ele_id, anc, nid, '-mat', *[mat_ghost]*6, '-dir', 1, 2, 3, 4, 5, 6)
            ele_id += 1

        # Eigen
        try:
            vals = ops.eigen('-fullGenLapack', 1)
            f1 = math.sqrt(vals[0])/(2*math.pi) if vals and vals[0] > 0 else 0.0
        except:
            f1 = 0.0

        if i_scour == 0: base_freq = f1
        ratio = f1 / base_freq if base_freq > 0 else 0.0
        results.append({'scour_m': float(scour_depth), 'f1_Hz': f1, 'f_f0': ratio})
        print(f"  {scour_depth:>6.1f} {f1:>10.4f} {ratio:>8.4f}")

    return pd.DataFrame(results), base_freq


# ============================================================
# RUN A: Original parameters
# ============================================================
print("=" * 80)
print("RUN A: Original parameters (OpenSees_Master_Parameters_Global.xlsx)")
print("=" * 80)

orig_file = os.path.join(POST_DIR, 'OpenSees_Master_Parameters_Global.xlsx')
df_a, bf_a = run_sweep(orig_file, "ORIGINAL")

# ============================================================
# RUN B: New pipeline parameters
# ============================================================
print("\n" + "=" * 80)
print("RUN B: New pipeline parameters (from raw Excel integration)")
print("=" * 80)

# Build new params Excel in original format
new_springs = pd.read_excel(os.path.join(OUT_DIR, '04_spring_parameters.xlsx'), sheet_name='All_Springs')
new_vh = pd.read_excel(os.path.join(OUT_DIR, '03_vh_capacity.xlsx'), sheet_name='Summary')
df_orig_tip = pd.read_excel(orig_file, sheet_name='Tip_Parameters')

new_rows = []
for mode in ['H', 'V']:
    s0 = new_springs[(new_springs['mode'] == mode) & (new_springs['scour_m'] == 0.0)].sort_values('depth_local_m')
    vh_s0 = new_vh[new_vh['scour_m'] == 0.0]
    cap = vh_s0['H_ult_kN'].values[0] if mode == 'H' else vh_s0['V_ult_kN'].values[0]

    for _, row in s0.iterrows():
        new_rows.append({
            'Scour_Depth': 0.0,
            'Direction': mode,
            'Node_Depth_Global': row['depth_global_m'],
            'Node_Depth_Local': row['depth_local_m'],
            'py_k_ini_Nm': row['k_ini_dynamic_kNm2'] * 1000,
            'py_p_ult_N': row['p_ult_kNm'] * 1000,
            'k_fit_A': 0, 'k_fit_B': 0,
            'SMALL_STRAIN_RATIO': 1,
            'Capacity_Global_kN': cap,
        })

new_params_file = os.path.join(MODEL_DIR, 'NEW_params_temp.xlsx')
with pd.ExcelWriter(new_params_file) as writer:
    pd.DataFrame(new_rows).to_excel(writer, sheet_name='OpenSees_Parameters', index=False)
    pd.DataFrame([{'Mode': 'H (P-Y)', 'a_coefficient': 0, 'b_exponent': 0, 'R_squared': 0, 'SMALL_STRAIN_RATIO': 1, 'Formula': 'depth-averaged'}]).to_excel(writer, sheet_name='Master_Fit_Coefficients', index=False)
    df_orig_tip.to_excel(writer, sheet_name='Tip_Parameters', index=False)

per_scour_file = os.path.join(OUT_DIR, '04_spring_parameters.xlsx')
df_b, bf_b = run_sweep(new_params_file, "NEW (per-scour VH + power-law)", per_scour_file=per_scour_file)

# Cleanup temp file
os.remove(new_params_file)

# ============================================================
# COMPARISON
# ============================================================
print("\n" + "=" * 80)
print("COMPARISON")
print("=" * 80)
print(f"\n  Field measurement: f1 = 0.2433 Hz")
print(f"  Original:  f1 = {bf_a:.4f} Hz (error = {(bf_a-0.2433)/0.2433*100:+.1f}%)")
print(f"  New:       f1 = {bf_b:.4f} Hz (error = {(bf_b-0.2433)/0.2433*100:+.1f}%)")

print(f"\n{'Scour':>6} {'Orig f1':>10} {'New f1':>10} {'Orig f/f0':>10} {'New f/f0':>10} {'Diff':>8}")
print("-" * 56)
for i in range(len(SCOUR_RANGE)):
    fo = df_a.iloc[i]
    fn = df_b.iloc[i]
    diff = (fn['f1_Hz'] - fo['f1_Hz']) / fo['f1_Hz'] * 100 if fo['f1_Hz'] > 0 else 0
    print(f"{SCOUR_RANGE[i]:>6.1f} {fo['f1_Hz']:>10.4f} {fn['f1_Hz']:>10.4f} {fo['f_f0']:>10.4f} {fn['f_f0']:>10.4f} {diff:>+8.2f}%")

# Save
out_file = os.path.join(OUT_DIR, '06_opensees_comparison.xlsx')
with pd.ExcelWriter(out_file) as writer:
    df_compare = pd.DataFrame({
        'scour_m': SCOUR_RANGE,
        'S_D': SCOUR_RANGE / 8.0,
        'orig_f1': df_a['f1_Hz'].values,
        'orig_f_f0': df_a['f_f0'].values,
        'new_f1': df_b['f1_Hz'].values,
        'new_f_f0': df_b['f_f0'].values,
    })
    df_compare.to_excel(writer, sheet_name='Comparison', index=False)
    pd.DataFrame([{
        'field_f1': 0.2433, 'orig_f1': bf_a,
        'orig_err_pct': (bf_a-0.2433)/0.2433*100,
        'new_f1': bf_b, 'new_err_pct': (bf_b-0.2433)/0.2433*100,
    }]).to_excel(writer, sheet_name='Summary', index=False)

print(f"\n  Saved: {out_file}")

# Restore original
shutil.copy2(orig_file, os.path.join(MODEL_DIR, 'OpenSees_Master_Parameters_Global.xlsx'))
print("\nDONE")
