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
