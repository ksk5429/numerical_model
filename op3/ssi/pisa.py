"""
PISA SSI strategy: depth-function head stiffness from Burd 2020 /
Byrne 2020 coefficients.

Wraps :func:`op3.standards.pisa.pisa_pile_stiffness_6x6` so a
Monopile (or any other PISA-compatible foundation type) can compose
with it via ``foundation.with_ssi(PISA(soil_profile=..., n_segments=...))``.

Limitations inherited from ``op3.standards.pisa`` (see that module
for citations):

- Small-strain initial stiffness only; nonlinear p-y response is out
  of scope for this strategy (use ``BNWFPhysical`` instead).
- Calibration sets: Byrne 2020 Table 7 (Dunkirk dense sand) and
  Burd 2020 Table 6 (Cowden till clay). CITATION-VERIFIED; numerical
  validation against field-test response TBD.
- Assumes the foundation has ``diameter_m``, ``embed_length_m``, and
  ``soil_profile`` attributes. If the type is not PISA-compatible a
  :class:`TypeError` is raised with a clear message.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Sequence

import numpy as np

if TYPE_CHECKING:  # pragma: no cover
    from op3.foundations.base import FoundationProtocol
    from op3.standards.pisa import SoilState


class PISA:
    """PISA-framework SSI strategy for monopile-like foundations.

    Parameters
    ----------
    soil_profile : sequence of SoilState
        Layered soil from :mod:`op3.standards.pisa`.
    n_segments : int
        Depth discretisation for the PISA integration (default 50).
    label : str, optional
        Provenance tag for diagnostics (e.g. ``"OC3 Phase I dense sand"``).
    """

    name: str = "pisa"

    def __init__(
        self,
        soil_profile: "Sequence[SoilState]",
        n_segments: int = 50,
        label: str | None = None,
    ):
        if not soil_profile:
            raise ValueError("soil_profile must contain at least one layer")
        self.soil_profile = list(soil_profile)
        self.n_segments = int(n_segments)
        self.label = label or f"PISA ({len(self.soil_profile)} layers)"

    def compute_head_stiffness(
        self, foundation: "FoundationProtocol"
    ) -> np.ndarray:
        """Compute the 6x6 head stiffness of ``foundation`` under PISA.

        ``foundation`` must expose ``diameter_m`` and ``embed_length_m``.
        Any other type attributes (wall schedule, above-mudline stub
        length) are ignored — PISA only needs the embedded geometry.
        """
        from op3.standards.pisa import pisa_pile_stiffness_6x6

        D = getattr(foundation, "diameter_m", None)
        L = getattr(foundation, "embed_length_m", None)
        if D is None or L is None:
            raise TypeError(
                f"PISA strategy requires foundation.diameter_m and "
                f"foundation.embed_length_m; {type(foundation).__name__} "
                f"exposes neither."
            )
        return pisa_pile_stiffness_6x6(
            diameter_m=float(D),
            embed_length_m=float(L),
            soil_profile=self.soil_profile,
            n_segments=self.n_segments,
        )

    def __repr__(self) -> str:  # pragma: no cover - cosmetic
        return f"<PISA label={self.label!r} layers={len(self.soil_profile)}>"
