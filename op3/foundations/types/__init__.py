"""
Concrete foundation types (new-API v1.1+).

Each module in this package provides a single foundation TYPE class
that implements :class:`op3.foundations.base.FoundationProtocol` and
owns the topology for that class of structure.

Status
------
+----------------+------------+-----------------------------------------+
| Type           | Status     | Validated models                        |
+================+============+=========================================+
| Monopile       | skeleton   | nrel_5mw_oc3_monopile (YELLOW, PR #2)   |
| Jacket         | skeleton   | nrel_5mw_oc4_jacket (YELLOW, PR #3)     |
| Tripod         | skeleton   | gunsan_4mw_tripod (YELLOW, PR #4)       |
| SuctionBucket  | planned    | —                                       |
+----------------+------------+-----------------------------------------+

The test bar for any concrete type is a GREEN dossier in
:mod:`op3.models` — every V&V&C metric passing at its acceptance
threshold. Types stay in ``skeleton`` / ``planned`` status until
that bar is cleared.
"""
from __future__ import annotations

from op3.foundations.types.jacket import Jacket
from op3.foundations.types.monopile import Monopile
from op3.foundations.types.tripod import Tripod

__all__ = [
    "Jacket",
    "Monopile",
    "Tripod",
]
