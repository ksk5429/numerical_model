"""
Data model for suction-anchor analysis.

Three dataclasses, all SI-consistent with the rest of Op^3:

    SuctionAnchor           geometry + steel properties
    UndrainedClayProfile    linearly increasing undrained shear strength
    MooringLoad             tension + angle at padeye

References
----------
DNV-RP-E303 (2021), Section 2.2 "Geometry and notation".
Randolph, M. F., & Gourvenec, S. (2011). Offshore Geotechnical
    Engineering, Ch. 9.
Aubeny, C. P., Han, S.-W., & Murff, J. D. (2003). "Inclined load
    capacity of suction caissons". IJNAMG 27(14), 1235-1254.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import numpy as np


# ---------------------------------------------------------------------------
# Geometry
# ---------------------------------------------------------------------------

@dataclass
class SuctionAnchor:
    """Suction-anchor geometry and steel properties.

    All dimensions in SI units (m, mm for wall thickness, kN for weight).

    Parameters
    ----------
    diameter_m : float
        Outer diameter ``D``. Practical range 3-8 m.
    skirt_length_m : float
        Embedded skirt length ``L``. Typical range 10-30 m in deep-water
        clay; aspect ratio ``L/D`` usually between 1 and 6.
    wall_thickness_mm : float, default 30.0
        Skirt wall thickness. Typical range 20-50 mm.
    padeye_depth_m : Optional[float]
        Depth of the mooring attachment point below the mudline. If
        ``None``, the caller must set it (``optimal_padeye_*`` helpers in
        :mod:`op3.anchors.padeye` return a recommendation).
    padeye_offset_m : float, default 0.0
        Lateral offset of the padeye from the anchor centreline. A
        non-zero value introduces an installation-phase torque in some
        models but is ignored by the capacity methods implemented here
        (they assume plane of symmetry).
    lid_thickness_mm : float, default 40.0
        Top-cap plate thickness.
    submerged_weight_kN : float, default 0.0
        Total submerged weight of the anchor (steel minus buoyancy of
        displaced water). Used in self-weight penetration and vertical
        capacity. ``0.0`` is the conservative default for design-stage
        capacity checks.
    steel_grade : str, default "S355"
        Informational only; not used by any calculation.

    Notes
    -----
    The "outer" diameter is used throughout for shaft friction and lid
    area. The inner diameter is derived as ``D - 2 * wall_thickness``.
    Wall thickness enters only via inner-shaft and annulus areas and is
    a second-order effect for typical offshore anchors.
    """
    diameter_m: float
    skirt_length_m: float
    wall_thickness_mm: float = 30.0
    padeye_depth_m: Optional[float] = None
    padeye_offset_m: float = 0.0
    lid_thickness_mm: float = 40.0
    submerged_weight_kN: float = 0.0
    steel_grade: str = "S355"

    def __post_init__(self) -> None:
        if self.diameter_m <= 0:
            raise ValueError(f"diameter_m must be > 0, got {self.diameter_m}")
        if self.skirt_length_m <= 0:
            raise ValueError(f"skirt_length_m must be > 0, got {self.skirt_length_m}")
        if self.wall_thickness_mm <= 0:
            raise ValueError(
                f"wall_thickness_mm must be > 0, got {self.wall_thickness_mm}"
            )
        if self.padeye_depth_m is not None:
            if not (0.0 < self.padeye_depth_m < self.skirt_length_m):
                raise ValueError(
                    f"padeye_depth_m must satisfy 0 < z_p < L "
                    f"(L={self.skirt_length_m}), got {self.padeye_depth_m}"
                )
        # Physical plausibility: wall thickness must be smaller than radius
        if self.wall_thickness_mm / 1000.0 >= self.diameter_m / 2.0:
            raise ValueError(
                f"wall_thickness_mm={self.wall_thickness_mm} mm exceeds "
                f"radius={self.diameter_m / 2.0 * 1000:.1f} mm"
            )

    @property
    def aspect_ratio(self) -> float:
        """L/D ratio (dimensionless)."""
        return self.skirt_length_m / self.diameter_m

    @property
    def inner_diameter_m(self) -> float:
        """Inner diameter D - 2*t_w."""
        return self.diameter_m - 2.0 * self.wall_thickness_mm / 1000.0

    @property
    def outer_skirt_area_m2(self) -> float:
        """Outer shaft surface area in contact with soil, ``pi * D * L``."""
        return np.pi * self.diameter_m * self.skirt_length_m

    @property
    def inner_skirt_area_m2(self) -> float:
        """Inner shaft surface area in contact with soil plug,
        ``pi * D_i * L``."""
        return np.pi * self.inner_diameter_m * self.skirt_length_m

    @property
    def lid_area_m2(self) -> float:
        """Full plan area of the top cap, ``pi/4 * D**2``."""
        return np.pi / 4.0 * self.diameter_m ** 2

    @property
    def lid_inner_area_m2(self) -> float:
        """Interior plan area (soil-plug face area), ``pi/4 * D_i**2``."""
        return np.pi / 4.0 * self.inner_diameter_m ** 2

    @property
    def annulus_area_m2(self) -> float:
        """Steel annulus area at skirt tip, ``pi/4 * (D^2 - D_i^2)``."""
        return np.pi / 4.0 * (self.diameter_m ** 2 - self.inner_diameter_m ** 2)


# ---------------------------------------------------------------------------
# Soil
# ---------------------------------------------------------------------------

@dataclass
class UndrainedClayProfile:
    """Linearly increasing undrained shear strength profile.

    This is the standard design profile for deep-water normally or
    lightly over-consolidated clay at anchor sites. For more complex
    profiles, split into layers and integrate numerically.

    Parameters
    ----------
    su_mudline_kPa : float
        ``s_u(z=0)``. Typical range 2-10 kPa for NC clay, higher for
        over-consolidated crusts.
    su_gradient_kPa_per_m : float
        ``k = ds_u/dz``. Typical range 1-3 kPa/m.
    gamma_eff_kN_per_m3 : float, default 6.0
        Effective unit weight of the clay (saturated minus seawater).
        6 kN/m^3 is typical for Gulf-of-Mexico soft clay per
        API RP 2GEO Table 8.5.
    sensitivity : float, default 3.0
        ``S_t = s_u / s_u_remoulded``. Drives self-weight penetration
        resistance. Typical 2-5.
    plasticity_index : float, default 30.0
        ``PI`` [%]. Drives cyclic strength per Andersen 2015 contour
        diagrams.

    References
    ----------
    Randolph & Gourvenec 2011, Ch. 3.
    API RP 2GEO (2011) Table 8.5.
    """
    su_mudline_kPa: float
    su_gradient_kPa_per_m: float
    gamma_eff_kN_per_m3: float = 6.0
    sensitivity: float = 3.0
    plasticity_index: float = 30.0

    def __post_init__(self) -> None:
        if self.su_mudline_kPa < 0:
            raise ValueError(
                f"su_mudline_kPa must be >= 0, got {self.su_mudline_kPa}"
            )
        if self.su_gradient_kPa_per_m < 0:
            raise ValueError(
                f"su_gradient_kPa_per_m must be >= 0, got {self.su_gradient_kPa_per_m}"
            )
        if self.sensitivity <= 0:
            raise ValueError(
                f"sensitivity must be > 0, got {self.sensitivity}"
            )
        if self.gamma_eff_kN_per_m3 <= 0:
            raise ValueError(
                f"gamma_eff_kN_per_m3 must be > 0, got {self.gamma_eff_kN_per_m3}"
            )

    def su_at_depth(self, z_m: float | np.ndarray) -> float | np.ndarray:
        """Intact undrained shear strength at depth z below mudline."""
        return self.su_mudline_kPa + self.su_gradient_kPa_per_m * np.asarray(z_m)

    def su_remoulded_at_depth(
        self, z_m: float | np.ndarray
    ) -> float | np.ndarray:
        """Remoulded undrained shear strength, ``s_u / S_t``."""
        return self.su_at_depth(z_m) / self.sensitivity

    def su_average_to_depth(self, z_m: float) -> float:
        """Depth-averaged intact s_u from mudline to z.

        For a linear profile this is ``s_u_mudline + k * z / 2``.
        """
        if z_m <= 0:
            return self.su_mudline_kPa
        return self.su_mudline_kPa + 0.5 * self.su_gradient_kPa_per_m * z_m


# ---------------------------------------------------------------------------
# Mooring load at padeye
# ---------------------------------------------------------------------------

@dataclass
class MooringLoad:
    """Mooring-line load vector at the padeye.

    The angle is measured from the horizontal; ``angle_at_padeye_deg``
    accounts for inverse-catenary rotation from the fairlead-side angle.

    Parameters
    ----------
    tension_kN : float
        Line tension magnitude ``T``.
    angle_at_padeye_deg : float
        Angle of the tension vector from horizontal at the padeye,
        after the inverse-catenary solution. Range 0 (pure horizontal
        pull) to 90 (pure uplift).
    """
    tension_kN: float
    angle_at_padeye_deg: float

    def __post_init__(self) -> None:
        if self.tension_kN < 0:
            raise ValueError(f"tension_kN must be >= 0, got {self.tension_kN}")
        if not (-90.0 <= self.angle_at_padeye_deg <= 90.0):
            raise ValueError(
                f"angle_at_padeye_deg must lie in [-90, 90], "
                f"got {self.angle_at_padeye_deg}"
            )

    @property
    def horizontal_kN(self) -> float:
        """Horizontal component, ``T * cos(theta)``."""
        return self.tension_kN * np.cos(np.radians(self.angle_at_padeye_deg))

    @property
    def vertical_kN(self) -> float:
        """Vertical (uplift) component, ``T * sin(theta)``. Positive = up."""
        return self.tension_kN * np.sin(np.radians(self.angle_at_padeye_deg))
