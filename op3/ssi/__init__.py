"""
Op^3 Soil-Structure-Interaction (SSI) strategies.

This package hosts the FIDELITY axis of the new foundation API:

- :class:`~op3.ssi.base.SSIProtocol` — the strategy contract.
- :class:`~op3.ssi.stiffness_6x6.Stiffness6x6` — pre-computed 6x6.
- :class:`~op3.ssi.pisa.PISA` — PISA-framework depth-function
  stiffness (Burd 2020 / Byrne 2020), wrapping
  :func:`op3.standards.pisa.pisa_pile_stiffness_6x6`.

Future strategies (planned, blueprint-aligned):

- ``BNWFLumped`` — the legacy op³ Mode C lumped path.
- ``BNWFPhysical`` — the v1.1 distributed-skirt builder (wrapping
  :mod:`op3.opensees_foundations.bnwf_distributed`).
- ``CraigBampton`` — retained-mode reduction via
  :mod:`op3.openfast_coupling.craig_bampton`.

Each strategy is a small object implementing
:class:`~op3.ssi.base.SSIProtocol`. A foundation type composes itself
with a strategy via ``foundation.with_ssi(strategy)``; the strategy is
responsible for computing the 6x6 head stiffness and (optionally)
building topology-specific OpenSees elements.
"""
from __future__ import annotations

from op3.ssi.base import SSIProtocol
from op3.ssi.stiffness_6x6 import Stiffness6x6

# PISA strategy is optional (depends on op3.standards.pisa availability).
try:
    from op3.ssi.pisa import PISA
except ImportError:  # pragma: no cover
    PISA = None  # type: ignore

__all__ = [
    "SSIProtocol",
    "Stiffness6x6",
    "PISA",
]
