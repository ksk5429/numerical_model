"""Scour parametric endpoint -- sweep capacity over a list of depths."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from backend.models.schemas import ScourSweepRequest, ScourSweepResponse
from backend.services.op3_service import scour_sweep

router = APIRouter()


@router.get("/range")
def default_scour_range() -> list[float]:
    return [0.0, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0]


@router.post("/sweep", response_model=ScourSweepResponse)
def sweep(req: ScourSweepRequest) -> ScourSweepResponse:
    try:
        return scour_sweep(req)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
