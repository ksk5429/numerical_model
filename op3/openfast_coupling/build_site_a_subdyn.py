"""
Build SiteA 4MW SubDyn Input File from SSOT
===============================================
Generates a text-format SubDyn v4.0.2 file for the tripod substructure
(nodes 200-235) with SSI stiffness files at base reaction joints.

The tower (nodes 100-127) is handled by ElastoDyn.
SubDyn handles only the substructure below the interface (node 100 at z=23.591m).

Substructure nodes: 200-235 (16 nodes)
Interface node: 200 at z=19.800m (connects to ElastoDyn at node 100)
  Actually, the interface is at the TP top = node 100 at z=23.591m
  But SubDyn needs the substructure to include everything below TP.
  We use node 200 (z=19.800) as the top of SubDyn, and V28 (100->200)
  is in the transition piece handled by ElastoDyn's PtfmCMzt.

  Correction: SubDyn interface = where it connects to ElastoDyn.
  In our case, node 200 at z=19.800m is the SubDyn interface joint.
  ElastoDyn TowerBsHt should be set to 19.800m.
"""
import sys
import math
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')

from config import BUCKET, STIFFNESS, COUPLING_OUTPUT

# ═══════════════════════════════════════════════════════════════════
# SSOT DATA (from SSOT_REAL_FINAL.txt)
# ═══════════════════════════════════════════════════════════════════

# Substructure nodes (below interface, handled by SubDyn)
NODES = {
    # Central column
    200: (0.000, 0.000, 19.800),   # Interface (TP top)
    201: (0.000, 0.000, 13.800),
    202: (0.000, 0.000, 11.300),
    203: (0.000, 0.000, 4.300),
    204: (0.000, 0.000, -1.700),
    205: (0.000, 0.000, -3.700),
    # Leg 1
    210: (-1.263, -0.729, -2.348),
    211: (-10.029, -5.790, -2.200),
    212: (-10.029, -5.790, -5.400),
    213: (-10.029, -5.790, -6.600),
    214: (-10.029, -5.790, -6.850),
    215: (-10.029, -5.790, -8.200),  # Base reaction 1
    # Leg 2
    220: (1.263, -0.729, -2.348),
    221: (10.029, -5.790, -2.200),
    222: (10.029, -5.790, -5.400),
    223: (10.029, -5.790, -6.600),
    224: (10.029, -5.790, -6.850),
    225: (10.029, -5.790, -8.200),   # Base reaction 2
    # Leg 3
    230: (0.000, 1.458, -2.348),
    231: (0.000, 11.580, -2.200),
    232: (0.000, 11.580, -5.400),
    233: (0.000, 11.580, -6.600),
    234: (0.000, 11.580, -6.850),
    235: (0.000, 11.580, -8.200),    # Base reaction 3
}

# Members: (node1, node2, D_top, D_bot, thickness, member_type_name)
MEMBERS = [
    # Central column (V29-V33)
    (200, 201, 4.200, 4.200, 0.0560, "Central column"),
    (201, 202, 4.200, 4.200, 0.0560, "Central column"),
    (202, 203, 4.200, 4.200, 0.0700, "Central column"),
    (203, 204, 4.200, 3.300, 0.0550, "Central column taper"),
    (204, 205, 3.300, 3.000, 0.0600, "Central column bottom"),
    # Upper leg braces (BR1): 202 -> 212/222/232
    (202, 212, 1.600, 1.600, 0.0500, "Upper leg brace"),
    (202, 222, 1.600, 1.600, 0.0500, "Upper leg brace"),
    (202, 232, 1.600, 1.600, 0.0500, "Upper leg brace"),
    # Lower diagonals (BR2): 204 -> 210/220/230
    (204, 210, 0.812, 0.812, 0.0510, "Lower diagonal"),
    (204, 220, 0.812, 0.812, 0.0510, "Lower diagonal"),
    (204, 230, 0.812, 0.812, 0.0510, "Lower diagonal"),
    # Lower leg braces (BR3): 210->213, 220->223, 230->233
    (210, 213, 0.762, 0.762, 0.0260, "Lower leg brace"),
    (220, 223, 0.762, 0.762, 0.0260, "Lower leg brace"),
    (230, 233, 0.762, 0.762, 0.0260, "Lower leg brace"),
    # Horizontal braces (BR4)
    (214, 224, 0.450, 0.450, 0.0175, "Horizontal brace"),
    (224, 234, 0.450, 0.450, 0.0175, "Horizontal brace"),
    (234, 214, 0.450, 0.450, 0.0175, "Horizontal brace"),
    # Suction bucket piles (PI1): 211->215, 221->225, 231->235
    (211, 212, 1.800, 1.800, 0.0500, "Pile leg 1"),
    (212, 213, 1.800, 1.800, 0.0500, "Pile leg 1"),
    (213, 214, 1.800, 1.800, 0.0500, "Pile leg 1"),
    (214, 215, 1.800, 1.800, 0.0500, "Pile leg 1"),
    (221, 222, 1.800, 1.800, 0.0500, "Pile leg 2"),
    (222, 223, 1.800, 1.800, 0.0500, "Pile leg 2"),
    (223, 224, 1.800, 1.800, 0.0500, "Pile leg 2"),
    (224, 225, 1.800, 1.800, 0.0500, "Pile leg 2"),
    (231, 232, 1.800, 1.800, 0.0500, "Pile leg 3"),
    (232, 233, 1.800, 1.800, 0.0500, "Pile leg 3"),
    (233, 234, 1.800, 1.800, 0.0500, "Pile leg 3"),
    (234, 235, 1.800, 1.800, 0.0500, "Pile leg 3"),
]

# Lumped masses (secondary masses from SSOT)
LUMPED_MASSES = {
    200: 59350,   # Platform + lifting + internal
    204: 6218,    # Boat landing
    211: 1773,    # J-tube leg 1
    221: 1773,    # J-tube leg 2
    231: 1773,    # J-tube leg 3
    213: 11960,   # Anodes leg 1
    223: 11960,   # Anodes leg 2
    233: 11960,   # Anodes leg 3
}

# Material
E = 2.10e11    # Pa
G = 8.10e10    # Pa
RHO = 7850.0   # kg/m3

# Base reaction nodes
REACT_NODES = [215, 225, 235]
INTERFACE_NODE = 200


def build_property_sets():
    """Group unique cross-sections into property sets."""
    seen = {}
    prop_sets = []
    member_props = []

    for n1, n2, dt, db, t, name in MEMBERS:
        # Use average diameter for property set (SubDyn uses tapered if different)
        key = (round(dt, 4), round(t, 4))
        if key not in seen:
            pid = len(prop_sets) + 1
            seen[key] = pid
            prop_sets.append((pid, E, G, RHO, dt, t))
        member_props.append(seen[key])

    return prop_sets, member_props


def write_subdyn(output_path, ssi_files=None):
    """Write SubDyn v4.0.2 input file."""
    prop_sets, member_props = build_property_sets()
    n_joints = len(NODES)
    n_members = len(MEMBERS)
    n_props = len(prop_sets)

    if ssi_files is None:
        ssi_files = ["", "", ""]  # Fixed base

    lines = []
    def w(s=""):
        lines.append(s)

    w("----------- SubDyn MultiMember Support Structure Input File ---------------------------")
    w("SiteA 4MW Reference 4 MW OWT Tripod Suction Bucket - Generated from SSOT_REAL_FINAL.txt")
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
    w('             0   GuyanDampMod - Guyan damping {0=none, 1=Rayleigh, 2=user 6x6}')
    w('  0.000, 0.000   RayleighDamp - Mass and stiffness proportional damping')
    w('             6   GuyanDampSize - Guyan damping matrix size [only if GuyanDampMod=2]')
    for _ in range(6):
        w('   0.0   0.0   0.0   0.0   0.0   0.0')

    # JOINTS
    w(f'---- STRUCTURE JOINTS --------')
    w(f'           {n_joints}   NJoints     - Number of joints (-)')
    w('JointID          JointXss               JointYss               JointZss   JointType  JointDirX   JointDirY JointDirZ  JointStiff')
    w('  (-)               (m)                    (m)                    (m)         (-)        (-)        (-)       (-)     (Nm/rad)')
    for jid in sorted(NODES.keys()):
        x, y, z = NODES[jid]
        w(f'  {jid:<6d}      {x:>14.5f}            {y:>14.5f}            {z:>14.5f}        1         0.0        0.0       0.0       0.0')

    # BASE REACTIONS
    w(f'------------------- BASE REACTION JOINTS ---------------------')
    w(f'             {len(REACT_NODES)}   NReact      - Number of Joints with reaction forces')
    w('RJointID   RctTDXss    RctTDYss    RctTDZss    RctRDXss    RctRDYss    RctRDZss     SSIfile')
    w('  (-)       (flag)      (flag)      (flag)      (flag)      (flag)      (flag)      (string)')
    for i, rn in enumerate(REACT_NODES):
        ssi = ssi_files[i] if i < len(ssi_files) and ssi_files[i] else ""
        if ssi:
            w(f'   {rn}           0           0           0           0           0           0        "{ssi}"')
        else:
            w(f'   {rn}           1           1           1           1           1           1        ""')

    # INTERFACE
    w(f'------- INTERFACE JOINTS ---------')
    w(f'             1   NInterf     - Number of interface joints')
    w('IJointID   ItfTDXss    ItfTDYss    ItfTDZss    ItfRDXss    ItfRDYss    ItfRDZss')
    w('  (-)       (flag)      (flag)      (flag)      (flag)      (flag)      (flag)')
    w(f'  {INTERFACE_NODE}           1           1           1           1           1           1')

    # MEMBERS
    w(f'----------------------------------- MEMBERS -------------------------------------------')
    w(f'           {n_members}   NMembers    - Number of members (-)')
    w('MemberID   MJointID1   MJointID2   MPropSetID1   MPropSetID2  MType   COSMID')
    w('  (-)         (-)         (-)          (-)           (-)        (-)      (-)')
    for mid, ((n1, n2, dt, db, t, name), pid) in enumerate(zip(MEMBERS, member_props), 1):
        w(f'   {mid:<4d}      {n1:<6d}      {n2:<6d}         {pid:<4d}          {pid:<4d}       1        -1')

    # CIRCULAR BEAM PROPERTIES
    w(f'------------------ CIRCULAR BEAM CROSS-SECTION PROPERTIES -----------------------------')
    w(f'            {n_props}   NPropSets   - Number of structurally unique cross-sections')
    w('PropSetID     YoungE          ShearG          MatDens          XsecD           XsecT')
    w('  (-)         (N/m2)          (N/m2)          (kg/m3)           (m)             (m)')
    for pid, e, g, rho, d, t in prop_sets:
        w(f'   {pid:<4d}    {e:.5e}     {g:.5e}       {rho:.2f}         {d:.6f}        {t:.6f}')

    # Empty sections (required by SubDyn parser -- must include header rows)
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

    # COSINE MATRICES
    w('---------------------- MEMBER COSINE MATRICES COSM(i,j) -------------------------------')
    w('             0   NCOSMs      - Number of unique cosine matrices (i.e., of unique member alignments including principal axis rotations); ignored if NXPropSets=0   or 9999 in any element below')
    w('COSMID    COSM11    COSM12    COSM13    COSM21    COSM22    COSM23    COSM31    COSM32    COSM33')
    w(' (-)       (-)       (-)       (-)       (-)       (-)       (-)       (-)       (-)       (-)')

    # CONCENTRATED MASSES
    w('------------------------ JOINT ADDITIONAL CONCENTRATED MASSES--------------------------')
    w(f'             {len(LUMPED_MASSES)}   NCmass      - Number of joints with concentrated masses')
    w('CMJointID       JMass            JMXX             JMYY             JMZZ          JMXY        JMXZ         JMYZ        MCGX      MCGY        MCGZ')
    w('  (-)            (kg)          (kg*m^2)         (kg*m^2)         (kg*m^2)      (kg*m^2)    (kg*m^2)     (kg*m^2)       (m)      (m)          (m)')
    for nid, mass in sorted(LUMPED_MASSES.items()):
        w(f'  {nid:<6d}     {mass:>12.1f}           0.0              0.0              0.0           0.0         0.0          0.0        0.0      0.0          0.0')

    # OUTPUT
    w('---------------------------- OUTPUT: SUMMARY & OUTFILE --------------------------------')
    w('True             SumPrint    - Output a Summary File (flag)')
    w('1                OutCBModes  - Output Guyan and Craig-Bampton modes {0: No output, 1: JSON output}, (flag)')
    w('1                OutFEMModes - Output first 30 FEM modes {0: No output, 1: JSON output} (flag)')
    w('False            OutCOSM     - Output cosine matrices with the selected output member forces (flag)')
    w('False            OutAll      - [T/F] Output all members\' end forces ')
    w('             2   OutSwtch    - [1/2/3] Output requested channels to: 1=<rootname>.SD.out;  2=<rootname>.out (generated by FAST);  3=both files.')
    w('True             TabDelim    - Generate a tab-delimited output in the <rootname>.SD.out file')
    w('             1   OutDec      - Decimation of output in the <rootname>.SD.out file')
    w('"ES11.4e2"       OutFmt      - Output format for numerical results in the <rootname>.SD.out file')
    w('"A11"            OutSFmt     - Output format for header strings in the <rootname>.SD.out file')
    w('------------------------- MEMBER OUTPUT LIST ------------------------------------------')
    w('             0   NMOutputs   - Number of members whose forces/displacements/velocities/accelerations will be output (-) [Must be <= 99].')
    w('MemberID   NOutCnt    NodeCnt ![NOutCnt=how many nodes to get output for [< 10]; NodeCnt are local ordinal numbers from the start of the member, and must be >=1 and <= NDiv+1] If NMOutputs=0 leave blank as well.')
    w('  (-)        (-)        (-)')
    w('------------------------- SDOutList: The next line(s) contains a list of output parameters that will be output in <rootname>.SD.out or <rootname>.out. ------')
    w('END of output channels and end of file. (the word "END" must appear in the first 3 columns of this line)')

    content = '\n'.join(lines) + '\n'
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(content)

    print(f"  Written SubDyn: {output_path}")
    print(f"    Joints: {n_joints}, Members: {n_members}, PropSets: {n_props}")
    print(f"    Interface: node {INTERFACE_NODE} at z={NODES[INTERFACE_NODE][2]}m")
    print(f"    Reactions: {REACT_NODES} at z={NODES[REACT_NODES[0]][2]}m")
    if any(ssi_files):
        print(f"    SSI files: {ssi_files}")
    else:
        print(f"    Base: FIXED (all DOFs locked)")

    return content


def build_site_a_fst(output_dir, subdyn_name, tmax=120, comp_aero=0, comp_inflow=0):
    """
    Rewrite the SiteA .fst to match OpenFAST v4.0.2 format exactly.
    The v4.0.2 binary does NOT support NRotors, CompSoil, MirrorRotor, ModCoupling
    in the feature switches -- these were added later. Use OC3 reference format.
    """
    fst_path = Path(output_dir) / "SiteA-Ref4MW.fst"
    if not fst_path.exists():
        print(f"  ERROR: {fst_path} not found")
        return False

    # Read original to get ED file name and env conditions
    orig = open(fst_path, 'r', encoding='utf-8').read()

    # Extract ED filename
    import re
    ed_match = re.search(r'"([^"]+)"\s+EDFile', orig)
    ed_name = ed_match.group(1) if ed_match else "SiteA-Ref4MW_ElastoDyn.dat"

    content = f"""------- OpenFAST EXAMPLE INPUT FILE -------------------------------------------
SiteA 4MW Reference 4 MW OWT Tripod Suction Bucket OWT (v4.0.2 compatible)
---------------------- SIMULATION CONTROL --------------------------------------
False         Echo            - Echo input data to <RootName>.ech (flag)
"FATAL"       AbortLevel      - Error level when simulation should abort (string) {{"WARNING", "SEVERE", "FATAL"}}
         {tmax}   TMax            - Total run time (s)
       0.01   DT              - Recommended module time step (s)
          2   InterpOrder     - Interpolation order for input/output time history (-) {{1=linear, 2=quadratic}}
          0   NumCrctn        - Number of correction iterations (-) {{0=explicit calculation}}
      99999   DT_UJac         - Time between calls to get Jacobians (s)
    1000000   UJacSclFact     - Scaling factor used in Jacobians (-)
---------------------- FEATURE SWITCHES AND FLAGS ------------------------------
          1   CompElast       - Compute structural dynamics (switch) {{1=ElastoDyn; 2=ElastoDyn + BeamDyn for blades; 3=Simplified ElastoDyn}}
          {comp_inflow}   CompInflow      - Compute inflow wind velocities (switch) {{0=still air; 1=InflowWind; 2=external from ExtInflow}}
          {comp_aero}   CompAero        - Compute aerodynamic loads (switch) {{0=None; 1=AeroDisk; 2=AeroDyn; 3=ExtLoads}}
          0   CompServo       - Compute control and electrical-drive dynamics (switch) {{0=None; 1=ServoDyn}}
          0   CompSeaSt       - Compute sea state information (switch) {{0=None; 1=SeaState}}
          0   CompHydro       - Compute hydrodynamic loads (switch) {{0=None; 1=HydroDyn}}
          1   CompSub         - Compute sub-structural dynamics (switch) {{0=None; 1=SubDyn; 2=External Platform MCKF}}
          0   CompMooring     - Compute mooring system (switch) {{0=None; 1=MAP++; 2=FEAMooring; 3=MoorDyn; 4=OrcaFlex}}
          0   CompIce         - Compute ice loads (switch) {{0=None; 1=IceFloe; 2=IceDyn}}
          0   MHK             - MHK turbine type (switch) {{0=Not an MHK turbine; 1=Fixed MHK turbine; 2=Floating MHK turbine}}
---------------------- ENVIRONMENTAL CONDITIONS --------------------------------
    9.80665   Gravity         - Gravitational acceleration (m/s^2)
      1.225   AirDens         - Air density (kg/m^3)
       1025   WtrDens         - Water density (kg/m^3)
  1.464E-05   KinVisc         - Kinematic viscosity of working fluid (m^2/s)
        335   SpdSound        - Speed of sound in working fluid (m/s)
     103500   Patm            - Atmospheric pressure (Pa)
       1700   Pvap            - Vapour pressure of working fluid (Pa)
         14   WtrDpth         - Water depth (m)
          0   MSL2SWL         - Offset between still-water level and mean sea level (m)
---------------------- INPUT FILES ---------------------------------------------
"{ed_name}"    EDFile          - Name of file containing ElastoDyn input parameters (quoted string)
"unused"      BDBldFile(1)    - Name of file containing BeamDyn input parameters for blade 1
"unused"      BDBldFile(2)    - Name of file containing BeamDyn input parameters for blade 2
"unused"      BDBldFile(3)    - Name of file containing BeamDyn input parameters for blade 3
"unused"      InflowFile      - Name of file containing inflow wind input parameters
"unused"      AeroFile        - Name of file containing aerodynamic input parameters
"unused"      ServoFile       - Name of file containing control and electrical-drive input parameters
"unused"      SeaStFile       - Name of file containing sea state input parameters
"unused"      HydroFile       - Name of file containing hydrodynamic input parameters
"{subdyn_name}"      SubFile         - Name of file containing sub-structural input parameters
"unused"      MooringFile     - Name of file containing mooring system input parameters
"unused"      IceFile         - Name of file containing ice input parameters
---------------------- OUTPUT --------------------------------------------------
True          SumPrint        - Print summary data to "<RootName>.sum" (flag)
         10   SttsTime        - Amount of time between screen status messages (s)
      99999   ChkptTime       - Amount of time between creating checkpoint files (s)
    Default   DT_Out          - Time step for tabular output (s) (or "default")
          0   TStart          - Time to begin tabular output (s)
          1   OutFileFmt      - Format for tabular output file (switch) {{1: text file}}
True          TabDelim        - Use tab delimiters in text tabular output file
"ES10.3E2"    OutFmt          - Format used for text tabular output
---------------------- LINEARIZATION -------------------------------------------
False         Linearize       - Linearization analysis (flag)
False         CalcSteady      - Calculate steady-state periodic operating point
          3   TrimCase        - Controller parameter to be trimmed
      0.001   TrimTol         - Tolerance for the rotational speed convergence
       0.01   TrimGain        - Proportional gain for the rotational speed error
          0   Twr_Kdmp        - Damping factor for the tower (N/(m/s))
          0   Bld_Kdmp        - Damping factor for the blades (N/(m/s))
          1   NLinTimes       - Number of times to linearize
         60   LinTimes        - Linearization times (s)
          1   LinInputs       - Inputs included in linearization
          1   LinOutputs      - Outputs included in linearization
False         LinOutJac       - Include full Jacobians in linearization output
False         LinOutMod       - Write module-level linearization output files
---------------------- VISUALIZATION ------------------------------------------
          0   WrVTK           - VTK visualization data output
          2   VTK_type        - Type of VTK visualization data
False         VTK_fields      - Write mesh fields to VTK data files
         15   VTK_fps         - Frame rate for VTK output
"""

    with open(fst_path, 'w', encoding='utf-8') as f:
        f.write(content)

    print(f"  Updated .fst: CompSub=1, SubFile={subdyn_name}, TMax={tmax}")

    # Also update ElastoDyn: TowerBsHt and PtfmRefzt must match SubDyn interface
    ed_path = Path(output_dir) / ed_name
    if ed_path.exists():
        ed_lines = open(ed_path, 'r', encoding='utf-8').readlines()
        ed_new = []
        interface_z = NODES[INTERFACE_NODE][2]  # 19.800m
        tower_top_z = 96.298  # Node 127

        for line in ed_lines:
            l = line.strip()
            if 'TowerBsHt' in l and 'tower base' in l.lower():
                ed_new.append(f'{interface_z:<22.1f} TowerBsHt   - Height of tower base above MSL (meters)\n')
            elif 'TowerHt' in l and 'height of tower' in l.lower():
                ed_new.append(f'{tower_top_z:<22.1f} TowerHt     - Height of tower above MSL (meters)\n')
            elif 'PtfmRefzt' in l and 'platform reference' in l.lower():
                ed_new.append(f'{interface_z:<22.1f} PtfmRefzt   - Vertical distance from MSL to platform reference point (meters)\n')
            elif 'PtfmCMzt' in l and 'platform cm' in l.lower():
                ed_new.append(f'{interface_z:<22.1f} PtfmCMzt    - Vertical distance from MSL to platform CM (meters)\n')
            elif 'PtfmYIner' in l and 'PtfmXY' not in l:
                # Add PtfmYIner and the missing product-of-inertia lines
                ed_new.append(line)
                ed_new.append(f'{"0.0":<22s} PtfmXYIner  - Platform xy moment of inertia about the platform CM (=-int(xydm)) (kg m^2)\n')
                ed_new.append(f'{"0.0":<22s} PtfmYZIner  - Platform yz moment of inertia about the platform CM (=-int(yzdm)) (kg m^2)\n')
                ed_new.append(f'{"0.0":<22s} PtfmXZIner  - Platform xz moment of inertia about the platform CM (=-int(xzdm)) (kg m^2)\n')
                continue
            else:
                ed_new.append(line)

        with open(ed_path, 'w', encoding='utf-8') as f:
            f.writelines(ed_new)
        print(f"  Updated ElastoDyn: TowerBsHt={interface_z}, TowerHt={tower_top_z}")

    return True


if __name__ == '__main__':
    import shutil

    print("=" * 65)
    print("  Build SiteA 4MW SubDyn from SSOT")
    print("=" * 65)

    SITE_A_DIR = Path(r"f:\TREE_OF_THOUGHT\PHD\openfast\SiteA_Ref4MW")
    RESULTS_DIR = COUPLING_OUTPUT
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    # --- Test 1: Fixed base SubDyn (verify SubDyn works) ---
    print("\n[1] Fixed base SubDyn (verification)")
    fixed_dir = RESULTS_DIR / "site_a_fixed_v4"
    if fixed_dir.exists():
        shutil.rmtree(fixed_dir)
    shutil.copytree(SITE_A_DIR, fixed_dir)

    write_subdyn(
        fixed_dir / "SiteA-Ref4MW_SubDyn.dat",
        ssi_files=["", "", ""]
    )
    build_site_a_fst(fixed_dir, "SiteA-Ref4MW_SubDyn.dat", tmax=30)

    # --- Test 2: Full 6x6 SSI (Path A) ---
    print("\n[2] Path A: Full 6x6 SSI")
    ssi_dir = RESULTS_DIR / "site_a_pathA_v4"
    if ssi_dir.exists():
        shutil.rmtree(ssi_dir)
    shutil.copytree(SITE_A_DIR, ssi_dir)

    # Copy SSI files from coupling results
    for i in range(1, 4):
        src = RESULTS_DIR / f"SSI_bucket{i}_full6x6_S0.dat"
        dst = ssi_dir / f"SSI_bucket{i}.dat"
        if src.exists():
            shutil.copy2(src, dst)
            print(f"  Copied {src.name} -> {dst.name}")

    write_subdyn(
        ssi_dir / "SiteA-Ref4MW_SubDyn.dat",
        ssi_files=["SSI_bucket1.dat", "SSI_bucket2.dat", "SSI_bucket3.dat"]
    )
    build_site_a_fst(ssi_dir, "SiteA-Ref4MW_SubDyn.dat", tmax=30)

    # --- Test 3: Diagonal-only SSI (for comparison) ---
    print("\n[3] Diagonal SSI (comparison baseline)")
    diag_dir = RESULTS_DIR / "site_a_diagonal_v4"
    if diag_dir.exists():
        shutil.rmtree(diag_dir)
    shutil.copytree(SITE_A_DIR, diag_dir)

    for i in range(1, 4):
        src = RESULTS_DIR / f"SSI_bucket{i}_diagonal_S0.dat"
        dst = diag_dir / f"SSI_bucket{i}.dat"
        if src.exists():
            shutil.copy2(src, dst)

    write_subdyn(
        diag_dir / "SiteA-Ref4MW_SubDyn.dat",
        ssi_files=["SSI_bucket1.dat", "SSI_bucket2.dat", "SSI_bucket3.dat"]
    )
    build_site_a_fst(diag_dir, "SiteA-Ref4MW_SubDyn.dat", tmax=30)

    # --- Run OpenFAST ---
    print("\n" + "=" * 65)
    print("  Running OpenFAST tests")
    print("=" * 65)

    import subprocess
    OPENFAST_EXE = Path(r"f:\TREE_OF_THOUGHT\PHD\openfast\openfast_x64.exe")

    for name, test_dir in [
        ("Fixed base", fixed_dir),
        ("Path A (full 6x6)", ssi_dir),
        ("Diagonal only", diag_dir),
    ]:
        fst = test_dir / "SiteA-Ref4MW.fst"
        print(f"\n  [{name}] Running OpenFAST...")
        try:
            result = subprocess.run(
                [str(OPENFAST_EXE), str(fst)],
                capture_output=True, text=True, timeout=600,
                cwd=str(test_dir)
            )
            if result.returncode == 0:
                # Check for output files
                out_files = list(test_dir.glob("*.out")) + list(test_dir.glob("*.outb"))
                sum_files = list(test_dir.glob("*.sum"))
                print(f"    SUCCESS")
                if sum_files:
                    print(f"    Summary: {sum_files[0].name} ({sum_files[0].stat().st_size} bytes)")
                if out_files:
                    print(f"    Output: {out_files[0].name} ({out_files[0].stat().st_size} bytes)")
            else:
                # Print last 500 chars of stderr
                err = result.stderr[-500:] if result.stderr else "No stderr"
                print(f"    FAILED (returncode={result.returncode})")
                print(f"    {err}")
        except subprocess.TimeoutExpired:
            print(f"    TIMEOUT (>600s)")
        except Exception as e:
            print(f"    ERROR: {e}")

    print(f"\n{'='*65}")
    print(f"  Test results in: {RESULTS_DIR}/")
    print(f"{'='*65}")
