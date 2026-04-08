"""
API RP 2GEO — Geotechnical and Foundation Design Considerations.

Reference:
    API RP 2GEO (2011, addendum 2014). "Geotechnical and Foundation
    Design Considerations". American Petroleum Institute, 1st Edition.

API RP 2GEO is the American consensus standard for offshore geotechnical
foundation design. Section 8 provides closed-form impedance functions
for shallow and pile foundations that are essentially the Gazetas (1991)
formulas with API-specific shape correction factors.

This module also provides the **full Gazetas 6x6 coupled stiffness
matrix** including translational-rotational coupling terms, which is
the most accurate analytical 6x6 stiffness available for shallow
foundations and is the recommended Mode B input when no site-specific
PISA or FE analysis is available.
"""
from __future__ import annotations

import numpy as np

from op3.standards.dnv_st_0126 import _get_soil_props


def api_pile_stiffness(
    diameter_m: float,
    embedment_m: float,
    soil_type: str = "dense_sand",
    G: float | None = None,
    nu: float | None = None,
) -> np.ndarray:
    """6x6 pile stiffness per API RP 2GEO Section 8.3.

    Reference
    ---------
    API RP 2GEO (2011) Section 8.3 "Linear soil stiffness for foundation
        impedance analysis".
    """
    G, nu = _get_soil_props(soil_type, G, nu)
    D = diameter_m
    L = embedment_m
    R = 0.5 * D

    # API formulas (similar to ISO 19901-4 with API correction factors)
    K_xx = (8.0 * G * R / (2.0 - nu)) * (1.0 + 0.55 * (L / R) ** 0.85)
    K_zz = (4.0 * G * R / (1.0 - nu)) * (1.0 + 0.54 * L / R)
    K_rxx = ((8.0 / 3.0) * G * R ** 3 / (1.0 - nu)) * (1.0 + 2.3 * L / D)
    K_rzz = (16.0 / 3.0) * G * R ** 3

    return np.diag([K_xx, K_xx, K_zz, K_rxx, K_rxx, K_rzz])


def gazetas_full_6x6(
    radius_m: float,
    embedment_m: float = 0.0,
    soil_type: str = "dense_sand",
    G: float | None = None,
    nu: float | None = None,
) -> np.ndarray:
    """Full 6x6 coupled stiffness matrix per Gazetas (1991).

    Includes translational-rotational coupling terms K_xz, K_yz that
    are zero in the diagonal models. The coupling terms become
    significant for embedded foundations and are the right
    representation when used as a SubDyn 6x6 in OpenFAST.

    Reference
    ---------
    Gazetas, G. (1991). "Formulas and charts for impedances of surface
        and embedded foundations". Journal of Geotechnical Engineering
        117(9), 1363-1381.
    """
    G, nu = _get_soil_props(soil_type, G, nu)
    R = radius_m
    D = embedment_m

    K = np.zeros((6, 6))

    # Diagonal terms — Gazetas surface foundation
    K_x_0 = (8.0 * G * R) / (2.0 - nu)
    K_z_0 = (4.0 * G * R) / (1.0 - nu)
    K_rx_0 = (8.0 * G * R ** 3) / (3.0 * (1.0 - nu))
    K_rz_0 = (16.0 / 3.0) * G * R ** 3

    # Embedment factors
    if D > 0:
        eta_x = 1.0 + 0.55 * (D / R) ** 0.85
        eta_z = 1.0 + 0.54 * D / R
        eta_rx = 1.0 + 2.3 * D / (2 * R) + 0.58 * (D / (2 * R)) ** 3
        eta_rz = 1.0 + 1.6 * D / (2 * R)
        # Coupling term for embedded foundations
        K_xrx_factor = D * (1.0 / 3.0) * K_x_0 * eta_x
    else:
        eta_x = eta_z = eta_rx = eta_rz = 1.0
        K_xrx_factor = 0.0

    K[0, 0] = K_x_0 * eta_x        # Kxx
    K[1, 1] = K_x_0 * eta_x        # Kyy
    K[2, 2] = K_z_0 * eta_z        # Kzz
    K[3, 3] = K_rx_0 * eta_rx      # Krxx
    K[4, 4] = K_rx_0 * eta_rx      # Kryy
    K[5, 5] = K_rz_0 * eta_rz      # Krzz

    # Coupling: K_xrx (lateral-rocking)
    K[0, 4] = K_xrx_factor
    K[4, 0] = K_xrx_factor
    K[1, 3] = K_xrx_factor
    K[3, 1] = K_xrx_factor

    return K
