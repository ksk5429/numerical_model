"""Phase-3 tests: mesh generator + /mesh endpoints."""
from __future__ import annotations

import numpy as np
import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.services.mesh_generator import (
    generate_suction_bucket_mesh,
    generate_anchor_mesh,
    generate_tripod_mesh,
    _create_cylinder, _create_disc, _create_sphere,
    _stress_to_colors, _compute_catenary,
)


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


# ---------------------------------------------------------------------------
# Primitive geometry
# ---------------------------------------------------------------------------

class TestPrimitives:
    def test_cylinder_vertex_count(self):
        v, f = _create_cylinder(radius=1.0, height=2.0, n_segments=16)
        assert len(v) == 2 * (16 + 1)
        assert len(f) == 2 * 16  # two triangles per segment

    def test_cylinder_radius_obeyed(self):
        v, _ = _create_cylinder(radius=3.0, height=5.0, n_segments=8)
        radii = [np.hypot(p[0], p[2]) for p in v]
        assert max(radii) == pytest.approx(3.0, rel=1e-9)
        assert min(radii) == pytest.approx(3.0, rel=1e-9)

    def test_disc_lies_in_plane(self):
        v, f = _create_disc(radius=2.5, n_segments=16, y_offset=-1.5)
        ys = {p[1] for p in v}
        assert ys == {-1.5}
        assert len(f) == 16

    def test_sphere_vertex_count(self):
        v, _ = _create_sphere(1.0, (0, 0, 0), n_segments=8)
        assert len(v) == 9 * 9


class TestStressColors:
    def test_basic_colors(self):
        cols = _stress_to_colors(np.array([0.0, 0.5, 1.0]),
                                 colormap="viridis")
        assert len(cols) == 3
        for c in cols:
            assert len(c) == 3
            assert all(0.0 <= ch <= 1.0 for ch in c)

    def test_empty_raises(self):
        with pytest.raises(ValueError):
            _stress_to_colors(np.array([]))


class TestCatenary:
    def test_starts_at_anchor(self):
        pts = _compute_catenary((0.0, -10.0, 0.0), 30.0, 50.0)
        assert pts[0] == pytest.approx([0.0, -10.0, 0.0], abs=1e-9)

    def test_ends_above_anchor(self):
        pts = _compute_catenary((0.0, -10.0, 0.0), 30.0, 50.0)
        assert pts[-1][1] > pts[0][1]


# ---------------------------------------------------------------------------
# Public mesh builders
# ---------------------------------------------------------------------------

class TestBucketMesh:
    def test_returns_required_components(self):
        c = generate_suction_bucket_mesh(diameter_m=8.0,
                                         skirt_length_m=8.0,
                                         scour_depth_m=1.0)
        assert {"lid", "skirt_outer", "soil_surface",
                "scour_cavity"}.issubset(c.keys())

    def test_no_cavity_when_no_scour(self):
        c = generate_suction_bucket_mesh(8.0, 8.0, scour_depth_m=0.0)
        assert "scour_cavity" not in c

    def test_stress_profile_produces_colors(self):
        n_seg = 16
        stress = np.linspace(0.0, 100.0, n_seg + 1).tolist()
        c = generate_suction_bucket_mesh(8.0, 8.0,
                                         n_segments=n_seg,
                                         stress_profile=stress)
        assert "colors" in c["skirt_outer"]
        assert len(c["skirt_outer"]["colors"]) == \
               len(c["skirt_outer"]["vertices"])


class TestAnchorMesh:
    def test_components(self):
        c = generate_anchor_mesh(diameter_m=5.0, skirt_length_m=15.0,
                                 padeye_depth_m=10.0,
                                 mooring_angle_deg=35.0)
        assert {"anchor_body", "anchor_lid", "padeye",
                "mooring_line", "soil_surface"}.issubset(c.keys())

    def test_padeye_at_correct_depth(self):
        c = generate_anchor_mesh(5.0, 15.0, padeye_depth_m=10.0,
                                 mooring_angle_deg=30.0)
        ys = [p[1] for p in c["padeye"]["vertices"]]
        assert min(ys) <= -10.0 <= max(ys)

    def test_mooring_line_is_line_type(self):
        c = generate_anchor_mesh(5.0, 15.0, padeye_depth_m=10.0)
        assert c["mooring_line"]["type"] == "line"
        assert len(c["mooring_line"]["points"]) > 10


class TestTripodMesh:
    def test_three_buckets(self):
        c = generate_tripod_mesh(8.0, 8.0, tripod_spacing_m=20.0,
                                 tower_height_m=80.0)
        bucket_keys = [k for k in c if k.startswith("bucket_")]
        assert len(bucket_keys) > 0
        # 3 buckets, each contributes lid + skirt_outer + soil_surface
        assert any("bucket_0" in k for k in c)
        assert any("bucket_1" in k for k in c)
        assert any("bucket_2" in k for k in c)
        assert "tower" in c
        assert "nacelle" in c
        assert "sea_surface" in c


# ---------------------------------------------------------------------------
# /mesh endpoints
# ---------------------------------------------------------------------------

class TestMeshEndpoints:
    def test_foundation_mesh_endpoint(self, client):
        r = client.post("/api/foundation/mesh", json={
            "foundation": {
                "type": "suction_bucket", "diameter_m": 8.0,
                "length_m": 8.0, "wall_thickness_mm": 25.0,
                "foundation_mode": "stiffness_6x6", "standard": "dnv",
            },
            "scour_depth_m": 1.0,
            "n_segments": 16,
        })
        assert r.status_code == 200, r.text
        body = r.json()
        assert "lid" in body["components"]
        assert "scour_cavity" in body["components"]

    def test_anchor_mesh_endpoint(self, client):
        r = client.post("/api/anchor/mesh", json={
            "anchor": {
                "diameter_m": 5.0, "skirt_length_m": 15.0,
                "wall_thickness_mm": 30.0, "padeye_depth_m": 10.0,
            },
            "mooring_angle_deg": 35.0, "mooring_length_m": 50.0,
            "n_segments": 16,
        })
        assert r.status_code == 200, r.text
        body = r.json()
        assert "anchor_body" in body["components"]
        assert body["components"]["mooring_line"]["type"] == "line"

    def test_tripod_mesh_endpoint(self, client):
        r = client.post("/api/foundation/mesh", json={
            "foundation": {
                "type": "tripod", "diameter_m": 8.0,
                "length_m": 8.0, "wall_thickness_mm": 25.0,
                "foundation_mode": "stiffness_6x6", "standard": "dnv",
            },
            "scour_depth_m": 0.0,
            "n_segments": 16,
        })
        assert r.status_code == 200, r.text
        body = r.json()
        assert any(k.startswith("bucket_") for k in body["components"])
