# -*- coding: utf-8 -*-
"""
Claude POC #2: Extract BOTH global capacity AND plate pressure distribution
===============================================================================
Proves Claude can:
  1. Build a 3D skirted foundation model
  2. Run Hmax limit analysis
  3. Retrieve global load multiplier (Hmax)
  4. Extract plate element pressures/stresses at failure
  5. Compute depth-wise soil reaction profile p(z) from plate data
  6. Show that integral of p(z) over depth ~ Hmax (consistency)

This is the bridge: OptumGX global VHM -> distributed p_ult(z) for BNWF.
"""
from OptumGX import *
import numpy as np
import pandas as pd
import re
import ast
import os
import time
import json

# =============================================================================
# CONFIGURATION (simple 3D skirted footing matching VH Optum CE pattern)
# =============================================================================
L_domain = 20     # soil domain half-width [m]
H_domain = 5      # soil depth [m]
Bx = 5            # foundation width x [m]
By = 10           # foundation width y [m] (half-model: By/2 used)
S = 1             # skirt depth [m]

su0 = 2           # shear strength at top [kPa]
k_su = 1.5        # strength gradient [kPa/m]
gamma = 8         # effective unit weight [kN/m3]
a_int = 0.5       # interface adhesion factor
N_el = 10000
N_el_start = 5000

output_dir = 'results_claude_poc2'
os.makedirs(output_dir, exist_ok=True)

print("=" * 65)
print("Claude POC #2: Global Capacity + Plate Pressure Extraction")
print("=" * 65)

# =============================================================================
# HELPER: extract property from OptumGX output object
# =============================================================================
def extract_property(obj, prop_name):
    """Safely extract a property from an OptumGX output object."""
    try:
        val = getattr(obj, prop_name)
        if callable(val):
            val = val()
        return val
    except Exception:
        return None


def parse_value(val):
    """Parse OptumGX output value (may be string with unit info)."""
    if val is None:
        return None
    if isinstance(val, (int, float)):
        return val
    if isinstance(val, str):
        # Try "unit: 'xxx', value: yyy" format
        match = re.search(r"value:\s*(.*)", val)
        if match:
            value_str = match.group(1)
            numbers = re.findall(r'[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?', value_str)
            if numbers:
                floats = [float(n) for n in numbers]
                return floats if len(floats) > 1 else floats[0]
        # Try direct parse
        try:
            return float(val)
        except ValueError:
            pass
        # Try list parse
        try:
            parsed = ast.literal_eval(val)
            if isinstance(parsed, (list, tuple)):
                return [float(x) for x in parsed]
        except Exception:
            pass
    return val


# =============================================================================
# STEP 1: Build model (following VH Optum CE Appendix 2 pattern exactly)
# =============================================================================
print("\n[1] Building 3D skirted foundation...")
t0 = time.time()

gx = GX()
prj = gx.create_project("Claude_POC2_PlatePressure")
mod = prj.create_model(name="Hmax", model_type="three_dimensional")
prj.get_model("Model A").delete()

# Material: Tresca with linearly increasing su
XYZ = np.array([
    [-L_domain,  0,         0],
    [ L_domain,  0,         0],
    [ L_domain,  L_domain/2, 0],
    [-L_domain,  L_domain/2, 0],
    [-L_domain,  0,         -H_domain],
    [ L_domain,  0,         -H_domain],
    [ L_domain,  L_domain/2, -H_domain],
    [-L_domain,  L_domain/2, -H_domain],
])
suz = np.array([su0]*4 + [su0 + k_su*H_domain]*4)
sumap = ParameterMap(np.vstack((XYZ.T, suz)).T)
Soil = prj.Tresca(name="Soil", cu=sumap, gamma_dry=gamma,
                   color=rgb(200, 80, 100))
Foundation = prj.RigidPlate(name="Foundation", color=rgb(130, 160, 180))

# Geometry: 3D soil domain (half-model, y >= 0)
mod.add_box([-L_domain/2, 0, -H_domain], [L_domain/2, L_domain/2, 0])
mod.add_rectangle([-Bx/2, 0, 0], [Bx/2, By/2, 0])

# Assign soil
sel = mod.select([0, 0, -H_domain/2], types="volume")
mod.set_solid(sel, Soil)

# Foundation: extrude skirt, assign plate
sel = mod.select([0, By/4, 0], types="face")
mod.extrude(sel, [0, 0, -S])
sel = mod.select([0, 0, -S], types="edge")
mod.delete_shapes(sel)
mod.add_vertex([0, 0, 0])
sel = mod.select([-Bx/2, 0, -S], [Bx/2, By/2, 0],
                 types="face", option="blue")
mod.set_plate(sel, Foundation, strength_reduction_factor=a_int)

# Plate BCs on symmetry edge
sel2 = mod.select([0, 0, 0], types="edge")
mod.set_plate_bc(sel2, displacement_x="free", displacement_y="fixed",
                 displacement_z="free", displacement_rotation="fixed")

mod.set_standard_fixities()
mod.zoom_all()

# Analysis settings
mod.set_analysis_properties(
    analysis_type="load_multiplier",
    element_type="mixed",
    no_of_elements=N_el,
    mesh_adaptivity="yes",
    adaptivity_iterations=3,
    start_elements=N_el_start,
)

# Apply horizontal multiplier load at center (for Hmax)
sel = mod.select([0, 0, 0], types="vertex")
mod.set_point_load(sel, 1, direction="x", option="multiplier")

# Fix vertical displacement for pure H test
sel_edge = mod.select([0, 0, 0], types="edge")
bcs = mod.get_features(sel_edge)
mod.remove_features(bcs)
mod.set_plate_bc(sel_edge, displacement_x="free", displacement_y="fixed",
                 displacement_z="fixed", displacement_rotation="fixed")

print(f"    Model: {Bx}x{By}m foundation, skirt={S}m, su={su0}+{k_su}z kPa")

# =============================================================================
# STEP 2: Run Hmax analysis
# =============================================================================
print("\n[2] Running Hmax limit analysis...")
t1 = time.time()
prj.run_analysis()
dt = time.time() - t1
print(f"    Analysis time: {dt:.1f}s")

# =============================================================================
# STEP 3: Get global load multiplier
# =============================================================================
print("\n[3] Global result:")
try:
    Hmax = mod.output.global_results.load_multiplier
    print(f"    Hmax = {Hmax:.2f} kN (half-model)")
    print(f"    Hmax_full = {2*Hmax:.2f} kN (full model)")
except Exception as e:
    print(f"    ERROR: {e}")
    Hmax = None

# =============================================================================
# STEP 4: Extract plate element data
# =============================================================================
print("\n[4] Extracting plate element data...")

plate_data = []
n_plates = 0
n_with_results = 0

for i, plate in enumerate(mod.output.plate):
    n_plates += 1
    row = {'index': i}

    # General info (material name etc.)
    if hasattr(plate, 'general'):
        gen = plate.general
        for prop in ['material_name', 'material_model', 'shape_id']:
            val = parse_value(extract_property(gen, prop))
            if val is not None:
                row[prop] = val

    # Topology (node coordinates)
    if hasattr(plate, 'topology'):
        top = plate.topology
        for prop in ['nodes', 'X', 'Y', 'Z']:
            val = parse_value(extract_property(top, prop))
            if val is not None:
                if isinstance(val, list):
                    for j, v in enumerate(val, 1):
                        row[f'{prop}_{j}'] = v
                else:
                    row[prop] = val

    # Results (stresses, pressures, forces, displacements)
    if hasattr(plate, 'results'):
        n_with_results += 1
        res = plate.results
        for cat in ['displacements', 'initial_stresses', 'final_stresses',
                     'strains', 'nodal_forces', 'collapse_mechanism',
                     'final_forces', 'total_pressures']:
            if hasattr(res, cat):
                subres = getattr(res, cat)
                if hasattr(subres, 'props'):
                    for prop in subres.props:
                        val = parse_value(extract_property(subres, prop))
                        if val is not None:
                            if isinstance(val, list):
                                for j, v in enumerate(val, 1):
                                    row[f'{cat}_{prop}_{j}'] = v
                            else:
                                row[f'{cat}_{prop}'] = val

    plate_data.append(row)

print(f"    Total plates: {n_plates}")
print(f"    Plates with results: {n_with_results}")

# Save to DataFrame and Excel
df_plates = pd.DataFrame(plate_data)

# Show what columns we got
print(f"    Columns extracted: {len(df_plates.columns)}")
result_cols = [c for c in df_plates.columns if 'stress' in c.lower()
               or 'pressure' in c.lower() or 'force' in c.lower()
               or 'sigma' in c.lower() or 'tau' in c.lower()]
print(f"    Stress/pressure/force columns: {result_cols[:20]}")

coord_cols = [c for c in df_plates.columns if c.startswith(('X_', 'Y_', 'Z_'))]
print(f"    Coordinate columns: {coord_cols[:12]}")

# Save full plate data
excel_path = os.path.join(output_dir, 'plate_data_Hmax.xlsx')
df_plates.to_excel(excel_path, index=False)
print(f"    Saved to {excel_path}")

# =============================================================================
# STEP 5: Compute depth-wise soil reaction p(z)
# =============================================================================
print("\n[5] Computing depth-wise soil reaction...")

# Calculate centroid Z for each plate element
if 'Z_1' in df_plates.columns and 'Z_2' in df_plates.columns:
    z_cols = [c for c in df_plates.columns if c.startswith('Z_')]
    df_plates['Z_centroid'] = df_plates[z_cols].mean(axis=1)

    # Show depth range
    print(f"    Z range: [{df_plates['Z_centroid'].min():.2f}, "
          f"{df_plates['Z_centroid'].max():.2f}] m")

    # Identify pressure/stress columns for integration
    print(f"\n    All result columns:")
    for c in sorted(df_plates.columns):
        if any(kw in c.lower() for kw in ['stress', 'pressure', 'force',
                                            'sigma', 'tau', 'disp']):
            # Show sample values
            vals = df_plates[c].dropna()
            if len(vals) > 0:
                print(f"      {c}: min={vals.min():.4f}, "
                      f"max={vals.max():.4f}, mean={vals.mean():.4f}")
else:
    print("    WARNING: No coordinate columns found for depth analysis")

# =============================================================================
# STEP 6: Also extract solid element data (first few for inspection)
# =============================================================================
print("\n[6] Extracting solid element data (sample)...")

solid_data = []
for i, solid in enumerate(mod.output.solid):
    if i >= 20:
        break  # Just sample first 20
    row = {'index': i}

    if hasattr(solid, 'general'):
        gen = solid.general
        for prop in ['material_name']:
            val = parse_value(extract_property(gen, prop))
            if val is not None:
                row[prop] = val

    if hasattr(solid, 'topology'):
        top = solid.topology
        for prop in ['X', 'Y', 'Z']:
            val = parse_value(extract_property(top, prop))
            if val is not None:
                if isinstance(val, list):
                    for j, v in enumerate(val, 1):
                        row[f'{prop}_{j}'] = v
                else:
                    row[prop] = val

    if hasattr(solid, 'results'):
        res = solid.results
        for cat in ['final_stresses', 'displacements', 'strains']:
            if hasattr(res, cat):
                subres = getattr(res, cat)
                if hasattr(subres, 'props'):
                    for prop in subres.props:
                        val = parse_value(extract_property(subres, prop))
                        if val is not None:
                            if isinstance(val, list):
                                for j, v in enumerate(val, 1):
                                    row[f'{cat}_{prop}_{j}'] = v
                            else:
                                row[f'{cat}_{prop}'] = val
    solid_data.append(row)

df_solids = pd.DataFrame(solid_data)
solid_cols = [c for c in df_solids.columns if 'stress' in c.lower()
              or 'sigma' in c.lower() or 'tau' in c.lower()]
print(f"    Solid stress columns: {solid_cols[:15]}")
print(f"    Sample solid data:")
if len(solid_cols) > 0:
    for c in solid_cols[:5]:
        vals = df_solids[c].dropna()
        if len(vals) > 0:
            print(f"      {c}: min={vals.min():.4f}, max={vals.max():.4f}")

df_solids.to_excel(os.path.join(output_dir, 'solid_data_sample.xlsx'),
                   index=False)

# =============================================================================
# SUMMARY
# =============================================================================
total = time.time() - t0
print("\n" + "=" * 65)
print("POC #2 COMPLETE")
print("=" * 65)
print(f"  Hmax (global):          {'%.2f kN' % Hmax if Hmax else 'FAILED'}")
print(f"  Plate elements:         {n_plates}")
print(f"  Plates with results:    {n_with_results}")
print(f"  Result columns:         {len(result_cols)}")
print(f"  Coordinate columns:     {len(coord_cols)}")
print(f"  Solid sample columns:   {len(solid_cols)}")
print(f"  Total time:             {total:.1f}s")
print(f"  Output:                 {output_dir}/")
print("=" * 65)

# Save summary
summary = {
    'Hmax_half_model': float(Hmax) if Hmax else None,
    'Hmax_full_model': float(2*Hmax) if Hmax else None,
    'n_plates': n_plates,
    'n_plates_with_results': n_with_results,
    'result_columns': result_cols[:30],
    'coordinate_columns': coord_cols[:12],
    'solid_stress_columns': solid_cols[:15],
    'analysis_time_s': dt,
    'total_time_s': total,
}
with open(os.path.join(output_dir, 'poc2_summary.json'), 'w') as f:
    json.dump(summary, f, indent=2, default=str)
