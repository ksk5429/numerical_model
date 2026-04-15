"""
Tests for op3.anchors.capacity -- analytical capacity methods.

Covers:
  * Physical plausibility of H_ult, V_ult (signs, monotonicity in D, L, su)
  * Consistency between methods (same order of magnitude)
  * V-H envelope properties (convex, endpoints match H_ult / V_ult)
  * Dispatcher routing
  * FE-calibrated method raises FileNotFoundError with correct message
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from op3.anchors import (
    SuctionAnchor,
    UndrainedClayProfile,
    MooringLoad,
    anchor_capacity,
    capacity_dnv_rp_e303,
    capacity_murff_hamilton,
    capacity_api_rp_2sk,
    capacity_aubeny_2003,
    capacity_fe_calibrated,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def reference_anchor():
    """Reference suction anchor: D=5 m, L=15 m, z_p=10 m."""
    return SuctionAnchor(
        diameter_m=5.0, skirt_length_m=15.0,
        wall_thickness_mm=30.0,
        padeye_depth_m=10.0,
        submerged_weight_kN=500.0,
    )


@pytest.fixture
def reference_soil():
    """Normally-consolidated clay: su_0 = 5 kPa, k = 1.5 kPa/m."""
    return UndrainedClayProfile(
        su_mudline_kPa=5.0,
        su_gradient_kPa_per_m=1.5,
        sensitivity=3.0,
    )


ANALYTICAL_METHODS = ["dnv_rp_e303", "murff_hamilton",
                      "api_rp_2sk", "aubeny_2003"]


# ---------------------------------------------------------------------------
# Physical plausibility
# ---------------------------------------------------------------------------

class TestPhysicalPlausibility:

    @pytest.mark.parametrize("method", ANALYTICAL_METHODS)
    def test_H_ult_positive(self, reference_anchor, reference_soil, method):
        r = anchor_capacity(reference_anchor, reference_soil, method=method)
        assert r.H_ult_kN > 0

    @pytest.mark.parametrize("method", ANALYTICAL_METHODS)
    def test_V_ult_positive(self, reference_anchor, reference_soil, method):
        r = anchor_capacity(reference_anchor, reference_soil, method=method)
        assert r.V_ult_kN > 0

    @pytest.mark.parametrize("method", ANALYTICAL_METHODS)
    def test_T_ult_between_H_and_T_max(
        self, reference_anchor, reference_soil, method,
    ):
        # At 30 deg, T_ult should be less than max(H_ult, V_ult/sin)
        r = anchor_capacity(reference_anchor, reference_soil,
                            method=method, load_angle_deg=30.0)
        assert r.T_ult_kN > 0
        # horizontal component should be below H_ult
        H_comp = r.T_ult_kN * np.cos(np.radians(30.0))
        assert H_comp <= r.H_ult_kN + 1e-6

    @pytest.mark.parametrize("method", ANALYTICAL_METHODS)
    def test_H_monotonic_in_L(self, reference_soil, method):
        a_short = SuctionAnchor(diameter_m=5.0, skirt_length_m=10.0,
                                padeye_depth_m=7.0)
        a_long = SuctionAnchor(diameter_m=5.0, skirt_length_m=20.0,
                               padeye_depth_m=14.0)
        r_s = anchor_capacity(a_short, reference_soil, method=method)
        r_l = anchor_capacity(a_long, reference_soil, method=method)
        assert r_l.H_ult_kN > r_s.H_ult_kN

    @pytest.mark.parametrize("method", ANALYTICAL_METHODS)
    def test_H_monotonic_in_su(self, reference_anchor, method):
        soil_weak = UndrainedClayProfile(su_mudline_kPa=2.0,
                                         su_gradient_kPa_per_m=1.0)
        soil_strong = UndrainedClayProfile(su_mudline_kPa=20.0,
                                           su_gradient_kPa_per_m=2.0)
        r_w = anchor_capacity(reference_anchor, soil_weak, method=method)
        r_s = anchor_capacity(reference_anchor, soil_strong, method=method)
        assert r_s.H_ult_kN > r_w.H_ult_kN


# ---------------------------------------------------------------------------
# V-H envelope
# ---------------------------------------------------------------------------

class TestInteractionEnvelope:

    @pytest.mark.parametrize("method", ANALYTICAL_METHODS)
    def test_envelope_endpoints(self, reference_anchor, reference_soil, method):
        r = anchor_capacity(reference_anchor, reference_soil, method=method)
        env = r.interaction_envelope
        # angle=0 -> H=H_ult, V=0
        row0 = env.iloc[0]
        assert row0["H_kN"] == pytest.approx(r.H_ult_kN, rel=1e-3)
        assert row0["V_kN"] == pytest.approx(0.0, abs=1e-3 * r.H_ult_kN)
        # angle=90 -> H=0, V=V_ult
        row90 = env.iloc[-1]
        assert row90["V_kN"] == pytest.approx(r.V_ult_kN, rel=1e-3)
        assert row90["H_kN"] == pytest.approx(
            0.0, abs=1e-3 * r.V_ult_kN
        )

    @pytest.mark.parametrize("method", ANALYTICAL_METHODS)
    def test_envelope_monotone(self, reference_anchor, reference_soil, method):
        r = anchor_capacity(reference_anchor, reference_soil, method=method)
        env = r.interaction_envelope
        # As angle increases, H decreases, V increases
        assert env["H_kN"].is_monotonic_decreasing
        assert env["V_kN"].is_monotonic_increasing


# ---------------------------------------------------------------------------
# Cross-method consistency
# ---------------------------------------------------------------------------

class TestMethodConsistency:

    def test_all_methods_same_order_of_magnitude(
        self, reference_anchor, reference_soil,
    ):
        results = {
            m: anchor_capacity(reference_anchor, reference_soil, method=m)
            for m in ANALYTICAL_METHODS
        }
        H = np.array([r.H_ult_kN for r in results.values()])
        # spread less than factor 3 across methods
        assert H.max() / H.min() < 3.0

    def test_api_more_conservative_than_aubeny_rough(
        self, reference_anchor, reference_soil,
    ):
        """API (Np_deep=9) with alpha=0.5 should give lower H than
        Aubeny rough (Np_deep=11.94, alpha=1.0)."""
        r_api = anchor_capacity(reference_anchor, reference_soil,
                                method="api_rp_2sk")
        r_aub = anchor_capacity(reference_anchor, reference_soil,
                                method="aubeny_2003", interface="rough")
        assert r_aub.H_ult_kN > r_api.H_ult_kN


# ---------------------------------------------------------------------------
# Dispatcher
# ---------------------------------------------------------------------------

class TestDispatcher:

    def test_unknown_method_raises(self, reference_anchor, reference_soil):
        with pytest.raises(ValueError, match="Unknown capacity method"):
            anchor_capacity(reference_anchor, reference_soil,
                            method="not_a_method")

    def test_case_insensitive(self, reference_anchor, reference_soil):
        r = anchor_capacity(reference_anchor, reference_soil,
                            method="DNV_RP_E303")
        assert r.method == "dnv_rp_e303"

    def test_load_overrides_angle(self, reference_anchor, reference_soil):
        load = MooringLoad(tension_kN=1000.0, angle_at_padeye_deg=35.0)
        r = anchor_capacity(reference_anchor, reference_soil,
                            method="dnv_rp_e303", load=load)
        assert r.load_angle_deg == 35.0

    def test_factor_of_safety(self, reference_anchor, reference_soil):
        r = anchor_capacity(reference_anchor, reference_soil,
                            method="dnv_rp_e303", load_angle_deg=30.0)
        fos = r.factor_of_safety(applied_kN=1000.0)
        assert fos == pytest.approx(r.T_ult_kN / 1000.0)


# ---------------------------------------------------------------------------
# FE-calibrated method: real-data contract
# ---------------------------------------------------------------------------

class TestFECalibrated:

    def test_missing_csv_raises_with_hint(
        self, reference_anchor, reference_soil, tmp_path,
    ):
        fake = tmp_path / "absent_fe_envelope.csv"
        with pytest.raises(FileNotFoundError) as exc:
            capacity_fe_calibrated(reference_anchor, reference_soil,
                                   fe_csv=fake)
        msg = str(exc.value)
        assert "optumgx_anchor_run.py" in msg
        assert "ANCHOR_OPTUMGX_GUIDE" in msg

    def test_valid_csv_is_consumed(
        self, reference_anchor, reference_soil, tmp_path,
    ):
        """Use a minimal valid envelope (3 angles) to exercise parsing."""
        csv = tmp_path / "fe_envelope.csv"
        # Synthetic CSV is NEVER shipped with Op^3 -- this is a pytest
        # fixture only, testing that the parser works when a real
        # OptumGX CSV is provided. The values are intentionally
        # unphysical small numbers so the test does not masquerade as
        # a real benchmark.
        pd.DataFrame({
            "angle_deg": [0.0, 45.0, 90.0],
            "H_ult_kN": [1000.0, 700.0, 0.0],
            "V_ult_kN": [0.0, 700.0, 1000.0],
        }).to_csv(csv, index=False)
        r = capacity_fe_calibrated(reference_anchor, reference_soil,
                                   fe_csv=csv, load_angle_deg=45.0)
        assert r.method == "fe_calibrated"
        assert r.H_ult_kN == pytest.approx(1000.0)
        assert r.V_ult_kN == pytest.approx(1000.0)
        assert r.metadata["fe_csv"] == str(csv)

    def test_malformed_csv_raises(
        self, reference_anchor, reference_soil, tmp_path,
    ):
        csv = tmp_path / "bad.csv"
        pd.DataFrame({"foo": [1, 2]}).to_csv(csv, index=False)
        with pytest.raises(ValueError, match="missing columns"):
            capacity_fe_calibrated(reference_anchor, reference_soil,
                                   fe_csv=csv)
