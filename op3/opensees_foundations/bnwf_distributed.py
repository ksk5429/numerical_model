"""
Physically-distributed Beam-on-Nonlinear-Winkler-Foundation builder.

This is the blueprint Q1(a) primary: a vertical elasticBeamColumn
skirt under the tower base with one ``zeroLength`` soil spring per
depth station. The spring backbones can be linear (``Elastic``, for
eigenvalue analysis and Craig-Bampton extraction) or nonlinear
(``PySimple1`` / ``TzSimple1``, for pushover and cyclic analysis).

Tag allocation (avoids collisions with existing builder conventions):

    12000           skirt head node (z = 0, mudline)
    12001..12099    skirt body nodes at each depth station
    13000..13099    ghost fixed nodes for soil springs
    13999           ghost fixed node for base (skirt tip)
    14000..14098    per-depth soil ``zeroLength`` elements
    14999           base ``zeroLength`` element (skirt tip)
    12001           ``geomTransf`` tag
    12100..12899    per-depth uniaxial material tags
    13000..13005    base uniaxial material tags

Static condensation at the tower base node is obtained via
``run_static_condensation_perturbation``: unit displacements applied at
each of the six DOFs of ``base_node`` yield the full 6x6 tangent
stiffness, including off-diagonal lateral-rocking coupling that the
legacy Winkler integral cannot capture.
"""
from __future__ import annotations

import math
import warnings
from typing import TYPE_CHECKING, Tuple

import numpy as np
import pandas as pd

if TYPE_CHECKING:
    from op3.foundations import Foundation


# --- Default PROXY ratios (used only when Foundation fields are None).
# Replace with OptumG2-calibrated values when the base-probe and t-z
# axial-probe pipelines are wired in (blueprint Week 5).
_DEFAULT_BASE_H_STIFFNESS_FRACTION: float = 0.1
_DEFAULT_BASE_V_TO_H_RATIO: float = 3.0
_DEFAULT_SHAFT_T_TO_P_RATIO: float = 0.5
_DEFAULT_SHAFT_KZ_TO_KX_RATIO: float = 0.5
_DEFAULT_MISSING_PULT_FACTOR: float = 10.0
_BASE_KROT_SHAPE_FACTOR: float = 0.1   # k_rot_base = factor * integrated_kx * mean_dz^2
_BASE_KTOR_FRACTION: float = 0.5       # k_tor_base = fraction * k_rot_base


# --- Tag constants (kept in one place so tests can reference them) ---
SKIRT_HEAD_TAG: int = 12000
SKIRT_NODE_OFFSET: int = 12001
GHOST_NODE_OFFSET: int = 13000
BASE_GHOST_TAG: int = 13999
SKIRT_ELEM_OFFSET: int = 12001
SOIL_ELEM_OFFSET: int = 14000
BASE_ELEM_TAG: int = 14999
GEOM_TRANSF_TAG: int = 12001
MAT_TAG_BASE: int = 12100
MAT_BASE_TAGS: Tuple[int, ...] = (13000, 13001, 13002, 13003, 13004, 13005)

E_STEEL: float = 2.1e11
G_STEEL: float = 8.1e10
RHO_STEEL: float = 7850.0


def _tributary_dz(depths: np.ndarray, skirt_length_m: float) -> np.ndarray:
    """Centred tributary thickness for each depth station.

    ``depths`` must be a sorted ascending array of POSITIVE depth-below-
    mudline values. Boundaries use half-intervals to the mudline
    (``z = 0``) at the top and to ``skirt_length_m`` at the bottom so
    that ``sum(dz) == skirt_length_m``.
    """
    n = len(depths)
    if n == 0:
        return np.zeros(0)
    if n == 1:
        return np.array([skirt_length_m], dtype=float)

    dz = np.empty(n, dtype=float)
    dz[0] = 0.5 * (depths[0] + depths[1])  # top tributary: from 0 to midpoint
    for i in range(1, n - 1):
        dz[i] = 0.5 * (depths[i + 1] - depths[i - 1])
    dz[n - 1] = skirt_length_m - 0.5 * (depths[n - 1] + depths[n - 2])
    # Guard against negative tributaries if depth[-1] overshoots skirt_length_m.
    dz = np.maximum(dz, 0.0)
    return dz


def _normalised_springs(
    spring_table: pd.DataFrame,
    skirt_length_m_override: float | None,
    scour_depth: float = 0.0,
    missing_pult_factor: float = _DEFAULT_MISSING_PULT_FACTOR,
) -> dict:
    """Extract depth, k_per_m, p_ult_per_m from a spring table.

    Returns a dict with sorted arrays and a resolved ``skirt_length_m``.
    Accepts either sign convention for ``depth_m`` (negative below
    mudline OR positive depth magnitude) and applies scour relief
    internally using the positive-depth convention (``relief(z) =
    sqrt((z - S) / z)`` below the scour front, 0 above). This keeps
    the physical builder robust against the shipped CSVs whose
    ``z_m`` is negative.
    """
    if "depth_m" not in spring_table.columns:
        raise ValueError("spring_table must have a 'depth_m' column")
    if "k_ini_kN_per_m" not in spring_table.columns:
        raise ValueError("spring_table must have a 'k_ini_kN_per_m' column")

    z_raw = spring_table["depth_m"].to_numpy(dtype=float)
    k_raw = spring_table["k_ini_kN_per_m"].to_numpy(dtype=float)
    if "p_ult_kN_per_m" in spring_table.columns:
        p_raw = spring_table["p_ult_kN_per_m"].to_numpy(dtype=float)
    else:
        # Fallback: p_ult scales with k_ini. This is a PROXY and distorts
        # PySimple1 y50 — warn loudly so callers don't rely on it silently.
        warnings.warn(
            "spring_table has no 'p_ult_kN_per_m' column; using "
            f"p_ult = {missing_pult_factor:.2f} * k_ini as a fallback. "
            "This is a proxy — PySimple1 y50 is derived from p_ult, so "
            "capacity-governed results will be unreliable. Provide a "
            "p_ult column for production use.",
            stacklevel=3,
        )
        p_raw = float(missing_pult_factor) * k_raw

    depth_below = np.abs(z_raw)
    order = np.argsort(depth_below)
    depths = depth_below[order]
    k = k_raw[order] * 1.0e3  # kN/m per m -> N/m per m
    p = p_raw[order] * 1.0e3  # kN/m per m -> N per m

    # Sign-aware scour relief against the positive-depth convention.
    # The legacy `apply_scour_relief` with negative depths would zero
    # every row, so we rebuild the relief factor here.
    S = max(float(scour_depth), 0.0)
    if S > 0:
        # relief = sqrt((z - S) / z) for z > S, else 0. Matches the
        # Chapter 6 stress-relief factor used in the legacy builder.
        relief = np.where(
            depths > S,
            np.sqrt(np.clip((depths - S) / np.maximum(depths, 1e-6), 0.0, 1.0)),
            0.0,
        )
        k = k * relief
        p = p * relief

    # Drop rows where stiffness vanished (scour above z) or the row
    # sits at the mudline (depth=0) and would overlap the skirt head.
    mask = (k > 1.0) & (depths > 1e-6)
    depths = depths[mask]
    k = k[mask]
    p = p[mask]

    if depths.size == 0:
        raise ValueError(
            "spring_table has no usable springs after scour relief "
            f"(scour_depth={S} m). Check that spring_profile reaches "
            "below the scour front and k_ini_kN_per_m is positive."
        )

    L = float(skirt_length_m_override) if skirt_length_m_override else float(depths.max())
    if L <= 0:
        raise ValueError(f"skirt_length_m must be > 0, got {L}")

    return {
        "depths_m": depths,
        "k_per_m": k,
        "p_per_m": p,
        "skirt_length_m": L,
    }


def attach_distributed_bnwf_physical(
    ops,
    spring_table: pd.DataFrame,
    base_node: int,
    foundation: "Foundation",
    *,
    nonlinear: bool,
) -> dict:
    """Build a physical distributed-skirt BNWF attached to ``base_node``.

    The skirt is a single vertical steel tube (effective monopile
    equivalent) with depth-distributed soil springs. For tripod
    geometries the caller can still use this primitive three times
    (one per leg) and connect via a rigid transition piece, but that
    is outside the scope of the single-foundation dataclass.

    Parameters
    ----------
    ops : openseespy.opensees module
        Already imported by the caller. Passed in so this module does
        not force a hard dependency on OpenSeesPy at import time.
    spring_table : pd.DataFrame
        Must contain ``depth_m`` and ``k_ini_kN_per_m`` columns. An
        optional ``p_ult_kN_per_m`` column is required when
        ``nonlinear=True``.
    base_node : int
        Tower base node tag. It must already exist in the OpenSees
        domain and must NOT be fixed — this function rigid-links it to
        the skirt head, which carries the 6-DOF boundary condition.
    foundation : Foundation
        Supplies ``diameter_m``, ``skirt_length_m``, ``skirt_thickness_m``.
    nonlinear : bool
        When True uses ``PySimple1`` (lateral) + ``TzSimple1`` (shaft
        friction). When False uses ``Elastic`` with the same tangent
        stiffness, suitable for eigen + Craig-Bampton reduction.

    Returns
    -------
    dict
        Diagnostic info (number of skirt elements, integrated stiffness,
        geometry, etc.).
    """
    if not isinstance(spring_table, pd.DataFrame):
        raise TypeError("spring_table must be a pandas DataFrame")

    # Resolve PROXY ratios — warn loudly when any fall back to the
    # research defaults, so nobody mistakes the resulting K matrix for
    # a calibrated model.
    base_H_frac = (
        float(foundation.base_H_stiffness_fraction)
        if foundation.base_H_stiffness_fraction is not None
        else _DEFAULT_BASE_H_STIFFNESS_FRACTION
    )
    base_VH_ratio = (
        float(foundation.base_V_to_H_ratio)
        if foundation.base_V_to_H_ratio is not None
        else _DEFAULT_BASE_V_TO_H_RATIO
    )
    shaft_tp_ratio = (
        float(foundation.shaft_t_to_p_ratio)
        if foundation.shaft_t_to_p_ratio is not None
        else _DEFAULT_SHAFT_T_TO_P_RATIO
    )
    shaft_kz_ratio = (
        float(foundation.shaft_kz_to_kx_ratio)
        if foundation.shaft_kz_to_kx_ratio is not None
        else _DEFAULT_SHAFT_KZ_TO_KX_RATIO
    )
    missing_pult_factor = (
        float(foundation.missing_pult_fallback_factor)
        if foundation.missing_pult_fallback_factor is not None
        else _DEFAULT_MISSING_PULT_FACTOR
    )
    defaulted = []
    if foundation.base_H_stiffness_fraction is None:
        defaulted.append(f"base_H_stiffness_fraction={base_H_frac}")
    if foundation.base_V_to_H_ratio is None:
        defaulted.append(f"base_V_to_H_ratio={base_VH_ratio}")
    if foundation.shaft_t_to_p_ratio is None:
        defaulted.append(f"shaft_t_to_p_ratio={shaft_tp_ratio}")
    if foundation.shaft_kz_to_kx_ratio is None:
        defaulted.append(f"shaft_kz_to_kx_ratio={shaft_kz_ratio}")
    if defaulted:
        warnings.warn(
            "Physical BNWF is using proxy values for "
            + ", ".join(defaulted)
            + ". These are NOT calibrated — they hold the skirt-tip and "
            "shaft-friction boundary conditions to plausible but "
            "uncalibrated ratios until the OptumG2 base-probe and t-z "
            "axial-probe pipelines land (blueprint Week 5). Override via "
            "Foundation(base_H_stiffness_fraction=..., base_V_to_H_ratio="
            "..., shaft_t_to_p_ratio=..., shaft_kz_to_kx_ratio=...).",
            stacklevel=3,
        )

    springs = _normalised_springs(
        spring_table,
        foundation.skirt_length_m,
        scour_depth=float(foundation.scour_depth),
        missing_pult_factor=missing_pult_factor,
    )
    depths = springs["depths_m"]
    k_per_m = springs["k_per_m"]
    p_per_m = springs["p_per_m"]
    L_skirt = springs["skirt_length_m"]

    D = float(foundation.diameter_m)
    t_skirt = float(foundation.skirt_thickness_m)
    if D <= 2 * t_skirt:
        raise ValueError(
            f"diameter_m ({D}) must be greater than 2*skirt_thickness_m "
            f"({2*t_skirt})"
        )

    R_o = 0.5 * D
    R_i = R_o - t_skirt
    A_skirt = math.pi * (R_o ** 2 - R_i ** 2)
    I_skirt = math.pi * (R_o ** 4 - R_i ** 4) / 4.0
    J_skirt = 2.0 * I_skirt

    # ---- Geometry: decide whether a transition beam is needed ----
    # If the tower base node sits above mudline (z > 0), insert a
    # vertical elasticBeamColumn from base_node down to a new skirt-head
    # node at (0, 0, 0). When base_node is already at mudline the skirt
    # head coincides with base_node and no transition element is added.
    base_coord = ops.nodeCoord(int(base_node))
    base_z = float(base_coord[2])

    # vecxz for vertical beam: pointing along global x is fine (defines
    # the local x-z plane; local-x = axial = global-z).
    ops.geomTransf("Linear", GEOM_TRANSF_TAG, 1.0, 0.0, 0.0)

    if base_z > 1.0e-6:
        ops.node(SKIRT_HEAD_TAG, 0.0, 0.0, 0.0)
        ops.element(
            "elasticBeamColumn",
            SKIRT_ELEM_OFFSET - 1, int(base_node), SKIRT_HEAD_TAG,
            A_skirt, E_STEEL, G_STEEL, J_skirt, I_skirt, I_skirt,
            GEOM_TRANSF_TAG,
            "-mass", A_skirt * RHO_STEEL,
        )
        skirt_top_node = SKIRT_HEAD_TAG
        has_transition = True
    else:
        # base_node is already at (0, 0, 0) or below; attach skirt
        # directly to it without a transition element.
        skirt_top_node = int(base_node)
        has_transition = False

    # ---- Skirt body nodes at each depth station ----
    node_tags = [skirt_top_node]
    for i, d in enumerate(depths):
        tag = SKIRT_NODE_OFFSET + i
        ops.node(tag, 0.0, 0.0, -float(d))
        node_tags.append(tag)

    n_segments = len(depths)
    for i in range(n_segments):
        ele_tag = SKIRT_ELEM_OFFSET + i
        ops.element(
            "elasticBeamColumn",
            ele_tag, node_tags[i], node_tags[i + 1],
            A_skirt, E_STEEL, G_STEEL, J_skirt, I_skirt, I_skirt,
            GEOM_TRANSF_TAG,
            "-mass", A_skirt * RHO_STEEL,
        )

    # ---- Per-depth soil springs ----
    dz_arr = _tributary_dz(depths, L_skirt)
    k_trib = k_per_m * dz_arr  # N/m per spring
    p_trib = p_per_m * dz_arr  # N per spring

    n_soil_elements = 0
    mat_counter = 0
    integrated_kx = 0.0
    integrated_pult = 0.0

    for i in range(n_segments):
        k_lat = float(k_trib[i])
        p_lat = float(p_trib[i])
        if k_lat <= 1.0:
            continue

        skirt_node = node_tags[i + 1]
        ghost_tag = GHOST_NODE_OFFSET + i
        ops.node(ghost_tag, 0.0, 0.0, -float(depths[i]))
        ops.fix(ghost_tag, 1, 1, 1, 1, 1, 1)

        # Shaft friction: t_ult = shaft_tp_ratio * p_ult;
        # k_vert = shaft_kz_ratio * k_lat.
        # Ratios are configurable via Foundation(shaft_t_to_p_ratio=...,
        # shaft_kz_to_kx_ratio=...); defaults 0.5 / 0.5 match the
        # existing Op^3 nonlinear-BNWF convention pending an OptumG2
        # t-z calibration.
        t_ult = shaft_tp_ratio * p_lat
        k_vert = shaft_kz_ratio * k_lat
        y50 = max(0.5 * p_lat / max(k_lat, 1e-6), 1e-6)
        z50 = max(0.5 * t_ult / max(k_vert, 1e-6), 1e-6)

        mx_tag = MAT_TAG_BASE + mat_counter; mat_counter += 1
        my_tag = MAT_TAG_BASE + mat_counter; mat_counter += 1
        mz_tag = MAT_TAG_BASE + mat_counter; mat_counter += 1

        if nonlinear:
            ops.uniaxialMaterial(
                "PySimple1", mx_tag, 2, max(p_lat, 1.0), y50, 0.0
            )
            ops.uniaxialMaterial(
                "PySimple1", my_tag, 2, max(p_lat, 1.0), y50, 0.0
            )
            ops.uniaxialMaterial(
                "TzSimple1", mz_tag, 2, max(t_ult, 1.0), z50, 0.0
            )
        else:
            ops.uniaxialMaterial("Elastic", mx_tag, max(k_lat, 1.0))
            ops.uniaxialMaterial("Elastic", my_tag, max(k_lat, 1.0))
            ops.uniaxialMaterial("Elastic", mz_tag, max(k_vert, 1.0))

        soil_ele_tag = SOIL_ELEM_OFFSET + i
        ops.element(
            "zeroLength", soil_ele_tag, ghost_tag, skirt_node,
            "-mat", mx_tag, my_tag, mz_tag,
            "-dir", 1, 2, 3,
        )
        n_soil_elements += 1
        integrated_kx += k_lat
        integrated_pult += p_lat

    # ---- Base (skirt-tip) reaction ----
    # Proxy end-bearing values until the Op^3 OptumG2 base-probe is
    # wired in. Ratios come from Foundation.base_H_stiffness_fraction
    # etc.; defaults are announced via the UserWarning above.
    mean_dz = float(np.mean(dz_arr)) if dz_arr.size else 1.0
    k_H_base = max(base_H_frac * integrated_kx, 1.0)
    k_V_base = max(base_VH_ratio * k_H_base, 1.0)
    k_rot_base = max(integrated_kx * mean_dz ** 2 * _BASE_KROT_SHAPE_FACTOR, 1.0)
    k_tor_base = max(_BASE_KTOR_FRACTION * k_rot_base, 1.0)

    tip_tag = node_tags[-1]
    # zeroLength requires L=0 — place the base ghost at the same
    # coordinate as the skirt tip, not at -L_skirt (which would
    # produce a 0.1-0.5 m gap when the deepest spring row does not
    # sit exactly at the skirt tip).
    tip_x, tip_y, tip_z = ops.nodeCoord(tip_tag)
    ops.node(BASE_GHOST_TAG, float(tip_x), float(tip_y), float(tip_z))
    ops.fix(BASE_GHOST_TAG, 1, 1, 1, 1, 1, 1)
    base_ks = [k_H_base, k_H_base, k_V_base, k_rot_base, k_rot_base, k_tor_base]
    for tag, k in zip(MAT_BASE_TAGS, base_ks):
        ops.uniaxialMaterial("Elastic", tag, float(k))
    ops.element(
        "zeroLength", BASE_ELEM_TAG, BASE_GHOST_TAG, tip_tag,
        "-mat", *MAT_BASE_TAGS,
        "-dir", 1, 2, 3, 4, 5, 6,
    )

    return {
        "description": (
            "physical distributed BNWF (PySimple1/TzSimple1 backbones)"
            if nonlinear else
            "physical distributed BNWF (Elastic tangent stiffness)"
        ),
        "n_skirt_segments": int(n_segments),
        "n_soil_elements": int(n_soil_elements),
        "n_springs": int(n_soil_elements),  # back-compat alias
        "skirt_length_m": float(L_skirt),
        "diameter_m": float(D),
        "skirt_thickness_m": float(t_skirt),
        "nonlinear": bool(nonlinear),
        "has_transition_beam": bool(has_transition),
        "base_elev_m": float(base_z),
        "integrated_lateral_kN_per_m": float(integrated_kx / 1.0e3),
        "integrated_p_ult_kN": float(integrated_pult / 1.0e3),
        "base_kH_kN_per_m": float(k_H_base / 1.0e3),
        "base_kV_kN_per_m": float(k_V_base / 1.0e3),
        "base_kRot_kN_m_per_rad": float(k_rot_base / 1.0e3),
        # Expose the proxy ratios so downstream code can report which
        # defaults fell through vs. which were user-supplied.
        "proxy_base_H_stiffness_fraction": base_H_frac,
        "proxy_base_V_to_H_ratio": base_VH_ratio,
        "proxy_shaft_t_to_p_ratio": shaft_tp_ratio,
        "proxy_shaft_kz_to_kx_ratio": shaft_kz_ratio,
        "proxy_defaulted": tuple(defaulted),
    }


