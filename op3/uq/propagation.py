"""
Soil parameter UQ propagation (Phase 5 / Task 5.1).

Monte Carlo propagation of geotechnical input uncertainty through the
PISA / cyclic / HSsmall pipeline. Samples are drawn from a layered
soil prior and the resulting 6x6 head-stiffness distribution is
summarised by mean, std, and 5/50/95 percentiles for each diagonal
term.

The motivating use case: published soil investigation reports give
G_max as a band (e.g. 60-120 MPa) rather than a point value. This
module turns that band into a defensible distribution on the
foundation stiffness that downstream Op^3 stages (eigenvalue,
DLC simulation, fatigue) can consume.

Reference
---------
Phoon, K. K., & Kulhawy, F. H. (1999). "Characterization of
    geotechnical variability". Canadian Geotechnical Journal, 36(4),
    612-624.  -- baseline COVs for soil parameters.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Optional

import numpy as np

from op3.standards.pisa import SoilState, pisa_pile_stiffness_6x6


@dataclass
class SoilPrior:
    """
    Probabilistic specification for one soil layer. The prior is
    parameterised by mean and coefficient of variation (COV =
    std / mean) for each fluctuating quantity. Lognormal sampling is
    used so that all draws stay strictly positive.
    """
    depth_m: float
    G_mean_Pa: float
    G_cov: float = 0.30                # Phoon & Kulhawy 1999
    soil_type: str = "sand"
    su_or_phi_mean: float = 35.0
    su_or_phi_cov: float = 0.10

    def sample(self, rng: np.random.Generator) -> SoilState:
        # Lognormal: mu = ln(mean) - sigma^2/2, sigma = ln(1+cov^2)^0.5
        sigma_G = np.sqrt(np.log(1 + self.G_cov ** 2))
        mu_G = np.log(self.G_mean_Pa) - 0.5 * sigma_G ** 2
        G = float(rng.lognormal(mu_G, sigma_G))

        sigma_phi = np.sqrt(np.log(1 + self.su_or_phi_cov ** 2))
        mu_phi = np.log(self.su_or_phi_mean) - 0.5 * sigma_phi ** 2
        phi_or_su = float(rng.lognormal(mu_phi, sigma_phi))

        return SoilState(
            depth_m=self.depth_m, G_Pa=G,
            su_or_phi=phi_or_su, soil_type=self.soil_type,
        )


def propagate_pisa_mc(
    *,
    diameter_m: float,
    embed_length_m: float,
    soil_priors: list[SoilPrior],
    n_samples: int = 500,
    seed: int = 42,
    correlated: bool = True,
) -> np.ndarray:
    """
    Run an MC sweep through ``pisa_pile_stiffness_6x6`` and return an
    (n_samples, 6, 6) array of K matrices.

    Parameters
    ----------
    correlated
        If True (default), all layers share the same realisation of
        the underlying standard normal so that "soft" draws have all
        layers softer simultaneously (perfectly correlated). If False,
        each layer is sampled independently. The published practice
        for site-specific design is to assume strong correlation.
    """
    rng = np.random.default_rng(seed)
    out = np.zeros((n_samples, 6, 6), dtype=float)
    n_layers = len(soil_priors)
    for i in range(n_samples):
        if correlated:
            # Single shared realisation across layers; use a
            # per-sample sub-rng so the same shock applies to all.
            sub = np.random.default_rng(rng.integers(2**63 - 1))
            profile = []
            for prior in soil_priors:
                # Replay sub for each layer to enforce correlation
                G_seed = sub.standard_normal()
                phi_seed = sub.standard_normal()
                sigma_G = np.sqrt(np.log(1 + prior.G_cov ** 2))
                mu_G = np.log(prior.G_mean_Pa) - 0.5 * sigma_G ** 2
                G = float(np.exp(mu_G + sigma_G * G_seed))
                sigma_phi = np.sqrt(np.log(1 + prior.su_or_phi_cov ** 2))
                mu_phi = np.log(prior.su_or_phi_mean) - 0.5 * sigma_phi ** 2
                phi = float(np.exp(mu_phi + sigma_phi * phi_seed))
                profile.append(SoilState(prior.depth_m, G,
                                          phi, prior.soil_type))
        else:
            profile = [p.sample(rng) for p in soil_priors]
        K = pisa_pile_stiffness_6x6(
            diameter_m=diameter_m,
            embed_length_m=embed_length_m,
            soil_profile=profile,
        )
        out[i] = K
    return out


def summarise_samples(samples: np.ndarray) -> dict:
    """
    Reduce an (n, 6, 6) sample array to per-DOF summary statistics
    on the diagonal terms.

    Returns
    -------
    dict
        Keys: 'Kxx', 'Kyy', 'Kzz', 'Krxrx', 'Kryry', 'Krzrz'
        Each value is a sub-dict with mean, std, p05, p50, p95.
    """
    labels = ["Kxx", "Kyy", "Kzz", "Krxrx", "Kryry", "Krzrz"]
    out: dict = {}
    for i, label in enumerate(labels):
        diag = samples[:, i, i]
        out[label] = {
            "mean": float(np.mean(diag)),
            "std": float(np.std(diag)),
            "cov": float(np.std(diag) / np.mean(diag)) if np.mean(diag) != 0 else 0.0,
            "p05": float(np.percentile(diag, 5)),
            "p50": float(np.percentile(diag, 50)),
            "p95": float(np.percentile(diag, 95)),
            "n": int(samples.shape[0]),
        }
    return out
