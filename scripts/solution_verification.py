"""
Solution verification: mesh and time-step convergence (Task 2.4).

Refines (1) the spatial discretisation N_SEG and (2) the transient
time step dt on the same analytical cantilever used in
``tests/test_code_verification.py``, and reports the discretisation
error vs the closed-form Euler-Bernoulli reference.

A converged solution should:
  - approach the analytical f1 monotonically as N_SEG -> infinity
  - approach the analytical period as dt -> 0
  - show the expected order of accuracy
    (elastic beam: O(h^2) for f, O(dt^2) for Newmark average accel)

Run:
    python scripts/solution_verification.py
Output:
    validation/benchmarks/solution_verification.json + printed table.
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import numpy as np

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

# Reuse the cantilever fixture from the verification suite so that
# parameters cannot drift between scripts.
from tests.test_code_verification import (  # noqa: E402
    A, E, EI, G, Iy, Iz, Jx, L, RHO, m_per_L,
    analytical_cantilever_freq,
)


def build_cantilever_n(n_seg: int, tip_mass: float = 0.0) -> int:
    import openseespy.opensees as ops
    ops.wipe()
    ops.model("basic", "-ndm", 3, "-ndf", 6)

    base = 1000
    zs = np.linspace(0.0, L, n_seg + 1)
    for i, z in enumerate(zs):
        ops.node(base + i, 0.0, 0.0, float(z))
    ops.fix(base, 1, 1, 1, 1, 1, 1)

    ops.geomTransf("Linear", 1, 0.0, 1.0, 0.0)
    for i in range(n_seg):
        ops.element(
            "elasticBeamColumn",
            1000 + i + 1,
            base + i, base + i + 1,
            A, E, G, Jx, Iy, Iz,
            1,
            "-mass", m_per_L,
        )
    tip = base + n_seg
    if tip_mass > 0:
        ops.mass(tip, tip_mass, tip_mass, tip_mass, 1.0, 1.0, 1.0)
    return tip


def first_freq() -> float:
    import openseespy.opensees as ops
    ev = ops.eigen("-fullGenLapack", 1)
    return math.sqrt(ev[0]) / (2 * math.pi)


def transient_period(n_seg: int, dt: float, duration: float = 5.0) -> float:
    """Plucked cantilever: prescribe initial tip displacement, free vibrate,
    measure period from zero crossings."""
    import openseespy.opensees as ops
    tip = build_cantilever_n(n_seg)

    # Initial-condition by static load then release: apply tip load,
    # solve static, then run transient with no load.
    ops.timeSeries("Linear", 1)
    ops.pattern("Plain", 1, 1)
    ops.load(tip, 1.0e6, 0.0, 0.0, 0.0, 0.0, 0.0)
    ops.system("BandGeneral")
    ops.numberer("RCM")
    ops.constraints("Plain")
    ops.integrator("LoadControl", 1.0)
    ops.algorithm("Linear")
    ops.analysis("Static")
    ops.analyze(1)
    ops.loadConst("-time", 0.0)
    ops.remove("loadPattern", 1)

    ops.wipeAnalysis()
    ops.system("BandGeneral")
    ops.numberer("RCM")
    ops.constraints("Plain")
    ops.integrator("Newmark", 0.5, 0.25)
    ops.algorithm("Linear")
    ops.analysis("Transient")

    n_steps = int(duration / dt)
    times, ux = [], []
    for k in range(n_steps):
        ops.analyze(1, dt)
        times.append((k + 1) * dt)
        ux.append(float(ops.nodeDisp(tip, 1)))

    # Peak-to-peak period via zero crossings of (u - mean)
    u = np.asarray(ux) - np.mean(ux)
    sign = np.sign(u)
    zc = np.where(np.diff(sign) != 0)[0]
    if len(zc) < 2:
        return float("nan")
    # Two zero crossings = one half-period
    crossings = np.asarray(times)[zc]
    half_periods = np.diff(crossings)
    return float(2.0 * np.mean(half_periods))


def main():
    f_ref = analytical_cantilever_freq()
    T_ref = 1.0 / f_ref

    print()
    print("=" * 72)
    print(" Op3 solution verification -- Task 2.4")
    print("=" * 72)
    print(f" Reference (analytical): f1 = {f_ref:.6f} Hz, T = {T_ref:.6f} s")
    print()

    # ---- Mesh convergence ----
    mesh_results = []
    print("  Mesh convergence (eigen):")
    print(f"  {'N_seg':>6}  {'f1 [Hz]':>12}  {'err':>10}  {'order':>8}")
    print("  " + "-" * 48)
    prev_err = None
    for n in [5, 10, 20, 40, 80, 160]:
        build_cantilever_n(n)
        f = first_freq()
        err = (f - f_ref) / f_ref
        order = ""
        if prev_err is not None and abs(err) > 0:
            order = f"{math.log2(abs(prev_err) / abs(err)):.2f}"
        prev_err = err
        mesh_results.append({"n_seg": n, "f1_hz": f, "rel_err": err, "order": order})
        print(f"  {n:>6}  {f:>12.6f}  {err:>+9.3%}  {order:>8}")

    # ---- Time-step convergence ----
    print()
    print("  Time-step convergence (transient, N_seg = 40):")
    print(f"  {'dt [s]':>9}  {'T [s]':>12}  {'f [Hz]':>12}  {'err':>10}")
    print("  " + "-" * 50)
    dt_results = []
    for dt in [0.05, 0.02, 0.01, 0.005, 0.002]:
        T = transient_period(40, dt, duration=8.0)
        f = 1.0 / T if T == T else float("nan")
        err = (f - f_ref) / f_ref if T == T else float("nan")
        dt_results.append({"dt_s": dt, "period_s": T, "f1_hz": f, "rel_err": err})
        print(f"  {dt:>9.4f}  {T:>12.6f}  {f:>12.6f}  {err:>+9.3%}")

    out = REPO_ROOT / "validation/benchmarks/solution_verification.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(
        {"reference_f1_hz": f_ref,
         "mesh_convergence": mesh_results,
         "dt_convergence": dt_results},
        indent=2), encoding="utf-8")
    print(f"\n  JSON written: {out}\n")


if __name__ == "__main__":
    main()
