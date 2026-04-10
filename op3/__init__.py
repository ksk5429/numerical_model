"""
Op3: OptumGX-OpenSeesPy-OpenFAST integration framework for offshore wind.

Public API::

    from op3 import build_foundation, compose_tower_model
    foundation = build_foundation(mode='fixed')
    model = compose_tower_model(
        rotor='nrel_5mw_baseline',
        tower='nrel_5mw_tower',
        foundation=foundation,
    )
    freqs = model.eigen(n_modes=3)
"""

from op3.config import load_site_config
from op3.foundations import build_foundation, FoundationMode
from op3.composer import compose_tower_model
from op3.cross_compare import cross_compare

__version__ = "1.0.0-rc1"

__all__ = [
    "load_site_config",
    "build_foundation",
    "FoundationMode",
    "compose_tower_model",
    "cross_compare",
    "__version__",
]
