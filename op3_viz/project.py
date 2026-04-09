"""
.op3proj project file format -- save and load full analysis state.

An Op^3 project is a single YAML file that carries the tower model,
foundation mode, soil profile, scour depth, DLC configuration, and
view state. The format is human-readable, git-diff friendly, and
intended to support "Open Project" / "Save Project" / "Share with
colleague" workflows in the web application.

Schema (v1):

    schema_version: "1.0"
    name: "Gunsan 4.2 MW baseline"
    created: "2026-04-09T13:30:00"
    modified: "2026-04-09T13:30:00"
    op3_version: "1.0.0-rc1"

    turbine:
        reference: "ref_4mw_owt"     # or "nrel_5mw", "iea_15mw"
        tower_template: "gunsan_u136_tower"

    foundation:
        mode: "distributed_bnwf"      # fixed | stiffness_6x6 | distributed_bnwf | dissipation_weighted
        scour_m: 0.0
        mode_d_alpha: null
        mode_d_beta: null

    soil:
        profile_source: "private_csv"  # or "public_placeholder"
        su0_kPa: null                  # proprietary; loaded at runtime
        k_su_kPa_per_m: null

    analysis:
        eigen_modes: 6
        damping_ratio: 0.01
        pushover_target_disp_m: 1.0

    dlc:
        family: "1.1"
        wind_speeds_mps: [6, 8, 11.4, 15, 19, 25]
        tmax_s: 120

    view_state:
        field_overlay: "real_stress"
        scour_slider_m: 0.0
        tab: "viewer"

API
---

    from op3_viz.project import Project, load, save

    p = Project.new(name="My Project")
    p.foundation.mode = "dissipation_weighted"
    save(p, "myproject.op3proj")

    p2 = load("myproject.op3proj")
"""
from __future__ import annotations

import datetime as dt
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Optional

try:
    import yaml
except ImportError as exc:  # pragma: no cover
    raise ImportError(
        "op3_viz.project requires PyYAML. Install with `pip install pyyaml`."
    ) from exc

SCHEMA_VERSION = "1.0"
DEFAULT_OP3_VERSION = "1.0.0-rc1"


@dataclass
class Turbine:
    reference: str = "ref_4mw_owt"
    tower_template: str = "gunsan_u136_tower"


@dataclass
class Foundation:
    mode: str = "distributed_bnwf"
    scour_m: float = 0.0
    mode_d_alpha: Optional[float] = None
    mode_d_beta: Optional[float] = None


@dataclass
class Soil:
    profile_source: str = "private_csv"
    su0_kPa: Optional[float] = None
    k_su_kPa_per_m: Optional[float] = None


@dataclass
class Analysis:
    eigen_modes: int = 6
    damping_ratio: float = 0.01
    pushover_target_disp_m: float = 1.0


@dataclass
class DLC:
    family: str = "1.1"
    wind_speeds_mps: list = field(
        default_factory=lambda: [6.0, 8.0, 11.4, 15.0, 19.0, 25.0]
    )
    tmax_s: float = 120.0


@dataclass
class ViewState:
    field_overlay: str = "real_stress"
    scour_slider_m: float = 0.0
    tab: str = "viewer"


@dataclass
class Project:
    schema_version: str = SCHEMA_VERSION
    name: str = "Untitled Op^3 Project"
    created: str = ""
    modified: str = ""
    op3_version: str = DEFAULT_OP3_VERSION
    turbine: Turbine = field(default_factory=Turbine)
    foundation: Foundation = field(default_factory=Foundation)
    soil: Soil = field(default_factory=Soil)
    analysis: Analysis = field(default_factory=Analysis)
    dlc: DLC = field(default_factory=DLC)
    view_state: ViewState = field(default_factory=ViewState)

    @classmethod
    def new(cls, name: str = "Untitled Op^3 Project") -> "Project":
        now = dt.datetime.now().isoformat(timespec="seconds")
        return cls(name=name, created=now, modified=now)


def save(project: Project, path: str | Path) -> Path:
    """Write the project to a .op3proj YAML file."""
    project.modified = dt.datetime.now().isoformat(timespec="seconds")
    p = Path(path)
    if p.suffix != ".op3proj":
        p = p.with_suffix(".op3proj")
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("w", encoding="utf-8") as f:
        yaml.safe_dump(
            asdict(project),
            f,
            default_flow_style=False,
            sort_keys=False,
            allow_unicode=True,
        )
    return p


def load(path: str | Path) -> Project:
    """Read a .op3proj file and return a Project."""
    p = Path(path)
    with p.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if data.get("schema_version") != SCHEMA_VERSION:
        raise ValueError(
            f"unsupported schema_version: {data.get('schema_version')!r} "
            f"(expected {SCHEMA_VERSION!r})"
        )
    return Project(
        schema_version=data["schema_version"],
        name=data.get("name", "Untitled"),
        created=data.get("created", ""),
        modified=data.get("modified", ""),
        op3_version=data.get("op3_version", DEFAULT_OP3_VERSION),
        turbine=Turbine(**data.get("turbine", {})),
        foundation=Foundation(**data.get("foundation", {})),
        soil=Soil(**data.get("soil", {})),
        analysis=Analysis(**data.get("analysis", {})),
        dlc=DLC(**data.get("dlc", {})),
        view_state=ViewState(**data.get("view_state", {})),
    )
