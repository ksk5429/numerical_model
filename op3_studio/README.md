# Op3 Studio

Production GUI for the Op3 offshore foundation analysis framework.
React + Three.js + Tailwind frontend, FastAPI backend, LLM-powered
chat that calls Op3 by natural language.

## Architecture

```
op3_studio/
  backend/                 FastAPI server, wraps op3 + op3.anchors via REST
    main.py                /api/health + 8 routers
    config.py              env-backed settings (ANTHROPIC_API_KEY, model, sandbox)
    routers/               site, foundation, anchor, analysis, scour,
                           openfast, report, chat
    services/
      op3_service.py       FastAPI ↔ op3 + op3.anchors bridge
      mesh_generator.py    Three.js BufferGeometry from real dimensions
      llm_service.py       Anthropic SDK + sandboxed op3 exec
      report_generator.py  Markdown design report from real op3 calls
    models/schemas.py      18 Pydantic schemas (kept in sync with TS types)
    tests/                 57 pytest tests (FastAPI TestClient)

  frontend/                React 18 + TS + Vite + Three.js + recharts
    src/
      api/                 axios wrappers (client, meshes, analysis, chat)
      stores/projectStore  Zustand global state
      components/
        layout/            Sidebar, Header (live backend / AI status)
        shared/            UnitInput, ParamSlider, PlotPanel, DataTable,
                           LoadingOverlay, ErrorBoundary
        three/SceneManager Three.js viewer (orbit, lighting, sea bobbing,
                           per-vertex stress colormap)
        chat/              ChatPanel, ChatMessage, ChatInput, CodeBlock,
                           ResultCard
        tabs/              Site, Foundation, Anchor, Scour, Analysis,
                           Validation, DigitalTwin, Report
      types/op3.ts         TS counterparts of every Pydantic schema

  Dockerfile.backend       python:3.12-slim + op3 -e + studio reqs
  Dockerfile.frontend      node:20-alpine + vite dev
  docker-compose.yml       backend (8000) + frontend (5173)
  Makefile                 dev / backend / frontend / install / test
```

The legacy desktop PyInstaller version is the standalone files
[`../op3_studio_launcher.py`](../op3_studio_launcher.py) and
[`../op3_studio.spec`](../op3_studio.spec); they remain for reference
but are superseded by this web version.

## Quick start (docker)

```bash
cd op3_studio
cp .env.example .env       # add ANTHROPIC_API_KEY for chat (optional)
docker compose up
```

- Backend: <http://localhost:8000> (OpenAPI: `/docs`)
- Frontend: <http://localhost:5173>

## Quick start (native, no docker)

```bash
make install   # pip install op3 + studio backend, npm install frontend
make backend   # uvicorn on :8000
# in another terminal:
make frontend  # vite on :5173
```

## Tests

```bash
make test
# or directly:
PYTHONPATH=op3_studio:. pytest op3_studio/backend/tests/ -v
```

Current totals: **57 backend tests passing.**

## Features by phase

| Phase | Feature | Status |
|-------|---------|--------|
| 1 | Skeleton: docker, FastAPI health, React shell, 8 router stubs | ✅ |
| 2 | Op3 bridge -- foundation/scour/anchor/installation/padeye endpoints | ✅ |
| 3 | Three.js mesh generator (bucket / anchor / tripod) + viewer | ✅ |
| 4 | 8-tab UI with real plots, editable tables, parameter sliders | ✅ |
| 5 | LLM chat (Anthropic) with sandboxed op3 code execution | ✅ |
| 6 | Markdown report generator + PDF (via pandoc), error boundary | ✅ |

## Live endpoints

| Endpoint | What | Used by |
|---|---|---|
| `GET /api/health` | liveness probe + op3 version | Header |
| `POST /api/foundation/capacity` | DNV-ST-0126 stiffness | FoundationTab |
| `POST /api/foundation/mesh` | bucket / monopile / tripod 3D | SceneManager |
| `POST /api/scour/sweep` | parametric capacity vs scour | ScourTab |
| `POST /api/anchor/capacity` | DNV / Murff / API / Aubeny | AnchorTab |
| `POST /api/anchor/installation` | self-weight + suction + plug-heave | AnchorTab |
| `POST /api/anchor/optimize-padeye` | Supachawarote 2005 z_p* | AnchorTab |
| `POST /api/anchor/mesh` | anchor + catenary 3D | SceneManager |
| `POST /api/report/generate` | Markdown design report | ReportTab |
| `POST /api/chat/message` | Claude + sandboxed op3 exec | ChatPanel |
| `GET /api/chat/info` | model + availability (no key leak) | Header / ChatPanel |

The full OpenAPI spec lives at `/docs` once the backend is running.

## No synthetic data

* All capacity / installation / padeye numbers come from real `op3` /
  `op3.anchors` calls. If `op3` is not importable, the backend
  returns 503 with a clear hint -- it never invents fallback values.
* Mesh data is parametric geometry derived from real dimensions
  (D, L, padeye depth, scour depth). `_stress_to_colors()` requires
  a real stress array and raises `ValueError` on empty input.
* The LLM chat sandbox executes real op3 code; the system prompt
  instructs Claude to ask for missing parameters rather than guess.
* `capacity_fe_calibrated()` (op3.anchors) still raises
  `FileNotFoundError` with an OptumGX-driver hint when its CSV is
  missing -- nothing in Studio bypasses that contract.

## Security

* `ANTHROPIC_API_KEY` is read from environment only; never logged
  or returned by any endpoint. `/api/chat/info` reports availability
  as a boolean only (asserted by `test_chat_info_does_not_leak_key`).
* The chat sandbox restricts imports to `op3.*`, `numpy`, `pandas`,
  and `math` via a custom `__import__` (asserted by
  `test_disallowed_import_blocked`).
* `open()`, `eval()`, `exec()`, `compile()` are not in the sandbox
  builtins (asserted by `test_open_file_blocked`).
* Wall-clock timeout via daemon worker thread; GIL caveat documented
  in `safe_execute()` -- production deployments should swap to a
  `multiprocessing.Process` sandbox.
* CORS allows only the dev frontend origin by default.
* `.env` is gitignored; `.env.example` is the canonical template.
