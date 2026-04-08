"""
Cyclic soil stiffness degradation (Phase 3 / Task 3.2).

Implements the Hardin-Drnevich (1972) modified-hyperbolic backbone
curve and the Vucetic-Dobry (1991) plasticity-index-dependent
reference shear strain, plus convenience wrappers that take a layered
soil profile and an applied (or estimated) cyclic shear strain and
return a degraded profile suitable for re-running the PISA Mode B
6x6 stiffness assembly under design-storm conditions.

Backbone curve
--------------
The modified hyperbolic Hardin-Drnevich:

    G / G_max = 1 / (1 + (gamma / gamma_ref) ** a)

with curvature exponent ``a`` (default 1.0 for the original 1972
form). For a = 0.92 the curve matches the Darendeli (2001)
formulation widely used in seismic site response analysis.

Reference strain
----------------
Vucetic & Dobry (1991) Figure 5: gamma_ref increases with plasticity
index (PI). For sands (PI = 0): gamma_ref ~ 1e-4. For high-plasticity
clays (PI = 200): gamma_ref ~ 5e-3. Linear-in-log fit between.

References
----------
Hardin, B. O., & Drnevich, V. P. (1972). "Shear modulus and damping
    in soils: design equations and curves". J. Soil Mech. Found. Div.
    ASCE, 98(7), 667-692.
Vucetic, M., & Dobry, R. (1991). "Effect of soil plasticity on cyclic
    response". J. Geotech. Eng., 117(1), 89-107.
Darendeli, M. B. (2001). "Development of a new family of normalized
    modulus reduction and material damping curves". PhD dissertation,
    Univ. of Texas at Austin.
"""
from __future__ import annotations

from dataclasses import replace

import numpy as np

from op3.standards.pisa import SoilState


# ---------------------------------------------------------------------------
# Backbone curve
# ---------------------------------------------------------------------------

def hardin_drnevich(gamma: float, gamma_ref: float, a: float = 1.0) -> float:
    """
    Modulus reduction G / G_max for shear strain ``gamma``.

    Parameters
    ----------
    gamma
        Cyclic shear strain (engineering strain, dimensionless).
    gamma_ref
        Reference shear strain at which G / G_max = 0.5.
    a
        Curvature exponent. Default 1.0 (Hardin-Drnevich 1972). Use
        0.92 for the Darendeli 2001 form.

    Returns
    -------
    float
        G / G_max in [0, 1].
    """
    if gamma <= 0:
        return 1.0
    return 1.0 / (1.0 + (gamma / gamma_ref) ** a)


def hardin_drnevich_array(gamma: np.ndarray, gamma_ref: float,
                          a: float = 1.0) -> np.ndarray:
    g = np.asarray(gamma, dtype=float)
    out = np.ones_like(g)
    pos = g > 0
    out[pos] = 1.0 / (1.0 + (g[pos] / gamma_ref) ** a)
    return out


def damping_ratio(gamma: float, gamma_ref: float,
                  D_min: float = 0.01, D_max: float = 0.20) -> float:
    """
    Hyperbolic damping ratio companion to the Hardin-Drnevich
    modulus reduction. Linearly interpolates between ``D_min`` (small
    strain) and ``D_max`` (large strain) using the same gamma_ref.
    """
    g_over = (gamma / gamma_ref) if gamma > 0 else 0.0
    return D_min + (D_max - D_min) * g_over / (1.0 + g_over)


# ---------------------------------------------------------------------------
# Reference strain from plasticity index (Vucetic-Dobry 1991)
# ---------------------------------------------------------------------------

# Approximate digitisation of Vucetic-Dobry (1991) Figure 5.
# Maps PI [%] -> gamma_ref [-].
_PI_KNOTS = np.array([0.0, 15.0, 30.0, 50.0, 100.0, 200.0])
_GAMMA_REF_KNOTS = np.array([1.0e-4, 2.5e-4, 5.0e-4, 1.0e-3, 3.0e-3, 5.0e-3])


def vucetic_dobry_gamma_ref(PI_percent: float) -> float:
    """
    Reference shear strain as a function of plasticity index.

    Linear-in-log interpolation through the Vucetic-Dobry (1991)
    Figure 5 curve. ``PI_percent = 0`` recovers the sand value
    (gamma_ref ~ 1e-4) and ``PI_percent = 200`` saturates at ~5e-3.
    """
    PI = float(np.clip(PI_percent, _PI_KNOTS[0], _PI_KNOTS[-1]))
    log_g = np.interp(PI, _PI_KNOTS, np.log10(_GAMMA_REF_KNOTS))
    return float(10.0 ** log_g)


def gamma_ref_for(soil: SoilState, PI_percent: float | None = None) -> float:
    """
    Pick a reference strain for a given SoilState. For sand (the
    Op^3 SoilState convention is su_or_phi = friction angle), use the
    sand baseline 1e-4. For clay use the Vucetic-Dobry curve with the
    user-supplied PI; if PI is not provided, default to PI = 30%.
    """
    if soil.soil_type == "clay":
        return vucetic_dobry_gamma_ref(PI_percent if PI_percent is not None else 30.0)
    return 1.0e-4


# ---------------------------------------------------------------------------
# Profile-level convenience
# ---------------------------------------------------------------------------

def degrade_profile(
    soil_profile: list[SoilState],
    cyclic_strain: float,
    PI_percent: float | None = None,
    a: float = 1.0,
) -> list[SoilState]:
    """
    Apply Hardin-Drnevich modulus reduction layer-by-layer to a
    soil profile and return a NEW profile with degraded G values.

    The original profile is not mutated. The new profile is suitable
    for re-running ``pisa_pile_stiffness_6x6`` to obtain a cyclic /
    strain-softened 6x6 K matrix.

    Parameters
    ----------
    soil_profile
        List of SoilState (same convention used by ``op3.standards.pisa``).
    cyclic_strain
        The shear strain at which the modulus is to be evaluated.
        Engineering strain, dimensionless.
    PI_percent
        Plasticity index for clay layers. Ignored for sand layers.
    a
        Hardin-Drnevich curvature exponent (default 1.0).

    Returns
    -------
    list[SoilState]
        Degraded profile with G_Pa replaced by G_max * (G/G_max).
    """
    if cyclic_strain < 0:
        raise ValueError("cyclic_strain must be non-negative")

    out: list[SoilState] = []
    for soil in soil_profile:
        gamma_ref = gamma_ref_for(soil, PI_percent)
        ratio = hardin_drnevich(cyclic_strain, gamma_ref, a=a)
        out.append(replace(soil, G_Pa=soil.G_Pa * ratio))
    return out


def cyclic_stiffness_6x6(
    *,
    diameter_m: float,
    embed_length_m: float,
    soil_profile: list[SoilState],
    cyclic_strain: float,
    PI_percent: float | None = None,
    a: float = 1.0,
    n_segments: int = 50,
) -> np.ndarray:
    """
    Convenience wrapper: degrade the profile via Hardin-Drnevich,
    then call ``pisa_pile_stiffness_6x6`` on the degraded profile.
    """
    from op3.standards.pisa import pisa_pile_stiffness_6x6

    degraded = degrade_profile(
        soil_profile, cyclic_strain, PI_percent=PI_percent, a=a)
    return pisa_pile_stiffness_6x6(
        diameter_m=diameter_m,
        embed_length_m=embed_length_m,
        soil_profile=degraded,
        n_segments=n_segments,
    )
