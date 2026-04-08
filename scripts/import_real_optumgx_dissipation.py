"""
Import real OptumGX Gunsan dissipation + spring parameters into the
Op^3 Mode C / Mode D pipeline.

Replaces the v0.1 synthetic Gaussian placeholders at
``data/fem_results/spring_profile_op3.csv`` and
``data/fem_results/dissipation_profile.csv`` with the real OptumGX
v4 dissipation pipeline outputs extracted from the dissertation
working directory at
``F:/TREE_OF_THOUGHT/PHD/data/optumgx/dissipation/``.

Source files (copied verbatim into ``data/fem_results/`` with the
``gunsan_real_*`` prefix for provenance):

  - ``spring_params_v4_dissipation.csv`` (19 rows, 0.5 -> 9.5 m depth)
    columns: z_m, su_kPa, w_dissip, Np, k_ini_kNm3, p_ult_kNm,
             y50_mm, t_ult_kNm, source_*
  - ``dissipation_skirt_Vmax.csv`` (18 rows at +/-0.25 m depth bins)
    columns: db (depth), diss_mean, diss_norm, count
  - ``fn_vs_scour_v4_dissipation.csv`` (9 rows, 0 -> 4 m scour)
    columns: scour_m, f_n_Hz, drop_pct, err_pct

The conversion produces the Op^3 canonical CSV schema:

  ``spring_profile_op3.csv``  columns: depth_m, k_ini_kN_per_m,
                              p_ult_kN_per_m, spring_type
  ``dissipation_profile.csv`` columns: depth_m, w_z, D_total_kJ

The OptumGX k_ini is in kN/m^3 (Winkler modulus of subgrade) and
p_ult is in kN/m (force per unit pile length). Op^3 expects
k_ini_kN_per_m (stiffness per unit pile length). For a suction
bucket of diameter D_bucket = 8 m:
    k_ini [kN/m per m of pile] = k_ini [kN/m^3] * D_bucket

Run
---
    python scripts/import_real_optumgx_dissipation.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = REPO_ROOT / "data/fem_results"

D_BUCKET_M = 8.0   # Gunsan suction bucket diameter


def main():
    sys.stdout.reconfigure(encoding="utf-8")

    src_params = DATA_DIR / "gunsan_real_spring_params.csv"
    src_diss = DATA_DIR / "gunsan_real_dissipation_skirt.csv"

    if not src_params.exists():
        raise FileNotFoundError(
            f"Real OptumGX spring params not found: {src_params}\n"
            "Run the copy step first or check the source path in PHD/data/optumgx/dissipation/"
        )
    if not src_diss.exists():
        raise FileNotFoundError(f"Real OptumGX dissipation not found: {src_diss}")

    print("=" * 72)
    print(" Op3 OptumGX dissipation importer -- replacing synthetic placeholders")
    print("=" * 72)

    # ------------------------------------------------------------------
    # Spring profile: k_ini [kN/m^3] * D_bucket -> k_ini [kN/m per m]
    # ------------------------------------------------------------------
    params = pd.read_csv(src_params)
    print(f"\n  source: {src_params.name}  ({len(params)} rows)")
    print(f"  depth range: {params['z_m'].min():.2f} -> {params['z_m'].max():.2f} m")
    print(f"  k_ini [kN/m^3] range: {params['k_ini_kNm3'].min():.0f} -> "
          f"{params['k_ini_kNm3'].max():.0f}")
    print(f"  p_ult [kN/m] range:   {params['p_ult_kNm'].min():.0f} -> "
          f"{params['p_ult_kNm'].max():.0f}")

    sp_out = pd.DataFrame({
        "depth_m": params["z_m"].values.astype(float),
        "k_ini_kN_per_m": params["k_ini_kNm3"].values * D_BUCKET_M,
        "p_ult_kN_per_m": params["p_ult_kNm"].values.astype(float),
        "spring_type": ["lateral"] * len(params),
    })
    sp_path = DATA_DIR / "spring_profile_op3.csv"
    sp_out.to_csv(sp_path, index=False, float_format="%.6e")
    print(f"\n  wrote {sp_path.name}: {len(sp_out)} rows (REAL OptumGX)")
    print(f"    k_ini_kN_per_m range: {sp_out['k_ini_kN_per_m'].min():.0f} -> "
          f"{sp_out['k_ini_kN_per_m'].max():.0f}")

    # ------------------------------------------------------------------
    # Dissipation profile: use w_dissip from spring_params (already
    # normalized) aligned with the same depth grid as the spring profile
    # ------------------------------------------------------------------
    # Compute D_total_kJ by integrating diss_mean from dissipation_skirt
    # Vmax onto the spring-profile depth grid.
    diss = pd.read_csv(src_diss)
    print(f"\n  source: {src_diss.name}  ({len(diss)} rows)")

    # Interpolate diss_mean onto the spring profile depths.
    # The dissipation file uses db (depth below mudline) in 0.5 m bins
    # with a peak at 1.25 m (312.96 kJ) near the skirt wedge.
    diss_on_sp = np.interp(
        sp_out["depth_m"].values,
        diss["db"].values,
        diss["diss_mean"].values,
        left=0.0, right=0.0,
    )

    diss_out = pd.DataFrame({
        "depth_m": sp_out["depth_m"].values,
        "w_z": params["w_dissip"].values.astype(float),
        "D_total_kJ": diss_on_sp,
    })
    diss_path = DATA_DIR / "dissipation_profile.csv"
    diss_out.to_csv(diss_path, index=False, float_format="%.6e")
    print(f"\n  wrote {diss_path.name}: {len(diss_out)} rows (REAL OptumGX)")
    print(f"    w_z range: {diss_out['w_z'].min():.3f} -> {diss_out['w_z'].max():.3f}")
    print(f"    D_total_kJ range: {diss_out['D_total_kJ'].min():.1f} -> "
          f"{diss_out['D_total_kJ'].max():.1f}")
    print(f"    w_z peak at z = {diss_out.loc[diss_out['w_z'].idxmax(), 'depth_m']:.2f} m")
    print(f"    D_total peak at z = {diss_out.loc[diss_out['D_total_kJ'].idxmax(), 'depth_m']:.2f} m")

    print()
    print("=" * 72)
    print(" Both files are now the REAL OptumGX Gunsan output.")
    print(" No synthetic placeholders remain.")
    print("=" * 72)


if __name__ == "__main__":
    main()
