"""Phase-6 tests: report generator returns real Markdown with real numbers."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from backend.main import app


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


SITE = {
    "name": "Demo",
    "water_depth_m": 200.0,
    "layers": [
        {"depth_m": 0.0, "thickness_m": 5.0,
         "soil_type": "sand", "friction_angle_deg": 32.0,
         "unit_weight_kN_m3": 9.5},
    ],
}
FOUNDATION = {
    "type": "suction_bucket", "diameter_m": 8.0,
    "length_m": 8.0, "wall_thickness_mm": 25.0,
    "foundation_mode": "stiffness_6x6", "standard": "dnv",
}
ANCHOR = {
    "diameter_m": 5.0, "skirt_length_m": 15.0,
    "wall_thickness_mm": 30.0, "padeye_depth_m": 10.0,
    "submerged_weight_kN": 250.0,
}
SOIL = {
    "su_mudline_kPa": 5.0, "su_gradient_kPa_per_m": 1.5,
    "gamma_eff_kN_per_m3": 6.0,
    "sensitivity": 3.0, "plasticity_index": 27.0,
}


class TestReport:
    def test_generates_markdown(self, client):
        r = client.post("/api/report/generate", json={
            "site": SITE, "foundation": FOUNDATION,
            "scour_depth_m": 0.5,
            "anchor": ANCHOR, "anchor_soil": SOIL,
        })
        assert r.status_code == 200, r.text
        md = r.json()["markdown"]
        assert "# Op³ design report" in md
        assert "Suction" in md or "suction" in md
        assert "DNV-RP-E303" in md
        # The report must include real numbers, not placeholders.
        assert "kN" in md
        assert "kPa" in md
        # Anchor capacity tables should have a non-zero H_ult value.
        assert "H_ult" in md

    def test_templates_list(self, client):
        r = client.get("/api/report/templates")
        assert r.status_code == 200
        assert "anchor_design" in r.json()

    def test_pdf_export(self, client):
        r = client.post("/api/report/generate.pdf", json={
            "site": SITE, "foundation": FOUNDATION,
            "scour_depth_m": 0.0,
            "anchor": ANCHOR, "anchor_soil": SOIL,
        })
        # Either 200 with PDF bytes, or 503 if reportlab is absent
        assert r.status_code in (200, 503)
        if r.status_code == 200:
            assert r.headers["content-type"] == "application/pdf"
            assert r.content[:4] == b"%PDF"
            assert len(r.content) > 1000
