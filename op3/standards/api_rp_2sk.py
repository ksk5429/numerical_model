"""
API RP 2SK (2005, reaff. 2015) -- Design and Analysis of Stationkeeping
Systems for Floating Structures.

Op^3 uses API RP 2SK as a cross-check against DNV-RP-E303. The two
standards largely agree on the controlling mechanics (plastic limit
analysis of a rigid caisson translating and rotating in a linearly
increasing s_u profile) but differ in the recommended N_p and in the
form of the V-H interaction envelope.

Reference
---------
API (2005, reaffirmed 2015). "Recommended Practice 2SK: Design and
    Analysis of Stationkeeping Systems for Floating Structures",
    3rd edition. American Petroleum Institute.
"""
from __future__ import annotations


# ---------------------------------------------------------------------------
# Adhesion factor (API RP 2SK Section 5.4.2.2)
# ---------------------------------------------------------------------------
#
# API adopts a slightly more conservative alpha than DNV for design
# purposes:
#
#     alpha = 0.5      for s_u / sigma'_v0 < 0.25
#     alpha = 0.5 * (s_u / sigma'_v0)^(-0.25)   otherwise
#
# For typical NC clay alpha is usually close to 0.5.

API_ALPHA_DEFAULT = 0.50


# ---------------------------------------------------------------------------
# Lateral bearing capacity factor N_p (API RP 2SK Section 5.4.2.3)
# ---------------------------------------------------------------------------
#
# API uses a constant deep N_p = 9 throughout the embedded length,
# reduced near the mudline by a shallow-mechanism cap:
#
#     N_p(z) = min( 3 + z/D ,  9 )
#
# This is the classical Matlock "cut-off" form and is more conservative
# than the Aubeny 2003 / DNV-RP-E303 formulation.

API_NP_DEEP = 9.0
API_NP_SHALLOW_INTERCEPT = 3.0
API_NP_SHALLOW_SLOPE = 1.0  # per z/D


def np_factor_api(z_over_D: float) -> float:
    """Depth-dependent lateral bearing capacity factor per API RP 2SK.

    Linear-increase with cut-off at 9:

        N_p(z/D) = min(3 + z/D, 9)
    """
    if z_over_D < 0:
        raise ValueError(f"z_over_D must be >= 0, got {z_over_D}")
    return min(API_NP_SHALLOW_INTERCEPT + API_NP_SHALLOW_SLOPE * z_over_D,
               API_NP_DEEP)


# ---------------------------------------------------------------------------
# Reverse end-bearing N_c
# ---------------------------------------------------------------------------
# API RP 2SK Section 5.4.3 recommends N_c = 9 for uplift of a plugged
# caisson, same as DNV.

API_NC_REVERSE = 9.0


# ---------------------------------------------------------------------------
# V-H interaction envelope (API RP 2SK Section 5.4.4)
# ---------------------------------------------------------------------------
#
# API retains the simpler linear envelope for design:
#
#     H/H_ult + V/V_ult = 1
#
# This is always more conservative than the DNV quadratic envelope.

API_VH_A = 1.0
API_VH_B = 1.0


# ---------------------------------------------------------------------------
# Partial safety factors (API RP 2SK Section 6)
# ---------------------------------------------------------------------------
# For dynamic analysis with max 100-yr environmental conditions:
#   intact: FoS >= 1.67
#   one-line-broken: FoS >= 1.25
#
# These are TOTAL factors of safety (not partial factors on material).

API_FOS_INTACT_DYNAMIC = 1.67
API_FOS_DAMAGED_DYNAMIC = 1.25
