"""
HSsmall wrapper V&V (Phase 3 / Task 3.3 tests).

Verifies:
  1. G_0(z) recovers G_0_ref at depth such that sigma_3' = p_ref
  2. G_0 power law: doubling sigma_3' multiplies G by 2 ** m
  3. Clay layer is depth-independent in G when phi = 0 and c = 0
  4. CSV round-trip: write a synthetic OptumGX-style CSV, parse it,
     and check that all numeric values survive
  5. hssmall_to_pisa produces a SoilState list ordered by depth
  6. hssmall_to_pisa -> pisa_pile_stiffness_6x6 returns a valid 6x6
  7. End-to-end pipeline: HSsmall layers -> PISA -> 6x6 K is symmetric
     and positive-definite
  8. Aliased column names are resolved by the loader

Run:
    python tests/test_hssmall.py
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

import numpy as np

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from op3.standards.hssmall import (  # noqa: E402
    HSsmallParams,
    hssmall_G_at_depth,
    hssmall_to_pisa,
    load_hssmall_profile,
    _effective_horizontal_stress,
)
from op3.standards.pisa import pisa_pile_stiffness_6x6  # noqa: E402


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_G_at_reference_depth():
    """At a depth where sigma_3' equals p_ref, G_0(z) must equal G_0_ref."""
    p_ref = 1.0e5  # Pa
    # Solve sigma_3 = K0 * gamma * z = p_ref => z = p_ref / (K0 * gamma)
    z = p_ref / (0.5 * 10.0e3)
    pars = HSsmallParams(
        layer_name="test", z_top_m=0, z_bot_m=100,
        soil_type="sand", G0_ref_Pa=1.0e8, m_exp=0.5, phi_deg=35.0,
    )
    G = hssmall_G_at_depth(pars, z)
    print(f"  [3.3.1] G at sigma3=p_ref: G={G:.3e} ref={pars.G0_ref_Pa:.3e}")
    assert abs(G - pars.G0_ref_Pa) / pars.G0_ref_Pa < 0.001


def test_power_law_doubling():
    """Doubling effective stress multiplies G by 2 ** m (sand, c = 0)."""
    pars = HSsmallParams(
        layer_name="t", z_top_m=0, z_bot_m=100,
        soil_type="sand", G0_ref_Pa=1.0e8, m_exp=0.5,
        phi_deg=0.0, c_Pa=0.0,   # zero shift -> pure stress power law
    )
    z1 = 5.0
    z2 = 10.0
    G1 = hssmall_G_at_depth(pars, z1)
    G2 = hssmall_G_at_depth(pars, z2)
    ratio = G2 / G1
    expected = 2.0 ** pars.m_exp
    print(f"  [3.3.2] G(2z)/G(z) = {ratio:.4f}  expected 2^m = {expected:.4f}")
    assert abs(ratio - expected) / expected < 1e-3


def test_clay_depth_independent():
    pars = HSsmallParams(
        layer_name="clay", z_top_m=0, z_bot_m=20,
        soil_type="clay", G0_ref_Pa=5.0e7, su_Pa=100.0e3,
        phi_deg=0.0, c_Pa=0.0,
    )
    G_top = hssmall_G_at_depth(pars, 1.0)
    G_bot = hssmall_G_at_depth(pars, 20.0)
    print(f"  [3.3.3] clay G_top={G_top:.3e}, G_bot={G_bot:.3e}")
    assert G_top == G_bot == pars.G0_ref_Pa


def test_csv_round_trip():
    csv = (
        "layer_name,z_top_m,z_bot_m,soil_type,G0_ref_Pa,m,phi_deg\n"
        "Sand1,0.0,10.0,sand,5.0e7,0.5,33\n"
        "Sand2,10.0,30.0,sand,1.2e8,0.5,36\n"
    )
    with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
        f.write(csv)
        path = f.name
    layers = load_hssmall_profile(path)
    print(f"  [3.3.4] parsed {len(layers)} layers")
    assert len(layers) == 2
    assert layers[0].soil_type == "sand"
    assert layers[1].G0_ref_Pa == 1.2e8
    assert layers[1].phi_deg == 36
    Path(path).unlink()


def test_to_pisa_ordering():
    layers = [
        HSsmallParams("L1", 0.0, 10.0, "sand", 5.0e7, m_exp=0.5, phi_deg=33),
        HSsmallParams("L2", 10.0, 30.0, "sand", 1.2e8, m_exp=0.5, phi_deg=36),
    ]
    profile = hssmall_to_pisa(layers, n_points_per_layer=3)
    depths = [s.depth_m for s in profile]
    print(f"  [3.3.5] HSsmall->PISA depths: {[round(d,1) for d in depths]}")
    assert depths == sorted(depths)
    assert depths[0] == 0.0
    assert depths[-1] == 30.0


def test_end_to_end_to_K6x6():
    layers = [
        HSsmallParams("L1", 0.0, 15.0, "sand", 6.0e7, m_exp=0.5, phi_deg=34),
        HSsmallParams("L2", 15.0, 35.0, "sand", 1.4e8, m_exp=0.5, phi_deg=37),
    ]
    profile = hssmall_to_pisa(layers, n_points_per_layer=4)
    K = pisa_pile_stiffness_6x6(diameter_m=8.0, embed_length_m=30.0,
                                soil_profile=profile)
    eigs = np.linalg.eigvalsh(0.5 * (K + K.T))
    print(f"  [3.3.7] HSsmall->PISA->K: Kxx={K[0,0]:.3e}, min eig={eigs.min():.3e}")
    assert np.allclose(K, K.T)
    assert eigs.min() > 0


def test_alias_resolution():
    csv = (
        "layer,top_m,bottom_m,material,g0_ref,m,friction_angle\n"
        "L1,0,10,sand,5e7,0.5,32\n"
    )
    with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
        f.write(csv)
        path = f.name
    layers = load_hssmall_profile(path)
    print(f"  [3.3.8] alias load: layers={len(layers)}, phi={layers[0].phi_deg}")
    assert len(layers) == 1
    assert layers[0].phi_deg == 32
    Path(path).unlink()


def test_effective_stress_monotone():
    s1 = _effective_horizontal_stress(5.0)
    s2 = _effective_horizontal_stress(10.0)
    print(f"  [3.3.9] sigma3 at z=5: {s1:.3e}, at z=10: {s2:.3e}")
    assert s2 > s1
    assert abs(s2 / s1 - 2.0) < 1e-6


# ---------------------------------------------------------------------------
# Standalone runner
# ---------------------------------------------------------------------------

def main():
    print()
    print("=" * 70)
    print(" Op3 HSsmall wrapper V&V -- Task 3.3")
    print("=" * 70)
    tests = [
        test_G_at_reference_depth,
        test_power_law_doubling,
        test_clay_depth_independent,
        test_csv_round_trip,
        test_to_pisa_ordering,
        test_end_to_end_to_K6x6,
        test_alias_resolution,
        test_effective_stress_monotone,
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
    print(f" {len(tests) - fails}/{len(tests)} HSsmall invariants held")
    print("=" * 70)
    return fails


if __name__ == "__main__":
    sys.exit(main())
