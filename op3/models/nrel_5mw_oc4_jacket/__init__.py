"""
NREL 5MW OC4 Phase I jacket dossier.

See ``site.yaml``, ``geometry.yaml``, ``soil.yaml`` for the model
definition and ``vvc.yaml`` for V&V&C status. The ``build`` module
instantiates the model via :mod:`op3.foundations.types.Jacket`.
"""
from __future__ import annotations

from pathlib import Path

#: Directory that holds the dossier YAMLs.
DOSSIER_DIR: Path = Path(__file__).resolve().parent

from op3.models.nrel_5mw_oc4_jacket.build import (  # noqa: E402
    OC4_K_CSV,
    OC4_SACS_DECK,
    build_jacket,
    build_tower_model,
)

__all__ = [
    "DOSSIER_DIR",
    "OC4_K_CSV",
    "OC4_SACS_DECK",
    "build_jacket",
    "build_tower_model",
]
