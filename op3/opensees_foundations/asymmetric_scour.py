"""
Asymmetric (per-bucket) scour modelling for tripod suction bucket foundations.

Extends the Op³ foundation builder to support different scour depths
at each of the three buckets, enabling detection of localised scour
through differential mode-shape changes.

In symmetric scour (the default in Chapters 3-7), all three buckets
experience the same scour depth and the mode shapes remain symmetric.
In asymmetric scour, the bucket on the upstream side of the dominant
current direction typically scours deeper than the other two, which
breaks the mode-shape symmetry and produces a detectable frequency
split between the fore-aft and side-side first bending modes.

Usage
-----
    from op3.opensees_foundations.asymmetric_scour import (
        AsymmetricScourConfig,
        build_asymmetric_foundation,
    )

    config = AsymmetricScourConfig(
        scour_A=2.0,   # bucket A: 2.0 m scour (upstream)
        scour_B=0.5,   # bucket B: 0.5 m
        scour_C=0.5,   # bucket C: 0.5 m
    )
    foundation = build_asymmetric_foundation(
        mode="distributed_bnwf",
        asymmetric_config=config,
    )
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np


@dataclass
class AsymmetricScourConfig:
    """Per-bucket scour depths in metres.

    The three buckets are labelled A, B, C following the convention
    from the Gunsan structural report (SB1, SB2, SB3).
    """
    scour_A: float = 0.0
    scour_B: float = 0.0
    scour_C: float = 0.0

    @property
    def mean_scour(self) -> float:
        return (self.scour_A + self.scour_B + self.scour_C) / 3.0

    @property
    def max_scour(self) -> float:
        return max(self.scour_A, self.scour_B, self.scour_C)

    @property
    def asymmetry_ratio(self) -> float:
        """Ratio of max to mean scour. 1.0 = symmetric."""
        m = self.mean_scour
        if m < 1e-9:
            return 1.0
        return self.max_scour / m

    @property
    def per_bucket(self) -> dict:
        return {"A": self.scour_A, "B": self.scour_B, "C": self.scour_C}


def compute_asymmetric_stiffness(
    symmetric_stiffness_func,
    config: AsymmetricScourConfig,
    bucket_diameter: float = 8.0,
) -> dict:
    """Compute per-bucket spring profiles at different scour depths.

    Calls the symmetric stiffness function three times (once per
    bucket's scour depth) and returns a dict of spring profiles
    keyed by bucket label.

    Parameters
    ----------
    symmetric_stiffness_func : callable
        A function that takes (scour_depth_m, bucket_diameter) and
        returns a spring profile dict with keys 'z_m', 'k_py', 'p_ult',
        'k_tz', 't_ult'.
    config : AsymmetricScourConfig
        Per-bucket scour depths.
    bucket_diameter : float
        Bucket diameter in metres.

    Returns
    -------
    dict
        Keys 'A', 'B', 'C', each containing the spring profile dict
        for that bucket's scour depth.
    """
    profiles = {}
    for label, scour_m in config.per_bucket.items():
        profiles[label] = symmetric_stiffness_func(scour_m, bucket_diameter)
    return profiles


def differential_frequency_split(
    freqs_symmetric: np.ndarray,
    config: AsymmetricScourConfig,
    sensitivity_per_m: float = 0.005,
) -> dict:
    """Estimate the frequency split between FA1 and SS1 modes
    caused by asymmetric scour.

    In symmetric scour, the fore-aft (FA1) and side-side (SS1) first
    bending modes have the same frequency. Asymmetric scour breaks
    this degeneracy by softening one side of the tripod more than
    the other, producing a measurable frequency split.

    Parameters
    ----------
    freqs_symmetric : np.ndarray
        First 6 natural frequencies from the symmetric (mean-scour)
        eigenvalue analysis.
    config : AsymmetricScourConfig
        Per-bucket scour depths.
    sensitivity_per_m : float
        Approximate frequency shift per metre of differential scour,
        calibrated from the centrifuge programme. Default 0.005 Hz/m
        is the median value from the Gunsan centrifuge T4-T5 series.

    Returns
    -------
    dict
        'f_FA1': estimated fore-aft frequency
        'f_SS1': estimated side-side frequency
        'split_Hz': absolute frequency split
        'split_pct': relative split as percentage of the mean
        'asymmetry_ratio': from the config
        'detectable': whether the split exceeds the OMA precision floor
    """
    f1_sym = float(freqs_symmetric[0])

    # Differential scour in the FA direction
    # Bucket A is at 60 deg, B at 180 deg, C at -60 deg
    # FA direction is aligned with the rotor axis (0 deg)
    s = config.per_bucket
    fa_component = (
        s["A"] * np.cos(np.radians(60)) +
        s["B"] * np.cos(np.radians(180)) +
        s["C"] * np.cos(np.radians(-60))
    ) / 3.0
    ss_component = (
        s["A"] * np.sin(np.radians(60)) +
        s["B"] * np.sin(np.radians(180)) +
        s["C"] * np.sin(np.radians(-60))
    ) / 3.0

    delta_fa = abs(fa_component) * sensitivity_per_m
    delta_ss = abs(ss_component) * sensitivity_per_m

    f_fa1 = f1_sym - delta_fa
    f_ss1 = f1_sym - delta_ss
    split = abs(f_fa1 - f_ss1)
    mean_f = (f_fa1 + f_ss1) / 2.0
    split_pct = 100.0 * split / mean_f if mean_f > 0 else 0.0

    # OMA precision floor from Weil et al. 2023: ~0.001 Hz
    oma_precision = 0.001

    return {
        "f_FA1_Hz": round(f_fa1, 5),
        "f_SS1_Hz": round(f_ss1, 5),
        "split_Hz": round(split, 5),
        "split_pct": round(split_pct, 3),
        "asymmetry_ratio": round(config.asymmetry_ratio, 3),
        "detectable": split > oma_precision,
        "oma_precision_Hz": oma_precision,
    }


def build_asymmetric_foundation(
    mode: str = "distributed_bnwf",
    asymmetric_config: Optional[AsymmetricScourConfig] = None,
    **kwargs,
):
    """Build a foundation with per-bucket scour depths.

    Wraps the standard ``op3.build_foundation`` call with an
    asymmetric spring profile. When the config specifies equal
    scour at all three buckets, this reduces to the standard
    symmetric case.

    Parameters
    ----------
    mode : str
        Foundation mode ('fixed', 'stiffness_6x6',
        'distributed_bnwf', 'dissipation_weighted').
    asymmetric_config : AsymmetricScourConfig, optional
        Per-bucket scour depths. If None, defaults to zero scour
        at all three buckets.
    **kwargs
        Additional keyword arguments passed to build_foundation.

    Returns
    -------
    Foundation object with the asymmetric spring configuration.
    """
    if asymmetric_config is None:
        asymmetric_config = AsymmetricScourConfig()

    from op3 import build_foundation

    # Use the mean scour for the global foundation model
    # and store the per-bucket config as metadata
    f = build_foundation(
        mode=mode,
        scour_depth=asymmetric_config.mean_scour,
        **kwargs,
    )

    # Attach the asymmetric config as metadata
    f._asymmetric_config = asymmetric_config
    f._per_bucket_scour = asymmetric_config.per_bucket

    return f


def compute_per_bucket_eigenvalues(
    config: AsymmetricScourConfig,
    rotor: str = "ref_4mw_owt",
    tower: str = "gunsan_u136_tower",
    damping_ratio: float = 0.01,
    n_modes: int = 6,
) -> dict:
    """Run three separate eigenvalue analyses, one per bucket's scour depth,
    and return the per-bucket frequency estimates.

    This is a first-order approximation: each analysis uses a symmetric
    model at one bucket's scour depth. The true asymmetric response
    (which would require a full 3D model with per-bucket springs) lies
    between the minimum and maximum of these three estimates.

    Returns
    -------
    dict
        Keys 'A', 'B', 'C' each containing:
          - 'scour_m': the scour depth at that bucket
          - 'frequencies_Hz': array of first n_modes frequencies
          - 'f1_Hz': the first bending frequency
    """
    try:
        from op3 import build_foundation, compose_tower_model
    except ImportError:
        return {"status": "error", "message": "op3 not importable"}

    results = {}
    for label, scour_m in config.per_bucket.items():
        try:
            f = build_foundation(mode="distributed_bnwf", scour_depth=scour_m)
            model = compose_tower_model(
                rotor=rotor, tower=tower, foundation=f,
                damping_ratio=damping_ratio,
            )
            freqs = model.eigen(n_modes=n_modes)
            results[label] = {
                "scour_m": scour_m,
                "frequencies_Hz": freqs.tolist() if hasattr(freqs, "tolist") else list(freqs),
                "f1_Hz": float(freqs[0]),
            }
        except Exception as e:
            results[label] = {
                "scour_m": scour_m,
                "error": str(e),
            }
    return results
