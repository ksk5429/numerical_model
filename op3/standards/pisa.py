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

- L/D = 2..10  (rigid to semi-rigid monopiles)
- D   = 2..10 m

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


#
# ---- SAND (Burd 2020 Table 5, D_R = 75%) -----------------------------------
# "First-stage" depth-function form:
#     k_p  = k_p1 + k_p2 * (z/D)
#     k_m  = const
#     k_H  = k_H1 + k_H2 * (L/D)        (pile-base shear)
#     k_M  = const                       (pile-base moment)
#
# ---- CLAY (Byrne 2020 Table 4, "Second-stage calibration") -----------------
# Same structure. Note the Byrne 2020 paper uses cot(phi)-shifted stresses
# but for initial elastic stiffness evaluation we only need the linear
# coefficients.

PISA_SAND = {
    "lateral_p": {
        "k_1": 8.64, "k_2": -0.81,       # k_p = 8.64 - 0.81 z/D
        "n_1": 0.966, "n_2": 0.0,
        "x_u_1": 64.78, "x_u_2": 0.0,
        "y_u_1": 20.86, "y_u_2": -5.83,  # y_u varies with z/L
    },
    "moment_m": {
        "k_1": 18.1, "k_2": 0.0,
        "n_1": 0.0, "n_2": 0.0,
        "x_u_1": 64.78, "x_u_2": 0.0,
        "y_u_1": 0.23, "y_u_2": -0.05,
    },
    "base_shear": {                      # L/D-dependent
        "k_1": 3.28, "k_2": -0.37,       # k_H = 3.28 - 0.37 * (L/D)
        "n_1": 0.83, "n_2": -0.058,
        "x_u_1": 2.13, "x_u_2": -0.31,
        "y_u_1": 0.63, "y_u_2": -0.07,
    },
    "base_moment": {                     # Constant except ultimate
        "k_1": 0.30, "k_2": 0.0,
        "n_1": 0.86, "n_2": 0.0,
        "x_u_1": 49.4, "x_u_2": 0.0,
        "y_u_1": 0.39, "y_u_2": -0.05,
    },
}

# Byrne 2020 clay (Cowden till), second-stage calibration. Table 4.
# Distributed lateral p: k_p = 10.60 - 1.650 * (z/D)
# Curvature: n_p = 0.9390 - 0.03345 * (z/D)
# Ultimate p: p_u = 10.70 - 7.101 * exp(-0.3085 * z/D)  -- nonlinear.
# For the small-strain 6x6 stiffness we only need the initial slope,
# so we approximate the ultimate with the linear expansion near z/D = 0
# (which overpredicts capacity at depth but does not affect the initial
# slope). Full nonlinear support is a follow-up.

PISA_CLAY = {
    "lateral_p": {
        "k_1": 10.60, "k_2": -1.650,     # k_p = 10.60 - 1.650 z/D
        "n_1": 0.9390, "n_2": -0.03345,
        "x_u_1": 241.4, "x_u_2": 0.0,
        "y_u_1": 3.599, "y_u_2": 0.0,    # = 10.70 - 7.101 (linear approx)
    },
    "moment_m": {
        "k_1": 1.420, "k_2": -0.09643,
        "n_1": 0.0, "n_2": 0.0,
        "x_u_1": 115.0, "x_u_2": 0.0,
        "y_u_1": 0.2899, "y_u_2": -0.04775,
    },
    "base_shear": {                      # L/D-dependent
        "k_1": 2.717, "k_2": -0.3575,
        "n_1": 0.8793, "n_2": -0.03150,
        "x_u_1": 235.7, "x_u_2": 0.0,
        "y_u_1": 0.4038, "y_u_2": 0.04812,
    },
    "base_moment": {                     # L/D-dependent
        "k_1": 0.2146, "k_2": -0.002132,
        "n_1": 1.079, "n_2": -0.1087,
        "x_u_1": 173.1, "x_u_2": 0.0,
        "y_u_1": 0.8192, "y_u_2": -0.08588,
    },
}

PISA_PARAMS = {"sand": PISA_SAND, "clay": PISA_CLAY}


def pisa_coeffs(component: str, soil_type: str,
                z_over_D: float = 0.0,
                L_over_D: float = 0.0) -> dict:
    """
    Evaluate the depth-function-adjusted conic parameters for a
    specific soil reaction component at a given depth.

    For distributed components ``lateral_p`` and ``moment_m`` the
    variable is ``z/D``. For base components ``base_shear`` and
    ``base_moment`` the variable is ``L/D`` (the full pile slenderness)
    and the ``z/D`` argument is ignored.
    """
    table = PISA_PARAMS[soil_type][component]
    var = L_over_D if component.startswith("base") else z_over_D
    return {
        "k":   max(table["k_1"]   + table["k_2"]   * var, 1e-6),
        "n":   max(min(table["n_1"] + table["n_2"] * var, 0.999), 0.0),
        "x_u": max(table["x_u_1"] + table["x_u_2"] * var, 1e-6),
        "y_u": max(table["y_u_1"] + table["y_u_2"] * var, 1e-6),
    }


# ---------------------------------------------------------------------------
# Conic shape function
# ---------------------------------------------------------------------------

def conic(x: float, k: float, n: float, x_u: float, y_u: float) -> float:
    """
    PISA 4-parameter conic function.

    y / y_u = c1 - sqrt(c1^2 - 4 n (x / x_u) c2)

    where:

    - c1 = 1 + n (1 - x / x_u)
    - c2 = 1 - n

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
    p = pisa_coeffs("lateral_p", soil.soil_type, z_over_D=z / D)
    sigma_ref = _ref_pressure(z, soil)
    v_norm = v * soil.G_Pa / (D * sigma_ref)
    y_norm = conic(v_norm, **p)
    return y_norm * sigma_ref * D


def pisa_moment_pl(z: float, psi: float, D: float, L: float,
                   soil: SoilState) -> float:
    """Distributed moment reaction m [N] at depth z, rotation psi."""
    p = pisa_coeffs("moment_m", soil.soil_type, z_over_D=z / D)
    sigma_ref = _ref_pressure(z, soil)
    psi_norm = psi * soil.G_Pa / sigma_ref
    y_norm = conic(psi_norm, **p)
    return y_norm * sigma_ref * D ** 2


def pisa_base_shear(v_b: float, D: float, soil: SoilState,
                    L: float = 0.0) -> float:
    """Pile-base shear H_b [N] as a function of base lateral displacement."""
    p = pisa_coeffs("base_shear", soil.soil_type, L_over_D=L / D)
    sigma_ref = _ref_pressure(0.0, soil)
    v_norm = v_b * soil.G_Pa / (D * sigma_ref)
    y_norm = conic(v_norm, **p)
    return y_norm * sigma_ref * D ** 2


def pisa_base_moment(psi_b: float, D: float, soil: SoilState,
                     L: float = 0.0) -> float:
    """Pile-base moment M_b [Nm] as a function of base rotation."""
    p = pisa_coeffs("base_moment", soil.soil_type, L_over_D=L / D)
    sigma_ref = _ref_pressure(0.0, soil)
    psi_norm = psi_b * soil.G_Pa / sigma_ref
    y_norm = conic(psi_norm, **p)
    return y_norm * sigma_ref * D ** 3


# ---------------------------------------------------------------------------
# 6x6 small-strain stiffness from PISA initial slopes
# ---------------------------------------------------------------------------

def effective_head_stiffness(K: np.ndarray, h_load_m: float) -> float:
    """
    Secant stiffness H / v_G for a horizontal load H applied at height
    ``h_load_m`` above the ground-line reference of the 6x6 pile-head
    stiffness matrix.

    For a rigid-pile 2x2 {translation, rotation} block
        [ Kxx   Kxrx ] [v ]   [ H    ]
        [ Kxrx  Krxrx] [psi] = [ H h  ]
    the ground-level translation is
        v = H (Krxrx - h Kxrx) / det
    where det = Kxx Krxrx - Kxrx^2. Therefore
        k_eff = H / v = det / (Krxrx - h Kxrx).

    This is the apples-to-apples comparator for the McAdam 2020 and
    Byrne 2020 field-test k_Hinit values, which are defined as the
    secant slope of H vs v_G at small displacement.
    """
    # For a horizontal force in +x producing rotation about +y, the
    # relevant 2x2 block is (x, ry). K[0,4] is the off-diagonal.
    Kxx = float(K[0, 0])
    Kryry = float(K[4, 4])
    Kx_ry = float(K[0, 4])
    det = Kxx * Kryry - Kx_ry ** 2
    # For the Op^3 convention K[0,4] is negative; the sign makes the
    # denominator (Kryry - h * Kx_ry) strictly positive.
    denom = Kryry - h_load_m * Kx_ry
    if abs(denom) < 1e-30:
        return float("inf")
    return abs(det / denom)


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
    L_over_D = L / D
    soil_type = soil_profile[0].soil_type
    for z in z_mid:
        G_z = float(np.interp(z, depths, G))
        z_over_D = z / D
        p_par = pisa_coeffs("lateral_p", soil_type, z_over_D=z_over_D)
        m_par = pisa_coeffs("moment_m", soil_type, z_over_D=z_over_D)
        # Depth-function-adjusted initial slopes. In the PISA
        # normalisation:  dp/dv = k_p(z) * G(z)    [N/m^2]
        #                 dm/dpsi = k_m(z) * G(z) * D^2
        # The factor k_p = k_p1 + k_p2 * (z/D) reduces for short
        # rigid piles, which is the key physics missed in v0.3.0.
        k_p = max(p_par["k"], 0.0) * G_z
        k_m = max(m_par["k"], 0.0) * G_z * D ** 2
        Kxx += k_p * dz
        Kxrx += k_p * dz * z
        Krxrx += k_p * dz * z * z + k_m * dz

    # Base contributions (L/D-dependent)
    G_b = float(np.interp(L, depths, G))
    bs = pisa_coeffs("base_shear", soil_type, L_over_D=L_over_D)
    bm = pisa_coeffs("base_moment", soil_type, L_over_D=L_over_D)
    K_b_shear = max(bs["k"], 0.0) * G_b * D
    K_b_moment = max(bm["k"], 0.0) * G_b * D ** 3
    Kxx += K_b_shear
    Krxrx += K_b_moment + K_b_shear * L * L
    Kxrx += K_b_shear * L

    # Vertical stiffness: full pile shaft friction + base bearing.
    # For a slender elastic pile in a halfspace,
    #     K_zz ~ 2 pi G_avg L / ln(2 L / D) + 4 G_b D
    # The base bearing term from Randolph & Wroth (1978).
    # Torsional stiffness: slender pile shaft integral rather than
    # the rigid-disk value.
    #     K_rzz ~ pi G_avg D^3 * L / (L + 2 D)  (empirical slender-pile form)
    G_avg = float(np.mean(G))
    Kzz = 2 * np.pi * G_avg * L / np.log(max(2 * L / D, 1.1)) \
          + 4.0 * G_b * D
    Krzz = np.pi * G_avg * (D ** 3) * L / (L + 2.0 * D)

    K = np.diag([Kxx, Kxx, Kzz, Krxrx, Krxrx, Krzz])
    K[0, 4] = K[4, 0] = -Kxrx
    K[1, 3] = K[3, 1] = Kxrx
    return K
