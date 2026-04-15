"""Anchor endpoints -- capacity, installation, padeye optimisation."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from backend.models.schemas import (
    AnchorCapacityRequest, AnchorCapacityResponse,
    InstallationRequest, InstallationResponse,
    PadeyeRequest, PadeyeResponse,
)
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
