"""
NREL 5MW OC4 Phase I jacket -- model builder.

Public entry points:

- :func:`build_jacket` — returns a configured :class:`Jacket` ready
  for head-stiffness queries. Defaults to the SubDyn-condensed CSV
  at ``data/fem_results/K_6x6_oc4_jacket.csv`` as the SSI.
- :func:`build_tower_model` — bridges the jacket to the legacy
  composer pipeline so eigen / pushover analyses work unchanged.

Matches the pattern established by the OC3 monopile dossier (PR #1).
"""
from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Optional

from op3.foundations.types import Jacket

if TYPE_CHECKING:  # pragma: no cover
    from op3.composer import TowerModel
    from op3.ssi.base import SSIProtocol


DOSSIER_DIR: Path = Path(__file__).resolve().parent
REPO_ROOT: Path = DOSSIER_DIR.parents[2]
OC4_K_CSV: Path = REPO_ROOT / "data" / "fem_results" / "K_6x6_oc4_jacket.csv"
OC4_SACS_DECK: Path = (
    REPO_ROOT / "nrel_reference" / "sacs_jackets" / "nrel_oc4" / "NREL_OC4.sacs"
)


def build_jacket(ssi: Optional["SSIProtocol"] = None) -> Jacket:
    """Instantiate the OC4 jacket with its dossier geometry + SACS deck.

    Parameters
    ----------
    ssi : SSIProtocol, optional
        SSI fidelity strategy. Defaults to
        :class:`op3.ssi.Stiffness6x6` loaded from
        ``data/fem_results/K_6x6_oc4_jacket.csv`` — the SubDyn-
        condensed 6x6 produced by OpenFAST v3.x on the OC4 Phase I
        reference jacket. Override with a PISA or custom strategy
        for site-specific work.
    """
    if ssi is None:
        from op3.ssi import Stiffness6x6

        if not OC4_K_CSV.exists():
            raise FileNotFoundError(
                f"OC4 head-stiffness CSV not found at {OC4_K_CSV}. Either "
                "restore the file or pass an explicit ssi= strategy."
            )
        ssi = Stiffness6x6.from_csv(
            str(OC4_K_CSV),
            label="OC4 Phase I SubDyn-condensed K (Popko 2012 configuration)",
        )

    jacket = Jacket.from_yaml(DOSSIER_DIR)
    jacket.with_ssi(ssi)
    return jacket


def build_tower_model(ssi: Optional["SSIProtocol"] = None) -> "TowerModel":
    """Build a legacy ``TowerModel`` wired with the OC4 jacket SSI.

    Uses ``rotor="nrel_5mw_baseline"`` and ``tower="nrel_5mw_tower"``
    — the onshore NREL 5MW tower that sits on top of the jacket's
    transition piece at z = +20.15 m. Calibrated against the OC4
    Phase I coupled f1 = 0.319 Hz (Popko 2012).
    """
    from op3.composer import compose_tower_model

    jacket = build_jacket(ssi)
    legacy_foundation = jacket.as_legacy_foundation()
    return compose_tower_model(
        rotor="nrel_5mw_baseline",
        tower="nrel_5mw_tower",
        foundation=legacy_foundation,
    )
