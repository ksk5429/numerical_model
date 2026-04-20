"""
Foundation-type protocol and base class (new-API v1.1+).

A :class:`FoundationProtocol` implementation owns the TOPOLOGY of a
foundation (monopile, tripod, jacket, suction bucket, ...) and
delegates SOIL-STRUCTURE-INTERACTION FIDELITY to an ``SSIProtocol``
strategy from :mod:`op3.ssi`.

The split separates two concerns that v1.0 op³ conflated into a
single ``FoundationMode`` enum:

- **Type** — geometry, mass, wall schedule, bucket count, brace
  layout. These are properties of the physical foundation; they
  cannot be swapped at runtime without rebuilding the model.
- **SSI fidelity** — fixed base, lumped 6x6 stiffness, lumped BNWF,
  physical distributed BNWF, Craig-Bampton reduction. These describe
  HOW the soil-foundation interaction is represented numerically;
  they are strategies the type composes with.

Every concrete type implements :class:`FoundationProtocol` and may
inherit from :class:`BaseFoundation` for the back-compat bridge to
the legacy ``Foundation`` dataclass + ``composer.compose_tower_model``
pipeline.

Validation protocol
-------------------
A concrete type is expected to live under :mod:`op3.models.<name>/`
and to maintain a ``vvc.yaml`` dossier (V&V&C: verification,
validation, calibration). Until every V&V metric in the dossier is
GREEN the type MUST NOT be re-exported from any public namespace
outside its own ``models`` directory.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from enum import Enum
from typing import Protocol, TYPE_CHECKING, runtime_checkable

import numpy as np

if TYPE_CHECKING:  # pragma: no cover
    from op3.foundations._legacy import Foundation
    from op3.ssi.base import SSIProtocol


class FoundationType(str, Enum):
    """High-level classification of supported foundation topologies.

    These are DESCRIPTIVE labels attached to each concrete type; they
    do NOT replace the legacy ``FoundationMode`` enum (which describes
    SSI fidelity, not topology). A single ``FoundationType`` value can
    be instantiated with any compatible ``SSIProtocol``.
    """
    MONOPILE = "monopile"
    TRIPOD = "tripod"
    JACKET = "jacket"
    SUCTION_BUCKET = "suction_bucket"
    GBS = "gbs"  # Gravity-based structure, placeholder for future work


@runtime_checkable
class FoundationProtocol(Protocol):
    """Contract for a foundation TYPE.

    Implementations own geometry + mass + the OpenSees topology they
    need to build, and compose with an ``SSIProtocol`` strategy for
    soil-structure interaction. The protocol is deliberately small so
    new types (e.g. gravity-based structures) can be added without
    touching the core pipeline.
    """

    #: Canonical short name, e.g. ``"monopile"`` or ``"tripod"``. Used
    #: for logging, dossier lookup, and registry keys.
    type_name: str

    #: High-level classification (see :class:`FoundationType`).
    foundation_type: FoundationType

    def head_stiffness_6x6(self) -> np.ndarray:
        """Return the 6x6 stiffness at the tower-base (foundation-top)
        interface, in SI units (N/m, N·m/rad, mixed off-diagonals).

        For fixed-base and elastic-head-spring SSI strategies this is
        analytical. For physical BNWF with Craig-Bampton reduction it
        may trigger an OpenSees model build and matrix condensation.
        """
        ...

    def as_legacy_foundation(self) -> "Foundation":
        """Back-compat bridge: return a legacy :class:`Foundation`
        (``mode=STIFFNESS_6X6``, ``stiffness_matrix=head_stiffness_6x6()``)
        so the v1.0 :func:`op3.composer.compose_tower_model` pipeline
        works unchanged.

        Future types with non-trivial topology (skirt, braces, etc.)
        will grow a second bridge, ``build_opensees(ops, base_node)``,
        that instantiates the real topology directly. For v1.1 the
        condensed-6x6 bridge is the only supported handover.
        """
        ...


class BaseFoundation(ABC):
    """Optional base class with a default back-compat bridge.

    Concrete types may subclass :class:`BaseFoundation` for the
    :meth:`as_legacy_foundation` default (which delegates to
    :meth:`head_stiffness_6x6`), or implement :class:`FoundationProtocol`
    directly via duck typing.

    Subclasses MUST:

    - set ``type_name`` and ``foundation_type`` class attributes
    - implement :meth:`head_stiffness_6x6`

    Subclasses SHOULD:

    - provide a classmethod ``.from_dossier(path)`` that loads
      ``site.yaml``, ``geometry.yaml``, ``soil.yaml`` from a
      :mod:`op3.models` subdirectory and returns an instance
    - carry a ``ssi`` attribute set by :meth:`with_ssi` so the same
      topology can be re-used across fidelity levels
    """

    type_name: str = "<abstract>"
    foundation_type: FoundationType = FoundationType.MONOPILE  # overridden

    # The SSI strategy is injected post-construction via ``with_ssi``.
    # It is the means by which head_stiffness_6x6 is computed.
    ssi: "SSIProtocol | None" = None

    @abstractmethod
    def head_stiffness_6x6(self) -> np.ndarray:
        """Compute or return the 6x6 interface stiffness.

        Concrete types typically delegate to ``self.ssi.compute_head_stiffness(self)``.
        """
        ...

    def with_ssi(self, ssi: "SSIProtocol") -> "BaseFoundation":
        """Attach an SSI strategy and return ``self`` for chaining.

        The strategy is stored on the instance; repeated calls replace
        the previous strategy. The same type instance can therefore be
        evaluated under multiple fidelity levels by calling
        :meth:`with_ssi` then :meth:`head_stiffness_6x6` in sequence.
        """
        self.ssi = ssi
        return self

    def as_legacy_foundation(self) -> "Foundation":
        """Default back-compat bridge: wrap :meth:`head_stiffness_6x6`
        in a legacy ``Foundation(mode=STIFFNESS_6X6)`` object.

        The ``_suppress_deprecation_warning`` kwarg on
        :func:`build_foundation` is intentionally NOT used here
        because ``Foundation(...)`` is constructed directly (no
        factory call). The legacy enum itself is silent until called.
        """
        from op3.foundations._legacy import Foundation, FoundationMode

        K = np.asarray(self.head_stiffness_6x6(), dtype=float)
        if K.shape != (6, 6):
            raise ValueError(
                f"{self.type_name}.head_stiffness_6x6() returned shape "
                f"{K.shape}; must be (6, 6)"
            )
        f = Foundation(mode=FoundationMode.STIFFNESS_6X6)
        f.stiffness_matrix = K
        ssi_name = getattr(self.ssi, "name", None) or "unknown-SSI"
        f.source = f"{self.type_name} via as_legacy_foundation() ({ssi_name})"
        return f

    def __repr__(self) -> str:  # pragma: no cover - cosmetic
        ssi_name = getattr(self.ssi, "name", None) or "no SSI"
        return f"<{type(self).__name__} type={self.type_name} ssi={ssi_name}>"
