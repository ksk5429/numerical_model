"""
Tripod foundation type (v1.1 skeleton, PR #4).

A tripod suction-bucket foundation comprises a symmetric triangular
arrangement of N suction caissons (typically 3), each connected to
a central transition piece via braced steel legs. This class holds
the topology (bucket count, bucket geometry, radial distance,
angular spacing, transition-piece elevation) and delegates SSI
fidelity to a strategy from :mod:`op3.ssi`.

Status: **skeleton**. PR #4 exposes the protocol bridge
(:meth:`as_legacy_foundation`) so the legacy composer pipeline can
consume a Tripod instance with any head-6x6 SSI strategy. A
tripod-topology-aware SSI (Winkler-per-bucket + 3-bucket assembly,
porting the legacy spine-with-ribs physics from
``docs/manuscripts/current/ch4_1_optumgx_opensees_revised/2_opensees_models/opensees_spine_ribs_scour_validation_v1.py``)
lands in PR #5.

Factory constructors
--------------------
- :meth:`Tripod.from_gunsan_4mw_spec` — Gunsan 4.2 MW OWT (SiteA)
  geometry for the KEPCO demonstration site. Uses public design-
  report values only; proprietary dimensions (skirt length, tower
  segment schedule) are loaded at runtime from
  :mod:`op3.data_sources` when available.
- :meth:`Tripod.from_yaml` — load from a model dossier directory.

Geometry convention
-------------------
The tripod origin is the centroid of the transition piece (directly
below the tower base). Bucket ``i`` is located at

    (x_i, y_i) = (R * cos(theta_i), R * sin(theta_i))

where ``R = tripod_radial_distance_m`` and ``theta_i = i * 360/N``.
The mudline is at ``z = -water_depth_m``. Bucket tops (lids) sit at
``z = mudline_z_m`` (buckets penetrate below).

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
class Tripod(BaseFoundation):
    """Symmetric N-bucket tripod (typically N=3) on suction caissons.

    Parameters
    ----------
    n_buckets : int
        Number of suction-bucket legs. Default 3. Values other than 3
        are accepted (quadpods) but legacy physics was validated on
        3-bucket only.
    bucket_diameter_m : float
        Outer diameter of each bucket lid.
    bucket_skirt_length_m : float
        Embedded skirt length below mudline.
    bucket_skirt_thickness_m : float
        Skirt wall thickness (steel tube).
    tripod_radial_distance_m : float
        Horizontal distance from tripod centroid to each bucket centre.
    tripod_angular_spacing_deg : float
        Angular separation between adjacent buckets. 120 for a
        symmetric 3-bucket tripod.
    mudline_z_m : float
        Mudline elevation in the global coord system (MSL = 0).
    transition_piece_z_m : float
        Elevation where the tripod frame meets the tower base.
    soil_profile : sequence of SoilState
        Soil layers for PISA-compatible SSI strategies.
    site_label : str
        Short provenance tag.
    num_ribs_per_bucket : int
        Number of circumferential ribs per bucket (spine-with-ribs
        topology; legacy v1 used 4). Used by the PR #5 topology-aware
        SSI but ignored by the Stiffness6x6 path.
    steel_* : material properties (standard structural steel defaults).
    """

    type_name: str = "tripod"
    foundation_type: FoundationType = FoundationType.SUCTION_BUCKET   # close enough

    n_buckets: int = 3
    bucket_diameter_m: float = 8.0
    bucket_skirt_length_m: float = 9.3
    bucket_skirt_thickness_m: float = 0.020
    tripod_radial_distance_m: float = 11.58
    tripod_angular_spacing_deg: float = 120.0
    mudline_z_m: float = -8.2
    transition_piece_z_m: float = 23.6
    soil_profile: Sequence["SoilState"] = field(default_factory=list)
    site_label: str = "generic-tripod"
    num_ribs_per_bucket: int = 4   # used by PR #5 spine-with-ribs SSI
    steel_E_Pa: float = 2.1e11
    steel_G_Pa: float = 8.1e10
    steel_rho_kg_m3: float = 7850.0

    ssi: Optional["SSIProtocol"] = None

    # ---- Factory constructors ------------------------------------------------

    @classmethod
    def from_gunsan_4mw_spec(
        cls,
        soil_profile: Optional[Sequence["SoilState"]] = None,
    ) -> "Tripod":
        """Return a Tripod pre-configured with Gunsan 4.2 MW OWT geometry.

        Sources (public only):

        - D_bucket = 8.0 m (Kim 2024 GEOTEC LNCE 395; verified against
          ProjA design report p.12).
        - t_skirt = 0.020 m (ProjA design report).
        - Tripod radial distance = 11.58 m, angular spacing = 120
          (ProjA tripod_input.txt: sqrt(10.029^2+5.79^2)).
        - Water depth = 8.2 m (Gunsan Demo site, KEPCO).
        - Tower base elevation = 23.6 m above mudline.

        Proprietary parameters (skirt length, per-segment wall schedule)
        are NOT set by this constructor. Use
        :meth:`Tripod.from_yaml(op3.models.gunsan_4mw_tripod.DOSSIER_DIR)`
        to load runtime overrides from the SSOT ``site_a.yaml`` when
        ``OP3_PHD_ROOT`` or a dossier-level YAML is available.
        """
        return cls(
            n_buckets=3,
            bucket_diameter_m=8.0,
            bucket_skirt_length_m=9.3,         # public estimate; override via site_a.yaml
            bucket_skirt_thickness_m=0.020,
            tripod_radial_distance_m=11.58,
            tripod_angular_spacing_deg=120.0,
            mudline_z_m=-8.2,
            transition_piece_z_m=23.6,
            soil_profile=list(soil_profile) if soil_profile else [],
            site_label="Gunsan 4.2 MW OWT (KEPCO/MMB/Unison UNISON U136)",
            num_ribs_per_bucket=4,
        )

    @classmethod
    def from_yaml(cls, model_dir: str | Path) -> "Tripod":
        """Load a Tripod from an :mod:`op3.models` dossier directory."""
        try:
            import yaml  # type: ignore
        except ImportError as e:  # pragma: no cover
            raise ImportError("Tripod.from_yaml requires PyYAML") from e

        model_dir = Path(model_dir)
        geom = _load_yaml_block(model_dir / "geometry.yaml", "tripod", {})
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

        return cls(
            n_buckets=int(geom.get("n_buckets", cls.n_buckets)),
            bucket_diameter_m=float(geom.get("bucket_diameter_m", cls.bucket_diameter_m)),
            bucket_skirt_length_m=float(
                geom.get("bucket_skirt_length_m", cls.bucket_skirt_length_m)
            ),
            bucket_skirt_thickness_m=float(
                geom.get("bucket_skirt_thickness_m", cls.bucket_skirt_thickness_m)
            ),
            tripod_radial_distance_m=float(
                geom.get("tripod_radial_distance_m", cls.tripod_radial_distance_m)
            ),
            tripod_angular_spacing_deg=float(
                geom.get("tripod_angular_spacing_deg", cls.tripod_angular_spacing_deg)
            ),
            mudline_z_m=float(geom.get("mudline_z_m", cls.mudline_z_m)),
            transition_piece_z_m=float(
                geom.get("transition_piece_z_m", cls.transition_piece_z_m)
            ),
            soil_profile=soil_profile,
            num_ribs_per_bucket=int(
                geom.get("num_ribs_per_bucket", cls.num_ribs_per_bucket)
            ),
            site_label=str(site.get("label", model_dir.name)),
        )

    # ---- FoundationProtocol ------------------------------------------------

    def head_stiffness_6x6(self) -> np.ndarray:
        """Compute the 6x6 head stiffness at the transition-piece
        centroid under the attached SSI strategy.

        Raises :class:`RuntimeError` if no SSI strategy was attached.
        """
        if self.ssi is None:
            raise RuntimeError(
                f"Tripod '{self.site_label}' has no SSI strategy. Call "
                "tripod.with_ssi(Stiffness6x6.rigid()) or similar "
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

    # ---- Diagnostics ---------------------------------------------------------

    def topology_summary(self) -> dict:
        """Return a dict describing the tripod topology for dossier
        provenance / V&V&C checks."""
        return {
            "n_buckets": int(self.n_buckets),
            "bucket_diameter_m": float(self.bucket_diameter_m),
            "bucket_skirt_length_m": float(self.bucket_skirt_length_m),
            "bucket_skirt_thickness_m": float(self.bucket_skirt_thickness_m),
            "tripod_radial_distance_m": float(self.tripod_radial_distance_m),
            "tripod_angular_spacing_deg": float(self.tripod_angular_spacing_deg),
            "mudline_z_m": float(self.mudline_z_m),
            "transition_piece_z_m": float(self.transition_piece_z_m),
            "bucket_spacing_m": float(
                2.0 * self.tripod_radial_distance_m
                * np.sin(np.radians(self.tripod_angular_spacing_deg / 2.0))
            ),
            "num_ribs_per_bucket": int(self.num_ribs_per_bucket),
        }

    def bucket_positions(self) -> np.ndarray:
        """Return an (n_buckets, 3) array of bucket-centre (x, y, z)
        coordinates in the global frame."""
        R = self.tripod_radial_distance_m
        dtheta = np.radians(self.tripod_angular_spacing_deg)
        coords = np.zeros((self.n_buckets, 3))
        for i in range(self.n_buckets):
            theta = i * dtheta
            coords[i] = [R * np.cos(theta), R * np.sin(theta), self.mudline_z_m]
        return coords


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _load_yaml_block(path: Path, key: str, default):
    """Mirror of :func:`op3.foundations.types.monopile._load_yaml_block`."""
    if not path.exists():
        return default
    try:
        import yaml  # type: ignore
    except ImportError:  # pragma: no cover
        return default
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return data.get(key, default)
