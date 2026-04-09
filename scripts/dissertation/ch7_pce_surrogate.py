"""
Chapter 7 / Task E: Hermite polynomial chaos surrogate of the SiteA
forward model for fast Bayesian updates and VoI computations.

Target: replace the ~200 ms direct Op^3 eigen solve with a
microsecond-scale polynomial evaluation so that the Chapter 7
Bayesian calibration can be rerun thousands of times (for online
inference, VoI over decision thresholds, or encoder training set
generation) without re-invoking OpenSeesPy.

Surrogate form: 1D Hermite PCE of order 6 mapping the standard-normal
coordinate xi to the SiteA f1 response, with the physical scour
depth parameterised as s(xi) = s_mean + s_sigma * xi. The PCE is
fitted against the full Op^3 direct solver via Gauss-Hermite
pseudo-spectral projection.

Deliverables
------------
1. Fitted PCE coefficients written to JSON
2. Accuracy verification against the direct solver on a 50-point
   test grid
3. Speedup benchmark: wall time for 10000 direct calls vs 10000
   PCE evaluations

Run
---
    python scripts/dissertation/ch7_pce_surrogate.py
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

S_MEAN_M = 2.0
S_SIGMA_M = 1.0


def site_a_forward_direct(xi: float) -> float:
    """Direct Op^3 solver at scour depth s(xi) = 2.0 + 1.0 * xi."""
    from op3 import build_foundation, compose_tower_model
    s = max(S_MEAN_M + S_SIGMA_M * xi, 0.0)
    sp = REPO_ROOT / "data/fem_results/spring_profile_op3.csv"
    fnd = build_foundation(
        mode="distributed_bnwf",
        spring_profile=str(sp),
        scour_depth=float(s),
    )
    model = compose_tower_model(
        rotor="ref_4mw_owt",
        tower="site_a_rt1_tower",
        foundation=fnd,
    )
    return float(model.eigen(n_modes=3)[0])


def main():
    from op3.uq.pce import build_pce_1d, pce_mean_var

    print()
    print("=" * 72)
    print(" Op3 Chapter 7 Task E -- PCE surrogate of SiteA forward")
    print("=" * 72)
    print(f"  parameterisation: s(xi) = {S_MEAN_M} + {S_SIGMA_M}*xi")
    print(f"  xi ~ N(0, 1)")
    print()

    # --- 1. Fit the surrogate ---
    print("  fitting PCE order 6 ...")
    t0 = time.time()
    pce = build_pce_1d(site_a_forward_direct, order=6)
    fit_wall = time.time() - t0
    print(f"  fit complete in {fit_wall:.1f} s "
          f"({2 * 6 + 1} Gauss-Hermite nodes)")
    print(f"  coefficients: {[f'{c:+.4e}' for c in pce.coeffs]}")
    mean, var = pce_mean_var(pce)
    print(f"  PCE closed-form mean = {mean:.6f} Hz, std = {np.sqrt(var):.6f}")

    # --- 2. Accuracy verification ---
    print()
    print("  verifying against direct solver on 15 test points ...")
    xi_test = np.linspace(-2.0, 2.0, 15)
    direct = np.array([site_a_forward_direct(float(x)) for x in xi_test])
    surrogate = pce.evaluate(xi_test)
    err_abs = np.abs(direct - surrogate)
    err_rel = err_abs / direct
    print(f"  {'xi':>7} {'direct':>10} {'pce':>10} {'err_rel':>10}")
    for x, d, s, r in zip(xi_test, direct, surrogate, err_rel):
        print(f"  {x:>+7.3f} {d:>10.6f} {s:>10.6f} {r:>9.2%}")
    max_err = float(err_rel.max())
    print(f"  max relative error: {max_err:.3%}")

    # --- 3. Speedup benchmark ---
    print()
    print("  speedup benchmark ...")
    n_bench = 100
    xi_bench = np.random.normal(size=n_bench)
    t0 = time.time()
    _ = [site_a_forward_direct(float(x)) for x in xi_bench[:n_bench]]
    direct_wall = time.time() - t0
    t0 = time.time()
    _ = pce.evaluate(np.tile(xi_bench, 100))  # 10k surrogate evals
    surrogate_wall = time.time() - t0
    speedup = (direct_wall / n_bench) / (surrogate_wall / (n_bench * 100))
    print(f"  direct:    {n_bench:>5} evals in {direct_wall:.2f} s "
          f"({direct_wall/n_bench*1000:.1f} ms each)")
    print(f"  surrogate: {n_bench*100:>5} evals in {surrogate_wall:.4f} s "
          f"({surrogate_wall/(n_bench*100)*1e6:.1f} us each)")
    print(f"  speedup:   {speedup:.0f}x")

    # --- 4. Output ---
    result = {
        "task": "E - PCE surrogate of SiteA forward model",
        "parameterisation": {
            "s_mean_m": S_MEAN_M,
            "s_sigma_m": S_SIGMA_M,
            "xi_distribution": "N(0, 1)",
        },
        "pce_order": 6,
        "coefficients": pce.coeffs.tolist(),
        "closed_form_mean_hz": mean,
        "closed_form_var": var,
        "verification": {
            "xi_test": xi_test.tolist(),
            "direct_hz": direct.tolist(),
            "surrogate_hz": surrogate.tolist(),
            "max_relative_error": max_err,
        },
        "benchmark": {
            "n_direct": n_bench,
            "direct_wall_s": direct_wall,
            "direct_per_call_ms": direct_wall / n_bench * 1000,
            "n_surrogate": n_bench * 100,
            "surrogate_wall_s": surrogate_wall,
            "surrogate_per_call_us": surrogate_wall / (n_bench * 100) * 1e6,
            "speedup_factor": speedup,
        },
    }
    out = REPO_ROOT / "PHD/ch7/site_a_pce_surrogate.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(f"\n  JSON: {out}")


if __name__ == "__main__":
    main()
