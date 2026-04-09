"""
Op^3 cross-comparison utility.

`cross_compare` runs a single (rotor, tower) combination across all
four foundation modes and a grid of scour depths, and returns a pandas
DataFrame with the results. This is the function that produces the
headline comparison tables in the dissertation and in the
FOUNDATION_MODE_STUDY.md document.

Usage:

    from op3 import cross_compare
    df = cross_compare(
        rotor='nrel_5mw_baseline',
        tower='site_a_rt1_tower',
        scour_levels=[0.0, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0],
        spring_profile='data/fem_results/opensees_spring_stiffness.csv',
        stiffness_matrix='data/fem_results/K_6x6_baseline.csv',
        ogx_dissipation='data/fem_results/dissipation_profile.csv',
    )
    print(df.pivot(index='scour_m', columns='mode', values='f1_Hz'))
"""
from __future__ import annotations

from typing import Sequence

import numpy as np
import pandas as pd

from op3.composer import compose_tower_model
from op3.foundations import build_foundation, FoundationMode


def cross_compare(
    rotor: str,
    tower: str,
    scour_levels: Sequence[float],
    *,
    spring_profile: str | None = None,
    stiffness_matrix: str | None = None,
    ogx_dissipation: str | None = None,
    modes: Sequence[str] | None = None,
) -> pd.DataFrame:
    """Run a cross-comparison of foundation modes and scour levels.

    Parameters
    ----------
    rotor : str
        Rotor template name (see composer.compose_tower_model).
    tower : str
        Tower template name.
    scour_levels : sequence of float
        Scour depths in meters.
    spring_profile : str, optional
        Path to the distributed-BNWF spring CSV. Required for Modes C and D.
    stiffness_matrix : str, optional
        Path to the 6x6 stiffness matrix CSV. Required for Mode B.
    ogx_dissipation : str, optional
        Path to the dissipation profile CSV. Required for Mode D.
    modes : sequence of str, optional
        Which modes to include. Default: all four.

    Returns
    -------
    pandas.DataFrame
        One row per (mode, scour_m) with columns:
            mode, scour_m, f1_Hz, f2_Hz, f3_Hz, integrated_K_kN_per_m,
            wall_clock_s
    """
    if modes is None:
        modes = [m.value for m in FoundationMode]

    rows = []
    for mode in modes:
        for scour in scour_levels:
            try:
                kwargs = dict(scour_depth=float(scour))
                if mode == FoundationMode.STIFFNESS_6X6.value:
                    if stiffness_matrix is None:
                        continue
                    kwargs["stiffness_matrix"] = stiffness_matrix
                elif mode in (FoundationMode.DISTRIBUTED_BNWF.value,
                              FoundationMode.DISSIPATION_WEIGHTED.value):
                    if spring_profile is None:
                        continue
                    kwargs["spring_profile"] = spring_profile
                    if mode == FoundationMode.DISSIPATION_WEIGHTED.value:
                        if ogx_dissipation is None:
                            continue
                        kwargs["ogx_dissipation"] = ogx_dissipation

                foundation = build_foundation(mode=mode, **kwargs)
                model = compose_tower_model(rotor=rotor, tower=tower,
                                            foundation=foundation)

                import time
                t0 = time.time()
                freqs = model.eigen(n_modes=3)
                elapsed = time.time() - t0

                rows.append(dict(
                    mode=mode,
                    scour_m=float(scour),
                    f1_Hz=float(freqs[0]) if len(freqs) > 0 else np.nan,
                    f2_Hz=float(freqs[1]) if len(freqs) > 1 else np.nan,
                    f3_Hz=float(freqs[2]) if len(freqs) > 2 else np.nan,
                    wall_clock_s=elapsed,
                    source=foundation.source,
                ))
            except Exception as e:
                rows.append(dict(
                    mode=mode,
                    scour_m=float(scour),
                    f1_Hz=np.nan,
                    f2_Hz=np.nan,
                    f3_Hz=np.nan,
                    wall_clock_s=np.nan,
                    source=f"ERROR: {e}",
                ))

    return pd.DataFrame(rows)
