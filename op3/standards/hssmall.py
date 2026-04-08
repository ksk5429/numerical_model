"""
HSsmall constitutive wrapper (Phase 3 / Task 3.3).

Bridges the OptumGX Hardening-Soil-with-small-strain-stiffness output
to the Op^3 PISA / cyclic-degradation pipeline.

The Hardening Soil model with small-strain stiffness (Benz 2007;
Schanz et al. 1999) parameterises the soil with:

    E_50_ref     reference secant stiffness at 50% strength
    E_oed_ref    oedometric reference stiffness
    E_ur_ref     unload-reload reference stiffness
    G_0_ref      small-strain shear modulus at reference pressure
    gamma_07     shear strain at G/G_0 = 0.7
    m            power-law stress exponent
    c, phi, psi  strength parameters
    p_ref        reference pressure (usually 100 kPa)

For Op^3 the relevant outputs are:

    G_0(z) = G_0_ref * ((c cot(phi) + sigma_3'(z)) / (c cot(phi) + p_ref)) ** m

which gives a depth-dependent small-strain shear modulus that feeds
the PISA framework directly. For sand (c = 0):

    G_0(z) = G_0_ref * (sigma_3'(z) / p_ref) ** m

This module exposes:

    HSsmallParams           : dataclass for HSsmall material parameters
    hssmall_G_at_depth()    : evaluate G_0(z) for one HSsmall material
    load_hssmall_profile()  : read an OptumGX-exported CSV -> list[SoilState]
    hssmall_to_pisa()       : convert an HSsmall material list to a PISA-ready
                              soil profile

Reference
---------
Benz, T. (2007). "Small-strain stiffness of soils and its numerical
    consequences". PhD dissertation, Univ. of Stuttgart.
Schanz, T., Vermeer, P. A., & Bonnier, P. G. (1999). "The hardening
    soil model: formulation and verification". Beyond 2000 in
    Computational Geotechnics, 281-296.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import pandas as pd

from op3.standards.pisa import SoilState


# ---------------------------------------------------------------------------
# HSsmall material parameter set
# ---------------------------------------------------------------------------

@dataclass
class HSsmallParams:
    """One HSsmall material layer."""
    layer_name: str
    z_top_m: float
    z_bot_m: float
    soil_type: str            # 'sand' or 'clay'
    G0_ref_Pa: float          # G_0 at p_ref
    p_ref_Pa: float = 1.0e5
    m_exp: float = 0.5
    phi_deg: float = 0.0
    c_Pa: float = 0.0
    su_Pa: float = 0.0        # for clay
    gamma_07: float = 1.0e-4  # used by Benz hardening law
    PI_percent: Optional[float] = None
    notes: str = ""


# ---------------------------------------------------------------------------
# Stress-dependent G_0
# ---------------------------------------------------------------------------

def _effective_horizontal_stress(z_m: float, gamma_eff_kN_per_m3: float = 10.0,
                                 K0: float = 0.5) -> float:
    """Crude effective horizontal stress at depth z below mudline."""
    sigma_v = gamma_eff_kN_per_m3 * 1000.0 * z_m   # Pa
    return K0 * sigma_v


def hssmall_G_at_depth(params: HSsmallParams, z_m: float,
                       gamma_eff_kN_per_m3: float = 10.0,
                       K0: float = 0.5) -> float:
    """
    Stress-dependent small-strain shear modulus G_0(z) per the
    HSsmall power law.

    For sand (c = 0): G_0(z) = G_0_ref * (sigma_3'/p_ref) ** m
    For clay (phi = 0, c > 0): use cohesion-shifted form.
    """
    sigma_3 = _effective_horizontal_stress(z_m, gamma_eff_kN_per_m3, K0)
    if params.soil_type == "clay":
        # For undrained clay, G_0 is approximately depth-independent and
        # closely tied to su; default to G_0_ref unless the user wants
        # a power law.
        if params.c_Pa <= 0 and params.phi_deg <= 0:
            return params.G0_ref_Pa
    # Stress-shift term: c * cot(phi) + sigma_3 (Schanz 1999)
    if params.phi_deg > 0:
        cot_phi = 1.0 / math.tan(math.radians(params.phi_deg))
        shift = params.c_Pa * cot_phi
    else:
        shift = 0.0
    num = max(shift + sigma_3, 1.0)
    den = max(shift + params.p_ref_Pa, 1.0)
    return params.G0_ref_Pa * (num / den) ** params.m_exp


# ---------------------------------------------------------------------------
# Convert HSsmall layers -> SoilState profile
# ---------------------------------------------------------------------------

def hssmall_to_pisa(
    layers: list[HSsmallParams],
    n_points_per_layer: int = 3,
) -> list[SoilState]:
    """
    Sample each HSsmall layer at ``n_points_per_layer`` depths and
    return a flat list of SoilState records that PISA can integrate.
    """
    if not layers:
        raise ValueError("layers must contain at least one HSsmallParams")
    if n_points_per_layer < 2:
        raise ValueError("n_points_per_layer must be >= 2")

    out: list[SoilState] = []
    for L in layers:
        zs = [L.z_top_m + (L.z_bot_m - L.z_top_m) * i / (n_points_per_layer - 1)
              for i in range(n_points_per_layer)]
        for z in zs:
            G = hssmall_G_at_depth(L, z)
            su_or_phi = L.su_Pa if L.soil_type == "clay" else L.phi_deg
            out.append(SoilState(
                depth_m=z, G_Pa=G,
                su_or_phi=su_or_phi, soil_type=L.soil_type,
            ))
    # Strip exact-duplicate depths (layer interfaces)
    seen = set()
    deduped: list[SoilState] = []
    for s in out:
        key = (round(s.depth_m, 6), s.soil_type)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(s)
    return deduped


# ---------------------------------------------------------------------------
# CSV loader (OptumGX export format)
# ---------------------------------------------------------------------------

# Column-name aliases supported by the loader
_COLUMN_ALIASES = {
    "layer_name": ["layer", "layer_name", "name"],
    "z_top_m":    ["z_top", "z_top_m", "top_m", "depth_top"],
    "z_bot_m":    ["z_bot", "z_bot_m", "bottom_m", "depth_bot"],
    "soil_type":  ["soil_type", "type", "material"],
    "G0_ref_Pa":  ["g0_ref", "G0_ref", "G0_ref_Pa", "G_0_ref"],
    "p_ref_Pa":   ["p_ref", "p_ref_Pa"],
    "m_exp":      ["m", "m_exp"],
    "phi_deg":    ["phi", "phi_deg", "friction_angle"],
    "c_Pa":       ["c", "c_Pa", "cohesion"],
    "su_Pa":      ["su", "su_Pa", "undrained_strength"],
    "gamma_07":   ["gamma_07", "gamma07"],
    "PI_percent": ["PI", "PI_percent", "plasticity_index"],
}


def _resolve_column(df: pd.DataFrame, key: str) -> Optional[str]:
    for alias in _COLUMN_ALIASES[key]:
        if alias in df.columns:
            return alias
    return None


def load_hssmall_profile(csv_path: str | Path) -> list[HSsmallParams]:
    """
    Read an OptumGX HSsmall layer export.

    Expected columns (case-sensitive aliases supported):
        layer_name, z_top_m, z_bot_m, soil_type, G0_ref_Pa,
        [p_ref_Pa], [m_exp], [phi_deg], [c_Pa], [su_Pa],
        [gamma_07], [PI_percent]

    Anything in [brackets] is optional and falls back to the
    HSsmallParams dataclass default.
    """
    df = pd.read_csv(csv_path)
    required = ["layer_name", "z_top_m", "z_bot_m", "soil_type", "G0_ref_Pa"]
    missing_real = []
    resolved = {}
    for k in _COLUMN_ALIASES:
        col = _resolve_column(df, k)
        if col is not None:
            resolved[k] = col
    for k in required:
        if k not in resolved:
            missing_real.append(k)
    if missing_real:
        raise ValueError(
            f"HSsmall CSV {csv_path} missing required columns: {missing_real}")

    layers: list[HSsmallParams] = []
    for _, row in df.iterrows():
        kwargs = {}
        for k, col in resolved.items():
            v = row[col]
            if pd.isna(v):
                continue
            if k in ("layer_name", "soil_type"):
                kwargs[k] = str(v)
            else:
                kwargs[k] = float(v)
        layers.append(HSsmallParams(**kwargs))
    return layers
