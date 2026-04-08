"""
Op^3 OpenSeesPy foundation module implementations.

This subpackage contains the actual OpenSeesPy commands that instantiate
the four foundation modes. It is imported lazily by `op3.foundations`
and `op3.composer` so that the rest of Op^3 can be used as a data
structure library even if OpenSeesPy is not installed.

Each foundation mode is one public function:

    attach_foundation(foundation, base_node)   -- dispatch by mode
    _attach_fixed(base_node)                   -- Mode A
    _attach_stiffness_6x6(K, base_node)        -- Mode B
    _attach_distributed_bnwf(table, ...)       -- Mode C
    _attach_dissipation_weighted(...)          -- Mode D

Plus helpers:

    build_opensees_model(tower_model)          -- composer entry point
    run_eigen_analysis(tower_model, n_modes)
    run_static_condensation(tower_model)       -- returns 6x6 K at base

The tower templates are instantiated by `op3.opensees_foundations.templates`.
"""
from op3.opensees_foundations.builder import (
    attach_foundation,
    build_opensees_model,
    run_eigen_analysis,
    run_static_condensation,
)

__all__ = [
    "attach_foundation",
    "build_opensees_model",
    "run_eigen_analysis",
    "run_static_condensation",
]
