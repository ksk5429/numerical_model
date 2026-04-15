"""
Example 04 -- Post-storm (cyclic) capacity reduction.

For a 3-hour design storm with Hs = 10 m, Tp = 12 s, tau_cyc/su = 0.5:
  * Compute the equivalent number of cycles.
  * Apply the Andersen 2015 Drammen-clay reduction surrogate.
  * Re-compute the DNV-RP-E303 capacity with the degraded soil.
  * Report the ratio of post-cyclic to static capacity.
"""
from __future__ import annotations

import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from op3.anchors import (
    SuctionAnchor, UndrainedClayProfile,
    anchor_capacity,
    cyclic_capacity_reduction, apply_cyclic_to_soil,
)

OUT_DIR = Path(__file__).resolve().parent / "anchor_04_results"
OUT_DIR.mkdir(exist_ok=True)


def main() -> int:
    anchor = SuctionAnchor(diameter_m=5.0, skirt_length_m=15.0,
                           padeye_depth_m=10.0,
                           submerged_weight_kN=500.0)
    soil = UndrainedClayProfile(su_mudline_kPa=5.0,
                                su_gradient_kPa_per_m=1.5,
                                plasticity_index=27.0)

    # Static capacity
    r_static = anchor_capacity(anchor, soil, method="dnv_rp_e303",
                               load_angle_deg=30.0)

    # Storm loading
    storm_duration = 3.0   # h
    Tp = 12.0              # s
    tau_ratio = 0.5
    cyc = cyclic_capacity_reduction(anchor, soil,
                                    storm_duration_hours=storm_duration,
                                    wave_period_s=Tp,
                                    tau_cyc_over_su=tau_ratio)
    soil_post = apply_cyclic_to_soil(soil, cyc)

    # Post-cyclic capacity
    r_post = anchor_capacity(anchor, soil_post, method="dnv_rp_e303",
                             load_angle_deg=30.0)

    print("Op^3 anchor example 04 -- post-storm cyclic capacity")
    print(f"  Storm: {storm_duration:.1f} h, Tp = {Tp:.1f} s, "
          f"tau_cyc/su = {tau_ratio:.2f}")
    print(f"  N_cycles = {cyc.n_cycles:.0f}")
    print(f"  Andersen 2015 delta = {cyc.reduction_factor:.3f}")
    print()
    print(f"  Static H_ult  = {r_static.H_ult_kN:10.1f} kN")
    print(f"  Post   H_ult  = {r_post.H_ult_kN:10.1f} kN  "
          f"({r_post.H_ult_kN/r_static.H_ult_kN*100:.1f}% of static)")
    print(f"  Static T_ult  = {r_static.T_ult_kN:10.1f} kN")
    print(f"  Post   T_ult  = {r_post.T_ult_kN:10.1f} kN  "
          f"({r_post.T_ult_kN/r_static.T_ult_kN*100:.1f}% of static)")

    # Plot envelopes
    fig, ax = plt.subplots(figsize=(7, 6))
    ax.plot(r_static.interaction_envelope["H_kN"] / 1000,
            r_static.interaction_envelope["V_kN"] / 1000,
            label="Static", linewidth=2)
    ax.plot(r_post.interaction_envelope["H_kN"] / 1000,
            r_post.interaction_envelope["V_kN"] / 1000,
            label=f"Post-storm (delta={cyc.reduction_factor:.2f})",
            linewidth=2, linestyle="--")
    ax.set_xlabel("Horizontal capacity H [MN]")
    ax.set_ylabel("Vertical capacity V [MN]")
    ax.set_title(
        f"Static vs post-cyclic V-H envelope "
        f"(N = {cyc.n_cycles:.0f}, tau_cyc/su = {tau_ratio})"
    )
    ax.legend()
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(OUT_DIR / "cyclic_envelope.png", dpi=150)
    plt.close(fig)

    print(f"\nResults saved to: {OUT_DIR}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
