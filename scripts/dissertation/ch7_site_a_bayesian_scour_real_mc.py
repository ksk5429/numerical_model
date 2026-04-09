"""
Chapter 7 / Task A (v2): Bayesian identification of SiteA scour
depth from OMA, driven by the REAL 1794-sample MC database.

Upgrade over the v1 script that used the Op^3 eigen rebuild: this
version uses the real OptumGX + OpenSeesPy coupled results stored
in ``F:/TREE_OF_THOUGHT/PHD/data/integrated_database_1794.csv``
as the forward model. No synthetic Op^3 re-solve.

Procedure
---------
1. Load the 1794-row SiteA MC database via
   ``op3.uq.encoder_bridge.load_site_a_mc()``.
2. Treat each row as a joint (scour, su0, k_su) -> f1 sample.
3. For the field-measured f1 = 0.244 Hz, form a likelihood weight
   over all 1794 rows:
       w_i = N(f1_meas | f1_i, sigma)
   where sigma comes from the Ch. 5 RANSAC OMA scatter.
4. Compute the weighted marginal posterior on scour depth by
   resampling the MC rows with weights w_i and binning in 0.25 m
   scour intervals. This is the importance-sampling posterior.
5. Also compute marginal posteriors on su0 and k_su for completeness.

Deliverables
------------
- Posterior mean, std, 5/50/95 percentiles on scour_m, su0, k_su
- Full posterior histograms as JSON
- Goes into Chapter 7 as the numerical backbone of the prescriptive
  maintenance framework.

Run
---
    python scripts/dissertation/ch7_site_a_bayesian_scour_real_mc.py
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


def weighted_stats(values: np.ndarray, weights: np.ndarray) -> dict:
    """Importance-sampling summary statistics."""
    w = weights / weights.sum()
    mean = float(np.sum(values * w))
    var = float(np.sum((values - mean) ** 2 * w))
    std = float(np.sqrt(max(var, 0.0)))
    # Weighted quantiles
    order = np.argsort(values)
    sv = values[order]
    sw = w[order]
    cdf = np.cumsum(sw)
    cdf /= cdf[-1]
    def q(p: float) -> float:
        return float(np.interp(p, cdf, sv))
    return {
        "mean": mean,
        "std": std,
        "p05": q(0.05),
        "p50": q(0.50),
        "p95": q(0.95),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--measured", type=float, default=SITE_A_F1_MEASURED_HZ)
    ap.add_argument("--sigma", type=float, default=SITE_A_F1_SIGMA_HZ)
    ap.add_argument("--out",
                    default="PHD/ch7/site_a_bayesian_scour_real_mc.json")
    args = ap.parse_args()

    from op3.uq.encoder_bridge import load_site_a_mc

    print()
    print("=" * 72)
    print(" Op3 Ch.7 Task A (v2) -- Bayesian scour ID from REAL 1794 MC")
    print("=" * 72)
    df = load_site_a_mc()
    print(f"  database   : {len(df)} MC runs")
    print(f"  scour range: {df.scour_m.min():.2f} -> {df.scour_m.max():.2f} m")
    print(f"  f1 range   : {df.f1_Hz.min():.4f} -> {df.f1_Hz.max():.4f} Hz")
    print(f"  su0 range  : {df.su0.min():.2f} -> {df.su0.max():.2f} kPa")
    print(f"  k_su range : {df.k_su.min():.2f} -> {df.k_su.max():.2f} kPa/m")
    print()
    print(f"  measured f1: {args.measured} +/- {args.sigma} Hz")
    print(f"  (PhD Ch.5 field OMA, 20039 RANSAC windows)")

    # Likelihood weights: Gaussian on f1
    resid = df.f1_Hz.values - args.measured
    loglik = -0.5 * (resid / args.sigma) ** 2
    loglik -= loglik.max()
    weights = np.exp(loglik)

    # Effective sample size
    w_norm = weights / weights.sum()
    ess = float(1.0 / np.sum(w_norm ** 2))

    # Marginal posteriors
    post_scour = weighted_stats(df.scour_m.values, weights)
    post_su0 = weighted_stats(df.su0.values, weights)
    post_ksu = weighted_stats(df.k_su.values, weights)
    post_hmax = weighted_stats(df.Hmax_kN.values, weights)
    post_hratio = weighted_stats(df.H_ratio.values, weights)
    post_fixity = weighted_stats(df.fixity_proxy.values, weights)

    # Histogram of scour posterior (binned importance resampling)
    scour_bins = np.linspace(0.0, 4.0, 17)
    scour_hist, _ = np.histogram(df.scour_m.values, bins=scour_bins,
                                  weights=weights, density=True)

    print()
    print("=" * 72)
    print(f" Effective sample size = {ess:.0f} of {len(df)}")
    print("=" * 72)
    print(f"\n  POSTERIOR ON SCOUR DEPTH [m]:")
    print(f"    mean = {post_scour['mean']:.3f}")
    print(f"    std  = {post_scour['std']:.3f}")
    print(f"    5%   = {post_scour['p05']:.3f}")
    print(f"    50%  = {post_scour['p50']:.3f}")
    print(f"    95%  = {post_scour['p95']:.3f}")
    print(f"    90% credible interval: [{post_scour['p05']:.2f}, "
          f"{post_scour['p95']:.2f}] m")

    print(f"\n  POSTERIOR ON SURFACE SU [kPa]:")
    print(f"    mean = {post_su0['mean']:.2f}")
    print(f"    5-95: [{post_su0['p05']:.2f}, {post_su0['p95']:.2f}]")

    print(f"\n  POSTERIOR ON K_SU (su gradient) [kPa/m]:")
    print(f"    mean = {post_ksu['mean']:.2f}")
    print(f"    5-95: [{post_ksu['p05']:.2f}, {post_ksu['p95']:.2f}]")

    print(f"\n  POSTERIOR ON H_max [kN]:")
    print(f"    mean = {post_hmax['mean']:.0f}")
    print(f"    5-95: [{post_hmax['p05']:.0f}, {post_hmax['p95']:.0f}]")

    print(f"\n  POSTERIOR ON H_ratio [-]:")
    print(f"    mean = {post_hratio['mean']:.3f}")
    print(f"    5-95: [{post_hratio['p05']:.3f}, {post_hratio['p95']:.3f}]")

    result = {
        "task": "A (v2) - SiteA Bayesian scour ID from REAL 1794 MC",
        "measurement": {
            "f1_Hz": args.measured,
            "sigma_Hz": args.sigma,
            "source": "PhD Chapter 5 field OMA, 20039 RANSAC windows",
        },
        "forward_model": {
            "type": "non-parametric importance sampling on real MC database",
            "database": "PHD/data/integrated_database_1794.csv",
            "n_samples": int(len(df)),
            "source": "OptumGX 3D FE limit analysis + OpenSeesPy "
                      "BNWF structural dynamics",
        },
        "effective_sample_size": ess,
        "posterior_marginal": {
            "scour_m": post_scour,
            "su0_kPa": post_su0,
            "k_su_kPa_per_m": post_ksu,
            "Hmax_kN": post_hmax,
            "H_ratio": post_hratio,
            "fixity_proxy": post_fixity,
        },
        "scour_posterior_histogram": {
            "bin_edges_m": scour_bins.tolist(),
            "density": scour_hist.tolist(),
        },
    }
    out = REPO_ROOT / args.out
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(f"\n  JSON: {out}")


if __name__ == "__main__":
    main()
