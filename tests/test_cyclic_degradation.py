"""
Cyclic degradation V&V (Phase 3 / Task 3.2 tests).

Verifies the Hardin-Drnevich backbone, the Vucetic-Dobry reference
strain curve, and the integration with PISA via the
``cyclic_stiffness_6x6`` wrapper.

Asserted invariants
-------------------
1. G/Gmax(0)         == 1                (no strain -> no degradation)
2. G/Gmax(gamma_ref) == 0.5              (definition of gamma_ref)
3. G/Gmax(inf)       -> 0                (asymptote at high strain)
4. Monotone decrease of G/Gmax with gamma
5. Vucetic-Dobry: gamma_ref(PI=0) < gamma_ref(PI=200)
6. Vucetic-Dobry: gamma_ref interpolation is monotone in PI
7. degrade_profile leaves the original profile unchanged
8. degrade_profile reduces G by exactly G/Gmax at gamma_ref
9. cyclic_stiffness_6x6 < pisa_pile_stiffness_6x6 elementwise on diag
10. Damping ratio increases with gamma

Run:
    python tests/test_cyclic_degradation.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from op3.standards.cyclic_degradation import (  # noqa: E402
    cyclic_stiffness_6x6,
    damping_ratio,
    degrade_profile,
    gamma_ref_for,
    hardin_drnevich,
    hardin_drnevich_array,
    vucetic_dobry_gamma_ref,
)
from op3.standards.pisa import SoilState, pisa_pile_stiffness_6x6  # noqa: E402


PROFILE = [
    SoilState(0.0,  5.0e7, 35.0, "sand"),
    SoilState(20.0, 1.2e8, 35.0, "sand"),
]


def test_no_strain_no_degradation():
    r = hardin_drnevich(0.0, 1e-4)
    print(f"  [3.2.1] G/Gmax(0) = {r:.4f}")
    assert r == 1.0


def test_half_at_gamma_ref():
    g_ref = 5e-4
    r = hardin_drnevich(g_ref, g_ref)
    print(f"  [3.2.2] G/Gmax(gamma_ref) = {r:.4f}")
    assert abs(r - 0.5) < 1e-12


def test_asymptote_at_high_strain():
    r = hardin_drnevich(1.0, 1e-4)
    print(f"  [3.2.3] G/Gmax(huge) = {r:.2e}")
    assert r < 1e-3


def test_monotone_decrease():
    gs = np.logspace(-7, -1, 200)
    rs = hardin_drnevich_array(gs, 1e-4)
    diffs = np.diff(rs)
    print(f"  [3.2.4] G/Gmax monotone: max +ve diff = {diffs.max():.2e}")
    assert diffs.max() <= 1e-12


def test_vucetic_dobry_extremes():
    g0 = vucetic_dobry_gamma_ref(0.0)
    g200 = vucetic_dobry_gamma_ref(200.0)
    print(f"  [3.2.5] gamma_ref(PI=0)={g0:.2e}, gamma_ref(PI=200)={g200:.2e}")
    assert g0 < g200
    assert 5e-5 < g0 < 5e-4
    assert 1e-3 < g200 < 1e-2


def test_vucetic_dobry_monotone():
    PIs = np.linspace(0, 200, 50)
    grs = np.array([vucetic_dobry_gamma_ref(p) for p in PIs])
    diffs = np.diff(grs)
    print(f"  [3.2.6] gamma_ref(PI) monotone: min diff = {diffs.min():.2e}")
    assert diffs.min() >= 0


def test_degrade_profile_immutability():
    original_G = [s.G_Pa for s in PROFILE]
    _ = degrade_profile(PROFILE, cyclic_strain=1e-3)
    after_G = [s.G_Pa for s in PROFILE]
    print(f"  [3.2.7] original profile preserved: {original_G == after_G}")
    assert original_G == after_G


def test_degrade_profile_exact_at_gamma_ref():
    """At cyclic_strain == gamma_ref the layer's G should be halved."""
    soil = SoilState(0.0, 1.0e8, 35.0, "sand")
    g_ref = gamma_ref_for(soil)
    degraded = degrade_profile([soil], cyclic_strain=g_ref)
    ratio = degraded[0].G_Pa / soil.G_Pa
    print(f"  [3.2.8] G_after / G_before at gamma_ref = {ratio:.4f}")
    assert abs(ratio - 0.5) < 1e-12


def test_cyclic_stiffness_lower_than_static():
    K_static = pisa_pile_stiffness_6x6(8.0, 30.0, PROFILE)
    K_cyclic = cyclic_stiffness_6x6(
        diameter_m=8.0, embed_length_m=30.0,
        soil_profile=PROFILE, cyclic_strain=1e-3,
    )
    print(f"  [3.2.9] Kxx static={K_static[0,0]:.3e}, cyclic={K_cyclic[0,0]:.3e}")
    for i in range(6):
        assert K_cyclic[i, i] <= K_static[i, i] + 1e-6 * abs(K_static[i, i])
    assert K_cyclic[0, 0] < K_static[0, 0]
    assert K_cyclic[3, 3] < K_static[3, 3]


def test_damping_increases_with_strain():
    d_low = damping_ratio(1e-6, 1e-4)
    d_mid = damping_ratio(1e-4, 1e-4)
    d_hi = damping_ratio(1e-2, 1e-4)
    print(f"  [3.2.10] D(low)={d_low:.3f} D(mid)={d_mid:.3f} D(high)={d_hi:.3f}")
    assert d_low < d_mid < d_hi


# ---------------------------------------------------------------------------
# Standalone runner
# ---------------------------------------------------------------------------

def main():
    print()
    print("=" * 70)
    print(" Op3 cyclic degradation V&V -- Task 3.2")
    print("=" * 70)
    tests = [
        test_no_strain_no_degradation,
        test_half_at_gamma_ref,
        test_asymptote_at_high_strain,
        test_monotone_decrease,
        test_vucetic_dobry_extremes,
        test_vucetic_dobry_monotone,
        test_degrade_profile_immutability,
        test_degrade_profile_exact_at_gamma_ref,
        test_cyclic_stiffness_lower_than_static,
        test_damping_increases_with_strain,
    ]
    fails = 0
    for t in tests:
        # Reset OpenSeesPy global domain between tests (Linux CI fix).
        try:
            import openseespy.opensees as _ops
            _ops.wipe()
        except Exception:
            pass
        try:
            t()
        except AssertionError as e:
            print(f"  FAIL: {t.__name__}: {e}")
            fails += 1
        except Exception as e:
            print(f"  ERROR: {t.__name__}: {type(e).__name__}: {e}")
            fails += 1
    print("=" * 70)
    print(f" {len(tests) - fails}/{len(tests)} cyclic degradation invariants held")
    print("=" * 70)
    return fails


if __name__ == "__main__":
    sys.exit(main())
