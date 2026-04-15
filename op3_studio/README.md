# Op3 Studio

Production GUI for the Op3 offshore foundation analysis framework.
React + Three.js frontend, FastAPI backend, LLM-powered chat that
calls Op3 by natural language.

## Architecture

```
op3_studio/
  backend/        FastAPI server, wraps op3 + op3.anchors via REST
  frontend/       React + TS + Vite, Three.js viewer, Tailwind UI
  docker-compose.yml
  Dockerfile.backend
  Dockerfile.frontend
  Makefile
```

The legacy desktop PyInstaller version is the standalone files
[`../op3_studio_launcher.py`](../op3_studio_launcher.py) and
[`../op3_studio.spec`](../op3_studio.spec); they remain for reference
but are superseded by this web version.

## Quick start (docker)

```bash
cd op3_studio
cp .env.example .env       # add ANTHROPIC_API_KEY for chat
docker compose up
```

Backend: <http://localhost:8000> (OpenAPI: `/docs`)
Frontend: <http://localhost:5173>

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
```

## Roadmap

| Phase | Scope                                                      | Status |
|-------|------------------------------------------------------------|--------|
| 1     | Skeleton: docker, FastAPI health, React shell              | done   |
| 2     | Backend op3 bridge (foundation/anchor/site/scour endpoints) | done   |
| 3     | Three.js viewer + mesh generator                           | done   |
| 4     | Tab UIs (DataTable, PlotPanel, ParamSlider, 8 tabs)        | TODO   |
| 5     | LLM chat (Anthropic + sandbox)                             | done   |
| 6     | Polish / report PDF                                        | TODO   |

## Security

* `ANTHROPIC_API_KEY` is read from environment only; never logged or
  returned by any endpoint (`/api/chat/info` reports availability as
  a boolean only).
* The chat sandbox restricts imports to `op3.*`, `numpy`, `pandas`
  and a whitelist of safe builtins.
* CORS allows only the dev frontend origin by default.
