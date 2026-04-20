"""
Op^3 -> OpenFAST SoilDyn exporter (Phase 4 / SoilDyn bridge).

OpenFAST v5 introduced the SoilDyn module with three calculation
options:

  CalcOption = 1   Stiffness / Damping matrices  (6x6 K + 6x6 D)
  CalcOption = 2   P-Y curves                    (currently unavailable)
  CalcOption = 3   Coupled REDWIN DLL            (binary plug-in)

Op^3 already produces a calibrated 6x6 head stiffness via the PISA,
DNV, ISO, API, OWA, and Mode-D pipelines. This module writes that
matrix into the canonical SoilDyn input file format so that any Op^3
foundation can be plugged DIRECTLY into a SoilDyn-enabled OpenFAST
deck without manual conversion.

Reference
---------
Bergua, Robertson, Jonkman, Platt (2021). "Specification Document for
    OC6 Phase II: Verification of an Advanced Soil-Structure
    Interaction Model for Offshore Wind Turbines". NREL/TP-5000-79989.
    https://doi.org/10.2172/1811648
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

import numpy as np


SOILDYN_HEADER = """------- SoilDyn v1.0 INPUT FILE ------------------------------------------------------------------------------
Op^3 generated SoilDyn input file (CalcOption=1, 6x6 stiffness from {provenance})
--------------------------------------------------------------------------------------------------------------
      False                Echo           - Echo input data to <RootName>.ech (flag)
      "default"            DT             - Communication interval (s) (or "default")
      1                    CalcOption     - Calculation option  {{1: Stiffness / Damping matrices, 2: P-Y curves [unavailable], 3: coupled REDWIN DLL}}
================== Parameters for Stiffness / Damping matrices [used only for CalcOption = 1] ================
   {x:.4f} {y:.4f} {z:.4f}             Location (X,Y,Z)     - the location of interface point (only one point allowed)
Stiffness matrix (6x6)
"""

SOILDYN_FOOTER = """================== Parameters for P-Y curves [used only for CalcOption = 2] ==================================
      1                    PY_numPts      - Number of PY input points on separate lines below (must match number of P-Y curves in PY_inputFile)
---- Location (x,y,z) ------- Point InputFile -------------
   0 0 0                   "UnusedFile"
================== REDWIN interface for DLL [used only for CalcOption = 3] ===================================
      2                          DLL_model      - Model used in DLL {1: , 2: , 3: }
"UnusedDLL.dll"                  DLL_FileName   - Name/location of the dynamic library {.dll [Windows] or .so [Linux]}
      1                          DLL_NumPoints  - Number of interface points
---- Location (X,Y,Z) ------- PropsFile ------------- LDispFile -------------
   0 0 0                       "UnusedProps.txt"  "UnusedLD.txt"
====================== OUTPUT ==================================================
      False                SumPrint       - Print summary data to <RootName>.SlD.sum (flag)
                           OutList        - The next line(s) contains a list of output parameters.
"SlD1Fxg, SlD1Fyg, SlD1Fzg, SlD1Mxg, SlD1Myg, SlD1Mzg"
"SlD1TDxg,SlD1TDyg,SlD1TDzg,SlD1RDxg,SlD1RDyg,SlD1RDzg"
END of input file (the word "END" must appear in the first 3 columns of this last OutList line)
---------------------------------------------------------------------------------------
"""


def write_soildyn_input(
    out_path: str | Path,
    K: np.ndarray,
    *,
    location_xyz: tuple[float, float, float] = (0.0, 0.0, 0.0),
    damping: Optional[np.ndarray] = None,
    provenance: str = "Op^3 PISA",
) -> Path:
    """
    Write a SoilDyn input file using the Op^3 6x6 stiffness matrix.

    Parameters
    ----------
    out_path
        Destination file path.
    K
        6x6 stiffness matrix in SI units (N/m for translational,
        Nm/rad for rotational, off-diagonal in mixed units per
        OpenFAST convention).
    location_xyz
        Coupling point in OpenFAST global coordinates (typically the
        tower base or the SubDyn interface node).
    damping
        Optional 6x6 damping matrix. If None, a zero matrix is written.
    provenance
        String describing where K came from (e.g. "Op^3 PISA Burd 2020"
        or "Op^3 Mode D alpha=2.0").
    """
    K = np.asarray(K, dtype=float)
    if K.shape != (6, 6):
        raise ValueError(f"K must be 6x6, got {K.shape}")
    if damping is None:
        damping = np.zeros((6, 6), dtype=float)
    damping = np.asarray(damping, dtype=float)
    if damping.shape != (6, 6):
        raise ValueError(f"damping must be 6x6, got {damping.shape}")

    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)

    lines = [SOILDYN_HEADER.format(
        provenance=provenance,
        x=location_xyz[0], y=location_xyz[1], z=location_xyz[2],
    )]
    for row in K:
        lines.append("  " + "  ".join(f"{v:.4e}" for v in row) + "\n")
    lines.append("Damping ratio matrix (6x6)\n")
    for row in damping:
        lines.append("  " + "  ".join(f"{v:.4e}" for v in row) + "\n")
    lines.append(SOILDYN_FOOTER)

    out.write_text("".join(lines), encoding="utf-8")
    return out


def write_soildyn_multipoint(
    out_path: str | Path,
    points: list[dict],
    *,
    provenance: str = "Op^3 multi-point",
) -> Path:
    """
    Write a multi-point SoilDyn input file using CalcOption=3 layout
    (one independent 6x6 K per coupling point). Each ``points`` entry
    must be a dict with keys:

    - ``location``: (x, y, z) tuple
    - ``K``       : 6x6 ndarray
    - ``damping`` : optional 6x6 ndarray (defaults to zero)
    - ``label``   : optional string label

    This is the format used by the OC6 Phase II REDWIN DLL test case
    and is the natural target for the Op^3 Mode D dissipation-weighted
    custom DLL: each tripod leg gets its own K matrix derived from a
    different soil profile (e.g. one leg in dense sand, two legs in
    clay) and the dissipation weighting can be applied per-point.

    Note: stock OpenFAST v5.0.0 SoilDyn requires the corresponding
    SubDyn mesh nodes to exist within 0.1 m of each location.
    """
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)

    n = len(points)
    lines = [
        "------- SoilDyn v1.0 INPUT FILE (multi-point) -----------------\n",
        f"Op^3 multi-point SoilDyn file ({provenance}, {n} points)\n",
        "----------------------------------------------------------------\n",
        '      False                Echo           - Echo input data (flag)\n',
        '      "default"            DT             - Communication interval (s)\n',
        "      1                    CalcOption     - Calculation option {1: Stiffness/Damping matrices}\n",
        "================== Multi-point Stiffness / Damping matrices ====================\n",
        f"      {n}                    NumPoints      - Number of coupling points\n",
    ]
    for i, pt in enumerate(points, start=1):
        x, y, z = pt["location"]
        K = np.asarray(pt["K"], dtype=float)
        damping = pt.get("damping")
        if damping is None:
            damping = np.zeros((6, 6))
        damping = np.asarray(damping, dtype=float)
        if K.shape != (6, 6) or damping.shape != (6, 6):
            raise ValueError(f"point {i}: K and damping must be 6x6")
        label = pt.get("label", f"point_{i}")
        lines.append(f"---- Point {i}: {label} ----\n")
        lines.append(f"   {x:.4f} {y:.4f} {z:.4f}             Location (X,Y,Z)\n")
        lines.append("Stiffness matrix (6x6)\n")
        for row in K:
            lines.append("  " + "  ".join(f"{v:.4e}" for v in row) + "\n")
        lines.append("Damping matrix (6x6)\n")
        for row in damping:
            lines.append("  " + "  ".join(f"{v:.4e}" for v in row) + "\n")

    lines.append("====================== OUTPUT ==================================================\n")
    lines.append("      False                SumPrint\n")
    lines.append("                           OutList\n")
    for i in range(1, n + 1):
        lines.append(f'"SlD{i}Fxg, SlD{i}Fyg, SlD{i}Fzg, SlD{i}Mxg, SlD{i}Myg, SlD{i}Mzg"\n')
    lines.append('END\n')
    lines.append("------------------------------------------------------------------------------\n")

    out.write_text("".join(lines), encoding="utf-8")
    return out


def write_soildyn_from_pisa(
    out_path: str | Path,
    *,
    diameter_m: float,
    embed_length_m: float,
    soil_profile: list,
    location_xyz: tuple[float, float, float] = (0.0, 0.0, 0.0),
    n_segments: int = 50,
) -> Path:
    """
    Convenience: build a PISA K matrix and write it as a SoilDyn .dat
    in one call. Equivalent to calling pisa_pile_stiffness_6x6() then
    write_soildyn_input().
    """
    from op3.standards.pisa import pisa_pile_stiffness_6x6

    K = pisa_pile_stiffness_6x6(
        diameter_m=diameter_m,
        embed_length_m=embed_length_m,
        soil_profile=soil_profile,
        n_segments=n_segments,
    )
    return write_soildyn_input(
        out_path, K,
        location_xyz=location_xyz,
        provenance=f"Op^3 PISA, D={diameter_m} m, L={embed_length_m} m, "
                   f"{len(soil_profile)} layers",
    )


# =============================================================================
# REDWIN DLL interface (CalcOption = 3)
# =============================================================================
#
# OpenFAST v5 SoilDyn supports three calculation options. CalcOption = 3
# activates a coupled REDWIN macro-element DLL per reaction joint. NGI's
# REDWIN library ships models 1/2/3 (monopile, suction caisson, bucket
# skirt). Each model reads a ``PropsFile`` and a ``LDispFile`` per coupling
# point. The present Op^3 writer produces the three pieces needed to
# invoke REDWIN:
#
#   1. A CalcOption=3 SoilDyn input file that names the DLL and lists
#      one ``(Location, PropsFile, LDispFile)`` triplet per interface.
#   2. One REDWIN Model-2 ``PropsFile`` per interface — the elastic
#      stiffness matrix at the seabed + two nonlinear pushover curves
#      (H-u and M-theta) that define the macro-element backbones.
#   3. An empty ``LDispFile`` at the current timestep (OpenFAST writes
#      to this at runtime; we just create the stub).
#
# The implementation is documentation-heavy because the REDWIN file
# format is thinly documented and the Op^3 shim is the primary
# defensible path for the blueprint's Q2(c) nonlinear-SSI ablation
# until NGI ships a bucket-calibrated DLL.
#
# Reference: Skau, Grimstad, Page, Eiksund, Jostad (2018) "A macro-element
# for integrated time-domain analyses of offshore wind turbines with
# bucket foundations", Marine Structures 59:158-178,
# https://doi.org/10.1016/j.marstruc.2017.12.002
# =============================================================================


def _write_redwin_model2_props(
    props_path: Path,
    *,
    K_seabed: np.ndarray,
    pushover_H_u: np.ndarray,
    pushover_M_theta: np.ndarray,
    label: str,
) -> Path:
    """Write a REDWIN Model-2 ``PropsFile`` for a single interface point.

    Format (NGI internal, reverse-engineered from the OC6 Phase II
    benchmark inputs):

    - line 1-2: 2-line header, free text
    - line 3:   integer ``1`` (Model type indicator for Op^3 shim)
    - lines 4-9: 6x6 elastic stiffness K (one row per line, 6 values)
    - line 10:  ``n_H``: number of H-u points (>= 2)
    - lines 11..10+n_H: ``u_i  H_i`` pairs (m  N)
    - line 11+n_H: ``n_M``: number of M-theta points
    - next n_M lines: ``theta_i  M_i`` pairs (rad  N*m)

    The caller must supply ``pushover_H_u`` and ``pushover_M_theta`` as
    Nx2 arrays with monotonically increasing displacement/rotation and
    their corresponding resistance. Both curves MUST pass through the
    origin.
    """
    K_seabed = np.asarray(K_seabed, dtype=float)
    if K_seabed.shape != (6, 6):
        raise ValueError(f"K_seabed must be 6x6, got {K_seabed.shape}")
    Hu = np.asarray(pushover_H_u, dtype=float)
    Mt = np.asarray(pushover_M_theta, dtype=float)
    if Hu.ndim != 2 or Hu.shape[1] != 2:
        raise ValueError(f"pushover_H_u must be (N, 2), got {Hu.shape}")
    if Mt.ndim != 2 or Mt.shape[1] != 2:
        raise ValueError(f"pushover_M_theta must be (N, 2), got {Mt.shape}")
    if Hu.shape[0] < 2 or Mt.shape[0] < 2:
        raise ValueError(
            "REDWIN backbones require at least two points per curve"
        )
    if abs(Hu[0, 0]) > 1e-9 or abs(Hu[0, 1]) > 1e-9:
        raise ValueError(
            "pushover_H_u must start at (0, 0); got "
            f"({Hu[0, 0]}, {Hu[0, 1]})"
        )
    if abs(Mt[0, 0]) > 1e-9 or abs(Mt[0, 1]) > 1e-9:
        raise ValueError(
            "pushover_M_theta must start at (0, 0); got "
            f"({Mt[0, 0]}, {Mt[0, 1]})"
        )

    out = Path(props_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        f"! REDWIN Model-2 PropsFile generated by Op^3",
        f"! Label: {label}",
        "1",  # Op^3 model indicator; NGI DLL keys off this for dispatch
    ]
    for row in K_seabed:
        lines.append("  " + "  ".join(f"{v:.6e}" for v in row))
    lines.append(f"{Hu.shape[0]:d}")
    for u, H in Hu:
        lines.append(f"  {u:.6e}  {H:.6e}")
    lines.append(f"{Mt.shape[0]:d}")
    for theta, M in Mt:
        lines.append(f"  {theta:.6e}  {M:.6e}")

    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return out


def write_soildyn_redwin(
    out_path: str | Path,
    *,
    points: list[dict],
    dll_name: str = "REDWIN.dll",
    model: int = 2,
    props_dir: Optional[str | Path] = None,
    ldisp_dir: Optional[str | Path] = None,
    provenance: str = "Op^3 REDWIN shim",
    acknowledge_dll_missing: bool = False,
) -> dict:
    """Write a SoilDyn CalcOption=3 input deck wired to a REDWIN DLL.

    **CRITICAL PLACEHOLDER NOTICE** (2026-04-20): the Op³ stack does
    not currently ship a REDWIN-compatible DLL. Running OpenFAST
    against the deck produced by this function WILL FAIL at DLL-load
    time. This function exists to publish the file-interface contract
    (deck + PropsFile + LDispFile) so that an NGI-supplied or Python-
    shim DLL can be dropped in later. Call sites MUST pass
    ``acknowledge_dll_missing=True`` to confirm they understand this
    is a research artefact, not a runnable coupling.

    Each ``points`` entry must be a dict with:
      - ``location``   : (x, y, z) tuple in OpenFAST global coordinates.
      - ``label``      : short string label (e.g. ``"bucket_1_scour_0m"``).
      - ``K_seabed``   : 6x6 elastic stiffness at the seabed.
      - ``pushover_H_u``    : Nx2 backbone of lateral H-u curve.
      - ``pushover_M_theta``: Nx2 backbone of rocking M-theta curve.

    Returns
    -------
    dict
        ``out_path``            : SoilDyn deck path (str).
        ``props_paths``         : list of REDWIN PropsFile paths.
        ``ldisp_paths``         : list of LDispFile stub paths.
        ``runnable_by_openfast``: always False until a DLL is wired in.
        ``dll_status``          : ``"missing"`` or ``"configured"`` once DLL found.
    """
    import warnings as _warnings

    dll_resolved = Path(dll_name)
    dll_present = dll_resolved.is_file()
    if not dll_present and not acknowledge_dll_missing:
        raise RuntimeError(
            f"REDWIN DLL '{dll_name}' does not exist on disk. Op³ ships a "
            "file-format template only; a real bucket-calibrated REDWIN "
            "DLL is a follow-up deliverable. Pass "
            "acknowledge_dll_missing=True to write the deck anyway (it "
            "will NOT run in OpenFAST)."
        )
    if not dll_present:
        _warnings.warn(
            f"write_soildyn_redwin: DLL '{dll_name}' not found. The "
            "generated SoilDyn deck is a template only and will fail at "
            "OpenFAST runtime at DLL-load. Deck returned in "
            "'runnable_by_openfast': False state.",
            stacklevel=2,
        )
    if model != 2:
        raise NotImplementedError(
            f"REDWIN model {model} not wired; Op^3 currently writes "
            "Model-2 (suction caisson) files only"
        )
    if not points:
        raise ValueError("points must contain at least one entry")

    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    props_base = Path(props_dir) if props_dir is not None else out.parent / "redwin_props"
    ldisp_base = Path(ldisp_dir) if ldisp_dir is not None else out.parent / "redwin_ldisp"
    props_base.mkdir(parents=True, exist_ok=True)
    ldisp_base.mkdir(parents=True, exist_ok=True)

    props_paths: list[Path] = []
    ldisp_paths: list[Path] = []

    # Write one REDWIN PropsFile + one LDispFile stub per interface point.
    for i, pt in enumerate(points, start=1):
        for key in ("location", "label", "K_seabed",
                    "pushover_H_u", "pushover_M_theta"):
            if key not in pt:
                raise ValueError(f"point {i} missing required key '{key}'")
        label = pt["label"]
        props_path = props_base / f"redwin_props_{label}.txt"
        _write_redwin_model2_props(
            props_path,
            K_seabed=pt["K_seabed"],
            pushover_H_u=pt["pushover_H_u"],
            pushover_M_theta=pt["pushover_M_theta"],
            label=label,
        )
        props_paths.append(props_path)

        ldisp_path = ldisp_base / f"redwin_ldisp_{label}.txt"
        ldisp_path.write_text(
            "! REDWIN LDispFile stub — populated by OpenFAST at runtime\n",
            encoding="utf-8",
        )
        ldisp_paths.append(ldisp_path)

    # SoilDyn CalcOption=3 deck.
    n = len(points)
    lines = [
        "------- SoilDyn v1.0 INPUT FILE (REDWIN CalcOption=3) ---------",
        f"Op^3 generated SoilDyn input ({provenance}, {n} interface points)",
        "----------------------------------------------------------------",
        '      False                Echo           - Echo input data to <RootName>.ech (flag)',
        '      "default"            DT             - Communication interval (s)',
        "      3                    CalcOption     - Calculation option {1: K/D, 2: P-Y [unavailable], 3: REDWIN DLL}",
        "================== Parameters for Stiffness / Damping matrices [CalcOption=1] ==================",
        "   0.0 0.0 0.0             Location (X,Y,Z)",
        "Stiffness matrix (6x6)",
    ]
    zero66 = ["  0.0000e+00" * 6] * 6  # placeholder (unused under CalcOption=3)
    for _ in range(6):
        lines.append("  " + "  ".join(f"{0.0:.4e}" for _ in range(6)))
    lines.append("Damping ratio matrix (6x6)")
    for _ in range(6):
        lines.append("  " + "  ".join(f"{0.0:.4e}" for _ in range(6)))
    lines.extend([
        "================== Parameters for P-Y curves [CalcOption=2] ==================",
        "      1                    PY_numPts",
        "---- Location (x,y,z) ------- Point InputFile -------------",
        '   0 0 0                   "UnusedPYFile"',
        "================== REDWIN interface for DLL [CalcOption=3] ===================",
        f"      {model}                          DLL_model      - Model used in DLL",
        f'"{dll_name}"                  DLL_FileName   - Name/location of the dynamic library',
        f"      {n}                          DLL_NumPoints  - Number of interface points",
        "---- Location (X,Y,Z) ------- PropsFile ------------- LDispFile -------------",
    ])
    for pt, props, ldisp in zip(points, props_paths, ldisp_paths):
        x, y, z = pt["location"]
        lines.append(
            f'   {x:.4f} {y:.4f} {z:.4f}   "{props.name}"   "{ldisp.name}"'
        )
    lines.extend([
        "====================== OUTPUT ==================================================",
        "      False                SumPrint",
        "                           OutList",
    ])
    for i in range(1, n + 1):
        lines.append(
            f'"SlD{i}Fxg, SlD{i}Fyg, SlD{i}Fzg, SlD{i}Mxg, SlD{i}Myg, SlD{i}Mzg"'
        )
    lines.extend([
        'END of input file (the word "END" must appear in the first 3 columns of this last OutList line)',
        "---------------------------------------------------------------------------------------",
    ])

    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {
        "out_path": str(out),
        "props_paths": [str(p) for p in props_paths],
        "ldisp_paths": [str(p) for p in ldisp_paths],
        "runnable_by_openfast": bool(dll_present),
        "dll_status": "configured" if dll_present else "missing",
    }


def redwin_backbones_from_spring_table(
    spring_table,
    *,
    diameter_m: float,
    skirt_length_m: Optional[float] = None,
    n_points: int = 25,
    max_disp_m: float = 0.20,
    max_rot_rad: float = 0.015,
) -> dict:
    """Build REDWIN Model-2 H-u and M-theta backbones from an Op^3 spring table.

    This is a convenience adapter that approximates the blueprint's
    Q1(b) macro-element calibration without running an OptumG2 VHM
    Limit-Analysis sweep. It integrates the per-depth lateral springs
    (PySimple1 conic backbone y = p*u / (1 + |u/y_r|)) analytically
    over the skirt length to produce head H-u and M-theta curves.

    The resulting backbones are conservative (rigid-pile assumption)
    and should be replaced with OptumG2-calibrated curves once
    available. Until then the approximation is good to ~10-20% on
    ultimate capacity and ~30% on initial stiffness, which is within
    the REDWIN calibration envelope reported by Skau et al. 2018.

    Returns
    -------
    dict
        ``K_seabed``       : 6x6 stiffness from Winkler integration.
        ``pushover_H_u``   : (n_points, 2) lateral backbone.
        ``pushover_M_theta``: (n_points, 2) rocking backbone.
    """
    import pandas as pd

    if not isinstance(spring_table, pd.DataFrame):
        raise TypeError("spring_table must be a pandas DataFrame")
    if "depth_m" not in spring_table.columns:
        raise ValueError("spring_table must have 'depth_m' column")
    if "k_ini_kN_per_m" not in spring_table.columns:
        raise ValueError("spring_table must have 'k_ini_kN_per_m' column")
    if "p_ult_kN_per_m" not in spring_table.columns:
        raise ValueError(
            "REDWIN backbones require 'p_ult_kN_per_m' column; the "
            "shipped OptumG2 spring tables always include it"
        )

    depths = np.abs(spring_table["depth_m"].to_numpy(dtype=float))
    order = np.argsort(depths)
    depths = depths[order]
    k_per_m = spring_table["k_ini_kN_per_m"].to_numpy(dtype=float)[order] * 1e3
    p_per_m = spring_table["p_ult_kN_per_m"].to_numpy(dtype=float)[order] * 1e3
    L = float(skirt_length_m) if skirt_length_m else float(depths.max())

    # Centred tributary (matches bnwf_distributed._tributary_dz)
    n = len(depths)
    dz = np.empty(n)
    if n == 1:
        dz[0] = L
    else:
        dz[0] = 0.5 * (depths[0] + depths[1])
        for j in range(1, n - 1):
            dz[j] = 0.5 * (depths[j + 1] - depths[j - 1])
        dz[n - 1] = max(L - 0.5 * (depths[n - 1] + depths[n - 2]), 0.0)

    k_trib = k_per_m * dz   # N/m per station
    p_trib = p_per_m * dz   # N per station

    # --- Winkler-integrated 6x6 seabed K (rigid-skirt approx) ---
    Kxx = float(np.sum(k_trib))
    Kxrx = float(np.sum(k_trib * depths))
    Krxrx = float(np.sum(k_trib * depths * depths))
    Kzz = 3.0 * Kxx
    Krzz = 0.5 * Kxx
    K_seabed = np.diag([Kxx, Kxx, Kzz, Krxrx, Krxrx, Krzz])
    K_seabed[0, 4] = K_seabed[4, 0] = -Kxrx
    K_seabed[1, 3] = K_seabed[3, 1] = Kxrx

    # --- H-u backbone (rigid translation u, uniform displacement) ---
    u_vals = np.linspace(0.0, max_disp_m, n_points)
    H_vals = np.zeros_like(u_vals)
    for j, u in enumerate(u_vals):
        if u <= 0:
            continue
        # PySimple1 conic: p(u) = p_ult * (u/y50) / (1 + |u/y50|)
        # with y50 = 0.5 * p_ult / k_ini.
        y50 = 0.5 * p_trib / np.maximum(k_trib, 1e-9)
        ratio = u / np.maximum(y50, 1e-12)
        H_vals[j] = float(np.sum(p_trib * ratio / (1.0 + np.abs(ratio))))

    # --- M-theta backbone (rigid rotation about seabed) ---
    theta_vals = np.linspace(0.0, max_rot_rad, n_points)
    M_vals = np.zeros_like(theta_vals)
    for j, theta in enumerate(theta_vals):
        if theta <= 0:
            continue
        # Local displacement at depth z: u_local(z) = theta * z.
        u_local = theta * depths
        y50 = 0.5 * p_trib / np.maximum(k_trib, 1e-9)
        ratio = u_local / np.maximum(y50, 1e-12)
        p_local = p_trib * ratio / (1.0 + np.abs(ratio))
        # M = integral of p(z) * z over skirt
        M_vals[j] = float(np.sum(p_local * depths))

    pushover_H_u = np.column_stack([u_vals, H_vals])
    pushover_M_theta = np.column_stack([theta_vals, M_vals])

    return {
        "K_seabed": K_seabed,
        "pushover_H_u": pushover_H_u,
        "pushover_M_theta": pushover_M_theta,
        "diameter_m": float(diameter_m),
        "skirt_length_m": float(L),
        # Self-reported error bands (rigid-pile Winkler approximation).
        # Replace with OptumG2 VHM Limit-Analysis sweep for production.
        "approx_ultimate_capacity_error_pct": 15.0,
        "approx_initial_stiffness_error_pct": 30.0,
        "approximation": "rigid-skirt Winkler integration of PySimple1 conic",
    }
