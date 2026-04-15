"""
Suction-anchor ultimate capacity calculators.

Five methods with a common return type :class:`AnchorCapacityResult`
and a unified dispatcher :func:`anchor_capacity`:

    'dnv_rp_e303'     DNV-RP-E303 (2021) plastic limit analysis  [DEFAULT]
    'murff_hamilton'  Murff & Hamilton (1993) upper bound
    'api_rp_2sk'      API RP 2SK simplified
    'aubeny_2003'     Aubeny, Han & Murff (2003) depth-dependent N_p
    'fe_calibrated'   Op^3 OptumGX finite-element envelope
                      (requires FE CSV produced by
                      `op3/anchors/optumgx_anchor_run.py`)

The first four methods are pure-Python and need no external solver;
the fifth reads a real OptumGX result CSV and never fabricates FE
data (raises FileNotFoundError with the expected path if absent).

All methods use:
  * numerical depth-wise integration of shaft friction (N = 100 segments)
  * explicit adhesion factor alpha (separate outer/inner)
  * V-H interaction per the named standard

References
----------
DNV (2021). DNV-RP-E303.
API (2005, reaff. 2015). API RP 2SK, 3rd ed.
Murff, J. D., & Hamilton, J. M. (1993). J. Geotech. Eng., 119(1), 91-107.
Aubeny, C. P., Han, S.-W., & Murff, J. D. (2003). IJNAMG, 27(14), 1235-1254.
Randolph, M. F., & House, A. R. (2002). OTC 14236.
Supachawarote, C., Randolph, M. F., & Gourvenec, S. (2005). IACMAG Turin.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

from op3.anchors.anchor import (
    SuctionAnchor,
    UndrainedClayProfile,
    MooringLoad,
)
from op3.standards.dnv_rp_e303 import (
    DNV_ALPHA_OUTER,
    DNV_ALPHA_INNER,
    DNV_NC_REVERSE,
    DNV_NP_SHALLOW,
    DNV_NP_DEEP,
    DNV_Z_CRIT_OVER_D,
    DNV_VH_A,
    DNV_VH_B,
    np_factor_dnv,
)
from op3.standards.api_rp_2sk import (
    API_ALPHA_DEFAULT,
    API_NC_REVERSE,
    API_VH_A,
    API_VH_B,
    np_factor_api,
)


# ---------------------------------------------------------------------------
# Result container
# ---------------------------------------------------------------------------

@dataclass
class AnchorCapacityResult:
    """Unified return type for every capacity method.

    Attributes
    ----------
    method : str
        Name of the capacity method that produced this result.
    H_ult_kN : float
        Ultimate horizontal capacity at the current padeye depth.
    V_ult_kN : float
        Ultimate vertical (uplift) capacity assuming a plugged
        failure (outer + inner friction + reverse end-bearing).
    T_ult_kN : float
        Ultimate inclined tension at the applied ``load_angle_deg``
        obtained by scaling a unit load vector until it meets the
        V-H envelope of the parent method.
    load_angle_deg : float
        Load angle used for T_ult_kN.
    interaction_exponents : tuple[float, float]
        (a, b) in ``(H/H_ult)^a + (V/V_ult)^b = 1``.
    interaction_envelope : pd.DataFrame
        Columns ``H_kN, V_kN`` describing the V-H envelope at 36
        evenly-spaced load angles 0..90 deg.
    depth_profile : pd.DataFrame
        Columns ``depth_m, su_kPa, Np, dH_per_m_kN_per_m``. Used for
        visualisation and Op3 Mode D dissipation comparison.
    alpha_outer : float
        Outer skin-friction adhesion factor used.
    alpha_inner : float
        Inner skin-friction adhesion factor used.
    metadata : dict
        Free-form extra fields (e.g. FE file path, N_p table tag).
    """
    method: str
    H_ult_kN: float
    V_ult_kN: float
    T_ult_kN: float
    load_angle_deg: float
    interaction_exponents: tuple
    interaction_envelope: pd.DataFrame
    depth_profile: pd.DataFrame
    alpha_outer: float
    alpha_inner: float
    metadata: dict = field(default_factory=dict)

    def factor_of_safety(self, applied_kN: float) -> float:
        """Ratio T_ult / T_applied at the method's load angle."""
        if applied_kN <= 0:
            raise ValueError(f"applied_kN must be > 0, got {applied_kN}")
        return self.T_ult_kN / applied_kN


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _depth_grid(anchor: SuctionAnchor, n: int = 100) -> np.ndarray:
    """Midpoint depth array from 0 to L with n segments."""
    edges = np.linspace(0.0, anchor.skirt_length_m, n + 1)
    return 0.5 * (edges[:-1] + edges[1:])


def _solve_inclined_capacity(
    H_ult: float, V_ult: float,
    load_angle_deg: float,
    a: float, b: float,
) -> float:
    """Intersect the ray at load_angle with the envelope (H/Hu)^a + (V/Vu)^b = 1.

    Returns the inclined capacity T_ult such that
    H = T_ult cos(theta), V = T_ult sin(theta) lies exactly on the
    envelope.
    """
    if H_ult <= 0 or V_ult <= 0:
        raise ValueError(
            f"H_ult ({H_ult}) and V_ult ({V_ult}) must be > 0 to define envelope"
        )
    c = np.cos(np.radians(load_angle_deg))
    s = np.sin(np.radians(load_angle_deg))
    # Find T > 0 such that (T c / Hu)^a + (T s / Vu)^b = 1.
    # No closed-form when a != b; use scalar bisection.
    def resid(T):
        return (abs(T * c) / H_ult) ** a + (abs(T * s) / V_ult) ** b - 1.0
    lo, hi = 0.0, max(H_ult, V_ult) * 1.5
    while resid(hi) < 0:
        hi *= 2
        if hi > 1e12:
            raise RuntimeError("inclined capacity bracketing failed")
    for _ in range(100):
        mid = 0.5 * (lo + hi)
        if resid(mid) > 0:
            hi = mid
        else:
            lo = mid
        if hi - lo < 1e-6 * (H_ult + V_ult):
            break
    return 0.5 * (lo + hi)


def _envelope(H_ult: float, V_ult: float, a: float, b: float,
              n: int = 37) -> pd.DataFrame:
    angles = np.linspace(0.0, 90.0, n)
    H_arr, V_arr = [], []
    for ang in angles:
        T = _solve_inclined_capacity(H_ult, V_ult, ang, a, b)
        H_arr.append(T * np.cos(np.radians(ang)))
        V_arr.append(T * np.sin(np.radians(ang)))
    return pd.DataFrame({"angle_deg": angles, "H_kN": H_arr, "V_kN": V_arr})


def _vertical_plugged_capacity(
    anchor: SuctionAnchor,
    soil: UndrainedClayProfile,
    alpha_outer: float,
    alpha_inner: float,
    nc_reverse: float,
    include_submerged_weight: bool = True,
) -> float:
    """Plugged-failure uplift capacity:

        V_ult = W_sub + alpha_o * su_avg * A_outer + alpha_i * su_avg * A_inner
                + N_c * su(tip) * A_lid
    """
    L = anchor.skirt_length_m
    su_avg = soil.su_average_to_depth(L)
    su_tip = soil.su_at_depth(L)
    V = (
        alpha_outer * su_avg * anchor.outer_skirt_area_m2
        + alpha_inner * su_avg * anchor.inner_skirt_area_m2
        + nc_reverse * su_tip * anchor.lid_area_m2
    )
    if include_submerged_weight:
        V += anchor.submerged_weight_kN
    return float(V)


# ---------------------------------------------------------------------------
# Method 1: DNV-RP-E303
# ---------------------------------------------------------------------------

def capacity_dnv_rp_e303(
    anchor: SuctionAnchor,
    soil: UndrainedClayProfile,
    load: Optional[MooringLoad] = None,
    *,
    alpha_outer: float = DNV_ALPHA_OUTER,
    alpha_inner: float = DNV_ALPHA_INNER,
    np_shallow: float = DNV_NP_SHALLOW,
    np_deep: float = DNV_NP_DEEP,
    z_crit_over_D: float = DNV_Z_CRIT_OVER_D,
    vh_a: float = DNV_VH_A,
    vh_b: float = DNV_VH_B,
    nc_reverse: float = DNV_NC_REVERSE,
    n_segments: int = 100,
    load_angle_deg: float = 0.0,
) -> AnchorCapacityResult:
    """Ultimate capacity per DNV-RP-E303 (2021).

    The horizontal capacity is obtained by numerical integration of
    the depth-dependent lateral bearing ``N_p(z/D) * s_u(z) * D``
    along the skirt length. The vertical capacity is the plugged
    reverse-end-bearing formula. V-H interaction uses the quadratic
    envelope from RP-E303 Eq. 4.12.

    Parameters
    ----------
    anchor, soil : data model
    load : MooringLoad, optional
        If given, ``load_angle_deg`` is taken from it and
        ``T_ult_kN`` is evaluated at that angle.
    alpha_outer, alpha_inner : float
        Adhesion factors. Defaults are DNV design values (0.65).
    np_shallow, np_deep, z_crit_over_D : float
        N_p profile coefficients.
    vh_a, vh_b : float
        V-H interaction exponents.
    nc_reverse : float
        Reverse end-bearing factor for uplift.
    n_segments : int
        Number of depth segments for numerical integration.
    load_angle_deg : float
        Load inclination at padeye if ``load`` is not given.
    """
    if load is not None:
        load_angle_deg = load.angle_at_padeye_deg

    # --- depth-wise lateral resistance ----------------------------
    z = _depth_grid(anchor, n_segments)
    dz = anchor.skirt_length_m / n_segments
    D = anchor.diameter_m
    su = soil.su_at_depth(z)
    Np = np.array([np_factor_dnv(zi / D, np_shallow, np_deep, z_crit_over_D)
                   for zi in z])
    p_ult_per_m = Np * su * D                                  # kN/m
    H_ult = float(np.sum(p_ult_per_m * dz))                    # kN

    # --- vertical plugged capacity --------------------------------
    V_ult = _vertical_plugged_capacity(
        anchor, soil,
        alpha_outer=alpha_outer, alpha_inner=alpha_inner,
        nc_reverse=nc_reverse,
    )

    # --- inclined capacity + envelope -----------------------------
    T_ult = _solve_inclined_capacity(H_ult, V_ult, load_angle_deg,
                                     vh_a, vh_b)
    env = _envelope(H_ult, V_ult, vh_a, vh_b)

    prof = pd.DataFrame({
        "depth_m": z,
        "su_kPa": su,
        "Np": Np,
        "dH_per_m_kN_per_m": p_ult_per_m,
    })

    return AnchorCapacityResult(
        method="dnv_rp_e303",
        H_ult_kN=H_ult,
        V_ult_kN=V_ult,
        T_ult_kN=T_ult,
        load_angle_deg=load_angle_deg,
        interaction_exponents=(vh_a, vh_b),
        interaction_envelope=env,
        depth_profile=prof,
        alpha_outer=alpha_outer,
        alpha_inner=alpha_inner,
        metadata={"standard": "DNV-RP-E303 (2021)",
                  "np_table": "alpha=0.5 default"},
    )


# ---------------------------------------------------------------------------
# Method 2: Murff & Hamilton (1993) upper bound
# ---------------------------------------------------------------------------

def capacity_murff_hamilton(
    anchor: SuctionAnchor,
    soil: UndrainedClayProfile,
    load: Optional[MooringLoad] = None,
    *,
    alpha_outer: float = 0.5,
    alpha_inner: float = 0.5,
    nc_reverse: float = DNV_NC_REVERSE,
    n_segments: int = 100,
    load_angle_deg: float = 0.0,
) -> AnchorCapacityResult:
    """Murff & Hamilton (1993) upper-bound plasticity solution.

    The original Murff-Hamilton formulation is for laterally loaded
    piles and introduced the depth-dependent N_p with a shallow
    wedge mechanism transitioning to a deep flow-around mechanism:

        N_p(z) = N1 - N2 * exp( -xi * z/D )

    with ``N1 ~ 11.94`` (full flow, rough), ``N2 ~ 8`` and
    ``xi ~ 0.25-0.35``. Op^3 uses the coefficients quoted in
    Randolph & House (2002) Eq. 7 as representative of suction-
    caisson geometry.

    V_ult uses the same plugged formula as DNV; V-H envelope is
    circular (a = b = 2) per Supachawarote 2005.
    """
    if load is not None:
        load_angle_deg = load.angle_at_padeye_deg

    N1, N2, xi = 11.94, 8.0, 0.30   # Randolph & House 2002 Eq. 7, alpha-rough

    D = anchor.diameter_m
    z = _depth_grid(anchor, n_segments)
    dz = anchor.skirt_length_m / n_segments
    Np = N1 - N2 * np.exp(-xi * z / D)
    su = soil.su_at_depth(z)
    p_ult_per_m = Np * su * D
    H_ult = float(np.sum(p_ult_per_m * dz))

    V_ult = _vertical_plugged_capacity(
        anchor, soil,
        alpha_outer=alpha_outer, alpha_inner=alpha_inner,
        nc_reverse=nc_reverse,
    )

    a, b = 2.0, 2.0
    T_ult = _solve_inclined_capacity(H_ult, V_ult, load_angle_deg, a, b)
    env = _envelope(H_ult, V_ult, a, b)

    prof = pd.DataFrame({
        "depth_m": z, "su_kPa": su, "Np": Np,
        "dH_per_m_kN_per_m": p_ult_per_m,
    })
    return AnchorCapacityResult(
        method="murff_hamilton",
        H_ult_kN=H_ult, V_ult_kN=V_ult, T_ult_kN=T_ult,
        load_angle_deg=load_angle_deg,
        interaction_exponents=(a, b),
        interaction_envelope=env,
        depth_profile=prof,
        alpha_outer=alpha_outer, alpha_inner=alpha_inner,
        metadata={"standard": "Murff & Hamilton (1993)",
                  "np_table": f"N1={N1}, N2={N2}, xi={xi}"},
    )


# ---------------------------------------------------------------------------
# Method 3: API RP 2SK
# ---------------------------------------------------------------------------

def capacity_api_rp_2sk(
    anchor: SuctionAnchor,
    soil: UndrainedClayProfile,
    load: Optional[MooringLoad] = None,
    *,
    alpha_outer: float = API_ALPHA_DEFAULT,
    alpha_inner: float = API_ALPHA_DEFAULT,
    nc_reverse: float = API_NC_REVERSE,
    n_segments: int = 100,
    load_angle_deg: float = 0.0,
) -> AnchorCapacityResult:
    """Ultimate capacity per API RP 2SK (2005, reaff. 2015).

    Uses the classical ``N_p = min(3 + z/D, 9)`` cut-off and linear
    V-H interaction ``H/H_ult + V/V_ult = 1``.
    """
    if load is not None:
        load_angle_deg = load.angle_at_padeye_deg

    D = anchor.diameter_m
    z = _depth_grid(anchor, n_segments)
    dz = anchor.skirt_length_m / n_segments
    Np = np.array([np_factor_api(zi / D) for zi in z])
    su = soil.su_at_depth(z)
    p_ult_per_m = Np * su * D
    H_ult = float(np.sum(p_ult_per_m * dz))

    V_ult = _vertical_plugged_capacity(
        anchor, soil,
        alpha_outer=alpha_outer, alpha_inner=alpha_inner,
        nc_reverse=nc_reverse,
    )

    a, b = API_VH_A, API_VH_B
    T_ult = _solve_inclined_capacity(H_ult, V_ult, load_angle_deg, a, b)
    env = _envelope(H_ult, V_ult, a, b)

    prof = pd.DataFrame({
        "depth_m": z, "su_kPa": su, "Np": Np,
        "dH_per_m_kN_per_m": p_ult_per_m,
    })
    return AnchorCapacityResult(
        method="api_rp_2sk",
        H_ult_kN=H_ult, V_ult_kN=V_ult, T_ult_kN=T_ult,
        load_angle_deg=load_angle_deg,
        interaction_exponents=(a, b),
        interaction_envelope=env,
        depth_profile=prof,
        alpha_outer=alpha_outer, alpha_inner=alpha_inner,
        metadata={"standard": "API RP 2SK (2005, reaff. 2015)",
                  "np_table": "min(3+z/D, 9) cut-off"},
    )


# ---------------------------------------------------------------------------
# Method 4: Aubeny et al. (2003)
# ---------------------------------------------------------------------------

# Aubeny 2003 Table 2 -- piecewise N_p:
#     N_p(z/D) = N_p1 + N_p2 * z/D    for z/D <= z_cr/D
#     N_p(z/D) = N_p_deep            otherwise
# Coefficients for smooth (alpha=0) and rough (alpha=1) interfaces:
AUBENY_2003 = {
    "smooth": dict(N_p1=2.82, N_p2=1.67, z_cr_over_D=4.30, N_p_deep=9.14),
    "rough":  dict(N_p1=5.63, N_p2=1.38, z_cr_over_D=3.08, N_p_deep=11.94),
}


def capacity_aubeny_2003(
    anchor: SuctionAnchor,
    soil: UndrainedClayProfile,
    load: Optional[MooringLoad] = None,
    *,
    interface: str = "rough",
    alpha_outer: Optional[float] = None,
    alpha_inner: Optional[float] = None,
    nc_reverse: float = DNV_NC_REVERSE,
    n_segments: int = 100,
    load_angle_deg: float = 0.0,
) -> AnchorCapacityResult:
    """Ultimate capacity per Aubeny, Han & Murff (2003).

    Uses the published piecewise depth profile of N_p from Table 2
    of the paper, selected by ``interface`` ('smooth' or 'rough').
    V-H envelope: quadratic (a = b = 2) as recommended in the paper.

    For coefficients corresponding to intermediate roughness
    (0 < alpha < 1), pass custom ``alpha_outer`` / ``alpha_inner`` and
    use ``interface='rough'`` -- the N_p table itself is not
    interpolated because Aubeny's coefficients are not smooth
    functions of alpha.
    """
    if interface not in AUBENY_2003:
        raise ValueError(
            f"interface must be one of {list(AUBENY_2003)}, got {interface!r}"
        )
    tab = AUBENY_2003[interface]
    if alpha_outer is None:
        alpha_outer = 1.0 if interface == "rough" else 0.0
    if alpha_inner is None:
        alpha_inner = alpha_outer

    if load is not None:
        load_angle_deg = load.angle_at_padeye_deg

    D = anchor.diameter_m
    z = _depth_grid(anchor, n_segments)
    dz = anchor.skirt_length_m / n_segments
    z_over_D = z / D
    Np = np.where(
        z_over_D <= tab["z_cr_over_D"],
        tab["N_p1"] + tab["N_p2"] * z_over_D,
        tab["N_p_deep"],
    )
    su = soil.su_at_depth(z)
    p_ult_per_m = Np * su * D
    H_ult = float(np.sum(p_ult_per_m * dz))

    V_ult = _vertical_plugged_capacity(
        anchor, soil,
        alpha_outer=alpha_outer, alpha_inner=alpha_inner,
        nc_reverse=nc_reverse,
    )

    a, b = 2.0, 2.0
    T_ult = _solve_inclined_capacity(H_ult, V_ult, load_angle_deg, a, b)
    env = _envelope(H_ult, V_ult, a, b)

    prof = pd.DataFrame({
        "depth_m": z, "su_kPa": su, "Np": Np,
        "dH_per_m_kN_per_m": p_ult_per_m,
    })
    return AnchorCapacityResult(
        method="aubeny_2003",
        H_ult_kN=H_ult, V_ult_kN=V_ult, T_ult_kN=T_ult,
        load_angle_deg=load_angle_deg,
        interaction_exponents=(a, b),
        interaction_envelope=env,
        depth_profile=prof,
        alpha_outer=alpha_outer, alpha_inner=alpha_inner,
        metadata={"standard": "Aubeny, Han & Murff (2003)",
                  "interface": interface,
                  "np_table": str(tab)},
    )


# ---------------------------------------------------------------------------
# Method 5: FE-calibrated from OptumGX
# ---------------------------------------------------------------------------

def capacity_fe_calibrated(
    anchor: SuctionAnchor,
    soil: UndrainedClayProfile,
    fe_csv: str | Path,
    load: Optional[MooringLoad] = None,
    *,
    load_angle_deg: float = 0.0,
) -> AnchorCapacityResult:
    """Ultimate capacity from a real OptumGX FE envelope CSV.

    The CSV must be produced by the Op^3 anchor OptumGX driver
    (``op3/anchors/optumgx_anchor_run.py``, loaded into the OptumGX
    desktop scripting console). Expected columns:

        angle_deg, H_ult_kN, V_ult_kN

    where each row is a separate OptumGX probe at a fixed load
    angle. From that tabulated envelope the inclined capacity at
    any ``load_angle_deg`` is interpolated, and H_ult / V_ult are
    extracted at the two end points.

    Parameters
    ----------
    fe_csv : str | Path
        Absolute path to the OptumGX envelope CSV.
    anchor, soil, load : data model (used for metadata only)

    Raises
    ------
    FileNotFoundError
        If ``fe_csv`` does not exist. The error message includes the
        exact path and a pointer to the driver script.

    Notes
    -----
    No synthetic data is permitted by this function. If the FE
    results are not yet available, use one of the analytical
    methods instead.
    """
    fe_csv = Path(fe_csv)
    if not fe_csv.exists():
        raise FileNotFoundError(
            f"FE envelope CSV not found: {fe_csv}\n"
            "To produce it, open OptumGX, load "
            "'op3/anchors/optumgx_anchor_run.py' into the scripting "
            "console, and run a VHM sweep for this anchor geometry. "
            "See docs/ANCHOR_OPTUMGX_GUIDE.md."
        )
    df = pd.read_csv(fe_csv)
    required = {"angle_deg", "H_ult_kN", "V_ult_kN"}
    if not required.issubset(df.columns):
        raise ValueError(
            f"FE CSV {fe_csv} is missing columns: "
            f"{required - set(df.columns)}"
        )
    df = df.sort_values("angle_deg").reset_index(drop=True)

    if load is not None:
        load_angle_deg = load.angle_at_padeye_deg

    # H_ult = FE H at angle=0; V_ult = FE V at angle=90
    H_ult = float(df.loc[df["angle_deg"].idxmin(), "H_ult_kN"])
    V_ult = float(df.loc[df["angle_deg"].idxmax(), "V_ult_kN"])

    # Inclined capacity: interpolate the magnitude T = sqrt(H^2 + V^2)
    # at the requested angle.
    df["T_kN"] = np.hypot(df["H_ult_kN"], df["V_ult_kN"])
    T_ult = float(np.interp(load_angle_deg,
                            df["angle_deg"], df["T_kN"]))

    # Interaction exponents: fit (H/Hu)^a + (V/Vu)^b = 1 with a=b
    # by least squares on ln(H/Hu) + ln(V/Vu) residual.
    with np.errstate(divide="ignore", invalid="ignore"):
        H_n = df["H_ult_kN"] / H_ult
        V_n = df["V_ult_kN"] / V_ult
        mask = (H_n > 1e-3) & (V_n > 1e-3)
        if mask.sum() >= 3:
            ln_Hn = np.log(H_n[mask])
            ln_Vn = np.log(V_n[mask])
            # ln((Hn)^a + (Vn)^a) = 0 => minimise residual for fixed a
            best_a, best_res = 2.0, np.inf
            for a in np.linspace(1.0, 5.0, 41):
                res = np.mean(
                    (np.log(np.exp(a * ln_Hn) + np.exp(a * ln_Vn))) ** 2
                )
                if res < best_res:
                    best_a, best_res = a, res
            a = best_a
        else:
            a = 2.0
    b = a

    # Empty depth profile -- FE method does not return one per design.
    prof = pd.DataFrame(columns=["depth_m", "su_kPa", "Np",
                                 "dH_per_m_kN_per_m"])

    return AnchorCapacityResult(
        method="fe_calibrated",
        H_ult_kN=H_ult, V_ult_kN=V_ult, T_ult_kN=T_ult,
        load_angle_deg=load_angle_deg,
        interaction_exponents=(a, b),
        interaction_envelope=df[["angle_deg", "H_ult_kN",
                                 "V_ult_kN"]].rename(
            columns={"H_ult_kN": "H_kN", "V_ult_kN": "V_kN"}
        ),
        depth_profile=prof,
        alpha_outer=float("nan"), alpha_inner=float("nan"),
        metadata={"standard": "OptumGX FE",
                  "fe_csv": str(fe_csv),
                  "n_probes": int(len(df))},
    )


# ---------------------------------------------------------------------------
# Dispatcher
# ---------------------------------------------------------------------------

_METHODS = {
    "dnv_rp_e303": capacity_dnv_rp_e303,
    "murff_hamilton": capacity_murff_hamilton,
    "api_rp_2sk": capacity_api_rp_2sk,
    "aubeny_2003": capacity_aubeny_2003,
    "fe_calibrated": capacity_fe_calibrated,
}


def anchor_capacity(
    anchor: SuctionAnchor,
    soil: UndrainedClayProfile,
    method: str = "dnv_rp_e303",
    load: Optional[MooringLoad] = None,
    **kwargs,
) -> AnchorCapacityResult:
    """Dispatch to the requested capacity method.

    Parameters
    ----------
    method : str
        One of 'dnv_rp_e303', 'murff_hamilton', 'api_rp_2sk',
        'aubeny_2003', 'fe_calibrated'. Case-insensitive.
    load : MooringLoad, optional
        If given, ``load_angle_deg`` in the result is taken from the
        load's padeye angle.
    **kwargs : dict
        Forwarded to the chosen method (e.g. ``alpha_outer``,
        ``fe_csv`` for fe_calibrated, ``interface`` for Aubeny).

    Returns
    -------
    AnchorCapacityResult
    """
    key = method.lower()
    if key not in _METHODS:
        raise ValueError(
            f"Unknown capacity method '{method}'. "
            f"Expected one of {list(_METHODS)}."
        )
    return _METHODS[key](anchor, soil, load=load, **kwargs)
