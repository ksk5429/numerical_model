"""
Example 01 -- Basic suction-anchor ultimate capacity

Runs all four analytical methods for a reference anchor
(D=5 m, L=15 m, padeye at z_p=10 m) in NC clay (su = 5 + 1.5 z kPa),
prints a comparison table, and saves V-H interaction plots.

Run:
    python examples/anchor_01_basic_capacity.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

# Ensure `op3` is importable when running from a fresh checkout
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from op3.anchors import (
    SuctionAnchor, UndrainedClayProfile, MooringLoad, anchor_capacity,
)


OUT_DIR = Path(__file__).resolve().parent / "anchor_01_results"
OUT_DIR.mkdir(exist_ok=True)


def main() -> int:
    # ------------------------------------------------------------------
    # Reference geometry and soil (matches tests/fixtures)
    # ------------------------------------------------------------------
    anchor = SuctionAnchor(
        diameter_m=5.0,
        skirt_length_m=15.0,
        wall_thickness_mm=30.0,
        padeye_depth_m=10.0,
        submerged_weight_kN=500.0,
    )
    soil = UndrainedClayProfile(
        su_mudline_kPa=5.0,
        su_gradient_kPa_per_m=1.5,
        sensitivity=3.0,
    )
    load = MooringLoad(tension_kN=4000.0, angle_at_padeye_deg=25.0)

    print("=" * 70)
    print(f"Op^3 anchor example 01 -- basic capacity")
    print(f"  D = {anchor.diameter_m} m, L = {anchor.skirt_length_m} m, "
          f"L/D = {anchor.aspect_ratio:.2f}, z_p = {anchor.padeye_depth_m} m")
    print(f"  su(z) = {soil.su_mudline_kPa} + {soil.su_gradient_kPa_per_m} z "
          "kPa")
    print(f"  Applied: T = {load.tension_kN} kN at "
          f"theta = {load.angle_at_padeye_deg} deg")
    print("=" * 70)

    methods = ["dnv_rp_e303", "murff_hamilton", "api_rp_2sk", "aubeny_2003"]
    rows = []
    envelopes = {}
    for m in methods:
        kwargs = {"interface": "rough"} if m == "aubeny_2003" else {}
        r = anchor_capacity(anchor, soil, method=m, load=load, **kwargs)
        fos = r.factor_of_safety(load.tension_kN)
        rows.append(dict(
            method=m,
            H_ult_kN=r.H_ult_kN,
            V_ult_kN=r.V_ult_kN,
            T_ult_kN=r.T_ult_kN,
            FoS=fos,
            a=r.interaction_exponents[0],
            b=r.interaction_exponents[1],
        ))
        envelopes[m] = r.interaction_envelope

    df = pd.DataFrame(rows)
    print(df.to_string(index=False, float_format=lambda x: f"{x:,.1f}"))
    df.to_csv(OUT_DIR / "capacity_comparison.csv", index=False)

    # ------------------------------------------------------------------
    # V-H interaction plot
    # ------------------------------------------------------------------
    fig, ax = plt.subplots(figsize=(7, 6))
    for m, env in envelopes.items():
        ax.plot(env["H_kN"] / 1000, env["V_kN"] / 1000,
                label=m, linewidth=2)
    ax.plot([load.horizontal_kN / 1000], [load.vertical_kN / 1000],
            marker="*", markersize=18, color="red",
            label=f"Applied T ({load.tension_kN:.0f} kN @ "
                  f"{load.angle_at_padeye_deg:.0f}deg)")
    ax.set_xlabel("Horizontal capacity H [MN]")
    ax.set_ylabel("Vertical capacity V [MN]")
    ax.set_title("V-H interaction envelope -- four methods compared")
    ax.legend(loc="upper right")
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig(OUT_DIR / "vh_envelope.png", dpi=150)
    plt.close(fig)

    print(f"\nResults saved to: {OUT_DIR}")
    # Exit 0 on success so the pytest harness can pick it up if desired
    return 0


if __name__ == "__main__":
    sys.exit(main())
