# -*- coding: utf-8 -*-
"""
Claude Proof-of-Concept: Autonomous OptumGX Control
====================================================
Proves Claude can: connect, build, run, retrieve results, interpret, modify.

Test: Vertical bearing capacity of 3D surface footing on Tresca clay.
Analytical: Nc ~ 5.14 (strip), but 3D effects increase this.
"""
from OptumGX import *
import numpy as np
import time
import json
import os

# =============================================================================
# CONFIGURATION
# =============================================================================
L = 10         # Soil domain half-width [m]
H = 8          # Soil depth [m]
Bx = 2         # Footing width x [m]
By = 2         # Footing width y [m]

su = 50.0      # Undrained shear strength [kPa]
gamma = 18.0   # Unit weight [kN/m3]

N_el = 5000
N_el_start = 2000

output_dir = 'results_claude_poc'
os.makedirs(output_dir, exist_ok=True)

print("=" * 60)
print("Claude POC: OptumGX Autonomous Control")
print("=" * 60)

# =============================================================================
# STEP 1: Connect
# =============================================================================
print("\n[1] Connecting to OptumGX...")
t0 = time.time()
gx = GX()
print("    Connected.")

# =============================================================================
# STEP 2: Build model (follows ex_skirted_found3d.py pattern exactly)
# =============================================================================
print("\n[2] Building 3D surface footing model...")
prj = gx.create_project("Claude_POC")

# Create model FIRST, then delete default
mod = prj.create_model(name="Footing_v1", model_type="three_dimensional")
prj.get_model("Model A").delete()

# Material: uniform Tresca clay
Soil = prj.Tresca(name="Soil", cu=su, gamma_dry=gamma,
                   color=rgb(195, 165, 120))
Foundation = prj.RigidPlate(name="Foundation", color=rgb(130, 160, 180))

# Geometry: soil domain (3D box, half-model using symmetry y=0)
mod.add_box([-L/2, 0, -H], [L/2, L/2, 0])

# Footing footprint on surface
mod.add_rectangle([-Bx/2, 0, 0], [Bx/2, By/2, 0])

# Assign soil to volume
sel = mod.select([0, 0, -H/2], types="volume")
mod.set_solid(sel, Soil)

# Assign footing plate on surface
sel = mod.select([0, By/4, 0], types="face")
mod.set_plate(sel, Foundation, strength_reduction_factor=1.0)

# Center vertex for load application
mod.add_vertex([0, 0, 0])

# Foundation plate BC on symmetry edge (y=0)
sel = mod.select([0, 0, 0], types="edge")
mod.set_plate_bc(sel, displacement_x="free", displacement_y="fixed",
                 displacement_z="free", displacement_rotation="fixed")

# Standard fixities (all outer boundaries)
mod.set_standard_fixities()
mod.zoom_all()

# Analysis: load multiplier (limit analysis)
mod.set_analysis_properties(
    analysis_type="load_multiplier",
    element_type="mixed",
    no_of_elements=N_el,
    mesh_adaptivity="yes",
    adaptivity_iterations=3,
    start_elements=N_el_start,
)

# Apply unit downward multiplier load at center
sel = mod.select([0, 0, 0], types="vertex")
mod.set_point_load(sel, -1, direction="z", option="multiplier")

print(f"    Model: {Bx}x{By}m footing, su={su} kPa, {N_el} elements")

# =============================================================================
# STEP 3: Run analysis
# =============================================================================
print("\n[3] Running load multiplier analysis...")
t1 = time.time()
prj.run_analysis()
dt = time.time() - t1
print(f"    Analysis time: {dt:.1f}s")

# =============================================================================
# STEP 4: Retrieve results
# =============================================================================
print("\n[4] Retrieving results...")
results = {}

# Load multiplier (primary result)
try:
    lm = mod.output.global_results.load_multiplier
    results['load_multiplier'] = float(lm)
    print(f"    Load multiplier = {lm}")
except Exception as e:
    print(f"    global_results error: {e}")
    try:
        lm = mod.output.critical_results.load_multiplier
        results['load_multiplier'] = float(lm)
        print(f"    Load multiplier (critical) = {lm}")
    except Exception as e2:
        print(f"    critical_results error: {e2}")
        lm = None

# Try to list all available output attributes
try:
    out = mod.output
    print(f"    Output type: {type(out)}")
    print(f"    Output dir: {[a for a in dir(out) if not a.startswith('_')]}")
except Exception as e:
    print(f"    Output inspection: {e}")

# Result points
try:
    rps = list(mod.output.resultpoint)
    print(f"    Result points: {len(rps)}")
    for i, rp in enumerate(rps):
        try:
            print(f"      RP[{i}] general: {[a for a in dir(rp.general) if not a.startswith('_')]}")
        except Exception:
            pass
        try:
            print(f"      RP[{i}] results: {[a for a in dir(rp.results) if not a.startswith('_')]}")
        except Exception:
            pass
except Exception as e:
    print(f"    Result points: {e}")

# Plates
try:
    plates = list(mod.output.plate)
    print(f"    Plates: {len(plates)}")
except Exception as e:
    print(f"    Plates: {e}")

# Solids
try:
    solids = list(mod.output.solid)
    print(f"    Solids: {len(solids)}")
except Exception as e:
    print(f"    Solids: {e}")

# =============================================================================
# STEP 5: Interpret
# =============================================================================
print("\n[5] Interpretation:")
if lm is not None:
    # For a square footing on Tresca: Nc ~ 5.14 (strip) * shape factor
    # Shape factor for square ~ 1.2, so Nc_square ~ 6.17
    # But load multiplier = Nc * su * A (footing area)
    A = Bx * By / 2  # half-model area
    Nc_fem = float(lm) / (su * A)
    results['Nc_fem'] = Nc_fem
    results['footing_area_half'] = A

    print(f"    V_ult (half model) = {lm:.2f} kN")
    print(f"    Nc_fem = V_ult / (su * A) = {Nc_fem:.3f}")
    print(f"    Expected Nc (square) ~ 6.0-6.2")

    error_est = abs(Nc_fem - 6.1) / 6.1 * 100
    print(f"    Approx error vs expected: {error_est:.1f}%")
else:
    print("    No load multiplier available.")

# =============================================================================
# STEP 6: Save results
# =============================================================================
results['run_time_s'] = dt
results['config'] = {'Bx': Bx, 'By': By, 'su': su, 'gamma': gamma,
                      'N_el': N_el, 'L': L, 'H': H}

out_path = os.path.join(output_dir, 'poc_results.json')
with open(out_path, 'w') as f:
    json.dump(results, f, indent=2, default=str)
print(f"\n[6] Results saved to {out_path}")

# =============================================================================
# STEP 7: Demonstrate self-modification (refine if needed)
# =============================================================================
if lm is not None:
    print("\n[7] Demonstrating adaptive modification...")
    N_el_v2 = N_el * 2

    mod2 = mod.clone("Footing_v2_refined")
    mod2.set_analysis_properties(
        analysis_type="load_multiplier",
        element_type="mixed",
        no_of_elements=N_el_v2,
        mesh_adaptivity="yes",
        adaptivity_iterations=4,
        start_elements=N_el,
    )

    print(f"    Re-running with {N_el_v2} elements...")
    t2 = time.time()
    prj.run_analysis()
    dt2 = time.time() - t2

    try:
        lm2 = mod2.output.global_results.load_multiplier
    except Exception:
        try:
            lm2 = mod2.output.critical_results.load_multiplier
        except Exception:
            lm2 = None

    if lm2 is not None:
        Nc2 = float(lm2) / (su * A)
        print(f"    V_ult_v2 = {lm2:.2f} kN (Nc = {Nc2:.3f})")
        print(f"    Convergence check: |Nc2 - Nc1| = {abs(Nc2 - Nc_fem):.4f}")
        results['v2_load_multiplier'] = float(lm2)
        results['v2_Nc'] = Nc2
        results['v2_time_s'] = dt2
    else:
        print("    Refined run: no result obtained")

    # Save updated
    with open(out_path, 'w') as f:
        json.dump(results, f, indent=2, default=str)
else:
    print("\n[7] Skipped (no initial result).")

# =============================================================================
# SUMMARY
# =============================================================================
total = time.time() - t0
print("\n" + "=" * 60)
print("PROOF-OF-CONCEPT COMPLETE")
print("=" * 60)
print(f"  Connected:          YES")
print(f"  Built model:        YES")
print(f"  Ran analysis:       {'YES' if lm is not None else 'FAILED'}")
print(f"  Retrieved results:  {'YES' if lm is not None else 'FAILED'}")
print(f"  Interpreted:        {'YES' if lm is not None else 'N/A'}")
print(f"  Self-modified:      {'YES' if lm is not None else 'N/A'}")
print(f"  Total time:         {total:.1f}s")
print("=" * 60)
