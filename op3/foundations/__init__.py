"""
Op^3 foundations package.

Two coexisting APIs:

1. **Legacy API (frozen at v1.0)** — re-exported from
   :mod:`op3.foundations._legacy`. Emits :class:`DeprecationWarning`
   when :func:`build_foundation` is called. Will be removed in v2.0.

2. **New type/SSI API (v1.1+)** — :mod:`op3.foundations.types`
   provides concrete foundation topologies (``Monopile``, ``Tripod``,
   ``Jacket``, ``SuctionBucket``); :mod:`op3.ssi` provides SSI
   fidelity strategies (``Fixed``, ``Stiffness6x6``, ``BNWFLumped``,
   ``BNWFPhysical``, ``CraigBampton``). Each model under
   :mod:`op3.models` is a validated-dossier instance that combines
   the two.

Import cheat sheet
------------------
>>> # Legacy (still works; DeprecationWarning)
>>> from op3.foundations import build_foundation, FoundationMode
>>>
>>> # New types
>>> from op3.foundations.types import Monopile
>>> from op3.ssi import Stiffness6x6
>>>
>>> # Foundation protocol (for duck-typing / type hints)
>>> from op3.foundations.base import FoundationProtocol

The package import surface is intentionally thin: everything below is
re-exported from either ``_legacy`` (with a deprecation trail) or
``base`` (the new protocol). Concrete types are NOT re-exported here;
import them explicitly from :mod:`op3.foundations.types`.
"""
from __future__ import annotations

# Re-export the legacy API verbatim so ``from op3.foundations import
# Foundation, FoundationMode, build_foundation, apply_scour_relief,
# foundation_from_pisa`` continues to work for every v1.0 caller.
from op3.foundations._legacy import (
    Foundation,
    FoundationMode,
    apply_scour_relief,
    build_foundation,
    foundation_from_pisa,
)

# New-API surface (opt-in).
from op3.foundations.base import (
    BaseFoundation,
    FoundationProtocol,
    FoundationType,
)

__all__ = [
    # Legacy (deprecated)
    "Foundation",
    "FoundationMode",
    "apply_scour_relief",
    "build_foundation",
    "foundation_from_pisa",
    # New
    "BaseFoundation",
    "FoundationProtocol",
    "FoundationType",
]
