"""
Snapshot regression gates for Op^3 stiffness formulas.

WARNING: These tests are INTENTIONALLY FRAGILE. They capture the exact
numerical output of each formula at a specific set of inputs. If a
formula changes (coefficient update, sign fix, refactoring bug), these
tests WILL break. That is their purpose.

When a test breaks:
  1. Verify the formula change is intentional and correct.
  2. Re-compute the snapshot value using the instructions in the
     docstring of the failing test.
  3. Update the expected value in this file.
  4. Commit with a message explaining WHY the snapshot changed.

Tolerance: 1% relative error (rtol = 0.01). This catches real formula
changes while absorbing minor floating-point platform differences.

Snapshot values were computed on 2026-04-10 using the Op^3 v1.0.0-rc1
codebase on Windows 10 / Python 3.11 / NumPy 1.26.
"""
from __future__ import annotations

import numpy as np
import pytest

from op3.standards.api_rp_2geo import gazetas_full_6x6
from op3.standards.pisa import (
    SoilState,
    pisa_pile_stiffness_6x6,
)
from op3.standards.dnv_st_0126 import (
    dnv_monopile_stiffness,
    dnv_suction_bucket_stiffness,
)
from op3.standards.owa_bearing import owa_suction_bucket_stiffness
from op3.standards.cyclic_degradation import hardin_drnevich
from op3.fatigue import compute_del


RTOL = 0.01  # 1% relative tolerance


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _oc3_sand_profile() -> list[SoilState]:
    """OC3-like sand profile for PISA: D=6m, L=36m."""
    return [
        SoilState(depth_m=0.0, G_Pa=80e6, su_or_phi=35.0, soil_type="sand"),
        SoilState(depth_m=36.0, G_Pa=120e6, su_or_phi=35.0, soil_type="sand"),
    ]


# ---------------------------------------------------------------------------
# 1. Gazetas full 6x6
# ---------------------------------------------------------------------------

class TestGazetasSnapshot:
    """Regression gate: Gazetas (1991) full 6x6 for R=4m, D=9.3m."""

    K_REF = gazetas_full_6x6.__name__  # just for documentation

    def test_Kxx(self):
        K = gazetas_full_6x6(radius_m=4.0, embedment_m=9.3, G=42e6, nu=0.35)
        assert abs(K[0, 0] - 1.732323e+09) / 1.732323e+09 < RTOL

    def test_Kzz(self):
        K = gazetas_full_6x6(radius_m=4.0, embedment_m=9.3, G=42e6, nu=0.35)
        assert abs(K[2, 2] - 2.331840e+09) / 2.331840e+09 < RTOL

    def test_Krxx(self):
        K = gazetas_full_6x6(radius_m=4.0, embedment_m=9.3, G=42e6, nu=0.35)
        assert abs(K[3, 3] - 5.056126e+10) / 5.056126e+10 < RTOL

    def test_Krzz(self):
        K = gazetas_full_6x6(radius_m=4.0, embedment_m=9.3, G=42e6, nu=0.35)
        assert abs(K[5, 5] - 4.100096e+10) / 4.100096e+10 < RTOL

    def test_coupling_K04(self):
        K = gazetas_full_6x6(radius_m=4.0, embedment_m=9.3, G=42e6, nu=0.35)
        assert abs(K[0, 4] - 5.370202e+09) / 5.370202e+09 < RTOL


# ---------------------------------------------------------------------------
# 2. PISA 6x6 for OC3 monopile in sand
# ---------------------------------------------------------------------------

class TestPISASnapshot:
    """Regression gate: PISA K for D=6m, L=36m in Dunkirk sand."""

    def test_Kxx(self):
        K = pisa_pile_stiffness_6x6(diameter_m=6.0, embed_length_m=36.0,
                                     soil_profile=_oc3_sand_profile())
        assert abs(K[0, 0] - 2.253623e+10) / 2.253623e+10 < RTOL

    def test_Krxrx(self):
        K = pisa_pile_stiffness_6x6(diameter_m=6.0, embed_length_m=36.0,
                                     soil_profile=_oc3_sand_profile())
        assert abs(K[3, 3] - 1.177395e+13) / 1.177395e+13 < RTOL

    def test_Kzz(self):
        K = pisa_pile_stiffness_6x6(diameter_m=6.0, embed_length_m=36.0,
                                     soil_profile=_oc3_sand_profile())
        assert abs(K[2, 2] - 1.198274e+10) / 1.198274e+10 < RTOL

    def test_coupling_K04(self):
        """K[0,4] should be negative (x-ry coupling convention)."""
        K = pisa_pile_stiffness_6x6(diameter_m=6.0, embed_length_m=36.0,
                                     soil_profile=_oc3_sand_profile())
        assert abs(K[0, 4] - (-3.937393e+11)) / 3.937393e+11 < RTOL

    def test_coupling_K13(self):
        """K[1,3] should be positive (y-rx coupling)."""
        K = pisa_pile_stiffness_6x6(diameter_m=6.0, embed_length_m=36.0,
                                     soil_profile=_oc3_sand_profile())
        assert abs(K[1, 3] - 3.937393e+11) / 3.937393e+11 < RTOL


# ---------------------------------------------------------------------------
# 3. DNV monopile
# ---------------------------------------------------------------------------

class TestDNVMonopileSnapshot:
    """Regression gate: DNV-ST-0126 monopile for D=6m, L=36m in dense sand."""

    def test_Kxx(self):
        K = dnv_monopile_stiffness(diameter_m=6.0, embedment_m=36.0,
                                    G=150e6, nu=0.30)
        assert abs(K[0, 0] - 6.352749e+09) / 6.352749e+09 < RTOL

    def test_Kzz(self):
        K = dnv_monopile_stiffness(diameter_m=6.0, embedment_m=36.0,
                                    G=150e6, nu=0.30)
        assert abs(K[2, 2] - 1.748571e+10) / 1.748571e+10 < RTOL

    def test_Krxx(self):
        K = dnv_monopile_stiffness(diameter_m=6.0, embedment_m=36.0,
                                    G=150e6, nu=0.30)
        assert abs(K[3, 3] - 2.005714e+11) / 2.005714e+11 < RTOL


# ---------------------------------------------------------------------------
# 4. OWA suction bucket
# ---------------------------------------------------------------------------

class TestOWASnapshot:
    """Regression gate: OWA suction bucket D=8m, L=6m in soft clay."""

    def test_Kxx(self):
        K = owa_suction_bucket_stiffness(diameter_m=8.0, skirt_length_m=6.0,
                                          G=5e6, nu=0.49)
        assert abs(K[0, 0] - 5.098039e+08) / 5.098039e+08 < RTOL

    def test_Kzz(self):
        K = owa_suction_bucket_stiffness(diameter_m=8.0, skirt_length_m=6.0,
                                          G=5e6, nu=0.49)
        assert abs(K[2, 2] - 2.980392e+08) / 2.980392e+08 < RTOL

    def test_Krxx(self):
        K = owa_suction_bucket_stiffness(diameter_m=8.0, skirt_length_m=6.0,
                                          G=5e6, nu=0.49)
        assert abs(K[3, 3] - 5.312418e+09) / 5.312418e+09 < RTOL


# ---------------------------------------------------------------------------
# 5. DNV suction bucket
# ---------------------------------------------------------------------------

class TestDNVSuctionBucketSnapshot:
    """Regression gate: DNV suction bucket D=8m, L=6m in soft clay."""

    def test_Kxx(self):
        K = dnv_suction_bucket_stiffness(diameter_m=8.0, skirt_length_m=6.0,
                                          G=5e6, nu=0.49)
        assert abs(K[0, 0] - 1.882192e+08) / 1.882192e+08 < RTOL

    def test_Krxx(self):
        K = dnv_suction_bucket_stiffness(diameter_m=8.0, skirt_length_m=6.0,
                                          G=5e6, nu=0.49)
        assert abs(K[3, 3] - 4.968889e+09) / 4.968889e+09 < RTOL


# ---------------------------------------------------------------------------
# 6. Hardin-Drnevich at gamma_ref
# ---------------------------------------------------------------------------

class TestHardinDrnevichSnapshot:
    """Regression gate: G/Gmax = 0.5 at gamma = gamma_ref (by definition)."""

    def test_at_gamma_ref(self):
        ratio = hardin_drnevich(gamma=1e-4, gamma_ref=1e-4, a=1.0)
        assert abs(ratio - 0.5) / 0.5 < RTOL

    def test_at_half_gamma_ref(self):
        """G/Gmax at gamma = 0.5 * gamma_ref should be 2/3."""
        ratio = hardin_drnevich(gamma=0.5e-4, gamma_ref=1e-4, a=1.0)
        expected = 1.0 / (1.0 + 0.5)  # = 2/3
        assert abs(ratio - expected) / expected < RTOL

    def test_darendeli_exponent(self):
        """Darendeli (2001) form with a=0.92 at gamma_ref."""
        ratio = hardin_drnevich(gamma=1e-4, gamma_ref=1e-4, a=0.92)
        expected = 1.0 / (1.0 + 1.0 ** 0.92)  # = 0.5
        assert abs(ratio - expected) / expected < RTOL


# ---------------------------------------------------------------------------
# 7. Fatigue DEL for pure sine
# ---------------------------------------------------------------------------

class TestDELSineSnapshot:
    """Regression gate: DEL for 100-amplitude sine, m=3, 10 seconds."""

    def test_del_pure_sine(self):
        t = np.linspace(0, 10, 1000)
        signal = 100.0 * np.sin(2 * np.pi * t)
        del_val = compute_del(signal, m=3.0, dt=t[1] - t[0])
        assert abs(del_val - 197.434367) / 197.434367 < RTOL

    def test_del_double_amplitude(self):
        """Doubling amplitude should scale DEL by 2.0 (linear in amplitude)."""
        t = np.linspace(0, 10, 1000)
        del_1 = compute_del(100.0 * np.sin(2 * np.pi * t), m=3.0,
                            dt=t[1] - t[0])
        del_2 = compute_del(200.0 * np.sin(2 * np.pi * t), m=3.0,
                            dt=t[1] - t[0])
        ratio = del_2 / del_1
        assert abs(ratio - 2.0) / 2.0 < RTOL, \
            f"DEL amplitude scaling: expected 2.0, got {ratio:.4f}"


# ---------------------------------------------------------------------------
# 8. Cross-standard consistency (sanity bounds)
# ---------------------------------------------------------------------------

class TestCrossStandardBounds:
    """Regression gate: relative ordering between standards.

    These are NOT exact value checks but bounded ratios that should
    remain stable. If a formula change flips the ordering, something
    is wrong.
    """

    def test_pisa_stiffer_than_dnv_lateral(self):
        """For a long monopile (L/D=6), PISA lateral K should exceed DNV.

        PISA integrates depth-varying reactions while DNV uses a
        single-coefficient approximation, so PISA is generally stiffer
        for slender piles in competent sand.
        """
        K_pisa = pisa_pile_stiffness_6x6(
            diameter_m=6.0, embed_length_m=36.0,
            soil_profile=_oc3_sand_profile())
        K_dnv = dnv_monopile_stiffness(
            diameter_m=6.0, embedment_m=36.0, G=100e6, nu=0.30)
        assert K_pisa[0, 0] > K_dnv[0, 0], \
            "PISA should be stiffer than DNV for L/D=6 in sand"

    def test_owa_stiffer_than_dnv_bucket_lateral(self):
        """OWA lateral stiffness should exceed DNV for the same bucket.

        OWA uses the Houlsby-Byrne caisson formulation which includes
        a stronger embedment correction than the Gazetas-based DNV
        expression.
        """
        K_owa = owa_suction_bucket_stiffness(
            diameter_m=8.0, skirt_length_m=6.0, G=5e6, nu=0.49)
        K_dnv = dnv_suction_bucket_stiffness(
            diameter_m=8.0, skirt_length_m=6.0, G=5e6, nu=0.49)
        assert K_owa[0, 0] > K_dnv[0, 0], \
            "OWA should give higher lateral K than DNV for suction bucket"
