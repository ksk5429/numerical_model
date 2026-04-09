"""Tests for op3_viz.compliance — audit + DLC dispatch wiring."""
from __future__ import annotations

from pathlib import Path

import pytest


def test_run_dnv_audit_graceful_when_script_missing(monkeypatch, tmp_path):
    import op3_viz.compliance as comp
    # Redirect the DNV script path to a non-existent file
    monkeypatch.setattr(comp, "DNV_SCRIPT", tmp_path / "nope.py")
    result = comp.run_dnv_audit()
    assert result["status"] == "missing"
    assert "not found" in result["message"]


def test_run_iec_audit_graceful_when_script_missing(monkeypatch, tmp_path):
    import op3_viz.compliance as comp
    monkeypatch.setattr(comp, "IEC_SCRIPT", tmp_path / "nope.py")
    result = comp.run_iec_audit()
    assert result["status"] == "missing"


def test_dispatch_dlc_unsupported_family():
    from op3_viz.compliance import dispatch_dlc_run
    result = dispatch_dlc_run(family="99.99", wind_speeds=[1], tmax_s=1.0)
    assert result["status"] == "unsupported"
    assert "99.99" in str(result)


def test_run_script_handles_missing_file():
    """The internal _run_script helper must return a 'missing' status
    for any path that does not exist (regression guard)."""
    from op3_viz.compliance import _run_script
    result = _run_script(Path("/nonexistent/script.py"), "bogus")
    assert result["status"] == "missing"
    assert result["label"] == "bogus"
