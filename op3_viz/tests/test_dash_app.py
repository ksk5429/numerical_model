"""Smoke tests for the op3_viz Dash app.

Verifies that create_app() always returns a Dash instance -- with a
full 4-tab layout when the private data tree is available, or a
graceful error card when it is not. Never crashes at import time.
"""
from __future__ import annotations

import pytest
from dash import Dash

from op3_viz.dash_app.app import create_app


def test_create_app_returns_dash_instance():
    app = create_app()
    assert isinstance(app, Dash)
    assert app.layout is not None


def test_create_app_has_non_empty_layout():
    app = create_app()
    # Layout is always a Div with at least one child, even in the
    # error-card branch.
    children = getattr(app.layout, "children", None)
    assert children is not None
    assert len(children) >= 1


def test_create_app_graceful_on_missing_data(monkeypatch, tmp_path):
    """With OP3_PHD_ROOT pointing at an empty directory, create_app
    must return a Dash instance with the error-card layout rather
    than raising."""
    monkeypatch.setenv("OP3_PHD_ROOT", str(tmp_path))
    # Force reimport so cached tower segments reload from the empty tree
    import importlib
    import op3.opensees_foundations.site_a_real_tower as tower_mod
    import op3_viz.geometry as geom_mod
    importlib.reload(tower_mod)
    importlib.reload(geom_mod)
    import op3_viz.dash_app.app as app_mod
    importlib.reload(app_mod)

    app = app_mod.create_app()
    assert isinstance(app, Dash)
    # Error-card layout has exactly 3 children: H2, description Div, Pre
    children = getattr(app.layout, "children", None)
    assert children is not None
    assert len(children) == 3
