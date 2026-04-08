"""
Wind-Excited Scour Sweep with ROSCO Controller
===============================================
Run OC3 5MW + Gunsan SSI at multiple scour levels with steady wind.
Extract f1 (tower bending mode) from FFT of tower-top displacement.
Compare with OpenSeesPy eigenvalue at each scour level.
"""
import sys
import os
import struct
import shutil
import subprocess
import numpy as np
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, str(Path(__file__).parent))

from config import BUCKET, STIFFNESS, PARAMS, COUPLING_OUTPUT
from opensees_stiffness_extractor import StiffnessExtractor, SSIWriter

OPENFAST = Path(r"f:\TREE_OF_THOUGHT\PHD\openfast\openfast_x64.exe")
TEMPLATE = COUPLING_OUTPUT / "oc3_with_gunsan_ssi"
SWEEP_DIR = COUPLING_OUTPUT / "wind_scour_sweep"

# OpenSeesPy reference (from v4 dissipation model eigenvalue)
OPENSEES_F1 = {
    0.0: 0.2367, 0.5: 0.2344, 1.0: 0.2311, 1.5: 0.2274,
    2.0: 0.2231, 2.5: 0.2183, 3.0: 0.2128, 3.5: 0.2064, 4.0: 0.1990
}


def read_outb(fp):
    """Read OpenFAST compressed binary output."""
    with open(fp, 'rb') as f:
        fid = struct.unpack('<h', f.read(2))[0]
        nc = struct.unpack('<i', f.read(4))[0]
        nt = struct.unpack('<i', f.read(4))[0]
        ts = struct.unpack('<d', f.read(8))[0]
        t0 = struct.unpack('<d', f.read(8))[0]
        dsl = struct.unpack('<i', f.read(4))[0]; f.read(dsl)
        names = [f.read(10).decode('ascii', errors='replace').strip() for _ in range(nc + 1)]
        units = [f.read(10).decode('ascii', errors='replace').strip() for _ in range(nc + 1)]
        slopes = np.frombuffer(f.read(4 * nc), dtype='<f4')
        offsets = np.frombuffer(f.read(4 * nc), dtype='<f4')
        raw = np.frombuffer(f.read(2 * nt * nc), dtype='<i2').reshape(nt, nc)
        data = (raw - offsets) / np.where(slopes != 0, slopes, 1.0)
    dt = t0 if ts == 0 else ts
    time = np.arange(nt) * dt
    return names, time, data, dt


def extract_f1_tower(names, time, data, dt, skip_s=15.0, f_range=(0.1, 0.8)):
    """Extract tower bending f1 from TwHt1TPxi channel."""
    ch = 'TwHt1TPxi'
    if ch not in names:
        return 0.0, 0.0

    idx = names.index(ch) - 1
    sig = data[:, idx]
    mask = time > skip_s
    s = sig[mask]

    if np.any(np.isnan(s)) or np.std(s) < 1e-15:
        return 0.0, 0.0

    s = s - np.mean(s)
    n = len(s)
    nfft = max(n, 32768)
    freqs = np.fft.rfftfreq(nfft, d=dt)
    fft_mag = np.abs(np.fft.rfft(s * np.hanning(n), n=nfft))

    # Look for tower bending mode in 0.1-0.8 Hz band
    # Skip the platform rocking mode (typically < 0.1 Hz)
    band = (freqs >= f_range[0]) & (freqs <= f_range[1])
    if not np.any(band):
        return 0.0, 0.0

    fb = fft_mag[band]
    fr = freqs[band]
    peak_idx = np.argmax(fb)

    return fr[peak_idx], fb[peak_idx]


def run_scour_level(scour, extractor):
    """Run one scour level: extract K -> write SSI -> run OpenFAST."""
    SD = scour / BUCKET.D
    run_dir = SWEEP_DIR / f"S{scour:.1f}m"

    print(f"  S = {scour:.1f} m (S/D = {SD:.3f})", end="", flush=True)

    # Extract 6x6 stiffness
    K_all = extractor.extract_all_buckets(scour=scour, verbose=False)

    # Create run directory from template
    if run_dir.exists():
        try:
            shutil.rmtree(run_dir)
        except:
            import time as tm
            run_dir = SWEEP_DIR / f"S{scour:.1f}m_{int(tm.time()) % 10000}"

    shutil.copytree(TEMPLATE, run_dir)

    # Write SSI files
    for idx, (bn, K) in enumerate(K_all.items(), 1):
        SSIWriter.write(run_dir / f"SSI_pile{idx}.dat", K,
                        scour_depth=scour, bucket_id=idx)

    # Run OpenFAST
    print(" -> OpenFAST", end="", flush=True)
    fst = run_dir / "5MW_OC3Trpd_DLL_WSt_WavesReg.fst"

    try:
        result = subprocess.run(
            [str(OPENFAST), str(fst)],
            capture_output=True, text=True, timeout=600,
            cwd=str(run_dir)
        )

        outb = run_dir / "5MW_OC3Trpd_DLL_WSt_WavesReg.outb"
        if outb.exists() and outb.stat().st_size > 10000:
            names, time, data, dt = read_outb(outb)
            f1, amp = extract_f1_tower(names, time, data, dt)

            # Also get platform rocking frequency
            f1_rock, amp_rock = extract_f1_tower(names, time, data, dt, f_range=(0.02, 0.1))

            # Get stiffness for this scour level
            K1 = K_all[list(K_all.keys())[0]]
            KH = K1[0, 0]
            KM = K1[4, 4]

            print(f" -> f1_tower={f1:.4f} Hz, f1_rock={f1_rock:.4f} Hz")

            return {
                'scour': scour, 'SD': SD,
                'f1_tower': f1, 'f1_tower_amp': amp,
                'f1_rocking': f1_rock, 'f1_rocking_amp': amp_rock,
                'KH': KH, 'KM': KM,
                'opensees_f1': OPENSEES_F1.get(scour, 0),
            }
        else:
            print(" -> NO OUTPUT")
            return {'scour': scour, 'SD': SD, 'error': 'no_output'}

    except subprocess.TimeoutExpired:
        print(" -> TIMEOUT")
        return {'scour': scour, 'SD': SD, 'error': 'timeout'}
    except Exception as e:
        print(f" -> ERROR: {e}")
        return {'scour': scour, 'SD': SD, 'error': str(e)}


if __name__ == '__main__':
    print("=" * 70)
    print("  Wind-Excited Scour Sweep: OC3 5MW + Gunsan SSI + ROSCO")
    print("=" * 70)

    SWEEP_DIR.mkdir(parents=True, exist_ok=True)

    print("\n  Initializing stiffness extractor...")
    extractor = StiffnessExtractor()

    scour_depths = [0.0, 1.0, 2.0, 3.0, 4.0]
    results = []

    for S in scour_depths:
        r = run_scour_level(S, extractor)
        if r:
            results.append(r)

    # Results table
    print(f"\n{'=' * 80}")
    print(f"  SCOUR SWEEP RESULTS")
    print(f"{'=' * 80}")

    print(f"\n  {'S/D':<6s} {'KH (N/m)':<12s} {'f1_tower Hz':<12s} {'f1_rock Hz':<12s} {'OS_f1 Hz':<10s} {'Df1_tower%':<10s}")
    print(f"  {'-' * 65}")

    f1_ref = results[0].get('f1_tower', 0) if results else 0
    for r in results:
        if 'error' in r:
            print(f"  {r['SD']:<6.3f} ERROR: {r.get('error', '')}")
            continue
        f1t = r.get('f1_tower', 0)
        f1r = r.get('f1_rocking', 0)
        os_f1 = r.get('opensees_f1', 0)
        df = (f1t - f1_ref) / f1_ref * 100 if f1_ref > 0 and f1t > 0 else 0
        print(f"  {r['SD']:<6.3f} {r.get('KH', 0):<12.3e} {f1t:<12.4f} {f1r:<12.4f} {os_f1:<10.4f} {df:<+10.1f}")

    # Save CSV
    csv_path = SWEEP_DIR / "wind_scour_sweep_results.csv"
    with open(csv_path, 'w') as f:
        f.write("scour_m,SD,KH_Nm,KM_Nmrad,f1_tower_Hz,f1_rocking_Hz,opensees_f1_Hz\n")
        for r in results:
            if 'error' in r: continue
            f.write(f"{r['scour']},{r['SD']},{r.get('KH',0)},{r.get('KM',0)},"
                    f"{r.get('f1_tower',0)},{r.get('f1_rocking',0)},{r.get('opensees_f1',0)}\n")

    print(f"\n  Results: {csv_path}")
    print(f"  Runs: {SWEEP_DIR}/S*m/")
