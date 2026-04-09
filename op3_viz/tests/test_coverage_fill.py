"""Coverage-fill tests for internal Dash helpers, report metadata,
and compliance module helpers.
"""
from __future__ import annotations

import numpy as np
import pytest


# --- internal Dash helpers that render figures --------------------

def test_mudline_disk_returns_mesh3d():
    from op3_viz.dash_app.app import _mudline_disk
    d = _mudline_disk(radius=15.0, z=-1.0)
    # plotly Mesh3d object has x/y/z attributes
    assert hasattr(d, "x")
    assert len(d.x) == 49  # 1 centre + 48 rim


def test_mesh3d_helper_with_intensity():
    """_mesh3d should accept an explicit intensity array."""
    from op3_viz.dash_app.app import _mesh3d
    from op3_viz.geometry import build_rotor_disk
    m = build_rotor_disk(n_theta=16)
    intensity = np.linspace(0, 1, len(m.x))
    trace = _mesh3d(m, intensity=intensity, colorscale="Viridis",
                    name="test", showscale=True)
    assert hasattr(trace, "intensity")
    assert trace.name == "test"


def test_mesh3d_helper_with_color():
    from op3_viz.dash_app.app import _mesh3d
    from op3_viz.geometry import build_rotor_disk
    m = build_rotor_disk(n_theta=12)
    trace = _mesh3d(m, color="#123456", name="solid")
    assert trace.color == "#123456"


# --- compliance _run_script script-exists path --------------------

def test_run_script_missing_is_reported(monkeypatch):
    """_run_script returns status 'missing' with the script path when
    it does not exist (covers the early-return branch)."""
    from pathlib import Path
    from op3_viz.compliance import _run_script
    r = _run_script(Path("/definitely/not/here.py"), "unit_test")
    assert r["status"] == "missing"
    assert "here.py" in r["script"]
    assert r["label"] == "unit_test"
    assert r["clauses"] == []


# --- report generator metadata fields -----------------------------

def test_report_render_contains_all_project_sections(tmp_path):
    """The rendered .qmd must include headings for every major
    section documented in the Op^3 analysis-report template."""
    from op3_viz.project import Project
    from op3_viz.report import render_qmd
    p = Project.new(name="coverage test project")
    p.turbine.reference = "test_turbine"
    p.foundation.mode = "fixed"
    p.foundation.scour_m = 1.5
    p.soil.su0_kPa = 42.0
    p.soil.k_su_kPa_per_m = 3.14
    qmd = render_qmd(p, tmp_path)
    body = qmd.read_text(encoding="utf-8")
    for heading in ("# Project Summary",
                    "# Turbine and Foundation",
                    "# Soil Profile",
                    "# Analysis Configuration",
                    "# Design Load Case Configuration",
                    "# Conformance",
                    "# Provenance"):
        assert heading in body, f"missing: {heading}"
    assert "coverage test project" in body
    assert "42.0" in body
    assert "3.14" in body


# --- project defaults -----------------------------------------------

def test_project_defaults():
    """A fresh Project has sensible defaults across all subrecords."""
    from op3_viz.project import Project
    p = Project.new()
    assert p.schema_version == "1.0"
    assert p.turbine.reference == "ref_4mw_owt"
    assert p.foundation.mode == "distributed_bnwf"
    assert p.foundation.scour_m == 0.0
    assert p.soil.profile_source == "private_csv"
    assert p.analysis.eigen_modes == 6
    assert p.analysis.damping_ratio == 0.01
    assert p.dlc.family == "1.1"
    assert len(p.dlc.wind_speeds_mps) >= 5
    assert p.view_state.tab == "viewer"
