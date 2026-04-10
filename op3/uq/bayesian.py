"""
Bayesian calibration of tower / foundation parameters (Phase 5 / Task 5.3).

Grid-based Bayesian inversion of a single scalar parameter (typically
the tower fore-aft EI scaling factor or the foundation rotational
stiffness multiplier) given a measured first natural frequency.

The grid approach is preferred over MCMC for the 1D problems Op^3
needs because:

1. The posterior is uni-modal and concentrated, so 200-500 grid
   points are enough for sub-percent posterior summaries.
2. No tuning parameters (chain length, burn-in, proposal width).
3. The forward model is fast (~10 ms per Op^3 eigen call) so the
   200-point grid runs in 2 seconds end-to-end.
4. The result is fully reproducible -- no random seed dependence.

The output is a posterior PDF on the calibration parameter, plus
the posterior mean, std, and 5/50/95 percentiles.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

import numpy as np


@dataclass
class BayesianPosterior:
    grid: np.ndarray
    prior: np.ndarray
    likelihood: np.ndarray
    posterior: np.ndarray
    mean: float
    std: float
    p05: float
    p50: float
    p95: float


def normal_likelihood(measured: float, sigma: float) -> Callable[[float], float]:
    """Return L(predicted) = N(measured | predicted, sigma^2) callable."""
    inv2s2 = 1.0 / (2.0 * sigma * sigma)
    norm = 1.0 / (np.sqrt(2.0 * np.pi) * sigma)

    def L(pred: float) -> float:
        return float(norm * np.exp(-(measured - pred) ** 2 * inv2s2))

    return L


def grid_bayesian_calibration(
    *,
    forward_model: Callable[[float], float],
    likelihood_fn: Callable[[float], float],
    grid: np.ndarray,
    prior: np.ndarray | None = None,
) -> BayesianPosterior:
    """
    1D grid Bayesian calibration.

    Parameters
    ----------
    forward_model
        Map from the calibration parameter (e.g. EI scale factor) to
        the predicted observable (e.g. f1 in Hz).
    likelihood_fn
        Maps a *predicted* value to its likelihood under the measurement
        noise model. Use ``normal_likelihood(measured, sigma)``.
    grid
        Discretisation of the parameter axis.
    prior
        Prior PDF over the same grid (un-normalised is fine). If None,
        a uniform prior is used.
    """
    if prior is None:
        prior = np.ones_like(grid)
    pred = np.array([forward_model(float(p)) for p in grid])
    lk = np.array([likelihood_fn(float(p)) for p in pred])
    post_unnorm = prior * lk
    Z = float(np.trapezoid(post_unnorm, grid))
    if Z <= 0:
        raise ValueError("posterior unnormalisable: Z = 0")
    post = post_unnorm / Z

    # Cumulative for percentiles
    cdf = np.concatenate([[0.0], np.cumsum(0.5 * (post[1:] + post[:-1])
                                            * np.diff(grid))])
    cdf /= cdf[-1]

    def quantile(q: float) -> float:
        return float(np.interp(q, cdf, grid))

    mean = float(np.trapezoid(grid * post, grid))
    var = float(np.trapezoid((grid - mean) ** 2 * post, grid))

    return BayesianPosterior(
        grid=grid, prior=prior / np.trapezoid(prior, grid),
        likelihood=lk, posterior=post,
        mean=mean, std=float(np.sqrt(max(var, 0.0))),
        p05=quantile(0.05), p50=quantile(0.50), p95=quantile(0.95),
    )
