"""
Gunsan 4.2 MW OWT tripod suction bucket dossier.

See ``site.yaml``, ``geometry.yaml``, ``soil.yaml`` for the model
definition and ``vvc.yaml`` for V&V&C status. The ``build`` module
instantiates the model via :mod:`op3.foundations.types.Tripod`.
"""
from __future__ import annotations

from pathlib import Path

#: Directory that holds the dossier YAMLs.
DOSSIER_DIR: Path = Path(__file__).resolve().parent

from op3.models.gunsan_4mw_tripod.build import (  # noqa: E402
    LID_STIFFNESS_CSV,
    SCOUR_K_MASTER_CSV,
    SCOUR_K_SMOOTHED_CSV,
    build_tower_model,
    build_tripod,
)

__all__ = [
    "DOSSIER_DIR",
    "LID_STIFFNESS_CSV",
    "SCOUR_K_MASTER_CSV",
    "SCOUR_K_SMOOTHED_CSV",
    "build_tower_model",
    "build_tripod",
]
