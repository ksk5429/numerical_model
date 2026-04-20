"""
NREL 5MW OC3 Phase I monopile dossier.

See ``site.yaml``, ``geometry.yaml``, ``soil.yaml`` for the model
definition and ``vvc.yaml`` for V&V&C status. The ``build`` module
instantiates the model via :mod:`op3.foundations.types.Monopile`.
"""
from __future__ import annotations

from pathlib import Path

#: Directory that holds the dossier YAMLs.
DOSSIER_DIR: Path = Path(__file__).resolve().parent

from op3.models.nrel_5mw_oc3_monopile.build import (  # noqa: E402
    build_monopile,
    build_tower_model,
)

__all__ = [
    "DOSSIER_DIR",
    "build_monopile",
    "build_tower_model",
]
