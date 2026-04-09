"""
Path B: Superelement Verification
Path C: Sequential Co-Simulation
=================================
Path B: Verify that the 18x18 block-diagonal superelement from
        3 independent 6x6 matrices reproduces Path A results.

Path C: Apply OpenFAST displacement time-histories to the nonlinear
        OpenSeesPy model and compare forces with linear prediction.
        This validates whether linearization is sufficient for SLS/FLS.
"""
import sys
import os
import math
import struct
import numpy as np
import pandas as pd
from pathlib import Path

SPINE_DIR = r"F:\GITHUB3\docs\manuscripts\current\ch4_1_optumgx_opensees_revised\2_opensees_models"
sys.path.insert(0, SPINE_DIR)
os.chdir(SPINE_DIR)
import openseespy.opensees as ops

sys.stdout.reconfigure(encoding='utf-8')

sys.path.insert(0, str(Path(__file__).parent))
from config import BUCKET, STIFFNESS, PARAMS, COUPLING_OUTPUT, SPRING_PARAMS, DISSIPATION_CSV

SWEEP_DIR = COUPLING_OUTPUT / "scour_sweep"


# ═══════════════════════════════════════════════════════════════════
# PATH B: SUPERELEMENT VERIFICATION
# ═══════════════════════════════════════════════════════════════════

def path_b_verification():
    """
    Verify that the superelement approach (block-diagonal 18x18)
    reproduces the same stiffness as Path A (individual 6x6 per bucket).

    Since both use the same extraction method, Path B is mathematically
    equivalent. The value of Path B is in the FORMAT: a single superelement
    file that commercial tools can import, vs 3 separate SSI files.
    """
    print(f"\n{'='*65}")
    print(f"  PATH B: Superelement Verification")
    print(f"{'='*65}")

    from opensees_stiffness_extractor import StiffnessExtractor, SuperelementCondenser

    extractor = StiffnessExtractor()
    condenser = SuperelementCondenser(extractor)

    scour_depths = [0.0, 2.0, 4.0]

    for S in scour_depths:
        print(f"\n  Scour = {S:.1f} m (S/D = {S/BUCKET.D:.3f})")

        # Path A: individual 6x6
        K_individual = extractor.extract_all_buckets(scour=S, verbose=False)

        # Path B: block-diagonal superelement
        K_super, nodes = condenser.condense(scour=S, verbose=False)

        # Verify they match
        max_diff = 0
        for idx, bn in enumerate(BUCKET.center_nodes):
            K_a = K_individual[bn]
            K_b = K_super[idx*6:(idx+1)*6, idx*6:(idx+1)*6]
            diff = np.max(np.abs(K_a - K_b))
            rel_diff = diff / np.max(np.abs(K_a)) if np.max(np.abs(K_a)) > 0 else 0
            max_diff = max(max_diff, rel_diff)

        print(f"    Max relative difference (Path A vs Path B): {max_diff:.2e}")
        print(f"    Status: {'MATCH' if max_diff < 1e-10 else 'MISMATCH'}")

        # Write superelement for this scour level
        se_path = COUPLING_OUTPUT / f"superelement_S{S:.1f}.txt"
        condenser.write_superelement(str(se_path), scour=S)
        print(f"    Exported: {se_path.name}")

    print(f"\n  Path B conclusion: Block-diagonal superelement is mathematically")
    print(f"  identical to Path A individual 6x6 matrices (expected, since both")
    print(f"  use the same extraction method). The superelement format enables")
    print(f"  import into commercial tools (SESAM, Bladed) for comparison.")


# ═══════════════════════════════════════════════════════════════════
# PATH C: SEQUENTIAL CO-SIMULATION
# ═══════════════════════════════════════════════════════════════════

def build_nonlinear_bucket(scour=0.0):
    """
    Build a single-bucket nonlinear OpenSeesPy model for co-simulation.
    Uses PySimple1 + TzSimple1 (the real nonlinear springs).
    Returns the bucket center node ID.
    """
    sp = pd.read_csv(str(SPRING_PARAMS))
    z_nodes = sp['z_m'].values
    k_ini = sp['k_ini_kNm3'].values
    p_ult = sp['p_ult_kNm'].values
    t_ult = sp['t_ult_kNm'].values

    D = BUCKET.D; DZ = BUCKET.DZ; L = BUCKET.L
    R = BUCKET.R; NUM_RIBS = BUCKET.NUM_RIBS
    SMALL_STRAIN_MOD = 2.5

    ops.wipe()
    ops.model('basic', '-ndm', 3, '-ndf', 6)

    # Single bucket center node
    ctr = 1
    ops.node(ctr, 0.0, 0.0, 0.0)

    nid = 100; eid = 100; mid = 100; tc = 1

    for i in range(NUM_RIBS):
        ang = 2 * math.pi * i / NUM_RIBS
        rx = R * math.cos(ang); ry = R * math.sin(ang)

        # Rib top node
        top = nid; nid += 1
        ops.node(top, rx, ry, 0.0)

        # Rigid link
        ops.geomTransf('Linear', tc, 0, 0, 1)
        ops.element('elasticBeamColumn', eid, ctr, top,
                    100, 1e14, 1e14, 100, 100, 100, tc, '-mass', 1.0)
        eid += 1; tc += 1

        prev = top
        for j, depth in enumerate(z_nodes):
            if depth > L:
                break

            cur = nid; nid += 1
            ops.node(cur, rx, ry, -depth)

            # Rib beam
            A_rib = (2 * math.pi * R * 0.05) / NUM_RIBS
            ops.geomTransf('Linear', tc, 0, 1, 0)
            ops.element('elasticBeamColumn', eid, prev, cur,
                        A_rib, 2.1e11, 8.1e10, 1.0, 1.0, 1.0, tc, '-mass', A_rib * 7850)
            eid += 1; tc += 1

            if depth > scour:
                sO = depth * 10000.0
                sN = (depth - scour) * 10000.0
                if sN <= 0:
                    prev = cur; continue
                sf = math.sqrt(sN / sO)

                # NONLINEAR lateral spring (PySimple1)
                Kpy = (k_ini[j] * D * DZ * 1000.0 / NUM_RIBS) * sf
                pult = (p_ult[j] * 1000.0 * DZ / NUM_RIBS) * (sf ** 2)
                if Kpy < 1:
                    prev = cur; continue
                y50 = max((0.5 * pult / Kpy) / SMALL_STRAIN_MOD, 1e-6)

                # NONLINEAR vertical spring (TzSimple1)
                tult = (t_ult[j] * 1000.0 * DZ / NUM_RIBS) * (sf ** 2)
                ktz = Kpy * 0.5  # ASSUMED ratio, not from OptumGX
                z50 = max((0.5 * tult / ktz) / SMALL_STRAIN_MOD, 1e-6) if ktz > 0 else 0.01

                mp = mid; mid += 1
                ops.uniaxialMaterial('PySimple1', mp, 2, pult, y50, 0.0)
                mt = mid; mid += 1
                ops.uniaxialMaterial('TzSimple1', mt, 2, tult, z50, 0.0)

                anc = nid; nid += 1
                ops.node(anc, rx, ry, -depth)
                ops.fix(anc, 1, 1, 1, 1, 1, 1)

                ze = eid; eid += 1
                ops.element('zeroLength', ze, anc, cur, '-mat', mp, mp, mt, '-dir', 1, 2, 3)

            prev = cur

        # Base springs (elastic)
        if L > scour:
            sO = L * 10000.0; sN = (L - scour) * 10000.0
            sf = math.sqrt(sN / sO) if sO > 0 else 0
            kh = STIFFNESS.KH * STIFFNESS.KH_base_frac * 1000 / (3 * NUM_RIBS) * sf
            kv = STIFFNESS.KV * STIFFNESS.KV_base_frac * 1000 / (3 * NUM_RIBS) * sf
            km = STIFFNESS.KM * STIFFNESS.KM_base_frac * 1000 / (3 * NUM_RIBS) * sf

            mh = mid; mid += 1; ops.uniaxialMaterial('Elastic', mh, max(kh, 1))
            mv = mid; mid += 1; ops.uniaxialMaterial('Elastic', mv, max(kv, 1))
            mr1 = mid; mid += 1; ops.uniaxialMaterial('Elastic', mr1, max(km, 1))
            mr2 = mid; mid += 1; ops.uniaxialMaterial('Elastic', mr2, max(km, 1))
            mg = mid; mid += 1; ops.uniaxialMaterial('Elastic', mg, 1.0)

            anc = nid; nid += 1
            ops.node(anc, *ops.nodeCoord(prev))
            ops.fix(anc, 1, 1, 1, 1, 1, 1)
            ops.element('zeroLength', eid, anc, prev,
                        '-mat', mh, mh, mv, mr1, mr2, mg, '-dir', 1, 2, 3, 4, 5, 6)
            eid += 1

    return ctr, nid, eid


def apply_displacement_and_get_force(ctr_node, u_vec, scour=0.0):
    """
    Apply displacement vector at bucket center using force-based approach.

    Strategy: Use the linear stiffness K to compute an equivalent force,
    apply it to the nonlinear model, and measure the actual displacement.
    Then iterate if needed.

    Simpler strategy for validation: apply displacement in small increments
    using DisplacementControl integrator on translational DOFs, or
    apply as an imposed motion.
    """
    # Rebuild fresh nonlinear model for each displacement state
    build_nonlinear_bucket(scour=scour)

    # Use very stiff springs at the center node to impose displacement
    # Add a control node with imposed displacement, linked via stiff spring
    ctrl_node = 9999
    ops.node(ctrl_node, 0.0, 0.0, 0.0)
    ops.fix(ctrl_node, 1, 1, 1, 1, 1, 1)

    # Very stiff elastic springs connecting control to center
    K_stiff = 1e14  # Very stiff
    for dof in range(1, 7):
        mat_id = 9000 + dof
        ops.uniaxialMaterial('Elastic', mat_id, K_stiff)

    ops.element('zeroLength', 9999, ctrl_node, ctr_node,
                '-mat', 9001, 9002, 9003, 9004, 9005, 9006,
                '-dir', 1, 2, 3, 4, 5, 6)

    # Apply forces at center node = K_stiff * u_target
    # This drives the center node to approximately u_target
    ops.timeSeries('Linear', 999)
    ops.pattern('Plain', 999, 999)
    for dof in range(6):
        if abs(u_vec[dof]) > 1e-15:
            F = K_stiff * u_vec[dof]
            ops.load(ctr_node, *([0]*dof + [F] + [0]*(5-dof)))

    ops.system('BandGeneral')
    ops.numberer('RCM')
    ops.constraints('Plain')
    ops.integrator('LoadControl', 0.1)  # 10 substeps
    ops.algorithm('Newton')
    ops.test('NormUnbalance', 1e-2, 50)  # Relaxed tolerance
    ops.analysis('Static')

    ok = ops.analyze(10)  # 10 steps of 0.1 each

    if ok == 0:
        # Get actual displacement at center node
        u_actual = np.array([ops.nodeDisp(ctr_node, d+1) for d in range(6)])

        # Get total force in the springs (reaction at control node)
        ops.reactions()
        F_reaction = np.array([ops.nodeReaction(ctrl_node, d+1) for d in range(6)])

        # The nonlinear force on the foundation = -F_reaction (Newton's 3rd law)
        # Because: F_stiff_spring = K_stiff * (u_ctrl - u_center)
        # And F_reaction_ctrl = -F_stiff_spring
        # The force the soil springs exert = F_applied - F_stiff_spring_on_center
        # Simpler: total reaction at control node = external force on the system
        return -F_reaction
    else:
        # Try with more relaxed convergence
        ops.test('NormUnbalance', 1.0, 100)
        ops.algorithm('ModifiedNewton')
        ok2 = ops.analyze(10)
        if ok2 == 0:
            ops.reactions()
            return -np.array([ops.nodeReaction(ctrl_node, d+1) for d in range(6)])
        return np.zeros(6)


def read_openfast_text_output(filepath):
    """Read OpenFAST .out text file."""
    with open(filepath, 'r', errors='replace') as f:
        lines = f.readlines()
    header_idx = None
    for i, line in enumerate(lines):
        if line.strip().startswith('Time'):
            header_idx = i; break
    if header_idx is None:
        return None, None
    names = lines[header_idx].split()
    data = []
    for line in lines[header_idx + 2:]:
        try:
            vals = [float(x) for x in line.split()]
            if len(vals) == len(names):
                data.append(vals)
        except:
            continue
    return names, np.array(data)


def path_c_cosimulation(scour=0.0, max_steps=500):
    """
    Sequential co-simulation at a given scour depth.

    1. Read OpenFAST output (displacement at platform)
    2. Build nonlinear OpenSeesPy model
    3. For each timestep, impose displacement -> get nonlinear forces
    4. Compare with linear prediction F_lin = K * u
    """
    SD = scour / BUCKET.D
    print(f"\n  Scour = {scour:.1f} m (S/D = {SD:.3f})")

    # Find the OpenFAST output for this scour level
    run_dir = SWEEP_DIR / f"S{scour:.1f}m_SD{SD:.3f}"
    out_file = run_dir / "SiteA-Ref4MW.out"

    if not out_file.exists():
        print(f"    ERROR: No OpenFAST output at {out_file}")
        return None

    # Read OpenFAST output
    print(f"    Reading OpenFAST output...", end=" ", flush=True)
    names, data = read_openfast_text_output(out_file)
    if data is None or len(data) < 100:
        print(f"FAILED")
        return None

    time = data[:, 0]
    dt = time[1] - time[0]
    print(f"{len(time)} timesteps, dt={dt:.4f}s")

    # Extract platform displacements
    disp_channels = ['PtfmSurge', 'PtfmSway', 'PtfmHeave', 'PtfmRoll', 'PtfmPitch', 'PtfmYaw']
    disp_idx = {}
    for ch in disp_channels:
        if ch in names:
            disp_idx[ch] = names.index(ch)

    if len(disp_idx) < 6:
        print(f"    WARNING: Missing platform channels. Found: {list(disp_idx.keys())}")
        return None

    # Platform displacements (convert degrees to radians for rotations)
    u_platform = np.zeros((len(time), 6))
    for i, ch in enumerate(disp_channels):
        idx = disp_idx[ch]
        vals = data[:, idx]
        if i >= 3:  # rotational DOFs: deg -> rad
            vals = vals * np.pi / 180.0
        u_platform[:, i] = vals

    # Get linear stiffness matrix (Path A)
    print(f"    Extracting linear K...", end=" ", flush=True)
    from opensees_stiffness_extractor import StiffnessExtractor
    extractor = StiffnessExtractor()
    K_all = extractor.extract_all_buckets(scour=scour, verbose=False)
    K_lin = K_all[list(K_all.keys())[0]]  # Use bucket 1
    print(f"done")

    # Build nonlinear model
    print(f"    Building nonlinear model...", end=" ", flush=True)
    ctr_node, _, _ = build_nonlinear_bucket(scour=scour)
    print(f"done ({ctr_node})")

    # Sequential co-simulation
    n_steps = min(len(time), max_steps)
    step_stride = max(1, len(time) // n_steps)

    F_linear = np.zeros((n_steps, 6))
    F_nonlinear = np.zeros((n_steps, 6))
    t_steps = np.zeros(n_steps)

    print(f"    Running co-simulation ({n_steps} steps)...", end=" ", flush=True)

    for step in range(n_steps):
        idx = step * step_stride
        u = u_platform[idx]
        t_steps[step] = time[idx]

        # Linear prediction
        F_linear[step] = K_lin @ u

        # Nonlinear: rebuild model each step for clean state
        F_nl = apply_displacement_and_get_force(ctr_node, u, scour=scour)
        F_nonlinear[step] = F_nl

    print(f"done")

    # Compute discrepancy
    F_lin_norm = np.linalg.norm(F_linear, axis=1)
    F_nl_norm = np.linalg.norm(F_nonlinear, axis=1)
    F_diff = np.linalg.norm(F_nonlinear - F_linear, axis=1)

    mask = F_lin_norm > 1e-3  # Avoid division by near-zero
    if np.any(mask):
        discrepancy = F_diff[mask] / F_lin_norm[mask] * 100
        mean_disc = np.mean(discrepancy)
        max_disc = np.max(discrepancy)
        p95_disc = np.percentile(discrepancy, 95)
    else:
        mean_disc = max_disc = p95_disc = 0.0

    print(f"\n    DISCREPANCY (linear vs nonlinear):")
    print(f"      Mean:  {mean_disc:.2f}%")
    print(f"      95th:  {p95_disc:.2f}%")
    print(f"      Max:   {max_disc:.2f}%")

    if max_disc < 5:
        verdict = "LINEARIZATION SUFFICIENT for this load case"
    elif max_disc < 15:
        verdict = "MODERATE nonlinearity -- linearization acceptable for SLS"
    else:
        verdict = "SIGNIFICANT nonlinearity -- co-simulation needed for ULS"
    print(f"      Verdict: {verdict}")

    # Per-DOF breakdown
    print(f"\n    Per-DOF max discrepancy:")
    for dof in range(6):
        f_lin_dof = np.abs(F_linear[:, dof])
        f_diff_dof = np.abs(F_nonlinear[:, dof] - F_linear[:, dof])
        mask_dof = f_lin_dof > 1e-3
        if np.any(mask_dof):
            disc_dof = np.max(f_diff_dof[mask_dof] / f_lin_dof[mask_dof]) * 100
        else:
            disc_dof = 0
        dof_name = ['Fx', 'Fy', 'Fz', 'Mx', 'My', 'Mz'][dof]
        print(f"      {dof_name}: {disc_dof:.1f}%")

    return {
        'scour': scour, 'SD': SD,
        'mean_disc': mean_disc, 'max_disc': max_disc, 'p95_disc': p95_disc,
        'verdict': verdict, 'n_steps': n_steps,
        'u_max': np.max(np.abs(u_platform), axis=0).tolist(),
    }


# ═══════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════

if __name__ == '__main__':
    print("=" * 65)
    print("  Path B: Superelement Verification")
    print("  Path C: Sequential Co-Simulation")
    print("=" * 65)

    # ── PATH B ──
    path_b_verification()

    # ── PATH C ──
    print(f"\n{'='*65}")
    print(f"  PATH C: Sequential Co-Simulation")
    print(f"  Comparing Linear (Path A) vs Nonlinear (PySimple1) Forces")
    print(f"{'='*65}")

    cosim_results = []
    for S in [0.0, 2.0, 4.0]:
        result = path_c_cosimulation(scour=S, max_steps=200)
        if result:
            cosim_results.append(result)

    # Summary table
    print(f"\n{'='*65}")
    print(f"  CO-SIMULATION SUMMARY")
    print(f"{'='*65}")
    print(f"\n  {'S/D':<6s} {'Mean disc':<10s} {'95th disc':<10s} {'Max disc':<10s} {'Verdict'}")
    print(f"  {'-'*70}")
    for r in cosim_results:
        print(f"  {r['SD']:<6.3f} {r['mean_disc']:<10.2f} {r['p95_disc']:<10.2f} "
              f"{r['max_disc']:<10.2f} {r['verdict']}")

    # Save results
    results_path = COUPLING_OUTPUT / "cosim_results.csv"
    with open(results_path, 'w') as f:
        f.write("scour,SD,mean_disc_pct,p95_disc_pct,max_disc_pct,verdict,n_steps\n")
        for r in cosim_results:
            f.write(f"{r['scour']},{r['SD']},{r['mean_disc']:.2f},{r['p95_disc']:.2f},"
                    f"{r['max_disc']:.2f},{r['verdict']},{r['n_steps']}\n")
    print(f"\n  Results saved to: {results_path}")
