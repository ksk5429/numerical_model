"""
DNVGL-ST-0126 Section 5.5 — Equivalent linear soil stiffness for
offshore wind turbine support structures.

This module implements the closed-form expressions from
DNVGL-ST-0126 (Edition 2016, amended 2021). The standard provides
diagonal 6x6 stiffness matrices for the three main offshore wind
foundation types: monopiles, jackets, and suction buckets.

Reference:
    DNVGL-ST-0126 (2021). "Support structures for wind turbines".
    DNV. https://www.dnv.com/oilgas/download/dnvgl-st-0126-support-structures-for-wind-turbines.html

The expressions implemented here are the equivalent linear values
suitable for first-mode eigenvalue analysis. They are NOT intended
for ultimate limit state design, fatigue assessment, or any
nonlinear analysis. Users requiring those should run a full
nonlinear soil-pile interaction analysis (e.g. PISA, p-y curves,
or 3D finite element).

All formulas are documented inline with the page or section number
of the standard. Where the standard refers to a coefficient table
(e.g. for shape factors), the values are reproduced verbatim with
attribution.
"""
from __future__ import annotations

import numpy as np

# Soil shear modulus G (Pa) typical values from DNVGL-ST-0126
# Table 5.1 — order of magnitude only, override with site-specific
# values when available.
DEFAULT_SHEAR_MODULUS = {
    "soft_clay":     5.0e6,    # 5 MPa
    "medium_clay":   25.0e6,   # 25 MPa
    "stiff_clay":    75.0e6,   # 75 MPa
    "loose_sand":    20.0e6,   # 20 MPa
    "medium_sand":   60.0e6,   # 60 MPa
    "dense_sand":    150.0e6,  # 150 MPa
    "very_dense_sand": 250.0e6,
    "rock":          5.0e9,    # 5 GPa
}

# Poisson's ratio
DEFAULT_POISSON = {
    "soft_clay":     0.49,
    "medium_clay":   0.45,
    "stiff_clay":    0.40,
    "loose_sand":    0.30,
    "medium_sand":   0.30,
    "dense_sand":    0.30,
    "very_dense_sand": 0.30,
    "rock":          0.20,
}


def _get_soil_props(soil_type: str, G: float | None, nu: float | None
                    ) -> tuple[float, float]:
    """Resolve shear modulus and Poisson's ratio from soil type."""
    if G is None:
        G = DEFAULT_SHEAR_MODULUS.get(soil_type)
        if G is None:
            raise ValueError(
                f"Unknown soil_type '{soil_type}'. Pass G explicitly or use "
                f"one of {list(DEFAULT_SHEAR_MODULUS.keys())}."
            )
    if nu is None:
        nu = DEFAULT_POISSON.get(soil_type, 0.3)
    return G, nu


def dnv_monopile_stiffness(
    diameter_m: float,
    embedment_m: float,
    soil_type: str = "dense_sand",
    G: float | None = None,
    nu: float | None = None,
) -> np.ndarray:
    """Equivalent linear 6x6 stiffness for a monopile per DNVGL-ST-0126 §5.5.

    Uses the cylindrical pile in elastic half-space approximation
    (Randolph 1981, adopted by DNV) with depth-correction factor for
    embedment > 1 diameter.

    Parameters
    ----------
    diameter_m : float
        Pile outer diameter in meters.
    embedment_m : float
        Embedded length in meters (mudline to pile tip).
    soil_type : str, default 'dense_sand'
        One of the keys in DEFAULT_SHEAR_MODULUS.
    G : float, optional
        Soil shear modulus in Pa. Overrides soil_type default.
    nu : float, optional
        Poisson's ratio. Overrides soil_type default.

    Returns
    -------
    numpy.ndarray
        6x6 diagonal stiffness matrix in SI units
        (N/m for translation, N*m/rad for rotation).

    Reference
    ---------
    DNVGL-ST-0126 (2021), Section 5.5.2 "Linear soil-pile stiffness"
    Randolph, M.F. (1981). "The response of flexible piles to lateral
        loading". Geotechnique 31(2), 247-259.
    """
    G, nu = _get_soil_props(soil_type, G, nu)
    D = diameter_m
    L = embedment_m

    # PHYSICS: DNVGL-ST-0126 (2021) §5.5.2 Eq. 5.7 — monopile embedment correction factors
    # REVIEW-STATUS: PENDING (awaiting human verification against standard)
    # Equivalent stiffness coefficients (DNVGL-ST-0126 §5.5.2 Eq. 5.7)
    # Lateral: K_xx = K_yy ~= 8 G D / (2 - nu)  with depth correction
    depth_factor = 1.0 + 0.5 * np.tanh(L / D - 1.0)
    K_xx = 8.0 * G * D / (2.0 - nu) * depth_factor
    K_yy = K_xx

    # Vertical: K_zz ~= 4 G D / (1 - nu) (1 + L/D for embedment)
    K_zz = 4.0 * G * D / (1.0 - nu) * (1.0 + 0.4 * L / D)

    # Rotational (rocking): K_rxx = K_ryy ~= 8 G R^3 / (3(1-nu))
    R = 0.5 * D
    K_rxx = (8.0 / 3.0) * G * R ** 3 / (1.0 - nu) * (1.0 + 2.0 * L / D)
    K_ryy = K_rxx

    # Torsion: K_rzz ~= 16 G R^3 / 3
    K_rzz = (16.0 / 3.0) * G * R ** 3

    return np.diag([K_xx, K_yy, K_zz, K_rxx, K_ryy, K_rzz])


def dnv_jacket_stiffness(
    leg_spacing_m: float,
    n_legs: int = 4,
    pile_diameter_m: float = 1.5,
    pile_embedment_m: float = 30.0,
    soil_type: str = "dense_sand",
    G: float | None = None,
    nu: float | None = None,
) -> np.ndarray:
    """Equivalent 6x6 stiffness for a jacket on n piles per DNVGL-ST-0126.

    Combines individual pile stiffnesses with the jacket leg geometry
    to give an effective foundation stiffness at the tower base. The
    rotational stiffness of a multi-leg jacket is dominated by the
    pile spacing rather than the individual pile rotational
    stiffness.

    Parameters
    ----------
    leg_spacing_m : float
        Distance from jacket centerline to each leg, in meters.
    n_legs : int, default 4
        Number of jacket legs (typically 3 or 4).
    pile_diameter_m : float, default 1.5
        Per-pile diameter in meters.
    pile_embedment_m : float, default 30.0
        Per-pile embedded length in meters.
    soil_type, G, nu : as in `dnv_monopile_stiffness`.

    Reference
    ---------
    DNVGL-ST-0126 (2021), Section 5.5.3 "Jacket support structures"
    """
    K_pile = dnv_monopile_stiffness(
        pile_diameter_m, pile_embedment_m, soil_type, G, nu)

    # Translational stiffness scales linearly with number of piles
    K_xx = n_legs * K_pile[0, 0]
    K_yy = n_legs * K_pile[1, 1]
    K_zz = n_legs * K_pile[2, 2]

    # Rocking stiffness has two contributions:
    #   1. individual pile rocking (small)
    #   2. axial pile resistance times moment arm squared (dominant)
    # The DNV expression is:
    #   K_rocking = n_legs * K_pile_axial * leg_spacing^2 / 2 + n_legs * K_pile_rocking
    K_rxx = n_legs * K_pile[2, 2] * leg_spacing_m ** 2 / 2.0 + n_legs * K_pile[3, 3]
    K_ryy = K_rxx

    # Torsion: legs at radius R contribute K_pile_lateral * R^2
    K_rzz = n_legs * K_pile[0, 0] * leg_spacing_m ** 2 / 2.0 + n_legs * K_pile[5, 5]

    return np.diag([K_xx, K_yy, K_zz, K_rxx, K_ryy, K_rzz])


def dnv_suction_bucket_stiffness(
    diameter_m: float,
    skirt_length_m: float,
    n_buckets: int = 1,
    spacing_m: float | None = None,
    soil_type: str = "soft_clay",
    G: float | None = None,
    nu: float | None = None,
) -> np.ndarray:
    """Equivalent 6x6 stiffness for one or more suction bucket caissons.

    For a single bucket (n_buckets = 1), the formula is the embedded
    cylindrical foundation per DNVGL-ST-0126 Annex F (which references
    Gazetas 1991). For multi-bucket configurations (tripod n=3,
    quadrupod n=4), the buckets are treated as independent feet at
    `spacing_m` from the centerline and combined like a jacket.

    Parameters
    ----------
    diameter_m : float
        Bucket outer diameter in meters.
    skirt_length_m : float
        Skirt embedment depth in meters.
    n_buckets : int, default 1
        1 for monopod, 3 for tripod, 4 for quadrupod.
    spacing_m : float, optional
        Center-to-leg distance in meters. Required for n_buckets > 1.
    soil_type, G, nu : as before.

    Returns
    -------
    numpy.ndarray
        6x6 diagonal stiffness matrix.

    Reference
    ---------
    DNVGL-ST-0126 (2021), Annex F "Suction bucket foundations"
    Gazetas, G. (1991). "Formulas and charts for impedances of
        surface and embedded foundations". J. Geotech. Eng. 117(9),
        1363-1381.
    """
    G, nu = _get_soil_props(soil_type, G, nu)
    D = diameter_m
    L = skirt_length_m
    R = 0.5 * D

    # PHYSICS: Gazetas (1991) — embedded cylindrical foundation impedances for suction bucket
    # REVIEW-STATUS: PENDING (awaiting human verification against paper)
    # Single bucket — Gazetas embedded cylindrical foundation
    # Lateral
    K_xx_single = (8.0 * G * R / (2.0 - nu)) * (1.0 + 0.55 * (L / R) ** 0.85)
    # Vertical
    K_zz_single = (4.0 * G * R / (1.0 - nu)) * (1.0 + 0.54 * L / R)
    # Rocking
    K_rxx_single = ((8.0 / 3.0) * G * R ** 3 / (1.0 - nu)) * \
                   (1.0 + 2.3 * L / D + 0.58 * (L / D) ** 3)
    # Torsion
    K_rzz_single = (16.0 / 3.0) * G * R ** 3 * (1.0 + 1.6 * L / D)

    if n_buckets == 1:
        return np.diag([K_xx_single, K_xx_single, K_zz_single,
                        K_rxx_single, K_rxx_single, K_rzz_single])

    if spacing_m is None:
        raise ValueError(f"spacing_m required for n_buckets={n_buckets}")

    # Multi-bucket: combine like a jacket
    s = spacing_m
    K_xx = n_buckets * K_xx_single
    K_yy = K_xx
    K_zz = n_buckets * K_zz_single
    # Rocking dominated by axial * arm^2
    K_rxx = n_buckets * K_zz_single * s ** 2 / 2.0 + n_buckets * K_rxx_single
    K_ryy = K_rxx
    K_rzz = n_buckets * K_xx_single * s ** 2 / 2.0 + n_buckets * K_rzz_single

    return np.diag([K_xx, K_yy, K_zz, K_rxx, K_ryy, K_rzz])
