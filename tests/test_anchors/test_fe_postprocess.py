"""
Tests for op3.anchors.fe_postprocess.

Covers:
  * Missing results_dir raises with driver hint
  * End-to-end consumption of a valid envelope + dissipation pair
  * Behaviour when only envelope.csv is present (optimal_padeye = None)
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from op3.anchors import SuctionAnchor, UndrainedClayProfile
from op3.anchors.fe_postprocess import load_anchor_fe_results


@pytest.fixture
def anchor():
    return SuctionAnchor(diameter_m=5.0, skirt_length_m=15.0,
                         padeye_depth_m=10.0)


@pytest.fixture
def soil():
    return UndrainedClayProfile(su_mudline_kPa=5.0,
                                su_gradient_kPa_per_m=1.5)


def _write_valid_envelope(dirp: Path) -> None:
    pd.DataFrame({
        "angle_deg": [0.0, 30.0, 60.0, 90.0],
        "T_ult_kN_half": [5000.0, 4800.0, 5500.0, 6200.0],
        "H_ult_kN": [10000.0, 8314.0, 5500.0, 0.0],
        "V_ult_kN": [0.0, 4800.0, 9526.0, 12400.0],
        "time_s": [120.0, 110.0, 115.0, 125.0],
    }).to_csv(dirp / "envelope.csv", index=False)


def _write_valid_dissipation(dirp: Path) -> None:
    z = np.linspace(0.0, 15.0, 30)
    psi = np.exp(-((z - 10.0) ** 2) / (2.0 * 3.0 ** 2))  # peak at 10 m
    pd.DataFrame({
        "depth_m": z,
        "w_z": psi,
        "D_total_kJ": psi * 50.0,
    }).to_csv(dirp / "dissipation.csv", index=False)


class TestLoadFEResults:

    def test_missing_directory_raises(self, anchor, soil, tmp_path):
        with pytest.raises(FileNotFoundError, match="optumgx_anchor_run.py"):
            load_anchor_fe_results(tmp_path / "absent",
                                   anchor, soil)

    def test_full_pipeline(self, anchor, soil, tmp_path):
        _write_valid_envelope(tmp_path)
        _write_valid_dissipation(tmp_path)
        res = load_anchor_fe_results(tmp_path, anchor, soil,
                                     load_angle_deg=30.0)
        assert res.capacity.method == "fe_calibrated"
        assert res.capacity.H_ult_kN == pytest.approx(10000.0)
        assert res.capacity.V_ult_kN == pytest.approx(12400.0)
        # padeye centroid: Gaussian peaked at z=10
        assert res.optimal_padeye_m == pytest.approx(10.0, abs=0.5)

    def test_envelope_only_no_padeye(self, anchor, soil, tmp_path):
        _write_valid_envelope(tmp_path)  # no dissipation file
        res = load_anchor_fe_results(tmp_path, anchor, soil)
        assert res.optimal_padeye_m is None
        assert res.dissipation is None
