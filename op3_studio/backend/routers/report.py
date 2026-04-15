"""Report generation endpoints."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.models.schemas import (
    AnchorParams, ClayProfile, FoundationParams, SiteProfile,
)
from backend.services.report_generator import generate_markdown_report

router = APIRouter()


@router.get("/templates")
def list_templates() -> list[str]:
    return ["foundation_design", "anchor_design", "vv_summary"]


class ReportRequest(BaseModel):
    site: SiteProfile
    foundation: FoundationParams
    scour_depth_m: float = 0.0
    anchor: AnchorParams
    anchor_soil: ClayProfile


class ReportResponse(BaseModel):
    markdown: str


@router.post("/generate", response_model=ReportResponse)
def generate(req: ReportRequest) -> ReportResponse:
    try:
        md = generate_markdown_report(
            site=req.site, foundation=req.foundation,
            scour_depth_m=req.scour_depth_m,
            anchor=req.anchor, anchor_soil=req.anchor_soil,
        )
        return ReportResponse(markdown=md)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
