"""Phase-1 smoke tests: backend boots, health endpoint, all routers mount."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from backend.main import app


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def test_health_returns_ok(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert "op3_version" in body
    assert isinstance(body["llm_available"], bool)


def test_openapi_docs_available(client):
    r = client.get("/openapi.json")
    assert r.status_code == 200
    spec = r.json()
    assert spec["info"]["title"] == "Op3 Studio API"


@pytest.mark.parametrize("path", [
    "/api/site/list",
    "/api/foundation/modes",
    "/api/anchor/methods",
    "/api/analysis/jobs",
    "/api/scour/range",
    "/api/openfast/decks",
    "/api/report/templates",
    "/api/chat/info",
])
def test_router_mounted(client, path):
    """Every router answers its trivial GET endpoint."""
    r = client.get(path)
    assert r.status_code == 200, f"{path} returned {r.status_code}"


def test_chat_info_does_not_leak_key(client):
    r = client.get("/api/chat/info")
    body = r.json()
    assert "api_key" not in body
    assert "anthropic_api_key" not in body
    assert "ANTHROPIC_API_KEY" not in str(body)
