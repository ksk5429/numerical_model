"""
Monopile foundation type (v1.1 skeleton).

A monopile is a single vertical steel tube driven or drilled into
the seabed. This class holds the geometry and soil profile but
delegates head-stiffness computation to an SSI strategy from
:mod:`op3.ssi`.

Status: **skeleton**. PR #1 exposes the protocol bridge
(:meth:`as_legacy_foundation`) so the legacy composer pipeline can
consume a Monopile instance; topology-specific OpenSees instantiation
(for distributed BNWF and Craig-Bampton reduction) lands in later
PRs once the NREL 5MW OC3 dossier goes GREEN.

Factory constructors
--------------------
- :meth:`Monopile.from_oc3_spec` — NREL 5MW OC3 Phase I geometry
  (D=6 m, t=0.06 m, L_embed=36 m, 20 m water depth).
- :meth:`Monopile.from_yaml` — load geometry + soil from a model
  dossier directory (:mod:`op3.models.<name>`).

Instances are immutable w.r.t. geometry; only the attached SSI
strategy is swappable via :meth:`with_ssi`.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Optional, Sequence

import numpy as np

from op3.foundations.base import BaseFoundation, FoundationType

if TYPE_CHECKING:  # pragma: no cover
    from op3.standards.pisa import SoilState
    from op3.ssi.base import SSIProtocol


@dataclass
class Monopile(BaseFoundation):
    """Single steel tube driven into the seabed.

    Parameters
    ----------
    diameter_m : float
        Outer diameter of the tube (assumed constant along the length
        in this v1.1 skeleton; varying wall schedules are future work).
    wall_thickness_m : float
        Wall thickness (assumed constant).
    embed_length_m : float
        Embedded length below mudline.
    stub_length_m : float
        Length of monopile protruding above mudline, up to the tower
        base interface. For OC3 Phase I this is ``mudline → tower-base
        elevation = 10 m − (−20 m) = 30 m`` (20 m water depth + 10 m
        above MSL).
    soil_profile : sequence of SoilState
        Soil layers consumed by PISA-style SSI strategies. May be
        empty for SSI strategies (e.g. :class:`~op3.ssi.stiffness_6x6.Stiffness6x6`)
        that don't need soil properties.
    site_label : str
        Short provenance tag (e.g. ``"OC3-Phase-I"``).
    steel_E_Pa, steel_G_Pa, steel_rho_kg_m3 : float
        Material properties; defaults are standard structural steel.
    """

    type_name: str = "monopile"
    foundation_type: FoundationType = FoundationType.MONOPILE

    diameter_m: float = 6.0
    wall_thickness_m: float = 0.06
    embed_length_m: float = 36.0
    stub_length_m: float = 30.0
    soil_profile: Sequence["SoilState"] = field(default_factory=list)
    site_label: str = "generic-monopile"
    steel_E_Pa: float = 2.1e11
    steel_G_Pa: float = 8.1e10
    steel_rho_kg_m3: float = 7850.0

    # SSI strategy is injected via .with_ssi(); the BaseFoundation base
    # class declares the attribute, but the dataclass needs its own
    # default for type-check friendliness.
    ssi: Optional["SSIProtocol"] = None

    # ---- Factory constructors ------------------------------------------------

    @classmethod
    def from_oc3_spec(
        cls,
        soil_profile: Optional[Sequence["SoilState"]] = None,
    ) -> "Monopile":
        """Return a Monopile pre-configured with NREL 5MW OC3 Phase I
        geometry (Jonkman et al. 2010, NREL/TP-500-47535).

        The SSI strategy is NOT attached; call :meth:`with_ssi` on the
        returned instance to pick a fidelity level. If ``soil_profile``
        is omitted the Monopile carries an empty soil list and only
        SSI-agnostic strategies (e.g. ``Stiffness6x6.rigid()``) will
        work against it.
        """
        return cls(
            diameter_m=6.0,
            wall_thickness_m=0.060,
            embed_length_m=36.0,
            stub_length_m=30.0,   # 20 m water + 10 m above MSL
            soil_profile=list(soil_profile) if soil_profile else [],
            site_label="NREL 5MW OC3 Phase I (Jonkman 2010)",
        )

    @classmethod
    def from_yaml(cls, model_dir: str | Path) -> "Monopile":
        """Load a Monopile from an :mod:`op3.models` dossier directory.

        Expected files:

        - ``geometry.yaml`` — ``monopile`` block with ``diameter_m``,
          ``wall_thickness_m``, ``embed_length_m``, ``stub_length_m``.
        - ``soil.yaml`` — optional ``layers`` block consumed by PISA.
        - ``site.yaml`` — optional ``label`` / ``site_id``.

        Any missing file falls back to the class defaults; only a
        malformed YAML raises.
        """
        try:
            import yaml  # type: ignore
        except ImportError as e:  # pragma: no cover
            raise ImportError("Monopile.from_yaml requires PyYAML") from e

        model_dir = Path(model_dir)
        geom = _load_yaml_block(model_dir / "geometry.yaml", "monopile", {})
        soil = _load_yaml_block(model_dir / "soil.yaml", "layers", [])
        site = _load_yaml_block(model_dir / "site.yaml", "site", {})

        # Convert soil layers to SoilState objects (optional op3.standards.pisa).
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

        return cls(
            diameter_m=float(geom.get("diameter_m", cls.diameter_m)),
            wall_thickness_m=float(geom.get("wall_thickness_m", cls.wall_thickness_m)),
            embed_length_m=float(geom.get("embed_length_m", cls.embed_length_m)),
            stub_length_m=float(geom.get("stub_length_m", cls.stub_length_m)),
            soil_profile=soil_profile,
            site_label=str(site.get("label", model_dir.name)),
        )

    # ---- FoundationProtocol ------------------------------------------------

    def head_stiffness_6x6(self) -> np.ndarray:
        """Compute the 6x6 head stiffness under the attached SSI strategy.

        Raises :class:`RuntimeError` if no SSI strategy was attached.
        """
        if self.ssi is None:
            raise RuntimeError(
                f"Monopile '{self.site_label}' has no SSI strategy. "
                "Call monopile.with_ssi(Stiffness6x6(...)) or similar "
                "before requesting head_stiffness_6x6()."
            )
        K = self.ssi.compute_head_stiffness(self)
        K = np.asarray(K, dtype=float)
        if K.shape != (6, 6):
            raise RuntimeError(
                f"SSI strategy {self.ssi.name!r} returned shape {K.shape}; "
                "expected (6, 6)"
            )
        return K


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _load_yaml_block(path: Path, key: str, default):
    """Return ``yaml_content[key]`` from ``path``, falling back to ``default``
    if the file or the key is missing. Malformed YAML propagates."""
    if not path.exists():
        return default
    try:
        import yaml  # type: ignore
    except ImportError:  # pragma: no cover
        return default
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return data.get(key, default)
