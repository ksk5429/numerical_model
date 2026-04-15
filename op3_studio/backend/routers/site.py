"""Site & soil endpoints. Phase-1 stub; populated in Phase 2."""
from __future__ import annotations

from fastapi import APIRouter

from backend.models.schemas import SiteProfile

router = APIRouter()


@router.get("/list")
def list_sites() -> list[str]:
    """Return the names of saved site profiles. Stub returns empty list."""
    return []


@router.post("/validate")
def validate_site(site: SiteProfile) -> dict:
    """Validate a SiteProfile without persisting it."""
    return {"valid": True, "name": site.name, "n_layers": len(site.layers)}
