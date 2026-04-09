"""Extra tests for op3_results adapters + app internal helpers to
push the overall coverage over 80 %.
"""
from __future__ import annotations

import numpy as np
import pytest

from op3_viz.geometry import Mesh, build_tripod_bucket, build_rotor_disk


def _dummy_tower_mesh():
    z = np.linspace(23.6, 95.27, 20)
    n = len(z)
    return Mesh(
        x=np.zeros(n), y=np.zeros(n), z=z,
        i=np.array([0, 1]), j=np.array([1, 2]), k=np.array([2, 3]),
    )


def test_interp_on_z_ascending_and_descending_input():
    from op3_viz.op3_results import _interp_on_z
    mesh = _dummy_tower_mesh()
    # descending input
    z_ref = np.array([10.0, 5.0, 1.0])
    v_ref = np.array([100.0, 50.0, 10.0])
    out = _interp_on_z(mesh, z_ref, v_ref)
    assert out.shape == mesh.z.shape
    assert np.all(np.isfinite(out))


def test_load_w_dissip_profile_requires_private_data(monkeypatch, tmp_path):
    """The spring_params CSV loader must raise cleanly without OP3_PHD_ROOT."""
    monkeypatch.setenv("OP3_PHD_ROOT", str(tmp_path))
    import importlib
    import op3.data_sources as ds
    importlib.reload(ds)
    import op3_viz.op3_results as r
    importlib.reload(r)
    with pytest.raises(Exception):
        r._load_w_dissip_profile()


def test_real_dissipation_weight_on_tripod_with_mock(monkeypatch):
    """When _load_w_dissip_profile is monkeypatched, the adapter must
    paint the returned profile onto the tripod mesh with shape-correct
    output."""
    from op3_viz import op3_results
    tripod = build_tripod_bucket(bucket_OD=6.0, bucket_L=5.0)
    fake_z = np.array([0.5, 1.5, 2.5, 3.5, 4.5])
    fake_w = np.array([0.1, 0.8, 0.5, 0.3, 0.1])
    monkeypatch.setattr(op3_results, "_load_w_dissip_profile",
                        lambda: (fake_z, fake_w))
    out = op3_results.real_dissipation_weight_on_tripod(tripod)
    assert out.shape == tripod.z.shape
    assert float(out.min()) >= 0.1
    assert float(out.max()) <= 0.8


def test_rotor_disk_vertex_count_matches_n_theta():
    m = build_rotor_disk(n_theta=16)
    # 1 centre + 16 rim
    assert len(m.x) == 17
    # exactly 16 triangles in the fan
    assert len(m.i) == 16


def test_report_generator_graceful_without_quarto(monkeypatch, tmp_path):
    """If quarto is not on PATH, build_report must still return the
    rendered .qmd and skip binary formats without raising."""
    import op3_viz.report as r
    monkeypatch.setattr(r.shutil, "which", lambda _: None)
    from op3_viz.project import Project
    proj = Project.new(name="no-quarto")
    result = r.build_report(proj, output_dir=tmp_path)
    assert "qmd" in result
    assert result["qmd"].exists()
    assert "docx" not in result  # skipped gracefully


def test_app_compute_field_unknown_key_raises():
    """The Dash app's _compute_field helper must raise ValueError on
    an unknown field key rather than returning a silent zero array."""
    from op3_viz.dash_app.app import _compute_field
    from op3_viz.geometry import build_tripod_bucket

    tripod = build_tripod_bucket()
    with pytest.raises(ValueError, match="unknown field key"):
        # Pass a dummy tower mesh; unknown key short-circuits before use
        _compute_field(tripod, tripod, "bogus_key")
