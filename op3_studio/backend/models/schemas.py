"""Pydantic request/response schemas for the Op3 Studio API.

The schemas in this module are the authoritative wire format between
the React frontend and the FastAPI backend. TypeScript counterparts
live in ``frontend/src/types/op3.ts`` and must be kept in sync.

All physical units are SI (m, mm for wall thickness, kPa, kN, deg)
and match the conventions of the underlying ``op3`` package.
"""
from __future__ import annotations

from typing import List, Literal, Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Site & soil
# ---------------------------------------------------------------------------

class SoilLayer(BaseModel):
    depth_m: float = Field(..., description="Top of layer below mudline")
    thickness_m: float
    soil_type: Literal["sand", "clay", "silt", "rock"]
    undrained_shear_strength_kPa: Optional[float] = None
    friction_angle_deg: Optional[float] = None
    unit_weight_kN_m3: float = 10.0
    color: str = "#8B7355"


class SiteProfile(BaseModel):
    name: str
    water_depth_m: float
    layers: List[SoilLayer]
    cpt_data: Optional[List[dict]] = None


# ---------------------------------------------------------------------------
# Foundation
# ---------------------------------------------------------------------------

class FoundationParams(BaseModel):
    type: Literal["monopile", "suction_bucket", "tripod",
                  "jacket", "suction_anchor"]
    diameter_m: float
    length_m: float
    wall_thickness_mm: float = 25.0
    foundation_mode: Literal[
        "fixed", "stiffness_6x6", "distributed_bnwf", "dissipation_weighted"
    ] = "distributed_bnwf"
    standard: Literal["dnv", "api", "iso", "owa", "pisa", "hssmall"] = "dnv"


class FoundationCapacityRequest(BaseModel):
    site: SiteProfile
    foundation: FoundationParams
    scour_depth_m: float = 0.0


class CapacityResponse(BaseModel):
    vertical_kN: float
    horizontal_kN: float
    moment_kNm: float
    natural_frequency_Hz: float | None = None
    safety_factor: float | None = None
    interaction_curve: List[dict] = []
    warnings: List[str] = []
    metadata: dict = {}


class EigenRequest(BaseModel):
    site: SiteProfile
    foundation: FoundationParams
    n_modes: int = 6


class EigenResponse(BaseModel):
    frequencies_Hz: List[float]
    metadata: dict = {}


class ScourSweepRequest(BaseModel):
    site: SiteProfile
    foundation: FoundationParams
    scour_depths_m: List[float]


class ScourSweepResponse(BaseModel):
    scour_depths_m: List[float]
    H_ult_kN: List[float]
    V_ult_kN: List[float]
    M_ult_kNm: List[float]
    natural_frequency_Hz: List[float] | None = None


# ---------------------------------------------------------------------------
# Anchor
# ---------------------------------------------------------------------------

class AnchorParams(BaseModel):
    diameter_m: float
    skirt_length_m: float
    wall_thickness_mm: float = 30.0
    padeye_depth_m: Optional[float] = None
    padeye_offset_m: float = 0.0
    submerged_weight_kN: float = 0.0


class ClayProfile(BaseModel):
    su_mudline_kPa: float
    su_gradient_kPa_per_m: float
    gamma_eff_kN_per_m3: float = 6.0
    sensitivity: float = 3.0
    plasticity_index: float = 30.0


class AnchorCapacityRequest(BaseModel):
    anchor: AnchorParams
    soil: ClayProfile
    method: Literal["dnv_rp_e303", "murff_hamilton", "api_rp_2sk",
                    "aubeny_2003"] = "dnv_rp_e303"
    load_angle_deg: float = 0.0
    aubeny_interface: Literal["smooth", "rough"] = "rough"


class AnchorCapacityResponse(BaseModel):
    method: str
    H_ult_kN: float
    V_ult_kN: float
    T_ult_kN: float
    load_angle_deg: float
    interaction_envelope: List[dict]
    depth_profile: List[dict]
    metadata: dict = {}


class InstallationRequest(BaseModel):
    anchor: AnchorParams
    soil: ClayProfile
    water_depth_m: float


class InstallationResponse(BaseModel):
    self_weight_depth_m: float
    max_suction_required_kPa: float
    max_allowable_suction_kPa: float
    plug_heave_ok: bool
    feasible: bool
    profile: List[dict]
    metadata: dict = {}


class PadeyeRequest(BaseModel):
    anchor: AnchorParams
    soil: ClayProfile
    method: Literal["supachawarote_2005", "murff_hamilton"] = "supachawarote_2005"


class PadeyeResponse(BaseModel):
    optimal_padeye_depth_m: float
    optimal_padeye_over_L: float
    method: str


# ---------------------------------------------------------------------------
# 3D mesh
# ---------------------------------------------------------------------------

class MeshComponent(BaseModel):
    """One Three.js BufferGeometry-compatible component."""
    vertices: Optional[List[List[float]]] = None
    faces: Optional[List[List[int]]] = None
    normals: Optional[List[List[float]]] = None
    colors: Optional[List[List[float]]] = None
    type: Optional[str] = None       # 'line', 'water_plane', or None for mesh
    points: Optional[List[List[float]]] = None  # for type='line'
    color: Optional[List[float]] = None
    linewidth: Optional[int] = None
    extent: Optional[float] = None
    y_offset: Optional[float] = None
    opacity: Optional[float] = None


class MeshResponse(BaseModel):
    components: dict[str, MeshComponent]
    metadata: dict = {}


class FoundationMeshRequest(BaseModel):
    foundation: FoundationParams
    scour_depth_m: float = 0.0
    n_segments: int = 32
    stress_profile: Optional[List[float]] = None


class AnchorMeshRequest(BaseModel):
    anchor: AnchorParams
    mooring_angle_deg: float = 35.0
    mooring_length_m: float = 50.0
    n_segments: int = 32


# ---------------------------------------------------------------------------
# Chat
# ---------------------------------------------------------------------------

class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class ChatRequest(BaseModel):
    message: str
    conversation_history: List[ChatMessage] = []
    project_state: dict = {}


class ChatResponse(BaseModel):
    reply: str
    code_executed: Optional[List[str]] = None
    results: Optional[List[dict]] = None
    error: Optional[str] = None
