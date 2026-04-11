"""
Carbon Trust Offshore Wind Accelerator (OWA) suction bucket foundation
guidance.

Reference:
    Carbon Trust OWA (2019). "Bearing Capacity Report — Suction
    Bucket Jackets". The Carbon Trust, OWA Joint Industry Project.

    Houlsby, G. T., & Byrne, B. W. (2005). "Design procedures for
    installation of suction caissons in clay and other materials".
    Proc. ICE — Geotechnical Engineering, 158(2), 75-82.

    Houlsby, G. T., & Byrne, B. W. (2005). "Design procedures for
    installation of suction caissons in sand". Proc. ICE — Geotechnical
    Engineering, 158(3), 135-144.

The OWA Bearing Capacity Report is the most authoritative open
guidance on suction bucket foundation design and is the standard
that the offshore wind industry adopted for the early commercial
suction bucket projects (Borkum Riffgrund, Aberdeen Bay, Aberdeen
Offshore Wind Farm). Op^3 Mode B can use these expressions for
preliminary suction bucket stiffness when no site-specific PISA or
3D FE analysis is available.
"""
from __future__ import annotations

import numpy as np

from op3.standards.dnv_st_0126 import _get_soil_props


def owa_suction_bucket_stiffness(
    diameter_m: float,
    skirt_length_m: float,
    n_buckets: int = 1,
    spacing_m: float | None = None,
    soil_type: str = "soft_clay",
    G: float | None = None,
    nu: float | None = None,
) -> np.ndarray:
    """6x6 stiffness for a suction bucket per OWA Bearing Capacity Report.

    The OWA expressions are based on the Houlsby & Byrne (2005) caisson
    impedance functions extended to multi-bucket configurations
    (tripod, quadrupod) by treating each bucket as an independent
    foundation and combining via parallel axis theorem.

    Parameters
    ----------
    diameter_m : float
        Bucket outer diameter.
    skirt_length_m : float
        Skirt embedment depth.
    n_buckets : int, default 1
        Number of buckets (1, 3, or 4).
    spacing_m : float, optional
        Center-to-leg distance for multi-bucket configurations.
    soil_type, G, nu : as in dnv_st_0126.

    Reference
    ---------
    Carbon Trust OWA (2019), Section 4.3 "Equivalent linear stiffness
        for design"
    Houlsby, G. T., & Byrne, B. W. (2005), Section 5
    """
    G, nu = _get_soil_props(soil_type, G, nu)
    D = diameter_m
    L = skirt_length_m
    R = 0.5 * D

    # PHYSICS: Houlsby & Byrne (2005) Eqs. 5.2-5.5 — suction caisson elastic impedances
    # REVIEW-STATUS: PENDING (awaiting human verification against paper)
    # Houlsby & Byrne (2005) Eq. 5.2-5.5 for embedded caisson
    # Lateral
    K_xx_single = (4.0 * G * R / (1.0 - nu)) * (1.0 + 1.5 * L / R)
    # Vertical (axial)
    K_zz_single = (4.0 * G * R / (1.0 - nu)) * (1.0 + 0.6 * L / R)
    # Rocking
    K_rxx_single = ((8.0 / 3.0) * G * R ** 3 / (1.0 - nu)) * \
                   (1.0 + 1.0 * (L / R) + 0.3 * (L / R) ** 2)
    # Torsion
    K_rzz_single = (16.0 / 3.0) * G * R ** 3 * (1.0 + 0.5 * L / R)

    if n_buckets == 1:
        return np.diag([K_xx_single, K_xx_single, K_zz_single,
                        K_rxx_single, K_rxx_single, K_rzz_single])

    if spacing_m is None:
        raise ValueError(f"spacing_m required for n_buckets={n_buckets}")

    s = spacing_m
    K_xx = n_buckets * K_xx_single
    K_yy = K_xx
    K_zz = n_buckets * K_zz_single
    # Multi-bucket rocking dominated by axial * arm^2 (parallel axis)
    K_rxx = n_buckets * K_zz_single * s ** 2 / 2.0 + n_buckets * K_rxx_single
    K_ryy = K_rxx
    K_rzz = n_buckets * K_xx_single * s ** 2 / 2.0 + n_buckets * K_rzz_single

    return np.diag([K_xx, K_yy, K_zz, K_rxx, K_ryy, K_rzz])


def houlsby_byrne_caisson_stiffness(
    diameter_m: float,
    skirt_length_m: float,
    soil_type: str = "soft_clay",
    G: float | None = None,
    nu: float | None = None,
) -> np.ndarray:
    """Direct call to the single-caisson Houlsby & Byrne (2005) formulas.

    Convenience alias for `owa_suction_bucket_stiffness(n_buckets=1, ...)`.
    """
    return owa_suction_bucket_stiffness(
        diameter_m=diameter_m,
        skirt_length_m=skirt_length_m,
        n_buckets=1,
        soil_type=soil_type,
        G=G,
        nu=nu,
    )
