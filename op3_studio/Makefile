# Op3 Studio dev commands. From op3_studio/.
.PHONY: dev backend frontend install test test-backend test-frontend clean

# --- Compose ---------------------------------------------------------------

dev:
	docker compose up

down:
	docker compose down

# --- Native (no Docker) ----------------------------------------------------

backend:
	cd backend && PYTHONPATH=$(PWD) PYTHONUTF8=1 \
	  uvicorn backend.main:app --reload --port 8000

frontend:
	cd frontend && npm run dev

# --- Install ---------------------------------------------------------------

install: install-backend install-frontend

install-backend:
	pip install -e ..
	pip install -r backend/requirements.txt

install-frontend:
	cd frontend && npm install

# --- Tests -----------------------------------------------------------------

test: test-backend

test-backend:
	cd .. && PYTHONPATH=op3_studio:. PYTHONUTF8=1 \
	  python -m pytest op3_studio/backend/tests/ -v

# --- Cleanup ---------------------------------------------------------------

clean:
	rm -rf backend/__pycache__ backend/**/__pycache__
	rm -rf frontend/dist frontend/node_modules
