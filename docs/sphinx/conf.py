"""
Sphinx configuration for Op^3 -- Phase 7 / Task 7.1.

Build with:
    sphinx-build -b html docs/sphinx docs/sphinx/_build/html

The conf is intentionally minimal so that fresh clones can build
without extra dependencies. Autodoc pulls docstrings directly from
the op3 package.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

# Make the op3 package importable for autodoc
REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

# Mock heavy / platform-specific imports so autodoc works on ReadTheDocs'
# Ubuntu runner without pulling in openseespy (no manylinux wheels).
autodoc_mock_imports = [
    "openseespy",
    "openseespy.opensees",
    "opsvis",
    "openfast_io",
    "openfast_io.FAST_output_reader",
    "rainflow",
    "fatpack",
    "pcrunch",
    "welib",
    "torch",
]


# -- Project information -----------------------------------------------------

project = "Op^3 -- Integrated Numerical and Digital Twin Framework"
author = "Kim Kyeong Sun (Seoul National University)"
copyright = "2026, Kim Kyeong Sun"
release = "1.0.0-rc2"
version = "1.0.0-rc2"


# -- General configuration ---------------------------------------------------

extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.autosummary",
    "sphinx.ext.napoleon",       # Google / NumPy docstrings
    "sphinx.ext.mathjax",        # math rendering
    "sphinx.ext.viewcode",       # source links
    "sphinx.ext.intersphinx",    # cross-link to numpy / scipy
    "sphinx.ext.todo",
]
# Optional: nbsphinx renders the tutorial notebooks as HTML pages.
# Only enabled if BOTH nbsphinx is importable AND pandoc is on PATH
# (nbsphinx shells out to pandoc at build time). On developer machines
# without pandoc the extension is silently disabled so the rest of
# the build still succeeds.
import shutil as _shutil
try:
    import nbsphinx  # noqa: F401
    if _shutil.which("pandoc") is not None:
        extensions.append("nbsphinx")
        nbsphinx_execute = "never"
        nbsphinx_allow_errors = True
    else:
        # Exclude tutorial notebooks from the build when pandoc is missing
        exclude_patterns_notebooks = ["tutorials/*.ipynb"]
except ImportError:
    exclude_patterns_notebooks = ["tutorials/*.ipynb"]

autosummary_generate = True
autodoc_default_options = {
    "members": True,
    "undoc-members": False,
    "show-inheritance": True,
}
napoleon_google_docstring = True
napoleon_numpy_docstring = True
napoleon_include_init_with_doc = False

intersphinx_mapping = {
    "python":   ("https://docs.python.org/3", None),
    "numpy":    ("https://numpy.org/doc/stable/", None),
    "scipy":    ("https://docs.scipy.org/doc/scipy/", None),
    "pandas":   ("https://pandas.pydata.org/docs/", None),
    "openfast": ("https://openfast.readthedocs.io/en/dev/", None),
}

todo_include_todos = True

# Suppress noisy warnings that are not real documentation issues
suppress_warnings = [
    "epub.unknown_project_files",  # ePub builder complains about non-HTML
]

templates_path = ["_templates"]
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store", "tutorials/*"]


# -- HTML output -------------------------------------------------------------

# Prefer sphinx_rtd_theme when available (Read the Docs default);
# fall back to alabaster for local dev installs that do not have it.
try:
    import sphinx_rtd_theme  # noqa: F401
    html_theme = "sphinx_rtd_theme"
except ImportError:
    html_theme = "alabaster"
html_static_path = ["_static"]
html_title = "Op^3 -- Integrated Numerical and Digital Twin Framework for Offshore Wind Turbine Foundations"
html_short_title = "Op^3"
