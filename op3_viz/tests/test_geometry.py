"""Unit tests for op3_viz.geometry.

These tests do not require a private data tree. They verify that the
pure-geometry builders (tripod, RNA, rotor disk) produce well-formed
manifold meshes with the expected vertex / face counts, and that the
tower builder raises a clear RuntimeError rather than hallucinating
defaults when the private segment CSV is unavailable.
"""
from __future__ import annotations

import numpy as np
import pytest

from op3_viz.geometry import (
    Mesh,
    build_rna,
    build_rotor_disk,
    build_tripod_bucket,
)


# -------------------------------------------------------------
# tripod
# -------------------------------------------------------------

def test_tripod_default_geometry_is_well_formed():
    m = build_tripod_bucket()
    # Duck-type check (pytest reload tests can swap class identity)
    assert hasattr(m, "x") and hasattr(m, "i")
    # 3 buckets x 20 rings x 24 vertices per ring
    assert len(m.x) == 3 * 20 * 24
    assert len(m.y) == len(m.x)
    assert len(m.z) == len(m.x)
    assert len(m.i) == len(m.j) == len(m.k)
    # z lies between -L (default 6 m) and 0 (mudline)
    assert m.z.min() == pytest.approx(-6.0)
    assert m.z.max() == pytest.approx(0.0)
    # All face indices point into the vertex array
    n = len(m.x)
    assert m.i.max() < n and m.j.max() < n and m.k.max() < n
    assert m.i.min() >= 0 and m.j.min() >= 0 and m.k.min() >= 0


def test_tripod_custom_dimensions():
    m = build_tripod_bucket(r_leg=12.5, bucket_OD=9.0, bucket_L=8.0)
    # Vertex count is independent of dims
    assert len(m.x) == 3 * 20 * 24
    # z range matches the requested skirt length
    assert m.z.min() == pytest.approx(-8.0)
    assert m.z.max() == pytest.approx(0.0)
    # Max horizontal radius from origin ~ r_leg + OD/2
    r_horiz = np.sqrt(m.x ** 2 + m.y ** 2)
    assert r_horiz.max() == pytest.approx(12.5 + 4.5, rel=1e-3)


# -------------------------------------------------------------
# RNA
# -------------------------------------------------------------

def test_rna_box_default():
    m = build_rna(z_hub=100.0)
    # 8 box vertices, 12 triangle faces
    assert len(m.x) == 8
    assert len(m.i) == 12
    assert m.z.min() == pytest.approx(100.0)
    assert m.z.max() == pytest.approx(104.0)  # default box height 4 m


# -------------------------------------------------------------
# Rotor disk
# -------------------------------------------------------------

def test_rotor_disk_default():
    m = build_rotor_disk()
    # 1 centre + 48 rim vertices
    assert len(m.x) == 49
    # All 48 triangles share the centre vertex 0
    assert (m.i == 0).all()
    # Disk lies on the y-z plane (x == 0 for every vertex)
    assert np.allclose(m.x, 0.0)


def test_rotor_disk_dimensions():
    m = build_rotor_disk(hub_z=95.0, rotor_D=136.0)
    # z range = hub_z +/- rotor_D/2
    assert m.z.min() == pytest.approx(95.0 - 68.0)
    assert m.z.max() == pytest.approx(95.0 + 68.0)


# -------------------------------------------------------------
# tower loader raises rather than hallucinating
# -------------------------------------------------------------

def test_tower_loader_raises_without_private_data(monkeypatch, tmp_path):
    """When OP3_PHD_ROOT points at an empty dir, section_properties
    must raise a clear RuntimeError -- never return synthetic values."""
    monkeypatch.setenv("OP3_PHD_ROOT", str(tmp_path))
    # Force a fresh import so the cached segments are reloaded
    import importlib
    import op3.opensees_foundations.site_a_real_tower as mod
    importlib.reload(mod)
    with pytest.raises(RuntimeError, match="tower segment CSV not found"):
        mod.section_properties()
