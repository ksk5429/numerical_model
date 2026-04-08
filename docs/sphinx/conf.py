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


# -- Project information -----------------------------------------------------

project = "Op^3"
author = "Kim Kyeong Sun (Seoul National University)"
copyright = "2026, Kim Kyeong Sun"
release = "0.3.0"
version = "0.3"


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
    "python": ("https://docs.python.org/3", None),
    "numpy":  ("https://numpy.org/doc/stable/", None),
    "scipy":  ("https://docs.scipy.org/doc/scipy/", None),
}

todo_include_todos = True

templates_path = ["_templates"]
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]


# -- HTML output -------------------------------------------------------------

html_theme = "alabaster"
html_static_path = ["_static"]
html_title = "Op^3 -- OptumGX-OpenSeesPy-OpenFAST integration framework"
html_short_title = "Op^3"
