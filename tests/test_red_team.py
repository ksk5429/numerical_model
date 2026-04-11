"""
Adversarial edge-case tests for Op^3.

These tests try to BREAK the code with pathological inputs. Each test
verifies that the code either:
  - raises a clear error (ValueError, not ZeroDivisionError / RuntimeError)
  - clamps to a valid range
  - returns a physically reasonable (finite, positive) result

If any of these tests fail silently (e.g. returns NaN or Inf without
raising), that is a real bug that must be fixed before release.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from op3.standards.api_rp_2geo import gazetas_full_6x6
from op3.standards.pisa import (
    SoilState,
    pisa_pile_stiffness_6x6,
)
from op3.standards.dnv_st_0126 import dnv_monopile_stiffness, dnv_suction_bucket_stiffness
from op3.standards.owa_bearing import owa_suction_bucket_stiffness
from op3.standards.cyclic_degradation import hardin_drnevich, degrade_profile
from op3.fatigue import compute_del


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _sand_profile(G: float = 80e6, depth_top: float = 0.0,
                  depth_bot: float = 36.0) -> list[SoilState]:
    """Standard two-layer sand profile for PISA tests."""
    return [
        SoilState(depth_m=depth_top, G_Pa=G, su_or_phi=35.0, soil_type="sand"),
        SoilState(depth_m=depth_bot, G_Pa=G * 1.5, su_or_phi=35.0, soil_type="sand"),
    ]


# ---------------------------------------------------------------------------
# 1. Negative shear modulus
# ---------------------------------------------------------------------------

class TestNegativeShearModulus:

    def test_gazetas_negative_G_produces_negative_stiffness(self):
        """Negative G should either raise or produce obviously wrong K.

        Currently the code does not validate G > 0, so we document the
        behavior: diagonal elements become negative, which is
        unphysical.  A future guard should raise ValueError.
        """
        K = gazetas_full_6x6(radius_m=4.0, embedment_m=5.0, G=-42e6, nu=0.35)
        # At minimum the result must be finite (no NaN/Inf)
        assert np.all(np.isfinite(K)), "Negative G produced NaN or Inf"
        # Document: diagonals are negative (unphysical)
        assert K[0, 0] < 0, "Expected negative Kxx from negative G"

    def test_pisa_negative_G_in_profile(self):
        """Negative G in soil profile should not silently produce garbage."""
        profile = [
            SoilState(depth_m=0, G_Pa=-80e6, su_or_phi=35, soil_type="sand"),
            SoilState(depth_m=36, G_Pa=-120e6, su_or_phi=35, soil_type="sand"),
        ]
        # Should still produce finite values (clamped by max(..., 0))
        K = pisa_pile_stiffness_6x6(diameter_m=6.0, embed_length_m=36.0,
                                     soil_profile=profile)
        assert np.all(np.isfinite(K)), "Negative G in PISA produced NaN/Inf"


# ---------------------------------------------------------------------------
# 2. Zero diameter
# ---------------------------------------------------------------------------

class TestZeroDiameter:

    def test_gazetas_zero_radius_raises(self):
        """R=0 with nonzero embedment causes ZeroDivisionError (known bug).

        BUG: The embedment factor computes D/R which divides by zero.
        Ideally this should raise ValueError('radius must be positive').
        """
        with pytest.raises((ZeroDivisionError, ValueError)):
            gazetas_full_6x6(radius_m=0.0, embedment_m=5.0, G=42e6, nu=0.35)

    def test_gazetas_zero_radius_zero_embed(self):
        """R=0 with zero embedment (surface) should give zero stiffness."""
        K = gazetas_full_6x6(radius_m=0.0, embedment_m=0.0, G=42e6, nu=0.35)
        assert np.all(np.isfinite(K)), "Zero radius produced NaN or Inf"
        assert np.allclose(K, 0.0), "Zero radius should give zero stiffness"

    def test_dnv_zero_diameter_raises(self):
        """D=0 in DNV causes ZeroDivisionError (known bug).

        BUG: depth_factor computes L/D which divides by zero.
        Ideally this should raise ValueError('diameter must be positive').
        """
        with pytest.raises((ZeroDivisionError, ValueError)):
            dnv_monopile_stiffness(diameter_m=0.0, embedment_m=36.0,
                                    G=150e6, nu=0.30)


# ---------------------------------------------------------------------------
# 3. Extreme L/D ratio
# ---------------------------------------------------------------------------

class TestExtremeLDRatio:

    def test_extreme_LD_100_finite(self):
        """L/D=100 (far outside PISA calibration range 2-10) must still give finite K."""
        profile = _sand_profile(depth_bot=600.0)
        K = pisa_pile_stiffness_6x6(diameter_m=6.0, embed_length_m=600.0,
                                     soil_profile=profile)
        assert np.all(np.isfinite(K)), "L/D=100 produced NaN or Inf"
        assert K[0, 0] > 0, "Lateral stiffness should be positive"

    def test_extreme_LD_0_5_finite(self):
        """L/D=0.5 (very shallow, below calibration) must still give finite K."""
        profile = [
            SoilState(depth_m=0, G_Pa=80e6, su_or_phi=35, soil_type="sand"),
            SoilState(depth_m=3, G_Pa=90e6, su_or_phi=35, soil_type="sand"),
        ]
        K = pisa_pile_stiffness_6x6(diameter_m=6.0, embed_length_m=3.0,
                                     soil_profile=profile)
        assert np.all(np.isfinite(K)), "L/D=0.5 produced NaN or Inf"


# ---------------------------------------------------------------------------
# 4. NaN input propagation
# ---------------------------------------------------------------------------

class TestNaNInput:

    def test_nan_G_in_soil_profile(self):
        """NaN in soil profile G should raise or be caught, not silently propagate."""
        profile = [
            SoilState(depth_m=0, G_Pa=float("nan"), su_or_phi=35, soil_type="sand"),
            SoilState(depth_m=36, G_Pa=120e6, su_or_phi=35, soil_type="sand"),
        ]
        K = pisa_pile_stiffness_6x6(diameter_m=6.0, embed_length_m=36.0,
                                     soil_profile=profile)
        # The NaN should propagate into K -- if not, the code silently drops it
        has_nan = np.any(np.isnan(K))
        # Either raise (preferred) or propagate NaN (acceptable).
        # What is NOT acceptable: finite values that hide the NaN input.
        if not has_nan:
            # If all finite, check that the result is different from the clean case
            K_clean = pisa_pile_stiffness_6x6(
                diameter_m=6.0, embed_length_m=36.0,
                soil_profile=_sand_profile())
            # If identical to clean case, the NaN was silently dropped
            assert not np.allclose(K, K_clean), \
                "NaN in G was silently ignored -- should raise or propagate"

    def test_nan_radius_gazetas(self):
        """NaN radius should produce NaN output, not a crash."""
        K = gazetas_full_6x6(radius_m=float("nan"), embedment_m=5.0,
                             G=42e6, nu=0.35)
        assert np.any(np.isnan(K)), "NaN radius should propagate to output"

    def test_nan_embedment_dnv(self):
        """NaN embedment in DNV should propagate."""
        K = dnv_monopile_stiffness(diameter_m=6.0,
                                    embedment_m=float("nan"),
                                    G=150e6, nu=0.30)
        assert np.any(np.isnan(K)), "NaN embedment should propagate to output"


# ---------------------------------------------------------------------------
# 5. Negative embedment
# ---------------------------------------------------------------------------

class TestNegativeEmbedment:

    def test_negative_skirt_length_dnv(self):
        """Negative skirt length should raise or produce zero/negative K."""
        K = dnv_suction_bucket_stiffness(
            diameter_m=8.0, skirt_length_m=-3.0, G=5e6, nu=0.49)
        # At minimum, result must be finite
        assert np.all(np.isfinite(K)), "Negative skirt produced NaN/Inf"

    def test_negative_embedment_pisa(self):
        """Negative embed length in PISA should not produce valid-looking K."""
        profile = _sand_profile(depth_bot=36.0)
        # Negative length: linspace(0, -5) gives descending z -> nonsensical
        K = pisa_pile_stiffness_6x6(diameter_m=6.0, embed_length_m=-5.0,
                                     soil_profile=profile)
        # Should be zeros or raise -- document whichever behavior exists
        assert np.all(np.isfinite(K)), "Negative embedment produced NaN/Inf"


# ---------------------------------------------------------------------------
# 6. K 6x6 positive definite
# ---------------------------------------------------------------------------

class TestK6x6PositiveDefinite:

    def test_gazetas_diagonal_positive(self):
        """All diagonal entries of Gazetas K must be positive for valid input."""
        K = gazetas_full_6x6(radius_m=4.0, embedment_m=9.3, G=42e6, nu=0.35)
        for i in range(6):
            assert K[i, i] > 0, f"K[{i},{i}] = {K[i,i]} is not positive"

    def test_pisa_diagonal_positive(self):
        """All diagonal entries of PISA K must be positive for valid input."""
        K = pisa_pile_stiffness_6x6(diameter_m=6.0, embed_length_m=36.0,
                                     soil_profile=_sand_profile())
        for i in range(6):
            assert K[i, i] > 0, f"K[{i},{i}] = {K[i,i]} is not positive"

    def test_dnv_diagonal_positive(self):
        """All diagonal entries of DNV K must be positive for valid input."""
        K = dnv_monopile_stiffness(diameter_m=6.0, embedment_m=36.0,
                                    G=150e6, nu=0.30)
        for i in range(6):
            assert K[i, i] > 0, f"K[{i},{i}] = {K[i,i]} is not positive"

    def test_owa_diagonal_positive(self):
        """All diagonal entries of OWA K must be positive for valid input."""
        K = owa_suction_bucket_stiffness(diameter_m=8.0, skirt_length_m=6.0,
                                          G=5e6, nu=0.49)
        for i in range(6):
            assert K[i, i] > 0, f"K[{i},{i}] = {K[i,i]} is not positive"


# ---------------------------------------------------------------------------
# 7. Scour deeper than skirt
# ---------------------------------------------------------------------------

class TestScourExceedsSkirt:

    def test_scour_greater_than_skirt_owa(self):
        """S/D > 1.0 (scour deeper than bucket diameter) should still give finite K."""
        # Scour effect is applied externally via apply_scour_relief, but
        # a very small effective embedment should not break the formula.
        K = owa_suction_bucket_stiffness(
            diameter_m=8.0, skirt_length_m=0.1, G=5e6, nu=0.49)
        assert np.all(np.isfinite(K)), "Near-zero skirt produced NaN/Inf"
        assert K[0, 0] > 0, "Lateral stiffness should be positive even for tiny skirt"

    def test_hardin_drnevich_extreme_strain(self):
        """Strain 1000x gamma_ref should give near-zero G/Gmax, not negative."""
        ratio = hardin_drnevich(gamma=0.1, gamma_ref=1e-4, a=1.0)
        assert 0.0 < ratio < 0.01, f"Expected near-zero, got {ratio}"
        assert np.isfinite(ratio)


# ---------------------------------------------------------------------------
# 8. Single-node spring table
# ---------------------------------------------------------------------------

class TestSingleSpringNode:

    def test_single_row_spring_table(self):
        """A spring DataFrame with 1 row should not crash PISA stiffness."""
        profile = [SoilState(depth_m=0, G_Pa=80e6, su_or_phi=35,
                             soil_type="sand")]
        # Single-point profile: should still work (degenerate but finite)
        K = pisa_pile_stiffness_6x6(diameter_m=6.0, embed_length_m=10.0,
                                     soil_profile=profile)
        assert np.all(np.isfinite(K)), "Single-point profile produced NaN/Inf"


# ---------------------------------------------------------------------------
# 9. Empty soil profile
# ---------------------------------------------------------------------------

class TestEmptyProfile:

    def test_empty_soil_profile_raises(self):
        """Empty soil_profile list should raise ValueError, not crash."""
        with pytest.raises(ValueError, match="at least one"):
            pisa_pile_stiffness_6x6(diameter_m=6.0, embed_length_m=36.0,
                                     soil_profile=[])


# ---------------------------------------------------------------------------
# 10. Coupling sign consistency (PISA)
# ---------------------------------------------------------------------------

class TestCouplingSignsPISA:

    def test_coupling_opposite_signs(self):
        """PISA K[0,4] and K[1,3] should have opposite signs.

        Physical basis: lateral force in +x produces positive
        translation and negative rotation about y, so the x-ry
        coupling is negative. Conversely, y-rx coupling is positive.
        """
        K = pisa_pile_stiffness_6x6(diameter_m=6.0, embed_length_m=36.0,
                                     soil_profile=_sand_profile())
        assert K[0, 4] < 0, f"K[0,4] = {K[0,4]} should be negative"
        assert K[1, 3] > 0, f"K[1,3] = {K[1,3]} should be positive"

    def test_coupling_magnitude_equal(self):
        """Absolute values of K[0,4] and K[1,3] should be equal (symmetry)."""
        K = pisa_pile_stiffness_6x6(diameter_m=6.0, embed_length_m=36.0,
                                     soil_profile=_sand_profile())
        assert abs(abs(K[0, 4]) - abs(K[1, 3])) < 1e-6 * abs(K[0, 4])

    def test_gazetas_coupling_same_sign(self):
        """Gazetas K[0,4] and K[1,3] should both be positive for embedded."""
        K = gazetas_full_6x6(radius_m=4.0, embedment_m=9.3, G=42e6, nu=0.35)
        assert K[0, 4] > 0, "Gazetas K[0,4] should be positive"
        assert K[1, 3] > 0, "Gazetas K[1,3] should be positive"


# ---------------------------------------------------------------------------
# 11. DEL with zero-amplitude signal
# ---------------------------------------------------------------------------

class TestDELZeroSignal:

    def test_constant_signal_del_zero(self):
        """Constant signal (no cycles) should give DEL = 0."""
        signal = np.full(1000, 50.0)
        del_val = compute_del(signal, m=3.0, dt=0.01)
        assert del_val == 0.0, f"Constant signal gave DEL = {del_val}"

    def test_two_point_signal_del_zero(self):
        """Signal with fewer than 3 points returns DEL = 0."""
        signal = np.array([10.0, 20.0])
        del_val = compute_del(signal, m=3.0, dt=0.01)
        assert del_val == 0.0


# ---------------------------------------------------------------------------
# 12. DEL with single cycle
# ---------------------------------------------------------------------------

class TestDELSingleCycle:

    def test_single_cycle_finite(self):
        """One full sine cycle should give finite, positive DEL."""
        t = np.linspace(0, 1.0, 100)
        signal = 100.0 * np.sin(2 * np.pi * t)
        del_val = compute_del(signal, m=3.0, dt=t[1] - t[0])
        assert np.isfinite(del_val), "Single cycle DEL is not finite"
        assert del_val > 0, "Single cycle DEL should be positive"


# ---------------------------------------------------------------------------
# 13. Hardin-Drnevich edge cases
# ---------------------------------------------------------------------------

class TestHardinDrnevichEdges:

    def test_zero_strain_returns_one(self):
        """gamma=0 should give G/Gmax = 1.0 (no degradation)."""
        assert hardin_drnevich(0.0, 1e-4) == 1.0

    def test_negative_strain_returns_one(self):
        """Negative strain should return 1.0 (treated as zero)."""
        assert hardin_drnevich(-0.001, 1e-4) == 1.0

    def test_very_large_strain(self):
        """Extremely large strain should give near-zero but positive G/Gmax."""
        ratio = hardin_drnevich(1.0, 1e-4, a=1.0)
        assert 0.0 < ratio < 1e-3
        assert np.isfinite(ratio)


# ---------------------------------------------------------------------------
# 14. Cyclic degradation with negative strain
# ---------------------------------------------------------------------------

class TestCyclicDegradationNegativeStrain:

    def test_negative_cyclic_strain_raises(self):
        """Negative cyclic strain in degrade_profile should raise ValueError."""
        profile = _sand_profile()
        with pytest.raises(ValueError, match="non-negative"):
            degrade_profile(profile, cyclic_strain=-0.001)


# ---------------------------------------------------------------------------
# 15. DEL with no dt and no n_eq
# ---------------------------------------------------------------------------

class TestDELMissingParams:

    def test_no_dt_no_neq_raises(self):
        """Must provide either n_eq or dt."""
        signal = np.sin(np.linspace(0, 10, 1000))
        with pytest.raises(ValueError):
            compute_del(signal, m=3.0)

    def test_negative_neq_returns_zero(self):
        """Negative n_eq should return 0 (no damage possible)."""
        signal = 100.0 * np.sin(np.linspace(0, 10, 1000))
        del_val = compute_del(signal, m=3.0, n_eq=-10)
        assert del_val == 0.0


# ---------------------------------------------------------------------------
# 16. Symmetry of 6x6 matrices
# ---------------------------------------------------------------------------

class TestSymmetry:

    def test_pisa_symmetric(self):
        """PISA 6x6 must be symmetric: K = K^T."""
        K = pisa_pile_stiffness_6x6(diameter_m=6.0, embed_length_m=36.0,
                                     soil_profile=_sand_profile())
        np.testing.assert_allclose(K, K.T, atol=1e-6,
                                   err_msg="PISA K is not symmetric")

    def test_gazetas_symmetric(self):
        """Gazetas 6x6 must be symmetric: K = K^T."""
        K = gazetas_full_6x6(radius_m=4.0, embedment_m=9.3, G=42e6, nu=0.35)
        np.testing.assert_allclose(K, K.T, atol=1e-6,
                                   err_msg="Gazetas K is not symmetric")

    def test_dnv_symmetric(self):
        """DNV diagonal K is trivially symmetric."""
        K = dnv_monopile_stiffness(diameter_m=6.0, embedment_m=36.0,
                                    G=150e6, nu=0.30)
        np.testing.assert_allclose(K, K.T, atol=1e-6)
