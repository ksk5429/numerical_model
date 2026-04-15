"""Foundation endpoints. Phase-1 stub; populated in Phase 2."""
from __future__ import annotations

from fastapi import APIRouter

router = APIRouter()


@router.get("/modes")
def list_foundation_modes() -> list[str]:
    return ["fixed", "stiffness_6x6", "distributed_bnwf",
            "dissipation_weighted"]
