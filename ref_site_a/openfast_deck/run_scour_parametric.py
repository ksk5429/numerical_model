"""
Run OpenFAST parametric study: vary scour depth.
For each scour depth, update the SSI stiffness matrix from OpenSeesPy v4.
"""
import os
import subprocess
import numpy as np
from pathlib import Path

OPENFAST = Path(r"F:\TREE_OF_THOUGHT\PHD\openfast\openfast_x64.exe")
MODEL_DIR = Path(r"F:\TREE_OF_THOUGHT\PHD\openfast\SiteA_Ref4MW")

# Foundation stiffness vs scour (from v4 dissipation model)
# KH scales approximately as (1 - 0.30 * S/D) based on capacity degradation
SCOUR_DEPTHS = [0, 1, 2, 3, 4]  # meters

# Baseline stiffness (from SSOT, 3 buckets)
KH_0 = 6.97e8 * 3
KV_0 = 9.96e8 * 3
KM_0 = 4.67e10 * 3
KT_0 = 2.01e10 * 3

for scour in SCOUR_DEPTHS:
    sd = scour / 8.0
    # Stiffness reduction from v4 model scour curve
    # f1/f0 at this S/D (from fullGenLapack)
    f1f0_curve = {0: 1.0, 0.0625: 0.996, 0.125: 0.991, 0.1875: 0.986,
                  0.25: 0.981, 0.3125: 0.975, 0.375: 0.968, 0.4375: 0.960, 0.5: 0.950}
    f1f0 = np.interp(sd, list(f1f0_curve.keys()), list(f1f0_curve.values()))
    k_ratio = f1f0**2  # stiffness scales as frequency squared

    KH = KH_0 * k_ratio
    KV = KV_0 * k_ratio
    KM = KM_0 * k_ratio
    KT = KT_0 * k_ratio

    # Update SSI file
    ssi = f"""------- SSI INPUT FILE -------
Scour = {scour}m (S/D = {sd:.3f}), k_ratio = {k_ratio:.4f}
1                SSIMode
{KH:.4e}   0.0         0.0         0.0         0.0         0.0
0.0         {KH:.4e}   0.0         0.0         0.0         0.0
0.0         0.0         {KV:.4e}   0.0         0.0         0.0
0.0         0.0         0.0         {KM:.4e}   0.0         0.0
0.0         0.0         0.0         0.0         {KM:.4e}   0.0
0.0         0.0         0.0         0.0         0.0         {KT:.4e}
"""
    (MODEL_DIR / "SiteA-Ref4MW_SSI.dat").write_text(ssi)
    print(f"Scour {scour}m: KH={KH:.2e}, running OpenFAST...")

    # Run OpenFAST
    result = subprocess.run(
        [str(OPENFAST), str(MODEL_DIR / "SiteA-Ref4MW.fst")],
        capture_output=True, text=True, timeout=600
    )

    if result.returncode == 0:
        print(f"  SUCCESS")
    else:
        print(f"  FAILED: {result.stderr[:200]}")
