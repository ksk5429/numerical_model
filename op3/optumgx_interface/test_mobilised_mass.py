# -*- coding: utf-8 -*-
"""
Test: What data is available from OptumGX collapse mechanism output?
Runs a quick small model and inspects ALL available output attributes
for solid elements, plate elements, and global/critical results.
Goal: determine if mobilised mass / dissipation / collapse zone volume
can be reliably extracted.
"""
from OptumGX import *
import numpy as np
import re
import time
import json

D = 8.0; R = D/2; S = float('nan')  # <REDACTED>
N_sectors = 12
L_dom = 20*R; H_dom = 15*R
su0 = 15.0; k_su = 20.0; gamma = 10.0; a_int = 0.67

import math
if math.isnan(S):
    raise RuntimeError(
        "Proprietary dimension S (skirt length) not configured. "
        "Set OP3_SKIRT_LENGTH env var or replace float('nan') with actual value."
    )

print("=" * 70)
print("TEST: Mobilised Mass / Collapse Mechanism Data Extraction")
print("=" * 70)

gx = GX()
prj = gx.create_project("Test_MobilisedMass")
prj.get_model("Model A").delete()

# Build quick model (small mesh for speed)
XYZ = np.array([
    [-L_dom,0,0],[L_dom,0,0],[L_dom,L_dom/2,0],[-L_dom,L_dom/2,0],
    [-L_dom,0,-H_dom],[L_dom,0,-H_dom],[L_dom,L_dom/2,-H_dom],[-L_dom,L_dom/2,-H_dom],
])
su_vals = np.array([su0]*4 + [su0+k_su*H_dom]*4)
sumap = ParameterMap(np.column_stack([XYZ, su_vals]))

Soil = prj.Tresca(name="Soil_test", cu=sumap, gamma_dry=gamma,
                   color=rgb(195,165,120))
Fdn = prj.RigidPlate(name="Fdn_test", color=rgb(130,160,180))

m2 = prj.create_model(name="AX_test", model_type="plane_strain")
m2.add_rectangle([0,-H_dom],[L_dom/2,0])
m2.add_line([0,0],[R,0])
m2.add_line([R,0],[R,-S])
sel = m2.select([L_dom/4,-H_dom/2], types="face")
m2.set_solid(sel, Soil)
sel = m2.select([R/2,0], types="edge")
m2.set_plate(sel, Fdn, strength_reduction_factor=a_int)
sel = m2.select([R,-S/2], types="edge")
m2.set_plate(sel, Fdn, strength_reduction_factor=a_int)

mod = m2.revolve_2d_to_3d(angle_deg=180, N=N_sectors, name="Test_V")
m2.delete()
try:
    sel = mod.select([0,0,-H_dom/2], types="edge")
    if sel: mod.delete_shapes(sel)
except Exception: pass  # edge cleanup after revolution

mod.add_vertex([0,0,0])
sel_c = mod.select([0,0,0], types="vertex")
mod.set_resultpoint(sel_c)

sel = mod.select([0,0,0], types="edge")
mod.set_plate_bc(sel, displacement_x="fixed", displacement_y="fixed",
                 displacement_z="free", displacement_rotation="fixed")
sel = mod.select([R,0,-S/2], types="edge")
mod.set_plate_bc(sel, displacement_x="free", displacement_y="fixed",
                 displacement_z="free", displacement_rotation="fixed")
sel = mod.select([-R,0,-S/2], types="edge")
mod.set_plate_bc(sel, displacement_x="free", displacement_y="fixed",
                 displacement_z="free", displacement_rotation="fixed")
mod.set_standard_fixities()
mod.set_point_bc(shapes=sel_c, displacement_x='fixed', displacement_y='fixed',
                 displacement_z='free', displacement_rotation_x='fixed',
                 displacement_rotation_y='fixed', displacement_rotation_z='fixed',
                 use_local_coord=False)

mod.set_analysis_properties(
    analysis_type='load_multiplier', element_type="mixed",
    no_of_elements=3000, mesh_adaptivity='yes',
    adaptivity_iterations=2, start_elements=1500,
    design_approach='unity',
)
mod.zoom_all()
mod.set_point_load(sel_c, -1, direction="z", option="multiplier")

print("\n[1] Running Vmax analysis (3000 elements, fast)...")
t0 = time.time()
prj.run_analysis()
dt = time.time() - t0
lm = float(mod.output.global_results.load_multiplier)
print(f"    Vmax = {lm:.0f} kN, time = {dt:.0f}s")

# =============================================================================
# DEEP INSPECTION OF ALL OUTPUT OBJECTS
# =============================================================================
output = mod.output

print("\n[2] Output object attributes:")
out_attrs = [a for a in dir(output) if not a.startswith('_')]
print(f"    {out_attrs}")

# Global results
print("\n[3] Global results:")
gr = output.global_results
gr_attrs = [a for a in dir(gr) if not a.startswith('_')]
print(f"    Attributes: {gr_attrs}")
for attr in gr_attrs:
    try:
        val = getattr(gr, attr)
        if not callable(val):
            print(f"    {attr} = {val}")
    except Exception: pass  # attribute may not be readable

# Critical results
print("\n[4] Critical results:")
try:
    cr = output.critical_results
    cr_attrs = [a for a in dir(cr) if not a.startswith('_')]
    print(f"    Attributes: {cr_attrs}")
    for attr in cr_attrs:
        try:
            val = getattr(cr, attr)
            if not callable(val):
                s = str(val)[:200]
                print(f"    {attr} = {s}")
        except Exception: pass  # attribute may not be readable
except Exception as e:
    print(f"    Error: {e}")

# First solid element - deep dive
print("\n[5] First solid element (deep inspection):")
solid_iter = iter(output.solid)
solid0 = next(solid_iter)

print(f"    Top-level attrs: {[a for a in dir(solid0) if not a.startswith('_')]}")

if hasattr(solid0, 'general'):
    gen = solid0.general
    print(f"    general attrs: {[a for a in dir(gen) if not a.startswith('_')]}")
    for attr in [a for a in dir(gen) if not a.startswith('_')]:
        try:
            val = getattr(gen, attr)
            if not callable(val):
                print(f"      general.{attr} = {str(val)[:150]}")
        except Exception: pass  # attribute may not be readable

if hasattr(solid0, 'topology'):
    top = solid0.topology
    print(f"    topology attrs: {[a for a in dir(top) if not a.startswith('_')]}")

if hasattr(solid0, 'results'):
    res = solid0.results
    print(f"    results attrs: {[a for a in dir(res) if not a.startswith('_')]}")
    for cat_name in [a for a in dir(res) if not a.startswith('_')]:
        try:
            cat = getattr(res, cat_name)
            if hasattr(cat, 'props'):
                print(f"      results.{cat_name}.props = {cat.props}")
                for prop in cat.props[:5]:
                    try:
                        val = getattr(cat, prop)
                        s = str(val)[:200]
                        print(f"        {prop} = {s}")
                    except Exception: pass  # attribute may not be readable
            elif not callable(cat):
                print(f"      results.{cat_name} = {str(cat)[:150]}")
        except Exception: pass  # attribute may not be readable

# First plate element - deep dive
print("\n[6] First plate element (deep inspection):")
plate0 = next(iter(output.plate))
print(f"    Top-level attrs: {[a for a in dir(plate0) if not a.startswith('_')]}")

if hasattr(plate0, 'results'):
    res = plate0.results
    print(f"    results attrs: {[a for a in dir(res) if not a.startswith('_')]}")
    for cat_name in [a for a in dir(res) if not a.startswith('_')]:
        try:
            cat = getattr(res, cat_name)
            if hasattr(cat, 'props'):
                print(f"      results.{cat_name}.props = {cat.props}")
        except Exception: pass  # attribute may not be readable

# Count elements with non-zero collapse mechanism
print("\n[7] Collapse mechanism statistics (ALL solid elements):")
u_norms = []
n_solids = 0
for solid in output.solid:
    n_solids += 1
    if hasattr(solid, 'results') and hasattr(solid.results, 'collapse_mechanism'):
        cm = solid.results.collapse_mechanism
        if hasattr(cm, 'u_norm'):
            val = cm.u_norm
            if isinstance(val, (list, np.ndarray)):
                u_norms.extend([float(v) for v in val])
            elif isinstance(val, (int, float)):
                u_norms.append(float(val))
            else:
                s = str(val)
                nums = re.findall(r'[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?', s)
                if nums:
                    u_norms.extend([float(n) for n in nums])

if u_norms:
    u_arr = np.array(u_norms)
    print(f"    Total solid elements: {n_solids}")
    print(f"    u_norm values collected: {len(u_arr)}")
    print(f"    u_norm range: [{u_arr.min():.6f}, {u_arr.max():.6f}]")
    print(f"    u_norm mean: {u_arr.mean():.6f}")
    print(f"    u_norm std: {u_arr.std():.6f}")
    print(f"    u_norm > 0: {np.sum(u_arr > 0)} ({np.sum(u_arr > 0)/len(u_arr)*100:.1f}%)")

    # Threshold analysis
    for pct in [0.01, 0.05, 0.10, 0.25, 0.50]:
        thresh = pct * u_arr.max()
        n_above = np.sum(u_arr > thresh)
        print(f"    u_norm > {pct:.0%} of max ({thresh:.6f}): "
              f"{n_above} elements ({n_above/len(u_arr)*100:.1f}%)")
else:
    print(f"    No u_norm data found in {n_solids} solid elements")

# Check for dissipation data
print("\n[8] Looking for dissipation/energy data:")
solid_first = next(iter(output.solid))
if hasattr(solid_first, 'results'):
    res = solid_first.results
    for cat_name in dir(res):
        if any(kw in cat_name.lower() for kw in ['dissip', 'energy', 'work', 'plastic', 'strain']):
            print(f"    Found: results.{cat_name}")
            try:
                cat = getattr(res, cat_name)
                if hasattr(cat, 'props'):
                    print(f"      props = {cat.props}")
            except Exception: pass  # attribute may not be readable

# Check vertices/coordinates for volume computation
print("\n[9] Solid element topology for volume computation:")
solid_first = next(iter(output.solid))
if hasattr(solid_first, 'topology'):
    top = solid_first.topology
    for attr in ['X', 'Y', 'Z', 'nodes', 'mesh_id', 'volume']:
        val = getattr(top, attr, None)
        if val is not None:
            s = str(val)[:200]
            print(f"    topology.{attr} = {s}")

mod.delete()

print("\n" + "=" * 70)
print("TEST COMPLETE")
print("=" * 70)
