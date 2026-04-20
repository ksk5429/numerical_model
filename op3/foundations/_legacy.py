"""
LEGACY Op^3 foundation factory (frozen at v1.0).

This module is the original ``op3.foundations`` module moved verbatim
into a submodule of the new ``op3.foundations`` package. The public
API (``Foundation``, ``FoundationMode``, ``build_foundation``,
``apply_scour_relief``, ``foundation_from_pisa``) is preserved for
backwards compatibility and re-exported by ``op3.foundations.__init__``.

A :class:`DeprecationWarning` is emitted when ``build_foundation`` or
``FoundationMode`` is used, pointing to the new
:mod:`op3.foundations.types` API (``Monopile``, ``Tripod``, ``Jacket``,
``SuctionBucket``) introduced in v1.1+. The legacy path will remain
functional until the next major version bump.

The four original modes (A/B/C/D) represent **SSI fidelity levels**
(fixed / 6x6 / lumped-BNWF / dissipation-weighted BNWF) — they are
NOT foundation types. The new API separates the axes:

    FoundationType (Monopile, Tripod, Jacket, ...) x
    SSIStrategy   (Fixed, Stiffness6x6, BNWFLumped, BNWFPhysical, CraigBampton)

Concrete foundation topologies with their own mass, geometry, and
coupling interface now live under :mod:`op3.foundations.types`; SSI
strategies live under :mod:`op3.ssi`.
"""
from __future__ import annotations

import warnings
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd


class FoundationMode(str, Enum):
    """The five Op^3 foundation representations (LEGACY, frozen at v1.0).

    The first four are the original v1.0 fidelity ladder (Modes A-D).
    ``distributed_bnwf_nonlinear`` (v1.1+) is the blueprint Q1(a) primary:
    a physically-distributed skirt column with per-depth PySimple1/
    TzSimple1 backbones.

    **Deprecation notice (v1.1+):** these values represent SSI fidelity
    levels, not foundation types. New code should use the type/SSI
    split under :mod:`op3.foundations.types` and :mod:`op3.ssi`. The
    legacy ``build_foundation(mode=...)`` path remains functional
    throughout v1.x.
    """
    FIXED = "fixed"
    STIFFNESS_6X6 = "stiffness_6x6"
    DISTRIBUTED_BNWF = "distributed_bnwf"
    DISSIPATION_WEIGHTED = "dissipation_weighted"
    DISTRIBUTED_BNWF_NONLINEAR = "distributed_bnwf_nonlinear"


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
    # --- NOT a calibration ---
    # ``mode_d_alpha`` and ``mode_d_beta`` are SENSITIVITY-SWEEP parameters,
    # not fitted values. The pair (alpha=1.0, beta=0.05) is a nominal
    # starting point chosen for dimensional convenience (linear shape
    # function with a 5% floor so zero-dissipation zones retain numerical
    # stiffness). Users are expected to run a parameter study over alpha
    # in [0.5, 3] and beta in [0.01, 0.2] and report sensitivities. See
    # docs/MODE_D_DISSIPATION_WEIGHTED.md for the intended usage pattern.
    # Reference calibration against OptumG2 plastic-dissipation fields
    # remains future work (blueprint Week 11).
    mode_d_alpha: float = 1.0
    mode_d_beta: float = 0.05
    # Scour depth applied at build time
    scour_depth: float = 0.0
    # --- Physical-skirt geometry knobs (Modes C/D opt-in, C_nonlinear required) ---
    # Bucket outer diameter at skirt. Defaults to SiteA 4 MW reference (D=8 m).
    diameter_m: float = 8.0
    # Skirt embed length below mudline. If None, derived from
    # max(abs(depth_m)) of the spring table.
    skirt_length_m: Optional[float] = None
    # Skirt wall thickness (steel tube).
    skirt_thickness_m: float = 0.025
    # Opt-in flag: when True for Mode C / D, build the new physical
    # distributed-skirt model instead of the legacy lumped zero-length.
    # DISTRIBUTED_BNWF_NONLINEAR always uses the physical model.
    physical: bool = False
    # --- Physical-skirt PROXY knobs ---
    # The following ratios set base / shaft boundary conditions when an
    # OptumG2-calibrated base probe / t-z axial probe are not yet
    # available. Leaving ALL of them at None triggers a UserWarning at
    # attach time and falls back to the historical defaults below.
    # When the OptumG2 base probe and t-z axial probe are wired in
    # (blueprint Week 5) these will become required inputs.
    #
    # base_H_stiffness_fraction:  k_H_base / integrated_k_lateral
    #                             (default 0.1 — rigid-base proxy)
    # base_V_to_H_ratio:          k_V_base / k_H_base  (default 3.0)
    # shaft_t_to_p_ratio:         t_ult / p_ult        (default 0.5)
    # shaft_kz_to_kx_ratio:       k_vertical / k_lateral (default 0.5)
    # missing_pult_fallback_factor: p_ult = factor * k_ini when p_ult
    #                             column is absent from the spring table
    #                             (default 10.0)
    base_H_stiffness_fraction: Optional[float] = None
    base_V_to_H_ratio: Optional[float] = None
    shaft_t_to_p_ratio: Optional[float] = None
    shaft_kz_to_kx_ratio: Optional[float] = None
    missing_pult_fallback_factor: Optional[float] = None
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
    diameter_m: float = 8.0,
    skirt_length_m: Optional[float] = None,
    skirt_thickness_m: float = 0.025,
    physical: bool = False,
    _suppress_deprecation_warning: bool = False,
) -> Foundation:
    """Construct a Foundation handle ready for the composer (LEGACY API).

    **Deprecated (v1.1+):** use :mod:`op3.foundations.types` and
    :mod:`op3.ssi` for new code. Example:

    >>> from op3.foundations.types import Monopile
    >>> from op3.ssi import Stiffness6x6
    >>> mono = Monopile.from_oc3_spec(soil_profile=...)
    >>> mono.with_ssi(Stiffness6x6(K=mono.head_stiffness_6x6()))

    Parameters
    ----------
    mode : str
        One of 'fixed', 'stiffness_6x6', 'distributed_bnwf',
        'dissipation_weighted', 'distributed_bnwf_nonlinear'.
        Case-insensitive.
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
    _suppress_deprecation_warning : bool
        Internal flag used by ``op3.foundations.types`` adapters to
        avoid spurious deprecation noise on the back-compat bridge.
    """
    if not _suppress_deprecation_warning:
        warnings.warn(
            "op3.foundations.build_foundation (and FoundationMode) are "
            "frozen at v1.0 and will be removed in v2.0. Use the new "
            "type/SSI split: op3.foundations.types.{Monopile,Tripod,"
            "Jacket,SuctionBucket} + op3.ssi.{Fixed,Stiffness6x6,"
            "BNWFLumped,BNWFPhysical,CraigBampton}. See "
            "op3/models/<name>/build.py for reference use.",
            DeprecationWarning,
            stacklevel=2,
        )

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
        diameter_m=diameter_m,
        skirt_length_m=skirt_length_m,
        skirt_thickness_m=skirt_thickness_m,
        physical=physical,
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

    if mode_enum == FoundationMode.DISTRIBUTED_BNWF_NONLINEAR:
        if spring_profile is None:
            raise ValueError(
                "Mode distributed_bnwf_nonlinear requires spring_profile argument"
            )
        df = pd.read_csv(spring_profile)
        foundation.spring_table = df
        # Physical is implicit for the nonlinear mode.
        foundation.physical = True
        foundation.source = f"CSV: {spring_profile} (PySimple1/TzSimple1 backbones)"
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
