"""OpenFAST coupling endpoints. Phase-1 stub."""
from __future__ import annotations

from fastapi import APIRouter

router = APIRouter()


@router.get("/decks")
def list_decks() -> list[str]:
    return ["site_a_ref4mw", "iea_15mw_volturnus", "nrel_5mw_oc3"]
