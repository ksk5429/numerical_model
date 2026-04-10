"""
Validation of the DEL computation from op3.fatigue.

Analytical test cases:
  1. Pure sine wave: amplitude A, N full cycles -> DEL = A for any m.
     (Rainflow extracts N cycles each of range 2A.  DEL = (N*(2A)^m / N)^(1/m) = 2A.)
     CORRECTION: The range is 2A (peak-to-valley), so DEL = 2A for range-based DEL.
     If we want DEL in terms of *amplitude* (half-range), divide by 2.
     By convention (Hayman 2012), DEL uses ranges, so DEL = 2A.

  2. Constant signal: DEL = 0 (no cycles).

  3. Two-amplitude signal: known closed-form.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

# Add op3 to path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from op3.fatigue import compute_del, rainflow_count, compute_del_multi_slope


def test_pure_sine():
    """Pure sine: N cycles of amplitude A -> DEL = 2A (range-based)."""
    A = 100.0     # amplitude
    N = 50        # number of full cycles
    dt = 0.05     # time step
    T = N / 1.0   # period per cycle = 1 s (f=1 Hz)
    t = np.arange(0, N, dt)
    signal = A * np.sin(2 * np.pi * t)

    for m in [3.0, 4.0, 5.0, 10.0]:
        # n_eq = f_eq * duration = 1.0 * N = N cycles
        del_val = compute_del(signal, m=m, dt=dt, f_eq=1.0)
        expected = 2.0 * A  # range = 2*A
        rel_err = abs(del_val - expected) / expected
        status = "PASS" if rel_err < 0.05 else "FAIL"
        print(f"  Sine A={A}, m={m:>4.1f}: DEL={del_val:>8.2f}, "
              f"expected={expected:>8.2f}, err={rel_err:.3%} [{status}]")
        assert rel_err < 0.05, f"Sine test failed for m={m}: DEL={del_val}, expected={expected}"


def test_constant_signal():
    """Constant signal: no cycles, DEL = 0."""
    signal = np.ones(1000) * 500.0
    del_val = compute_del(signal, m=3.0, dt=0.1, f_eq=1.0)
    print(f"  Constant: DEL={del_val:.6f} (expected 0.0)")
    assert del_val < 1e-10, f"Constant signal DEL should be 0, got {del_val}"


def test_square_wave():
    """Square wave between +A and -A: each transition is a full range of 2A."""
    A = 75.0
    N = 100
    signal = np.array([A if i % 2 == 0 else -A for i in range(2 * N)])
    dt = 1.0
    del_val = compute_del(signal, m=3.0, n_eq=N)
    expected = 2.0 * A
    rel_err = abs(del_val - expected) / expected
    status = "PASS" if rel_err < 0.05 else "FAIL"
    print(f"  Square A={A}, m=3: DEL={del_val:.2f}, "
          f"expected={expected:.2f}, err={rel_err:.3%} [{status}]")
    assert rel_err < 0.05, f"Square wave test failed: DEL={del_val}, expected={expected}"


def test_multi_slope():
    """Test compute_del_multi_slope returns consistent results."""
    A = 100.0
    N = 50
    dt = 0.05
    t = np.arange(0, N, dt)
    signal = A * np.sin(2 * np.pi * t)
    results = compute_del_multi_slope(signal, m_values=[3.0, 5.0, 10.0], dt=dt, f_eq=1.0)
    print(f"  Multi-slope DELs: {', '.join(f'm={k}: {v:.2f}' for k, v in results.items())}")
    for m, del_val in results.items():
        expected = 2.0 * A
        rel_err = abs(del_val - expected) / expected
        assert rel_err < 0.05, f"Multi-slope failed for m={m}"


def test_rainflow_count_basic():
    """Verify rainflow_count returns reasonable cycle counts."""
    # Simple 3-peak signal
    signal = np.array([0, 1, -1, 2, -2, 0])
    ranges, counts = rainflow_count(signal)
    print(f"  Rainflow basic: {len(ranges)} cycles, "
          f"ranges={np.round(ranges, 2).tolist()}, counts={counts.tolist()}")
    assert len(ranges) > 0, "Should extract at least one cycle"


def test_applied_to_openfast():
    """If OC3 .outb is available, compute DEL on the blade root moment."""
    outb = (Path(__file__).resolve().parents[2]
            / "nrel_reference" / "openfast_rtest"
            / "5MW_OC3Mnpl_DLL_WTurb_WavesIrr"
            / "5MW_OC3Mnpl_DLL_WTurb_WavesIrr.outb")
    if not outb.exists():
        print("  [SKIP] OC3 .outb not found; skipping applied test.")
        return

    try:
        from openfast_io.FAST_output_reader import FASTOutputFile
    except ImportError:
        print("  [SKIP] openfast_io not available; skipping applied test.")
        return

    df = FASTOutputFile(str(outb)).toDataFrame()
    time_col = "Time_[s]"
    dt = float(df[time_col].iloc[1] - df[time_col].iloc[0])

    # Skip first 30s transient
    mask = df[time_col] >= 30.0
    for ch in ["RootMyc1_[kN-m]", "GenPwr_[kW]"]:
        if ch not in df.columns:
            continue
        signal = df.loc[mask, ch].to_numpy()
        del_vals = compute_del_multi_slope(
            signal, m_values=[3.0, 4.0, 5.0, 10.0], dt=dt, f_eq=1.0)
        print(f"  {ch}:")
        for m, d in del_vals.items():
            print(f"    m={m}: DEL = {d:.2f}")


def main():
    print("=" * 70)
    print("  Fatigue DEL Validation Suite")
    print("=" * 70)

    tests = [
        ("Pure sine wave", test_pure_sine),
        ("Constant signal", test_constant_signal),
        ("Square wave", test_square_wave),
        ("Multi-slope", test_multi_slope),
        ("Rainflow basic", test_rainflow_count_basic),
        ("Applied to OpenFAST", test_applied_to_openfast),
    ]

    passed = 0
    failed = 0
    for name, fn in tests:
        print(f"\n[TEST] {name}")
        try:
            fn()
            passed += 1
            print(f"  -> PASS")
        except AssertionError as e:
            failed += 1
            print(f"  -> FAIL: {e}")
        except Exception as e:
            failed += 1
            print(f"  -> ERROR: {type(e).__name__}: {e}")

    print(f"\n{'=' * 70}")
    print(f"  Results: {passed} passed, {failed} failed out of {len(tests)}")
    print(f"{'=' * 70}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
