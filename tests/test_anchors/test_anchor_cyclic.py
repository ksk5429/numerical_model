"""
Tests for op3.anchors.cyclic.

Covers:
  * Andersen 2015 surrogate boundary behaviour (N=1 -> 1.0,
    large N, large amplitude -> smaller delta)
  * PI validity range
  * Storm-duration wrapper produces sensible N and delta
  * apply_cyclic_to_soil scales both su0 and gradient
"""
from __future__ import annotations

import pytest

from op3.anchors import (
    SuctionAnchor, UndrainedClayProfile,
    cyclic_capacity_reduction, andersen_cyclic_reduction,
    apply_cyclic_to_soil, CyclicResult,
)


@pytest.fixture
def anchor():
    return SuctionAnchor(diameter_m=5.0, skirt_length_m=15.0)


@pytest.fixture
def soil():
    return UndrainedClayProfile(su_mudline_kPa=5.0,
                                su_gradient_kPa_per_m=1.5,
                                plasticity_index=27.0)


class TestAndersenSurrogate:

    def test_unity_at_n_1(self):
        d = andersen_cyclic_reduction(1.0, 0.3, 27.0)
        assert d == pytest.approx(1.0, abs=5e-3)

    def test_decreases_with_cycles(self):
        d_low = andersen_cyclic_reduction(10.0, 0.5, 27.0)
        d_high = andersen_cyclic_reduction(10000.0, 0.5, 27.0)
        assert d_high < d_low

    def test_decreases_with_amplitude(self):
        d_low = andersen_cyclic_reduction(1000.0, 0.3, 27.0)
        d_high = andersen_cyclic_reduction(1000.0, 0.7, 27.0)
        assert d_high < d_low

    def test_result_in_range(self):
        for N in [10, 100, 1000, 10000]:
            for r in [0.2, 0.4, 0.6, 0.8]:
                d = andersen_cyclic_reduction(N, r, 27.0)
                assert 0.3 <= d <= 1.0, f"d={d} out of range for N={N}, r={r}"

    def test_PI_out_of_range_raises(self):
        with pytest.raises(ValueError, match="PI"):
            andersen_cyclic_reduction(100.0, 0.5, 80.0)

    def test_amplitude_range(self):
        with pytest.raises(ValueError, match="tau_cyc_over_su"):
            andersen_cyclic_reduction(100.0, 1.5, 27.0)

    def test_few_cycles(self):
        with pytest.raises(ValueError, match="n_cycles"):
            andersen_cyclic_reduction(0.5, 0.4, 27.0)


class TestStormWrapper:

    def test_default_3h_storm(self, anchor, soil):
        res = cyclic_capacity_reduction(anchor, soil)
        assert isinstance(res, CyclicResult)
        # 3 h / 10 s = 1080 cycles
        assert res.n_cycles == pytest.approx(1080.0)
        assert 0.5 < res.reduction_factor < 1.0

    def test_longer_storm_reduces_more(self, anchor, soil):
        r1 = cyclic_capacity_reduction(anchor, soil,
                                       storm_duration_hours=1.0)
        r6 = cyclic_capacity_reduction(anchor, soil,
                                       storm_duration_hours=6.0)
        assert r6.reduction_factor < r1.reduction_factor

    def test_higher_amplitude_reduces_more(self, anchor, soil):
        r03 = cyclic_capacity_reduction(anchor, soil,
                                        tau_cyc_over_su=0.3)
        r07 = cyclic_capacity_reduction(anchor, soil,
                                        tau_cyc_over_su=0.7)
        assert r07.reduction_factor < r03.reduction_factor

    def test_unknown_method_raises(self, anchor, soil):
        with pytest.raises(ValueError, match="Unknown cyclic method"):
            cyclic_capacity_reduction(anchor, soil, method="fake")


class TestApplyCyclicToSoil:

    def test_both_su0_and_gradient_scaled(self, soil):
        res = CyclicResult(n_cycles=1000.0, tau_cyc_over_su=0.5,
                           reduction_factor=0.7, method="andersen_2015")
        s2 = apply_cyclic_to_soil(soil, res)
        assert s2.su_mudline_kPa == pytest.approx(
            soil.su_mudline_kPa * 0.7
        )
        assert s2.su_gradient_kPa_per_m == pytest.approx(
            soil.su_gradient_kPa_per_m * 0.7
        )

    def test_other_params_preserved(self, soil):
        res = CyclicResult(n_cycles=1000.0, tau_cyc_over_su=0.5,
                           reduction_factor=0.8, method="andersen_2015")
        s2 = apply_cyclic_to_soil(soil, res)
        assert s2.sensitivity == soil.sensitivity
        assert s2.gamma_eff_kN_per_m3 == soil.gamma_eff_kN_per_m3
        assert s2.plasticity_index == soil.plasticity_index
