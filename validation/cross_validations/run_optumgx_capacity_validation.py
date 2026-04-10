"""
OptumGX limit analysis validation: capacity benchmarks.

Benchmarks:
  #14  Fu & Bienen (2017) — NcV bearing capacity factor for circular
       foundation on homogeneous Tresca clay
  #15  Vulpe (2015) — NcV, NcH, NcM for skirted foundation (d/D=0.5)
       on homogeneous NC clay
  #18  Achmus (2013) — Hu for suction bucket (D=12m, L=9m) in dense sand

Requires: OptumGX running on the local machine.

Usage:
    python validation/cross_validations/run_optumgx_capacity_validation.py
"""
from __future__ import annotations

# Save stdlib modules BEFORE OptumGX wildcard import clobbers them
import builtins
import json
import os
import re
import sys
import time as _time_mod
from pathlib import Path

import numpy as np

from OptumGX import *  # noqa: F403

# Restore builtins clobbered by OptumGX wildcard import
time = _time_mod
float = builtins.float
int = builtins.int
str = builtins.str
print = builtins.print
len = builtins.len
type = builtins.type
range = builtins.range
abs = builtins.abs
round = builtins.round
sum = builtins.sum
min = builtins.min
max = builtins.max

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

OUT_DIR = Path(__file__).resolve().parent
RESULTS_FILE = OUT_DIR / "optumgx_capacity_results.json"

results = {}


def parse_val(attr):
    """Parse any OptumGX output attribute to Python numeric."""
    if attr is None:
        return None
    if isinstance(attr, (int, float)):
        return attr
    if isinstance(attr, np.ndarray):
        return attr.tolist()
    s = str(attr)
    m = re.search(r"value:\s*(.*)", s)
    if m:
        nums = re.findall(r'[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?', m.group(1))
        if nums:
            floats = [float(n) for n in nums]
            return floats[0] if len(floats) == 1 else floats
    try:
        return float(s)
    except ValueError:
        return s


def get_load_multiplier(mod):
    """Robustly extract load multiplier from model output."""
    try:
        return float(mod.output.global_results.load_multiplier)
    except Exception:
        try:
            return float(mod.output.critical_results.load_multiplier)
        except Exception:
            return None


# ============================================================
# Benchmark #14: Fu & Bienen (2017) NcV
#   Surface circular foundation on homogeneous Tresca clay:
#     NcV = V_ult / (A * su) = 5.94  (d/D = 0, kD/su0 = 0)
#   Embedded (d/D = 0.5):
#     NcV = 10.51
# ============================================================
def run_fu_bienen_benchmark(prj):
    """Validate bearing capacity factor NcV against Fu & Bienen 2017."""


    print("\n" + "=" * 60)
    print("[#14] Fu & Bienen (2017) — NcV bearing capacity factor")
    print("=" * 60)

    # Common parameters
    su = 50.0       # kPa (homogeneous, kD/su0 = 0)
    gamma = 0.01    # near-zero self-weight (pure bearing capacity)
    D = 10.0        # m (diameter, arbitrary for Nc)
    R = D / 2
    A = np.pi * R**2  # full circle area
    N_el = 8000
    N_el_start = 4000

    # --- Case A: Surface footing via 2D revolve (proper circle) ---
    print("\n  Case A: Surface circular footing (d/D = 0) via revolve")
    print(f"  D = {D}m, su = {su} kPa, expected NcV = 5.94-6.05")

    N_SIDES = 24
    N_sectors = N_SIDES // 2
    L_dom = 6 * R
    H_dom = 4 * R

    Soil_A = prj.Tresca(name="Soil_A", cu=su, gamma_dry=gamma,
                         color=rgb(195, 165, 120))
    Fdn_A = prj.RigidPlate(name="Fdn_A", color=rgb(130, 160, 180))

    # 2D cross-section: soil half-space + surface footing (lid only, no skirt)
    m2a = prj.create_model(name="AX_NcV_surf", model_type="plane_strain")
    m2a.add_rectangle([0, -H_dom], [L_dom/2, 0])
    m2a.add_line([0, 0], [R, 0])   # lid only

    sel = m2a.select([L_dom/4, -H_dom/2], types="face")
    m2a.set_solid(sel, Soil_A)
    sel = m2a.select([R/2, 0], types="edge")
    m2a.set_plate(sel, Fdn_A, strength_reduction_factor=1.0)

    mod_a = m2a.revolve_2d_to_3d(angle_deg=180, N=N_sectors, name="NcV_surface")
    m2a.delete()

    # Clean axis edge
    try:
        sel = mod_a.select([0, 0, -H_dom/2], types="edge")
        if sel:
            mod_a.delete_shapes(sel)
    except Exception:
        pass

    mod_a.add_vertex([0, 0, 0])
    sel_c = mod_a.select([0, 0, 0], types="vertex")
    mod_a.set_resultpoint(sel_c)

    # Symmetry BC on plate edge at y=0 (center axis)
    sel_edge = mod_a.select([0, 0, 0], types="edge")
    mod_a.set_plate_bc(sel_edge, displacement_x="fixed", displacement_y="fixed",
                       displacement_z="free", displacement_rotation="fixed")

    mod_a.set_standard_fixities()
    mod_a.set_analysis_properties(
        analysis_type="load_multiplier", element_type="mixed",
        no_of_elements=N_el, mesh_adaptivity="yes",
        adaptivity_iterations=3, start_elements=N_el_start,
    )

    # Point BC at center
    mod_a.set_point_bc(shapes=sel_c,
                       displacement_x='fixed', displacement_y='fixed',
                       displacement_z='free',
                       displacement_rotation_x='fixed',
                       displacement_rotation_y='fixed',
                       displacement_rotation_z='fixed',
                       )

    # Vertical multiplier load
    mod_a.set_point_load(sel_c, -1, direction="z", option="multiplier")
    mod_a.zoom_all()

    print("  Running analysis (surface)...")
    t0 = time.time()
    prj.run_analysis()
    dt = time.time() - t0

    lm_a = get_load_multiplier(mod_a)
    if lm_a is not None:
        # Half-model: multiply by 2 for full
        V_ult_full = abs(float(lm_a)) * 2
        NcV_a = V_ult_full / (A * su)
        ref_NcV_a = 5.94
        err_a = (NcV_a - ref_NcV_a) / ref_NcV_a * 100
        print(f"  V_ult (full) = {V_ult_full:.1f} kN")
        print(f"  NcV = {NcV_a:.3f}  (ref = {ref_NcV_a}, error = {err_a:+.1f}%)")
        print(f"  Time: {dt:.0f}s")
        results["fu_bienen_surface"] = {
            "NcV_op3": round(NcV_a, 3), "NcV_ref": ref_NcV_a,
            "error_pct": round(err_a, 1), "V_ult_kN": round(V_ult_full, 1),
            "time_s": round(dt, 1),
        }
    else:
        print("  ERROR: no load multiplier returned")
        results["fu_bienen_surface"] = {"error": "no result"}

    mod_a.delete()

    # --- Case B: Embedded skirted (d/D = 0.5) ---
    print("\n  Case B: Skirted foundation (d/D = 0.5)")
    S = D * 0.5  # skirt depth = 5m for D=10m
    print(f"  D = {D}m, S = {S}m, d/D = 0.5, expected NcV = 10.51")

    N_SIDES = 24
    N_sectors = N_SIDES // 2
    L_dom_b = 12 * R
    H_dom_b = 8 * R

    Soil_B = prj.Tresca(name="Soil_B", cu=su, gamma_dry=gamma,
                         color=rgb(195, 165, 120))
    Fdn_B = prj.RigidPlate(name="Fdn_B", color=rgb(130, 160, 180))

    # 2D cross-section -> revolve
    m2 = prj.create_model(name="AX_NcV_emb", model_type="plane_strain")
    m2.add_rectangle([0, -H_dom_b], [L_dom_b/2, 0])
    m2.add_line([0, 0], [R, 0])        # lid
    m2.add_line([R, 0], [R, -S])       # skirt

    sel = m2.select([L_dom_b/4, -H_dom_b/2], types="face")
    m2.set_solid(sel, Soil_B)
    sel = m2.select([R/2, 0], types="edge")
    m2.set_plate(sel, Fdn_B, strength_reduction_factor=1.0)
    sel = m2.select([R, -S/2], types="edge")
    m2.set_plate(sel, Fdn_B, strength_reduction_factor=1.0)

    mod_b = m2.revolve_2d_to_3d(angle_deg=180, N=N_sectors, name="NcV_embedded")
    m2.delete()

    # Clean axis edge
    try:
        sel = mod_b.select([0, 0, -H_dom_b/2], types="edge")
        if sel:
            mod_b.delete_shapes(sel)
    except Exception:
        pass

    mod_b.add_vertex([0, 0, 0])
    sel_c = mod_b.select([0, 0, 0], types="vertex")
    mod_b.set_resultpoint(sel_c)

    # Plate BCs
    sel_edge = mod_b.select([0, 0, 0], types="edge")
    mod_b.set_plate_bc(sel_edge, displacement_x="fixed", displacement_y="fixed",
                       displacement_z="free", displacement_rotation="fixed")
    for x_sign in [1, -1]:
        try:
            sel = mod_b.select([x_sign * R, 0, -S/2], types="edge")
            mod_b.set_plate_bc(sel, displacement_x="free", displacement_y="fixed",
                               displacement_z="free", displacement_rotation="fixed")
        except Exception:
            pass

    mod_b.set_standard_fixities()

    # Point BC
    mod_b.set_point_bc(shapes=sel_c,
                       displacement_x='fixed', displacement_y='fixed',
                       displacement_z='free',
                       displacement_rotation_x='fixed',
                       displacement_rotation_y='fixed',
                       displacement_rotation_z='fixed',
                       )

    # Mesh fans at skirt tip
    for ang in np.linspace(0, 180, N_sectors + 1):
        try:
            sf = mod_b.select([R*np.cos(np.radians(ang)),
                               R*np.sin(np.radians(ang)), -S], types="vertex")
            if sf:
                mod_b.set_mesh_fan(shapes=sf, fan_angle=30)
        except Exception:
            pass

    mod_b.set_analysis_properties(
        analysis_type="load_multiplier", element_type="mixed",
        no_of_elements=N_el, mesh_adaptivity="yes",
        adaptivity_iterations=3, start_elements=N_el_start,
        design_approach='unity',
    )

    mod_b.set_point_load(sel_c, -1, direction="z", option="multiplier")
    mod_b.zoom_all()

    print("  Running analysis (embedded d/D=0.5)...")
    t0 = time.time()
    prj.run_analysis()
    dt = time.time() - t0

    lm_b = get_load_multiplier(mod_b)
    if lm_b is not None:
        V_ult_full = abs(float(lm_b)) * 2
        NcV_b = V_ult_full / (A * su)
        ref_NcV_b = 10.51
        err_b = (NcV_b - ref_NcV_b) / ref_NcV_b * 100
        print(f"  V_ult (full) = {V_ult_full:.1f} kN")
        print(f"  NcV = {NcV_b:.3f}  (ref = {ref_NcV_b}, error = {err_b:+.1f}%)")
        print(f"  Time: {dt:.0f}s")
        results["fu_bienen_embedded"] = {
            "NcV_op3": round(NcV_b, 3), "NcV_ref": ref_NcV_b,
            "error_pct": round(err_b, 1), "V_ult_kN": round(V_ult_full, 1),
            "time_s": round(dt, 1), "d_D": 0.5,
        }
    else:
        print("  ERROR: no load multiplier returned")
        results["fu_bienen_embedded"] = {"error": "no result"}

    mod_b.delete()


# ============================================================
# Benchmark #15: Vulpe (2015) NcV, NcH, NcM
#   d/D = 0.5, kappa = 0 (homogeneous NC clay), rough interface
#   Published: NcV = 10.69, NcH = 4.17, NcM = 1.48
# ============================================================
def run_vulpe_benchmark(prj):
    """Validate VHM capacity factors against Vulpe 2015."""


    print("\n" + "=" * 60)
    print("[#15] Vulpe (2015) — NcV, NcH, NcM (d/D=0.5, kappa=0)")
    print("=" * 60)

    su = 50.0       # kPa (homogeneous)
    gamma = 0.01    # near-zero (pure Nc)
    D = 10.0
    R = D / 2
    S = D * 0.5     # d/D = 0.5
    A = np.pi * R**2
    N_SIDES = 24
    N_sectors = N_SIDES // 2
    L_dom = 12 * R
    H_dom = 8 * R
    N_el = 10000
    N_el_start = 6000

    ref = {"NcV": 10.69, "NcH": 4.17, "NcM": 1.48}

    def build_skirted_model(name):
        """Build skirted foundation model via 2D revolve."""
        Soil = prj.Tresca(name=f"Soil_{name}", cu=su, gamma_dry=gamma,
                           color=rgb(195, 165, 120))
        Fdn = prj.RigidPlate(name=f"Fdn_{name}", color=rgb(130, 160, 180))

        m2 = prj.create_model(name=f"AX_{name}", model_type="plane_strain")
        m2.add_rectangle([0, -H_dom], [L_dom/2, 0])
        m2.add_line([0, 0], [R, 0])
        m2.add_line([R, 0], [R, -S])

        sel = m2.select([L_dom/4, -H_dom/2], types="face")
        m2.set_solid(sel, Soil)
        sel = m2.select([R/2, 0], types="edge")
        m2.set_plate(sel, Fdn, strength_reduction_factor=1.0)  # rough
        sel = m2.select([R, -S/2], types="edge")
        m2.set_plate(sel, Fdn, strength_reduction_factor=1.0)  # rough

        mod = m2.revolve_2d_to_3d(angle_deg=180, N=N_sectors, name=name)
        m2.delete()

        try:
            sel = mod.select([0, 0, -H_dom/2], types="edge")
            if sel:
                mod.delete_shapes(sel)
        except Exception:
            pass

        mod.add_vertex([0, 0, 0])
        sel_c = mod.select([0, 0, 0], types="vertex")
        mod.set_resultpoint(sel_c)

        # Plate BCs (symmetry y=0)
        sel_edge = mod.select([0, 0, 0], types="edge")
        mod.set_plate_bc(sel_edge, displacement_x="fixed", displacement_y="fixed",
                         displacement_z="free", displacement_rotation="fixed")
        for x_sign in [1, -1]:
            try:
                sel = mod.select([x_sign * R, 0, -S/2], types="edge")
                mod.set_plate_bc(sel, displacement_x="free", displacement_y="fixed",
                                 displacement_z="free", displacement_rotation="fixed")
            except Exception:
                pass

        mod.set_standard_fixities()

        mod.set_point_bc(shapes=sel_c,
                         displacement_x='fixed', displacement_y='fixed',
                         displacement_z='free',
                         displacement_rotation_x='fixed',
                         displacement_rotation_y='fixed',
                         displacement_rotation_z='fixed',
                         )

        for ang in np.linspace(0, 180, N_sectors + 1):
            try:
                sf = mod.select([R*np.cos(np.radians(ang)),
                                 R*np.sin(np.radians(ang)), -S], types="vertex")
                if sf:
                    mod.set_mesh_fan(shapes=sf, fan_angle=30)
            except Exception:
                pass

        mod.set_analysis_properties(
            analysis_type="load_multiplier", element_type="mixed",
            no_of_elements=N_el, mesh_adaptivity="yes",
            adaptivity_iterations=3, start_elements=N_el_start,
            design_approach='unity',
        )
        mod.zoom_all()
        return mod, sel_c

    # --- Probe 1: Vmax ---
    print("\n  Probe: Vmax (pure vertical compression)")
    mod_v, sel_v = build_skirted_model("Vulpe_Vmax")
    mod_v.set_point_load(sel_v, -1, direction="z", option="multiplier")

    t0 = time.time()
    prj.run_analysis()
    dt = time.time() - t0
    lm_v = get_load_multiplier(mod_v)

    if lm_v is not None:
        V_ult = abs(float(lm_v)) * 2
        NcV = V_ult / (A * su)
        err_V = (NcV - ref["NcV"]) / ref["NcV"] * 100
        print(f"  V_ult = {V_ult:.1f} kN, NcV = {NcV:.3f} "
              f"(ref = {ref['NcV']}, error = {err_V:+.1f}%, time = {dt:.0f}s)")
        results["vulpe_NcV"] = {"op3": round(NcV, 3), "ref": ref["NcV"],
                                 "error_pct": round(err_V, 1)}
    else:
        print("  ERROR: no result")
        results["vulpe_NcV"] = {"error": "no result"}
    mod_v.delete()

    # --- Probe 2: Hmax ---
    print("\n  Probe: Hmax (pure horizontal)")
    mod_h, sel_h = build_skirted_model("Vulpe_Hmax")

    # Change BCs for horizontal probe
    sel_edge = mod_h.select([0, 0, 0], types="edge")
    bcs = mod_h.get_features(sel_edge)
    mod_h.remove_features(bcs)
    mod_h.set_plate_bc(sel_edge, displacement_x="free", displacement_y="fixed",
                       displacement_z="fixed", displacement_rotation="fixed")

    # Remove point BC, reapply for H probe
    pbc = mod_h.get_features(sel_h)
    mod_h.remove_features(pbc)
    mod_h.set_point_bc(shapes=sel_h,
                       displacement_x='free', displacement_y='fixed',
                       displacement_z='fixed',
                       displacement_rotation_x='fixed',
                       displacement_rotation_y='fixed',
                       displacement_rotation_z='fixed',
                       )

    mod_h.set_point_load(sel_h, 1, direction="x", option="multiplier")

    t0 = time.time()
    prj.run_analysis()
    dt = time.time() - t0
    lm_h = get_load_multiplier(mod_h)

    if lm_h is not None:
        H_ult = abs(float(lm_h)) * 2
        NcH = H_ult / (A * su)
        err_H = (NcH - ref["NcH"]) / ref["NcH"] * 100
        print(f"  H_ult = {H_ult:.1f} kN, NcH = {NcH:.3f} "
              f"(ref = {ref['NcH']}, error = {err_H:+.1f}%, time = {dt:.0f}s)")
        results["vulpe_NcH"] = {"op3": round(NcH, 3), "ref": ref["NcH"],
                                 "error_pct": round(err_H, 1)}
    else:
        print("  ERROR: no result")
        results["vulpe_NcH"] = {"error": "no result"}
    mod_h.delete()

    # --- Probe 3: Mmax ---
    print("\n  Probe: Mmax (pure moment)")
    mod_m, sel_m = build_skirted_model("Vulpe_Mmax")

    # Apply moment as eccentric load at edge
    sel_edge = mod_m.select([0, 0, 0], types="edge")
    bcs = mod_m.get_features(sel_edge)
    mod_m.remove_features(bcs)
    mod_m.set_plate_bc(sel_edge, displacement_x="free", displacement_y="fixed",
                       displacement_z="free", displacement_rotation="fixed")

    pbc = mod_m.get_features(sel_m)
    mod_m.remove_features(pbc)

    # Load at edge: F * R = moment
    mod_m.add_vertex([R, 0, 0])
    sel_edge_pt = mod_m.select([R, 0, 0], types="vertex")
    mod_m.set_point_load(sel_edge_pt, -1, direction="z", option="multiplier")
    mod_m.set_resultpoint(sel_edge_pt)

    t0 = time.time()
    prj.run_analysis()
    dt = time.time() - t0
    lm_m = get_load_multiplier(mod_m)

    if lm_m is not None:
        F_ult = abs(float(lm_m)) * 2
        M_ult = F_ult * R   # moment = force * arm
        NcM = M_ult / (A * su * D)
        err_M = (NcM - ref["NcM"]) / ref["NcM"] * 100
        print(f"  F_ult = {F_ult:.1f} kN, M_ult = {M_ult:.1f} kNm, "
              f"NcM = {NcM:.3f} (ref = {ref['NcM']}, error = {err_M:+.1f}%, "
              f"time = {dt:.0f}s)")
        results["vulpe_NcM"] = {"op3": round(NcM, 3), "ref": ref["NcM"],
                                 "error_pct": round(err_M, 1)}
    else:
        print("  ERROR: no result")
        results["vulpe_NcM"] = {"error": "no result"}
    mod_m.delete()


# ============================================================
# Benchmark #18: Achmus (2013) Hu in dense sand
#   D=12m, L=9m (L/D=0.75), dense sand phi=40
#   Published: Hu ~ 45 MN (pure horizontal)
# ============================================================
def run_achmus_benchmark(prj):
    """Validate horizontal capacity in sand against Achmus 2013."""


    print("\n" + "=" * 60)
    print("[#18] Achmus (2013) — Hu in dense sand (D=12m, L=9m)")
    print("=" * 60)

    D = 12.0;  R = D / 2;  S = 9.0  # L/D = 0.75
    phi = 40.0    # degrees
    psi = 10.0    # dilation angle (nonassociated)
    gamma = 11.0  # kN/m3 (submerged)
    c = 0.2       # small cohesion for numerical stability
    E_ref = 60e3  # kPa reference stiffness at 100 kPa
    nu = 0.3

    N_SIDES = 24;  N_sectors = N_SIDES // 2
    L_dom = 12 * R;  H_dom = 8 * R
    N_el = 10000;  N_el_start = 6000

    ref_Hu_MN = 45.0  # MN (approx from Achmus 2013 Fig. 8)

    print(f"  D = {D}m, L = {S}m, L/D = {S/D:.2f}")
    print(f"  phi = {phi}, gamma' = {gamma}, expected Hu ~ {ref_Hu_MN} MN")

    # Stress-dependent E: E(z) = E_ref * (sigma'_v / 100)^0.5
    # sigma'_v = gamma * z
    # For limit analysis, use representative constant values
    # At mid-depth (z = S/2 = 4.5m): sigma'_v = 11 * 4.5 = 49.5 kPa
    # E_mid = E_ref * (49.5/100)^0.5 = 60000 * 0.703 = 42180 kPa
    E_mid = E_ref * (gamma * S / 2 / 100) ** 0.5

    Sand = prj.MohrCoulomb(
        name="Dense_Sand",
        drainage='always_drained',
        gamma_sat=gamma + 10.0,  # total = submerged + water
        gamma_dry=gamma + 10.0,
        E=E_mid, nu=nu,
        phi=phi,
        flow_rule='nonassociated',
        psi=psi,
        c=c,
        tension_cutoff='yes', sigma_t=0,
        color=rgb(210, 190, 140),
    )
    Fdn = prj.RigidPlate(name="Fdn_Sand", color=rgb(130, 160, 180))

    # Build skirted model via 2D revolve
    m2 = prj.create_model(name="AX_Achmus", model_type="plane_strain")
    m2.add_rectangle([0, -H_dom], [L_dom/2, 0])
    m2.add_line([0, 0], [R, 0])
    m2.add_line([R, 0], [R, -S])

    sel = m2.select([L_dom/4, -H_dom/2], types="face")
    m2.set_solid(sel, Sand)
    sel = m2.select([R/2, 0], types="edge")
    m2.set_plate(sel, Fdn, strength_reduction_factor=0.67)
    sel = m2.select([R, -S/2], types="edge")
    m2.set_plate(sel, Fdn, strength_reduction_factor=0.67)

    mod = m2.revolve_2d_to_3d(angle_deg=180, N=N_sectors, name="Achmus_Hmax")
    m2.delete()

    try:
        sel = mod.select([0, 0, -H_dom/2], types="edge")
        if sel:
            mod.delete_shapes(sel)
    except Exception:
        pass

    mod.add_vertex([0, 0, 0])
    sel_c = mod.select([0, 0, 0], types="vertex")
    mod.set_resultpoint(sel_c)

    # Horizontal probe BCs
    sel_edge = mod.select([0, 0, 0], types="edge")
    mod.set_plate_bc(sel_edge, displacement_x="free", displacement_y="fixed",
                     displacement_z="fixed", displacement_rotation="fixed")
    for x_sign in [1, -1]:
        try:
            sel = mod.select([x_sign * R, 0, -S/2], types="edge")
            mod.set_plate_bc(sel, displacement_x="free", displacement_y="fixed",
                             displacement_z="free", displacement_rotation="fixed")
        except Exception:
            pass

    mod.set_standard_fixities()

    mod.set_point_bc(shapes=sel_c,
                     displacement_x='free', displacement_y='fixed',
                     displacement_z='fixed',
                     displacement_rotation_x='fixed',
                     displacement_rotation_y='fixed',
                     displacement_rotation_z='fixed',
                     )

    for ang in np.linspace(0, 180, N_sectors + 1):
        try:
            sf = mod.select([R*np.cos(np.radians(ang)),
                             R*np.sin(np.radians(ang)), -S], types="vertex")
            if sf:
                mod.set_mesh_fan(shapes=sf, fan_angle=30)
        except Exception:
            pass

    mod.set_analysis_properties(
        analysis_type="load_multiplier", element_type="mixed",
        no_of_elements=N_el, mesh_adaptivity="yes",
        adaptivity_iterations=3, start_elements=N_el_start,
        design_approach='unity',
    )

    # Horizontal multiplier load
    mod.set_point_load(sel_c, 1, direction="x", option="multiplier")
    mod.zoom_all()

    print("  Running analysis (Hmax in sand)...")
    t0 = time.time()
    prj.run_analysis()
    dt = time.time() - t0

    lm = get_load_multiplier(mod)
    if lm is not None:
        H_ult_kN = abs(float(lm)) * 2  # half-model -> full
        H_ult_MN = H_ult_kN / 1000
        err = (H_ult_MN - ref_Hu_MN) / ref_Hu_MN * 100
        print(f"  H_ult = {H_ult_MN:.1f} MN (ref ~ {ref_Hu_MN} MN, "
              f"error = {err:+.1f}%, time = {dt:.0f}s)")
        results["achmus_Hu"] = {
            "Hu_op3_MN": round(H_ult_MN, 1), "Hu_ref_MN": ref_Hu_MN,
            "error_pct": round(err, 1), "time_s": round(dt, 1),
            "config": {"D_m": D, "L_m": S, "phi": phi, "gamma": gamma},
        }
    else:
        print("  ERROR: no result")
        results["achmus_Hu"] = {"error": "no result"}

    mod.delete()


# ============================================================
# Main
# ============================================================
def main():
    print("=" * 72)
    print(" OptumGX Capacity Validation -- Benchmarks #14, #15, #18")
    print("=" * 72)

    T0 = time.time()
    gx = GX()
    prj = gx.create_project("Capacity_Validation")

    # Delete default model
    try:
        prj.get_model("Model A").delete()
    except Exception:
        pass

    run_fu_bienen_benchmark(prj)
    run_vulpe_benchmark(prj)
    run_achmus_benchmark(prj)

    # Save results
    RESULTS_FILE.write_text(json.dumps(results, indent=2), encoding="utf-8")
    total = time.time() - T0
    print(f"\n{'=' * 72}")
    print(f"  Total time: {total:.0f}s")
    print(f"  Results saved: {RESULTS_FILE}")
    print(f"{'=' * 72}")

    # Summary table
    print("\n  Summary:")
    for key, val in results.items():
        if "error_pct" in val:
            print(f"    {key}: error = {val['error_pct']:+.1f}%")
        elif "error" in val:
            print(f"    {key}: {val['error']}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
