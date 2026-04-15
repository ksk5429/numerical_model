"""Scour parametric endpoints. Phase-1 stub; populated in Phase 2."""
from __future__ import annotations

from fastapi import APIRouter

router = APIRouter()


@router.get("/range")
def default_scour_range() -> list[float]:
    return [0.0, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0]
