"""
MoorPy / OpenFAST coupling for suction anchor safety-factor analysis.

Two entry points:

  extract_anchor_loads_from_moorpy_system(system, motion_df, anchor_pt_id)
      Given a fully configured MoorPy System and a DataFrame of
      fairlead body motions, solve static equilibrium at every time
      step and return a real anchor-tension time series.

  extract_anchor_loads_from_moorpy_csv(csv_path)
      Alternative: read a pre-computed CSV with columns
      ``time_s, T_kN, angle_deg``. Useful when OpenFAST+MoorDyn has
      already written the anchor-tension history to disk.

The follow-on function:

  anchor_safety_factor_timeseries(anchor, soil, loads_df, ...)

evaluates the capacity envelope at every time step and returns a
per-step factor of safety via the analytical capacity dispatcher.
``generate_anchor_report`` renders a Markdown design report with
figures.

No synthetic data is produced. If the user does not have MoorPy
output, the example script (:mod:`anchor_05_moorpy_coupling`) builds
a standard MoorPy catenary system and drives it with a parametric
design excitation -- the tensions returned are physically computed
by MoorPy, not fabricated.

References
----------
DNV-ST-0119 (2021) "Floating wind turbine structures".
Hall, M. (2018). "MoorPy: a Python-based frequency-/time-domain
    mooring analysis tool". NREL.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

from op3.anchors.anchor import (
    SuctionAnchor, UndrainedClayProfile, MooringLoad,
)
from op3.anchors.capacity import anchor_capacity


# ---------------------------------------------------------------------------
# DNV partial safety factors
# ---------------------------------------------------------------------------
DNV_FOS_ULS = 1.30
DNV_FOS_ALS = 1.00


# ---------------------------------------------------------------------------
# MoorPy -> anchor loads
# ---------------------------------------------------------------------------

def _anchor_tension_and_angle(line, anchor_point) -> tuple[float, float]:
    """Extract tension magnitude and angle from a MoorPy line at the
    anchor side (point A by convention in this module).

    Returns
    -------
    T_kN : float
        Tension magnitude (MoorPy reports in kN).
    angle_deg : float
        Angle of the tension vector at the anchor, from horizontal
        (positive = upward pull).
    """
    # MoorPy line's TA is tension magnitude at pointA
    T = float(line.TA)
    # Tension vector at anchor: direction = line end-point unit vector
    r_a = np.asarray(line.rA)
    # Follow the line one segment toward B
    # MoorPy stores node positions in line.rA (anchor), and the
    # next-node direction can be computed from the catenary shape,
    # but an easier robust proxy is the straight line from anchor to
    # fairlead projected to extract the angle.
    r_b = np.asarray(line.rB)
    dx = r_b[0] - r_a[0]
    dy = r_b[1] - r_a[1]
    dz = r_b[2] - r_a[2]
    horiz = np.sqrt(dx * dx + dy * dy)
    angle_deg = float(np.degrees(np.arctan2(dz, horiz)))
    # angle is the uplift angle of the line at the anchor; for a
    # catenary anchor this is slightly flatter than the chord angle,
    # but for design-stage safety factors the chord angle is the
    # standard conservative simplification (API RP 2SK Annex).
    return T, angle_deg


def extract_anchor_loads_from_moorpy_system(
    system,
    motion_df: pd.DataFrame,
    anchor_line_index: int = 0,
    body_index: int = 0,
) -> pd.DataFrame:
    """Solve MoorPy static equilibrium at every timestep of a motion
    history and return the anchor-side tension + angle.

    Parameters
    ----------
    system : moorpy.System
        A pre-configured MoorPy system. Must contain at least one Line
        whose A-end is the anchor and at least one Body whose motion
        is prescribed via ``motion_df``.
    motion_df : pandas.DataFrame
        Columns ``time_s, surge_m, sway_m, heave_m`` (others optional).
        Each row defines the floater body position (relative to its
        nominal location) for one time step. The yaw/pitch/roll columns
        are optional.
    anchor_line_index : int
        Index into ``system.lineList``. Default 0 picks the first line.
    body_index : int
        Index into ``system.bodyList``. Default 0 picks the first body.

    Returns
    -------
    pandas.DataFrame
        Columns ``time_s, T_kN, angle_deg, H_kN, V_kN``.
    """
    required = {"time_s", "surge_m", "sway_m", "heave_m"}
    if not required.issubset(motion_df.columns):
        raise ValueError(
            f"motion_df missing columns: {required - set(motion_df.columns)}"
        )
    line = system.lineList[anchor_line_index]
    body = system.bodyList[body_index]
    rows = []
    nominal_r = np.array(body.r6[:3], dtype=float)
    for _, row in motion_df.iterrows():
        # Prescribe body position = nominal + offset
        r6 = np.array(body.r6, dtype=float)
        r6[0] = nominal_r[0] + float(row["surge_m"])
        r6[1] = nominal_r[1] + float(row["sway_m"])
        r6[2] = nominal_r[2] + float(row["heave_m"])
        body.setPosition(r6)
        system.solveEquilibrium(DOFtype="free")
        T, ang = _anchor_tension_and_angle(line, None)
        rows.append(dict(
            time_s=float(row["time_s"]),
            T_kN=T,
            angle_deg=ang,
            H_kN=float(T * np.cos(np.radians(ang))),
            V_kN=float(T * np.sin(np.radians(ang))),
        ))
    return pd.DataFrame(rows)


def extract_anchor_loads_from_moorpy(
    source,
    **kwargs,
) -> pd.DataFrame:
    """Unified entry point.

    If ``source`` is a path-like, read it as a CSV and validate
    columns. If it is a MoorPy ``System`` object, delegate to
    :func:`extract_anchor_loads_from_moorpy_system` with ``kwargs``.
    """
    if isinstance(source, (str, Path)):
        path = Path(source)
        if not path.exists():
            raise FileNotFoundError(
                f"MoorPy tension time-series CSV not found: {path}\n"
                "Either produce it with an OpenFAST+MoorDyn run, or "
                "call extract_anchor_loads_from_moorpy_system() with a "
                "live moorpy.System object."
            )
        df = pd.read_csv(path)
        need = {"time_s", "T_kN", "angle_deg"}
        if not need.issubset(df.columns):
            raise ValueError(
                f"CSV {path} missing columns: {need - set(df.columns)}"
            )
        if "H_kN" not in df.columns:
            df["H_kN"] = df["T_kN"] * np.cos(np.radians(df["angle_deg"]))
        if "V_kN" not in df.columns:
            df["V_kN"] = df["T_kN"] * np.sin(np.radians(df["angle_deg"]))
        return df
    # Assume moorpy.System (duck-typed)
    return extract_anchor_loads_from_moorpy_system(source, **kwargs)


# ---------------------------------------------------------------------------
# Safety-factor timeseries
# ---------------------------------------------------------------------------

def anchor_safety_factor_timeseries(
    anchor: SuctionAnchor,
    soil: UndrainedClayProfile,
    anchor_loads: pd.DataFrame,
    *,
    capacity_method: str = "dnv_rp_e303",
    fos_limit: float = DNV_FOS_ULS,
    **capacity_kwargs,
) -> pd.DataFrame:
    """Compute factor of safety at every time step.

    Parameters
    ----------
    anchor, soil : Op^3 data model
    anchor_loads : pandas.DataFrame
        Output of :func:`extract_anchor_loads_from_moorpy`. Must have
        columns ``time_s, T_kN, angle_deg``.
    capacity_method : str, default 'dnv_rp_e303'
        Forwarded to :func:`op3.anchors.anchor_capacity`.
    fos_limit : float, default 1.30 (DNV-ST-0119 ULS).

    Returns
    -------
    pandas.DataFrame
        Columns ``time_s, T_kN, angle_deg, T_ult_kN, FoS, pass``.
    """
    rows = []
    for _, r in anchor_loads.iterrows():
        T = float(r["T_kN"])
        ang = float(r["angle_deg"])
        cap = anchor_capacity(anchor, soil,
                              method=capacity_method,
                              load_angle_deg=ang,
                              **capacity_kwargs)
        fos = cap.T_ult_kN / max(T, 1e-6)
        rows.append(dict(
            time_s=float(r["time_s"]),
            T_kN=T, angle_deg=ang,
            T_ult_kN=cap.T_ult_kN,
            FoS=fos,
            pass_=fos >= fos_limit,
        ))
    out = pd.DataFrame(rows).rename(columns={"pass_": "pass"})
    return out


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------

def generate_anchor_report(
    results: pd.DataFrame,
    anchor: SuctionAnchor,
    soil: UndrainedClayProfile,
    output_path: str | Path = "anchor_design_report.md",
) -> Path:
    """Render a Markdown design report from the FoS timeseries."""
    out = Path(output_path)
    crit_row = results.loc[results["FoS"].idxmin()]
    fail_frac = float((~results["pass"]).mean())
    txt = [
        "# Suction-anchor design report",
        "",
        "## Anchor geometry",
        f"- D = {anchor.diameter_m} m",
        f"- L = {anchor.skirt_length_m} m",
        f"- padeye depth = {anchor.padeye_depth_m} m",
        f"- submerged weight = {anchor.submerged_weight_kN} kN",
        "",
        "## Soil",
        f"- su(z) = {soil.su_mudline_kPa} + {soil.su_gradient_kPa_per_m} z kPa",
        f"- PI = {soil.plasticity_index}%",
        f"- S_t = {soil.sensitivity}",
        "",
        "## Time-series summary",
        f"- N steps: {len(results)}",
        f"- max T : {results['T_kN'].max():.1f} kN",
        f"- min FoS: {results['FoS'].min():.2f} at t = {crit_row['time_s']:.1f} s",
        f"- T at critical step: {crit_row['T_kN']:.1f} kN at "
        f"{crit_row['angle_deg']:.1f} deg",
        f"- fraction of steps with FoS < 1.3: {fail_frac*100:.1f}%",
        "",
        "## Verdict",
        ("PASS (all steps >= 1.3)." if fail_frac == 0
         else f"FAIL: {fail_frac*100:.1f}% of steps below FoS=1.3"),
    ]
    out.write_text("\n".join(txt), encoding="utf-8")
    return out
