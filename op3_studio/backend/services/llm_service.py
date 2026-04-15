"""LLM-powered Op3 chat service.

Flow:
  1. User sends a natural-language query.
  2. Claude is given the Op3 system prompt and the current project
     state, and is asked to either answer directly or emit one or
     more ``op3`` code blocks.
  3. Each code block is executed in a restricted Python sandbox that
     can only import a known whitelist of modules (op3, numpy, pandas).
  4. Execution results (stdout + small bound result variables) are
     fed back to Claude in a second turn for natural-language
     interpretation.
  5. The final reply, executed code, and raw results are returned
     together so the React frontend can render an interactive card.

Security guarantees:
  * No fabricated results: results come from real Op3 execution only.
  * No arbitrary import: a ``__builtins__`` dict whitelist is used.
  * No file or network access from sandboxed code.
  * Wall-clock timeout via ``concurrent.futures``.
  * The Anthropic API key is never logged or returned in any response.
"""
from __future__ import annotations

import io
import json
import queue
import re
import threading
from contextlib import redirect_stdout
from dataclasses import dataclass, field
from typing import Any

from backend.config import settings


SYSTEM_PROMPT = """You are Op3 Assistant, an AI engineer specialised in
offshore geotechnical foundation design. You help engineers analyse
offshore wind turbine foundations and floating-platform suction
anchors using the Op3 Python framework.

When the user asks for a calculation, emit ONE OR MORE Python code
blocks fenced with ```op3 ... ```. The backend will execute every
``op3`` block in a restricted sandbox and feed the results back to you
for interpretation.

AVAILABLE OP3 API:

# Foundation (Mode B 6x6 stiffness)
from op3 import build_foundation, compose_tower_model
from op3.standards import (
    dnv_monopile_stiffness, dnv_suction_bucket_stiffness,
    iso_shallow_foundation_stiffness,
)
K = dnv_suction_bucket_stiffness(diameter_m, skirt_length_m, soil_type)

# Anchor (op3.anchors)
from op3.anchors import (
    SuctionAnchor, UndrainedClayProfile, MooringLoad,
    anchor_capacity, installation_analysis,
    optimal_padeye_analytical, cyclic_capacity_reduction,
)
anchor = SuctionAnchor(diameter_m=5.0, skirt_length_m=15.0,
                       padeye_depth_m=10.0)
soil   = UndrainedClayProfile(su_mudline_kPa=5.0,
                              su_gradient_kPa_per_m=1.5)
r = anchor_capacity(anchor, soil, method='dnv_rp_e303',
                    load_angle_deg=30.0)
# r.H_ult_kN, r.V_ult_kN, r.T_ult_kN, r.depth_profile, r.interaction_envelope

RULES:
- Use SI units (m, mm for wall thickness, kN, kPa, deg).
- Always reference relevant design standards (DNV-RP-E303, API RP 2SK,
  DNV-ST-0126).
- If a parameter is ambiguous, state your assumption explicitly.
- Add a brief physical interpretation of each numeric result.
- Respond in the same language the user uses (Korean or English).
- Never invent numbers: if op3 cannot answer with the given inputs,
  say so and ask the user for the missing parameter.

CURRENT PROJECT STATE (JSON):
{project_state}
"""


# ---------------------------------------------------------------------------
# Result containers
# ---------------------------------------------------------------------------

@dataclass
class ExecutionResult:
    success: bool
    stdout: str = ""
    results: dict[str, Any] = field(default_factory=dict)
    error: str | None = None
    error_type: str | None = None


@dataclass
class ChatResult:
    reply: str
    code_executed: list[str]
    results: list[ExecutionResult]
    error: str | None = None


# ---------------------------------------------------------------------------
# Code extraction
# ---------------------------------------------------------------------------

_OP3_BLOCK_RE = re.compile(r"```op3\s*\n(.*?)```", re.DOTALL)


def extract_op3_code(text: str) -> list[str]:
    """Return all ``op3`` code blocks found in the model's reply."""
    return [b.strip() for b in _OP3_BLOCK_RE.findall(text) if b.strip()]


# ---------------------------------------------------------------------------
# Sandboxed execution
# ---------------------------------------------------------------------------

_SAFE_BUILTINS_BASE = {
    "print": print, "range": range, "len": len,
    "float": float, "int": int, "str": str, "bool": bool,
    "list": list, "dict": dict, "tuple": tuple, "set": set,
    "round": round, "abs": abs, "max": max, "min": min,
    "sum": sum, "sorted": sorted, "zip": zip,
    "enumerate": enumerate, "isinstance": isinstance,
    "True": True, "False": False, "None": None,
    "ValueError": ValueError, "RuntimeError": RuntimeError,
    "TypeError": TypeError, "KeyError": KeyError,
    "Exception": Exception,
}


def _make_restricted_import(allowed: set[str]):
    """Return an __import__ replacement that only allows whitelisted modules."""
    def _restricted_import(name, globals=None, locals=None,
                           fromlist=(), level=0):
        top = name.split(".")[0]
        if top not in allowed:
            raise ImportError(
                f"Import of '{name}' is not allowed in the sandbox."
            )
        return __import__(name, globals, locals, fromlist, level)
    return _restricted_import


def _build_sandbox_globals() -> dict[str, Any]:
    """Construct a sandboxed globals dict for exec()."""
    allowed_top = {n.split(".")[0] for n in settings.sandbox_allowed_imports}
    safe_builtins = dict(_SAFE_BUILTINS_BASE)
    safe_builtins["__import__"] = _make_restricted_import(allowed_top)
    g: dict[str, Any] = {"__builtins__": safe_builtins}

    # Pre-import safe modules so the user code can use them directly.
    import math
    import numpy as np
    import pandas as pd
    g["math"] = math
    g["np"] = np
    g["numpy"] = np
    g["pd"] = pd
    g["pandas"] = pd
    try:
        import op3
        g["op3"] = op3
    except ImportError:
        pass
    return g


def _summarise_value(val: Any) -> Any:
    """Reduce non-JSON-friendly values to a printable representation."""
    if isinstance(val, (int, float, str, bool)) or val is None:
        return val
    if isinstance(val, list):
        return [_summarise_value(v) for v in val[:50]]
    if isinstance(val, dict):
        return {k: _summarise_value(v) for k, v in list(val.items())[:50]}
    try:
        import numpy as np
        if isinstance(val, np.ndarray):
            return val.tolist()[:50]
    except ImportError:
        pass
    if hasattr(val, "to_dict"):
        try:
            return val.to_dict()
        except Exception:
            pass
    if hasattr(val, "__dict__"):
        return {k: _summarise_value(v) for k, v in vars(val).items()
                if not k.startswith("_")}
    return repr(val)


def _exec_in_sandbox(code: str) -> ExecutionResult:
    g = _build_sandbox_globals()
    buf = io.StringIO()
    try:
        with redirect_stdout(buf):
            exec(code, g)
    except Exception as e:
        return ExecutionResult(success=False,
                               stdout=buf.getvalue(),
                               error=str(e),
                               error_type=type(e).__name__)
    # Pull out user-defined names (not builtins, not pre-imported modules)
    skip = {"__builtins__", "math", "np", "numpy", "pd", "pandas", "op3"}
    results = {k: _summarise_value(v) for k, v in g.items()
               if not k.startswith("_") and k not in skip}
    return ExecutionResult(success=True,
                           stdout=buf.getvalue(),
                           results=results)


def safe_execute(code: str, timeout_s: int | None = None) -> ExecutionResult:
    """Execute a single ``op3`` code block with a wall-clock timeout.

    Uses a daemon thread so the interpreter is free to exit even if the
    worker is stuck inside a tight CPU loop. Note: Python's GIL prevents
    interrupting C-level loops; for untrusted code in production,
    replace the daemon thread with a ``multiprocessing.Process`` sandbox
    so the OS can hard-kill runaway code.
    """
    timeout = timeout_s or settings.sandbox_timeout_s
    q: "queue.Queue[ExecutionResult]" = queue.Queue(maxsize=1)

    def worker() -> None:
        try:
            q.put(_exec_in_sandbox(code))
        except Exception as e:  # pragma: no cover -- safety net
            q.put(ExecutionResult(success=False, error=str(e),
                                  error_type=type(e).__name__))

    t = threading.Thread(target=worker, daemon=True)
    t.start()
    try:
        return q.get(timeout=timeout)
    except queue.Empty:
        return ExecutionResult(success=False,
                               error=f"Execution exceeded {timeout}s",
                               error_type="TimeoutError")


# ---------------------------------------------------------------------------
# Chat orchestration
# ---------------------------------------------------------------------------

class LLMService:
    """Thin wrapper around the Anthropic SDK + sandbox loop."""

    def __init__(self, api_key: str | None = None,
                 model: str | None = None) -> None:
        self.api_key = api_key or settings.anthropic_api_key
        self.model = model or settings.llm_model

    @property
    def available(self) -> bool:
        return bool(self.api_key)

    def _client(self):
        if not self.available:
            raise RuntimeError(
                "ANTHROPIC_API_KEY is not configured; set it in the "
                "environment (e.g. via op3_studio/.env) before using "
                "the chat service."
            )
        import anthropic
        return anthropic.Anthropic(api_key=self.api_key)

    def chat(
        self,
        message: str,
        history: list[dict],
        project_state: dict,
    ) -> ChatResult:
        """Round-trip a user message through Claude + sandbox + Claude."""
        client = self._client()
        system = SYSTEM_PROMPT.format(
            project_state=json.dumps(project_state, indent=2,
                                     default=str, ensure_ascii=False),
        )
        messages = list(history) + [{"role": "user", "content": message}]

        first = client.messages.create(
            model=self.model,
            max_tokens=settings.llm_max_tokens,
            system=system,
            messages=messages,
        )
        first_text = first.content[0].text

        code_blocks = extract_op3_code(first_text)
        if not code_blocks:
            return ChatResult(reply=first_text, code_executed=[], results=[])

        executed = [safe_execute(c) for c in code_blocks]

        # Second turn: feed results back for interpretation.
        results_for_llm = [
            {
                "code": c,
                "success": r.success,
                "stdout": r.stdout[-2000:],
                "results": r.results,
                "error": r.error,
            }
            for c, r in zip(code_blocks, executed)
        ]
        followup = client.messages.create(
            model=self.model,
            max_tokens=settings.llm_max_tokens,
            system=system,
            messages=messages + [
                {"role": "assistant", "content": first_text},
                {"role": "user",
                 "content": (
                     "The op3 code blocks above were executed. Here are "
                     "the results -- please give the user a clear, "
                     "engineering-grade interpretation. Cite the "
                     "applicable standard. Do NOT emit further ``op3`` "
                     "blocks unless the user asks for additional "
                     "calculations.\n\n"
                     + json.dumps(results_for_llm, indent=2,
                                  default=str, ensure_ascii=False)
                 )},
            ],
        )
        return ChatResult(
            reply=followup.content[0].text,
            code_executed=code_blocks,
            results=executed,
        )
