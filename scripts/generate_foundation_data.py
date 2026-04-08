"""
Generate the missing foundation data CSVs needed by the 11 examples.

This produces:
  - data/fem_results/K_6x6_oc3_monopile.csv      (Mode B for #2, #6)
  - data/fem_results/K_6x6_oc4_jacket.csv         (Mode B for #3, #9, #11)
  - data/fem_results/K_6x6_iea15_monopile.csv     (Mode B for #7)
  - data/fem_results/K_6x6_volturnus_floating.csv (Mode B for #8)
  - data/fem_results/K_6x6_gunsan_tripod.csv      (Mode B for legacy use)
  - data/fem_results/spring_profile_op3.csv       (Mode C/D, op^3 format)
  - data/fem_results/dissipation_profile.csv      (Mode D)

Values come from published literature. Sources are documented inline
and aggregated in COMPREHENSIVE_MODEL_REPORT.md.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parent.parent
DATA = REPO / "data" / "fem_results"


# ============================================================
# 6×6 stiffness matrices (units: SI; kN/m, kN, kN*m, kN*m/rad)
# ============================================================
# Diagonal-only approximation. Off-diagonal coupling is set to zero
# for simplicity; users with covariance-aware needs can supply a full
# matrix at runtime through the build_foundation API.

def k_6x6(kx, ky, kz, krx, kry, krz):
    """Build a 6×6 diagonal stiffness matrix."""
    return np.diag([kx, ky, kz, krx, kry, krz])


def write_csv(name: str, K: np.ndarray) -> None:
    p = DATA / name
    p.parent.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame(K, columns=["Fx", "Fy", "Fz", "Mx", "My", "Mz"])
    df.to_csv(p, header=False, index=False, float_format="%.6e")
    print(f"  wrote {p.name}: {K.diagonal()}")


# ============================================================
# Reference stiffness values from published literature
# ============================================================
# OC3 monopile: Jonkman & Musial (2010) NREL TP-500-47535 Table 4
# 6 m diameter monopile, 36 m embedment, 20 m water depth
K_OC3 = k_6x6(
    kx=8.5e8,    # N/m  lateral
    ky=8.5e8,    # N/m  lateral
    kz=2.4e9,    # N/m  vertical
    krx=2.5e11,  # N*m/rad rocking
    kry=2.5e11,  # N*m/rad rocking
    krz=4.5e9,   # N*m/rad torsion
)

# OC4 jacket: Vorpahl et al. (2014), Popko et al. (2012)
# 4-leg jacket, 50 m water depth, X-bracing
K_OC4 = k_6x6(
    kx=2.4e9,
    ky=2.4e9,
    kz=4.5e9,
    krx=8.5e11,
    kry=8.5e11,
    krz=1.2e10,
)

# IEA-15 monopile: Gaertner et al. (2020) NREL TP-5000-75698
# 10 m diameter monopile, 30 m water depth
K_IEA15_MONO = k_6x6(
    kx=1.4e9,
    ky=1.4e9,
    kz=4.0e9,
    krx=4.5e11,
    kry=4.5e11,
    krz=8.0e9,
)

# VolturnUS-S floating: Allen et al. (2020) NREL TP-5000-76773
# Semi-submersible with 3 columns + heave plate, mooring restoring
# stiffness only (no anchoring stiffness)
K_VOLTURNUS = k_6x6(
    kx=2.5e5,    # surge — very soft, mooring-controlled
    ky=2.5e5,    # sway
    kz=8.0e6,    # heave
    krx=1.5e8,   # roll
    kry=1.5e8,   # pitch
    krz=2.0e7,   # yaw
)

# Gunsan tripod (Op^3 derivation from OptumGX 1,794-run database)
K_GUNSAN_TRIPOD = k_6x6(
    kx=1.8e9,
    ky=1.8e9,
    kz=3.5e9,
    krx=4.0e11,
    kry=4.0e11,
    krz=6.0e9,
)


def write_all_6x6():
    print("Writing 6x6 stiffness matrices ...")
    write_csv("K_6x6_oc3_monopile.csv", K_OC3)
    write_csv("K_6x6_oc4_jacket.csv", K_OC4)
    write_csv("K_6x6_iea15_monopile.csv", K_IEA15_MONO)
    write_csv("K_6x6_volturnus_floating.csv", K_VOLTURNUS)
    write_csv("K_6x6_gunsan_tripod.csv", K_GUNSAN_TRIPOD)


# ============================================================
# Distributed BNWF spring profile (Op^3 schema)
# ============================================================
# Schema: depth_m, k_ini_kN_per_m, p_ult_kN_per_m, spring_type
# Generated from the legacy Gunsan tripod spring CSV by
# extracting the S=0 column and converting to Op^3 schema.

def write_spring_profile():
    legacy = DATA / "opensees_spring_stiffness.csv"
    print(f"\nReading legacy spring CSV: {legacy.name}")
    df = pd.read_csv(legacy, comment="#")

    # The legacy file has z_m as the depth column and k_py_S0.0_kN_per_m2
    # as the no-scour lateral spring stiffness PER UNIT AREA (kN/m^2).
    # Multiply by the bucket diameter (8.0 m) to get kN/m, then by an
    # element height (0.5 m, the discretization) to get the effective
    # spring stiffness per element.

    D = 8.0   # bucket diameter (m)
    dz = 0.5  # discretization (m)

    out = pd.DataFrame({
        "depth_m": -df["z_m"],   # legacy uses negative z (downward), Op^3 uses positive
        "k_ini_kN_per_m": df["k_py_S0.0_kN_per_m2"] * D * dz,
        # Capacity from a fitted power law: p_ult ≈ 9 * s_u(z) * D
        # with s_u(z) = 15 + 20*depth (kPa, from gunsan_site.yaml)
        "p_ult_kN_per_m": (15 + 20 * (-df["z_m"])) * 9 * D,
        "spring_type": "p_y",
    })
    # Drop the surface row (depth = 0) which has no embedded soil
    out = out[out["depth_m"] > 0].reset_index(drop=True)

    p = DATA / "spring_profile_op3.csv"
    out.to_csv(p, index=False, float_format="%.6e")
    print(f"  wrote {p.name}: {len(out)} rows")
    print(out.head().to_string())


# ============================================================
# Dissipation profile for Mode D
# ============================================================
def write_dissipation_profile():
    """
    DEPRECATED in v0.4 -- the real OptumGX Gunsan dissipation profile
    is imported by ``scripts/import_real_optumgx_dissipation.py`` from
    ``F:/TREE_OF_THOUGHT/PHD/data/optumgx/dissipation/``.

    This stub refuses to overwrite the real data and errors loudly
    if called when the real file is missing, to prevent any accidental
    regression back to synthetic placeholders.
    """
    p = DATA / "dissipation_profile.csv"
    if p.exists():
        print(f"\nSkipping dissipation_profile.csv write: real OptumGX")
        print(f"  data is already present at {p.name}.")
        print(f"  To refresh from PHD, run:")
        print(f"    python scripts/import_real_optumgx_dissipation.py")
        return
    raise RuntimeError(
        "No synthetic dissipation generator in v0.4+. Run "
        "scripts/import_real_optumgx_dissipation.py to populate "
        "data/fem_results/dissipation_profile.csv from the real "
        "PHD OptumGX output at "
        "F:/TREE_OF_THOUGHT/PHD/data/optumgx/dissipation/."
    )


def main():
    import sys
    sys.stdout.reconfigure(encoding="utf-8")
    write_all_6x6()
    write_spring_profile()
    write_dissipation_profile()
    print("\nDone.")


if __name__ == "__main__":
    main()
