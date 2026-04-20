"""
SSIProtocol: contract for soil-structure interaction strategies.

An SSI strategy is a thin object that computes the 6x6 head stiffness
of a given foundation geometry. Strategies are type-agnostic in the
sense that a ``Monopile`` and a ``Jacket`` can both ask for a
``Stiffness6x6(K=...)`` result, but they're also permitted to
inspect ``foundation.foundation_type`` and refuse if the fidelity
doesn't match the topology (e.g. a ``BNWFPhysical`` built for
single-skirt piles should not cooperate with a jacket).
"""
from __future__ import annotations

from typing import Protocol, TYPE_CHECKING, runtime_checkable

import numpy as np

if TYPE_CHECKING:  # pragma: no cover
    from op3.foundations.base import FoundationProtocol


@runtime_checkable
class SSIProtocol(Protocol):
    """Contract for an SSI fidelity strategy.

    Implementations provide a 6x6 head stiffness for a foundation.
    The minimal API is :meth:`compute_head_stiffness`; strategies
    that build their own OpenSees topology (physical BNWF, CB
    reduction) add type-specific methods as needed.

    Attributes
    ----------
    name : str
        Short identifier used in diagnostic messages and provenance
        strings (e.g. ``"pisa"``, ``"stiffness_6x6"``, ``"bnwf_physical"``).
    """

    name: str

    def compute_head_stiffness(
        self, foundation: "FoundationProtocol"
    ) -> np.ndarray:
        """Return the foundation's 6x6 head stiffness under this SSI.

        The strategy reads whatever it needs from ``foundation``
        (geometry, soil profile, wall schedule). It MUST NOT mutate
        the foundation.
        """
        ...
