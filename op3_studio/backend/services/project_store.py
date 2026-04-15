"""Server-side project persistence.

Saves a project (site + foundation + scour + anchor + chat history) as
a single JSON file under ``op3_studio/projects/<name>.json``.

The backend is the source of truth so the same project can be opened
from a different browser. No database is used; this is filesystem-only
and intentionally simple.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path

from backend.config import settings


PROJECTS_DIR = settings.op3_root / "op3_studio" / "projects"
_NAME_RE = re.compile(r"^[A-Za-z0-9_\-]{1,64}$")


def _ensure_dir() -> Path:
    PROJECTS_DIR.mkdir(parents=True, exist_ok=True)
    return PROJECTS_DIR


def _path(name: str) -> Path:
    if not _NAME_RE.match(name):
        raise ValueError(
            f"Project name '{name}' invalid; allowed: A-Z a-z 0-9 _ -, "
            f"max 64 chars (path-traversal guard)."
        )
    return _ensure_dir() / f"{name}.json"


def list_projects() -> list[dict]:
    """Return [{name, modified, size_bytes}] sorted by mtime desc."""
    _ensure_dir()
    out = []
    for p in PROJECTS_DIR.glob("*.json"):
        s = p.stat()
        out.append({
            "name": p.stem,
            "modified": datetime.fromtimestamp(s.st_mtime,
                                               tz=timezone.utc).isoformat(),
            "size_bytes": s.st_size,
        })
    out.sort(key=lambda x: x["modified"], reverse=True)
    return out


def save_project(name: str, payload: dict) -> dict:
    p = _path(name)
    payload = dict(payload)  # shallow copy
    payload["_saved_at"] = datetime.now(timezone.utc).isoformat()
    payload["_name"] = name
    p.write_text(json.dumps(payload, indent=2, default=str,
                            ensure_ascii=False), encoding="utf-8")
    return {"name": name, "path": str(p), "size_bytes": p.stat().st_size}


def load_project(name: str) -> dict:
    p = _path(name)
    if not p.exists():
        raise FileNotFoundError(f"No project named '{name}' at {p}")
    return json.loads(p.read_text(encoding="utf-8"))


def delete_project(name: str) -> None:
    p = _path(name)
    if not p.exists():
        raise FileNotFoundError(f"No project named '{name}' at {p}")
    p.unlink()
