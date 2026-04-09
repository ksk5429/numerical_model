"""Tests for op3_viz.results_loader — the PHD JSON resolver + figures."""
from __future__ import annotations

import pytest


def test_loader_returns_none_when_phd_root_empty(monkeypatch, tmp_path):
    """When OP3_PHD_ROOT points at an empty directory, _load() must
    return None (callers render an 'empty state' figure) rather than
    raising and crashing the Dash app."""
    monkeypatch.setenv("OP3_PHD_ROOT", str(tmp_path))

    import importlib
    import op3.data_sources as ds
    importlib.reload(ds)
    import op3_viz.results_loader as rl
    importlib.reload(rl)

    assert rl._load("bayes") is None
    assert rl._load("mode_d") is None
    assert rl._load("pce") is None


def test_figure_functions_return_valid_figures_when_empty(monkeypatch, tmp_path):
    """When no data is available, each figure_* function must still
    return a Plotly Figure (with an empty-state title) instead of
    raising."""
    monkeypatch.setenv("OP3_PHD_ROOT", str(tmp_path))

    import importlib
    import op3.data_sources as ds
    importlib.reload(ds)
    import op3_viz.results_loader as rl
    importlib.reload(rl)

    import plotly.graph_objects as go
    for fn_name in ("figure_bayes_scour", "figure_mode_d", "figure_pce"):
        fig = getattr(rl, fn_name)()
        assert isinstance(fig, go.Figure)
        title = (fig.layout.title.text or "").lower()
        assert "not found" in title


def test_figure_bayes_title_contains_headline_when_data_present():
    """When the real Bayesian JSON is available, the title should
    contain the posterior mean, not a generic placeholder. This test
    is skipped if the private data tree is not configured."""
    import op3_viz.results_loader as rl
    fig = rl.figure_bayes_scour()
    title = fig.layout.title.text or ""
    if "not found" in title.lower():
        pytest.skip("PHD data not configured on this machine")
    assert "mean=" in title or "posterior" in title.lower()
