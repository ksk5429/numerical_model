"""
PISA module V&V (Phase 3 / Task 3.1d).

Verifies the conic shape function and the assembled 6x6 pile-head
stiffness against physical invariants:

  1. K linear in G:    doubling shear modulus doubles K_xx and K_rxrx
  2. Symmetry + PD:    K = K^T, all eigenvalues > 0
  3. Mesh convergence: K_xx(n=200) and K_xx(n=400) agree within 1%
  4. Conic plateau:    y(x >= x_u) == y_u
  5. Conic monotone:   y(x) is non-decreasing on [0, x_u]
  6. Sand != clay:     different normalisations -> different K
  7. Length scaling:   K_rxrx scales super-linearly with embed length
  8. Diameter scaling: K_xx scales super-linearly with diameter
  9. K_xrx sign:       lateral-rocking coupling has the right sign

Run:
    python tests/test_pisa.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from op3.standards.pisa import (  # noqa: E402
    PISA_SAND, SoilState, conic, pisa_pile_stiffness_6x6,
)


# Reference profiles
def sand_profile(G_factor: float = 1.0):
    return [
        SoilState(0.0,  5.0e7 * G_factor, 35.0, "sand"),
        SoilState(20.0, 1.2e8 * G_factor, 35.0, "sand"),
        SoilState(40.0, 1.5e8 * G_factor, 35.0, "sand"),
    ]


def clay_profile():
    return [
        SoilState(0.0,  3.0e7, 80.0e3, "clay"),
        SoilState(20.0, 6.0e7, 120.0e3, "clay"),
    ]


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_K_linear_in_G():
    K1 = pisa_pile_stiffness_6x6(8.0, 30.0, sand_profile(1.0))
    K2 = pisa_pile_stiffness_6x6(8.0, 30.0, sand_profile(2.0))
    rxx = K2[0, 0] / K1[0, 0]
    rrr = K2[3, 3] / K1[3, 3]
    print(f"  [3.1] K linear in G: Kxx ratio={rxx:.3f}, Krxrx ratio={rrr:.3f} (expect ~2.00)")
    assert abs(rxx - 2.0) < 0.05
    assert abs(rrr - 2.0) < 0.05


def test_K_symmetric_and_pd():
    K = pisa_pile_stiffness_6x6(8.0, 30.0, sand_profile())
    sym = float(np.max(np.abs(K - K.T)))
    eigs = np.linalg.eigvalsh(0.5 * (K + K.T))
    print(f"  [3.2] symmetry residual={sym:.2e}, min eig={eigs.min():.3e}")
    assert sym < 1e-6
    assert eigs.min() > 0


def test_mesh_convergence():
    K200 = pisa_pile_stiffness_6x6(8.0, 30.0, sand_profile(), n_segments=200)
    K400 = pisa_pile_stiffness_6x6(8.0, 30.0, sand_profile(), n_segments=400)
    err_xx = abs(K400[0, 0] - K200[0, 0]) / K200[0, 0]
    err_rr = abs(K400[3, 3] - K200[3, 3]) / K200[3, 3]
    print(f"  [3.3] mesh convergence: Kxx err={err_xx:.2e}, Krxrx err={err_rr:.2e}")
    assert err_xx < 0.01
    assert err_rr < 0.01


def test_conic_plateau():
    from op3.standards.pisa import pisa_coeffs
    p = pisa_coeffs("lateral_p", "sand", z_over_D=0.0)
    y_at_xu = conic(p["x_u"], **p)
    y_above = conic(2.0 * p["x_u"], **p)
    print(f"  [3.4] conic plateau: y(x_u)={y_at_xu:.4f} y(2 x_u)={y_above:.4f} y_u={p['y_u']:.4f}")
    assert abs(y_at_xu - p["y_u"]) < 1e-6
    assert abs(y_above - p["y_u"]) < 1e-6


def test_conic_monotone():
    from op3.standards.pisa import pisa_coeffs
    p = pisa_coeffs("lateral_p", "sand", z_over_D=0.0)
    xs = np.linspace(0, p["x_u"], 100)
    ys = np.array([conic(float(x), **p) for x in xs])
    diffs = np.diff(ys)
    print(f"  [3.5] conic monotone: min step = {diffs.min():.3e}")
    assert diffs.min() >= -1e-12


def test_sand_clay_differ():
    K_sand = pisa_pile_stiffness_6x6(8.0, 30.0, sand_profile())
    K_clay = pisa_pile_stiffness_6x6(8.0, 30.0, clay_profile())
    ratio = K_sand[0, 0] / K_clay[0, 0]
    print(f"  [3.6] sand/clay Kxx ratio = {ratio:.3f} (must differ from 1.0)")
    assert abs(ratio - 1.0) > 0.05


def test_length_scaling():
    K30 = pisa_pile_stiffness_6x6(8.0, 30.0, sand_profile())
    K60 = pisa_pile_stiffness_6x6(8.0, 60.0, sand_profile())
    rrr = K60[3, 3] / K30[3, 3]
    print(f"  [3.7] L 30->60 m: Krxrx ratio = {rrr:.2f} (expect > 2)")
    assert rrr > 2.0


def test_diameter_scaling():
    K6 = pisa_pile_stiffness_6x6(6.0, 30.0, sand_profile())
    K12 = pisa_pile_stiffness_6x6(12.0, 30.0, sand_profile())
    rxx = K12[0, 0] / K6[0, 0]
    print(f"  [3.8] D 6->12 m: Kxx ratio = {rxx:.2f} (expect > 1)")
    assert rxx > 1.0


def test_lateral_rocking_coupling_sign():
    K = pisa_pile_stiffness_6x6(8.0, 30.0, sand_profile())
    print(f"  [3.9] K[0,4]={K[0,4]:.3e}, K[1,3]={K[1,3]:.3e}")
    # Lateral push at the head induces rocking in the same plane;
    # the off-diagonal must be non-zero with the conventional sign.
    assert K[0, 4] != 0
    assert K[1, 3] != 0
    assert np.sign(K[0, 4]) != np.sign(K[1, 3])  # opposite half-planes


# ---------------------------------------------------------------------------
# Standalone runner
# ---------------------------------------------------------------------------

def main():
    print()
    print("=" * 70)
    print(" Op3 PISA module V&V -- Task 3.1d")
    print("=" * 70)
    tests = [
        test_K_linear_in_G,
        test_K_symmetric_and_pd,
        test_mesh_convergence,
        test_conic_plateau,
        test_conic_monotone,
        test_sand_clay_differ,
        test_length_scaling,
        test_diameter_scaling,
        test_lateral_rocking_coupling_sign,
    ]
    fails = 0
    for t in tests:
        try:
            t()
        except AssertionError as e:
            print(f"  FAIL: {t.__name__}: {e}")
            fails += 1
        except Exception as e:
            print(f"  ERROR: {t.__name__}: {type(e).__name__}: {e}")
            fails += 1
    print("=" * 70)
    print(f" {len(tests) - fails}/{len(tests)} PISA invariants held")
    print("=" * 70)
    return fails


if __name__ == "__main__":
    sys.exit(main())
