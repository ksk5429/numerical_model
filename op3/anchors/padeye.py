"""
Optimal padeye depth determination for suction anchors.

Three approaches:

    optimal_padeye_analytical(...)     -- Murff & Hamilton 1993 /
                                          Supachawarote 2005 tabulated
                                          depth for given L/D and su
                                          profile type
    padeye_sensitivity_study(...)      -- sweep the padeye depth and
                                          evaluate one of the analytical
                                          capacity methods at each
                                          position; returns the full
                                          capacity(z_p) curve
    optimal_padeye_from_dissipation()  -- NOVEL contribution to Op^3:
                                          centroid of the plastic-
                                          dissipation field at collapse
                                          (loaded from OptumGX Mode D
                                          output)

The dissipation-centroid method extends Op^3 Mode D (Kim 2026
dissertation, Appendix A) to anchor design. The physical argument is
that the depth of maximum plastic dissipation is where soil resistance
is most effectively mobilised, so applying the mooring load at that
depth minimises rotation and maximises translational capacity.

References
----------
Murff, J. D., & Hamilton, J. M. (1993). J. Geotech. Eng., 119(1), 91-107.
Supachawarote, C., Randolph, M. F., & Gourvenec, S. (2005). "The
    effect of crack formation on the inclined pull-out capacity of
    suction caissons". IACMAG Turin, Vol. 3, 577-584.
Randolph, M. F., & House, A. R. (2002). OTC 14236.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from op3.anchors.anchor import SuctionAnchor, UndrainedClayProfile
from op3.anchors.capacity import anchor_capacity


# ---------------------------------------------------------------------------
# Supachawarote et al. (2005) tabulated optimal z_p / L
# ---------------------------------------------------------------------------
#
# Supachawarote, Randolph, Gourvenec (2005) IACMAG Vol. 3, Fig. 6:
# Optimal padeye depth (for maximum horizontal capacity at a fixed
# load angle) as a function of aspect ratio for two reference
# undrained strength profiles:
#
#   profile 'uniform'  : s_u = constant
#   profile 'linear'   : s_u = k * z  (su_mudline = 0)
#
# Values reported for alpha = 0.5 (average design roughness) at a
# pull-out angle of 30 deg. For other angles Supachawarote shows
# the optimum changes by less than 0.05 in z_p/L, so we treat this
# as angle-independent for design purposes.
SUPACHAWAROTE_2005 = {
    "uniform": {
        1.0: 0.64, 2.0: 0.68, 3.0: 0.70, 4.0: 0.71, 5.0: 0.72,
    },
    "linear": {
        1.0: 0.68, 2.0: 0.72, 3.0: 0.73, 4.0: 0.74, 5.0: 0.75,
    },
}


# ---------------------------------------------------------------------------
# Analytical
# ---------------------------------------------------------------------------

def optimal_padeye_analytical(
    anchor: SuctionAnchor,
    soil: UndrainedClayProfile,
    method: str = "supachawarote_2005",
) -> float:
    """Analytical / tabulated optimal padeye depth.

    Parameters
    ----------
    method : {'supachawarote_2005', 'murff_hamilton'}
        * supachawarote_2005: interpolate in Table 2 by L/D and su
          profile type ('uniform' if k = 0, else 'linear').
        * murff_hamilton: constant z_p / L = 0.67 (Murff & Hamilton 1993
          upper-bound recommendation).

    Returns
    -------
    float
        Recommended ``padeye_depth_m``.
    """
    key = method.lower()
    LD = anchor.aspect_ratio
    if key == "murff_hamilton":
        return 0.67 * anchor.skirt_length_m
    if key == "supachawarote_2005":
        profile_type = "uniform" if soil.su_gradient_kPa_per_m == 0 \
            else "linear"
        table = SUPACHAWAROTE_2005[profile_type]
        xs = np.array(sorted(table.keys()))
        ys = np.array([table[x] for x in xs])
        # Clamp outside the tabulated range
        if LD <= xs.min():
            frac = float(ys[0])
        elif LD >= xs.max():
            frac = float(ys[-1])
        else:
            frac = float(np.interp(LD, xs, ys))
        return frac * anchor.skirt_length_m
    raise ValueError(
        f"Unknown padeye method '{method}'. "
        f"Expected 'supachawarote_2005' or 'murff_hamilton'."
    )


# ---------------------------------------------------------------------------
# Sensitivity study
# ---------------------------------------------------------------------------

def padeye_sensitivity_study(
    anchor: SuctionAnchor,
    soil: UndrainedClayProfile,
    z_p_range: np.ndarray,
    *,
    load_angle_deg: float = 0.0,
    capacity_method: str = "dnv_rp_e303",
    **capacity_kwargs,
) -> pd.DataFrame:
    """Evaluate inclined anchor capacity at each padeye depth in the range.

    This is a brute-force analogue of the optimisation: it reports
    the full capacity(z_p) curve so the caller can see how peaky or
    flat the optimum is.

    Parameters
    ----------
    z_p_range : np.ndarray
        Candidate padeye depths [m]. Must lie in (0, L).
    load_angle_deg : float
        Inclined load angle used for T_ult.
    capacity_method : str
        One of the analytical methods accepted by
        :func:`op3.anchors.anchor_capacity`.

    Returns
    -------
    pd.DataFrame
        Columns ``z_p_m, z_p_over_L, H_ult_kN, V_ult_kN, T_ult_kN``.

    Notes
    -----
    The analytical methods in Op^3 do not actually depend on the
    padeye depth for H_ult (since H_ult is the integrated lateral
    resistance). Padeye depth affects the moment equilibrium, which
    is captured in the DNV and Aubeny formulations implicitly via
    the inclined load resultant. For a pure horizontal pull
    (load_angle_deg=0) the returned H_ult is nearly constant with
    z_p; the sensitivity is stronger at higher load angles.
    The dissipation-centroid method (see :func:`optimal_padeye_from_dissipation`)
    gives a richer z_p-dependent answer.
    """
    L = anchor.skirt_length_m
    rows = []
    for z_p in z_p_range:
        if not (0.0 < z_p < L):
            continue
        a2 = SuctionAnchor(
            diameter_m=anchor.diameter_m,
            skirt_length_m=L,
            wall_thickness_mm=anchor.wall_thickness_mm,
            padeye_depth_m=float(z_p),
            padeye_offset_m=anchor.padeye_offset_m,
            lid_thickness_mm=anchor.lid_thickness_mm,
            submerged_weight_kN=anchor.submerged_weight_kN,
            steel_grade=anchor.steel_grade,
        )
        r = anchor_capacity(a2, soil, method=capacity_method,
                            load_angle_deg=load_angle_deg,
                            **capacity_kwargs)
        rows.append(dict(
            z_p_m=float(z_p),
            z_p_over_L=float(z_p) / L,
            H_ult_kN=r.H_ult_kN,
            V_ult_kN=r.V_ult_kN,
            T_ult_kN=r.T_ult_kN,
        ))
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# NOVEL: dissipation-centroid padeye (Op^3 Mode D extension)
# ---------------------------------------------------------------------------

DISSIPATION_CSV_COLUMNS = {"depth_m", "w_z", "D_total_kJ"}


def _load_dissipation_profile(path: str | Path) -> pd.DataFrame:
    """Read a Mode D dissipation CSV and validate it."""
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(
            f"Mode D dissipation CSV not found: {p}\n"
            "To produce it, open OptumGX, load "
            "'op3/anchors/optumgx_anchor_run.py' into the scripting "
            "console, and run the 'dissipation' probe on the target "
            "anchor geometry at the design load angle. See "
            "docs/ANCHOR_OPTUMGX_GUIDE.md."
        )
    df = pd.read_csv(p)
    missing = DISSIPATION_CSV_COLUMNS - set(df.columns)
    if missing:
        raise ValueError(
            f"Dissipation CSV {p} is missing columns: {missing}. "
            f"Required columns: {DISSIPATION_CSV_COLUMNS}."
        )
    if (df["w_z"] < 0).any():
        raise ValueError(
            f"Dissipation CSV {p} contains negative w(z) values, "
            "which are physically inadmissible."
        )
    return df.sort_values("depth_m").reset_index(drop=True)


def optimal_padeye_from_dissipation(
    anchor: SuctionAnchor,
    dissipation_csv: str | Path,
) -> float:
    """Centroid of the plastic-dissipation field at collapse.

    This is the novel Op^3 method: apply the mooring load at the
    depth ``z*`` which minimises the rotational component of the
    failure mechanism by definition, because that is where the
    plastic energy is most effectively mobilised.

        z* = integral_0^L z * psi(z) dz / integral_0^L psi(z) dz

    where ``psi(z)`` is the depth-distributed plastic dissipation
    weight from OptumGX Mode D.

    Parameters
    ----------
    anchor : SuctionAnchor
        Used only to clip the centroid to (0, L).
    dissipation_csv : str | Path
        Absolute path to an OptumGX Mode D dissipation CSV with
        columns ``depth_m, w_z, D_total_kJ``.

    Returns
    -------
    float
        Optimal padeye depth [m].

    Raises
    ------
    FileNotFoundError
        If the CSV is absent. The message names the driver script
        (``optumgx_anchor_run.py``) so a future session can regenerate
        the data on demand.

    Notes
    -----
    This is the single novel theoretical contribution of the Op^3
    anchor module; it is NOT in DNV-RP-E303 or API RP 2SK. Op^3
    ships it as a research extension. Validation against a brute-
    force FE padeye sweep is performed by the
    ``test_padeye_novel_method_matches_fe_sweep`` test, which
    requires a real OptumGX dataset.
    """
    df = _load_dissipation_profile(dissipation_csv)
    z = df["depth_m"].to_numpy()
    psi = df["w_z"].to_numpy()
    if psi.sum() <= 0:
        raise ValueError(
            "Dissipation weights sum to zero; cannot compute centroid."
        )
    z_opt = float(np.trapezoid(z * psi, z) / np.trapezoid(psi, z))
    z_opt = float(np.clip(z_opt, 1e-3, anchor.skirt_length_m - 1e-3))
    return z_opt
