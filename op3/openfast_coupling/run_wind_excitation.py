"""
Wind Excitation Investigation for Natural Frequency Extraction
===============================================================
Three excitation methods:
  1. Impulse: initial tower-top displacement (no wind)
  2. Steady wind: constant wind speed (aerodynamic thrust)
  3. Step release: initial displacement + gravity (free decay)

For each, run OpenFAST at S=0 and S=2m, extract f1 via FFT,
and compare with OpenSeesPy eigenvalue.
"""
import sys
import shutil
import subprocess
import numpy as np
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')

OPENFAST = Path(r"f:\TREE_OF_THOUGHT\PHD\openfast\openfast_x64.exe")
TEMPLATE = Path(r"f:\TREE_OF_THOUGHT\PHD\openfast\coupling_results\site_a_pathA_final")
RESULTS = Path(r"f:\TREE_OF_THOUGHT\PHD\openfast\coupling_results\wind_test")
RESULTS.mkdir(parents=True, exist_ok=True)

# OpenSeesPy reference
OS_F1 = {0.0: 0.2367, 2.0: 0.2231}


def read_text_output(filepath):
    """Read OpenFAST .out text file."""
    with open(filepath, 'r', errors='replace') as f:
        lines = f.readlines()
    for i, line in enumerate(lines):
        if line.strip().startswith('Time'):
            names = line.split()
            data = []
            for dl in lines[i+2:]:
                try:
                    vals = [float(x) for x in dl.split()]
                    if len(vals) == len(names):
                        data.append(vals)
                except ValueError:
                    continue  # skip non-numeric lines
            return names, np.array(data)
    return None, None


def estimate_f1(time, signal, dt, f_range=(0.1, 0.8)):
    """Extract f1 from time history via FFT with zero-crossing check."""
    # Skip initial transient
    t_skip = 5.0
    mask = time > t_skip
    if np.sum(mask) < 200:
        mask = time > 1.0
    sig = signal[mask] - np.mean(signal[mask])
    t = time[mask]

    if len(sig) < 100 or np.std(sig) < 1e-12:
        return 0.0, 0.0

    # Hanning window + FFT
    n = len(sig)
    nfft = max(n, 8192)
    freqs = np.fft.rfftfreq(nfft, d=dt)
    fft_mag = np.abs(np.fft.rfft(sig * np.hanning(n), n=nfft))

    # Peak in target range
    band = (freqs >= f_range[0]) & (freqs <= f_range[1])
    if not np.any(band):
        return 0.0, 0.0

    fft_band = fft_mag[band]
    freq_band = freqs[band]
    peak_idx = np.argmax(fft_band)

    return freq_band[peak_idx], fft_band[peak_idx]


def create_steady_wind_inflow(filepath, wind_speed=8.0, ref_height=96.3):
    """Create a simple steady wind InflowWind file (WindType=1)."""
    content = f"""------- InflowWind INPUT FILE -----------------------------------------------
Steady {wind_speed:.1f} m/s wind for structural excitation
---------------------------------------------------------------------------------------------------------------
False         Echo           - Echo input data to <RootName>.ech (flag)
          1   WindType       - switch for wind file type (1=steady)
          0   PropagationDir - Direction of wind propagation (degrees)
          0   VFlowAng       - Upflow angle (degrees)
False         VelInterpCubic - Use cubic interpolation for velocity in time
          1   NWindVel       - Number of points to output the wind velocity (0 to 9)
          0   WindVxiList    - List of coordinates in the inertial X direction (m)
          0   WindVyiList    - List of coordinates in the inertial Y direction (m)
        {ref_height:.1f}   WindVziList    - List of coordinates in the inertial Z direction (m)
================== Parameters for Steady Wind Conditions [used only for WindType = 1] =========================
       {wind_speed:.1f}   HWindSpeed     - Horizontal wind speed (m/s)
        {ref_height:.1f}   RefHt          - Reference height for horizontal wind speed (m)
        0.14   PLExp          - Power law exponent (-)
================== Parameters for Uniform wind file   [used only for WindType = 2] ============================
"unused"      FileName_Uni   - Filename of time series data for uniform wind field
        {ref_height:.1f}   RefHt_Uni      - Reference height for horizontal wind speed (m)
     {2*ref_height:.2f}   RefLength      - Reference length for linear horizontal and vertical sheer (-)
================== Parameters for Binary TurbSim Full-Field files   [used only for WindType = 3] ==============
"unused"      FileName_BTS   - Name of the Full field wind file to use (.bts)
================== Parameters for Binary Bladed-style Full-Field files   [used only for WindType = 4 or WindType = 7] =========
"unused"      FileNameRoot   - WindType=4: Rootname of the full-field wind file to use
False         TowerFile      - Have tower file (.twr) (flag)
================== Parameters for HAWC-format binary files  [Only used with WindType = 5] =====================
"unused"      FileName_u     - name of the file containing the u-component fluctuating wind (.bin)
"unused"      FileName_v     - name of the file containing the v-component fluctuating wind (.bin)
"unused"      FileName_w     - name of the file containing the w-component fluctuating wind (.bin)
         64   nx             - number of grids in the x direction (in the 3 files above) (-)
         32   ny             - number of grids in the y direction (in the 3 files above) (-)
         32   nz             - number of grids in the z direction (in the 3 files above) (-)
         16   dx             - distance (in meters) between two consecutive grids in the x direction (m)
          3   dy             - distance (in meters) between two consecutive grids in the y direction (m)
          3   dz             - distance (in meters) between two consecutive grids in the z direction (m)
        {ref_height:.1f}   RefHt_Hawc     - reference height; the height of the horizontal-wind center of the grid (m)
  -------------   Scaling parameters for turbulence   ---------------------------------------------------------
          1   ScaleMethod    - Turbulence scaling method [0 = none, 1 = direct scaling, 2 = calculate scaling factor based on a desired standard deviation]
       1.00   SFx            - Turbulence scaling factor for the x direction (-) [ScaleMethod=1]
       1.00   SFy            - Turbulence scaling factor for the y direction (-) [ScaleMethod=1]
       1.00   SFz            - Turbulence scaling factor for the z direction (-) [ScaleMethod=1]
       1.00   SigmaFx        - Turbulence standard deviation to calculate scaling from in x direction (m/s) [ScaleMethod=2]
       1.00   SigmaFy        - Turbulence standard deviation to calculate scaling from in y direction (m/s) [ScaleMethod=2]
       1.00   SigmaFz        - Turbulence standard deviation to calculate scaling from in z direction (m/s) [ScaleMethod=2]
  -------------   Mean wind profile parameters (added to road 'offset' winds)   --------------------------------
         12   URef           - Mean u-component wind speed at the reference height (m/s)
          2   WindProfile    - Wind profile type (0=constant, 1=logarithmic, 2=power law)
          0   PLExp_Hawc     - Power law exponent (-) (used for PL wind profile type only)
       0.03   Z0             - Surface roughness length (m) (used for LOG wind profile type only)
          0   XOffset        - Initial offset in +x direction (shift of wind box) (m)
====================== OUTPUT ==================================================
              OutList      - The next line(s) contains a list of output parameters
"Wind1VelX,Wind1VelY,Wind1VelZ"
END
"""
    with open(filepath, 'w') as f:
        f.write(content)


def setup_excitation_test(name, scour, excitation_type='impulse', wind_speed=8.0):
    """
    Create test directory with specified excitation.

    excitation_type:
      'impulse'  - Initial TTDspFA=0.5m, no wind, no aero
      'steady'   - Steady wind at wind_speed, aero enabled
      'combined' - Impulse + steady wind
    """
    test_dir = RESULTS / f"{name}_S{scour:.0f}"
    if test_dir.exists():
        try:
            shutil.rmtree(test_dir)
        except OSError:
            import time as tm
            test_dir = RESULTS / f"{name}_S{scour:.0f}_{int(tm.time())%10000}"

    shutil.copytree(TEMPLATE, test_dir)

    # Copy v4 ElastoDyn
    src_ed = Path("f:/TREE_OF_THOUGHT/PHD/openfast/SiteA_Ref4MW/SiteA-Ref4MW_ElastoDyn_v4.dat")
    if src_ed.exists():
        shutil.copy2(src_ed, test_dir / "SiteA-Ref4MW_ElastoDyn.dat")

    # Copy SSI files for this scour level
    SD = scour / 8.0
    sweep_dir = Path(f"f:/TREE_OF_THOUGHT/PHD/openfast/coupling_results/scour_sweep/S{scour:.1f}m_SD{SD:.3f}")
    if sweep_dir.exists():
        for ssi in sweep_dir.glob("SSI_bucket*.dat"):
            shutil.copy2(ssi, test_dir / ssi.name)

    # --- Write .fst ---
    comp_inflow = 1 if excitation_type in ['steady', 'combined'] else 0
    comp_aero = 2 if excitation_type in ['steady', 'combined'] else 0

    fst_content = f"""------- OpenFAST EXAMPLE INPUT FILE -------------------------------------------
SiteA 4MW - {excitation_type} excitation - S={scour:.1f}m
---------------------- SIMULATION CONTROL --------------------------------------
False         Echo            - Echo input data to <RootName>.ech (flag)
"FATAL"       AbortLevel      - Error level when simulation should abort
        120   TMax            - Total run time (s)
       0.01   DT              - Recommended module time step (s)
          2   InterpOrder     - Interpolation order
          0   NumCrctn        - Number of correction iterations
      99999   DT_UJac         - Time between calls to get Jacobians (s)
    1000000   UJacSclFact     - Scaling factor used in Jacobians
---------------------- FEATURE SWITCHES AND FLAGS ------------------------------
          1   CompElast       - Compute structural dynamics {{1=ElastoDyn}}
          {comp_inflow}   CompInflow      - Compute inflow wind velocities {{0=still air; 1=InflowWind}}
          {comp_aero}   CompAero        - Compute aerodynamic loads {{0=None; 2=AeroDyn}}
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
"SiteA-Ref4MW_ElastoDyn.dat"    EDFile
"unused"      BDBldFile(1)
"unused"      BDBldFile(2)
"unused"      BDBldFile(3)
"SiteA-Ref4MW_InflowWind.dat"    InflowFile
"SiteA-Ref4MW_AeroDyn15.dat"    AeroFile
"unused"      ServoFile
"unused"      SeaStFile
"unused"      HydroFile
"SiteA-Ref4MW_SubDyn.dat"      SubFile
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
    with open(test_dir / "SiteA-Ref4MW.fst", 'w') as f:
        f.write(fst_content)

    # --- Modify ElastoDyn for initial displacement ---
    ed_path = test_dir / "SiteA-Ref4MW_ElastoDyn.dat"
    if ed_path.exists():
        ed_text = open(ed_path, 'r', encoding='utf-8', errors='replace').read()
        if excitation_type in ['impulse', 'combined']:
            ed_text = ed_text.replace(
                '0.0                    TTDspFA',
                '0.5                    TTDspFA'
            )
        # Set rotor speed for aero excitation
        if excitation_type in ['steady', 'combined']:
            ed_text = ed_text.replace(
                '7.000000000000001      RotSpeed',
                '7.0                    RotSpeed'
            )
        else:
            ed_text = ed_text.replace(
                '7.000000000000001      RotSpeed',
                '0.0                    RotSpeed'
            )
        with open(ed_path, 'w', encoding='utf-8') as f:
            f.write(ed_text)

    # --- Create InflowWind file for steady wind ---
    if excitation_type in ['steady', 'combined']:
        create_steady_wind_inflow(
            test_dir / "SiteA-Ref4MW_InflowWind.dat",
            wind_speed=wind_speed, ref_height=96.3
        )

    return test_dir


def run_and_extract(test_dir, name, scour):
    """Run OpenFAST and extract f1."""
    fst = test_dir / "SiteA-Ref4MW.fst"
    print(f"    Running ({name}, S={scour:.0f}m, 120s)...", end=" ", flush=True)

    try:
        result = subprocess.run(
            [str(OPENFAST), str(fst)],
            capture_output=True, text=True, timeout=900,
            cwd=str(test_dir)
        )

        out_file = test_dir / "SiteA-Ref4MW.out"
        if out_file.exists() and out_file.stat().st_size > 1000:
            names, data = read_text_output(out_file)
            if names is not None and data is not None and len(data) > 100:
                time = data[:, 0]
                dt = time[1] - time[0] if len(time) > 1 else 0.02

                # Try multiple channels for f1 extraction
                results = {}
                for ch in ['TwHt1TPxi', 'TwHt1TPyi', 'PtfmPitch', 'PtfmSurge']:
                    if ch in names:
                        idx = names.index(ch)
                        sig = data[:, idx]
                        # Convert degrees to radians for angles
                        if 'Pitch' in ch or 'Roll' in ch or 'Yaw' in ch:
                            sig = sig * np.pi / 180.0

                        f1, amp = estimate_f1(time, sig, dt)
                        results[ch] = {'f1': f1, 'amp': amp, 'rms': np.std(sig[int(len(sig)*0.2):])}

                # Best f1 = from channel with highest FFT amplitude
                best_ch = max(results, key=lambda k: results[k]['amp']) if results else None
                best_f1 = results[best_ch]['f1'] if best_ch else 0

                print(f"f1={best_f1:.4f} Hz (from {best_ch})")

                for ch, r in results.items():
                    if r['f1'] > 0.05:
                        print(f"      {ch}: f1={r['f1']:.4f} Hz, amp={r['amp']:.2e}, rms={r['rms']:.4e}")

                return best_f1, results
            else:
                print("PARSE FAILED")
        else:
            # Check error
            err_lines = [l for l in (result.stdout + result.stderr).split('\n')
                         if 'error' in l.lower() or 'abort' in l.lower()]
            print(f"FAILED")
            for el in err_lines[:3]:
                print(f"      {el.strip()[:100]}")
    except subprocess.TimeoutExpired:
        print("TIMEOUT")
    except Exception as e:
        print(f"ERROR: {e}")

    return 0.0, {}


# ═══════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════

if __name__ == '__main__':
    print("=" * 70)
    print("  Wind Excitation Investigation for Natural Frequency Extraction")
    print("  SiteA 4MW with Path A Full 6x6 SSI")
    print("=" * 70)

    all_results = {}

    for scour in [0.0, 2.0]:
        print(f"\n{'='*70}")
        print(f"  SCOUR = {scour:.1f} m (S/D = {scour/8:.3f})")
        print(f"{'='*70}")

        # Test 1: Impulse (initial displacement, no wind, no aero)
        print(f"\n  [1] Impulse (TTDspFA=0.5m, no wind):")
        td = setup_excitation_test("impulse", scour, 'impulse')
        f1, r = run_and_extract(td, "impulse", scour)
        all_results[f"impulse_S{scour:.0f}"] = f1

        # Test 2: Steady wind (8 m/s, with AeroDyn)
        print(f"\n  [2] Steady wind (8 m/s, AeroDyn enabled):")
        td = setup_excitation_test("steady8", scour, 'steady', wind_speed=8.0)
        f1, r = run_and_extract(td, "steady8", scour)
        all_results[f"steady8_S{scour:.0f}"] = f1

        # Test 3: Steady wind (12 m/s, rated wind speed)
        print(f"\n  [3] Steady wind (12 m/s, rated):")
        td = setup_excitation_test("steady12", scour, 'steady', wind_speed=12.0)
        f1, r = run_and_extract(td, "steady12", scour)
        all_results[f"steady12_S{scour:.0f}"] = f1

        # Test 4: Combined (impulse + steady wind)
        print(f"\n  [4] Combined (impulse + 8 m/s wind):")
        td = setup_excitation_test("combined", scour, 'combined', wind_speed=8.0)
        f1, r = run_and_extract(td, "combined", scour)
        all_results[f"combined_S{scour:.0f}"] = f1

    # ═══════════════════════════════════════════════════════════════
    # COMPARISON TABLE
    # ═══════════════════════════════════════════════════════════════

    print(f"\n{'='*70}")
    print(f"  FREQUENCY EXTRACTION COMPARISON")
    print(f"{'='*70}")

    print(f"\n  {'Method':<20s} {'S=0 f1 (Hz)':<14s} {'S=2 f1 (Hz)':<14s} {'OS f1 S=0':<12s} {'OS f1 S=2':<12s}")
    print(f"  {'-'*70}")

    for method in ['impulse', 'steady8', 'steady12', 'combined']:
        f0 = all_results.get(f"{method}_S0", 0)
        f2 = all_results.get(f"{method}_S2", 0)
        print(f"  {method:<20s} {f0:<14.4f} {f2:<14.4f} {OS_F1[0.0]:<12.4f} {OS_F1[2.0]:<12.4f}")

    print(f"\n  {'OpenSeesPy eigen':<20s} {OS_F1[0.0]:<14.4f} {OS_F1[2.0]:<14.4f}")

    # Evaluate which method gives f1 closest to OpenSeesPy
    print(f"\n  BEST METHOD SELECTION:")
    best_method = None
    best_error = float('inf')
    for method in ['impulse', 'steady8', 'steady12', 'combined']:
        f0 = all_results.get(f"{method}_S0", 0)
        f2 = all_results.get(f"{method}_S2", 0)
        if f0 > 0.05 and f2 > 0.05:
            err0 = abs(f0 - OS_F1[0.0]) / OS_F1[0.0] * 100
            err2 = abs(f2 - OS_F1[2.0]) / OS_F1[2.0] * 100
            avg_err = (err0 + err2) / 2
            print(f"    {method}: err_S0={err0:.1f}%, err_S2={err2:.1f}%, avg={avg_err:.1f}%")
            if avg_err < best_error:
                best_error = avg_err
                best_method = method

    if best_method:
        print(f"\n  SELECTED: {best_method} (average error = {best_error:.1f}%)")
    else:
        print(f"\n  WARNING: No method extracted meaningful f1. Check excitation levels.")
