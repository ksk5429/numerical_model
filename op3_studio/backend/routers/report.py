"""Report generation endpoints. Phase-1 stub."""
from __future__ import annotations

from fastapi import APIRouter

router = APIRouter()


@router.get("/templates")
def list_templates() -> list[str]:
    return ["foundation_design", "anchor_design", "vv_summary"]
