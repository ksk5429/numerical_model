"""Anchor endpoints. Phase-1 stub; populated in Phase 2."""
from __future__ import annotations

from fastapi import APIRouter

router = APIRouter()


@router.get("/methods")
def list_anchor_methods() -> list[str]:
    return ["dnv_rp_e303", "murff_hamilton", "api_rp_2sk",
            "aubeny_2003", "fe_calibrated"]
