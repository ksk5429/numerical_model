"""
PISA wiring demo (Phase 3 / Task 3.1c).

Builds the OC3 NREL 5MW tower in two configurations:

  A) fixed at the mudline (current example 02 baseline)
  B) attached to a PISA-derived 6x6 foundation representing the
     OC3 monopile-in-sand profile (D = 6 m, embed = 36 m, dense sand)

Reports the eigenvalue shift and the dominant compliance terms in the
PISA stiffness matrix. Confirms that adding soil flexibility lowers
f1 -- the expected physical behaviour.

This is the first end-to-end exercise of:
  op3.standards.pisa  ->  op3.foundations.foundation_from_pisa
  ->  op3.composer.compose_tower_model  ->  OpenSeesPy eigen
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from op3 import build_foundation, compose_tower_model  # noqa: E402
from op3.foundations import foundation_from_pisa       # noqa: E402
from op3.standards.pisa import SoilState               # noqa: E402


# OC3 monopile is 6 m diameter, embed 36 m below mudline in 20 m water.
# Dense Baltic sand: G ~ 50 MPa near surface, ~150 MPa at depth.
PISA_PROFILE = [
    SoilState(depth_m=0.0,  G_Pa=5.0e7,  su_or_phi=35.0, soil_type="sand"),
    SoilState(depth_m=10.0, G_Pa=8.0e7,  su_or_phi=35.0, soil_type="sand"),
    SoilState(depth_m=20.0, G_Pa=1.2e8,  su_or_phi=36.0, soil_type="sand"),
    SoilState(depth_m=36.0, G_Pa=1.5e8,  su_or_phi=37.0, soil_type="sand"),
]


def f1_fixed() -> float:
    model = compose_tower_model(
        rotor="nrel_5mw_baseline",
        tower="nrel_5mw_oc3_tower",
        foundation=build_foundation(mode="fixed"),
    )
    return float(model.eigen(n_modes=3)[0])


def f1_pisa() -> tuple[float, np.ndarray]:
    fnd = foundation_from_pisa(
        diameter_m=6.0,
        embed_length_m=36.0,
        soil_profile=PISA_PROFILE,
    )
    model = compose_tower_model(
        rotor="nrel_5mw_baseline",
        tower="nrel_5mw_oc3_tower",
        foundation=fnd,
    )
    return float(model.eigen(n_modes=3)[0]), fnd.stiffness_matrix


def main():
    print()
    print("=" * 72)
    print(" Op3 PISA wiring demo -- NREL 5MW OC3 monopile")
    print("=" * 72)

    f0 = f1_fixed()
    print(f"  fixed (no soil flex):  f1 = {f0:.4f} Hz")

    f_pisa, K = f1_pisa()
    print(f"  PISA Mode B  (D=6 m, L=36 m, dense sand):")
    print(f"    Kxx    = {K[0,0]:.3e} N/m")
    print(f"    Kzz    = {K[2,2]:.3e} N/m")
    print(f"    Krxrx  = {K[3,3]:.3e} Nm/rad")
    print(f"    Kxrx   = {K[1,3]:.3e} N (lateral-rocking coupling)")
    print(f"    f1 = {f_pisa:.4f} Hz   ({(f_pisa-f0)/f0*100:+.2f}% vs fixed)")
    print()
    print("  Sanity:")
    print(f"    Symmetric:        {np.allclose(K, K.T)}")
    print(f"    Positive-def:     {np.all(np.linalg.eigvalsh(K) > 0)}")
    print(f"    f_PISA < f_fixed: {f_pisa < f0}  (soil flex must lower f1)")
    print("=" * 72)

    assert f_pisa < f0, "PISA flex did not lower f1 -- something is wrong"
    assert np.allclose(K, K.T), "PISA K not symmetric"
    assert np.all(np.linalg.eigvalsh(K) > 0), "PISA K not positive-definite"


if __name__ == "__main__":
    main()
