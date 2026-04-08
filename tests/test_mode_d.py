"""
Mode D dissipation-weighted formulation V&V (Phase 3 / Task 3.4 wiring).

Asserts the falsification gates listed in
docs/MODE_D_DISSIPATION_WEIGHTED.md section 4.

Invariants
----------
1. w(D=0) = 1                       (untouched soil keeps full stiffness)
2. w(D=D_max) = beta                (yielded soil reduced to floor)
3. w in [beta, 1] for all D         (bounded)
4. w monotone non-increasing in D
5. Mode D reduces to Mode C exactly when alpha = 0 OR when
   dissipation column is uniformly zero
6. Higher alpha => lower per-spring stiffness at any D > 0
7. Mode D end-to-end: composer.eigen() runs and returns f1 lower than
   the Mode C baseline (more flex from yielded layers)
8. Foundation diagnostics expose alpha, beta, w_min, w_max

Run:
    python tests/test_mode_d.py
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from op3 import build_foundation, compose_tower_model  # noqa: E402


# ---------------------------------------------------------------------------
# Synthetic spring + dissipation tables
# ---------------------------------------------------------------------------

def _spring_csv(path: Path) -> Path:
    df = pd.DataFrame({
        "depth_m":         np.linspace(0.0, 30.0, 16),
        "k_ini_kN_per_m":  np.linspace(5.0e4, 2.0e5, 16),
        "p_ult_kN_per_m":  np.linspace(2.0e3, 1.2e4, 16),
        "spring_type":     ["lateral"] * 16,
    })
    df.to_csv(path, index=False)
    return path


def _dissipation_csv(path: Path, peak_depth: float = 5.0) -> Path:
    """Triangular dissipation profile peaking near the mudline."""
    depth = np.linspace(0.0, 30.0, 16)
    D = 100.0 * np.exp(-((depth - peak_depth) / 6.0) ** 2)
    df = pd.DataFrame({"depth_m": depth, "D_total_kJ": D})
    df.to_csv(path, index=False)
    return path


def _zero_dissipation_csv(path: Path) -> Path:
    df = pd.DataFrame({
        "depth_m": np.linspace(0.0, 30.0, 16),
        "D_total_kJ": np.zeros(16),
    })
    df.to_csv(path, index=False)
    return path


# ---------------------------------------------------------------------------
# Pure-formula tests
# ---------------------------------------------------------------------------

def _w(D, alpha, beta, D_max):
    if D_max <= 0:
        return 1.0
    return beta + (1.0 - beta) * max(1.0 - D / D_max, 0.0) ** alpha


def test_w_at_zero_is_one():
    print(f"  [3.4.1] w(0) = {_w(0, 1.0, 0.05, 10):.4f}")
    assert _w(0.0, 1.0, 0.05, 10.0) == 1.0


def test_w_at_dmax_is_beta():
    beta = 0.05
    val = _w(10.0, 1.0, beta, 10.0)
    print(f"  [3.4.2] w(D_max) = {val:.4f}, beta = {beta:.4f}")
    assert abs(val - beta) < 1e-12


def test_w_bounded():
    for alpha in [0.5, 1.0, 2.0, 4.0]:
        for D in np.linspace(0, 10, 25):
            v = _w(float(D), alpha, 0.05, 10.0)
            assert 0.05 - 1e-12 <= v <= 1.0 + 1e-12, f"w out of bounds: {v}"
    print(f"  [3.4.3] w bounded in [beta, 1] across alpha sweep")


def test_w_monotone_in_D():
    for alpha in [0.5, 1.0, 2.0, 4.0]:
        Ds = np.linspace(0, 10, 50)
        vs = np.array([_w(float(D), alpha, 0.05, 10.0) for D in Ds])
        diffs = np.diff(vs)
        assert diffs.max() <= 1e-12, f"w not monotone for alpha={alpha}"
    print(f"  [3.4.4] w monotone non-increasing in D for all alpha")


# ---------------------------------------------------------------------------
# Builder integration tests
# ---------------------------------------------------------------------------

def _build_model(mode: str, springs: Path, dissipation: Path | None = None,
                 alpha: float = 1.0, beta: float = 0.05):
    fnd = build_foundation(
        mode=mode,
        spring_profile=str(springs),
        ogx_dissipation=str(dissipation) if dissipation else None,
        mode_d_alpha=alpha, mode_d_beta=beta,
    )
    return compose_tower_model(
        rotor="nrel_5mw_baseline",
        tower="nrel_5mw_oc3_tower",
        foundation=fnd,
    )


def test_zero_dissipation_equals_mode_C():
    """Mode D with all-zero D must give bit-identical f1 to Mode C."""
    with tempfile.TemporaryDirectory() as tmp:
        springs = _spring_csv(Path(tmp) / "springs.csv")
        diss = _zero_dissipation_csv(Path(tmp) / "diss.csv")
        f_C = float(_build_model("distributed_bnwf", springs).eigen(n_modes=3)[0])
        f_D = float(_build_model("dissipation_weighted", springs, diss,
                                 alpha=1.0).eigen(n_modes=3)[0])
        print(f"  [3.4.5] zero-D: f_C={f_C:.6f}  f_D={f_D:.6f}")
        assert abs(f_C - f_D) / f_C < 1e-6


def test_alpha_monotone_lowers_f1():
    """Increasing alpha at fixed D must lower the head stiffness, hence f1."""
    with tempfile.TemporaryDirectory() as tmp:
        springs = _spring_csv(Path(tmp) / "springs.csv")
        diss = _dissipation_csv(Path(tmp) / "diss.csv")
        freqs = []
        for alpha in [0.0, 0.5, 1.0, 2.0, 4.0]:
            f = float(_build_model("dissipation_weighted", springs, diss,
                                   alpha=alpha).eigen(n_modes=3)[0])
            freqs.append(f)
        print(f"  [3.4.6] f1(alpha) = {[round(f,5) for f in freqs]}")
        diffs = np.diff(freqs)
        assert (diffs <= 1e-9).all(), \
            f"f1 should not increase with alpha: diffs={diffs}"


def test_diagnostics_exposed():
    """The Foundation should expose alpha/beta/w_min/w_max in its
    attach diagnostics for V&V auditing."""
    with tempfile.TemporaryDirectory() as tmp:
        springs = _spring_csv(Path(tmp) / "springs.csv")
        diss = _dissipation_csv(Path(tmp) / "diss.csv")
        fnd = build_foundation(
            mode="dissipation_weighted",
            spring_profile=str(springs),
            ogx_dissipation=str(diss),
            mode_d_alpha=2.0, mode_d_beta=0.10,
        )
        # Trigger build to populate diagnostics
        model = compose_tower_model(
            rotor="nrel_5mw_baseline",
            tower="nrel_5mw_oc3_tower",
            foundation=fnd,
        )
        model.eigen(n_modes=3)
        diag = fnd.diagnostics
        print(f"  [3.4.7] diagnostics: alpha={diag.get('mode_d_alpha')}, "
              f"beta={diag.get('mode_d_beta')}, "
              f"w in [{diag.get('mode_d_w_min'):.3f}, {diag.get('mode_d_w_max'):.3f}]")
        assert diag.get("mode_d_alpha") == 2.0
        assert diag.get("mode_d_beta") == 0.10
        assert 0.05 <= diag["mode_d_w_min"] <= diag["mode_d_w_max"] <= 1.0


def test_dissipation_lowers_f1_vs_mode_C():
    """With non-zero dissipation, Mode D's f1 must be < Mode C's f1."""
    with tempfile.TemporaryDirectory() as tmp:
        springs = _spring_csv(Path(tmp) / "springs.csv")
        diss = _dissipation_csv(Path(tmp) / "diss.csv")
        f_C = float(_build_model("distributed_bnwf", springs).eigen(n_modes=3)[0])
        f_D = float(_build_model("dissipation_weighted", springs, diss,
                                 alpha=2.0).eigen(n_modes=3)[0])
        print(f"  [3.4.8] f_C={f_C:.5f}  f_D(alpha=2)={f_D:.5f}")
        assert f_D < f_C


# ---------------------------------------------------------------------------
# Standalone runner
# ---------------------------------------------------------------------------

def main():
    print()
    print("=" * 70)
    print(" Op3 Mode D dissipation-weighted V&V -- Task 3.4 wiring")
    print("=" * 70)
    tests = [
        test_w_at_zero_is_one,
        test_w_at_dmax_is_beta,
        test_w_bounded,
        test_w_monotone_in_D,
        test_zero_dissipation_equals_mode_C,
        test_alpha_monotone_lowers_f1,
        test_diagnostics_exposed,
        test_dissipation_lowers_f1_vs_mode_C,
    ]
    fails = 0
    for t in tests:
        # Reset OpenSeesPy global domain between tests (Linux CI fix).
        try:
            import openseespy.opensees as _ops
            _ops.wipe()
        except Exception:
            pass
        try:
            t()
        except AssertionError as e:
            print(f"  FAIL: {t.__name__}: {e}")
            fails += 1
        except Exception as e:
            print(f"  ERROR: {t.__name__}: {type(e).__name__}: {e}")
            fails += 1
    print("=" * 70)
    print(f" {len(tests) - fails}/{len(tests)} Mode D invariants held")
    print("=" * 70)
    return fails


if __name__ == "__main__":
    sys.exit(main())
