"""
Sensitivity invariants (V&V Task 2.6).

Whereas ``scripts/calibration_tornado.py`` produces a numerical
ranking, these tests assert *physical invariants* on the ranking.
They are intentionally loose-numerically and tight-physically: the
exact swing percentages depend on the specific tower, but the
*relative ordering* of inputs is a fundamental consequence of
$f \\propto \\sqrt{EI/m}$ and Rayleigh ratios. If a future code change
breaks one of these invariants, something is structurally wrong.

Asserted invariants
-------------------
1. Tower EI is the dominant lever (largest swing in the tornado).
2. Nacelle yaw inertia (NacYIner) has < 0.1% effect on f1
   (yaw axis decouples from bending).
3. Tower EI sensitivity is positive (stiffer -> higher frequency).
4. Mass-side inputs (nac_mass, hub_mass, blade_mass, tower_mass)
   are all negative (more mass -> lower frequency).
5. Tower mass and tower EI swings have opposite signs and the
   tower-EI swing is at least 5x the tower-mass swing
   (Rayleigh's quotient).

Run:
    python tests/test_sensitivity.py
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from scripts.calibration_tornado import tornado  # noqa: E402

EXAMPLE = "02_nrel_5mw_oc3_monopile"   # most accurately calibrated case
PCT = 0.10


def _by_param(rows):
    return {r["parameter"]: r for r in rows}


def test_tower_EI_dominates():
    result = tornado(EXAMPLE, PCT)
    rows = result["rows"]   # already sorted by |swing|
    top = rows[0]
    print(f"  [1] dominant lever: {top['parameter']} swing={top['swing_pct']:+.2f}%")
    assert top["parameter"] == "tower_EI", (
        f"expected tower_EI dominant, got {top['parameter']}")


def test_nac_yiner_negligible():
    result = tornado(EXAMPLE, PCT)
    by = _by_param(result["rows"])
    swing = abs(by["nac_yiner"]["swing_pct"])
    print(f"  [2] nac_yiner swing = {swing:.4f}% (must be < 0.1%)")
    assert swing < 0.1, f"nac_yiner sensitivity {swing}% > 0.1%"


def test_tower_EI_positive():
    result = tornado(EXAMPLE, PCT)
    by = _by_param(result["rows"])
    plus = by["tower_EI"]["df_plus_pct"]
    print(f"  [3] +10% EI -> {plus:+.2f}% f1 (must be > 0)")
    assert plus > 0, f"stiffening tower must raise f1, got {plus}%"


def test_mass_inputs_negative():
    result = tornado(EXAMPLE, PCT)
    by = _by_param(result["rows"])
    for key in ["nac_mass", "hub_mass", "blade_mass", "tower_mass"]:
        plus = by[key]["df_plus_pct"]
        print(f"  [4] +10% {key:<12} -> {plus:+.2f}% f1 (must be < 0)")
        assert plus < 0, f"adding mass via {key} should lower f1, got {plus}%"


def test_tower_EI_dominates_tower_mass():
    """Rayleigh: f ~ sqrt(EI/m). Equal % perturbations should give EI
    a swing comparable to mass, but EI's effect is much larger because
    only the tower mass changes (not the dominant nacelle mass)."""
    result = tornado(EXAMPLE, PCT)
    by = _by_param(result["rows"])
    ei = abs(by["tower_EI"]["swing_pct"])
    tm = abs(by["tower_mass"]["swing_pct"])
    ratio = ei / max(tm, 1e-12)
    print(f"  [5] |EI swing| / |tower-mass swing| = {ratio:.1f}  (must be > 5)")
    assert ratio > 5, f"tower_EI should dominate tower_mass, ratio={ratio:.1f}"


# ---------------------------------------------------------------------------
# Standalone runner
# ---------------------------------------------------------------------------

def main():
    print()
    print("=" * 70)
    print(" Op3 sensitivity invariants -- V&V Task 2.6")
    print("=" * 70)
    tests = [
        test_tower_EI_dominates,
        test_nac_yiner_negligible,
        test_tower_EI_positive,
        test_mass_inputs_negative,
        test_tower_EI_dominates_tower_mass,
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
            print(f"  ERROR: {t.__name__}: {e}")
            fails += 1
    print("=" * 70)
    print(f" {len(tests) - fails}/{len(tests)} sensitivity invariants held")
    print("=" * 70)
    return fails


if __name__ == "__main__":
    sys.exit(main())
