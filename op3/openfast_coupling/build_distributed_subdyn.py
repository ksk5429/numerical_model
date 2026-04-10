"""
Distributed Spring SubDyn: Embed BNWF Along Bucket Skirts
==========================================================
Instead of condensing 228 springs into one 6x6 per bucket,
add intermediate joints along each bucket skirt in SubDyn
and apply per-depth SSI stiffness matrices.

Two approaches:
  A. Multi-node SSI: Add extra reaction joints along each skirt,
     each with its own 6x6 SSI file (depth-specific stiffness)
  B. Spring members (MType=5): Connect structural nodes to fixed
     ground nodes via spring elements with 21-term K vectors

Approach A is safer (uses proven SSI mechanism).
Approach B uses untested functionality.

This script implements Approach A.
"""
import sys
import math
import numpy as np
import pandas as pd
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, str(Path(__file__).parent))

from config import BUCKET, STIFFNESS, PARAMS, COUPLING_OUTPUT, SPRING_PARAMS
from build_site_a_subdyn import (
    NODES, MEMBERS, LUMPED_MASSES, REACT_NODES, INTERFACE_NODE,
    E, G, RHO, build_property_sets
)
from opensees_stiffness_extractor import SSIWriter


def compute_distributed_stiffness(scour=0.0):
    """
    Compute per-depth stiffness matrices along each bucket skirt.

    Returns: list of (z_depth, K_6x6) for active depth nodes (below scour)
    """
    sp = pd.read_csv(str(SPRING_PARAMS))
    z_nodes = sp['z_m'].values
    k_ini = sp['k_ini_kNm3'].values    # kN/m^3
    t_ult = sp['t_ult_kNm'].values      # kN/m

    D = BUCKET.D; DZ = BUCKET.DZ; L = BUCKET.L
    NUM_RIBS = BUCKET.NUM_RIBS

    depth_stiffness = []
    for j, depth in enumerate(z_nodes):
        if depth > L or depth <= scour:
            continue

        # Stress correction
        sO = depth * 10000.0
        sN = (depth - scour) * 10000.0
        if sN <= 0:
            continue
        sf = math.sqrt(sN / sO)

        # Per-bucket lateral stiffness at this depth (all 4 ribs combined)
        Kpy_total = k_ini[j] * D * DZ * 1000.0 * sf  # N/m (all ribs)

        # Per-bucket vertical stiffness at this depth
        Ktz_total = Kpy_total * 0.5

        # Rocking contribution from this depth layer
        # K_rot = Kpy * R^2 (moment arm from center)
        R = BUCKET.R
        Krot = Kpy_total * R**2  # N-m/rad

        # Build 6x6 for this depth layer (diagonal)
        K = np.zeros((6, 6))
        K[0, 0] = Kpy_total    # Ux (horizontal)
        K[1, 1] = Kpy_total    # Uy (horizontal)
        K[2, 2] = Ktz_total    # Uz (vertical)
        K[3, 3] = Krot         # Rx (rocking from lateral springs)
        K[4, 4] = Krot         # Ry
        K[5, 5] = Krot * 0.5   # Rz (torsion, less)

        depth_stiffness.append((depth, K))

    # Add base spring at skirt tip
    if L > scour:
        sO = L * 10000.0; sN = (L - scour) * 10000.0
        sf = math.sqrt(sN / sO) if sO > 0 else 0
        K_base = np.zeros((6, 6))
        K_base[0, 0] = STIFFNESS.KH * STIFFNESS.KH_base_frac * 1000 / 3 * sf
        K_base[1, 1] = K_base[0, 0]
        K_base[2, 2] = STIFFNESS.KV * STIFFNESS.KV_base_frac * 1000 / 3 * sf
        K_base[3, 3] = STIFFNESS.KM * STIFFNESS.KM_base_frac * 1000 / 3 * sf
        K_base[4, 4] = K_base[3, 3]
        K_base[5, 5] = K_base[3, 3] * 0.5
        depth_stiffness.append((L, K_base))

    return depth_stiffness


def write_distributed_subdyn(output_path, scour=0.0, ssi_dir=None):
    """
    Write SubDyn file with distributed spring nodes along bucket skirts.

    For each bucket, add intermediate joints at each active depth node
    and write separate SSI files for each.
    """
    depth_stiffness = compute_distributed_stiffness(scour)
    n_depths = len(depth_stiffness)

    if ssi_dir is None:
        ssi_dir = Path(output_path).parent

    # Extend NODES with intermediate depth joints per bucket
    ext_nodes = dict(NODES)  # Copy original
    ext_members = list(MEMBERS)  # Copy original
    spring_react_joints = []  # (joint_id, ssi_filename)

    next_nid = 5000  # Start IDs for new nodes
    next_mid = 100   # Start IDs for new members

    bucket_centers = {
        215: (-10.029, -5.790, -8.200),
        225: (10.029, -5.790, -8.200),
        235: (0.000, 11.580, -8.200),
    }

    # Pile top nodes (where bucket legs start)
    bucket_tops = {
        215: 211,  # z=-2.200
        225: 221,
        235: 231,
    }

    ssi_files = {}  # joint_id -> ssi_filename

    for bucket_idx, (ctr_id, (cx, cy, cz)) in enumerate(bucket_centers.items(), 1):
        top_z = NODES[bucket_tops[ctr_id]][2]  # z of pile top

        for d_idx, (depth, K) in enumerate(depth_stiffness):
            z = cz + (BUCKET.L - depth)  # Convert depth to elevation (below bucket lid)
            # Actually: bucket center is at cz = -8.2m (mudline)
            # Depth 0.5m below mudline = z = -8.2 - 0.5 = -8.7
            z_joint = cz - depth  # Below bucket center

            # Only add joints that are within the bucket (below mudline)
            if z_joint > cz or z_joint < cz - BUCKET.L:
                continue

            # Create new joint for this spring
            new_jid = next_nid; next_nid += 1
            ext_nodes[new_jid] = (cx, cy, z_joint)

            # SSI file for this joint
            ssi_name = f"SSI_b{bucket_idx}_d{depth:.1f}.dat"
            SSIWriter.write(
                ssi_dir / ssi_name, K,
                scour_depth=scour, bucket_id=bucket_idx,
                label=f"Bucket {bucket_idx}, depth={depth:.1f}m, distributed BNWF"
            )

            spring_react_joints.append((new_jid, ssi_name))
            ssi_files[new_jid] = ssi_name

    # Also keep original bucket centers as reaction joints (for base spring)
    for ctr_id in REACT_NODES:
        # Write SSI for the lumped remainder (if any)
        # Actually, the distributed springs replace the single 6x6
        # So we make original reaction joints fixed (or with small residual spring)
        pass

    # Now write the SubDyn file
    all_react = [(jid, fname) for jid, fname in spring_react_joints]
    # Also keep original 3 bucket nodes as fixed (structural continuity)
    for rn in REACT_NODES:
        all_react.append((rn, ""))  # Fixed base at bucket center

    prop_sets, member_props = build_property_sets()
    n_joints = len(ext_nodes)
    n_members = len(ext_members)
    n_props = len(prop_sets)

    lines = []
    def w(s=""):
        lines.append(s)

    w("----------- SubDyn MultiMember Support Structure Input File ---------------------------")
    w(f"SiteA 4MW - DISTRIBUTED BNWF - Scour={scour:.1f}m - {n_depths} spring nodes per bucket")
    w("-------------------------- SIMULATION CONTROL -----------------------------------------")
    w('False            Echo        - Echo input data to "<rootname>.SD.ech" (flag)')
    w('"DEFAULT"        SDdeltaT    - Local Integration Step.')
    w('             3   IntMethod   - Integration Method [1/2/3/4 = RK4/AB4/ABM4/AM2].')
    w('True             SttcSolve   - Solve dynamics about static equilibrium point')
    w('-------------------- FEA and CRAIG-BAMPTON PARAMETERS ---------------------------------')
    w('             3   FEMMod      - FEM switch [1=E-B; 3=Timoshenko]')
    w('             1   NDiv        - Number of sub-elements per member')
    w('            12   Nmodes      - Number of internal modes to retain')
    w('             1   JDampings   - Damping Ratios for each retained mode (%)')
    w('             0   GuyanDampMod - Guyan damping {0=none}')
    w('  0.000, 0.000   RayleighDamp - Mass and stiffness proportional damping')
    w('             6   GuyanDampSize')
    for _ in range(6):
        w('   0.0   0.0   0.0   0.0   0.0   0.0')

    # JOINTS
    w(f'---- STRUCTURE JOINTS --------')
    w(f'           {n_joints}   NJoints')
    w('JointID          JointXss               JointYss               JointZss   JointType  JointDirX   JointDirY JointDirZ  JointStiff')
    w('  (-)               (m)                    (m)                    (m)         (-)        (-)        (-)       (-)     (Nm/rad)')
    for jid in sorted(ext_nodes.keys()):
        x, y, z = ext_nodes[jid]
        w(f'  {jid:<6d}      {x:>14.5f}            {y:>14.5f}            {z:>14.5f}        1         0.0        0.0       0.0       0.0')

    # BASE REACTIONS (distributed springs + original fixed nodes)
    w(f'------------------- BASE REACTION JOINTS ---------------------')
    w(f'             {len(all_react)}   NReact')
    w('RJointID   RctTDXss    RctTDYss    RctTDZss    RctRDXss    RctRDYss    RctRDZss     SSIfile')
    w('  (-)       (flag)      (flag)      (flag)      (flag)      (flag)      (flag)      (string)')
    for jid, ssi_name in all_react:
        if ssi_name:
            w(f'   {jid}           0           0           0           0           0           0        "{ssi_name}"')
        else:
            w(f'   {jid}           1           1           1           1           1           1        ""')

    # INTERFACE
    w(f'------- INTERFACE JOINTS ---------')
    w(f'             1   NInterf')
    w('IJointID   ItfTDXss    ItfTDYss    ItfTDZss    ItfRDXss    ItfRDYss    ItfRDZss')
    w('  (-)       (flag)      (flag)      (flag)      (flag)      (flag)      (flag)')
    w(f'  {INTERFACE_NODE}           1           1           1           1           1           1')

    # MEMBERS
    w(f'----------------------------------- MEMBERS -------------------------------------------')
    w(f'           {n_members}   NMembers')
    w('MemberID   MJointID1   MJointID2   MPropSetID1   MPropSetID2  MType   COSMID')
    w('  (-)         (-)         (-)          (-)           (-)        (-)      (-)')
    for mid, ((n1, n2, dt, db, t, name), pid) in enumerate(zip(MEMBERS, member_props), 1):
        w(f'   {mid:<4d}      {n1:<6d}      {n2:<6d}         {pid:<4d}          {pid:<4d}       1        -1')

    # Property sections (same as original)
    w(f'------------------ CIRCULAR BEAM CROSS-SECTION PROPERTIES -----------------------------')
    w(f'            {n_props}   NPropSets')
    w('PropSetID     YoungE          ShearG          MatDens          XsecD           XsecT')
    w('  (-)         (N/m2)          (N/m2)          (kg/m3)           (m)             (m)')
    for pid, e, g, rho, d, t in prop_sets:
        w(f'   {pid:<4d}    {e:.5e}     {g:.5e}       {rho:.2f}         {d:.6f}        {t:.6f}')

    # Empty sections
    w('----------------- ARBITRARY BEAM CROSS-SECTION PROPERTIES -----------------------------')
    w('             0   NXPropSets  - Number of structurally unique non-circular cross-sections (if 0 the following table is ignored)')
    w('PropSetID     YoungE          ShearG          MatDens          XsecA          XsecAsx       XsecAsy       XsecJxx       XsecJyy        XsecJ0')
    w('  (-)         (N/m2)          (N/m2)          (kg/m3)          (m2)            (m2)          (m2)          (m4)          (m4)          (m4)')
    w('-------------------------- CABLE PROPERTIES -------------------------------------------')
    w('             0   NCablePropSets   - Number of cable cable properties')
    w('PropSetID     EA          MatDens        T0         CtrlChannel')
    w('  (-)         (N)         (kg/m)        (N)             (-)')
    w('----------------------- RIGID LINK PROPERTIES -----------------------------------------')
    w('             0   NRigidPropSets - Number of rigid link properties')
    w('PropSetID   MatDens   ')
    w('  (-)       (kg/m)')
    w('----------------------- SPRING ELEMENT PROPERTIES -------------------------------------')
    w('             0   NSpringPropSets - Number of spring properties')
    w('PropSetID   k11     k12     k13     k14     k15     k16     k22     k23     k24     k25     k26     k33     k34     k35     k36     k44      k45      k46      k55      k56      k66    ')
    w('  (-)      (N/m)   (N/m)   (N/m)  (N/rad) (N/rad) (N/rad)  (N/m)   (N/m)  (N/rad) (N/rad) (N/rad)  (N/m)  (N/rad) (N/rad) (N/rad) (Nm/rad) (Nm/rad) (Nm/rad) (Nm/rad) (Nm/rad) (Nm/rad)')
    w('---------------------- MEMBER COSINE MATRICES COSM(i,j) -------------------------------')
    w('             0   NCOSMs      - Number of unique cosine matrices')
    w('COSMID    COSM11    COSM12    COSM13    COSM21    COSM22    COSM23    COSM31    COSM32    COSM33')
    w(' (-)       (-)       (-)       (-)       (-)       (-)       (-)       (-)       (-)       (-)')

    # Concentrated masses
    w('------------------------ JOINT ADDITIONAL CONCENTRATED MASSES--------------------------')
    w(f'             {len(LUMPED_MASSES)}   NCmass')
    w('CMJointID       JMass            JMXX             JMYY             JMZZ          JMXY        JMXZ         JMYZ        MCGX      MCGY        MCGZ')
    w('  (-)            (kg)          (kg*m^2)         (kg*m^2)         (kg*m^2)      (kg*m^2)    (kg*m^2)     (kg*m^2)       (m)      (m)          (m)')
    for nid, mass in sorted(LUMPED_MASSES.items()):
        w(f'  {nid:<6d}     {mass:>12.1f}           0.0              0.0              0.0           0.0         0.0          0.0        0.0      0.0          0.0')

    # Output
    w('---------------------------- OUTPUT: SUMMARY & OUTFILE --------------------------------')
    w('True             SumPrint    - Output a Summary File (flag)')
    w('1                OutCBModes  - Output Guyan and Craig-Bampton modes {0: No output, 1: JSON output}, (flag)')
    w('0                OutFEMModes - Output first 30 FEM modes {0: No output, 1: JSON output} (flag)')
    w('False            OutCOSM     - Output cosine matrices')
    w("False            OutAll      - [T/F] Output all members' end forces ")
    w('             2   OutSwtch    - [1/2/3] Output to: 1=.SD.out; 2=.out; 3=both')
    w('True             TabDelim    - Tab-delimited output')
    w('             1   OutDec      - Decimation of output')
    w('"ES11.4e2"       OutFmt      - Output format')
    w('"A11"            OutSFmt     - Header format')
    w('------------------------- MEMBER OUTPUT LIST ------------------------------------------')
    w('             0   NMOutputs')
    w('MemberID   NOutCnt    NodeCnt')
    w('  (-)        (-)        (-)')
    w('------------------------- SDOutList: The next line(s) contains a list of output parameters ------')
    w('END of output channels and end of file. (the word "END" must appear in the first 3 columns of this line)')

    content = '\n'.join(lines) + '\n'
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(content)

    print(f"  Written DISTRIBUTED SubDyn: {output_path}")
    print(f"    Original joints: {len(NODES)}, Added spring joints: {len(ext_nodes) - len(NODES)}")
    print(f"    Total joints: {n_joints}, Members: {n_members}")
    print(f"    Spring reaction joints: {len(spring_react_joints)} ({n_depths} depths x 3 buckets)")
    print(f"    SSI files written: {len(spring_react_joints)}")

    return len(spring_react_joints)


if __name__ == '__main__':
    import shutil, subprocess

    print("=" * 65)
    print("  Distributed BNWF in SubDyn")
    print("=" * 65)

    TEMPLATE = COUPLING_OUTPUT / "site_a_pathA_final"
    DIST_DIR = COUPLING_OUTPUT / "site_a_distributed"

    if DIST_DIR.exists():
        try: shutil.rmtree(DIST_DIR)
        except OSError: pass  # cleanup failure, will be overwritten

    if not DIST_DIR.exists():
        shutil.copytree(TEMPLATE, DIST_DIR)

    # Copy v4 ElastoDyn
    src_ed = Path("f:/TREE_OF_THOUGHT/PHD/openfast/SiteA_Ref4MW/SiteA-Ref4MW_ElastoDyn_v4.dat")
    if src_ed.exists():
        shutil.copy2(src_ed, DIST_DIR / "SiteA-Ref4MW_ElastoDyn.dat")

    # Generate distributed SubDyn
    n_springs = write_distributed_subdyn(
        DIST_DIR / "SiteA-Ref4MW_SubDyn.dat",
        scour=0.0,
        ssi_dir=DIST_DIR
    )

    # Write .fst
    fst_src = TEMPLATE / "SiteA-Ref4MW.fst"
    if fst_src.exists():
        shutil.copy2(fst_src, DIST_DIR / "SiteA-Ref4MW.fst")

    # Run OpenFAST
    print(f"\n  Running OpenFAST with distributed BNWF ({n_springs} springs)...")
    OPENFAST = Path(r"f:\TREE_OF_THOUGHT\PHD\openfast\openfast_x64.exe")
    fst = DIST_DIR / "SiteA-Ref4MW.fst"

    result = subprocess.run(
        [str(OPENFAST), str(fst)],
        capture_output=True, text=True, timeout=600,
        cwd=str(DIST_DIR)
    )

    out_files = list(DIST_DIR.glob("*.out"))
    json_files = list(DIST_DIR.glob("*.json"))

    if out_files:
        print(f"    SUCCESS: {out_files[0].name} ({out_files[0].stat().st_size/1e6:.1f} MB)")
    else:
        err = result.stdout[-500:] + result.stderr[-500:]
        print(f"    FAILED")
        # Show relevant error
        for line in (result.stdout + result.stderr).split('\n'):
            if 'error' in line.lower() or 'invalid' in line.lower() or 'abort' in line.lower():
                print(f"    {line.strip()}")
