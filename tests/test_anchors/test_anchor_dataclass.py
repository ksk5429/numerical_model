"""
Tests for op3.anchors.anchor -- SuctionAnchor / UndrainedClayProfile / MooringLoad.

Covers geometry properties, derived areas, validation, and load decomposition.
"""
from __future__ import annotations

import numpy as np
import pytest

from op3.anchors import SuctionAnchor, UndrainedClayProfile, MooringLoad


# ---------------------------------------------------------------------------
# SuctionAnchor
# ---------------------------------------------------------------------------

class TestSuctionAnchorGeometry:

    def test_aspect_ratio(self):
        a = SuctionAnchor(diameter_m=5.0, skirt_length_m=15.0)
        assert a.aspect_ratio == pytest.approx(3.0)

    def test_inner_diameter(self):
        a = SuctionAnchor(diameter_m=5.0, skirt_length_m=15.0,
                          wall_thickness_mm=30.0)
        # D_i = D - 2 * t  = 5.0 - 0.060 = 4.940
        assert a.inner_diameter_m == pytest.approx(4.940)

    def test_outer_skirt_area(self):
        a = SuctionAnchor(diameter_m=5.0, skirt_length_m=15.0)
        expected = np.pi * 5.0 * 15.0
        assert a.outer_skirt_area_m2 == pytest.approx(expected)

    def test_lid_area(self):
        a = SuctionAnchor(diameter_m=5.0, skirt_length_m=15.0)
        expected = np.pi / 4.0 * 5.0 ** 2
        assert a.lid_area_m2 == pytest.approx(expected)

    def test_annulus_area_equals_steel_ring(self):
        a = SuctionAnchor(diameter_m=5.0, skirt_length_m=15.0,
                          wall_thickness_mm=30.0)
        d_i = 5.0 - 0.06
        expected = np.pi / 4.0 * (5.0 ** 2 - d_i ** 2)
        assert a.annulus_area_m2 == pytest.approx(expected)

    def test_lid_area_equals_inner_plus_annulus(self):
        a = SuctionAnchor(diameter_m=5.0, skirt_length_m=15.0,
                          wall_thickness_mm=30.0)
        assert a.lid_area_m2 == pytest.approx(
            a.lid_inner_area_m2 + a.annulus_area_m2
        )


class TestSuctionAnchorValidation:

    @pytest.mark.parametrize("bad_D", [-1.0, 0.0])
    def test_bad_diameter_raises(self, bad_D):
        with pytest.raises(ValueError, match="diameter_m"):
            SuctionAnchor(diameter_m=bad_D, skirt_length_m=10.0)

    @pytest.mark.parametrize("bad_L", [-1.0, 0.0])
    def test_bad_skirt_length_raises(self, bad_L):
        with pytest.raises(ValueError, match="skirt_length_m"):
            SuctionAnchor(diameter_m=5.0, skirt_length_m=bad_L)

    def test_padeye_out_of_range_raises(self):
        with pytest.raises(ValueError, match="padeye_depth_m"):
            SuctionAnchor(diameter_m=5.0, skirt_length_m=15.0,
                          padeye_depth_m=20.0)  # below skirt tip

    def test_wall_too_thick_raises(self):
        with pytest.raises(ValueError, match="wall_thickness_mm"):
            SuctionAnchor(diameter_m=0.1, skirt_length_m=1.0,
                          wall_thickness_mm=60.0)  # 60 mm > 50 mm radius


# ---------------------------------------------------------------------------
# UndrainedClayProfile
# ---------------------------------------------------------------------------

class TestUndrainedClayProfile:

    def test_su_at_mudline(self):
        s = UndrainedClayProfile(su_mudline_kPa=5.0,
                                 su_gradient_kPa_per_m=1.5)
        assert s.su_at_depth(0.0) == pytest.approx(5.0)

    def test_su_linear(self):
        s = UndrainedClayProfile(su_mudline_kPa=5.0,
                                 su_gradient_kPa_per_m=1.5)
        # at z=10 m: 5 + 1.5*10 = 20
        assert s.su_at_depth(10.0) == pytest.approx(20.0)

    def test_su_remoulded(self):
        s = UndrainedClayProfile(su_mudline_kPa=5.0,
                                 su_gradient_kPa_per_m=1.5,
                                 sensitivity=2.5)
        assert s.su_remoulded_at_depth(10.0) == pytest.approx(20.0 / 2.5)

    def test_su_average_linear(self):
        s = UndrainedClayProfile(su_mudline_kPa=5.0,
                                 su_gradient_kPa_per_m=1.5)
        # avg over 0..10: midpoint = 5 + 0.5 * 1.5 * 10 = 12.5
        assert s.su_average_to_depth(10.0) == pytest.approx(12.5)

    def test_su_vectorized(self):
        s = UndrainedClayProfile(su_mudline_kPa=5.0,
                                 su_gradient_kPa_per_m=1.5)
        z = np.array([0.0, 5.0, 10.0])
        expected = np.array([5.0, 12.5, 20.0])
        np.testing.assert_allclose(s.su_at_depth(z), expected)

    def test_negative_su_raises(self):
        with pytest.raises(ValueError):
            UndrainedClayProfile(su_mudline_kPa=-1.0,
                                 su_gradient_kPa_per_m=1.5)


# ---------------------------------------------------------------------------
# MooringLoad
# ---------------------------------------------------------------------------

class TestMooringLoad:

    def test_pure_horizontal(self):
        m = MooringLoad(tension_kN=1000.0, angle_at_padeye_deg=0.0)
        assert m.horizontal_kN == pytest.approx(1000.0)
        assert m.vertical_kN == pytest.approx(0.0, abs=1e-9)

    def test_pure_vertical(self):
        m = MooringLoad(tension_kN=1000.0, angle_at_padeye_deg=90.0)
        assert m.horizontal_kN == pytest.approx(0.0, abs=1e-9)
        assert m.vertical_kN == pytest.approx(1000.0)

    def test_45deg(self):
        m = MooringLoad(tension_kN=1000.0, angle_at_padeye_deg=45.0)
        assert m.horizontal_kN == pytest.approx(1000.0 / np.sqrt(2))
        assert m.vertical_kN == pytest.approx(1000.0 / np.sqrt(2))

    def test_bad_angle_raises(self):
        with pytest.raises(ValueError):
            MooringLoad(tension_kN=100.0, angle_at_padeye_deg=120.0)
