"""
ISO 19901-4 Annex E — Stiffness coefficients for shallow and pile
foundations of offshore structures.

Reference:
    ISO 19901-4:2016 "Petroleum and natural gas industries — Specific
    requirements for offshore structures — Part 4: Geotechnical and
    foundation design considerations". International Organization
    for Standardization.

ISO 19901-4 is the international consensus standard for offshore
geotechnical foundation design and is the reference adopted by
DNVGL-ST-0126 §5.5 for offshore wind turbines. The expressions in
this module are reproduced from Annex E of ISO 19901-4.

The expressions are similar to (and in many cases identical to)
the Gazetas (1991) closed-form impedance formulas, with corrections
for embedment, layered soil profiles, and dynamic effects. For Op^3
Mode B (linear stiffness), only the static expressions are used.
"""
from __future__ import annotations

import numpy as np

from op3.standards.dnv_st_0126 import _get_soil_props


def iso_shallow_foundation_stiffness(
    radius_m: float,
    embedment_m: float = 0.0,
    shape: str = "circular",
    soil_type: str = "dense_sand",
    G: float | None = None,
    nu: float | None = None,
) -> np.ndarray:
    """6x6 stiffness for a shallow circular or square foundation per
    ISO 19901-4 Annex E Table E.1.

    Parameters
    ----------
    radius_m : float
        For 'circular': the radius. For 'square': half-side length.
    embedment_m : float, default 0.0
        Embedment depth (0 = surface foundation).
    shape : str, default 'circular'
        'circular' or 'square'. Square uses an equivalent radius.
    soil_type, G, nu : see dnv_st_0126.

    Reference
    ---------
    ISO 19901-4:2016 Annex E "Stiffness coefficients for shallow
        foundations".
    """
    G, nu = _get_soil_props(soil_type, G, nu)
    R = radius_m if shape == "circular" else radius_m * (4.0 / np.pi) ** 0.5
    D = embedment_m

    # ISO 19901-4 Eq. E.1 to E.4 — surface foundation
    K_xx_0 = (8.0 * G * R) / (2.0 - nu)
    K_zz_0 = (4.0 * G * R) / (1.0 - nu)
    K_rxx_0 = (8.0 * G * R ** 3) / (3.0 * (1.0 - nu))
    K_rzz_0 = (16.0 / 3.0) * G * R ** 3

    # ISO 19901-4 Eq. E.5 — embedment correction (Gazetas form)
    if D > 0:
        eta_x = 1.0 + 0.55 * (D / R) ** 0.85
        eta_z = 1.0 + 0.54 * (D / R)
        eta_rx = 1.0 + 2.3 * D / (2 * R) + 0.58 * (D / (2 * R)) ** 3
        eta_rz = 1.0 + 1.6 * D / (2 * R)
    else:
        eta_x = eta_z = eta_rx = eta_rz = 1.0

    K_xx = K_xx_0 * eta_x
    K_yy = K_xx
    K_zz = K_zz_0 * eta_z
    K_rxx = K_rxx_0 * eta_rx
    K_ryy = K_rxx
    K_rzz = K_rzz_0 * eta_rz

    return np.diag([K_xx, K_yy, K_zz, K_rxx, K_ryy, K_rzz])


def iso_pile_stiffness(
    diameter_m: float,
    embedment_m: float,
    soil_type: str = "dense_sand",
    G: float | None = None,
    nu: float | None = None,
    pile_type: str = "flexible",
) -> np.ndarray:
    """6x6 stiffness for a single pile per ISO 19901-4 Annex E.

    Distinguishes 'rigid' (slender, kinematic rotation) and
    'flexible' (long, elastic bending) pile responses.

    Reference
    ---------
    ISO 19901-4:2016 Annex E "Pile foundations".
    """
    G, nu = _get_soil_props(soil_type, G, nu)
    D = diameter_m
    L = embedment_m

    if pile_type == "rigid" or L / D < 6:
        # Short rigid pile — kinematic rotation dominates
        K_xx = 4.0 * G * D * (1.0 + L / D)
        K_zz = 4.0 * G * D * (1.0 + 0.5 * L / D) / (1.0 - nu)
        K_rxx = (G * D ** 3) * (1.0 + 0.7 * L / D)
        K_rzz = G * D ** 3 / 2.0
    else:
        # Long flexible pile — elastic bending dominates
        K_xx = 8.0 * G * D / (2.0 - nu)
        K_zz = 4.0 * G * D / (1.0 - nu) * (1.0 + L / D / 8.0)
        K_rxx = G * D ** 3 / 4.0 * (1.0 + L / D / 4.0)
        K_rzz = G * D ** 3 / 2.0

    return np.diag([K_xx, K_xx, K_zz, K_rxx, K_rxx, K_rzz])
