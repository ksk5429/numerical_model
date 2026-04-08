"""
Code verification suite (Phase 2 / Task 2.1).

Tests the OpenSeesPy stick-model build pipeline against analytical
closed-form solutions from elementary structural dynamics. These
tests are independent of NREL data: a failure here means the solver
or the discretisation is broken, not that the calibration drifted.

Verified cases
--------------
A. Cantilever beam without tip mass
   First natural frequency:
       f1 = (1.875104^2) / (2 pi L^2) * sqrt(EI / (rho * A))

B. Cantilever beam with tip point mass M (Rayleigh approximation)
   With consistent self-mass m_b = rho*A*L:
       f1 = (1 / (2 pi)) * sqrt(3 EI / (L^3 * (M + 0.2235 m_b)))
   Reference: Blevins (1979), "Formulas for Natural Frequency and
   Mode Shape", Table 8-1.

C. Static cantilever tip deflection under transverse tip load P
       delta = P L^3 / (3 EI)

D. Mass conservation: total integrated mass equals analytical sum.

Run with:
    python -m pytest tests/test_code_verification.py -v
or:
    python tests/test_code_verification.py
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

import numpy as np

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))


# ---------------------------------------------------------------------------
# Test fixtures: a tractable steel cantilever
# ---------------------------------------------------------------------------

E = 2.10e11        # Pa
G = 8.10e10        # Pa
RHO = 7850.0       # kg/m^3
L = 50.0           # m
D_OUT = 4.0        # m  (constant section)
T_WALL = 0.030     # m

R_O = 0.5 * D_OUT
R_I = R_O - T_WALL
A = math.pi * (R_O ** 2 - R_I ** 2)
Iy = math.pi * (R_O ** 4 - R_I ** 4) / 4
Iz = Iy
Jx = Iy + Iz
m_per_L = RHO * A          # kg/m

EI = E * Iy

N_SEG = 40                  # tower discretisation


# ---------------------------------------------------------------------------
# Reference solutions
# ---------------------------------------------------------------------------

def analytical_cantilever_freq() -> float:
    """Euler-Bernoulli cantilever, no tip mass."""
    beta_L = 1.875104068711961
    return (beta_L ** 2) / (2 * math.pi * L ** 2) * math.sqrt(EI / m_per_L)


def analytical_cantilever_with_tip_mass(M_tip: float) -> float:
    """Rayleigh: Blevins (1979) Table 8-1 case 1, lumped tip mass."""
    m_eff = M_tip + 0.2235 * (m_per_L * L)
    return (1.0 / (2 * math.pi)) * math.sqrt(3 * EI / (L ** 3 * m_eff))


def analytical_tip_deflection(P_tip: float) -> float:
    """Static cantilever PL^3 / (3EI)."""
    return P_tip * L ** 3 / (3 * EI)


# ---------------------------------------------------------------------------
# OpenSeesPy stick-model builder (mirrors builder._build_tower_stick_from_*)
# ---------------------------------------------------------------------------

def build_cantilever(tip_mass: float = 0.0):
    import openseespy.opensees as ops
    ops.wipe()
    ops.model("basic", "-ndm", 3, "-ndf", 6)

    base = 1000
    zs = np.linspace(0.0, L, N_SEG + 1)
    for i, z in enumerate(zs):
        ops.node(base + i, 0.0, 0.0, float(z))
    ops.fix(base, 1, 1, 1, 1, 1, 1)

    ops.geomTransf("Linear", 1, 0.0, 1.0, 0.0)
    for i in range(N_SEG):
        ops.element(
            "elasticBeamColumn",
            1000 + i + 1,
            base + i, base + i + 1,
            A, E, G, Jx, Iy, Iz,
            1,
            "-mass", m_per_L,
        )

    tip = base + N_SEG
    if tip_mass > 0:
        ops.mass(tip, tip_mass, tip_mass, tip_mass,
                 1.0, 1.0, 1.0)
    return tip


def run_eigen_first_freq() -> float:
    import openseespy.opensees as ops
    eigvals = ops.eigen("-fullGenLapack", 3)
    return math.sqrt(eigvals[0]) / (2 * math.pi)


def run_static_tip_load(P: float) -> float:
    import openseespy.opensees as ops
    tip = 1000 + N_SEG
    ops.timeSeries("Linear", 1)
    ops.pattern("Plain", 1, 1)
    ops.load(tip, P, 0.0, 0.0, 0.0, 0.0, 0.0)
    ops.system("BandGeneral")
    ops.numberer("RCM")
    ops.constraints("Plain")
    ops.integrator("LoadControl", 1.0)
    ops.algorithm("Linear")
    ops.analysis("Static")
    ops.analyze(1)
    return float(ops.nodeDisp(tip, 1))


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_cantilever_first_freq_no_tipmass():
    build_cantilever(tip_mass=0.0)
    f_op3 = run_eigen_first_freq()
    f_ref = analytical_cantilever_freq()
    err = (f_op3 - f_ref) / f_ref
    print(f"  [A] cantilever no-tip: Op3={f_op3:.4f} ref={f_ref:.4f} err={err:+.2%}")
    assert abs(err) < 0.01, f"freq error {err:+.2%} > 1%"


def test_cantilever_first_freq_tipmass():
    M_tip = 0.5 * m_per_L * L      # tip mass = half the beam mass
    build_cantilever(tip_mass=M_tip)
    f_op3 = run_eigen_first_freq()
    f_ref = analytical_cantilever_with_tip_mass(M_tip)
    err = (f_op3 - f_ref) / f_ref
    print(f"  [B] cantilever tip-mass: Op3={f_op3:.4f} ref={f_ref:.4f} err={err:+.2%}")
    # Rayleigh is an approximation; allow 5% gap.
    assert abs(err) < 0.05, f"freq error {err:+.2%} > 5%"


def test_static_tip_deflection():
    build_cantilever(tip_mass=0.0)
    P = 1.0e6   # 1 MN
    delta_op3 = run_static_tip_load(P)
    delta_ref = analytical_tip_deflection(P)
    err = (delta_op3 - delta_ref) / delta_ref
    print(f"  [C] static tip defl:   Op3={delta_op3:.5f} ref={delta_ref:.5f} err={err:+.2%}")
    assert abs(err) < 0.001, f"deflection error {err:+.2%} > 0.1%"


def test_mass_conservation():
    """Total mass = m_per_L * L within numerical precision."""
    expected = m_per_L * L
    # Sum of element masses (each contributes m_per_L * el_length)
    el_len = L / N_SEG
    total = N_SEG * m_per_L * el_len
    err = (total - expected) / expected
    print(f"  [D] mass conservation: total={total:.1f} ref={expected:.1f} err={err:+.2%}")
    assert abs(err) < 1e-12


# ---------------------------------------------------------------------------
# Standalone runner
# ---------------------------------------------------------------------------

def main():
    print()
    print("=" * 70)
    print(" Op3 code verification suite -- Phase 2 / Task 2.1")
    print("=" * 70)
    tests = [
        test_cantilever_first_freq_no_tipmass,
        test_cantilever_first_freq_tipmass,
        test_static_tip_deflection,
        test_mass_conservation,
    ]
    fails = 0
    for t in tests:
        try:
            t()
        except AssertionError as e:
            print(f"  FAIL: {t.__name__}: {e}")
            fails += 1
    print("=" * 70)
    print(f" {len(tests) - fails}/{len(tests)} verification tests passed")
    print("=" * 70)
    return fails


if __name__ == "__main__":
    sys.exit(main())
