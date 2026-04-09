"""
Chapter 6 / Task B: Mode D dissipation-weighted formulation
calibration on the SiteA 4 MW class tripod.

Closes the fourth falsification gate from docs/MODE_D_DISSIPATION_WEIGHTED.md
section 4: fit (alpha, beta) against the field-measured first
natural frequency f1 = 0.244 Hz (PhD Ch. 5 OMA) by minimising the
posterior mismatch over a 2D grid.

Strategy
--------
1. Load the SiteA dissipation profile (data/fem_results/dissipation_profile.csv).
2. Build the Mode D foundation over a grid alpha x beta.
3. For each (alpha, beta), compute f1 via Op^3 eigen.
4. Form a 2D Gaussian-likelihood posterior p(alpha, beta | f1_meas)
   with uniform prior on [alpha, beta] in [0.5, 4] x [0.02, 0.20].
5. Report the MAP and the marginal posterior means.

Run
---
    python scripts/dissertation/ch6_mode_d_site_a_calibration.py
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
SITE_A_F1_SIGMA_HZ = 0.003


def site_a_mode_d_forward(alpha: float, beta: float) -> float:
    """Op^3 SiteA Mode D forward model."""
    from op3 import build_foundation, compose_tower_model

    sp = REPO_ROOT / "data/fem_results/spring_profile_op3.csv"
    ds = REPO_ROOT / "data/fem_results/dissipation_profile.csv"
    fnd = build_foundation(
        mode="dissipation_weighted",
        spring_profile=str(sp),
        ogx_dissipation=str(ds),
        mode_d_alpha=float(alpha),
        mode_d_beta=float(beta),
    )
    model = compose_tower_model(
        rotor="ref_4mw_owt",
        tower="site_a_rt1_tower",
        foundation=fnd,
    )
    return float(model.eigen(n_modes=3)[0])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--alpha-min", type=float, default=0.5)
    ap.add_argument("--alpha-max", type=float, default=4.0)
    ap.add_argument("--n-alpha", type=int, default=11)
    ap.add_argument("--beta-min", type=float, default=0.02)
    ap.add_argument("--beta-max", type=float, default=0.20)
    ap.add_argument("--n-beta", type=int, default=7)
    ap.add_argument("--measured", type=float, default=SITE_A_F1_MEASURED_HZ)
    ap.add_argument("--sigma", type=float, default=SITE_A_F1_SIGMA_HZ)
    ap.add_argument("--out", default="PHD/ch6/site_a_mode_d_calibration.json")
    args = ap.parse_args()

    alpha_grid = np.linspace(args.alpha_min, args.alpha_max, args.n_alpha)
    beta_grid = np.linspace(args.beta_min, args.beta_max, args.n_beta)

    print()
    print("=" * 72)
    print(" Op3 Chapter 6 Task B -- Mode D SiteA calibration")
    print("=" * 72)
    print(f"  alpha grid : {args.alpha_min} .. {args.alpha_max} ({args.n_alpha} pts)")
    print(f"  beta grid  : {args.beta_min} .. {args.beta_max} ({args.n_beta} pts)")
    print(f"  total runs : {args.n_alpha * args.n_beta}")
    print(f"  measured   : {args.measured} +/- {args.sigma} Hz")
    print()

    preds = np.zeros((args.n_alpha, args.n_beta))
    for i, a in enumerate(alpha_grid):
        for j, b in enumerate(beta_grid):
            try:
                preds[i, j] = site_a_mode_d_forward(float(a), float(b))
            except Exception as e:
                print(f"  [{i},{j}] a={a:.2f} b={b:.3f}: ERROR {type(e).__name__}")
                preds[i, j] = float("nan")
        print(f"  alpha={a:.2f}: f1 range = [{np.nanmin(preds[i]):.4f}, "
              f"{np.nanmax(preds[i]):.4f}] Hz")

    # 2D Gaussian likelihood, uniform prior -> posterior
    residual = preds - args.measured
    loglik = -0.5 * (residual / args.sigma) ** 2
    loglik -= np.nanmax(loglik)  # numerical stability
    post = np.exp(loglik)
    post[np.isnan(post)] = 0.0
    # Normalise over the 2D grid via trapezoidal rule
    da = alpha_grid[1] - alpha_grid[0]
    db = beta_grid[1] - beta_grid[0]
    Z = float(np.sum(post) * da * db)
    post /= Z if Z > 0 else 1.0

    # MAP
    idx = np.unravel_index(np.nanargmax(post), post.shape)
    alpha_map = float(alpha_grid[idx[0]])
    beta_map = float(beta_grid[idx[1]])
    f1_map = float(preds[idx])

    # Marginal means
    post_alpha = np.sum(post, axis=1) * db
    post_beta = np.sum(post, axis=0) * da
    alpha_mean = float(np.sum(alpha_grid * post_alpha) * da / (np.sum(post_alpha) * da))
    beta_mean = float(np.sum(beta_grid * post_beta) * db / (np.sum(post_beta) * db))

    result = {
        "task": "B - Mode D SiteA calibration",
        "measurement": {
            "f1_Hz": args.measured,
            "sigma_Hz": args.sigma,
            "source": "PhD Chapter 5 field OMA, 20039 RANSAC windows",
        },
        "grid": {
            "alpha": alpha_grid.tolist(),
            "beta": beta_grid.tolist(),
        },
        "predictions_Hz": preds.tolist(),
        "posterior": post.tolist(),
        "MAP": {
            "alpha": alpha_map,
            "beta": beta_map,
            "f1_Hz_at_MAP": f1_map,
            "error_from_measured_Hz": f1_map - args.measured,
        },
        "marginal_means": {
            "alpha_mean": alpha_mean,
            "beta_mean": beta_mean,
        },
    }

    out = REPO_ROOT / args.out
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2), encoding="utf-8")

    print()
    print("=" * 72)
    print(f" Mode D MAP estimate for SiteA")
    print("=" * 72)
    print(f"  alpha_MAP = {alpha_map:.3f}")
    print(f"  beta_MAP  = {beta_map:.3f}")
    print(f"  f1 at MAP = {f1_map:.4f} Hz (measured {args.measured})")
    print(f"  error     = {(f1_map - args.measured)*1000:+.1f} mHz")
    print()
    print(f"  alpha_mean (marginal) = {alpha_mean:.3f}")
    print(f"  beta_mean  (marginal) = {beta_mean:.3f}")
    print(f"\n  JSON written: {out}")


if __name__ == "__main__":
    main()
