"""Anchor endpoints -- capacity, installation, padeye optimisation."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from backend.models.schemas import (
    AnchorCapacityRequest, AnchorCapacityResponse,
    AnchorMeshRequest, MeshResponse,
    InstallationRequest, InstallationResponse,
    PadeyeRequest, PadeyeResponse,
)
from backend.services.mesh_generator import generate_anchor_mesh
from backend.services.op3_service import (
    calculate_anchor_capacity,
    calculate_anchor_installation,
    optimize_padeye,
)

router = APIRouter()


@router.get("/methods")
def list_anchor_methods() -> list[str]:
    return ["dnv_rp_e303", "murff_hamilton", "api_rp_2sk",
            "aubeny_2003", "fe_calibrated"]


@router.post("/capacity", response_model=AnchorCapacityResponse)
def capacity(req: AnchorCapacityRequest) -> AnchorCapacityResponse:
    try:
        return calculate_anchor_capacity(req)
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/installation", response_model=InstallationResponse)
def installation(req: InstallationRequest) -> InstallationResponse:
    try:
        return calculate_anchor_installation(req)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/optimize-padeye", response_model=PadeyeResponse)
def optimize_padeye_endpoint(req: PadeyeRequest) -> PadeyeResponse:
    try:
        return optimize_padeye(req)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/mesh", response_model=MeshResponse)
def mesh(req: AnchorMeshRequest) -> MeshResponse:
    """Three.js mesh for the anchor + mooring catenary."""
    a = req.anchor
    z_p = a.padeye_depth_m if a.padeye_depth_m is not None \
        else 0.7 * a.skirt_length_m
    comp = generate_anchor_mesh(
        diameter_m=a.diameter_m,
        skirt_length_m=a.skirt_length_m,
        padeye_depth_m=z_p,
        mooring_angle_deg=req.mooring_angle_deg,
        mooring_length_m=req.mooring_length_m,
        n_segments=req.n_segments,
    )
    return MeshResponse(components=comp,
                        metadata={"shape": "suction_anchor"})
