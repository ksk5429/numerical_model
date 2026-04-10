# -*- coding: utf-8 -*-
"""
BNWF Pipeline Step 3: Global K → Distributed k(z) Spring Stiffness
===================================================================
Distributes the Gazetas global stiffness to depth-wise spring stiffness
for the BNWF model. Uses the CPT Gmax(z) profile shape and calibrates
the scaling factor so the integral matches the global value.

    k_h(z) = delta_h * G(z)
    such that: integral_0^L [ k_h(z) * D ] dz = Kh_global

Input:  results/gmax_profile.csv (from Step 1)
        results/gazetas_stiffness.json (from Step 2)
Output: results/spring_stiffness_profile.csv
        results/spring_stiffness_profile.json
"""
import numpy as np
import pandas as pd
from pathlib import Path
import json

RESULTS_DIR = Path(__file__).parent / 'results'

D = 8.0;  R = D / 2;  L = 9.3;  DZ = 0.5


# =============================================================================
# MAIN
# =============================================================================
if __name__ == "__main__":
    print("=" * 60)
    print("BNWF Pipeline Step 3: Distribute Stiffness k(z)")
    print("=" * 60)

    # Load inputs
    df_g = pd.read_csv(RESULTS_DIR / 'gmax_profile.csv')
    with open(RESULTS_DIR / 'gazetas_stiffness.json') as f:
        stiff = json.load(f)

    Kh_global = stiff['Kh_kN_m']     # kN/m
    Kv_global = stiff['Kv_kN_m']     # kN/m
    Kr_global = stiff['Kr_kNm_rad']  # kNm/rad

    G_z = df_g['G0_kPa'].values      # kPa at each depth node
    z = df_g['z_m'].values

    print(f"\n  Global stiffness (Gazetas Gibson):")
    print(f"    Kh = {Kh_global/1000:.1f} MN/m")
    print(f"    Kv = {Kv_global/1000:.1f} MN/m")
    print(f"    Kr = {Kr_global/1000:.1f} MNm/rad")

    # ---- Horizontal spring stiffness k_h(z) ----
    # Model: k_h(z) = delta_h * G(z)  [kN/m per m depth per m width]
    # Total: integral_0^L k_h(z) * D * dz = Kh_global
    # Therefore: delta_h = Kh_global / (D * integral_0^L G(z) dz)
    integral_G = np.trapezoid(G_z, z)
    delta_h = Kh_global / (D * integral_G) if integral_G > 0 else 1.0
    k_h = delta_h * G_z  # kN/m per m depth per m width

    # Spring stiffness per node (tributary area = D * dz)
    K_py_node = k_h * D * DZ  # kN/m per node

    # Verify
    Kh_check = np.trapezoid(k_h * D, z)
    print(f"\n  Horizontal springs:")
    print(f"    delta_h = {delta_h:.4f}")
    print(f"    Kh_check = {Kh_check/1000:.1f} MN/m "
          f"(target: {Kh_global/1000:.1f}, ratio: {Kh_check/Kh_global:.4f})")

    # ---- Vertical spring stiffness k_v(z) ----
    # Shaft friction springs along circumference
    # Model: k_v(z) = delta_v * G(z)
    # Total shaft stiffness (approximate): integral_0^L k_v(z) * pi * D * dz
    # We allocate ~20% of Kv to shaft (rest is base) based on OptumGX data
    SHAFT_FRACTION = 0.20  # from OptumGX Vmax probe: skirt carried 16% of Vmax
    Kv_shaft = Kv_global * SHAFT_FRACTION
    delta_v = Kv_shaft / (np.pi * D * integral_G) if integral_G > 0 else 1.0
    k_v = delta_v * G_z  # kN/m per m depth per m circumference
    K_tz_node = k_v * np.pi * D * DZ  # kN/m per node (full circumference)

    # Base spring stiffness (remaining vertical stiffness)
    Kv_base = Kv_global * (1 - SHAFT_FRACTION)

    Kv_shaft_check = np.trapezoid(k_v * np.pi * D, z)
    print(f"\n  Vertical springs:")
    print(f"    Shaft fraction = {SHAFT_FRACTION:.0%}")
    print(f"    delta_v = {delta_v:.4f}")
    print(f"    Kv_shaft_check = {Kv_shaft_check/1000:.1f} MN/m "
          f"(target: {Kv_shaft/1000:.1f})")
    print(f"    Kv_base = {Kv_base/1000:.1f} MN/m")

    # ---- Rotational stiffness check ----
    # The distributed lateral springs contribute to rotation:
    # Kr_distributed = integral_0^L k_h(z) * D * z^2 * dz
    Kr_dist = np.trapezoid(k_h * D * z**2, z)
    Kr_deficit = Kr_global - Kr_dist
    print(f"\n  Rotational stiffness:")
    print(f"    Kr from distributed p-y = {Kr_dist/1000:.1f} MNm/rad")
    print(f"    Kr target (Gazetas)     = {Kr_global/1000:.1f} MNm/rad")
    print(f"    Deficit (base moment)   = {Kr_deficit/1000:.1f} MNm/rad")
    if Kr_deficit > 0:
        print(f"    → Add base rotational spring: Kr_base = {Kr_deficit/1000:.1f} MNm/rad")
    else:
        Kr_deficit = 0
        print(f"    → No base rotational spring needed")

    # ---- Build output DataFrame ----
    df_out = pd.DataFrame({
        'z_m': z,
        'G0_kPa': G_z,
        'k_h_kPa': k_h,           # lateral subgrade reaction [kN/m3]
        'k_v_kPa': k_v,           # vertical subgrade reaction [kN/m3]
        'K_py_node_kN_m': K_py_node,   # spring stiffness per node [kN/m]
        'K_tz_node_kN_m': K_tz_node,   # shaft spring per node [kN/m]
    })

    csv_path = RESULTS_DIR / 'spring_stiffness_profile.csv'
    df_out.to_csv(csv_path, index=False)

    meta = {
        'delta_h': round(delta_h, 6),
        'delta_v': round(delta_v, 6),
        'shaft_fraction': SHAFT_FRACTION,
        'Kh_global_kN_m': Kh_global,
        'Kv_global_kN_m': Kv_global,
        'Kr_global_kNm_rad': Kr_global,
        'Kv_base_kN_m': round(Kv_base, 1),
        'Kr_base_kNm_rad': round(max(Kr_deficit, 0), 1),
        'Kh_check_kN_m': round(Kh_check, 1),
        'Kr_distributed_kNm_rad': round(Kr_dist, 1),
        'n_nodes': len(z),
        'dz': DZ, 'D': D, 'L': L,
    }
    json_path = RESULTS_DIR / 'spring_stiffness_profile.json'
    with open(json_path, 'w') as f:
        json.dump(meta, f, indent=2)

    print(f"\n  Profile table:")
    print(f"  {'z':>6s}  {'G0':>8s}  {'k_h':>8s}  {'K_py':>10s}  {'K_tz':>10s}")
    print(f"  {'[m]':>6s}  {'[kPa]':>8s}  {'[kPa]':>8s}  {'[kN/m]':>10s}  {'[kN/m]':>10s}")
    print("-" * 52)
    for _, r in df_out.iterrows():
        print(f"  {r['z_m']:6.1f}  {r['G0_kPa']:8.0f}  {r['k_h_kPa']:8.1f}  "
              f"{r['K_py_node_kN_m']:10.0f}  {r['K_tz_node_kN_m']:10.0f}")

    print(f"\n  Saved: {csv_path.name}, {json_path.name}")
    print("=" * 60)
