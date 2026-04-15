"""
Installation analysis for suction anchors in clay.

Three phases:

1. Self-weight penetration  :: how deep does the anchor sink under
   its own submerged weight before the shaft friction + tip
   resistance equals the driving force?

2. Suction-assisted penetration  :: beyond self-weight depth, the
   differential pressure ``s`` between the outside (hydrostatic) and
   the sealed interior pulls the anchor down. This function returns
   the required suction vs depth curve and checks against the
   cavitation and plug-heave limits.

3. Plug-heave check  :: as the anchor penetrates under suction the
   soil inside tries to lift off the sea floor (the "inverse bearing
   capacity" failure). If the plug heaves, installation stops.

All formulas use remoulded shear strength for shaft friction during
installation (DNV-RP-E303 Section 5.2.2).

References
----------
DNV-RP-E303 (2021) Sections 5.2, 5.3.
Houlsby, G. T., & Byrne, B. W. (2005). "Design procedures for
    installation of suction caissons in clay". Proc. ICE Geotech.
    Eng., 158(2), 75-82.
Andersen, K. H., & Jostad, H. P. (1999). "Foundation design of
    skirted foundations and anchors in clay". OTC 10824.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from op3.anchors.anchor import SuctionAnchor, UndrainedClayProfile
from op3.standards.dnv_rp_e303 import (
    DNV_ALPHA_OUTER,
    DNV_ALPHA_INNER,
    DNV_ALPHA_REM_FACTOR,
    DNV_NC_REVERSE,
)

SEAWATER_GAMMA_KN_PER_M3 = 10.25  # seawater unit weight


# ---------------------------------------------------------------------------
# Result container
# ---------------------------------------------------------------------------

@dataclass
class InstallationResult:
    """Collated installation analysis result."""
    profile: pd.DataFrame  # columns depth_m, F_drive_kN, F_resist_kN, s_req_kPa, s_allow_kPa, R_plug
    self_weight_depth_m: float
    max_suction_required_kPa: float
    max_allowable_suction_kPa: float
    plug_heave_ok: bool
    feasible: bool
    metadata: dict = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Penetration resistance (remoulded + tip)
# ---------------------------------------------------------------------------

def _friction_integral(anchor: SuctionAnchor,
                       soil: UndrainedClayProfile,
                       z: float,
                       alpha_outer: float,
                       alpha_inner: float,
                       remoulded: bool) -> tuple[float, float]:
    """Integrated outer and inner shaft friction down to depth z.

    Parameters
    ----------
    remoulded : bool
        If True, use s_u / S_t; else intact s_u.

    Returns
    -------
    (F_outer_kN, F_inner_kN)
    """
    if z <= 0:
        return 0.0, 0.0
    zz = np.linspace(0.0, z, 200)
    if remoulded:
        su = soil.su_remoulded_at_depth(zz)
    else:
        su = soil.su_at_depth(zz)
    # shear stress tau = alpha * su, area per unit depth = pi * D
    F_outer = alpha_outer * np.trapezoid(su, zz) * (np.pi * anchor.diameter_m)
    F_inner = alpha_inner * np.trapezoid(su, zz) * (
        np.pi * anchor.inner_diameter_m
    )
    return float(F_outer), float(F_inner)


def _tip_resistance(anchor: SuctionAnchor,
                    soil: UndrainedClayProfile,
                    z: float,
                    nc_tip: float = DNV_NC_REVERSE) -> float:
    """Bearing resistance at the skirt tip (annulus area only)."""
    su_tip = soil.su_at_depth(z)
    return float(nc_tip * su_tip * anchor.annulus_area_m2)


def penetration_resistance(anchor: SuctionAnchor,
                           soil: UndrainedClayProfile,
                           z: float,
                           *,
                           alpha_outer: float = DNV_ALPHA_OUTER,
                           alpha_inner: float = DNV_ALPHA_INNER,
                           remoulded: bool = True,
                           nc_tip: float = DNV_NC_REVERSE) -> float:
    """Total driving resistance at depth z during installation.

        R(z) = F_outer_friction + F_inner_friction + F_tip

    Returns
    -------
    float
        Total resistance in kN. A positive value resists penetration.
    """
    # DNV-RP-E303 Section 5.2.2: during penetration alpha is reduced
    # by the remoulded factor (accounts for disturbance).
    scale = DNV_ALPHA_REM_FACTOR if remoulded else 1.0
    F_o, F_i = _friction_integral(
        anchor, soil, z,
        alpha_outer=alpha_outer * scale,
        alpha_inner=alpha_inner * scale,
        remoulded=remoulded,
    )
    F_tip = _tip_resistance(anchor, soil, z, nc_tip=nc_tip)
    return F_o + F_i + F_tip


# ---------------------------------------------------------------------------
# Phase 1: self-weight penetration
# ---------------------------------------------------------------------------

def self_weight_penetration(anchor: SuctionAnchor,
                            soil: UndrainedClayProfile,
                            *,
                            alpha_outer: float = DNV_ALPHA_OUTER,
                            alpha_inner: float = DNV_ALPHA_INNER,
                            nc_tip: float = DNV_NC_REVERSE) -> float:
    """Depth to which the anchor penetrates under its own submerged
    weight before resistance balances driving force.

    Solves ``W_sub = R(z)`` by bisection. If ``W_sub`` exceeds the
    resistance at full embedment, returns the skirt length (anchor
    sits on the seabed on its tip).

    If ``W_sub = 0`` (typical for design-stage dummy weight) the
    self-weight depth is 0 by definition.
    """
    W = anchor.submerged_weight_kN
    if W <= 0:
        return 0.0
    R_full = penetration_resistance(anchor, soil, anchor.skirt_length_m,
                                    alpha_outer=alpha_outer,
                                    alpha_inner=alpha_inner,
                                    remoulded=True, nc_tip=nc_tip)
    if W >= R_full:
        return anchor.skirt_length_m
    lo, hi = 0.0, anchor.skirt_length_m
    for _ in range(80):
        mid = 0.5 * (lo + hi)
        R_mid = penetration_resistance(anchor, soil, mid,
                                       alpha_outer=alpha_outer,
                                       alpha_inner=alpha_inner,
                                       remoulded=True, nc_tip=nc_tip)
        if R_mid > W:
            hi = mid
        else:
            lo = mid
        if hi - lo < 1e-4:
            break
    return 0.5 * (lo + hi)


# ---------------------------------------------------------------------------
# Phase 2: suction penetration (DNV-RP-E303 Section 5.3)
# ---------------------------------------------------------------------------

def required_suction_kPa(anchor: SuctionAnchor,
                         soil: UndrainedClayProfile,
                         z: float,
                         *,
                         alpha_outer: float = DNV_ALPHA_OUTER,
                         alpha_inner: float = DNV_ALPHA_INNER,
                         nc_tip: float = DNV_NC_REVERSE) -> float:
    """Required suction pressure to penetrate to depth z.

        s_req(z) = ( R(z) - W_sub ) / A_lid_inner

    Uses the inner lid area because the suction force acts on the
    interior seal (DNV-RP-E303 Section 5.3.2).
    """
    R = penetration_resistance(anchor, soil, z,
                               alpha_outer=alpha_outer,
                               alpha_inner=alpha_inner,
                               remoulded=True, nc_tip=nc_tip)
    net = R - anchor.submerged_weight_kN
    if net <= 0:
        return 0.0
    return net / anchor.lid_inner_area_m2


def allowable_suction_kPa(water_depth_m: float,
                          z: float,
                          soil: UndrainedClayProfile,
                          cavitation_margin: float = 0.9) -> float:
    """Maximum suction that can be pulled before cavitation.

    The limit is the total overburden outside the anchor:

        s_allow = cavitation_margin * (gamma_w * z_w + gamma' * z)

    The cavitation margin (default 0.9) accounts for pump inefficiency
    and vapour pressure of seawater, per DNV-RP-E303 Section 5.3.5.
    """
    s = cavitation_margin * (
        SEAWATER_GAMMA_KN_PER_M3 * water_depth_m
        + soil.gamma_eff_kN_per_m3 * z
    )
    return float(s)


# ---------------------------------------------------------------------------
# Phase 3: plug-heave check
# ---------------------------------------------------------------------------

def plug_heave_check(anchor: SuctionAnchor,
                     soil: UndrainedClayProfile,
                     z: float,
                     suction_kPa: float,
                     *,
                     alpha_inner: float = DNV_ALPHA_INNER,
                     nc_reverse: float = DNV_NC_REVERSE) -> float:
    """Plug-heave stability ratio ``R_plug``.

    Following DNV-RP-E303 Section 5.4:

        R_plug = S_pull / S_resist

    where:
        S_pull   = s * A_lid_inner     (uplift on internal soil plug)
        S_resist = W_plug + F_inner + N_c * s_u(tip) * A_lid_inner

    ``R_plug < 1`` means installation is stable.
    """
    S_pull = suction_kPa * anchor.lid_inner_area_m2

    # Plug weight: cylinder of soil of radius D_i/2, height z
    # submerged unit weight gamma'
    W_plug = soil.gamma_eff_kN_per_m3 * anchor.lid_inner_area_m2 * z
    F_inner = _friction_integral(
        anchor, soil, z,
        alpha_outer=0.0,  # outer not relevant for plug heave
        alpha_inner=alpha_inner * DNV_ALPHA_REM_FACTOR,
        remoulded=True,
    )[1]
    su_tip = soil.su_at_depth(z)
    S_end = nc_reverse * su_tip * anchor.lid_inner_area_m2
    S_resist = W_plug + F_inner + S_end
    if S_resist <= 0:
        return float("inf")
    return float(S_pull / S_resist)


# ---------------------------------------------------------------------------
# Full installation analysis
# ---------------------------------------------------------------------------

def installation_analysis(anchor: SuctionAnchor,
                          soil: UndrainedClayProfile,
                          water_depth_m: float,
                          *,
                          alpha_outer: float = DNV_ALPHA_OUTER,
                          alpha_inner: float = DNV_ALPHA_INNER,
                          nc_tip: float = DNV_NC_REVERSE,
                          n_depths: int = 50) -> InstallationResult:
    """Run all three installation checks and return a single report.

    Parameters
    ----------
    water_depth_m : float
        Sea water depth at the anchor location. Sets the cavitation
        limit for suction.
    """
    if water_depth_m <= 0:
        raise ValueError(
            f"water_depth_m must be > 0, got {water_depth_m}"
        )
    if water_depth_m < 50.0:
        # physical plausibility warning, not an error: floating wind
        # anchors are practically always in deep water, but keep the
        # function usable for lab-scale validations
        pass

    z_self = self_weight_penetration(anchor, soil,
                                     alpha_outer=alpha_outer,
                                     alpha_inner=alpha_inner,
                                     nc_tip=nc_tip)

    z_grid = np.linspace(0.0, anchor.skirt_length_m, n_depths + 1)[1:]
    rows = []
    for z in z_grid:
        R = penetration_resistance(anchor, soil, z,
                                   alpha_outer=alpha_outer,
                                   alpha_inner=alpha_inner,
                                   remoulded=True, nc_tip=nc_tip)
        s_req = required_suction_kPa(anchor, soil, z,
                                     alpha_outer=alpha_outer,
                                     alpha_inner=alpha_inner,
                                     nc_tip=nc_tip)
        s_allow = allowable_suction_kPa(water_depth_m, z, soil)
        Rp = plug_heave_check(anchor, soil, z, s_req,
                              alpha_inner=alpha_inner)
        rows.append(dict(depth_m=float(z),
                         F_drive_kN=anchor.submerged_weight_kN
                                    + s_req * anchor.lid_inner_area_m2,
                         F_resist_kN=R,
                         s_req_kPa=s_req,
                         s_allow_kPa=s_allow,
                         R_plug=Rp))
    profile = pd.DataFrame(rows)
    max_s_req = float(profile["s_req_kPa"].max())
    max_s_allow = float(profile["s_allow_kPa"].min())
    plug_ok = bool((profile["R_plug"] < 1.0).all())
    feasible = (max_s_req <= max_s_allow) and plug_ok

    return InstallationResult(
        profile=profile,
        self_weight_depth_m=z_self,
        max_suction_required_kPa=max_s_req,
        max_allowable_suction_kPa=max_s_allow,
        plug_heave_ok=plug_ok,
        feasible=feasible,
        metadata=dict(
            water_depth_m=water_depth_m,
            alpha_outer=alpha_outer,
            alpha_inner=alpha_inner,
            standard="DNV-RP-E303 (2021) Sections 5.2-5.4",
        ),
    )


# Public alias matching the upgrade-plan name
suction_penetration = installation_analysis
