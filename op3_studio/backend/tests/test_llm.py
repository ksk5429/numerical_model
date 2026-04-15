"""Phase-5 tests: code extraction + sandbox isolation + endpoint guard.

These tests intentionally do NOT call the Anthropic API. The chat
round-trip is covered by an integration test the user runs locally
when ANTHROPIC_API_KEY is set.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.services.llm_service import (
    extract_op3_code, safe_execute, _build_sandbox_globals,
    LLMService,
)


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


# ---------------------------------------------------------------------------
# Code extraction
# ---------------------------------------------------------------------------

class TestExtraction:

    def test_no_blocks(self):
        assert extract_op3_code("just text, no code") == []

    def test_single_block(self):
        text = "Here we go:\n```op3\nx = 1 + 1\nprint(x)\n```\nDone."
        blocks = extract_op3_code(text)
        assert len(blocks) == 1
        assert "x = 1 + 1" in blocks[0]

    def test_multiple_blocks(self):
        text = (
            "Step 1:\n```op3\na = 1\n```\n"
            "Step 2:\n```op3\nb = 2\n```"
        )
        blocks = extract_op3_code(text)
        assert blocks == ["a = 1", "b = 2"]

    def test_python_block_ignored(self):
        text = "```python\nx = 1\n```"
        assert extract_op3_code(text) == []


# ---------------------------------------------------------------------------
# Sandbox
# ---------------------------------------------------------------------------

class TestSandbox:

    def test_simple_arithmetic(self):
        r = safe_execute("y = 2 + 3")
        assert r.success
        assert r.results["y"] == 5

    def test_print_captured(self):
        r = safe_execute("print('hello world')")
        assert r.success
        assert "hello world" in r.stdout

    def test_op3_anchors_available(self):
        r = safe_execute(
            "from op3.anchors import SuctionAnchor\n"
            "a = SuctionAnchor(diameter_m=5.0, skirt_length_m=15.0)\n"
            "ar = a.aspect_ratio\n"
        )
        assert r.success, r.error
        assert r.results["ar"] == 3.0

    def test_disallowed_import_blocked(self):
        r = safe_execute("import os\nx = os.listdir('.')")
        assert not r.success
        assert r.error_type == "ImportError"

    def test_disallowed_subprocess_blocked(self):
        r = safe_execute("import subprocess")
        assert not r.success
        assert r.error_type == "ImportError"

    def test_open_file_blocked(self):
        # 'open' is not in the safe builtins
        r = safe_execute("f = open('test.txt', 'w')")
        assert not r.success

    def test_timeout(self, monkeypatch):
        """Verify the TimeoutError path without spawning an unkillable
        worker. We monkeypatch _exec_in_sandbox to block on an event so
        the daemon worker exits cleanly when the test ends."""
        import threading
        from backend.services import llm_service as ls
        block = threading.Event()

        def slow_exec(code):
            block.wait()  # interpreter-level wait, releases GIL
            return ls.ExecutionResult(success=True)

        monkeypatch.setattr(ls, "_exec_in_sandbox", slow_exec)
        try:
            r = safe_execute("# whatever", timeout_s=1)
            assert not r.success
            assert r.error_type == "TimeoutError"
        finally:
            block.set()

    def test_real_dnv_capacity_round_trip(self):
        """Sandbox + real op3.anchors -- end-to-end."""
        r = safe_execute(
            "from op3.anchors import (SuctionAnchor, "
            "UndrainedClayProfile, anchor_capacity)\n"
            "a = SuctionAnchor(diameter_m=5.0, skirt_length_m=15.0,\n"
            "                  padeye_depth_m=10.0)\n"
            "s = UndrainedClayProfile(su_mudline_kPa=5.0,\n"
            "                         su_gradient_kPa_per_m=1.5)\n"
            "rr = anchor_capacity(a, s, method='dnv_rp_e303',\n"
            "                     load_angle_deg=30.0)\n"
            "H = rr.H_ult_kN\nV = rr.V_ult_kN\nT = rr.T_ult_kN\n"
        )
        assert r.success, r.error
        assert r.results["H"] > 0
        assert r.results["V"] > 0
        assert r.results["T"] > 0


# ---------------------------------------------------------------------------
# /api/chat/message guard
# ---------------------------------------------------------------------------

class TestChatEndpoint:

    def test_503_when_no_api_key(self, client, monkeypatch):
        from backend import config as cfg_mod
        monkeypatch.setattr(cfg_mod.settings, "anthropic_api_key", None)
        r = client.post("/api/chat/message", json={
            "message": "hi", "conversation_history": [],
            "project_state": {},
        })
        assert r.status_code == 503
        assert "ANTHROPIC_API_KEY" in r.json()["detail"]

    def test_chat_info_does_not_leak_key(self, client, monkeypatch):
        from backend import config as cfg_mod
        monkeypatch.setattr(cfg_mod.settings, "anthropic_api_key",
                            "sk-ant-secret-fake")
        r = client.get("/api/chat/info")
        body = r.json()
        # Endpoint must report availability as a boolean only.
        assert body["available"] is True
        assert "sk-ant-secret-fake" not in str(body)


class TestServiceConstruction:

    def test_available_false_without_key(self):
        s = LLMService(api_key=None)
        assert s.available is False

    def test_chat_raises_without_key(self):
        s = LLMService(api_key=None)
        with pytest.raises(RuntimeError, match="ANTHROPIC_API_KEY"):
            s.chat("hi", [], {})
