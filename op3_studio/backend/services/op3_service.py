"""Op3 service bridge -- pure Python adapters between the FastAPI
schemas and the underlying ``op3`` and ``op3.anchors`` Python APIs.

Design rules
------------
* Every function here is synchronous and side-effect-free; long-running
  analyses are launched asynchronously by ``analysis_runner`` (Phase 4).
* Only real Op3 results are returned. If a piece of data is unavailable
  (e.g. natural frequency without OpenSeesPy) the corresponding field
  is ``None`` -- never a placeholder number.
* Schemas are translated by hand so the wire format stays decoupled
  from internal Op3 dataclass changes.
"""
from __future__ import annotations

from typing import Any

import numpy as np

from backend.models.schemas import (
    AnchorCapacityRequest, AnchorCapacityResponse,
    AnchorParams, ClayProfile,
    CapacityResponse, FoundationCapacityRequest, FoundationParams,
    InstallationRequest, InstallationResponse,
    PadeyeRequest, PadeyeResponse,
    ScourSweepRequest, ScourSweepResponse,
    SiteProfile, SoilLayer,
)


# ---------------------------------------------------------------------------
# Foundation capacity (DNV-ST-0126 derived stiffness for Phase 2 -- the
# full Op3 OpenSees pipeline is exposed via /api/analysis in Phase 4).
# ---------------------------------------------------------------------------

def calculate_foundation_capacity(
    req: FoundationCapacityRequest,
) -> CapacityResponse:
    """Wrap op3.standards stiffness calculators.

    For the Studio's first release we report the equivalent linear
    diagonal 6x6 stiffness from DNV-ST-0126 (Mode B). The result is
    converted into "capacity proxies" suitable for the UI: K_x, K_z,
    K_phi -> H, V, M ultimate via small-strain limit estimates.
    """
    f = req.foundation
    site = req.site

    # Resolve a representative soil class for DNV-ST-0126 lookup.
    soil_type = _representative_soil_type(site.layers)

    # Lazy import: keep service import-time light; raise clearly if op3
    # is not on PYTHONPATH.
    try:
        from op3.standards import (
            dnv_monopile_stiffness,
            dnv_suction_bucket_stiffness,
        )
    except ImportError as e:
        raise RuntimeError(
            "op3 package not importable from FastAPI process. "
            "Did `pip install -e .` run in the repo root?"
        ) from e

    if f.type in ("monopile",):
        K = dnv_monopile_stiffness(
            diameter_m=f.diameter_m,
            embedment_m=f.length_m - req.scour_depth_m,
            soil_type=soil_type,
        )
        method = "DNV-ST-0126 monopile"
    else:
        # suction_bucket / tripod / suction_anchor / jacket fall through
        # to the bucket formulation for Phase 2; jackets get a more
        # accurate model in Phase 4.
        K = dnv_suction_bucket_stiffness(
            diameter_m=f.diameter_m,
            skirt_length_m=f.length_m,
            soil_type=soil_type,
        )
        method = "DNV-ST-0126 suction bucket"

    # K is a 6x6 numpy array in N/m and N*m/rad. Convert to "engineering
    # capacity proxy": multiply by a representative serviceability
    # displacement (0.05 m, 0.005 rad) to get unit-load capacities the
    # UI can plot. This is a reporting convenience; the true ULS
    # capacity comes from the OpenSees pushover analysis launched via
    # the /api/analysis router in a later phase.
    Kx = float(K[0, 0])
    Kz = float(K[2, 2])
    Kphi = float(K[4, 4])

    H_proxy_kN = Kx * 0.05 / 1000.0
    V_proxy_kN = Kz * 0.05 / 1000.0
    M_proxy_kNm = Kphi * 0.005 / 1000.0

    warnings: list[str] = []
    if req.scour_depth_m > 0 and f.type == "monopile":
        warnings.append(
            "Scour applied by reducing embedment; full Op3 scour "
            "relief profile available via /api/scour/sweep."
        )

    return CapacityResponse(
        vertical_kN=V_proxy_kN,
        horizontal_kN=H_proxy_kN,
        moment_kNm=M_proxy_kNm,
        natural_frequency_Hz=None,  # populated by /api/analysis/eigen
        safety_factor=None,
        interaction_curve=[],
        warnings=warnings,
        metadata={
            "method": method,
            "soil_type": soil_type,
            "Kxx_N_per_m": Kx,
            "Kzz_N_per_m": Kz,
            "Kpp_Nm_per_rad": Kphi,
        },
    )


def _representative_soil_type(layers: list[SoilLayer]) -> str:
    """Pick the dominant soil type by total thickness, mapped onto the
    DNV-ST-0126 soil-name vocabulary."""
    by_type: dict[str, float] = {}
    for L in layers:
        by_type[L.soil_type] = by_type.get(L.soil_type, 0.0) + L.thickness_m
    if not by_type:
        return "medium_sand"
    dominant = max(by_type.items(), key=lambda kv: kv[1])[0]
    # Map UI vocabulary -> DNV vocabulary
    return {
        "sand":  "medium_sand",
        "clay":  "medium_clay",
        "silt":  "soft_clay",
        "rock":  "rock",
    }.get(dominant, "medium_sand")


# ---------------------------------------------------------------------------
# Scour parametric
# ---------------------------------------------------------------------------

def scour_sweep(req: ScourSweepRequest) -> ScourSweepResponse:
    """Run capacity at every requested scour depth."""
    H, V, M = [], [], []
    for d in req.scour_depths_m:
        sub = FoundationCapacityRequest(
            site=req.site, foundation=req.foundation, scour_depth_m=d,
        )
        cap = calculate_foundation_capacity(sub)
        H.append(cap.horizontal_kN)
        V.append(cap.vertical_kN)
        M.append(cap.moment_kNm)
    return ScourSweepResponse(
        scour_depths_m=req.scour_depths_m,
        H_ult_kN=H, V_ult_kN=V, M_ult_kNm=M,
        natural_frequency_Hz=None,
    )


# ---------------------------------------------------------------------------
# Anchor capacity
# ---------------------------------------------------------------------------

def calculate_anchor_capacity(
    req: AnchorCapacityRequest,
) -> AnchorCapacityResponse:
    """Wrap op3.anchors.anchor_capacity()."""
    try:
        from op3.anchors import (
            SuctionAnchor, UndrainedClayProfile, anchor_capacity,
        )
    except ImportError as e:
        raise RuntimeError(
            "op3.anchors not importable; install op3 with the anchors "
            "module (pip install -e .)."
        ) from e

    a = SuctionAnchor(
        diameter_m=req.anchor.diameter_m,
        skirt_length_m=req.anchor.skirt_length_m,
        wall_thickness_mm=req.anchor.wall_thickness_mm,
        padeye_depth_m=req.anchor.padeye_depth_m,
        padeye_offset_m=req.anchor.padeye_offset_m,
        submerged_weight_kN=req.anchor.submerged_weight_kN,
    )
    s = UndrainedClayProfile(
        su_mudline_kPa=req.soil.su_mudline_kPa,
        su_gradient_kPa_per_m=req.soil.su_gradient_kPa_per_m,
        gamma_eff_kN_per_m3=req.soil.gamma_eff_kN_per_m3,
        sensitivity=req.soil.sensitivity,
        plasticity_index=req.soil.plasticity_index,
    )
    extra: dict[str, Any] = {}
    if req.method == "aubeny_2003":
        extra["interface"] = req.aubeny_interface

    r = anchor_capacity(a, s,
                        method=req.method,
                        load_angle_deg=req.load_angle_deg,
                        **extra)

    env = r.interaction_envelope[["H_kN", "V_kN"]].to_dict("records")
    prof = r.depth_profile[["depth_m", "su_kPa", "Np",
                            "dH_per_m_kN_per_m"]].to_dict("records")

    return AnchorCapacityResponse(
        method=r.method,
        H_ult_kN=r.H_ult_kN,
        V_ult_kN=r.V_ult_kN,
        T_ult_kN=r.T_ult_kN,
        load_angle_deg=r.load_angle_deg,
        interaction_envelope=env,
        depth_profile=prof,
        metadata=r.metadata,
    )


# ---------------------------------------------------------------------------
# Anchor installation
# ---------------------------------------------------------------------------

def calculate_anchor_installation(
    req: InstallationRequest,
) -> InstallationResponse:
    from op3.anchors import (
        SuctionAnchor, UndrainedClayProfile, installation_analysis,
    )
    a = SuctionAnchor(
        diameter_m=req.anchor.diameter_m,
        skirt_length_m=req.anchor.skirt_length_m,
        wall_thickness_mm=req.anchor.wall_thickness_mm,
        padeye_depth_m=req.anchor.padeye_depth_m,
        submerged_weight_kN=req.anchor.submerged_weight_kN,
    )
    s = UndrainedClayProfile(
        su_mudline_kPa=req.soil.su_mudline_kPa,
        su_gradient_kPa_per_m=req.soil.su_gradient_kPa_per_m,
        gamma_eff_kN_per_m3=req.soil.gamma_eff_kN_per_m3,
        sensitivity=req.soil.sensitivity,
    )
    res = installation_analysis(a, s, water_depth_m=req.water_depth_m)
    return InstallationResponse(
        self_weight_depth_m=res.self_weight_depth_m,
        max_suction_required_kPa=res.max_suction_required_kPa,
        max_allowable_suction_kPa=res.max_allowable_suction_kPa,
        plug_heave_ok=res.plug_heave_ok,
        feasible=res.feasible,
        profile=res.profile.to_dict("records"),
        metadata=res.metadata,
    )


# ---------------------------------------------------------------------------
# Padeye
# ---------------------------------------------------------------------------

def optimize_padeye(req: PadeyeRequest) -> PadeyeResponse:
    from op3.anchors import (
        SuctionAnchor, UndrainedClayProfile, optimal_padeye_analytical,
    )
    a = SuctionAnchor(
        diameter_m=req.anchor.diameter_m,
        skirt_length_m=req.anchor.skirt_length_m,
        wall_thickness_mm=req.anchor.wall_thickness_mm,
    )
    s = UndrainedClayProfile(
        su_mudline_kPa=req.soil.su_mudline_kPa,
        su_gradient_kPa_per_m=req.soil.su_gradient_kPa_per_m,
        sensitivity=req.soil.sensitivity,
    )
    z = optimal_padeye_analytical(a, s, method=req.method)
    return PadeyeResponse(
        optimal_padeye_depth_m=z,
        optimal_padeye_over_L=z / a.skirt_length_m,
        method=req.method,
    )
