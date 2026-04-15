"""Long-running analysis endpoints. Phase-1 stub; populated in Phase 2/4."""
from __future__ import annotations

from fastapi import APIRouter

router = APIRouter()


@router.get("/jobs")
def list_jobs() -> list[dict]:
    return []
