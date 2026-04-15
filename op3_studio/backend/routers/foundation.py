"""Foundation endpoints -- DNV-ST-0126 stiffness + scour, Op3 bridge."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from backend.models.schemas import (
    CapacityResponse, FoundationCapacityRequest,
    FoundationMeshRequest, MeshResponse,
)
from backend.services.op3_service import calculate_foundation_capacity
from backend.services.mesh_generator import (
    generate_suction_bucket_mesh, generate_tripod_mesh,
)

router = APIRouter()


@router.get("/modes")
def list_foundation_modes() -> list[str]:
    """List the four Op3 foundation representations."""
    return ["fixed", "stiffness_6x6", "distributed_bnwf",
            "dissipation_weighted"]


@router.get("/standards")
def list_standards() -> list[str]:
    """List the supported industry standards for Mode B stiffness."""
    return ["dnv", "api", "iso", "owa", "pisa", "hssmall"]


@router.post("/capacity", response_model=CapacityResponse)
def capacity(req: FoundationCapacityRequest) -> CapacityResponse:
    """Calculate foundation capacity / stiffness via DNV-ST-0126."""
    try:
        return calculate_foundation_capacity(req)
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/mesh", response_model=MeshResponse)
def mesh(req: FoundationMeshRequest) -> MeshResponse:
    """Generate Three.js-compatible mesh for the given foundation."""
    f = req.foundation
    if f.type == "tripod":
        comp = generate_tripod_mesh(
            bucket_diameter_m=f.diameter_m,
            bucket_length_m=f.length_m,
            tripod_spacing_m=max(2.5 * f.diameter_m, 12.0),
            tower_height_m=80.0,
            scour_depth_m=req.scour_depth_m,
            n_segments=req.n_segments,
        )
        meta = {"shape": "tripod"}
    else:
        comp = generate_suction_bucket_mesh(
            diameter_m=f.diameter_m,
            skirt_length_m=f.length_m,
            wall_thickness_mm=f.wall_thickness_mm,
            scour_depth_m=req.scour_depth_m,
            n_segments=req.n_segments,
            stress_profile=req.stress_profile,
        )
        meta = {"shape": "monopod_or_bucket"}
    return MeshResponse(components=comp, metadata=meta)
