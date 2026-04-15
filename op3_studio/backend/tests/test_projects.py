"""Tests for project save/load endpoints."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.services import project_store


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture(autouse=True)
def isolate_projects(tmp_path, monkeypatch):
    """Redirect the projects directory to a per-test tmpdir."""
    monkeypatch.setattr(project_store, "PROJECTS_DIR", tmp_path)
    yield


PAYLOAD = {
    "site": {"name": "demo", "water_depth_m": 30.0, "layers": []},
    "foundation": {"type": "suction_bucket", "diameter_m": 8.0,
                   "length_m": 8.0},
    "scour_depth_m": 1.0,
}


class TestProjectPersistence:

    def test_round_trip(self, client):
        r = client.post("/api/site/save?name=demo", json=PAYLOAD)
        assert r.status_code == 200, r.text
        meta = r.json()
        assert meta["name"] == "demo"

        r = client.get("/api/site/load", params={"name": "demo"})
        assert r.status_code == 200
        loaded = r.json()
        assert loaded["site"]["water_depth_m"] == 30.0
        assert loaded["_name"] == "demo"
        assert "_saved_at" in loaded

    def test_list_after_save(self, client):
        client.post("/api/site/save?name=alpha", json=PAYLOAD)
        client.post("/api/site/save?name=beta", json=PAYLOAD)
        r = client.get("/api/site/list")
        assert r.status_code == 200
        names = [p["name"] for p in r.json()]
        assert "alpha" in names and "beta" in names

    def test_load_missing(self, client):
        r = client.get("/api/site/load", params={"name": "nope"})
        assert r.status_code == 404

    def test_path_traversal_rejected(self, client):
        r = client.post("/api/site/save?name=../escape", json=PAYLOAD)
        assert r.status_code == 400

    def test_long_name_rejected(self, client):
        r = client.post(f"/api/site/save?name={'x' * 100}", json=PAYLOAD)
        assert r.status_code == 400

    def test_delete(self, client):
        client.post("/api/site/save?name=zap", json=PAYLOAD)
        r = client.delete("/api/site/delete", params={"name": "zap"})
        assert r.status_code == 200
        r = client.get("/api/site/load", params={"name": "zap"})
        assert r.status_code == 404
