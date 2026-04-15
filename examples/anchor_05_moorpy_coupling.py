"""
Example 05 -- End-to-end MoorPy -> Op^3 anchor safety factor.

Builds a single-line catenary mooring in MoorPy (chain, 200 m water
depth, 600 m line), drives the fairlead through a design surge
excitation, solves static equilibrium at each step, extracts the
anchor-side tension time-series, and feeds it to the Op^3 DNV-RP-E303
safety-factor checker. Finally writes a Markdown design report.

The fairlead-surge excitation is a parametric DESIGN LOAD CASE (pure
sinusoid 2 m amplitude at 0.1 Hz), clearly labelled as such. The
anchor tensions returned are real physics: MoorPy solves the non-
linear catenary equation at every step; nothing is fabricated.

Requirements
------------
* MoorPy installed: ``pip install moorpy``
* PYTHONUTF8=1 environment variable on Windows Korean locale
  (MoorPy's default line-type YAML contains non-ASCII characters)

Run::

    PYTHONUTF8=1 python examples/anchor_05_moorpy_coupling.py
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

# MoorPy reads its line-type YAML with system encoding; force UTF-8
os.environ.setdefault("PYTHONUTF8", "1")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from op3.anchors import (
    SuctionAnchor, UndrainedClayProfile,
    anchor_safety_factor_timeseries,
    generate_anchor_report,
)
from op3.anchors.mooring_coupling import _anchor_tension_and_angle


OUT_DIR = Path(__file__).resolve().parent / "anchor_05_results"
OUT_DIR.mkdir(exist_ok=True)


def build_moorpy_system():
    """Single-line chain catenary in 200 m water, both ends fixed.

    No floating body: the fairlead point is of type=1 (fixed) and
    moved explicitly between time steps. This is the cleanest setup
    for anchor-focused analyses because it avoids body-equilibrium
    iteration while still letting MoorPy solve the real non-linear
    catenary shape.
    """
    import moorpy as mp

    water_depth = 200.0
    fairlead_horizontal = 20.0
    anchor_offset = 500.0

    ms = mp.System(depth=water_depth)
    # Polyester taut mooring typical of floating wind designs (Borssele,
    # Hywind Scotland): lighter than studlink chain so anchor loads are
    # realistic for a 5 m suction anchor.
    ms.setLineType(dnommm=80.0, material="polyester", name="poly_80")

    ms.addPoint(1, [-anchor_offset, 0.0, -water_depth])
    ms.addPoint(1, [-fairlead_horizontal, 0.0, -10.0])
    # Line length slightly greater than straight-line distance so the
    # catenary carries some slack at rest.
    ms.addLine(530.0, "poly_80", pointA=1, pointB=2)
    ms.initialize()
    return ms


def main() -> int:
    try:
        import moorpy  # noqa: F401
    except ImportError:
        print("MoorPy not installed. Run `pip install moorpy` first.")
        return 1

    print("Building MoorPy catenary (single chain line, 200 m WD)...")
    ms = build_moorpy_system()
    line = ms.lineList[0]
    anchor_point = ms.pointList[0]
    fairlead_point = ms.pointList[1]
    print(f"  Anchor at {line.rA}, fairlead at {line.rB}")
    # initial static: move anchor from initial position to trigger solve
    line.staticSolve()
    print(f"  Static TA = {line.TA:.1f} kN,   TB = {line.TB:.1f} kN")

    # ------------------------------------------------------------------
    # DESIGN LOAD CASE: sinusoidal fairlead surge -- parametric input
    # ------------------------------------------------------------------
    dt = 0.5
    t = np.arange(0.0, 60.0 + dt, dt)
    amplitude = 4.0       # m
    period = 10.0         # s  (typical wind-wave period)
    surge = amplitude * np.sin(2 * np.pi * t / period)

    fairlead_nominal = np.array(fairlead_point.r, dtype=float)
    rows = []
    for ti, si in zip(t, surge):
        r = fairlead_nominal.copy()
        r[0] = fairlead_nominal[0] + si
        fairlead_point.setPosition(r)
        line.staticSolve()
        T, ang = _anchor_tension_and_angle(line, None)
        rows.append(dict(time_s=float(ti), T_kN=T, angle_deg=ang,
                         H_kN=T * np.cos(np.radians(ang)),
                         V_kN=T * np.sin(np.radians(ang))))
    loads = pd.DataFrame(rows)
    loads.to_csv(OUT_DIR / "anchor_loads.csv", index=False)
    print(f"Ran {len(loads)} MoorPy catenary solves")
    print(f"  T range: {loads['T_kN'].min():.1f} .. {loads['T_kN'].max():.1f} kN")
    print(f"  angle range: {loads['angle_deg'].min():.1f} .. "
          f"{loads['angle_deg'].max():.1f} deg")

    # ------------------------------------------------------------------
    # Op^3 safety factor per DNV-RP-E303
    # ------------------------------------------------------------------
    anchor = SuctionAnchor(diameter_m=5.0, skirt_length_m=15.0,
                           padeye_depth_m=10.0,
                           submerged_weight_kN=500.0)
    soil = UndrainedClayProfile(su_mudline_kPa=5.0,
                                su_gradient_kPa_per_m=1.5,
                                plasticity_index=27.0)

    res = anchor_safety_factor_timeseries(anchor, soil, loads,
                                          capacity_method="dnv_rp_e303",
                                          fos_limit=1.30)
    res.to_csv(OUT_DIR / "fos_timeseries.csv", index=False)
    print(f"\nDNV ULS (FoS >= 1.30) check:")
    print(f"  min FoS: {res['FoS'].min():.2f}")
    print(f"  PASS at every step: {bool(res['pass'].all())}")

    # Plot
    fig, axes = plt.subplots(2, 1, figsize=(9, 7), sharex=True)
    axes[0].plot(res["time_s"], res["T_kN"], label="T applied (anchor)")
    axes[0].plot(res["time_s"], res["T_ult_kN"], label="T_ult (DNV)")
    axes[0].set_ylabel("Tension [kN]")
    axes[0].legend()
    axes[0].grid(alpha=0.3)
    axes[1].plot(res["time_s"], res["FoS"], color="C2")
    axes[1].axhline(1.3, color="red", ls="--", label="ULS limit 1.30")
    axes[1].set_xlabel("Time [s]")
    axes[1].set_ylabel("Factor of safety")
    axes[1].legend()
    axes[1].grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(OUT_DIR / "fos_timeseries.png", dpi=150)
    plt.close(fig)

    # Report
    report = generate_anchor_report(res, anchor, soil,
                                    output_path=OUT_DIR / "design_report.md")
    print(f"\nReport: {report}")
    print(f"All results in {OUT_DIR}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
