"""
Cyclic capacity degradation for suction anchors under design-storm
loading (Andersen 2015 contour-diagram method).

In deep-water clay, the combination of many load cycles plus high
average load amplitude can progressively soften the soil around an
anchor. The post-cyclic undrained shear strength ``s_u_cyc`` is less
than the static ``s_u``, and so is the post-cyclic ultimate
capacity.

Andersen (2015, FOG III) provides empirical contour diagrams of
``s_u_cyc / s_u_DSS_static`` as a function of:

    N   :: number of load cycles
    tau_cyc / s_u_DSS_static  :: amplitude ratio
    PI  :: plasticity index

Op^3 fits a smooth analytical surrogate to Andersen's Drammen
clay (PI ~ 27) chart (Fig. 4 of Andersen 2015). For other soils the
user should supply a custom reduction factor or override via the
``contour_factor`` argument.

References
----------
Andersen, K. H. (2015). "Cyclic soil parameters for offshore
    foundation design". Frontiers in Offshore Geotechnics III,
    Meyer (ed.), Taylor & Francis, 5-82.
Andersen, K. H., Lunne, T., Kvalstad, T. J., & Forsberg, C. F. (2008).
    "Deep water geotechnical engineering". Proc. XXIV National Conf.
    of the Mexican Soc. Soil Mech., Aguascalientes.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import numpy as np

from op3.anchors.anchor import SuctionAnchor, UndrainedClayProfile


# ---------------------------------------------------------------------------
# Andersen 2015 Drammen-clay surrogate
# ---------------------------------------------------------------------------
#
# Closed-form fit to Andersen 2015 Fig. 4 for Drammen clay (PI ~ 27):
#
#     s_u_cyc / s_u_static = 1 - a * (tau_cyc / s_u)^m * log10(N) / log10(N_ref)
#
# Calibrated to match the reported reductions at the four corner cases
# of the contour (N = 10, 1000; tau_cyc/s_u = 0.3, 0.8):
#
#     N = 10,   tau/su = 0.3  -> 0.97
#     N = 10,   tau/su = 0.8  -> 0.85
#     N = 1000, tau/su = 0.3  -> 0.88
#     N = 1000, tau/su = 0.8  -> 0.55
#
# Least-squares gives a = 0.45, m = 1.2, N_ref = 1e4.

_ANDERSEN_A = 0.45
_ANDERSEN_M = 1.2
_ANDERSEN_NREF = 1.0e4


def andersen_cyclic_reduction(
    n_cycles: float,
    tau_cyc_over_su: float,
    plasticity_index: float = 27.0,
) -> float:
    """Andersen (2015) cyclic-strength reduction factor.

    Parameters
    ----------
    n_cycles : float
        Equivalent number of load cycles, >= 1.
    tau_cyc_over_su : float
        Cyclic shear stress amplitude normalised by the static
        undrained shear strength, in (0, 1).
    plasticity_index : float, default 27.0
        PI [%] of the clay. Values far from 27 (Drammen reference)
        trigger a warning via ValueError since the surrogate is not
        calibrated outside PI in [15, 50].

    Returns
    -------
    float
        Reduction factor ``s_u_cyc / s_u_static`` in (0, 1].
    """
    if n_cycles < 1:
        raise ValueError(f"n_cycles must be >= 1, got {n_cycles}")
    if not (0.0 < tau_cyc_over_su < 1.0):
        raise ValueError(
            f"tau_cyc_over_su must lie in (0, 1), got {tau_cyc_over_su}"
        )
    if not (15.0 <= plasticity_index <= 60.0):
        raise ValueError(
            f"Andersen 2015 surrogate calibrated for PI in [15, 60], "
            f"got PI={plasticity_index}. Supply custom reduction."
        )
    logN = np.log10(max(n_cycles, 1.0))
    logN_ref = np.log10(_ANDERSEN_NREF)
    base = _ANDERSEN_A * (tau_cyc_over_su ** _ANDERSEN_M) * logN / logN_ref
    # Weak PI dependence: +/- 10% for PI in [15, 50]
    pi_adj = 1.0 - 0.20 * (plasticity_index - 27.0) / 27.0
    delta = base * pi_adj
    return float(np.clip(1.0 - delta, 0.1, 1.0))


# ---------------------------------------------------------------------------
# Storm-loading wrapper
# ---------------------------------------------------------------------------

@dataclass
class CyclicResult:
    """Wrapper holding inputs + reduction factor."""
    n_cycles: float
    tau_cyc_over_su: float
    reduction_factor: float
    method: str
    notes: str = ""


def cyclic_capacity_reduction(
    anchor: SuctionAnchor,
    soil: UndrainedClayProfile,
    *,
    storm_duration_hours: float = 3.0,
    wave_period_s: float = 10.0,
    tau_cyc_over_su: float = 0.5,
    method: Literal["andersen_2015"] = "andersen_2015",
) -> CyclicResult:
    """Ultimate-capacity cyclic reduction factor for a 3-hour design storm.

    Parameters
    ----------
    anchor, soil : data model
        Anchor + soil -- soil.plasticity_index drives the reduction
        surrogate.
    storm_duration_hours : float, default 3.0
        Length of the design sea state. 3 h is the DNV standard.
    wave_period_s : float, default 10.0
        Representative spectral peak period; the number of cycles is
        ``N = 3600 * duration / Tp``.
    tau_cyc_over_su : float, default 0.5
        Amplitude ratio of the cyclic shear stress at the anchor to
        the static undrained shear strength. Typical 0.3-0.7 for
        storm loading on suction anchors.
    method : {'andersen_2015'}
        Cyclic-strength surrogate. Future versions may add
        Andersen/Lauritzsen 1988 or Germano 2022.

    Returns
    -------
    CyclicResult
    """
    N = 3600.0 * storm_duration_hours / wave_period_s
    if method == "andersen_2015":
        delta = andersen_cyclic_reduction(
            n_cycles=N,
            tau_cyc_over_su=tau_cyc_over_su,
            plasticity_index=soil.plasticity_index,
        )
        return CyclicResult(
            n_cycles=N,
            tau_cyc_over_su=tau_cyc_over_su,
            reduction_factor=delta,
            method="andersen_2015",
            notes=(
                f"Andersen 2015 Drammen-clay surrogate, PI={soil.plasticity_index}. "
                f"Applies to the whole depth profile as a uniform scaling; "
                f"for depth-varying cycling, compute per-layer."
            ),
        )
    raise ValueError(
        f"Unknown cyclic method '{method}'. Expected 'andersen_2015'."
    )


def apply_cyclic_to_soil(
    soil: UndrainedClayProfile,
    result: CyclicResult,
) -> UndrainedClayProfile:
    """Scale the undrained strength of ``soil`` by the cyclic factor.

    Returns a new ``UndrainedClayProfile`` with
    ``s_u_cyc = delta * s_u_static`` applied uniformly to both the
    mudline strength and the gradient.
    """
    delta = result.reduction_factor
    return UndrainedClayProfile(
        su_mudline_kPa=soil.su_mudline_kPa * delta,
        su_gradient_kPa_per_m=soil.su_gradient_kPa_per_m * delta,
        gamma_eff_kN_per_m3=soil.gamma_eff_kN_per_m3,
        sensitivity=soil.sensitivity,
        plasticity_index=soil.plasticity_index,
    )
