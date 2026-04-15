"""Subprocess sandbox worker -- runs untrusted op3 code in an isolated
Python interpreter so the OS can hard-kill runaway code.

Invoked by ``services/llm_service.py`` via ``multiprocessing.Process``.
The worker reads a single ``code`` string + the import-allowlist from
its arguments, sets up the same restricted ``__builtins__`` /
``__import__`` as the in-process sandbox, executes, and returns a
``dict`` payload through a ``multiprocessing.Queue``.

This module is *deliberately* free of any Op3 / FastAPI imports at the
top level so it stays cheap to spawn.
"""
from __future__ import annotations

import io
import sys
from contextlib import redirect_stdout
from typing import Any


_SAFE_BUILTINS_BASE: dict[str, Any] = {
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


def _make_restricted_import(allowed_top: set[str]):
    def _restricted_import(name, globals=None, locals=None,
                           fromlist=(), level=0):
        if name.split(".")[0] not in allowed_top:
            raise ImportError(
                f"Import of '{name}' is not allowed in the sandbox."
            )
        return __import__(name, globals, locals, fromlist, level)
    return _restricted_import


def _summarise_value(val: Any) -> Any:
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


def run(queue, code: str, allowed_imports: tuple[str, ...]) -> None:
    """Worker entry point. Puts a result dict on ``queue`` then exits."""
    allowed_top = {n.split(".")[0] for n in allowed_imports}
    safe_builtins = dict(_SAFE_BUILTINS_BASE)
    safe_builtins["__import__"] = _make_restricted_import(allowed_top)
    g: dict[str, Any] = {"__builtins__": safe_builtins}

    # Pre-import safe modules.
    import math
    g["math"] = math
    try:
        import numpy as np
        g["np"] = np
        g["numpy"] = np
    except ImportError:
        pass
    try:
        import pandas as pd
        g["pd"] = pd
        g["pandas"] = pd
    except ImportError:
        pass
    try:
        import op3
        g["op3"] = op3
    except ImportError:
        pass

    buf = io.StringIO()
    try:
        with redirect_stdout(buf):
            exec(code, g)
    except Exception as e:
        queue.put({
            "success": False,
            "stdout": buf.getvalue(),
            "results": {},
            "error": str(e),
            "error_type": type(e).__name__,
        })
        return

    skip = {"__builtins__", "math", "np", "numpy", "pd", "pandas", "op3"}
    results = {k: _summarise_value(v) for k, v in g.items()
               if not k.startswith("_") and k not in skip}
    queue.put({
        "success": True,
        "stdout": buf.getvalue(),
        "results": results,
        "error": None,
        "error_type": None,
    })


if __name__ == "__main__":  # pragma: no cover
    # Allow direct CLI use for debugging
    import argparse
    import multiprocessing as mp
    parser = argparse.ArgumentParser()
    parser.add_argument("code")
    args = parser.parse_args()
    q = mp.Queue()
    run(q, args.code, ("op3", "numpy", "pandas", "math"))
    print(q.get())
    sys.exit(0)
