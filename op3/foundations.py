"""
Op^3 foundation module factory.

This module exposes the four OpenSeesPy foundation representations that
differ in fidelity from "fixed base" (Mode A) to "dissipation-weighted
generalized BNWF" (Mode D). All four modes share the same tower
interface, so they can be swapped at runtime with a single flag.

The OpenSeesPy code that actually builds the springs and zero-length
elements lives in `op3.opensees_foundations.*`. This module is a thin
factory that picks the right builder based on the mode name.

The geotechnical/structural integration is the key contribution here:
the CSV schema produced by OptumGX (bearing capacity envelopes, contact
pressures, plastic dissipation fields) maps directly into the spring
parameters consumed by OpenSeesPy. Each mode uses a different subset of
this mapping.

Mode A (fixed):
    Does not use any OptumGX data. Fixes the tower base with `fix` on
    all six DOF.

Mode B (stiffness_6x6):
    Reads a 6x6 stiffness matrix from CSV and attaches it as a single
    zeroLength element at the tower base. The matrix is typically
    derived from OpenSeesPy Mode C or D via static condensation.

Mode C (distributed_bnwf):
    Reads depth-resolved spring stiffness and ultimate resistance from
    `opensees_spring_stiffness.csv` (produced by OptumGX) and builds
    a chain of lateral p-y and vertical t-z springs along the bucket
    skirt. Applies a stress-correction relief factor for scour.

Mode D (dissipation_weighted):
    Extends Mode C with a depth-dependent participation factor w(z)
    derived from the plastic dissipation field at collapse. This is
    the generalized cavity expansion framework of Appendix A of the
    dissertation.

Example
-------

>>> from op3 import build_foundation
>>> f = build_foundation(
...     mode='distributed_bnwf',
...     spring_profile='data/fem_results/opensees_spring_stiffness.csv',
...     scour_depth=1.5,
... )
>>> f.attach_to_opensees(base_node=1000)  # called by the composer
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd


class FoundationMode(str, Enum):
    """The four Op^3 foundation representations."""
    FIXED = "fixed"
    STIFFNESS_6X6 = "stiffness_6x6"
    DISTRIBUTED_BNWF = "distributed_bnwf"
    DISSIPATION_WEIGHTED = "dissipation_weighted"


@dataclass
class Foundation:
    """Opaque handle returned by `build_foundation`.

    The composer calls `attach_to_opensees(base_node)` at model-build
    time. The foundation is therefore described declaratively here and
    only touches OpenSees tags when the composer passes it a base
    node.
    """
    mode: FoundationMode
    # Depth-resolved spring table (Modes C, D)
    spring_table: Optional[pd.DataFrame] = None
    # 6x6 matrix (Mode B)
    stiffness_matrix: Optional[np.ndarray] = None
    # Dissipation weights (Mode D only)
    dissipation_weights: Optional[pd.DataFrame] = None
    # Mode D weighting parameters: w = beta + (1-beta) * (1 - D/D_max) ** alpha
    mode_d_alpha: float = 1.0
    mode_d_beta: float = 0.05
    # Scour depth applied at build time
    scour_depth: float = 0.0
    # Provenance: where did the data come from
    source: str = "analytical"
    # Diagnostic info filled at attach time
    diagnostics: dict = field(default_factory=dict)

    def attach_to_opensees(self, base_node: int) -> dict:
        """Instantiate the foundation as OpenSees elements and return
        a diagnostics dict.

        This is called by the composer at model-build time. The
        concrete OpenSees commands live in the opensees_foundations
        submodule because they require an active OpenSees model.

        Parameters
        ----------
        base_node : int
            The OpenSees node tag at the tower base that the
            foundation attaches to.

        Returns
        -------
        dict
            Diagnostic info: number of springs, integrated stiffness,
            energy balance check, etc.
        """
        # Delayed import so that pure-data use of Foundation objects
        # does not require OpenSeesPy to be installed.
        from op3.opensees_foundations import attach_foundation
        diag = attach_foundation(self, base_node)
        # Persist into the dataclass so callers (and V&V tests) can
        # inspect the weighting parameters that were actually applied.
        if isinstance(diag, dict):
            self.diagnostics.update(diag)
        return diag


def build_foundation(
    mode: str,
    *,
    spring_profile: Optional[str | Path] = None,
    stiffness_matrix: Optional[str | Path | np.ndarray] = None,
    ogx_dissipation: Optional[str | Path] = None,
    ogx_capacity: Optional[str | Path] = None,
    scour_depth: float = 0.0,
    mode_d_alpha: float = 1.0,
    mode_d_beta: float = 0.05,
) -> Foundation:
    """Construct a Foundation handle ready for the composer.

    Parameters
    ----------
    mode : str
        One of 'fixed', 'stiffness_6x6', 'distributed_bnwf',
        'dissipation_weighted'. Case-insensitive.
    spring_profile : str or Path, optional
        Path to a CSV with columns (depth_m, k_ini_kN_per_m,
        p_ult_kN_per_m, spring_type). Required for Modes C and D.
    stiffness_matrix : str, Path, or ndarray, optional
        A 6x6 stiffness matrix, either a path to a CSV or a NumPy
        array. Required for Mode B.
    ogx_dissipation : str or Path, optional
        Path to a CSV with columns (depth_m, w_z, D_total_kJ).
        Required for Mode D.
    ogx_capacity : str or Path, optional
        Path to the OptumGX power-law capacity CSV with columns
        (param_name, param_value). Used by Mode D for the ultimate
        resistance scaling.
    scour_depth : float, default 0.0
        Scour depth in meters. Affects Modes B, C, D.

    Returns
    -------
    Foundation
        An opaque handle the composer can attach to an OpenSees model.
    """
    try:
        mode_enum = FoundationMode(mode.lower())
    except ValueError:
        raise ValueError(
            f"Unknown foundation mode '{mode}'. "
            f"Expected one of {[m.value for m in FoundationMode]}."
        )

    foundation = Foundation(
        mode=mode_enum,
        scour_depth=scour_depth,
        mode_d_alpha=mode_d_alpha,
        mode_d_beta=mode_d_beta,
    )

    if mode_enum == FoundationMode.FIXED:
        foundation.source = "analytical (no data needed)"
        return foundation

    if mode_enum == FoundationMode.STIFFNESS_6X6:
        if stiffness_matrix is None:
            raise ValueError("Mode stiffness_6x6 requires stiffness_matrix argument")
        if isinstance(stiffness_matrix, (str, Path)):
            K = pd.read_csv(stiffness_matrix, header=None).values
            foundation.source = f"CSV: {stiffness_matrix}"
        else:
            K = np.asarray(stiffness_matrix)
            foundation.source = "ndarray (in-memory)"
        if K.shape != (6, 6):
            raise ValueError(f"stiffness_matrix must be 6x6, got {K.shape}")
        foundation.stiffness_matrix = K
        return foundation

    if mode_enum == FoundationMode.DISTRIBUTED_BNWF:
        if spring_profile is None:
            raise ValueError("Mode distributed_bnwf requires spring_profile argument")
        df = pd.read_csv(spring_profile)
        foundation.spring_table = df
        foundation.source = f"CSV: {spring_profile}"
        return foundation

    if mode_enum == FoundationMode.DISSIPATION_WEIGHTED:
        if spring_profile is None or ogx_dissipation is None:
            raise ValueError(
                "Mode dissipation_weighted requires both spring_profile and "
                "ogx_dissipation arguments"
            )
        df = pd.read_csv(spring_profile)
        foundation.spring_table = df
        foundation.dissipation_weights = pd.read_csv(ogx_dissipation)
        foundation.source = f"spring: {spring_profile}, dissipation: {ogx_dissipation}"
        return foundation

    raise RuntimeError(f"Unreachable — mode {mode_enum} not handled")


def apply_scour_relief(spring_table: pd.DataFrame, scour_depth: float) -> pd.DataFrame:
    """Apply a stress-relief factor to a spring table for a given scour depth.

    Rules:
      - Nodes above the scoured mudline (z < scour_depth) have zero stiffness
        and zero capacity (the soil is gone).
      - Nodes below but near the scour front have a smoothly tapered factor
        `relief(z) = sqrt((z - scour) / z)` to account for stress relief in
        the remaining soil column.
      - Nodes far below the scour front are unchanged.

    This is the stress-correction procedure from Chapter 6 of the
    dissertation and is mathematically identical to the factor documented
    in Appendix A Section A.3.
    """
    df = spring_table.copy()
    z = df["depth_m"].values
    relief = np.where(
        z < scour_depth,
        0.0,
        np.sqrt(np.clip((z - scour_depth) / np.maximum(z, 1e-6), 0.0, 1.0)),
    )
    for col in ("k_ini_kN_per_m", "p_ult_kN_per_m"):
        if col in df.columns:
            df[col] = df[col].values * relief
    return df


# ---------------------------------------------------------------------------
# PISA convenience: build a Mode B foundation directly from soil profile
# ---------------------------------------------------------------------------

def foundation_from_pisa(
    *,
    diameter_m: float,
    embed_length_m: float,
    soil_profile: list,
    n_segments: int = 50,
) -> Foundation:
    """
    Construct a STIFFNESS_6X6 Foundation whose K matrix is derived from
    the PISA framework (Burd 2020 / Byrne 2020). This is the canonical
    Op^3 entry point for monopile foundations when site-specific p-y
    curves are not available.

    Parameters
    ----------
    diameter_m, embed_length_m
        Pile geometry.
    soil_profile : list[op3.standards.pisa.SoilState]
        Layered soil definition (depth, G, su or phi, soil_type).
    n_segments
        Vertical discretisation for the PISA integration (default 50).
    """
    from op3.standards.pisa import pisa_pile_stiffness_6x6

    K = pisa_pile_stiffness_6x6(
        diameter_m=diameter_m,
        embed_length_m=embed_length_m,
        soil_profile=soil_profile,
        n_segments=n_segments,
    )
    foundation = Foundation(mode=FoundationMode.STIFFNESS_6X6)
    foundation.stiffness_matrix = K
    foundation.source = (
        f"PISA (Burd 2020 / Byrne 2020), D={diameter_m} m, "
        f"L={embed_length_m} m, {len(soil_profile)} soil layers"
    )
    return foundation

