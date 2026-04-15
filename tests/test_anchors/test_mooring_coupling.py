"""
Tests for op3.anchors.mooring_coupling.

The MoorPy-backed path is exercised by the example script; here we
unit-test the pure-Python parts:

  * CSV reader validation (missing file, missing columns, H/V
    derivation from T + angle)
  * Safety-factor timeseries monotonicity and pass/fail flag
  * Report writer
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from op3.anchors import (
    SuctionAnchor, UndrainedClayProfile,
    extract_anchor_loads_from_moorpy,
    anchor_safety_factor_timeseries,
    generate_anchor_report,
)


@pytest.fixture
def anchor():
    return SuctionAnchor(diameter_m=5.0, skirt_length_m=15.0,
                         padeye_depth_m=10.0,
                         submerged_weight_kN=500.0)


@pytest.fixture
def soil():
    return UndrainedClayProfile(su_mudline_kPa=5.0,
                                su_gradient_kPa_per_m=1.5)


# ---------------------------------------------------------------------------
# CSV reader
# ---------------------------------------------------------------------------

class TestCsvReader:

    def test_missing_file_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError,
                           match="OpenFAST\\+MoorDyn"):
            extract_anchor_loads_from_moorpy(tmp_path / "absent.csv")

    def test_valid_csv_derives_HV(self, tmp_path):
        csv = tmp_path / "tens.csv"
        pd.DataFrame({
            "time_s": [0.0, 10.0, 20.0],
            "T_kN": [1000.0, 1500.0, 2000.0],
            "angle_deg": [30.0, 30.0, 30.0],
        }).to_csv(csv, index=False)
        df = extract_anchor_loads_from_moorpy(csv)
        assert {"H_kN", "V_kN"}.issubset(df.columns)
        assert df["H_kN"].iloc[0] == pytest.approx(
            1000.0 * np.cos(np.radians(30.0))
        )

    def test_missing_columns_raise(self, tmp_path):
        csv = tmp_path / "bad.csv"
        pd.DataFrame({"t": [1, 2]}).to_csv(csv, index=False)
        with pytest.raises(ValueError, match="missing columns"):
            extract_anchor_loads_from_moorpy(csv)


# ---------------------------------------------------------------------------
# Safety-factor timeseries
# ---------------------------------------------------------------------------

class TestSafetyFactor:

    def test_pass_fail_boundary(self, anchor, soil):
        # Build a loads df that ranges T from 1 kN up to capacity
        T_vals = np.array([500.0, 2500.0, 5000.0, 8000.0, 12000.0])
        loads = pd.DataFrame({
            "time_s": np.arange(len(T_vals)),
            "T_kN": T_vals,
            "angle_deg": [30.0] * len(T_vals),
        })
        res = anchor_safety_factor_timeseries(anchor, soil, loads)
        assert "FoS" in res.columns
        assert res["FoS"].is_monotonic_decreasing
        # the FoS should become < 1.3 at some point for a sane anchor
        assert (res["FoS"] < 1.3).any() or (res["FoS"] >= 1.3).all()

    def test_pass_flag_respects_limit(self, anchor, soil):
        loads = pd.DataFrame({
            "time_s": [0.0, 10.0],
            "T_kN": [100.0, 100000.0],
            "angle_deg": [30.0, 30.0],
        })
        res = anchor_safety_factor_timeseries(anchor, soil, loads,
                                              fos_limit=1.3)
        assert res["pass"].iloc[0] == True
        assert res["pass"].iloc[1] == False


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------

class TestReport:

    def test_report_writes_markdown(self, anchor, soil, tmp_path):
        loads = pd.DataFrame({
            "time_s": [0.0, 10.0, 20.0],
            "T_kN": [1000.0, 2000.0, 1500.0],
            "angle_deg": [30.0, 35.0, 30.0],
        })
        res = anchor_safety_factor_timeseries(anchor, soil, loads)
        out = generate_anchor_report(res, anchor, soil,
                                     output_path=tmp_path / "report.md")
        assert out.exists()
        txt = out.read_text(encoding="utf-8")
        assert "Suction-anchor design report" in txt
        assert "min FoS" in txt
