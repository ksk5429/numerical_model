"""
NREL 5MW OC3 Phase I monopile -- model builder.

Instantiates the model via the new :mod:`op3.foundations.types` API
and bridges to the legacy :func:`op3.composer.compose_tower_model`
pipeline so the eigen / pushover / transient analyses work unchanged.

Public entry points
-------------------
- :func:`build_monopile` — returns a configured :class:`Monopile`
  ready for head-stiffness queries. Defaults to rigid SSI; pass an
  ``ssi`` kwarg to override.
- :func:`build_monopile_pisa` — convenience: Monopile pre-wired with
  the :class:`op3.ssi.PISA` strategy and the dossier soil profile.
- :func:`build_monopile_legacy_csv` — convenience: Monopile pre-wired
  with a :class:`op3.ssi.Stiffness6x6` loaded from the legacy
  ``data/fem_results/K_6x6_oc3_monopile.csv`` (useful for diffing the
  new API against the v1.0 pipeline).
- :func:`build_tower_model` — returns a legacy ``TowerModel`` wired
  with the Monopile-derived 6x6 head stiffness.

All functions read from the dossier YAMLs; no hidden constants.

Known limitations (PR #2, see vvc.yaml)
---------------------------------------
The legacy :func:`op3.opensees_foundations.builder._attach_stiffness_6x6`
attaches the 6x6 head stiffness as a diagonal-only ``zeroLength``
element (one :class:`Elastic` uniaxial per DOF). PISA-derived K
matrices carry significant lateral-rocking off-diagonals (``K[0,4]``,
``K[1,3]`` approximately -0.8 times ``sqrt(K[0,0]*K[4,4])``) which
are lost at this attachment. The audit-pass UserWarning fires when
this happens. Fixing it requires either a new custom ``zeroLengthND``
path or the physical-BNWF SSI (blueprint Q1(a), future PR).
"""
from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Optional

from op3.foundations.types import Monopile

if TYPE_CHECKING:  # pragma: no cover
    from op3.composer import TowerModel
    from op3.ssi.base import SSIProtocol


DOSSIER_DIR: Path = Path(__file__).resolve().parent
# op3/models/<name>/build.py -> <repo-root>
#   parents[0] = op3/models
#   parents[1] = op3
#   parents[2] = <repo root>
REPO_ROOT: Path = DOSSIER_DIR.parents[2]
LEGACY_K_CSV: Path = REPO_ROOT / "data" / "fem_results" / "K_6x6_oc3_monopile.csv"


def build_monopile(ssi: Optional["SSIProtocol"] = None) -> Monopile:
    """Instantiate the OC3 monopile with its dossier geometry / soil.

    Parameters
    ----------
    ssi : SSIProtocol, optional
        SSI fidelity strategy. Defaults to
        :meth:`op3.ssi.Stiffness6x6.rigid` (rigid head-spring; the
        most reproducible configuration for establishing the new-API
        contract).
    """
    if ssi is None:
        from op3.ssi import Stiffness6x6

        ssi = Stiffness6x6.rigid()

    monopile = Monopile.from_yaml(DOSSIER_DIR)
    monopile.with_ssi(ssi)
    return monopile


def build_monopile_pisa(n_segments: int = 50) -> Monopile:
    """Build the OC3 monopile pre-wired with the PISA SSI strategy.

    Uses the layered soil profile from ``soil.yaml`` and the PISA
    depth-function coefficients from :mod:`op3.standards.pisa` (Byrne
    2020 Table 7 sand). Raises :class:`ImportError` if
    :mod:`op3.ssi.pisa` is unavailable.
    """
    from op3.ssi import PISA

    if PISA is None:
        raise ImportError(
            "op3.ssi.PISA is unavailable — install PyYAML and ensure "
            "op3.standards.pisa is importable to use the PISA SSI "
            "strategy for this dossier."
        )

    monopile = Monopile.from_yaml(DOSSIER_DIR)
    if not monopile.soil_profile:
        raise RuntimeError(
            f"soil.yaml at {DOSSIER_DIR / 'soil.yaml'} loaded an empty "
            "soil profile; cannot instantiate PISA strategy"
        )
    monopile.with_ssi(
        PISA(
            soil_profile=monopile.soil_profile,
            n_segments=n_segments,
            label="OC3 Phase I dense sand (soil.yaml)",
        )
    )
    return monopile


def build_monopile_legacy_csv() -> Monopile:
    """Build the OC3 monopile with the legacy apparent-fixity K matrix
    from ``data/fem_results/K_6x6_oc3_monopile.csv``.

    Useful for reproducing v1.0 op³ results against the new API. The
    legacy CSV is diagonal-only and K_HH = 8.5e8 N/m; the modern
    PISA-derived K_HH is ~1.9e10 N/m but both give the same coupled
    f1 within 2% because the NREL 5MW OC3 first mode is
    tower-dominated.
    """
    from op3.ssi import Stiffness6x6

    if not LEGACY_K_CSV.exists():
        raise FileNotFoundError(
            f"Legacy OC3 K matrix not found at {LEGACY_K_CSV}. Check "
            "that the data/fem_results tree is present in this checkout."
        )
    monopile = Monopile.from_yaml(DOSSIER_DIR)
    monopile.with_ssi(
        Stiffness6x6.from_csv(
            str(LEGACY_K_CSV),
            label="v1.0 apparent-fixity equivalent (K_6x6_oc3_monopile.csv)",
        )
    )
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
