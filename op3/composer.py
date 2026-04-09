"""
Op^3 tower + foundation composer.

The composer assembles an OpenSeesPy model from three orthogonal
choices:

    (rotor template) x (tower template) x (foundation module)

The rotor and tower templates live in `op3.opensees_foundations.templates`
and map to published reference designs (NREL 5MW, IEA 15MW, Reference 4 MW OWT,
etc.). The foundation module is one of the four Op^3 foundation modes
from `op3.foundations`.

Example
-------

>>> from op3 import build_foundation, compose_tower_model
>>> f = build_foundation(mode='distributed_bnwf',
...                      spring_profile='data/fem_results/opensees_spring_stiffness.csv',
...                      scour_depth=1.0)
>>> model = compose_tower_model(
...     rotor='nrel_5mw_baseline',
...     tower='nrel_5mw_tower',
...     foundation=f,
...     damping_ratio=0.01,
... )
>>> freqs = model.eigen(n_modes=6)
>>> print(freqs)
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np

from op3.foundations import Foundation


@dataclass
class TowerModel:
    """Handle returned by the composer.

    Wraps an OpenSees domain and exposes the standard three analyses
    (eigenvalue, pushover, transient) plus a 6x6 static-condensation
    stiffness extraction for OpenFAST SubDyn export.
    """
    rotor_name: str
    tower_name: str
    foundation: Foundation
    # OpenSees domain state is held in the global OpenSees state; this
    # flag tells us whether the model has been built.
    _built: bool = False
    # Cached results
    _eigen_freqs: Optional[np.ndarray] = None
    _k_ssi_6x6: Optional[np.ndarray] = None

    def build(self) -> None:
        """Instantiate the OpenSees model. Idempotent."""
        if self._built:
            return
        from op3.opensees_foundations import build_opensees_model
        build_opensees_model(self)
        self._built = True

    def eigen(self, n_modes: int = 6) -> np.ndarray:
        """Run an eigenvalue analysis and return the first n natural frequencies in Hz."""
        from op3.opensees_foundations import run_eigen_analysis
        self.build()
        self._eigen_freqs = run_eigen_analysis(self, n_modes)
        return self._eigen_freqs

    def pushover(self, target_disp_m: float = 1.0, n_steps: int = 50) -> dict:
        """Run a static lateral pushover at the hub node.

        Returns a dict with `displacement_m` and `reaction_kN` arrays.
        """
        from op3.opensees_foundations.builder import run_pushover_analysis
        self.build()
        return run_pushover_analysis(self, target_disp_m=target_disp_m,
                                     n_steps=n_steps)

    def transient(self, duration_s: float = 10.0, dt_s: float = 0.01,
                  damping_ratio: float = 0.01) -> dict:
        """Run a free-vibration transient with hub-node initial perturbation.

        Returns a dict with `time_s` and `hub_disp_m` arrays for the hub node.
        """
        from op3.opensees_foundations.builder import run_transient_analysis
        self.build()
        return run_transient_analysis(self, duration_s=duration_s, dt_s=dt_s,
                                       damping_ratio=damping_ratio)

    def extract_6x6_stiffness(self) -> np.ndarray:
        """Static condensation of the foundation DOFs onto the tower base node.
        Returns a symmetric 6x6 stiffness matrix suitable for OpenFAST SubDyn."""
        from op3.opensees_foundations import run_static_condensation
        self.build()
        self._k_ssi_6x6 = run_static_condensation(self)
        return self._k_ssi_6x6


def compose_tower_model(
    rotor: str,
    tower: str,
    foundation: Foundation,
    damping_ratio: float = 0.01,
) -> TowerModel:
    """Build a TowerModel from the given rotor, tower, and foundation.

    Parameters
    ----------
    rotor : str
        Name of a rotor template. Valid values:
            'nrel_5mw_baseline', 'iea_15mw_rwt', 'ref_4mw_owt',
            'nrel_1.72_103', 'nrel_2.8_127', 'vestas_v27'
    tower : str
        Name of a tower template. Valid values:
            'nrel_5mw_tower', 'iea_15mw_tower', 'site_a_rt1_tower',
            'iea_land_onshore_tower'
    foundation : Foundation
        A Foundation handle from `build_foundation()`.
    damping_ratio : float
        Rayleigh structural damping ratio (fraction of critical).
        Default 0.01 (1%) matches most NREL reference decks.

    Returns
    -------
    TowerModel
        Not yet built. Call `model.eigen()` or `model.extract_6x6_stiffness()`
        which will trigger `.build()` internally.
    """
    valid_rotors = {
        'nrel_5mw_baseline', 'iea_15mw_rwt', 'ref_4mw_owt',
        'nrel_1.72_103', 'nrel_2.8_127', 'vestas_v27',
    }
    valid_towers = {
        'nrel_5mw_tower', 'nrel_5mw_oc3_tower', 'iea_15mw_tower',
        'site_a_rt1_tower', 'iea_land_onshore_tower',
    }
    if rotor not in valid_rotors:
        raise ValueError(f"Unknown rotor template '{rotor}'. "
                         f"Valid: {sorted(valid_rotors)}")
    if tower not in valid_towers:
        raise ValueError(f"Unknown tower template '{tower}'. "
                         f"Valid: {sorted(valid_towers)}")

    return TowerModel(
        rotor_name=rotor,
        tower_name=tower,
        foundation=foundation,
    )
