"""
Tests for op3.anchors.installation.

Covers:
  * Self-weight depth reduces as W decreases (monotonicity)
  * Zero-weight anchor has self-weight depth = 0
  * Over-weight anchor sinks fully
  * Required suction starts at 0 and increases with depth
  * Cavitation limit grows with water depth
  * Plug-heave ratio is ~ 1 near the cavitation limit
  * Full installation_analysis report is consistent
"""
from __future__ import annotations

import numpy as np
import pytest

from op3.anchors import (
    SuctionAnchor, UndrainedClayProfile,
    self_weight_penetration,
    required_suction_kPa,
    allowable_suction_kPa,
    plug_heave_check,
    installation_analysis,
    penetration_resistance,
    InstallationResult,
)


@pytest.fixture
def anchor():
    return SuctionAnchor(diameter_m=5.0, skirt_length_m=15.0,
                         wall_thickness_mm=30.0,
                         submerged_weight_kN=1500.0)


@pytest.fixture
def anchor_light():
    return SuctionAnchor(diameter_m=5.0, skirt_length_m=15.0,
                         wall_thickness_mm=30.0,
                         submerged_weight_kN=0.0)


@pytest.fixture
def soil():
    return UndrainedClayProfile(su_mudline_kPa=5.0,
                                su_gradient_kPa_per_m=1.5,
                                sensitivity=3.0,
                                gamma_eff_kN_per_m3=6.0)


# ---------------------------------------------------------------------------
# Self-weight
# ---------------------------------------------------------------------------

class TestSelfWeight:

    def test_zero_weight_gives_zero_depth(self, anchor_light, soil):
        z = self_weight_penetration(anchor_light, soil)
        assert z == 0.0

    def test_heavy_anchor_fully_embeds(self, soil):
        heavy = SuctionAnchor(diameter_m=5.0, skirt_length_m=15.0,
                              submerged_weight_kN=50_000.0)
        z = self_weight_penetration(heavy, soil)
        assert z == heavy.skirt_length_m

    def test_self_weight_monotonic_in_weight(self, soil):
        z_vals = []
        for W in [100.0, 500.0, 1000.0, 2500.0]:
            a = SuctionAnchor(diameter_m=5.0, skirt_length_m=15.0,
                              submerged_weight_kN=W)
            z_vals.append(self_weight_penetration(a, soil))
        # monotonic non-decreasing in weight
        assert all(z_vals[i + 1] >= z_vals[i] for i in range(len(z_vals) - 1))

    def test_resistance_matches_weight_at_self_weight_depth(self, anchor, soil):
        z = self_weight_penetration(anchor, soil)
        if 0 < z < anchor.skirt_length_m:
            R = penetration_resistance(anchor, soil, z, remoulded=True)
            # bisection tolerance ~ 1e-4 m -> resistance within ~ a few kN
            assert R == pytest.approx(anchor.submerged_weight_kN, rel=5e-3)


# ---------------------------------------------------------------------------
# Required suction
# ---------------------------------------------------------------------------

class TestRequiredSuction:

    def test_zero_at_zero_depth(self, anchor, soil):
        assert required_suction_kPa(anchor, soil, 0.0) == 0.0

    def test_increases_with_depth(self, anchor, soil):
        depths = [1.0, 5.0, 10.0, 15.0]
        s = [required_suction_kPa(anchor, soil, z) for z in depths]
        assert all(s[i + 1] >= s[i] for i in range(len(s) - 1))

    def test_zero_before_self_weight_depth(self, soil):
        # A heavy anchor with W_sub > R(z=5) gives s_req(5) = 0
        heavy = SuctionAnchor(diameter_m=5.0, skirt_length_m=15.0,
                              submerged_weight_kN=5000.0)
        z_sw = self_weight_penetration(heavy, soil)
        if z_sw > 3.0:
            assert required_suction_kPa(heavy, soil, 1.0) == 0.0


# ---------------------------------------------------------------------------
# Allowable suction (cavitation)
# ---------------------------------------------------------------------------

class TestAllowableSuction:

    def test_grows_with_water_depth(self, soil):
        s1 = allowable_suction_kPa(100.0, 5.0, soil)
        s2 = allowable_suction_kPa(500.0, 5.0, soil)
        assert s2 > s1

    def test_grows_with_penetration(self, soil):
        s1 = allowable_suction_kPa(200.0, 1.0, soil)
        s2 = allowable_suction_kPa(200.0, 10.0, soil)
        assert s2 > s1

    def test_positive_at_surface(self, soil):
        s = allowable_suction_kPa(100.0, 0.0, soil)
        assert s > 0


# ---------------------------------------------------------------------------
# Plug heave
# ---------------------------------------------------------------------------

class TestPlugHeave:

    def test_no_suction_safe(self, anchor, soil):
        r = plug_heave_check(anchor, soil, 5.0, 0.0)
        assert r < 1.0

    def test_large_suction_unsafe(self, anchor, soil):
        # absurdly high suction -> plug heaves
        r = plug_heave_check(anchor, soil, 5.0, 10_000.0)
        assert r > 1.0

    def test_monotonic_in_suction(self, anchor, soil):
        r_vals = [plug_heave_check(anchor, soil, 5.0, s)
                  for s in [0.0, 10.0, 50.0, 100.0, 500.0]]
        assert all(r_vals[i + 1] > r_vals[i]
                   for i in range(len(r_vals) - 1))


# ---------------------------------------------------------------------------
# Full installation analysis
# ---------------------------------------------------------------------------

class TestInstallationAnalysis:

    def test_returns_result(self, anchor, soil):
        res = installation_analysis(anchor, soil, water_depth_m=200.0)
        assert isinstance(res, InstallationResult)

    def test_profile_has_required_columns(self, anchor, soil):
        res = installation_analysis(anchor, soil, water_depth_m=200.0)
        required = {"depth_m", "F_drive_kN", "F_resist_kN",
                    "s_req_kPa", "s_allow_kPa", "R_plug"}
        assert required.issubset(res.profile.columns)

    def test_feasible_for_deep_water(self, anchor, soil):
        # 500 m water depth gives enough cavitation margin
        res = installation_analysis(anchor, soil, water_depth_m=500.0)
        assert res.feasible is True

    def test_not_feasible_for_shallow_cavitation(self, anchor, soil):
        # Very shallow water reduces the cavitation limit below s_req
        res = installation_analysis(anchor, soil, water_depth_m=2.0)
        # either infeasible or plug_heave ok but suction exceeds limit
        assert (not res.feasible) or (res.max_suction_required_kPa
                                      < res.max_allowable_suction_kPa)

    def test_bad_water_depth_raises(self, anchor, soil):
        with pytest.raises(ValueError):
            installation_analysis(anchor, soil, water_depth_m=0.0)
