"""
NREL 5MW OC3 Phase I monopile -- model builder.

Instantiates the model via the new :mod:`op3.foundations.types` API
and bridges to the legacy :func:`op3.composer.compose_tower_model`
pipeline so the eigen / pushover / transient analyses work unchanged.

Two public entry points:

- :func:`build_monopile` — returns a configured ``Monopile`` ready
  for head-stiffness queries.
- :func:`build_tower_model` — returns a legacy ``TowerModel`` wired
  with the Monopile-derived 6x6 head stiffness so the existing
  composer can drive eigen analyses.

Both functions load from the dossier YAMLs (no hidden constants).
SSI defaults to :class:`op3.ssi.Stiffness6x6.rigid` (fixed-base) —
this reproduces the NREL 5MW onshore tower behaviour at the
monopile's top elevation and is the most reproducible configuration
for PR #1. Calibrated SSI (PISA with OC3 soil) is future work.
"""
from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Optional

from op3.foundations.types import Monopile

if TYPE_CHECKING:  # pragma: no cover
    from op3.composer import TowerModel
    from op3.ssi.base import SSIProtocol


DOSSIER_DIR: Path = Path(__file__).resolve().parent


def build_monopile(ssi: Optional["SSIProtocol"] = None) -> Monopile:
    """Instantiate the OC3 monopile with its dossier geometry / soil.

    Parameters
    ----------
    ssi : SSIProtocol, optional
        SSI fidelity strategy. Defaults to
        :meth:`op3.ssi.Stiffness6x6.rigid` (fixed-base; the most
        reproducible configuration for PR #1).
    """
    if ssi is None:
        from op3.ssi import Stiffness6x6

        ssi = Stiffness6x6.rigid()

    monopile = Monopile.from_yaml(DOSSIER_DIR)
    monopile.with_ssi(ssi)
    return monopile


def build_tower_model(ssi: Optional["SSIProtocol"] = None) -> "TowerModel":
    """Build a legacy ``TowerModel`` wired with the OC3 monopile SSI.

    The function goes through ``Monopile.as_legacy_foundation()`` so
    the existing :func:`op3.composer.compose_tower_model` pipeline
    (tower template, RNA placement, eigen / pushover analyses) is
    reused unchanged.

    The legacy :func:`op3.foundations.build_foundation` emits a
    ``DeprecationWarning`` when called; ``as_legacy_foundation()``
    constructs the ``Foundation`` dataclass directly, so no
    deprecation noise is produced by this code path.
    """
    from op3.composer import compose_tower_model

    monopile = build_monopile(ssi)
    legacy_foundation = monopile.as_legacy_foundation()
    return compose_tower_model(
        rotor="nrel_5mw_baseline",
        tower="nrel_5mw_oc3_tower",
        foundation=legacy_foundation,
    )
