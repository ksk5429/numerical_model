"""Site & soil + project persistence endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Body, HTTPException

from backend.models.schemas import SiteProfile
from backend.services import project_store

router = APIRouter()


# ---- Site validation -------------------------------------------------------

@router.post("/validate")
def validate_site(site: SiteProfile) -> dict:
    """Validate a SiteProfile without persisting it."""
    return {"valid": True, "name": site.name, "n_layers": len(site.layers)}


# ---- Project persistence ---------------------------------------------------
# A "project" bundles site + foundation + scour + anchor + clay + chat
# history into a single JSON document under op3_studio/projects/.

@router.get("/list")
def list_projects() -> list[dict]:
    return project_store.list_projects()


@router.post("/save")
def save_project(name: str,
                 payload: dict = Body(...)) -> dict:
    try:
        return project_store.save_project(name, payload)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/load")
def load_project(name: str) -> dict:
    try:
        return project_store.load_project(name)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/delete")
def delete_project(name: str) -> dict:
    try:
        project_store.delete_project(name)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"deleted": name}
