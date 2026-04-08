"""
PISA monopile soil reaction framework (Phase 3 / Task 3.1).

Implements the PISA (Pile Soil Analysis) one-dimensional macro-element
formulation for laterally loaded monopiles in sand and clay. PISA
replaces the legacy API RP 2GEO p-y curves with FOUR distributed
reaction components per pile depth segment:

    1. p(z, v)   distributed lateral load     [N/m]    f(local lateral disp v)
    2. m(z, psi) distributed moment           [N]      f(local rotation psi)
    3. H_b(v_b)  pile-base shear              [N]      f(base lateral disp)
    4. M_b(psi_b) pile-base moment            [Nm]     f(base rotation)

The non-dimensional shape functions are 4-parameter conic curves:

    y / y_u = ((x_u - x) / (x_u - x_y)) - sqrt(((x_u - x) / (x_u - x_y))^2 - 4 n x / x_u * ((x_u - x_y) / x_u))

with parameters (k, n, x_u, y_u) calibrated for each component and
each soil type. This module exposes:

    pisa_lateral_pl(z, v, D, L, soil)            -> p [N/m]
    pisa_moment_pl (z, psi, D, L, soil)          -> m [N]
    pisa_base_shear (v_b, D, soil)               -> H_b [N]
    pisa_base_moment(psi_b, D, soil)             -> M_b [Nm]
    pisa_pile_stiffness_6x6(D, L, soil_profile) -> 6x6 K via small-strain

References
----------
Burd, H. J. et al. (2020). "PISA design model for monopiles for
    offshore wind turbines: application to a stiff glacial clay till".
    Geotechnique 70(11), 1030-1047.
Byrne, B. W. et al. (2020). "PISA design model for monopiles for
    offshore wind turbines: application to a marine sand".
    Geotechnique 70(11), 1048-1066.
McAdam, R. A. et al. (2020). "Monotonic laterally loaded pile testing
    in a dense marine sand at Dunkirk". Geotechnique 70(11), 986-998.

Calibration regime
------------------
The published PISA coefficients are calibrated for:
    L/D = 2..10  (rigid to semi-rigid monopiles)
    D   = 2..10 m
The parameters in this module are reproduced from Burd 2020 Table 6
(clay) and Byrne 2020 Table 7 (sand). Other soils require independent
calibration.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import numpy as np


# ---------------------------------------------------------------------------
# Calibrated PISA shape-function parameters
# ---------------------------------------------------------------------------
# Each component uses (k, n, x_u, y_u_norm) where:
#   k        = initial stiffness (normalised)
#   n        = curvature parameter (0..1, 0 = bilinear, 1 = elastic-perfectly plastic)
#   x_u      = displacement at ultimate (normalised)
#   y_u_norm = ultimate value (normalised by reference)
#
# Sources: Byrne 2020 Table 7 (sand, Dunkirk DR=80%)
#          Burd  2020 Table 6 (clay, Cowden glacial till)


PISA_SAND = {
    "lateral_p":   {"k": 8.731,  "n": 0.917, "x_u": 146.1, "y_u": 0.413},
    "moment_m":    {"k": 1.412,  "n": 0.0,   "x_u": 173.1, "y_u": 0.0577},
    "base_shear":  {"k": 2.717,  "n": 0.976, "x_u": 235.7, "y_u": 0.265},
    "base_moment": {"k": 0.2683, "n": 0.886, "x_u": 173.1, "y_u": 0.0989},
}

PISA_CLAY = {
    "lateral_p":   {"k": 10.6,   "n": 0.939, "x_u": 241.4, "y_u": 1.071},
    "moment_m":    {"k": 1.420,  "n": 0.0,   "x_u": 115.0, "y_u": 0.205},
    "base_shear":  {"k": 2.140,  "n": 0.792, "x_u": 173.0, "y_u": 0.367},
    "base_moment": {"k": 0.2150, "n": 0.804, "x_u": 173.1, "y_u": 0.135},
}

PISA_PARAMS = {"sand": PISA_SAND, "clay": PISA_CLAY}


# ---------------------------------------------------------------------------
# Conic shape function
# ---------------------------------------------------------------------------

def conic(x: float, k: float, n: float, x_u: float, y_u: float) -> float:
    """
    PISA 4-parameter conic function.

    y / y_u = c1 - sqrt(c1^2 - 4 n (x / x_u) c2)

    where
        c1 = 1 + n (1 - x / x_u)
        c2 = 1 - n
    For n -> 0 the curve is bilinear (k for x < x_y, then plateau at y_u).
    For n -> 1 it is asymptotically elastic-perfectly plastic.
    """
    if x <= 0:
        return 0.0
    if x >= x_u:
        return y_u
    xn = x / x_u
    c2 = 1.0 - n
    c1 = 1.0 + n * (1.0 - xn)
    disc = c1 * c1 - 4.0 * n * xn * c2
    if disc < 0:
        disc = 0.0
    return y_u * (c1 - np.sqrt(disc)) / max(2.0 * (1.0 - n), 1e-12) if n < 1 - 1e-6 \
        else y_u * (1.0 - (1.0 - xn) ** 2)


def conic_initial_slope(k: float, y_u: float, x_u: float) -> float:
    """Initial slope at x = 0 of the normalised conic = k * y_u / x_u."""
    return k * y_u / x_u


# ---------------------------------------------------------------------------
# PISA reaction components (dimensional)
# ---------------------------------------------------------------------------

@dataclass
class SoilState:
    """Local soil properties at a given depth."""
    depth_m: float
    G_Pa: float            # small-strain shear modulus
    su_or_phi: float       # undrained shear strength [Pa] (clay) or friction angle [deg] (sand)
    soil_type: Literal["sand", "clay"]


def _ref_pressure(z: float, soil: SoilState) -> float:
    """Reference normalising pressure: sigma_v' for sand, su for clay."""
    if soil.soil_type == "clay":
        return max(soil.su_or_phi, 1.0)
    # Effective vertical stress, simple buoyant unit weight 10 kN/m^3
    return max(10.0e3 * z, 1.0)


def pisa_lateral_pl(z: float, v: float, D: float, L: float,
                    soil: SoilState) -> float:
    """Distributed lateral reaction p [N/m] at depth z, displacement v."""
    p = PISA_PARAMS[soil.soil_type]["lateral_p"]
    sigma_ref = _ref_pressure(z, soil)
    # Normalisations from Byrne 2020 Eq. 1: v_norm = v G / (D sigma_ref)
    v_norm = v * soil.G_Pa / (D * sigma_ref)
    y_norm = conic(v_norm, **p)
    return y_norm * sigma_ref * D     # p [N/m]


def pisa_moment_pl(z: float, psi: float, D: float, L: float,
                   soil: SoilState) -> float:
    """Distributed moment reaction m [N] at depth z, rotation psi."""
    p = PISA_PARAMS[soil.soil_type]["moment_m"]
    sigma_ref = _ref_pressure(z, soil)
    psi_norm = psi * soil.G_Pa / sigma_ref
    y_norm = conic(psi_norm, **p)
    return y_norm * sigma_ref * D ** 2    # m [N]


def pisa_base_shear(v_b: float, D: float, soil: SoilState) -> float:
    """Pile-base shear H_b [N] as a function of base lateral displacement."""
    p = PISA_PARAMS[soil.soil_type]["base_shear"]
    sigma_ref = _ref_pressure(0.0, soil)   # base = ref at z=L (caller passes)
    v_norm = v_b * soil.G_Pa / (D * sigma_ref)
    y_norm = conic(v_norm, **p)
    return y_norm * sigma_ref * D ** 2


def pisa_base_moment(psi_b: float, D: float, soil: SoilState) -> float:
    """Pile-base moment M_b [Nm] as a function of base rotation."""
    p = PISA_PARAMS[soil.soil_type]["base_moment"]
    sigma_ref = _ref_pressure(0.0, soil)
    psi_norm = psi_b * soil.G_Pa / sigma_ref
    y_norm = conic(psi_norm, **p)
    return y_norm * sigma_ref * D ** 3


# ---------------------------------------------------------------------------
# 6x6 small-strain stiffness from PISA initial slopes
# ---------------------------------------------------------------------------

def pisa_pile_stiffness_6x6(
    diameter_m: float,
    embed_length_m: float,
    soil_profile: list[SoilState],
    n_segments: int = 50,
) -> np.ndarray:
    """
    Initial small-strain 6x6 K matrix at the pile head (mudline) by
    integrating the PISA distributed reactions along the embedded
    length and adding the base contributions.

    The cross-coupling K_xrx (lateral-rocking) is computed via the
    second moment of the distributed lateral stiffness:

        K_xx   = int_0^L  k_p(z) dz   +  K_b_shear
        K_xrx  = int_0^L  k_p(z) z dz  (-)
        K_rxrx = int_0^L  k_p(z) z^2 dz + int_0^L k_m(z) dz + K_b_moment

    Vertical and torsional terms use elementary skin-friction estimates
    since PISA does not address them; this is consistent with how
    monopile designers extend PISA in DNV-ST-0126 commentary.
    """
    D = diameter_m
    L = embed_length_m
    if len(soil_profile) == 0:
        raise ValueError("soil_profile must contain at least one SoilState")
    # Linear interp on the profile by depth
    depths = np.array([s.depth_m for s in soil_profile])
    G = np.array([s.G_Pa for s in soil_profile])

    zs = np.linspace(0.0, L, n_segments + 1)
    z_mid = 0.5 * (zs[:-1] + zs[1:])
    dz = zs[1] - zs[0]

    Kxx = 0.0
    Kxrx = 0.0
    Krxrx = 0.0
    for z in z_mid:
        G_z = float(np.interp(z, depths, G))
        soil = SoilState(z, G_z, soil_profile[0].su_or_phi,
                         soil_profile[0].soil_type)
        sigma_ref = _ref_pressure(z, soil)
        p_par = PISA_PARAMS[soil.soil_type]["lateral_p"]
        m_par = PISA_PARAMS[soil.soil_type]["moment_m"]
        # Initial stiffness: dy/dx at x=0 of the normalised conic = k
        # In dimensional form: k_p = k * G  (units N/m / m)
        k_p = p_par["k"] * G_z          # N/m / m of pile
        k_m = m_par["k"] * G_z * D ** 2 # Nm / rad / m
        Kxx += k_p * dz
        Kxrx += k_p * dz * z
        Krxrx += k_p * dz * z * z + k_m * dz

    # Base contributions
    G_b = float(np.interp(L, depths, G))
    bs = PISA_PARAMS[soil_profile[0].soil_type]["base_shear"]
    bm = PISA_PARAMS[soil_profile[0].soil_type]["base_moment"]
    K_b_shear = bs["k"] * G_b * D
    K_b_moment = bm["k"] * G_b * D ** 3
    Kxx += K_b_shear
    Krxrx += K_b_moment + K_b_shear * L * L
    Kxrx += K_b_shear * L

    # Vertical and torsional via Randolph-Wroth (1979) shaft friction
    # K_zz ~ 2 pi G L / ln(2 L / D)
    G_avg = float(np.mean(G))
    Kzz = 2 * np.pi * G_avg * L / np.log(max(2 * L / D, 1.1))
    Krzz = (16.0 / 3.0) * G_avg * (D / 2) ** 3   # torsion of rigid disk

    K = np.diag([Kxx, Kxx, Kzz, Krxrx, Krxrx, Krzz])
    K[0, 4] = K[4, 0] = -Kxrx
    K[1, 3] = K[3, 1] = Kxrx
    return K
