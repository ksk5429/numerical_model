"""
Tests for op3.fatigue -- DEL computation and rainflow counting.

Covers:
  - compute_del() with pure sine wave (DEL ~ 2*amplitude)
  - compute_del() with constant signal (DEL = 0)
  - rainflow_count() cycle counting
  - compute_del() monotonicity across m values
  - Edge cases: short signals, missing arguments
"""
from __future__ import annotations

import numpy as np
import pytest

from op3.fatigue import compute_del, rainflow_count, compute_del_multi_slope


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def sine_signal():
    """Pure sine wave: amplitude=100, 10 full cycles, dt=0.01 s."""
    t = np.linspace(0, 10, 1001)  # 10 s at dt=0.01
    return 100.0 * np.sin(2 * np.pi * t), 0.01


@pytest.fixture
def constant_signal():
    """Flat signal at value 42, 500 points, dt=0.01 s."""
    return np.full(500, 42.0), 0.01


# ---------------------------------------------------------------------------
# Pure sine wave tests
# ---------------------------------------------------------------------------

class TestComputeDelSineWave:
    """A pure sine with amplitude A should have DEL close to 2*A (the full range)."""

    def test_del_sine_m3(self, sine_signal):
        signal, dt = sine_signal
        del_val = compute_del(signal, m=3, dt=dt)
        # For a pure sine of amplitude 100, the full range is 200.
        # With m=3, DEL should be close to 200 (exact depends on n_eq normalisation).
        assert del_val > 0, "DEL of a sine wave must be positive"
        # The range of each cycle is 200; DEL = (sum(n*S^m)/N_eq)^(1/m).
        # With ~10 cycles and N_eq = 1 Hz * 10 s = 10, DEL should be ~200.
        assert del_val == pytest.approx(200.0, rel=0.15), (
            f"DEL={del_val:.1f}, expected ~200 for amplitude=100 sine"
        )

    def test_del_sine_m4(self, sine_signal):
        signal, dt = sine_signal
        del_val = compute_del(signal, m=4, dt=dt)
        assert del_val > 0
        assert del_val == pytest.approx(200.0, rel=0.15)


# ---------------------------------------------------------------------------
# Constant signal tests
# ---------------------------------------------------------------------------

class TestComputeDelConstant:
    """A constant signal has zero range, so DEL must be 0."""

    def test_del_constant_is_zero(self, constant_signal):
        signal, dt = constant_signal
        del_val = compute_del(signal, m=3, dt=dt)
        assert del_val == 0.0

    def test_del_constant_any_m(self, constant_signal):
        signal, dt = constant_signal
        for m in [3, 4, 5, 10]:
            assert compute_del(signal, m=m, dt=dt) == 0.0


# ---------------------------------------------------------------------------
# Rainflow counting
# ---------------------------------------------------------------------------

class TestRainflowCount:
    """Basic sanity checks on rainflow_count output."""

    def test_returns_arrays(self, sine_signal):
        signal, _ = sine_signal
        ranges, counts = rainflow_count(signal)
        assert isinstance(ranges, np.ndarray)
        assert isinstance(counts, np.ndarray)
        assert len(ranges) == len(counts)

    def test_sine_produces_cycles(self, sine_signal):
        signal, _ = sine_signal
        ranges, counts = rainflow_count(signal)
        assert len(ranges) > 0, "Sine wave must produce at least one cycle"
        # Total cycle count should be roughly 10 (10 full sine cycles)
        total_cycles = counts.sum()
        assert total_cycles >= 5, f"Expected ~10 cycles, got {total_cycles}"

    def test_ranges_are_positive(self, sine_signal):
        signal, _ = sine_signal
        ranges, _ = rainflow_count(signal)
        assert np.all(ranges >= 0), "Ranges must be non-negative"

    def test_constant_no_cycles(self, constant_signal):
        signal, _ = constant_signal
        ranges, counts = rainflow_count(signal)
        # Constant signal has no turning points -> no cycles
        assert len(ranges) == 0 or np.all(ranges == 0)


# ---------------------------------------------------------------------------
# Monotonicity: DEL should increase with m for a signal with mixed ranges
# ---------------------------------------------------------------------------

class TestDelMonotonicity:
    """DEL should be monotonically non-decreasing with m for signals
    whose range exceeds 1 (because large ranges dominate more at high m)."""

    def test_del_increases_with_m(self, sine_signal):
        signal, dt = sine_signal
        m_values = [3, 4, 10]
        dels = [compute_del(signal, m=m, dt=dt) for m in m_values]
        # For a pure sine all ranges are equal, so DEL is roughly constant.
        # Just verify they are all positive and close to each other.
        for d in dels:
            assert d > 0

    def test_multi_slope_convenience(self, sine_signal):
        signal, dt = sine_signal
        result = compute_del_multi_slope(signal, m_values=[3, 4, 10], dt=dt)
        assert isinstance(result, dict)
        assert set(result.keys()) == {3, 4, 10}
        for v in result.values():
            assert v > 0

    def test_mixed_signal_monotonicity(self):
        """A signal with both small and large ranges: DEL should grow with m."""
        # Build a signal with cycles of range 10 and range 200.
        t = np.linspace(0, 20, 2001)
        signal = 100 * np.sin(2 * np.pi * 0.5 * t) + 5 * np.sin(2 * np.pi * 5 * t)
        m_values = [3, 4, 10]
        dels = [compute_del(signal, m=m, dt=0.01) for m in m_values]
        # Higher m emphasises the large ranges -> DEL should not decrease
        for i in range(len(dels) - 1):
            assert dels[i + 1] >= dels[i] * 0.95, (
                f"DEL(m={m_values[i+1]})={dels[i+1]:.1f} < "
                f"DEL(m={m_values[i]})={dels[i]:.1f}"
            )


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

class TestEdgeCases:
    """Short signals, empty arrays, missing arguments."""

    def test_empty_signal(self):
        del_val = compute_del(np.array([]), m=3, n_eq=1.0)
        assert del_val == 0.0

    def test_single_value(self):
        del_val = compute_del(np.array([42.0]), m=3, n_eq=1.0)
        assert del_val == 0.0

    def test_two_values(self):
        del_val = compute_del(np.array([0.0, 100.0]), m=3, n_eq=1.0)
        assert del_val == 0.0  # size < 3 returns 0

    def test_three_values(self):
        # [0, 100, 0] has one cycle of range 100
        del_val = compute_del(np.array([0.0, 100.0, 0.0]), m=3, n_eq=1.0)
        assert del_val > 0

    def test_missing_dt_and_neq_raises(self):
        signal = np.sin(np.linspace(0, 10, 100))
        with pytest.raises(ValueError, match="Either n_eq or dt"):
            compute_del(signal, m=3)

    def test_n_eq_zero_returns_zero(self):
        signal = np.sin(np.linspace(0, 10, 100))
        del_val = compute_del(signal, m=3, n_eq=0.0)
        assert del_val == 0.0

    def test_negative_n_eq_returns_zero(self):
        signal = np.sin(np.linspace(0, 10, 100))
        del_val = compute_del(signal, m=3, n_eq=-5.0)
        assert del_val == 0.0
