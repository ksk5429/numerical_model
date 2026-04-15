"""
Example 02 -- Installation feasibility for a suction anchor.

For a reference anchor (D=5 m, L=15 m, W_sub=1500 kN) in NC clay at
200 m water depth, checks:
  * self-weight penetration depth
  * required suction vs depth
  * allowable (cavitation) suction vs depth
  * plug-heave stability ratio

Emits a PNG with the four profiles and a CSV with the numerical
values.
"""
from __future__ import annotations

import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from op3.anchors import (
    SuctionAnchor, UndrainedClayProfile, installation_analysis,
)


OUT_DIR = Path(__file__).resolve().parent / "anchor_02_results"
OUT_DIR.mkdir(exist_ok=True)


def main() -> int:
    # Submerged weight for a D=5 m, L=15 m steel anchor with 30 mm
    # skirt and 40 mm lid -- a realistic range is 200-500 kN after
    # buoyancy (Randolph & Gourvenec 2011 Table 9.1). Use the lower
    # bound so the suction-assisted phase is engaged.
    anchor = SuctionAnchor(diameter_m=5.0, skirt_length_m=15.0,
                           wall_thickness_mm=30.0,
                           submerged_weight_kN=250.0)
    soil = UndrainedClayProfile(su_mudline_kPa=5.0,
                                su_gradient_kPa_per_m=1.5,
                                sensitivity=3.0,
                                gamma_eff_kN_per_m3=6.0)

    water = 200.0
    res = installation_analysis(anchor, soil, water_depth_m=water)

    print("Op^3 anchor example 02 -- installation feasibility")
    print(f"  Self-weight penetration: {res.self_weight_depth_m:.2f} m"
          f" / {anchor.skirt_length_m} m skirt")
    print(f"  Max suction required: {res.max_suction_required_kPa:.1f} kPa")
    print(f"  Min cavitation limit: {res.max_allowable_suction_kPa:.1f} kPa")
    print(f"  Plug-heave ok (R_plug < 1 everywhere): {res.plug_heave_ok}")
    print(f"  Feasible: {res.feasible}")

    res.profile.to_csv(OUT_DIR / "installation_profile.csv", index=False)

    # ------------------------------------------------------------------
    # Plot
    # ------------------------------------------------------------------
    prof = res.profile
    fig, axes = plt.subplots(1, 3, figsize=(14, 6), sharey=True)

    axes[0].plot(prof["F_drive_kN"] / 1000, prof["depth_m"],
                 label="F_drive = W + s*A_i", linewidth=2)
    axes[0].plot(prof["F_resist_kN"] / 1000, prof["depth_m"],
                 label="R(z)", linewidth=2)
    axes[0].set_xlabel("Force [MN]")
    axes[0].set_ylabel("Depth below mudline [m]")
    axes[0].set_title("Driving vs resisting force")
    axes[0].invert_yaxis()
    axes[0].legend()
    axes[0].grid(alpha=0.3)

    axes[1].plot(prof["s_req_kPa"], prof["depth_m"],
                 label="required", linewidth=2, color="C3")
    axes[1].plot(prof["s_allow_kPa"], prof["depth_m"],
                 label="cavitation limit", linewidth=2, color="C2")
    axes[1].set_xlabel("Suction pressure [kPa]")
    axes[1].set_title(f"Suction feasibility (water = {water:.0f} m)")
    axes[1].legend()
    axes[1].grid(alpha=0.3)

    axes[2].plot(prof["R_plug"], prof["depth_m"], color="C1", linewidth=2)
    axes[2].axvline(1.0, ls="--", color="red",
                    label="stability limit R_plug = 1")
    axes[2].set_xlabel("Plug-heave ratio R_plug")
    axes[2].set_title("Plug heave")
    axes[2].legend()
    axes[2].grid(alpha=0.3)

    fig.suptitle(
        f"Installation of D={anchor.diameter_m} m L={anchor.skirt_length_m} m "
        f"anchor (W_sub={anchor.submerged_weight_kN:.0f} kN)"
    )
    fig.tight_layout()
    fig.savefig(OUT_DIR / "installation_profiles.png", dpi=150)
    plt.close(fig)

    print(f"\nResults saved to: {OUT_DIR}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
