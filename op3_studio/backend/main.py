"""Op3 Studio backend entry point.

Boots a FastAPI app that exposes the Op3 framework over REST. The app
is structured around eight routers (one per domain) and a small set
of shared services (Op3 bridge, mesh generator, LLM chat).

Run locally::

    cd op3_studio
    PYTHONPATH=. uvicorn backend.main:app --reload --port 8000

Or via Docker::

    docker compose up backend
"""
from __future__ import annotations

import sys
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Make the parent op3 package importable when running from a checkout
# (in container deployments this is handled by the Dockerfile).
_OP3_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_OP3_ROOT) not in sys.path:
    sys.path.insert(0, str(_OP3_ROOT))

from backend.config import settings  # noqa: E402
from backend.routers import (        # noqa: E402
    site, foundation, anchor, analysis, scour, openfast, report, chat,
)


def _op3_version() -> str:
    """Best-effort import of the Op3 version string."""
    try:
        import op3
        return getattr(op3, "__version__", "unknown")
    except ImportError:
        return "unavailable"


@asynccontextmanager
async def lifespan(app: FastAPI):
    print("[op3-studio] backend starting...")
    print(f"[op3-studio] op3 version : {_op3_version()}")
    print(f"[op3-studio] op3 root    : {settings.op3_root}")
    print(f"[op3-studio] llm model   : {settings.llm_model}")
    print(f"[op3-studio] llm enabled : {bool(settings.anthropic_api_key)}")
    yield
    print("[op3-studio] backend shutting down")


app = FastAPI(
    title="Op3 Studio API",
    description=(
        "REST API for the Op3 offshore foundation analysis framework. "
        "Wraps op3 Python primitives for the React/Three.js Studio UI."
    ),
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(site.router,       prefix="/api/site",       tags=["Site & Soil"])
app.include_router(foundation.router, prefix="/api/foundation", tags=["Foundation"])
app.include_router(anchor.router,     prefix="/api/anchor",     tags=["Anchor"])
app.include_router(analysis.router,   prefix="/api/analysis",   tags=["Analysis"])
app.include_router(scour.router,      prefix="/api/scour",      tags=["Scour"])
app.include_router(openfast.router,   prefix="/api/openfast",   tags=["OpenFAST"])
app.include_router(report.router,     prefix="/api/report",     tags=["Report"])
app.include_router(chat.router,       prefix="/api/chat",       tags=["AI Chat"])


@app.get("/api/health")
def health() -> dict:
    """Liveness probe + version reporting."""
    return {
        "status": "ok",
        "op3_version": _op3_version(),
        "llm_available": bool(settings.anthropic_api_key),
    }


if __name__ == "__main__":  # pragma: no cover
    import uvicorn
    uvicorn.run("backend.main:app",
                host=settings.host, port=settings.port,
                reload=settings.reload)
