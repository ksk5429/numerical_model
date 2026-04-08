"""
Op^3: OptumGX - OpenSeesPy - OpenFAST integrated numerical modeling framework
for offshore wind turbines.

Public API:

    from op3 import build_foundation, compose_tower_model, cross_compare
    from op3 import load_site_config

    # Build a foundation module
    foundation = build_foundation(
        mode='distributed_bnwf',
        ogx_data='data/fem_results/opensees_spring_stiffness.csv',
        scour_depth=1.5,
    )

    # Compose a full tower + foundation model
    model = compose_tower_model(
        rotor='nrel_5mw',
        tower='gunsan_u136',
        foundation=foundation,
    )

    # Run eigenvalue analysis
    freqs = model.eigen(n_modes=6)

    # Cross-compare across the 4 foundation modes
    results = cross_compare(
        rotor='nrel_5mw',
        tower='gunsan_u136',
        scour_levels=[0.0, 0.5, 1.0, 1.5, 2.0],
    )
"""

from op3.config import load_site_config
from op3.foundations import build_foundation, FoundationMode
from op3.composer import compose_tower_model
from op3.cross_compare import cross_compare

__version__ = "0.1.0"

__all__ = [
    "load_site_config",
    "build_foundation",
    "FoundationMode",
    "compose_tower_model",
    "cross_compare",
    "__version__",
]
