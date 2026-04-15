"""Phase-2 tests: anchor capacity, installation, and padeye optimisation."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from backend.main import app


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


ANCHOR = {
    "diameter_m": 5.0, "skirt_length_m": 15.0,
    "wall_thickness_mm": 30.0,
    "padeye_depth_m": 10.0,
    "submerged_weight_kN": 250.0,
}
SOIL = {
    "su_mudline_kPa": 5.0,
    "su_gradient_kPa_per_m": 1.5,
    "sensitivity": 3.0,
    "plasticity_index": 27.0,
    "gamma_eff_kN_per_m3": 6.0,
}


class TestAnchorCapacity:
    def test_methods_endpoint(self, client):
        r = client.get("/api/anchor/methods")
        assert "dnv_rp_e303" in r.json()

    def test_dnv_capacity_real_op3(self, client):
        r = client.post("/api/anchor/capacity", json={
            "anchor": ANCHOR, "soil": SOIL,
            "method": "dnv_rp_e303", "load_angle_deg": 30.0,
        })
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["method"] == "dnv_rp_e303"
        assert body["H_ult_kN"] > 0
        assert body["V_ult_kN"] > 0
        assert body["T_ult_kN"] > 0
        assert len(body["interaction_envelope"]) >= 30
        assert len(body["depth_profile"]) >= 30

    def test_aubeny_rough_higher_than_smooth(self, client):
        common = dict(anchor=ANCHOR, soil=SOIL,
                      method="aubeny_2003", load_angle_deg=0.0)
        rough = client.post("/api/anchor/capacity",
                            json={**common, "aubeny_interface": "rough"}).json()
        smooth = client.post("/api/anchor/capacity",
                             json={**common, "aubeny_interface": "smooth"}).json()
        assert rough["H_ult_kN"] > smooth["H_ult_kN"]


class TestAnchorInstallation:
    def test_installation_feasibility(self, client):
        r = client.post("/api/anchor/installation", json={
            "anchor": ANCHOR, "soil": SOIL,
            "water_depth_m": 200.0,
        })
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["max_suction_required_kPa"] >= 0
        assert body["max_allowable_suction_kPa"] > 0
        assert isinstance(body["plug_heave_ok"], bool)
        assert isinstance(body["feasible"], bool)
        assert len(body["profile"]) > 0

    def test_zero_water_depth_rejected(self, client):
        r = client.post("/api/anchor/installation", json={
            "anchor": ANCHOR, "soil": SOIL, "water_depth_m": 0.0,
        })
        assert r.status_code == 400


class TestPadeye:
    def test_supachawarote(self, client):
        r = client.post("/api/anchor/optimize-padeye", json={
            "anchor": ANCHOR, "soil": SOIL,
            "method": "supachawarote_2005",
        })
        assert r.status_code == 200, r.text
        body = r.json()
        # L/D=3 with linear su -> 0.73 * 15 = 10.95 m
        assert 0.5 < body["optimal_padeye_over_L"] < 0.85
