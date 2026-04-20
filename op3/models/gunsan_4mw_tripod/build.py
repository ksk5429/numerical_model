"""
Gunsan 4.2 MW OWT tripod -- model builder.

Public entry points:

- :func:`build_tripod` — returns a configured :class:`Tripod` ready
  for head-stiffness queries. Defaults to a RIGID :class:`Stiffness6x6`
  SSI (upper-bound baseline); pass ``ssi=`` to override.
- :func:`build_tower_model` — bridges the tripod to the legacy
  composer pipeline (rotor='ref_4mw_owt', tower='site_a_rt1_tower')
  so eigen / pushover analyses work unchanged.

Validation status (PR #4)
-------------------------
This dossier is **YELLOW** at PR #4 land. The rigid SSI gives
f1 ≈ 0.317 Hz which is a PHYSICAL UPPER BOUND — the real Gunsan
coupled f1 is 0.240-0.244 Hz per the ProjA design report (see
op3/models/gunsan_4mw_tripod/site.yaml:design_report_targets).
Validation against the coupled target requires a spine-with-ribs
SSI that ports the legacy v1 physics, which lands in PR #5.
"""
from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Optional

from op3.foundations.types import Tripod

if TYPE_CHECKING:  # pragma: no cover
    from op3.composer import TowerModel
    from op3.ssi.base import SSIProtocol


DOSSIER_DIR: Path = Path(__file__).resolve().parent
REPO_ROOT: Path = DOSSIER_DIR.parents[2]
SCOUR_K_MASTER_CSV: Path = (
    REPO_ROOT / "data" / "fem_results" / "Scour_Stiffness_Matrix_Master.csv"
)
SCOUR_K_SMOOTHED_CSV: Path = (
    REPO_ROOT / "data" / "fem_results" / "Scour_Stiffness_Matrix_Smoothed.csv"
)
LID_STIFFNESS_CSV: Path = (
    REPO_ROOT / "data" / "fem_results" / "opensees_lid_stiffness.csv"
)


def build_tripod(ssi: Optional["SSIProtocol"] = None) -> Tripod:
    """Instantiate the Gunsan tripod with its dossier geometry + soil.

    Parameters
    ----------
    ssi : SSIProtocol, optional
        SSI fidelity strategy. Defaults to
        :meth:`op3.ssi.Stiffness6x6.rigid` — this is the PR #4 upper-
        bound baseline. For calibrated analyses against the design-
        report f1 (0.240-0.244 Hz) pass a PR #5 ``TripodSpineRibs``
        SSI (not yet implemented at PR #4 land).
    """
    if ssi is None:
        from op3.ssi import Stiffness6x6

        ssi = Stiffness6x6.rigid()

    tripod = Tripod.from_yaml(DOSSIER_DIR)
    tripod.with_ssi(ssi)
    return tripod


def build_tower_model(ssi: Optional["SSIProtocol"] = None) -> "TowerModel":
    """Build a legacy ``TowerModel`` wired with the Gunsan tripod SSI.

    Uses ``rotor="ref_4mw_owt"`` (UNISON U136 4.2 MW class) and
    ``tower="site_a_rt1_tower"`` — the built-in Op^3 tower template
    that loads the real 27-segment ProjA wall schedule when
    ``OP3_PHD_ROOT`` is set, or a linear-taper fallback otherwise.
    """
    from op3.composer import compose_tower_model

    tripod = build_tripod(ssi)
    legacy_foundation = tripod.as_legacy_foundation()
    return compose_tower_model(
        rotor="ref_4mw_owt",
        tower="site_a_rt1_tower",
        foundation=legacy_foundation,
    )
