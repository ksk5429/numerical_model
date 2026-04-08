"""
pytest conftest for Op^3 (Task 13 -- pytest migration shim).

The existing test modules are standalone runners (`python tests/test_x.py`)
that return 0 on success. This conftest lets pytest discover and
execute the same modules without rewriting each one:

    pytest tests/                        # runs all standalone runners
    pytest tests/test_pisa.py -v         # runs just one
    pytest --cov=op3 --cov-report=xml    # coverage in CI

The standalone runners expose a ``main()`` that returns the fail
count; the conftest parametrises a single pytest wrapper over every
such module.

For pytest-native tests (functions prefixed with ``test_``) the
normal pytest discovery still applies on top of this wrapper.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

TESTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TESTS_DIR.parent
sys.path.insert(0, str(REPO_ROOT))

# Standalone runner modules to adapt via pytest
STANDALONE_RUNNERS = [
    "test_code_verification",
    "test_consistency",
    "test_sensitivity",
    "test_extended_vv",
    "test_pisa",
    "test_cyclic_degradation",
    "test_hssmall",
    "test_mode_d",
    "test_openfast_runner",
    "test_backlog_closure",
    "test_uq",
    "test_reproducibility",
]


def _import_runner(name: str):
    path = TESTS_DIR / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="session")
def repo_root() -> Path:
    return REPO_ROOT


@pytest.fixture(autouse=True)
def _ensure_clean_opensees():
    """
    Every Op^3 test that touches OpenSees starts from a clean domain
    because the global ops state leaks across builds. This fixture
    runs before every test and wipes the domain if OpenSeesPy is
    importable.
    """
    try:
        import openseespy.opensees as ops
        ops.wipe()
    except Exception:
        pass
    yield
