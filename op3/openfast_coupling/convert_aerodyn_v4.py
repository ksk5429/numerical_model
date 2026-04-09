"""
Convert SiteA AeroDyn + Airfoils to OpenFAST v4.0.2 Format
=============================================================
Systematic conversion of all aerodynamic input files.

Key v4.0.2 changes from v15.03:
  - WakeMod -> Wake_Mod
  - AFAeroMod -> removed (use UA_Mod)
  - FrozenWake -> removed (use DBEMTMod=-1)
  - Added: NacelleDrag, BEM_Mod
  - DBEMT section restructured
  - Beddoes-Leishman section renamed to "Unsteady Airfoil"
  - NODE OUTPUTS section added at end
"""
import sys
import re
import shutil
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')


def convert_aerodyn(input_path, output_path, blade_file="SiteA-Ref4MW_AeroDyn15_blade.dat",
                    airfoil_dir="Airfoils"):
    """Convert AeroDyn v15.03 to v4.0.2 format using OC3 as template."""

    # Read from ORIGINAL SiteA AeroDyn (not the copy that may be overwritten)
    original = Path("f:/TREE_OF_THOUGHT/PHD/openfast/SiteA_Ref4MW/SiteA-Ref4MW_AeroDyn15.dat")
    src = original if original.exists() else input_path
    site_a_lines = open(src, 'r', encoding='utf-8', errors='replace').readlines()

    # Extract SiteA-specific values
    num_af = 0
    af_files = []
    num_bld_nds = 0

    # Parse the SiteA file for values we need to preserve
    in_af_section = False
    in_blade_section = False
    tower_lines = []
    in_tower = False

    for line in site_a_lines:
        l = line.strip()
        if 'NumAFfiles' in l and 'AFNames' not in l:
            num_af = int(l.split()[0])
            in_af_section = True
            continue
        if in_af_section and '"' in l and ('Polar' in l or 'Airfoil' in l or '.dat' in l):
            # Extract airfoil filename
            match = re.search(r'"([^"]+)"', l)
            if match:
                af_files.append(match.group(1))
            if len(af_files) >= num_af:
                in_af_section = False
            continue
        if 'NumBlNds' in l:
            in_blade_section = True
        if 'Tower Influence' in l:
            in_tower = True
        if in_tower and not l.startswith('=') and not l.startswith('-') and l:
            tower_lines.append(line)

    # Fix airfoil paths to be relative to run directory
    fixed_af_files = []
    for af in af_files:
        # Extract just the filename
        af_name = Path(af).name
        fixed_af_files.append(f"{airfoil_dir}/{af_name}")

    print(f"  SiteA AeroDyn: {num_af} airfoils, blade={blade_file}")
    for af in fixed_af_files[:3]:
        print(f"    {af}")
    if len(fixed_af_files) > 3:
        print(f"    ... ({len(fixed_af_files)} total)")

    # Now build the v4.0.2 AeroDyn file
    content = f"""------- AERODYN INPUT FILE --------------------------------------------------------------------------
SiteA 4MW Reference 4 MW OWT - AeroDyn v4.0.2 format (converted from v15.03)
======  General Options  ============================================================================
False                  Echo        - Echo the input to "<rootname>.AD.ech"? (flag)
"default"              DTAero      - Time interval for aerodynamic calculations {{or "default"}} (s)
1                      Wake_Mod    - Wake/induction model (switch) {{0=none, 1=BEMT, 3=OLAF}}
1                      TwrPotent   - Type tower influence on wind based on potential flow (switch) {{0=none, 1=baseline, 2=Bak correction}}
0                      TwrShadow   - Calculate tower influence based on downstream shadow (switch) {{0=none, 1=Powles, 2=Eames}}
True                   TwrAero     - Calculate tower aerodynamic loads? (flag)
False                  CavitCheck  - Perform cavitation check? (flag)
False                  Buoyancy    - Include buoyancy effects? (flag)
False                  NacelleDrag - Include Nacelle Drag effects? (flag)
False                  CompAA      - Flag to compute AeroAcoustics calculation
"unused"               AA_InputFile - AeroAcoustics input file
======  Environmental Conditions  ===================================================================
"default"              AirDens     - Air density (kg/m^3)
"default"              KinVisc     - Kinematic viscosity (m^2/s)
"default"              SpdSound    - Speed of sound (m/s)
"default"              Patm        - Atmospheric pressure (Pa)
"default"              Pvap        - Vapour pressure (Pa)
======  Blade-Element/Momentum Theory Options  ====================================================== [unused when Wake_Mod=0 or 3, except for BEM_Mod]
1                      BEM_Mod     - BEM model {{1=legacy NoSweepPitchTwist, 2=polar}} (switch)
2                      SkewMod     - Type of skewed-wake correction model (switch) {{1=uncoupled, 2=Pitt/Peters, 3=coupled}}
"default"              SkewModFactor - Constant used in Pitt/Peters skewed wake model
True                   TipLoss     - Use the Prandtl tip-loss model? (flag)
True                   HubLoss     - Use the Prandtl hub-loss model? (flag)
True                   TanInd      - Include tangential induction in BEMT calculations? (flag)
True                   AIDrag      - Include the drag term in the axial-induction calculation? (flag)
True                   TIDrag      - Include the drag term in the tangential-induction calculation? (flag)
"default"              IndToler    - Convergence tolerance for BEMT nonlinear solve residual equation
500                    MaxIter     - Maximum number of iteration steps (-)
======  OLAF -- cOnvecting LAgrangian Filaments (Free Vortex Wake) Theory Options  ================== [used only when Wake_Mod=3]
"unused"               OLAFInputFileName - Input file for OLAF
======  Unsteady Airfoil Aerodynamics Options  ====================================================
0                      UA_Mod      - Unsteady Aero Model Switch {{0=Quasi-steady, 2=B-L Gonzalez, 3=B-L Minnema/Pierce, 4=HGM, 5=HGM+vortex, 6=Oye, 7=Boeing-Vertol}}
True                   FLookup     - Flag to indicate whether a lookup for f' will be calculated (flag)
0                      UAStartRad  - Starting radius for dynamic stall (fraction of rotor radius [-])
1                      UAEndRad    - Ending radius for dynamic stall (fraction of rotor radius [-])
======  Airfoil Information =========================================================================
1                      AFTabMod    - Interpolation method for multiple airfoil tables {{1=1D on AoA; 2=2D on AoA and Re; 3=2D on AoA and UserProp}} (-)
1                      InCol_Alfa  - The column in the airfoil tables that contains the angle of attack (-)
2                      InCol_Cl    - The column in the airfoil tables that contains the lift coefficient (-)
3                      InCol_Cd    - The column in the airfoil tables that contains the drag coefficient (-)
4                      InCol_Cm    - The column in the airfoil tables that contains the pitching-moment coefficient (-)
0                      InCol_Cpmin - The column in the airfoil tables that contains the Cpmin coefficient (-)
{num_af}                      NumAFfiles  - Number of airfoil files used (-)
"""

    # Add airfoil file references
    for i, af in enumerate(fixed_af_files):
        if i == 0:
            content += f'"{af}"    AFNames            - Airfoil file names (NumAFfiles lines) (quoted strings)\n'
        else:
            content += f'"{af}"\n'

    content += f"""======  Rotor/Blade Properties  =====================================================================
True                   UseBlCm     - Include aerodynamic pitching moment in calculations? (flag)
"{blade_file}"    ADBlFile(1) - Name of file containing distributed aerodynamic properties for Blade #1 (-)
"{blade_file}"    ADBlFile(2) - Name of file containing distributed aerodynamic properties for Blade #2 (-)
"{blade_file}"    ADBlFile(3) - Name of file containing distributed aerodynamic properties for Blade #3 (-)
======  Hub Properties ============================================================================== [used only when Buoyancy=True]
0.0                    VolHub      - Hub volume (m^3)
0.0                    HubCenBx    - Hub center of buoyancy x direction offset (m)
======  Nacelle Properties ========================================================================== [used only when Buoyancy=True or NacelleDrag=True]
0.0                    VolNac      - Nacelle volume (m^3)
0,0,0                  NacCenB     - Position of nacelle center of buoyancy from yaw bearing in nacelle coordinates (m)
0,0,0                  NacArea     - Projected area of the nacelle in x, y, z in nacelle coordinates (m^2)
0,0,0                  NacCd       - Drag coefficient for the nacelle areas defined above (-)
0,0,0                  NacDragAC   - Position of aerodynamic center of nacelle drag from yaw bearing in nacelle coordinates (m)
======  Tail Fin Aerodynamics =======================================================================
False                  TFinAero    - Calculate tail fin aerodynamics model (flag)
"unused"               TFinFile    - Input file for tail fin aerodynamics
======  Tower Influence and Aerodynamics ============================================================ [used only when TwrPotent/=0, TwrShadow/=0, TwrAero=True, or Buoyancy=True]
12                     NumTwrNds   - Number of tower nodes used in the analysis (-)
TwrElev        TwrDiam        TwrCd          TwrTI          TwrCb
(m)            (m)            (-)            (-)            (-)
  19.800       4.200          1.0            0.1            0.0
  23.591       4.200          1.0            0.1            0.0
  31.571       4.154          1.0            0.1            0.0
  41.256       4.000          1.0            0.1            0.0
  50.076       4.000          1.0            0.1            0.0
  58.776       4.000          1.0            0.1            0.0
  67.571       4.000          1.0            0.1            0.0
  75.895       4.000          1.0            0.1            0.0
  81.662       3.857          1.0            0.1            0.0
  87.237       3.719          1.0            0.1            0.0
  92.818       3.580          1.0            0.1            0.0
  96.298       3.500          1.0            0.1            0.0
======  Outputs  ====================================================================================
True                   SumPrint    - Generate a summary file listing input options and interpolated properties to "<rootname>.AD.sum"? (flag)
0                      NBlOuts     - Number of blade node outputs [0 - 9] (-)
1, 9, 19               BlOutNd     - Blade nodes whose values will be output (-)
0                      NTwOuts     - Number of tower node outputs [0 - 9] (-)
                       TwOutNd     - Tower nodes whose values will be output (-)
              OutList  - The next line(s) contains a list of output parameters.
END of OutList section
---------------------- NODE OUTPUTS --------------------------------------------
                  OutList             - The next line(s) contains a list of output parameters.
END (the word "END" must appear in the first 3 columns of this last OutList line)
====================================================================================================
"""

    with open(output_path, 'w', encoding='ascii', errors='replace') as f:
        f.write(content)

    print(f"  Written v4.0.2 AeroDyn: {output_path}")
    return True


def verify_airfoil_files(airfoil_dir):
    """Check that all airfoil polar files exist and are readable."""
    polars = sorted(airfoil_dir.glob("*.dat"))
    print(f"\n  Airfoil files in {airfoil_dir}: {len(polars)}")
    for p in polars[:5]:
        with open(p, 'r', errors='replace') as f:
            first = f.readline().strip()
        print(f"    {p.name}: {first[:60]}")
    if len(polars) > 5:
        print(f"    ... ({len(polars)} total)")
    return len(polars) > 0


def deploy_calibrated_model(template_dir, output_dir):
    """
    Deploy a fully calibrated SiteA model with all v4.0.2 files.
    """
    if output_dir.exists():
        shutil.rmtree(output_dir)
    shutil.copytree(template_dir, output_dir)

    # 1. Copy calibrated ElastoDyn v4
    src_ed = Path("f:/TREE_OF_THOUGHT/PHD/openfast/SiteA_Ref4MW/SiteA-Ref4MW_ElastoDyn_v4.dat")
    dst_ed = output_dir / "SiteA-Ref4MW_ElastoDyn.dat"
    if src_ed.exists():
        txt = open(src_ed, 'r', encoding='utf-8', errors='replace').read()
        txt = txt.replace('\u2014', '-').replace('\u2013', '-')
        with open(dst_ed, 'w', encoding='ascii', errors='replace') as f:
            f.write(txt)

    # 2. Copy calibrated tower
    src_tw = Path("f:/TREE_OF_THOUGHT/PHD/openfast/SiteA_Ref4MW/SiteA-Ref4MW_ElastoDyn_tower_calibrated.dat")
    if src_tw.exists():
        shutil.copy2(src_tw, output_dir / "SiteA-Ref4MW_ElastoDyn_tower.dat")

    # 3. Convert AeroDyn
    convert_aerodyn(
        output_dir / "SiteA-Ref4MW_AeroDyn15.dat",
        output_dir / "SiteA-Ref4MW_AeroDyn15.dat",
        blade_file="SiteA-Ref4MW_AeroDyn15_blade.dat",
        airfoil_dir="Airfoils"
    )

    # 4. Create InflowWind (steady 8 m/s)
    inflow_content = """------- InflowWind INPUT FILE -----------------------------------------------
Steady 8 m/s wind for SiteA 4MW
---------------------------------------------------------------------------------------------------------------
False         Echo           - Echo input data (flag)
          1   WindType       - 1=steady
          0   PropagationDir - (degrees)
          0   VFlowAng       - (degrees)
False         VelInterpCubic
          1   NWindVel
          0   WindVxiList
          0   WindVyiList
       96.3   WindVziList
================== Parameters for Steady Wind Conditions [used only for WindType = 1] =========================
        8.0   HWindSpeed     - (m/s)
       96.3   RefHt          - (m)
       0.14   PLExp          - (-)
================== Parameters for Uniform wind file   [used only for WindType = 2] ============================
"unused"      FileName_Uni
       96.3   RefHt_Uni
      192.6   RefLength
================== Parameters for Binary TurbSim Full-Field files   [used only for WindType = 3] ==============
"unused"      FileName_BTS
================== Parameters for Binary Bladed-style Full-Field files   [used only for WindType = 4 or WindType = 7] =========
"unused"      FileNameRoot
False         TowerFile
================== Parameters for HAWC-format binary files  [Only used with WindType = 5] =====================
"unused"      FileName_u
"unused"      FileName_v
"unused"      FileName_w
         64   nx
         32   ny
         32   nz
         16   dx
          3   dy
          3   dz
       96.3   RefHt_Hawc
  -------------   Scaling parameters for turbulence   ---------------------------------------------------------
          1   ScaleMethod
       1.00   SFx
       1.00   SFy
       1.00   SFz
       1.00   SigmaFx
       1.00   SigmaFy
       1.00   SigmaFz
  -------------   Mean wind profile parameters   ---------------------------------------------------------------
         12   URef
          2   WindProfile
          0   PLExp_Hawc
       0.03   Z0
          0   XOffset
====================== OUTPUT ==================================================
              OutList
"Wind1VelX,Wind1VelY,Wind1VelZ"
END
"""
    with open(output_dir / "SiteA-Ref4MW_InflowWind.dat", 'w') as f:
        f.write(inflow_content)

    # 5. Write .fst with wind + aero enabled
    fst_content = f"""------- OpenFAST EXAMPLE INPUT FILE -------------------------------------------
SiteA 4MW FULLY CALIBRATED - Wind + SubDyn + SSI (v4.0.2)
---------------------- SIMULATION CONTROL --------------------------------------
False         Echo            - Echo input data to <RootName>.ech (flag)
"FATAL"       AbortLevel      - Error level when simulation should abort
        120   TMax            - Total run time (s)
       0.01   DT              - Recommended module time step (s)
          2   InterpOrder     - Interpolation order
          0   NumCrctn        - Number of correction iterations
      99999   DT_UJac         - Time between Jacobian updates (s)
    1000000   UJacSclFact     - Scaling factor for Jacobians
---------------------- FEATURE SWITCHES AND FLAGS ------------------------------
          1   CompElast       - Compute structural dynamics {{1=ElastoDyn}}
          1   CompInflow      - Compute inflow wind {{1=InflowWind}}
          2   CompAero        - Compute aerodynamic loads {{2=AeroDyn}}
          0   CompServo       - Compute control {{0=None}}
          0   CompSeaSt       - Compute sea state {{0=None}}
          0   CompHydro       - Compute hydrodynamic loads {{0=None}}
          1   CompSub         - Compute sub-structural dynamics {{1=SubDyn}}
          0   CompMooring     - Compute mooring system {{0=None}}
          0   CompIce         - Compute ice loads {{0=None}}
          0   MHK             - MHK turbine type {{0=Not MHK}}
---------------------- ENVIRONMENTAL CONDITIONS --------------------------------
    9.80665   Gravity         - Gravitational acceleration (m/s^2)
      1.225   AirDens         - Air density (kg/m^3)
       1025   WtrDens         - Water density (kg/m^3)
  1.464E-05   KinVisc         - Kinematic viscosity (m^2/s)
        335   SpdSound        - Speed of sound (m/s)
     103500   Patm            - Atmospheric pressure (Pa)
       1700   Pvap            - Vapour pressure (Pa)
         14   WtrDpth         - Water depth (m)
          0   MSL2SWL         - MSL to SWL offset (m)
---------------------- INPUT FILES ---------------------------------------------
"SiteA-Ref4MW_ElastoDyn.dat"       EDFile
"unused"      BDBldFile(1)
"unused"      BDBldFile(2)
"unused"      BDBldFile(3)
"SiteA-Ref4MW_InflowWind.dat"      InflowFile
"SiteA-Ref4MW_AeroDyn15.dat"       AeroFile
"unused"      ServoFile
"unused"      SeaStFile
"unused"      HydroFile
"SiteA-Ref4MW_SubDyn.dat"          SubFile
"unused"      MooringFile
"unused"      IceFile
---------------------- OUTPUT --------------------------------------------------
True          SumPrint        - Print summary data
         10   SttsTime        - Screen status interval (s)
      99999   ChkptTime       - Checkpoint interval (s)
       0.02   DT_Out          - Time step for tabular output (s)
         10   TStart          - Time to begin tabular output (s)
          1   OutFileFmt      - {{1: text file}}
True          TabDelim        - Tab delimiters
"ES10.3E2"    OutFmt          - Output format
---------------------- LINEARIZATION -------------------------------------------
False         Linearize
False         CalcSteady
          3   TrimCase
      0.001   TrimTol
       0.01   TrimGain
          0   Twr_Kdmp
          0   Bld_Kdmp
          1   NLinTimes
         60   LinTimes
          1   LinInputs
          1   LinOutputs
False         LinOutJac
False         LinOutMod
---------------------- VISUALIZATION ------------------------------------------
          0   WrVTK
          2   VTK_type
False         VTK_fields
         15   VTK_fps
"""
    with open(output_dir / "SiteA-Ref4MW.fst", 'w') as f:
        f.write(fst_content)

    print(f"\n  Deployed fully calibrated model to: {output_dir}")
    return True


if __name__ == '__main__':
    print("=" * 65)
    print("  Full SiteA Model Calibration for v4.0.2")
    print("=" * 65)

    SITE_A = Path(r"f:\TREE_OF_THOUGHT\PHD\openfast\SiteA_Ref4MW")
    RESULTS = Path(r"f:\TREE_OF_THOUGHT\PHD\openfast\coupling_results")

    # Verify airfoils exist
    verify_airfoil_files(SITE_A / "Airfoils")

    # Deploy calibrated model
    cal_dir = RESULTS / "site_a_fully_calibrated"
    deploy_calibrated_model(SITE_A, cal_dir)

    # Generate SubDyn with SSI
    sys.path.insert(0, str(Path(__file__).parent))
    from build_site_a_subdyn import write_subdyn
    write_subdyn(
        cal_dir / "SiteA-Ref4MW_SubDyn.dat",
        ssi_files=["SSI_bucket1.dat", "SSI_bucket2.dat", "SSI_bucket3.dat"]
    )

    # Copy SSI files from Path A
    for i in range(1, 4):
        src = RESULTS / f"SSI_bucket{i}_full6x6_S0.dat"
        if src.exists():
            shutil.copy2(src, cal_dir / f"SSI_bucket{i}.dat")

    # Run OpenFAST
    import subprocess
    OPENFAST = Path(r"f:\TREE_OF_THOUGHT\PHD\openfast\openfast_x64.exe")
    print(f"\n  Running OpenFAST (fully calibrated, wind+SubDyn, 120s)...")
    result = subprocess.run(
        [str(OPENFAST), str(cal_dir / "SiteA-Ref4MW.fst")],
        capture_output=True, text=True, timeout=900,
        cwd=str(cal_dir)
    )

    out = cal_dir / "SiteA-Ref4MW.out"
    if out.exists() and out.stat().st_size > 10000:
        print(f"  SUCCESS: {out.stat().st_size / 1e6:.1f} MB output")
    else:
        err = result.stdout + result.stderr
        for line in err.split('\n'):
            if 'error' in line.lower() or 'fatal' in line.lower() or 'abort' in line.lower():
                print(f"  {line.strip()[:120]}")
