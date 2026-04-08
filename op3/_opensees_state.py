"""
OpenSees domain / analysis state context manager (Task 16).

OpenSeesPy uses a process-global state for the model domain and the
current analysis. Tests and scripts frequently need to:

  1. Build a model
  2. Run one analysis (eigen / static / transient)
  3. Run a different analysis without leftover state

The `ops.wipeAnalysis()` + re-setup pattern is error-prone because
forgetting a step leaves a stale solver configuration that breaks
subsequent calls with cryptic messages like "can't set handler after
analysis is created".

This module provides a `with` context manager that guarantees clean
enter/exit for any OpenSees analysis scope.
"""
from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator


@contextmanager
def analysis(kind: str = "static",
             system: str = "BandGeneral",
             numberer: str = "RCM",
             constraints: str = "Plain") -> Iterator[None]:
    """
    Scoped OpenSees analysis state.

    Usage
    -----
    >>> from op3._opensees_state import analysis
    >>> with analysis("static"):
    ...     ops.analyze(1)

    Parameters
    ----------
    kind
        One of "static", "transient", or "eigen". "eigen" does not
        set up an analysis object -- it just ensures the domain is
        clean so that `ops.eigen(...)` can be called directly.
    system
        Linear system solver ("BandGeneral", "UmfPack", "ProfileSPD").
    numberer
        Equation numberer ("RCM", "Plain").
    constraints
        Constraint handler ("Plain", "Transformation", "Penalty",
        "Lagrange").
    """
    import openseespy.opensees as ops

    try:
        ops.wipeAnalysis()
    except Exception:
        pass

    if kind == "eigen":
        yield
        return

    ops.system(system)
    ops.numberer(numberer)
    ops.constraints(constraints)
    ops.algorithm("Linear")

    if kind == "static":
        ops.integrator("LoadControl", 1.0)
        ops.analysis("Static")
    elif kind == "transient":
        ops.integrator("Newmark", 0.5, 0.25)
        ops.analysis("Transient")
    else:
        raise ValueError(f"unknown analysis kind: {kind}")

    try:
        yield
    finally:
        try:
            ops.wipeAnalysis()
        except Exception:
            pass
