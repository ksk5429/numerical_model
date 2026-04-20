"""
Jacket foundation type (v1.1 skeleton).

A jacket is a lattice-truss substructure made of tubular steel
members bracing a vertical leg set. Jackets span the deeper-water
range (roughly 30–80 m) where monopile eigenfrequencies drift out
of the soft-stiff band and tripods become fabrication-heavy.

This class stores geometry + soil + an optional parsed SACS deck
and delegates head-stiffness computation to an SSI strategy from
:mod:`op3.ssi`. For PR #3 the expected strategy is
:class:`~op3.ssi.stiffness_6x6.Stiffness6x6` loaded from a
pre-computed 6x6 CSV (see ``data/fem_results/K_6x6_oc4_jacket.csv``
for the OC4 Phase I benchmark). Later PRs will add a
``JacketCraigBampton`` strategy that rebuilds the jacket in
OpenSees from the SACS geometry and extracts K via
:mod:`op3.openfast_coupling.craig_bampton`.

Status: **skeleton**. The SACS deck is parsed eagerly in
:meth:`from_sacs_deck` but the geometry is only used for diagnostics
at the PR #3 fidelity. Topology-specific OpenSees instantiation
(per-leg members + X-bracing + mudline fix) is future work.

Factory constructors
--------------------
- :meth:`Jacket.from_oc4_phase1_spec` — NREL 5MW OC4 Phase I jacket
  geometry (Popko 2012, NREL/TP-5000-56129). Loads the SACS deck if
  available, otherwise falls back to metadata-only.
- :meth:`Jacket.from_sacs_deck` — parse a user-supplied SACS deck.
- :meth:`Jacket.from_yaml` — load from a dossier directory.

Instances are immutable w.r.t. geometry / SACS parse; only the
attached SSI strategy is swappable via :meth:`with_ssi`.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Optional, Sequence

import numpy as np

from op3.foundations.base import BaseFoundation, FoundationType

if TYPE_CHECKING:  # pragma: no cover
    from op3.sacs_interface.parser import SacsJacket
    from op3.standards.pisa import SoilState
    from op3.ssi.base import SSIProtocol


@dataclass
class Jacket(BaseFoundation):
    """Lattice-truss jacket substructure.

    Parameters
    ----------
    n_legs : int
        Number of vertical legs (3 or 4; OC4 Phase I is 4).
    n_x_braces : int
        Number of X-brace levels between mudline and the tower-
        transition piece (OC4 Phase I: 4).
    leg_diameter_m : float
        Outer diameter of the leg tubes at the base (legs in real
        jackets are stepped; a single representative value is stored
        here for provenance and will be replaced when per-segment
        schedules land).
    leg_wall_thickness_m : float
        Representative leg wall thickness.
    brace_diameter_m : float
        Representative X-brace diameter.
    brace_wall_thickness_m : float
        Representative X-brace wall thickness.
    mudline_z_m : float
        Elevation of the mudline in the jacket's own coordinate system
        (negative below MSL by convention).
    transition_piece_z_m : float
        Elevation where the jacket meets the tower base.
    footprint_spacing_m : float
        Horizontal spacing between adjacent legs at the mudline.
    soil_profile : sequence of SoilState
        Mudline soil layers consumed by PISA-style SSI strategies.
    sacs_deck : SacsJacket, optional
        Parsed SACS deck for diagnostic / topology inspection.
    site_label : str
        Short provenance tag.
    steel_* : material properties (standard structural steel defaults).
    """

    type_name: str = "jacket"
    foundation_type: FoundationType = FoundationType.JACKET

    n_legs: int = 4
    n_x_braces: int = 4
    leg_diameter_m: float = 1.2
    leg_wall_thickness_m: float = 0.05
    brace_diameter_m: float = 0.8
    brace_wall_thickness_m: float = 0.02
    mudline_z_m: float = -50.0
    transition_piece_z_m: float = 20.0
    footprint_spacing_m: float = 12.0
    soil_profile: Sequence["SoilState"] = field(default_factory=list)
    sacs_deck: Optional["SacsJacket"] = None
    site_label: str = "generic-jacket"
    steel_E_Pa: float = 2.1e11
    steel_G_Pa: float = 8.1e10
    steel_rho_kg_m3: float = 7850.0

    ssi: Optional["SSIProtocol"] = None

    # ---- Factory constructors ------------------------------------------------

    @classmethod
    def from_oc4_phase1_spec(
        cls,
        soil_profile: Optional[Sequence["SoilState"]] = None,
        sacs_deck_path: Optional[str | Path] = None,
    ) -> "Jacket":
        """Return a Jacket pre-configured with OC4 Phase I geometry.

        OC4 Phase I jacket dimensions per Popko et al. (2012),
        NREL/TP-5000-56129:

        - 4 vertical legs at 12 m base spacing (batter 1:30).
        - 4 X-brace levels between mudline and transition piece.
        - Seabed at z = -50 m (50 m water depth).
        - Tower base (transition piece) at z = +20.15 m.
        - Representative leg OD ~ 1.2 m, wall ~ 0.05 m.
        - Representative brace OD ~ 0.8 m, wall ~ 0.02 m.

        ``sacs_deck_path`` (optional): path to the OC4 SACS deck at
        ``nrel_reference/sacs_jackets/nrel_oc4/NREL_OC4.sacs``. When
        provided, :func:`op3.sacs_interface.parse_sacs` is called
        eagerly; the parsed deck is stored in :attr:`sacs_deck`.
        """
        jacket = cls(
            n_legs=4,
            n_x_braces=4,
            leg_diameter_m=1.2,
            leg_wall_thickness_m=0.05,
            brace_diameter_m=0.8,
            brace_wall_thickness_m=0.02,
            mudline_z_m=-50.0,
            transition_piece_z_m=20.15,
            footprint_spacing_m=12.0,
            soil_profile=list(soil_profile) if soil_profile else [],
            site_label="NREL 5MW OC4 Phase I (Popko 2012)",
        )
        if sacs_deck_path is not None:
            jacket.sacs_deck = _parse_sacs_safe(sacs_deck_path)
        return jacket

    @classmethod
    def from_sacs_deck(
        cls,
        sacs_path: str | Path,
        soil_profile: Optional[Sequence["SoilState"]] = None,
    ) -> "Jacket":
        """Parse a SACS deck and infer coarse jacket metadata.

        Leg / brace counts are NOT read from the deck in v1.1 (the
        SACS parser returns joint/member lists without topology
        classification). Downstream work should populate the
        topology fields via an explicit argument or with a SACS
        group-name heuristic.
        """
        deck = _parse_sacs_safe(sacs_path)
        return cls(
            soil_profile=list(soil_profile) if soil_profile else [],
            sacs_deck=deck,
            site_label=f"SACS: {Path(sacs_path).name}",
            mudline_z_m=float(deck.seabed_elev_m),
        )

    @classmethod
    def from_yaml(cls, model_dir: str | Path) -> "Jacket":
        """Load a Jacket from an :mod:`op3.models` dossier directory.

        Reads ``geometry.yaml`` (``jacket`` block), ``soil.yaml``
        (``layers`` block), and optionally parses a SACS deck at the
        path referenced by ``geometry.yaml:jacket.sacs_deck``.
        """
        try:
            import yaml  # type: ignore
        except ImportError as e:  # pragma: no cover
            raise ImportError("Jacket.from_yaml requires PyYAML") from e

        model_dir = Path(model_dir)
        geom = _load_yaml_block(model_dir / "geometry.yaml", "jacket", {})
        soil = _load_yaml_block(model_dir / "soil.yaml", "layers", [])
        site = _load_yaml_block(model_dir / "site.yaml", "site", {})

        soil_profile: list = []
        if soil:
            try:
                from op3.standards.pisa import SoilState

                for layer in soil:
                    soil_profile.append(
                        SoilState(
                            depth_m=float(layer["depth_m"]),
                            G_Pa=float(layer["G_Pa"]),
                            su_or_phi=float(layer.get("su_or_phi", 0.0)),
                            soil_type=str(layer.get("soil_type", "sand")),
                        )
                    )
            except ImportError:  # pragma: no cover
                pass

        sacs_deck = None
        sacs_rel = geom.get("sacs_deck")
        if sacs_rel:
            sacs_path = (model_dir / sacs_rel).resolve()
            if sacs_path.exists():
                sacs_deck = _parse_sacs_safe(sacs_path)

        return cls(
            n_legs=int(geom.get("n_legs", cls.n_legs)),
            n_x_braces=int(geom.get("n_x_braces", cls.n_x_braces)),
            leg_diameter_m=float(geom.get("leg_diameter_m", cls.leg_diameter_m)),
            leg_wall_thickness_m=float(
                geom.get("leg_wall_thickness_m", cls.leg_wall_thickness_m)
            ),
            brace_diameter_m=float(geom.get("brace_diameter_m", cls.brace_diameter_m)),
            brace_wall_thickness_m=float(
                geom.get("brace_wall_thickness_m", cls.brace_wall_thickness_m)
            ),
            mudline_z_m=float(geom.get("mudline_z_m", cls.mudline_z_m)),
            transition_piece_z_m=float(
                geom.get("transition_piece_z_m", cls.transition_piece_z_m)
            ),
            footprint_spacing_m=float(
                geom.get("footprint_spacing_m", cls.footprint_spacing_m)
            ),
            soil_profile=soil_profile,
            sacs_deck=sacs_deck,
            site_label=str(site.get("label", model_dir.name)),
        )

    # ---- FoundationProtocol ------------------------------------------------

    def head_stiffness_6x6(self) -> np.ndarray:
        """Compute the 6x6 head stiffness under the attached SSI strategy.

        The jacket class is agnostic to SSI fidelity at PR #3 — it
        delegates entirely to :attr:`ssi`. A
        :class:`~op3.ssi.stiffness_6x6.Stiffness6x6` strategy
        pre-loaded with the OC4 SubDyn-condensed 6x6 is the
        expected path.
        """
        if self.ssi is None:
            raise RuntimeError(
                f"Jacket '{self.site_label}' has no SSI strategy. Call "
                "jacket.with_ssi(Stiffness6x6.from_csv('K_6x6_oc4_jacket.csv')) "
                "or similar before requesting head_stiffness_6x6()."
            )
        K = self.ssi.compute_head_stiffness(self)
        K = np.asarray(K, dtype=float)
        if K.shape != (6, 6):
            raise RuntimeError(
                f"SSI strategy {self.ssi.name!r} returned shape {K.shape}; "
                "expected (6, 6)"
            )
        return K

    # ---- Diagnostics ---------------------------------------------------------

    def topology_summary(self) -> dict:
        """Return a dict describing the jacket topology. Useful for
        the dossier tests and the ``vvc.yaml`` provenance block."""
        summary = {
            "n_legs": int(self.n_legs),
            "n_x_braces": int(self.n_x_braces),
            "mudline_z_m": float(self.mudline_z_m),
            "transition_piece_z_m": float(self.transition_piece_z_m),
            "water_depth_m": float(self.transition_piece_z_m - self.mudline_z_m
                                   - 20.15) if self.transition_piece_z_m > 0 else 0.0,
            "leg_diameter_m": float(self.leg_diameter_m),
            "brace_diameter_m": float(self.brace_diameter_m),
            "footprint_spacing_m": float(self.footprint_spacing_m),
            "sacs_deck_loaded": self.sacs_deck is not None,
        }
        if self.sacs_deck is not None:
            summary["sacs_joints"] = len(self.sacs_deck.joints)
            summary["sacs_members"] = len(self.sacs_deck.members)
            summary["sacs_sections"] = len(self.sacs_deck.sections)
        return summary


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _load_yaml_block(path: Path, key: str, default):
    """Mirror of :func:`op3.foundations.types.monopile._load_yaml_block`.

    Kept local to avoid cross-module imports during type-definition
    time.
    """
    if not path.exists():
        return default
    try:
        import yaml  # type: ignore
    except ImportError:  # pragma: no cover
        return default
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return data.get(key, default)


def _parse_sacs_safe(sacs_path: str | Path) -> Optional["SacsJacket"]:
    """Parse a SACS deck, returning None on missing-file / parser error.

    The Op^3 SACS parser is tolerant but not bulletproof; a missing
    file should never crash the Jacket factory constructors.
    """
    try:
        from op3.sacs_interface.parser import parse_sacs
    except ImportError:  # pragma: no cover
        return None
    p = Path(sacs_path)
    if not p.exists():
        return None
    try:
        return parse_sacs(p)
    except Exception:  # pragma: no cover
        return None
