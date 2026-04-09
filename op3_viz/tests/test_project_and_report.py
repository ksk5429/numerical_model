"""Tests for op3_viz.project (.op3proj file format) and op3_viz.report.

These tests exercise the M-03 project file format and the M-04 report
generator. They do NOT require the private data tree.
"""
from __future__ import annotations

from pathlib import Path

import pytest


def test_project_new_roundtrip(tmp_path):
    from op3_viz.project import Project, save, load
    p = Project.new(name="My Project")
    p.foundation.mode = "dissipation_weighted"
    p.foundation.scour_m = 2.5
    p.analysis.eigen_modes = 10
    p.dlc.wind_speeds_mps = [6.0, 11.0, 25.0]

    path = save(p, tmp_path / "myproj.op3proj")
    assert path.exists()
    assert path.suffix == ".op3proj"

    p2 = load(path)
    assert p2.name == "My Project"
    assert p2.foundation.mode == "dissipation_weighted"
    assert p2.foundation.scour_m == 2.5
    assert p2.analysis.eigen_modes == 10
    assert p2.dlc.wind_speeds_mps == [6.0, 11.0, 25.0]


def test_project_suffix_auto_added(tmp_path):
    from op3_viz.project import Project, save, load
    p = Project.new(name="suffix test")
    path = save(p, tmp_path / "noext")
    assert path.suffix == ".op3proj"
    load(path)  # must parse back


def test_project_schema_version_mismatch_raises(tmp_path):
    from op3_viz.project import save, Project, load
    p = Project.new()
    path = save(p, tmp_path / "bad.op3proj")
    # Corrupt the schema version
    text = path.read_text(encoding="utf-8")
    text = text.replace('schema_version: \'1.0\'', 'schema_version: \'0.99\'')
    text = text.replace('schema_version: "1.0"', 'schema_version: "0.99"')
    path.write_text(text, encoding="utf-8")

    with pytest.raises(ValueError, match="unsupported schema_version"):
        load(path)


def test_sample_projects_load():
    """All three committed sample projects must load cleanly."""
    from op3_viz.project import load
    repo = Path(__file__).resolve().parents[2]
    samples = repo / "sample_projects"
    for name in ("gunsan_ref4mw.op3proj",
                 "nrel_5mw_oc3_monopile.op3proj",
                 "iea_15mw_monopile.op3proj"):
        p = samples / name
        assert p.exists(), f"sample missing: {p}"
        proj = load(p)
        assert proj.schema_version == "1.0"
        assert proj.name


def test_report_renders_qmd(tmp_path):
    """render_qmd must produce a syntactically valid .qmd file."""
    from op3_viz.project import Project
    from op3_viz.report import render_qmd
    p = Project.new(name="test report")
    p.foundation.mode = "distributed_bnwf"
    qmd = render_qmd(p, tmp_path)
    assert qmd.exists()
    body = qmd.read_text(encoding="utf-8")
    assert body.startswith("---")
    assert "title:" in body
    assert "distributed_bnwf" in body
    assert "test report" in body
