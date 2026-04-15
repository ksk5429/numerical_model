"""
Example 03 -- Optimal padeye depth: analytical vs sensitivity sweep vs
dissipation centroid.

If a real OptumGX Mode D dissipation CSV for this anchor is present at
  data/anchor_benchmarks/<D>m_L<L>m_dissipation.csv
the script also runs the novel dissipation-centroid method and compares
all three approaches. If the CSV is missing, the script still runs the
two analytical methods and prints instructions for generating the FE
data with the OptumGX driver.
"""
from __future__ import annotations

import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from op3.anchors import (
    SuctionAnchor, UndrainedClayProfile,
    optimal_padeye_analytical,
    optimal_padeye_from_dissipation,
    padeye_sensitivity_study,
)


ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = Path(__file__).resolve().parent / "anchor_03_results"
OUT_DIR.mkdir(exist_ok=True)


def main() -> int:
    D, L = 5.0, 15.0
    anchor = SuctionAnchor(diameter_m=D, skirt_length_m=L,
                           wall_thickness_mm=30.0,
                           submerged_weight_kN=500.0)
    soil = UndrainedClayProfile(su_mudline_kPa=5.0,
                                su_gradient_kPa_per_m=1.5)

    # ------------------------------------------------------------------
    # 1. Analytical estimates
    # ------------------------------------------------------------------
    z_sup = optimal_padeye_analytical(anchor, soil,
                                      method="supachawarote_2005")
    z_mh = optimal_padeye_analytical(anchor, soil,
                                     method="murff_hamilton")
    print(f"Supachawarote 2005:   z_p = {z_sup:.2f} m  ({z_sup/L:.2f} L)")
    print(f"Murff-Hamilton 1993:  z_p = {z_mh:.2f} m  ({z_mh/L:.2f} L)")

    # ------------------------------------------------------------------
    # 2. Brute-force sensitivity sweep over z_p
    # ------------------------------------------------------------------
    z_range = np.linspace(0.3 * L, 0.9 * L, 25)
    sweep = padeye_sensitivity_study(anchor, soil, z_range,
                                     load_angle_deg=30.0,
                                     capacity_method="dnv_rp_e303")
    sweep.to_csv(OUT_DIR / "padeye_sweep.csv", index=False)
    z_sweep_opt = float(sweep.loc[sweep["T_ult_kN"].idxmax(), "z_p_m"])
    T_spread = sweep["T_ult_kN"].max() - sweep["T_ult_kN"].min()
    T_rel = T_spread / sweep["T_ult_kN"].mean()
    print(f"Sweep (DNV, 30 deg):  z_p = {z_sweep_opt:.2f} m  "
          f"({z_sweep_opt/L:.2f} L)")
    print(f"  NB: analytical T_ult is nearly flat in z_p "
          f"(spread = {T_rel*100:.2f}%)")
    print("  -- this is expected: closed-form H/V do not capture the")
    print("     moment-equilibrium effect of padeye depth. Use the")
    print("     dissipation-centroid (FE-based) method for a proper z_p*.")

    # ------------------------------------------------------------------
    # 3. Dissipation-centroid (novel, Op^3 Mode D extension)
    # ------------------------------------------------------------------
    diss_csv = ROOT / "data" / "anchor_benchmarks" / \
        f"{D:.0f}m_L{L:.0f}m_dissipation.csv"
    if diss_csv.exists():
        z_diss = optimal_padeye_from_dissipation(anchor, diss_csv)
        print(f"Dissipation centroid: z_p = {z_diss:.2f} m  "
              f"({z_diss/L:.2f} L)   [FROM OPTUMGX]")
    else:
        z_diss = None
        print("Dissipation centroid: [skipped -- CSV not found]")
        print(f"  Expected path: {diss_csv}")
        print("  Generate it with the OptumGX driver "
              "(see docs/ANCHOR_OPTUMGX_GUIDE.md).")

    # ------------------------------------------------------------------
    # Plot
    # ------------------------------------------------------------------
    fig, ax = plt.subplots(figsize=(8, 6))
    ax.plot(sweep["z_p_over_L"], sweep["T_ult_kN"] / 1000,
            marker="o", linewidth=2, label="DNV capacity sweep")
    ax.axvline(z_sup / L, color="C1", ls="--",
               label=f"Supachawarote 2005 ({z_sup/L:.2f} L)")
    ax.axvline(z_mh / L, color="C2", ls="--",
               label=f"Murff-Hamilton ({z_mh/L:.2f} L)")
    if z_diss is not None:
        ax.axvline(z_diss / L, color="C3", ls="-",
                   label=f"Dissipation centroid ({z_diss/L:.2f} L) [FE]")
    ax.set_xlabel("Padeye depth fraction z_p / L")
    ax.set_ylabel("Inclined capacity T_ult [MN] at 30 deg")
    ax.set_title("Padeye optimisation -- analytical vs sensitivity vs FE")
    ax.legend()
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(OUT_DIR / "padeye_optimum.png", dpi=150)
    plt.close(fig)

    print(f"\nResults saved to: {OUT_DIR}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
