"""Foundation endpoints -- DNV-ST-0126 stiffness + scour, Op3 bridge."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from backend.models.schemas import (
    CapacityResponse, FoundationCapacityRequest,
)
from backend.services.op3_service import calculate_foundation_capacity

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
