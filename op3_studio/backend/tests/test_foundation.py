"""Phase-2 tests: foundation capacity + scour sweep against real op3."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from backend.main import app


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


SITE = {
    "name": "demo",
    "water_depth_m": 30.0,
    "layers": [
        {"depth_m": 0.0, "thickness_m": 5.0,
         "soil_type": "sand", "friction_angle_deg": 32.0,
         "unit_weight_kN_m3": 9.5},
        {"depth_m": 5.0, "thickness_m": 15.0,
         "soil_type": "sand", "friction_angle_deg": 35.0,
         "unit_weight_kN_m3": 10.0},
    ],
}


def _foundation(type_: str = "monopile", D: float = 6.0, L: float = 30.0) -> dict:
    return {
        "type": type_, "diameter_m": D, "length_m": L,
        "wall_thickness_mm": 60.0,
        "foundation_mode": "stiffness_6x6", "standard": "dnv",
    }


class TestFoundationModes:
    def test_modes_endpoint(self, client):
        r = client.get("/api/foundation/modes")
        assert r.status_code == 200
        assert "dissipation_weighted" in r.json()


class TestCapacity:
    def test_monopile_capacity_returns_positive(self, client):
        r = client.post("/api/foundation/capacity", json={
            "site": SITE,
            "foundation": _foundation("monopile", D=6.0, L=30.0),
            "scour_depth_m": 0.0,
        })
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["horizontal_kN"] > 0
        assert body["vertical_kN"] > 0
        assert body["moment_kNm"] > 0
        assert body["metadata"]["method"].startswith("DNV-ST-0126")

    def test_bucket_uses_bucket_formulation(self, client):
        r = client.post("/api/foundation/capacity", json={
            "site": SITE,
            "foundation": _foundation("suction_bucket", D=8.0, L=8.0),
            "scour_depth_m": 0.0,
        })
        assert r.status_code == 200
        body = r.json()
        assert "bucket" in body["metadata"]["method"].lower()


class TestScourSweep:
    def test_sweep_capacity_decreases_with_scour(self, client):
        r = client.post("/api/scour/sweep", json={
            "site": SITE,
            "foundation": _foundation("monopile", D=6.0, L=30.0),
            "scour_depths_m": [0.0, 1.0, 2.0, 3.0, 4.0],
        })
        assert r.status_code == 200, r.text
        body = r.json()
        # Monopile capacity uses (L - scour) embedment, so capacity
        # should monotonically decrease with scour.
        H = body["H_ult_kN"]
        assert all(H[i + 1] <= H[i] + 1e-6 for i in range(len(H) - 1))
