"""
Chapter 7 / Task A: Bayesian identification of SiteA scour depth
from operational modal analysis (OMA) of the field measurement.

The dissertation defense question is:
    "Given a field-measured first natural frequency f1_meas, what is
     the posterior distribution of the scour depth s at the SiteA
     4 MW class tripod suction-bucket foundation?"

This script answers it by:

  1. Building the Op^3 SiteA example forward model that maps scour
     depth -> f1 via the apply_scour_relief() formula
     relief(z) = sqrt((z - s) / z)    for z > s
     = 0                              for z <= s
     applied to the distributed Winkler spring stiffness profile.

  2. Discretising scour depth s in [0, 4] m on an 81-point grid.

  3. Running ``op3.uq.bayesian.grid_bayesian_calibration`` with the
     SiteA field-measured f1 = 0.244 Hz and a measurement sigma
     that matches the Chapter 5 RANSAC OMA scatter.

  4. Producing posterior mean, std, 5/50/95 percentiles, and the
     full posterior PDF as a JSON artifact + Markdown figure caption
     that plugs directly into Chapter 7.

Reference
---------
This dissertation Chapter 5: field operational modal analysis of the
SiteA 4 MW class tripod OWT, 20,039 RANSAC windows, f1 = 0.244 Hz.

Run
---
    python scripts/dissertation/ch7_site_a_bayesian_scour.py
    python scripts/dissertation/ch7_site_a_bayesian_scour.py --sigma 0.005
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))


SITE_A_F1_MEASURED_HZ = 0.244
SITE_A_F1_SIGMA_HZ = 0.003   # typical RANSAC OMA scatter per PhD Ch.5


def site_a_forward(scour_depth_m: float) -> float:
    """
    Op^3 SiteA forward model: scour depth -> first natural frequency.
    Rebuilds the SiteA example each time with the given scour depth
    applied to the distributed BNWF spring profile via
    ``op3.foundations.apply_scour_relief``.
    """
    from op3 import build_foundation, compose_tower_model

    sp = REPO_ROOT / "data/fem_results/spring_profile_op3.csv"
    fnd = build_foundation(
        mode="distributed_bnwf",
        spring_profile=str(sp),
        scour_depth=float(scour_depth_m),
    )
    model = compose_tower_model(
        rotor="ref_4mw_owt",
        tower="site_a_rt1_tower",
        foundation=fnd,
    )
    return float(model.eigen(n_modes=3)[0])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--measured", type=float, default=SITE_A_F1_MEASURED_HZ,
                    help="Field-measured f1 in Hz (default 0.244 per Ch. 5)")
    ap.add_argument("--sigma", type=float, default=SITE_A_F1_SIGMA_HZ,
                    help="Measurement sigma in Hz (default 0.003)")
    ap.add_argument("--s-max", type=float, default=4.0,
                    help="Maximum scour depth on the grid (m)")
    ap.add_argument("--n-grid", type=int, default=81,
                    help="Grid resolution")
    ap.add_argument("--out", default="PHD/ch7/site_a_bayesian_scour.json",
                    help="Output JSON path relative to Op^3 repo root")
    args = ap.parse_args()

    from op3.uq.bayesian import grid_bayesian_calibration, normal_likelihood

    print()
    print("=" * 72)
    print(" Op3 Chapter 7 Task A -- SiteA Bayesian scour identification")
    print("=" * 72)
    print(f"  measured f1 : {args.measured} +/- {args.sigma} Hz")
    print(f"  grid        : [0, {args.s_max}] m, {args.n_grid} points")
    print()

    grid = np.linspace(0.0, args.s_max, args.n_grid)

    # Pre-evaluate forward model on the grid (slow step, ~200 ms per build)
    print("  pre-computing forward model on the grid ...")
    preds = np.zeros(args.n_grid)
    for i, s in enumerate(grid):
        preds[i] = site_a_forward(float(s))
        if i % 10 == 0:
            print(f"    s={s:5.2f} m  ->  f1={preds[i]:.4f} Hz")

    # Bayesian update
    likelihood = normal_likelihood(args.measured, args.sigma)
    lk = np.array([likelihood(float(p)) for p in preds])
    post_unnorm = lk   # uniform prior
    Z = float(np.trapz(post_unnorm, grid))
    if Z <= 0:
        raise ValueError(f"posterior unnormalisable: Z={Z}")
    post = post_unnorm / Z

    # Summary statistics
    cdf = np.concatenate(
        [[0.0], np.cumsum(0.5 * (post[1:] + post[:-1]) * np.diff(grid))]
    )
    cdf /= cdf[-1]

    def quantile(q: float) -> float:
        return float(np.interp(q, cdf, grid))

    mean = float(np.trapz(grid * post, grid))
    var = float(np.trapz((grid - mean) ** 2 * post, grid))
    std = float(np.sqrt(max(var, 0.0)))

    result = {
        "task": "A - SiteA Bayesian scour identification",
        "measurement": {
            "f1_Hz": args.measured,
            "sigma_Hz": args.sigma,
            "source": "PhD Chapter 5 field OMA, 20039 RANSAC windows",
        },
        "forward_model": {
            "framework": "Op^3 v0.3.2",
            "example": "04_site_a_ref4mw_tripod",
            "foundation_mode": "distributed_bnwf (Mode C)",
            "scour_relief": "sqrt((z - s) / z) applied to k(z)",
        },
        "grid": {
            "s_min_m": 0.0,
            "s_max_m": args.s_max,
            "n_points": args.n_grid,
        },
        "predictions_Hz": preds.tolist(),
        "grid_m": grid.tolist(),
        "posterior_pdf": post.tolist(),
        "posterior": {
            "mean_m": mean,
            "std_m": std,
            "p05_m": quantile(0.05),
            "p50_m": quantile(0.50),
            "p95_m": quantile(0.95),
            "credible_interval_90pct": [quantile(0.05), quantile(0.95)],
        },
    }

    out = REPO_ROOT / args.out
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2), encoding="utf-8")

    print()
    print("=" * 72)
    print(f" Posterior on SiteA scour depth s")
    print("=" * 72)
    print(f"  mean = {mean:.3f} m")
    print(f"  std  = {std:.3f} m")
    print(f"  5%   = {result['posterior']['p05_m']:.3f} m")
    print(f"  50%  = {result['posterior']['p50_m']:.3f} m")
    print(f"  95%  = {result['posterior']['p95_m']:.3f} m")
    print(f"  90%% credible interval: "
          f"[{result['posterior']['p05_m']:.2f}, "
          f"{result['posterior']['p95_m']:.2f}] m")
    print(f"\n  JSON written: {out}")


if __name__ == "__main__":
    main()
