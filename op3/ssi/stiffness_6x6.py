"""
Stiffness6x6: a degenerate SSI strategy that holds a pre-computed
6x6 head stiffness matrix.

Use this when the head stiffness has already been computed upstream
(e.g. by an external PISA run, a SACS-exported jacket condensation,
or a cached OptumG2 probe). It is also the simplest possible SSI
strategy — useful for test fixtures and for the fixed-base limit
(``K`` set to a large-diagonal "rigid" matrix).
"""
from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:  # pragma: no cover
    from op3.foundations.base import FoundationProtocol


_RIGID_DIAGONAL = 1.0e20


class Stiffness6x6:
    """SSI strategy: return a fixed 6x6 matrix.

    Parameters
    ----------
    K : np.ndarray of shape (6, 6)
        The 6x6 head stiffness in SI units (N/m, N·m/rad, mixed
        off-diagonals following the Op³ sign convention K[0,4] < 0,
        K[1,3] > 0).
    label : str
        Provenance label (e.g. ``"OptumG2 2026-03 probe"``).
    """

    name: str = "stiffness_6x6"

    def __init__(self, K: np.ndarray, label: str = "user-supplied K"):
        K = np.asarray(K, dtype=float)
        if K.shape != (6, 6):
            raise ValueError(f"K must be (6, 6), got {K.shape}")
        self._K = K
        self.label = label

    # ---- Factory constructors ------------------------------------------------

    @classmethod
    def rigid(cls) -> "Stiffness6x6":
        """Return a rigid (fixed-base) 6x6 — all diagonal terms at 1e20."""
        return cls(
            K=np.diag([_RIGID_DIAGONAL] * 6),
            label="rigid / fixed-base surrogate",
        )

    @classmethod
    def from_csv(cls, path: str, label: str | None = None) -> "Stiffness6x6":
        """Load a 6x6 matrix from a headerless CSV."""
        import pandas as pd

        K = pd.read_csv(path, header=None).values
        return cls(K=K, label=label or f"CSV: {path}")

    # ---- SSIProtocol --------------------------------------------------------

    def compute_head_stiffness(
        self, foundation: "FoundationProtocol"  # noqa: ARG002 (unused)
    ) -> np.ndarray:
        """Return the stored K matrix. ``foundation`` is ignored."""
        return self._K.copy()

    def __repr__(self) -> str:  # pragma: no cover - cosmetic
        return f"<Stiffness6x6 label={self.label!r}>"
