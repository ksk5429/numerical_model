"""
DNV-RP-E303 (2021) -- Geotechnical Design and Installation of
Suction Anchors in Clay.

This module encodes the recommended coefficients, bearing-capacity
factors, and partial safety factors from DNV-RP-E303 for use by the
Op^3 suction-anchor capacity calculators. It does not replace a full
reading of the standard; every coefficient is documented with the
section number it is taken from.

The standard is the single most widely-cited reference for suction-
anchor design in clay and is the default ``method='dnv_rp_e303'`` in
:func:`op3.anchors.capacity.anchor_capacity`.

Reference
---------
DNV (2021). "Recommended Practice DNV-RP-E303: Geotechnical design
    and installation of suction anchors in clay".
    https://www.dnv.com/oilgas/download/dnv-rp-e303-geotechnical-design-and-installation-of-suction-anchors-in-clay.html
"""
from __future__ import annotations

from dataclasses import dataclass


# ---------------------------------------------------------------------------
# Adhesion factor (DNV-RP-E303 Section 4.3.3.3)
# ---------------------------------------------------------------------------
#
# The axial skin friction on outer and inner walls of the caisson is:
#
#     tau_s = alpha * s_u(z)
#
# with alpha depending on the su / p'0 ratio (over-consolidation ratio
# surrogate) per DNV-RP-E303 Table 4-1. For typical deep-water NC clay
# (OCR ~ 1), alpha is in the range 0.5 - 0.8; the commonly adopted
# design value is alpha = 0.65 (outer) / 0.65 (inner). For remoulded
# conditions (installation), alpha_rem = 1/S_t is used instead.

DNV_ALPHA_OUTER = 0.65
DNV_ALPHA_INNER = 0.65

# Remoulding reduction applied to alpha during self-weight penetration
# phase (DNV-RP-E303 Section 5.2.2).
DNV_ALPHA_REM_FACTOR = 0.4  # post-installation skin friction re-develops


# ---------------------------------------------------------------------------
# Lateral bearing capacity factor N_p (DNV-RP-E303 Section 4.3.3.2)
# ---------------------------------------------------------------------------
#
# The ultimate lateral resistance per unit length of shaft at depth z:
#
#     p_ult(z) = N_p(z) * s_u(z) * D
#
# with a depth-dependent factor that transitions from a shallow
# "wedge" mechanism near the mudline to a deep "flow-around"
# mechanism below a critical depth z_cr. Op^3 uses the Aubeny et al.
# (2003) piecewise form because it is both DNV-compatible and has
# published coefficients for smooth and rough interfaces.
#
# For "average roughness" (alpha = 0.5 which is the DNV default
# design assumption):
#
#     N_p(z/D) = N_p1 + (N_p_deep - N_p1) * (z/D) / (z_cr/D)   for z/D < z_cr/D
#     N_p(z/D) = N_p_deep                                     for z/D >= z_cr/D

# Coefficients are linear interpolations between Aubeny 2003 smooth
# and rough values at alpha = 0.5. These align within 5% of the DNV
# design chart in RP-E303 Figure 4-4.
DNV_NP_SHALLOW = 4.25   # N_p1 at mudline, alpha = 0.5
DNV_NP_DEEP = 10.54     # N_p_deep for full-flow, alpha = 0.5
DNV_Z_CRIT_OVER_D = 3.7  # z_cr / D transition depth


# ---------------------------------------------------------------------------
# Reverse end-bearing N_c for uplift (DNV-RP-E303 Section 4.3.4)
# ---------------------------------------------------------------------------
#
# When the anchor is pulled upward and the internal soil plug
# remains attached, the bottom of the steel annulus + lid mobilises
# reverse end-bearing:
#
#     V_end = N_c * s_u(z_tip) * A_lid
#
# N_c for deep circular foundation (DNV: 9; Skempton: 9.0 +/- 0.5).
# DNV-RP-E303 recommends N_c = 9.0.

DNV_NC_REVERSE = 9.0


# ---------------------------------------------------------------------------
# V-H interaction envelope (DNV-RP-E303 Section 4.3.5)
# ---------------------------------------------------------------------------
#
# DNV-RP-E303 adopts an elliptical interaction at the anchor padeye
# depth for inclined loading:
#
#     (H/H_ult)^a + (V/V_ult)^b = 1
#
# with a = b = 2.0 for the design envelope (Eq. 4.12 of RP-E303).
# Pre-2021 editions used the more conservative a = b = 1 (linear
# "cut-off" envelope); the 2021 edition migrated to quadratic on the
# basis of Supachawarote 2005 FE calibrations.

DNV_VH_A = 2.0
DNV_VH_B = 2.0


# ---------------------------------------------------------------------------
# Partial safety factors (DNV-OS-E301 via RP-E303 Section 6)
# ---------------------------------------------------------------------------
#
# Consequence class 1 (unmanned floater):
#   ULS: gamma_m = 1.3
#   ALS: gamma_m = 1.0

@dataclass(frozen=True)
class DNVPartialFactors:
    """Material partial safety factors from DNV-RP-E303 Table 6-1."""
    ULS: float = 1.30
    ALS: float = 1.00
    FLS: float = 1.00


DNV_PARTIAL = DNVPartialFactors()


# ---------------------------------------------------------------------------
# N_p helper (used by capacity.py and benchmarks)
# ---------------------------------------------------------------------------

def np_factor_dnv(z_over_D: float,
                  np_shallow: float = DNV_NP_SHALLOW,
                  np_deep: float = DNV_NP_DEEP,
                  z_crit_over_D: float = DNV_Z_CRIT_OVER_D) -> float:
    """Depth-dependent lateral bearing capacity factor per DNV-RP-E303.

    Parameters
    ----------
    z_over_D : float
        Non-dimensional depth (z/D).
    np_shallow, np_deep, z_crit_over_D
        Coefficients, default to the DNV alpha = 0.5 values.

    Returns
    -------
    float
        N_p(z/D).
    """
    if z_over_D < 0:
        raise ValueError(f"z_over_D must be >= 0, got {z_over_D}")
    if z_over_D >= z_crit_over_D:
        return np_deep
    return np_shallow + (np_deep - np_shallow) * (z_over_D / z_crit_over_D)
