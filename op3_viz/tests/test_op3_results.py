"""Tests for op3_viz.op3_results adapters.

These adapters load real Op^3 artefacts at runtime (OpenSeesPy eigen
run, private OptumGX spring_params CSV, section_properties table) and
map them onto mesh vertex intensities. Without the private data tree,
they must raise cleanly rather than return synthetic values.
"""
from __future__ import annotations

import numpy as np
import pytest

from op3_viz.geometry import build_tripod_bucket


# -------------------------------------------------------------
# real_dissipation_weight_on_tripod
# -------------------------------------------------------------

def test_dissipation_loader_raises_without_private_data(monkeypatch, tmp_path):
    """Without the private OptumGX spring-params CSV, the dissipation
    adapter must raise rather than return a synthetic profile."""
    monkeypatch.setenv("OP3_PHD_ROOT", str(tmp_path))

    import importlib
    import op3.data_sources as ds
    importlib.reload(ds)
    import op3_viz.op3_results as op3r
    importlib.reload(op3r)

    tripod = build_tripod_bucket(bucket_L=6.0)
    with pytest.raises(Exception):
        # Either FileNotFoundError or RuntimeError -- the important
        # invariant is that it does not silently return a mesh-sized
        # array of zeros or analytical values.
        op3r.real_dissipation_weight_on_tripod(tripod)


# -------------------------------------------------------------
# bending_stress_proxy
# -------------------------------------------------------------

def test_bending_stress_raises_without_private_tower(monkeypatch, tmp_path):
    """Without the private tower CSV, the stress proxy cannot
    evaluate sigma(z) = M c / I and must raise."""
    monkeypatch.setenv("OP3_PHD_ROOT", str(tmp_path))

    import importlib
    import op3.data_sources as ds
    importlib.reload(ds)
    import op3.opensees_foundations.site_a_real_tower as tower_mod
    importlib.reload(tower_mod)
    import op3_viz.op3_results as op3r
    importlib.reload(op3r)

    # Construct a throwaway mesh with a few points
    from op3_viz.geometry import Mesh
    z = np.linspace(0.0, 100.0, 10)
    mesh = Mesh(
        x=np.zeros_like(z), y=np.zeros_like(z), z=z,
        i=np.array([0, 1]), j=np.array([1, 2]), k=np.array([2, 3]),
    )
    with pytest.raises(RuntimeError, match="tower segment CSV not found"):
        op3r.bending_stress_proxy(mesh)


# -------------------------------------------------------------
# _interp_on_z helper (pure numeric)
# -------------------------------------------------------------

def test_interp_on_z_monotonic_profile():
    """Interpolation helper should honour the input profile without
    any hallucinated defaults, clipping at the endpoints."""
    from op3_viz.geometry import Mesh
    from op3_viz.op3_results import _interp_on_z

    # Mesh at z = [0, 2, 4, 6, 8, 10]
    z = np.array([0.0, 2.0, 4.0, 6.0, 8.0, 10.0])
    mesh = Mesh(
        x=np.zeros_like(z), y=np.zeros_like(z), z=z,
        i=np.array([0]), j=np.array([1]), k=np.array([2]),
    )
    # Profile from 1..9 linear
    z_ref = np.array([1.0, 9.0])
    v_ref = np.array([10.0, 90.0])
    out = _interp_on_z(mesh, z_ref, v_ref)

    # z=0 clips to left (v=10); z=10 clips to right (v=90);
    # interior linearly interpolated
    assert out[0] == pytest.approx(10.0)
    assert out[-1] == pytest.approx(90.0)
    assert out[2] == pytest.approx(40.0)  # z=4 -> (4-1)/(9-1)*80 + 10 = 40
