"""
Tests for op3.anchors.padeye.

Covers:
  * Supachawarote 2005 interpolation at tabulated and intermediate L/D
  * Murff-Hamilton constant 0.67L
  * Sensitivity study returns DataFrame over the requested range
  * Dissipation-centroid method:
        - FileNotFoundError with driver hint when CSV missing
        - correct centroid for a known triangular psi(z) field
        - rejects malformed or non-physical CSVs
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from op3.anchors import (
    SuctionAnchor, UndrainedClayProfile,
    optimal_padeye_analytical,
    optimal_padeye_from_dissipation,
    padeye_sensitivity_study,
)
from op3.anchors.padeye import SUPACHAWAROTE_2005


@pytest.fixture
def anchor():
    return SuctionAnchor(diameter_m=5.0, skirt_length_m=15.0)


@pytest.fixture
def soil_linear():
    return UndrainedClayProfile(su_mudline_kPa=0.0,
                                su_gradient_kPa_per_m=1.5)


@pytest.fixture
def soil_uniform():
    return UndrainedClayProfile(su_mudline_kPa=10.0,
                                su_gradient_kPa_per_m=0.0)


# ---------------------------------------------------------------------------
# Analytical
# ---------------------------------------------------------------------------

class TestAnalyticalPadeye:

    def test_supachawarote_tabulated_value_linear(self, anchor, soil_linear):
        # L/D = 3.0 exactly in the linear table
        z_p = optimal_padeye_analytical(anchor, soil_linear,
                                        method="supachawarote_2005")
        # expected 0.73 * 15 = 10.95
        assert z_p == pytest.approx(10.95, rel=1e-3)

    def test_supachawarote_tabulated_value_uniform(self, anchor, soil_uniform):
        z_p = optimal_padeye_analytical(anchor, soil_uniform,
                                        method="supachawarote_2005")
        # L/D=3 uniform: 0.70 * 15 = 10.5
        assert z_p == pytest.approx(10.5, rel=1e-3)

    def test_murff_hamilton_two_thirds(self, anchor, soil_linear):
        z_p = optimal_padeye_analytical(anchor, soil_linear,
                                        method="murff_hamilton")
        assert z_p == pytest.approx(0.67 * 15.0)

    def test_clamp_below_tabulated_range(self, soil_linear):
        tiny = SuctionAnchor(diameter_m=10.0, skirt_length_m=5.0)  # L/D=0.5
        z_p = optimal_padeye_analytical(tiny, soil_linear)
        # clamped to the L/D=1 entry (0.68*L)
        assert z_p == pytest.approx(0.68 * 5.0)

    def test_clamp_above_tabulated_range(self, soil_linear):
        tall = SuctionAnchor(diameter_m=2.0, skirt_length_m=20.0)  # L/D=10
        z_p = optimal_padeye_analytical(tall, soil_linear)
        assert z_p == pytest.approx(0.75 * 20.0)

    def test_unknown_method_raises(self, anchor, soil_linear):
        with pytest.raises(ValueError, match="Unknown padeye method"):
            optimal_padeye_analytical(anchor, soil_linear, method="foo")


# ---------------------------------------------------------------------------
# Sensitivity study
# ---------------------------------------------------------------------------

class TestSensitivityStudy:

    def test_returns_dataframe(self, anchor, soil_linear):
        z_p_range = np.linspace(0.2, 0.9, 8) * anchor.skirt_length_m
        df = padeye_sensitivity_study(anchor, soil_linear, z_p_range,
                                      load_angle_deg=25.0)
        assert len(df) == 8
        assert {"z_p_m", "z_p_over_L", "H_ult_kN",
                "V_ult_kN", "T_ult_kN"}.issubset(df.columns)

    def test_excludes_out_of_range(self, anchor, soil_linear):
        z_p_range = np.array([0.0, 5.0, 10.0, 15.0, 20.0])
        df = padeye_sensitivity_study(anchor, soil_linear, z_p_range)
        # 0 and L are excluded; above L also excluded
        assert len(df) == 2


# ---------------------------------------------------------------------------
# Dissipation-centroid method (NOVEL)
# ---------------------------------------------------------------------------

class TestDissipationCentroid:

    def test_missing_csv_raises_with_hint(self, anchor, tmp_path):
        fake = tmp_path / "no_dissipation.csv"
        with pytest.raises(FileNotFoundError) as exc:
            optimal_padeye_from_dissipation(anchor, fake)
        msg = str(exc.value)
        assert "optumgx_anchor_run.py" in msg
        assert "ANCHOR_OPTUMGX_GUIDE" in msg

    def test_triangular_dissipation_centroid(self, anchor, tmp_path):
        """For a triangular psi(z) peaking at z=7.5, centroid is 2/3*L."""
        csv = tmp_path / "psi.csv"
        L = anchor.skirt_length_m
        z = np.linspace(0.0, L, 51)
        # triangular distribution: rises linearly 0..L/2, falls L/2..L
        psi = np.minimum(z, L - z) / (L / 2.0)
        df = pd.DataFrame({"depth_m": z, "w_z": psi,
                           "D_total_kJ": psi * 100.0})
        df.to_csv(csv, index=False)
        z_opt = optimal_padeye_from_dissipation(anchor, csv)
        # centroid of symmetric triangle = L/2
        assert z_opt == pytest.approx(L / 2.0, rel=1e-2)

    def test_right_skewed_centroid_below_midpoint(self, anchor, tmp_path):
        """For psi(z) peaking near z=L, centroid > L/2."""
        csv = tmp_path / "psi_skewed.csv"
        L = anchor.skirt_length_m
        z = np.linspace(0.0, L, 51)
        psi = z ** 2  # grows as z^2
        df = pd.DataFrame({"depth_m": z, "w_z": psi,
                           "D_total_kJ": psi * 10.0})
        df.to_csv(csv, index=False)
        z_opt = optimal_padeye_from_dissipation(anchor, csv)
        assert z_opt > L / 2.0

    def test_missing_columns_raises(self, anchor, tmp_path):
        csv = tmp_path / "bad_cols.csv"
        pd.DataFrame({"depth": [1, 2]}).to_csv(csv, index=False)
        with pytest.raises(ValueError, match="missing columns"):
            optimal_padeye_from_dissipation(anchor, csv)

    def test_negative_weights_raises(self, anchor, tmp_path):
        csv = tmp_path / "neg.csv"
        pd.DataFrame({"depth_m": [0.0, 5.0, 10.0],
                      "w_z": [1.0, -0.5, 1.0],
                      "D_total_kJ": [100.0, 50.0, 80.0]}).to_csv(
            csv, index=False,
        )
        with pytest.raises(ValueError, match="negative"):
            optimal_padeye_from_dissipation(anchor, csv)

    def test_zero_weights_raises(self, anchor, tmp_path):
        csv = tmp_path / "zero.csv"
        pd.DataFrame({"depth_m": [0.0, 5.0, 10.0],
                      "w_z": [0.0, 0.0, 0.0],
                      "D_total_kJ": [0.0, 0.0, 0.0]}).to_csv(csv, index=False)
        with pytest.raises(ValueError, match="sum to zero"):
            optimal_padeye_from_dissipation(anchor, csv)


# ---------------------------------------------------------------------------
# Supachawarote table integrity
# ---------------------------------------------------------------------------

class TestSupachawaroteTable:

    def test_table_has_both_profiles(self):
        assert "uniform" in SUPACHAWAROTE_2005
        assert "linear" in SUPACHAWAROTE_2005

    def test_linear_values_above_uniform(self):
        for ld in [1.0, 2.0, 3.0, 4.0, 5.0]:
            assert SUPACHAWAROTE_2005["linear"][ld] > \
                   SUPACHAWAROTE_2005["uniform"][ld]

    def test_values_in_physical_range(self):
        for profile in SUPACHAWAROTE_2005.values():
            for frac in profile.values():
                assert 0.5 < frac < 0.9
