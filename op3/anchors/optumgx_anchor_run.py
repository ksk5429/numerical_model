# -*- coding: utf-8 -*-
"""
OptumGX driver for suction-anchor VHM envelope + dissipation field.

This script is NOT intended to be run by a stock Python interpreter.
It runs inside the OptumGX desktop scripting console, which exposes
the `from OptumGX import *` symbols (GX, ParameterMap, rgb, etc.). Any
Python environment without those symbols will raise ImportError on
the first line -- this is deliberate, so that the pure-Python Op^3
layer never accidentally "simulates" OptumGX output.

Usage
-----
1. Open OPTUM GX on your workstation.
2. In the scripting console, load this file (File -> Open Script, or
   paste the contents).
3. Edit the CONFIGURATION section at the top (D, L, su profile,
   load angles). Default is D = 5 m, L = 15 m, NC clay.
4. Press Run. OptumGX will build the 3D model, run every probe in the
   VHM sweep, extract plate pressures + collapse mechanism, and save
   CSVs under `results_anchor_<tag>/`.

The Op^3 Python layer then reads those CSVs via:
    op3.anchors.capacity_fe_calibrated(..., fe_csv=...)
    op3.anchors.optimal_padeye_from_dissipation(..., dissipation_csv=...)

Output files (in `OUTPUT_DIR`)
-----------------------------
    envelope.csv               columns: angle_deg, H_ult_kN, V_ult_kN
    dissipation.csv            columns: depth_m, w_z, D_total_kJ
    plates_<tag>.xlsx          raw plate-element data per probe
    profile_<tag>_pressure.csv depth-wise skirt reactions per probe
    summary.json               capacities, times, config

References
----------
Follows the same conventions as
``op3/optumgx_interface/optumgx_vhm_full.py`` (the bucket driver);
see that file for the provenance of the plate-force extraction logic
and the mesh-adaptivity settings.

Author: Kim Kyeong Sun (Seoul National University), 2026.
"""
# ---------------------------------------------------------------------------
# OptumGX scripting console imports -- guarded so importing this file
# from a non-OptumGX interpreter gives a helpful message rather than
# a cryptic NameError later.
# ---------------------------------------------------------------------------
try:
    from OptumGX import *  # noqa: F401,F403 -- provided by OptumGX GUI
    _OPTUMGX_AVAILABLE = True
except ImportError:
    _OPTUMGX_AVAILABLE = False


import json
import os
import re
import time
from pathlib import Path

import numpy as np
import pandas as pd


# =============================================================================
# 1. CONFIGURATION -- EDIT THESE FOR EACH ANCHOR RUN
# =============================================================================

# Geometry
D = 5.0          # outer diameter [m]
R = D / 2.0
L = 15.0         # skirt length [m]                (anchor, not bucket)
WALL_MM = 30.0   # wall thickness [mm]             (used for post-processing only)

# Domain sizing -- mirror bucket driver convention (L_dom >> R, H_dom >> L)
L_DOM = 20 * R
H_DOM = max(15 * R, 1.5 * L)

# Soil: linearly increasing undrained shear strength
SU0 = 5.0        # s_u at mudline [kPa]
K_SU = 1.5       # gradient [kPa/m]
GAMMA_EFF = 6.0  # effective unit weight [kN/m^3]
ALPHA_INTERFACE = 0.65   # adhesion factor on skirt/lid

# Mesh / sectors / fan
N_SIDES = 24
N_SECTORS = N_SIDES // 2
N_EL = 15000
N_EL_START = 10000
FAN_ANGLE = 30

# Envelope sweep -- load angles at padeye (deg from horizontal)
#   0 deg  = pure horizontal (H_ult)
#   90 deg = pure vertical uplift (V_ult)
#   intermediate values sample the V-H envelope
SWEEP_ANGLES_DEG = [0.0, 15.0, 30.0, 45.0, 60.0, 75.0, 90.0]

# Design angle at which to extract the plastic-dissipation field for
# the padeye-centroid method. Pick a representative mooring angle.
DISSIPATION_ANGLE_DEG = 30.0

# Padeye depth below mudline [m] -- where the probe load is applied
PADEYE_DEPTH_M = 10.0

# Project tag (folder suffix)
TAG = f"D{D:g}_L{L:g}_a{int(ALPHA_INTERFACE*100)}"
OUTPUT_DIR = Path(f"results_anchor_{TAG}")
OUTPUT_DIR.mkdir(exist_ok=True)


# =============================================================================
# 2. UTILITIES -- copied verbatim from optumgx_vhm_full.py to keep
#    extraction semantics identical. If that file is refactored, keep
#    these helpers in sync.
# =============================================================================

def parse_val(attr):
    """Parse any OptumGX output attribute to Python numeric."""
    if attr is None:
        return None
    if isinstance(attr, (int, float)):
        return attr
    if isinstance(attr, np.ndarray):
        return attr.tolist()
    if isinstance(attr, (list, tuple)):
        return [float(x) if isinstance(x, (int, float, np.floating)) else x
                for x in attr]
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


def gprop(obj, name):
    return parse_val(getattr(obj, name, None))


def collect_plates(output):
    """Collect plate-element coords, pressures, nodal forces, collapse
    mechanism. Same schema as bucket driver."""
    rows = []
    for plate in output.plate:
        row = {}
        if hasattr(plate, "general"):
            row["material"] = gprop(plate.general, "material_name")
        if hasattr(plate, "topology"):
            top = plate.topology
            for c in ["X", "Y", "Z"]:
                v = gprop(top, c)
                if isinstance(v, list):
                    for j, val in enumerate(v, 1):
                        row[f"{c}_{j}"] = val
        if hasattr(plate, "results"):
            res = plate.results
            for cat_name, props in [
                ("total_pressures", ["sigma_plus", "sigma_minus",
                                     "tau_plus", "tau_minus"]),
                ("nodal_forces", ["q_x", "q_y", "q_z"]),
                ("collapse_mechanism", ["u_x", "u_y", "u_z", "u_norm"]),
            ]:
                cat = getattr(res, cat_name, None)
                if cat is None:
                    continue
                for prop in props:
                    v = gprop(cat, prop)
                    prefix = prop if cat_name == "total_pressures" else \
                             f"F_{prop}" if cat_name == "nodal_forces" else \
                             f"cm_{prop}"
                    if isinstance(v, list):
                        for j, val in enumerate(v, 1):
                            row[f"{prefix}_{j}"] = val
                    elif v is not None:
                        row[prefix] = v
        rows.append(row)
    return pd.DataFrame(rows)


def add_geometry(df):
    """Centroid + area + normal + radial coord + part classification."""
    if "X_1" not in df.columns:
        return df
    p1 = df[["X_1", "Y_1", "Z_1"]].values
    p2 = df[["X_2", "Y_2", "Z_2"]].values
    p3 = df[["X_3", "Y_3", "Z_3"]].values
    df["Xc"] = (p1[:, 0] + p2[:, 0] + p3[:, 0]) / 3
    df["Yc"] = (p1[:, 1] + p2[:, 1] + p3[:, 1]) / 3
    df["Zc"] = (p1[:, 2] + p2[:, 2] + p3[:, 2]) / 3
    v1, v2 = p2 - p1, p3 - p1
    cross = np.cross(v1, v2)
    norms = np.maximum(np.linalg.norm(cross, axis=1, keepdims=True), 1e-20)
    df["area"] = norms.flatten() / 2
    df["nx"] = cross[:, 0] / norms.flatten()
    df["ny"] = cross[:, 1] / norms.flatten()
    df["nz"] = cross[:, 2] / norms.flatten()
    df["Rc"] = np.sqrt(df["Xc"] ** 2 + df["Yc"] ** 2)
    df["theta"] = np.arctan2(df["Yc"], df["Xc"])
    df["part"] = "unknown"
    df.loc[df["Zc"] > -0.3, "part"] = "lid"
    df.loc[(df["Zc"] < -0.3) & (df["Zc"] > -(L - 0.3)) &
           (df["Rc"] > R * 0.8), "part"] = "skirt_wall"
    df.loc[df["Zc"] < -(L - 0.3), "part"] = "tip_zone"
    return df


def dissipation_profile(df, n_slices=50):
    """Depth-wise plastic dissipation weight w(z) and total D(z) [kJ].

    Uses the collapse-mechanism displacement field ``u_norm`` times
    the nodal-force magnitude as a proxy for local plastic work. The
    proxy is integrated over the skirt-wall plates in each depth slice
    and normalised so that sum w_z * dz = 1. ``D_total_kJ`` is the
    unnormalised integrated plastic work, in kJ (per half-model).
    """
    if "cm_u_norm" not in df.columns and "F_q_x_1" not in df.columns:
        # Neither mechanism nor nodal forces available -- can't build psi
        return pd.DataFrame(columns=["depth_m", "w_z", "D_total_kJ"])

    f_cols = sorted([c for c in df.columns if c.startswith("F_q_")])
    cm_cols = sorted([c for c in df.columns if c.startswith("cm_u_norm")])

    def _row_plastic_work(row):
        # scalar proxy: sum over nodes of |F_q| * |cm_u|
        F = np.sqrt(
            (row.get("F_q_x_1", 0) or 0) ** 2
            + (row.get("F_q_y_1", 0) or 0) ** 2
            + (row.get("F_q_z_1", 0) or 0) ** 2
        )
        u = row.get("cm_u_norm_1", 0) or 0
        return abs(F * u)

    df = df.copy()
    df["dDiss"] = df.apply(_row_plastic_work, axis=1)
    z_top, z_bot = df["Zc"].max(), df["Zc"].min()
    edges = np.linspace(z_top, z_bot, n_slices + 1)
    rows = []
    for i in range(n_slices):
        zt, zb = edges[i], edges[i + 1]
        zm = 0.5 * (zt + zb)
        dz = abs(zt - zb)
        mask = (df["Zc"] <= zt) & (df["Zc"] > zb) & \
               (df["part"] == "skirt_wall")
        D_slice = float(df.loc[mask, "dDiss"].sum())
        depth_from_mudline = -zm   # convention: +z downward below mudline
        rows.append(dict(depth_m=depth_from_mudline,
                         D_total_kJ=D_slice,
                         dz=dz))
    out = pd.DataFrame(rows).sort_values("depth_m").reset_index(drop=True)
    total = float(out["D_total_kJ"].sum())
    if total > 0:
        out["w_z"] = out["D_total_kJ"] / total
    else:
        out["w_z"] = 0.0
    return out[["depth_m", "w_z", "D_total_kJ"]]


# =============================================================================
# 3. MODEL BUILDER -- long-slender anchor version
# =============================================================================

def build_anchor_model(prj, name):
    """Build a 3D circular anchor of D x L via 2D revolution.

    Returns (mod, sel_padeye_vertex) where sel_padeye_vertex is the
    vertex at depth PADEYE_DEPTH_M used for probe-load application.
    """
    if not _OPTUMGX_AVAILABLE:
        raise RuntimeError(
            "OptumGX scripting symbols are not available. This driver "
            "must be run from inside the OptumGX desktop scripting "
            "console. See docs/ANCHOR_OPTUMGX_GUIDE.md."
        )

    # Soil ParameterMap: linearly increasing s_u
    XYZ = np.array([
        [-L_DOM, 0, 0], [L_DOM, 0, 0],
        [L_DOM, L_DOM / 2, 0], [-L_DOM, L_DOM / 2, 0],
        [-L_DOM, 0, -H_DOM], [L_DOM, 0, -H_DOM],
        [L_DOM, L_DOM / 2, -H_DOM], [-L_DOM, L_DOM / 2, -H_DOM],
    ])
    su_top = SU0
    su_bot = SU0 + K_SU * H_DOM
    su_vals = np.array([su_top] * 4 + [su_bot] * 4)
    sumap = ParameterMap(np.column_stack([XYZ, su_vals]))

    Soil = prj.Tresca(name=f"Soil_{name}", cu=sumap,
                      gamma_dry=GAMMA_EFF, color=rgb(195, 165, 120))
    Anchor = prj.RigidPlate(name=f"Anchor_{name}", color=rgb(130, 160, 180))

    m2 = prj.create_model(name=f"AX_{name}", model_type="plane_strain")
    m2.add_rectangle([0, -H_DOM], [L_DOM / 2, 0])
    m2.add_line([0, 0], [R, 0])            # lid
    m2.add_line([R, 0], [R, -L])           # skirt (full L, not L_bucket)
    sel = m2.select([L_DOM / 4, -H_DOM / 2], types="face")
    m2.set_solid(sel, Soil)
    sel = m2.select([R / 2, 0], types="edge")
    m2.set_plate(sel, Anchor, strength_reduction_factor=ALPHA_INTERFACE)
    sel = m2.select([R, -L / 2], types="edge")
    m2.set_plate(sel, Anchor, strength_reduction_factor=ALPHA_INTERFACE)

    mod = m2.revolve_2d_to_3d(angle_deg=180, N=N_SECTORS, name=name)
    m2.delete()

    # Clean axis edge
    try:
        sel_axis = mod.select([0, 0, -H_DOM / 2], types="edge")
        if sel_axis:
            mod.delete_shapes(sel_axis)
    except Exception:
        pass

    # Add padeye vertex on centre axis at PADEYE_DEPTH_M below mudline.
    # Loads will be applied here; this is what gives the anchor probe
    # physical meaning (vs the bucket driver's centre-of-lid load).
    mod.add_vertex([0, 0, -PADEYE_DEPTH_M])
    sel_padeye = mod.select([0, 0, -PADEYE_DEPTH_M], types="vertex")
    mod.set_resultpoint(sel_padeye)

    # Plate BCs: lid edge and skirt edges rigid-body-constrained in
    # the y=0 symmetry plane
    sel = mod.select([0, 0, 0], types="edge")
    mod.set_plate_bc(sel, displacement_x="free", displacement_y="fixed",
                     displacement_z="free", displacement_rotation="fixed")
    for zr in [-L / 2, -L + 1e-3]:
        sel = mod.select([R, 0, zr], types="edge")
        mod.set_plate_bc(sel, displacement_x="free",
                         displacement_y="fixed",
                         displacement_z="free",
                         displacement_rotation="fixed")

    mod.set_standard_fixities()

    # Mesh fans at skirt tip for improved accuracy of the plastic hinge
    for ang in np.linspace(0, 180, N_SECTORS + 1):
        try:
            sf = mod.select([R * np.cos(np.radians(ang)),
                             R * np.sin(np.radians(ang)), -L],
                            types="vertex")
            if sf:
                mod.set_mesh_fan(shapes=sf, fan_angle=FAN_ANGLE)
        except Exception:
            pass

    mod.set_analysis_properties(
        analysis_type="load_multiplier", element_type="mixed",
        no_of_elements=N_EL, mesh_adaptivity="yes",
        adaptivity_iterations=3, start_elements=N_EL_START,
        design_approach="unity",
    )
    mod.zoom_all()
    return mod, sel_padeye


# =============================================================================
# 4. PROBE RUNNER -- inclined load at padeye
# =============================================================================

def run_inclined_probe(prj, angle_deg: float):
    """Apply a unit inclined load vector at the padeye vertex and
    request OptumGX's limit-analysis load multiplier.

    Inclined load direction is (+x cos, 0, +z sin) since +z is upward.
    """
    name = f"Probe_a{angle_deg:g}"
    mod, sel_padeye = build_anchor_model(prj, name)

    cx = np.cos(np.radians(angle_deg))
    cz = np.sin(np.radians(angle_deg))
    mod.set_point_load(sel_padeye, cx, direction="x", option="multiplier")
    mod.set_point_load(sel_padeye, cz, direction="z", option="multiplier")

    t0 = time.time()
    prj.run_analysis()
    dt = time.time() - t0
    lm = float(mod.output.global_results.load_multiplier)  # total |T| kN (half)
    df = collect_plates(mod.output)
    # H and V components of the total inclined capacity
    H = lm * cx
    V = lm * cz
    print(f"  angle={angle_deg:>5.1f} deg  T={lm:8.1f} kN  "
          f"H={H:8.1f}  V={V:8.1f}  t={dt:.0f}s  plates={len(df)}")
    mod.delete()
    return lm, H, V, df, dt


# =============================================================================
# 5. MAIN -- runs the full sweep, writes the CSVs Op^3 needs
# =============================================================================

def main():
    if not _OPTUMGX_AVAILABLE:
        print("=" * 70)
        print("ERROR: OptumGX Python bindings not found.")
        print("This driver must be run from the OptumGX desktop ")
        print("scripting console. See docs/ANCHOR_OPTUMGX_GUIDE.md.")
        print("=" * 70)
        return 1

    print("=" * 70)
    print(f"Op^3 anchor OptumGX driver (tag = {TAG})")
    print(f"  D = {D} m, L = {L} m, L/D = {L/D:.2f}, alpha = {ALPHA_INTERFACE}")
    print(f"  su(z) = {SU0} + {K_SU} z kPa, gamma' = {GAMMA_EFF} kN/m3")
    print(f"  Padeye depth = {PADEYE_DEPTH_M} m below mudline")
    print(f"  Sweep angles = {SWEEP_ANGLES_DEG}")
    print(f"  Dissipation probe at {DISSIPATION_ANGLE_DEG} deg")
    print("=" * 70)
    T_START = time.time()

    gx = GX()
    prj = gx.create_project(f"OP3_ANCHOR_{TAG}")
    try:
        prj.get_model("Model A").delete()
    except Exception:
        pass

    envelope_rows = []
    plate_dfs = {}
    for ang in SWEEP_ANGLES_DEG:
        print(f"\n[probe {ang:.0f} deg] ...")
        lm, H, V, df, dt = run_inclined_probe(prj, ang)
        envelope_rows.append(dict(angle_deg=float(ang),
                                  T_ult_kN_half=float(lm),
                                  H_ult_kN=float(H * 2),   # full anchor (x2)
                                  V_ult_kN=float(V * 2),
                                  time_s=float(dt)))
        if "X_1" in df.columns:
            df = add_geometry(df)
        plate_dfs[ang] = df
        df.to_excel(OUTPUT_DIR / f"plates_a{ang:g}.xlsx", index=False)

    envelope = pd.DataFrame(envelope_rows)
    envelope.to_csv(OUTPUT_DIR / "envelope.csv", index=False)
    print("\nWrote envelope.csv")

    # --- Dissipation field at the design angle ------------------------
    if DISSIPATION_ANGLE_DEG in plate_dfs:
        df_d = plate_dfs[DISSIPATION_ANGLE_DEG]
    else:
        # Re-run if the requested angle was not in the sweep
        print(f"\n[dissipation probe {DISSIPATION_ANGLE_DEG} deg] ...")
        _, _, _, df_d, _ = run_inclined_probe(prj, DISSIPATION_ANGLE_DEG)
        df_d = add_geometry(df_d)

    diss = dissipation_profile(df_d, n_slices=50)
    diss.to_csv(OUTPUT_DIR / "dissipation.csv", index=False)
    print("Wrote dissipation.csv")

    # --- Summary ------------------------------------------------------
    summary = dict(
        config=dict(D=D, L=L, L_over_D=L / D, alpha=ALPHA_INTERFACE,
                    padeye_depth_m=PADEYE_DEPTH_M,
                    su0=SU0, k_su=K_SU, gamma_eff=GAMMA_EFF),
        envelope=envelope_rows,
        total_time_s=time.time() - T_START,
    )
    with open(OUTPUT_DIR / "summary.json", "w") as f:
        json.dump(summary, f, indent=2)

    print(f"\nAll outputs in {OUTPUT_DIR.resolve()}")
    print("Now, from any Op^3 Python session, run:")
    print(f"  from op3.anchors import capacity_fe_calibrated")
    print(f"  r = capacity_fe_calibrated(anchor, soil, "
          f"fe_csv=r'{(OUTPUT_DIR/'envelope.csv').resolve()}')")
    print(f"  from op3.anchors import optimal_padeye_from_dissipation")
    print(f"  z_opt = optimal_padeye_from_dissipation(anchor, "
          f"dissipation_csv=r'{(OUTPUT_DIR/'dissipation.csv').resolve()}')")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
