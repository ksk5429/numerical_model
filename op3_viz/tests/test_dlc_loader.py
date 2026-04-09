"""Tests for op3_viz.dlc_loader — OpenFAST .outb discovery + plotting."""
from __future__ import annotations

import pytest
import plotly.graph_objects as go


def test_discover_runs_empty_dir(monkeypatch, tmp_path):
    """When the DLC partial directory does not exist, discover_runs
    must return an empty list rather than raising."""
    import op3_viz.dlc_loader as dl
    monkeypatch.setattr(dl, "DLC_ROOT", tmp_path / "absent")
    assert dl.discover_runs() == []


def test_discover_runs_empty_sweep(monkeypatch, tmp_path):
    import op3_viz.dlc_loader as dl
    sweep = tmp_path / "20260101_000000"
    sweep.mkdir()
    monkeypatch.setattr(dl, "DLC_ROOT", tmp_path)
    assert dl.discover_runs() == []


def test_figure_dlc_no_path_returns_empty_state():
    from op3_viz.dlc_loader import figure_dlc
    fig = figure_dlc(None, ["anything"])
    assert isinstance(fig, go.Figure)
    assert "No DLC run selected" in (fig.layout.title.text or "")


def test_figure_dlc_bad_path_graceful():
    from op3_viz.dlc_loader import figure_dlc
    fig = figure_dlc("/nonexistent/file.outb", ["x"])
    assert isinstance(fig, go.Figure)
    title = (fig.layout.title.text or "").lower()
    # Either a reader error card or no-data card, both acceptable
    assert "error" in title or "no dlc" in title or title == ""


def test_available_channels_bad_path():
    from op3_viz.dlc_loader import available_channels
    assert available_channels("/nonexistent/file.outb") == []
