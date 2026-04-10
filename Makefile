.PHONY: help install test lint docs clean viz

help:  ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2}'

install:  ## Install in editable mode with dev dependencies
	pip install -e ".[dev]"

test:  ## Run all tests
	python -m pytest tests/ -v --tb=short

test-fast:  ## Run tests (no slow OpenSeesPy tests)
	python -m pytest tests/ -v --tb=short -k "not OpenSees"

lint:  ## Run ruff linter
	ruff check op3/ tests/
	ruff format --check op3/ tests/

format:  ## Auto-format code
	ruff format op3/ tests/

docs:  ## Build Sphinx documentation
	python -m sphinx -b html docs/sphinx docs/sphinx/_build/html

docs-live:  ## Serve docs with auto-reload
	sphinx-autobuild docs/sphinx docs/sphinx/_build/html --port 8080

validate:  ## Run cross-validation suite
	python validation/cross_validations/run_all_cross_validations.py

viz:  ## Generate all visualization figures
	python scripts/visualize_op3.py
	python scripts/visualize_optumgx_openfast.py
	python -m op3.viz_tier1
	python -m op3.viz_tier2
	python -m op3.viz_tier3

clean:  ## Remove build artifacts
	rm -rf build/ dist/ *.egg-info .pytest_cache __pycache__
	rm -rf docs/sphinx/_build
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -name "*.pyc" -delete 2>/dev/null || true
