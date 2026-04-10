# -*- coding: utf-8 -*-
"""
Date: 2026-01-01
Author : Kyeong Sun Kim (kyeongsunkim@snu.ac.kr)

=============================================================================
"""
from OptumGX import *
import numpy as np
import pandas as pd
import json
import os
import matplotlib.pyplot as plt
import ast
import re
import math
from datetime import datetime
import time

scour = 0.6

# Directory paths
input_dir = 'results_v10_final'
output_dir = 'results_fixed_v10_final'
# Create directories if they don't exist
os.makedirs(input_dir, exist_ok=True)
os.makedirs(output_dir, exist_ok=True)
timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
start_time = time.time()

## ============define functions================ ##
def has_valid_output(stage):
    """
    Check if a stage has valid output data.
    Returns True if output exists and has data, False otherwise.
    """
    try:
        if not hasattr(stage, 'output'):
            return False
        # Try to access critical_results to verify output is accessible
        _ = stage.output.critical_results
        return True
    except (AttributeError, IndexError):
        return False

def fix_cell(cell):
    if isinstance(cell, str) and ('value:' in cell or 'unit:' in cell):
        # Extract all numeric values from the cell
        nums = re.findall(r'[-+]?(?:\d*\.\d+|\d+)(?:[eE][-+]?\d+)?', cell)
        floats = []
        for n in nums:
            try:
                floats.append(float(n))
            except ValueError:
                pass
        if not floats:
            return cell
        if len(floats) == 1:
            return floats[0]
        return floats  # Return list if multiple values
    return cell

def expand_list_columns(df):
    columns_to_expand = []
    for col in df.columns:
        if col == '_hint':
            continue
        # Check if all non-NA values are lists
        non_na_values = df[col].dropna()
        if non_na_values.empty:
            continue
        is_list_col = all(isinstance(x, list) for x in non_na_values)
        if not is_list_col:
            continue
        # Check if all elements in all lists are numeric and collect lengths
        all_numeric = True
        lengths = set()
        for lst in non_na_values:
            if not isinstance(lst, list) or not all(isinstance(item, (int, float)) for item in lst):
                all_numeric = False
                break
            lengths.add(len(lst))
        if not all_numeric:
            continue
        if not lengths:
            continue
        max_len = max(lengths)
        if max_len <= 1:
            continue  # Skip if max length <= 1
        columns_to_expand.append(col)

    for col in columns_to_expand:
        non_na_values = df[col].dropna()
        lengths = {len(lst) for lst in non_na_values}
        max_len = max(lengths)

        # Pad shorter lists with np.nan
        def pad_list(l, target_len):
            if isinstance(l, list):
                return l + [np.nan] * (target_len - len(l))
            return [np.nan] * target_len

        padded = df[col].apply(lambda x: pad_list(x, max_len))
        # Create expanded DataFrame
        expanded_data = {}
        for i in range(max_len):
            new_col = f"{col}_{i+1}"
            expanded_data[new_col] = padded.apply(lambda x: x[i] if isinstance(x, list) else np.nan)
        expanded = pd.DataFrame(expanded_data)
        # Concat to original df after dropping the column
        df = pd.concat([df.drop(col, axis=1), expanded], axis=1)
    return df

def safe_eval(x):
    if pd.isna(x):
        return x
    try:
        return ast.literal_eval(x)
    except (ValueError, SyntaxError):
        return x

def extract_property(obj, prop_name):
    if not hasattr(obj, prop_name):
        return None
    attr = getattr(obj, prop_name)
    # Try to get labels
    labels = None
    if hasattr(attr, 'labels'):
        labels = attr.labels
    # Try to get values
    if hasattr(attr, 'value'):
        values = attr.value
    elif hasattr(attr, 'values'):
        values = attr.values
    else:
        values = attr
    # If string, return as is
    if isinstance(values, str):
        return values
    # If int or float, return as is
    if isinstance(values, (int, float)):
        return values
    # If list-like, process
    if isinstance(values, (list, np.ndarray)):
        values = list(values)
        if labels and isinstance(labels, list) and len(labels) == len(values):
            return {'values': values, 'labels': labels}
        else:
            return values
    # If still an object, try to infer labels from str representation and extract attributes
    try:
        str_rep = str(attr)
        if str_rep.startswith('[') and str_rep.endswith(']'):
            labels = ast.literal_eval(str_rep)
            if isinstance(labels, list) and all(isinstance(l, str) for l in labels):
                values = []
                for label in labels:
                    if hasattr(attr, label):
                        values.append(getattr(attr, label))
                    else:
                        values.append(None)
                return {'values': values, 'labels': labels}
    except Exception:
        pass  # OptumGX attribute access can fail in many ways
    # Enhanced fallback: Parse if in "unit: 'xx', value: yy" format
    str_rep = str(attr)
    match = re.search(r"unit: '(.*?)', value: (.*)", str_rep)
    if match:
        unit = match.group(1)
        value_str = match.group(2)
        # Parse numbers from value_str
        values = re.findall(r'[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?', value_str)
        if values:
            try:
                value = [float(v) for v in values]
                if len(value) == 1:
                    value = value[0]
                return value
            except (ValueError, TypeError):
                pass  # value string not numeric
        return str_rep
    else:
        return str_rep

def collect_critical_results(output):
    crit = output.critical_results
    data = {}
    for field in dir(crit):
        if not field.startswith("__") and not callable(getattr(crit, field)):
            val = getattr(crit, field)
            if isinstance(val, complex):
                wrapped_val = {'real': val.real, 'imag': val.imag}
            elif isinstance(val, (int, float)):
                wrapped_val = val
            elif isinstance(val, (list, np.ndarray)):
                wrapped_val = val.tolist() if hasattr(val, 'tolist') else list(val)
            else:
                continue  # Skip unknown types
            data[field] = wrapped_val
    return data

def collect_resultpoints(output):
    df = pd.DataFrame()
    for i, rp in enumerate(output.resultpoint):
        row = {'index': i}
        if hasattr(rp, 'element_index'):
            row['element_index'] = rp.element_index
        if hasattr(rp, 'general'):
            gen = rp.general
            for prop in ['material_name', 'material_model', 'color', 'shape_id']:
                val = extract_property(gen, prop)
                if isinstance(val, str):
                    match = re.search(r"unit: '(.*?)', value: (.*)", val)
                    if match:
                        value_str = match.group(2)
                        values = re.findall(r'[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?', value_str)
                        if values:
                            try:
                                floats = [float(v) for v in values]
                                if len(floats) == 1:
                                    row[prop] = floats[0]
                                else:
                                    row.pop(prop, None)
                                    for j, f in enumerate(floats, 1):
                                        row[f'{prop}_{j}'] = f
                            except (ValueError, TypeError):
                                row[prop] = val
                        else:
                            row[prop] = val
                    else:
                        row[prop] = val
                else:
                    row[prop] = val
        if hasattr(rp, 'topology'):
            top = rp.topology
            row['mesh_id'] = extract_property(top, 'mesh_id')
            for prop_coord in ['nodes', 'X', 'Y', 'Z']:
                val = extract_property(top, prop_coord)
                if isinstance(val, str):
                    try:
                        list_val = ast.literal_eval(val)
                        if isinstance(list_val, list):
                            if len(list_val) == 1 and isinstance(list_val[0], (int, float)):
                                val = list_val[0]
                            elif all(isinstance(i, (int, float)) for i in list_val):
                                val = list_val
                    except (ValueError, SyntaxError):
                        pass
                if isinstance(val, str):
                    match = re.search(r"unit: '(.*?)', value: (.*)", val)
                    if match:
                        value_str = match.group(2)
                        values = re.findall(r'[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?', value_str)
                        if values:
                            try:
                                floats = [float(v) for v in values]
                                if len(floats) == 1:
                                    val = floats[0]
                                else:
                                    val = floats
                            except (ValueError, TypeError):
                                pass
                if isinstance(val, list):
                    for j, v in enumerate(val, 1):
                        row[f'{prop_coord}_{j}'] = v
                else:
                    row[prop_coord] = val
        if hasattr(rp, 'results'):
            res = rp.results
            for cat in ['displacements', 'initial_stresses', 'final_stresses', 'strains',
                        'nodal_forces', 'collapse_mechanism', 'final_forces', 'total_pressures']:
                if hasattr(res, cat):
                    subres = getattr(res, cat)
                    for prop in subres.props:
                        val = extract_property(subres, prop)
                        if isinstance(val, str):
                            match = re.search(r"unit: '(.*?)', value: (.*)", val)
                            if match:
                                value_str = match.group(2)
                                values = re.findall(r'[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?', value_str)
                                if values:
                                    try:
                                        floats = [float(v) for v in values]
                                        if len(floats) == 1:
                                            val = floats[0]
                                        else:
                                            val = floats
                                    except (ValueError, TypeError):
                                        pass
                        if isinstance(val, dict) and 'values' in val and 'labels' in val:
                            for label, v in zip(val['labels'], val['values']):
                                row[f'{cat}_{prop}_{label}'] = v
                        elif isinstance(val, list):
                            if all(isinstance(x, str) for x in val):
                                continue  # Skip if list of strings (labels)
                            for j, v in enumerate(val, 1):
                                row[f'{cat}_{prop}_{j}'] = v
                        else:
                            row[f'{cat}_{prop}'] = val
        df = pd.concat([df, pd.DataFrame([row])], ignore_index=True)
    return df

def collect_plates(output):
    df = pd.DataFrame()
    for i, plate in enumerate(output.plate):
        row = {'index': i}
        if hasattr(plate, 'general'):
            gen = plate.general
            for prop in ['material_name', 'material_model', 'color', 'shape_id']:
                val = extract_property(gen, prop)
                if isinstance(val, str):
                    match = re.search(r"unit: '(.*?)', value: (.*)", val)
                    if match:
                        value_str = match.group(2)
                        values = re.findall(r'[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?', value_str)
                        if values:
                            try:
                                floats = [float(v) for v in values]
                                if len(floats) == 1:
                                    row[prop] = floats[0]
                                else:
                                    row.pop(prop, None)
                                    for j, f in enumerate(floats, 1):
                                        row[f'{prop}_{j}'] = f
                            except (ValueError, TypeError):
                                row[prop] = val
                        else:
                            row[prop] = val
                    else:
                        row[prop] = val
                else:
                    row[prop] = val
        if hasattr(plate, 'topology'):
            top = plate.topology
            row['mesh_id'] = extract_property(top, 'mesh_id')
            for prop_coord in ['nodes', 'X', 'Y', 'Z']:
                val = extract_property(top, prop_coord)
                if isinstance(val, str):
                    try:
                        list_val = ast.literal_eval(val)
                        if isinstance(list_val, list):
                            if len(list_val) == 1 and isinstance(list_val[0], (int, float)):
                                val = list_val[0]
                            elif all(isinstance(i, (int, float)) for i in list_val):
                                val = list_val
                    except (ValueError, SyntaxError):
                        pass
                if isinstance(val, str):
                    match = re.search(r"unit: '(.*?)', value: (.*)", val)
                    if match:
                        value_str = match.group(2)
                        values = re.findall(r'[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?', value_str)
                        if values:
                            try:
                                floats = [float(v) for v in values]
                                if len(floats) == 1:
                                    val = floats[0]
                                else:
                                    val = floats
                            except (ValueError, TypeError):
                                pass
                if isinstance(val, list):
                    for j, v in enumerate(val, 1):
                        row[f'{prop_coord}_{j}'] = v
                else:
                    row[prop_coord] = val
        if hasattr(plate, 'results'):
            res = plate.results
            for cat in ['displacements', 'initial_stresses', 'final_stresses', 'strains',
                        'nodal_forces', 'collapse_mechanism', 'final_forces', 'total_pressures']:
                if hasattr(res, cat):
                    subres = getattr(res, cat)
                    for prop in subres.props:
                        val = extract_property(subres, prop)
                        if isinstance(val, str):
                            match = re.search(r"unit: '(.*?)', value: (.*)", val)
                            if match:
                                value_str = match.group(2)
                                values = re.findall(r'[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?', value_str)
                                if values:
                                    try:
                                        floats = [float(v) for v in values]
                                        if len(floats) == 1:
                                            val = floats[0]
                                        else:
                                            val = floats
                                    except (ValueError, TypeError):
                                        pass
                        if isinstance(val, dict) and 'values' in val and 'labels' in val:
                            for label, v in zip(val['labels'], val['values']):
                                row[f'{cat}_{prop}_{label}'] = v
                        elif isinstance(val, list):
                            if all(isinstance(x, str) for x in val):
                                continue  # Skip if list of strings (labels)
                            for j, v in enumerate(val, 1):
                                row[f'{cat}_{prop}_{j}'] = v
                        else:
                            row[f'{cat}_{prop}'] = val
        df = pd.concat([df, pd.DataFrame([row])], ignore_index=True)
    return df

def collect_solids(output):
    stress_labels = ['sigma_x', 'sigma_y', 'sigma_z', 'tau_xy', 'sigma_1', 'sigma_2',
                     'sigma_3', 't', 's', 'q', 'p', 'theta']
    strain_labels = ['epsilon_x', 'epsilon_y', 'epsilon_z', 'gamma_xy', 'epsilon_1',
                     'epsilon_2', 'epsilon_3', 'epsilon_v', 'epsilon_q']
    df = pd.DataFrame()
    for i, solid in enumerate(output.solid):
        row = {'index': i}
        if hasattr(solid, 'general'):
            gen = solid.general
            for prop in ['material_name', 'material_model', 'color', 'shape_id']:
                val = extract_property(gen, prop)
                if isinstance(val, str):
                    match = re.search(r"unit: '(.*?)', value: (.*)", val)
                    if match:
                        value_str = match.group(2)
                        values = re.findall(r'[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?', value_str)
                        if values:
                            try:
                                floats = [float(v) for v in values]
                                if len(floats) == 1:
                                    row[prop] = floats[0]
                                else:
                                    row.pop(prop, None)
                                    for j, f in enumerate(floats, 1):
                                        row[f'{prop}_{j}'] = f
                            except (ValueError, TypeError):
                                row[prop] = val
                        else:
                            row[prop] = val
                    else:
                        row[prop] = val
                else:
                    row[prop] = val
        if hasattr(solid, 'topology'):
            top = solid.topology
            row['mesh_id'] = extract_property(top, 'mesh_id')
            for prop_coord in ['nodes', 'X', 'Y', 'Z']:
                val = extract_property(top, prop_coord)
                if isinstance(val, str):
                    try:
                        list_val = ast.literal_eval(val)
                        if isinstance(list_val, list):
                            if len(list_val) == 1 and isinstance(list_val[0], (int, float)):
                                val = list_val[0]
                            elif all(isinstance(i, (int, float)) for i in list_val):
                                val = list_val
                    except (ValueError, SyntaxError):
                        pass
                if isinstance(val, str):
                    match = re.search(r"unit: '(.*?)', value: (.*)", val)
                    if match:
                        value_str = match.group(2)
                        values = re.findall(r'[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?', value_str)
                        if values:
                            try:
                                floats = [float(v) for v in values]
                                if len(floats) == 1:
                                    val = floats[0]
                                else:
                                    val = floats
                            except (ValueError, TypeError):
                                pass
                if isinstance(val, list):
                    for j, v in enumerate(val, 1):
                        row[f'{prop_coord}_{j}'] = v
                else:
                    row[prop_coord] = val
        if hasattr(solid, 'results'):
            res = solid.results
            for cat in ['collapse_mechanism', 'final_stresses', 'strains', 'plasticity', 'nodal_forces']:
                if hasattr(res, cat):
                    subres = getattr(res, cat)
                    for prop in subres.props:
                        val = extract_property(subres, prop)
                        if isinstance(val, str):
                            match = re.search(r"unit: '(.*?)', value: (.*)", val)
                            if match:
                                value_str = match.group(2)
                                values = re.findall(r'[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?', value_str)
                                if values:
                                    try:
                                        floats = [float(v) for v in values]
                                        if len(floats) == 1:
                                            val = floats[0]
                                        else:
                                            val = floats
                                    except (ValueError, TypeError):
                                        pass
                        if isinstance(val, dict) and 'values' in val and 'labels' in val:
                            for label, v in zip(val['labels'], val['values']):
                                row[f'{cat}_{prop}_{label}'] = v
                        elif isinstance(val, list):
                            if all(isinstance(x, str) for x in val):
                                continue  # Skip if list of strings (labels)
                            # Special handling for stresses and strains
                            handled = False
                            if cat == 'final_stresses' and prop == 'total_stresses' and len(val) == 12:
                                for l, v in zip(stress_labels, val):
                                    row[f'{cat}_{prop}_{l}'] = v
                                handled = True
                            elif cat == 'strains' and prop in ['total_strains', 'elastic_strains', 'plastic_strains'] and len(val) == 9:
                                for l, v in zip(strain_labels, val):
                                    row[f'{cat}_{prop}_{l}'] = v
                                handled = True
                            if not handled:
                                for j, v in enumerate(val, 1):
                                    row[f'{cat}_{prop}_{j}'] = v
                        else:
                            row[f'{cat}_{prop}'] = val
        df = pd.concat([df, pd.DataFrame([row])], ignore_index=True)
    return df

def save_collections_to_excel(resultpoints_coll, plates_coll, file_prefix):
    """Helper function to save resultpoints and plates collections to Excel files."""
    excel_files_local = [
        os.path.join(input_dir, f'resultpoints_{file_prefix}.xlsx'),
        os.path.join(input_dir, f'plates_{file_prefix}.xlsx')]

    # Save resultpoints
    if resultpoints_coll:
        try:
            with pd.ExcelWriter(excel_files_local[0], engine='openpyxl') as writer:
                for sheet_name, df in resultpoints_coll.items():
                    df.to_excel(writer, sheet_name=sheet_name, index=False)
            print(f"[SUCCESS] Result points saved to {excel_files_local[0]}")
        except Exception as e:
            print(f"[ERROR] Failed to save result points: {e}")
    else:
        print(f"[WARNING] No result points to save for {file_prefix}.")

    # Save plates
    if plates_coll:
        try:
            with pd.ExcelWriter(excel_files_local[1], engine='openpyxl') as writer:
                for sheet_name, df in plates_coll.items():
                    df.to_excel(writer, sheet_name=sheet_name, index=False)
            print(f"[SUCCESS] Plates data saved to {excel_files_local[1]}")
        except Exception as e:
            print(f"[ERROR] Failed to save plates data: {e}")
    else:
        print(f"[WARNING] No plates data to save for {file_prefix}.")

## =========================================== ##
"""Initialization"""
# Geometry parameters

D = 8    # Diameter of circular foundation
R = D / 2  # Radius of foundation
S = float('nan')    # Depth of skirts

L = 20*R   # Length of soil domain
H = 15*R    # Height of soil domain

prefixes = ['V_scour'+str(scour)+'m',
            'H_scour'+str(scour)+'m',
            'M_scour'+str(scour)+'m']

excel_files_fix = ['resultpoints_'+prefixes[0]+'.xlsx', 'plates_'+prefixes[0]+'.xlsx',
                   'resultpoints_'+prefixes[1]+'.xlsx', 'plates_'+prefixes[1]+'.xlsx',
                   'resultpoints_'+prefixes[2]+'.xlsx', 'plates_'+prefixes[2]+'.xlsx']

N_SIDES = 24  # Number of sides for circular approximation (full circle)
N_el_final = 30000
N_el_start = 10000
u_target = 80 # 0.01D
N_steps = 8
N_adap = 4
fan_angle_= 30

# Material parameters
su0 = 15      # Shear strength at top
k = 20      # Increase in shear strength with depth
gamma = 10    # Soil unit weight (effective)
a = 0.67      # Soil-foundation interface adhesion factor (su_interface = a*su_soil)
tc = False    # Soil-foundation interface tension cut-off to resist tension at the lid and interface (suction)

# Loads
N_PTS = 8   # Number of points in V-H diagram  16
t = np.linspace(0, 180, N_PTS)  # V = -sin(t), H = cos(t)

# GX client
gx = GX()

# Create new project
prj = gx.create_project("VH Diagram - Circular Foundation")

# Delete default model
prj.get_model("Model A").delete()

# Define materials
# Soil - using parameter map for varying shear strength with depth
XYZ = np.array([
    [-L,  0,    0],
    [ L,  0,    0],
    [ L,  L/2,  0],
    [-L,  L/2,  0],
    [-L,  0,   -H],
    [ L,  0,   -H],
    [ L,  L/2, -H],
    [-L,  L/2, -H]
])
suz = np.array([su0] * 4 + [su0 + k * H] * 4)
sumap = ParameterMap(np.vstack((XYZ.T, suz)).T)  # Map of (X,Y,Z,Su)
Soil = prj.Tresca(name="Soil", cu=sumap, gamma_dry=10, color=rgb(195, 165, 120))
Foundation = prj.RigidPlate(name="Foundation", color=rgb(130, 160, 180))

# =============================================================================
# Create 2D axisymmetric model first, then revolve to 3D
# =============================================================================
mod2d = prj.create_model(name="AX_Vmax", model_type="plane_strain")

# Add 2D soil domain (X = radial, Y = vertical)
mod2d.add_rectangle([0, -H], [L/2, 0])

# Add foundation lid (horizontal line at z=0 from x=0 to x=R)
mod2d.add_line([0, 0], [R, 0])

# Add skirt wall (vertical line at x=R from z=0 to z=-S)
mod2d.add_line([R, 0], [R, -S])

# Assign soil material
sel_soil = mod2d.select([L/4, -H/2], types="face")
mod2d.set_solid(sel_soil, Soil)

# Assign plate to foundation lid
sel_lid = mod2d.select([R/2, 0], types="edge")
mod2d.set_plate(sel_lid, Foundation, strength_reduction_factor=a)

# Assign plate to skirt wall
sel_skirt = mod2d.select([R, -S/2], types="edge")
mod2d.set_plate(sel_skirt, Foundation, strength_reduction_factor=a)

# =============================================================================
# Revolve 2D to 3D (half model: 180 degrees)
# =============================================================================
mod = mod2d.revolve_2d_to_3d(angle_deg=180, N=N_SIDES // 2, name="Vmax")

# Clean up radial artifact edges created by revolution

# Delete vertical axis lines
try:
    sel = mod.select([0, 0, -H/2], types="edge")
    if sel:
        mod.delete_shapes(sel)
except Exception:  # edge cleanup after revolution
    pass
# Add center vertex for load application
mod.add_vertex([0, 0, 0])
sel_ = mod.select([0, 0, 0], types="vertex")
mod.set_resultpoint(sel_)

# Define foundation BCs (symmetry along y=0)
sel_sym = mod.select([0, 0, 0], types="edge")
mod.set_plate_bc(sel_sym, displacement_x="fixed", displacement_y="fixed",
                 displacement_z="free", displacement_rotation="fixed")

sel_sym = mod.select([R, 0, -S/2], types="edge")
mod.set_plate_bc(sel_sym, displacement_x="free", displacement_y="fixed",
                 displacement_z="free", displacement_rotation="fixed")

sel_sym = mod.select([-R, 0, -S/2], types="edge")
mod.set_plate_bc(sel_sym, displacement_x="free", displacement_y="fixed",
                 displacement_z="free", displacement_rotation="fixed")

# Global scour modelling
if scour > 0:
    sel = mod.select([R + 5, R + 5, 0], types="face")
    mod.extrude(sel,[0, 0, -scour]) 
    sel = mod.select([R + 5, R + 5, -scour/2], types="volume")
    mod.delete_shapes(sel)  
    
# Add standard fixities and zoom all
mod.set_standard_fixities()
mod.zoom_all()

# Set analysis properties
mod.set_analysis_properties(
                        analysis_type='load_deformation',
                        element_type="mixed",
                        no_of_elements=N_el_final,
                        mesh_adaptivity='yes',
                        adaptivity_iterations = 4,
                        start_elements=N_el_start,
                        reset_displacements = "yes",
                        load_deformation_scheme= 'target',
                        load_deformation_target= 'displacement',
                        load_deformation_u_target= u_target,
                        load_deformation_no_of_steps= N_steps,
                        load_deformation_step_variation= 'linear',
                        design_approach='unity',
                        )

# Determine Vmax
# Select center point
sel = mod.select([0, 0, 0], types="vertex")

# Apply multiplier load
mod.set_point_load(sel, -1, direction="z", option="multiplier")

# Set Point BC
sel__ = mod.select([0, 0, 0], types="vertex")
mod.set_point_bc(shapes=sel__,
                          displacement_x='fixed',
                          displacement_y='fixed',
                          displacement_z='free',
                          displacement_rotation_x = 'fixed', 
                          displacement_rotation_y = 'fixed',
                          displacement_rotation_z = 'fixed',
                          use_local_coord= False
                          )

# Apply mesh fan to all skirt tip vertices
N_segments = N_SIDES // 2 # 12 segments for half model
angles = np.linspace(0, 180, N_segments + 1) # 13 vertices (0° to 180°)
for angle_deg in angles:
    angle_rad = np.radians(angle_deg)
    x = R * np.cos(angle_rad)
    y = R * np.sin(angle_rad)
    sel_fan = mod.select([x, y, -S], types="vertex")
    if sel_fan:
        mod.set_mesh_fan(shapes=sel_fan, fan_angle=fan_angle_)

# Run
prj.run_analysis()
vmax_comp_end = time.time()
print(f"[TIME] Vmax computation completed in {vmax_comp_end - start_time:.2f} seconds")

##################################################################################
# VMAX RESULT COLLECTION
##################################################################################
resultpoints_collections = {}
plates_collections = {}

print(f"[INFO] Collecting step-by-step results for Vmax...")
try:
    output_V = mod.output  # Access output once to check if valid
    for step_idx in range(N_steps):
        if hasattr(output_V, 'step') and len(output_V.step) > step_idx:
            step_output = output_V.step[step_idx]
            output_name = f'step{step_idx + 1}'
            try:
                resultpoints_collections[output_name] = collect_resultpoints(step_output)
                plates_collections[output_name] = collect_plates(step_output)
                print(f"[SUCCESS] {output_name} results collected.")
            except (IndexError, AttributeError) as e:
                print(f"[WARNING] {output_name} produced no results. Error: {e}")
                print(f"[WARNING] Skipping {output_name} collection.")
        else:
            print(f"[WARNING] FAILED extract mod step {step_idx + 1} does not exist. Skipping.")
except Exception as e:
    print(f"[ERROR] Failed to access Vmax output: {e}")
    print(f"[WARNING] Skipping Vmax result collection.")

# Save Vmax results
save_collections_to_excel(resultpoints_collections, plates_collections, prefixes[0])

print("[INFO] Vmax data saving phase completed.")
vmax_save_end = time.time()
print(f"[TIME] Vmax saving completed in {vmax_save_end - vmax_comp_end:.2f} seconds")
print(f"[TIME] Total elapsed: {vmax_save_end - start_time:.2f} seconds")


##################################################################################
# HMAX ANALYSIS
##################################################################################
mod = mod.clone("Hmax")
loads = mod.get_features(sel)
mod.remove_features(loads)
mod.set_point_load(sel, 1, direction="x", option="multiplier")

# Set displacement BC with ux = 0
sel2 = mod.select([0, 0, 0], types="edge")
bcs = mod.get_features(sel2)
mod.remove_features(bcs)
mod.set_plate_bc(sel2, displacement_x="free", displacement_y="fixed",
                 displacement_z="fixed", displacement_rotation="fixed")

# Set Point BC
sel__ = mod.select([0, 0, 0], types="vertex")
mod.set_point_bc(shapes=sel__,
                          displacement_x='free',
                          displacement_y='fixed',
                          displacement_z='fixed',
                          displacement_rotation_x = 'fixed', 
                          displacement_rotation_y = 'fixed',
                          displacement_rotation_z = 'fixed',
                          use_local_coord= False
                          )
sel_ = mod.select([0, 0, 0], types="vertex")
mod.set_resultpoint(sel_)

prj.run_analysis()
hmax_comp_end = time.time()
print(f"[TIME] Hmax computation completed in {hmax_comp_end - vmax_save_end:.2f} seconds")

resultpoints_collections = {}
plates_collections = {}

print(f"[INFO] Collecting step-by-step results for Hmax...")
try:
    output_H = mod.output  # Access output once to check if valid
    for step_idx in range(N_steps):
        if hasattr(output_H, 'step') and len(output_H.step) > step_idx:
            step_output = output_H.step[step_idx]
            output_name = f'step{step_idx + 1}'
            try:
                resultpoints_collections[output_name] = collect_resultpoints(step_output)
                plates_collections[output_name] = collect_plates(step_output)
                print(f"[SUCCESS] {output_name} results collected.")
            except (IndexError, AttributeError) as e:
                print(f"[WARNING] {output_name} produced no results. Error: {e}")
                print(f"[WARNING] Skipping {output_name} collection.")
        else:
            print(f"[WARNING] FAILED extract mod step {step_idx + 1} does not exist. Skipping.")
except Exception as e:
    print(f"[ERROR] Failed to access Hmax output: {e}")
    print(f"[WARNING] Skipping Hmax result collection.")

# Save  results
save_collections_to_excel(resultpoints_collections, plates_collections, prefixes[1])

print("[INFO] Hmax data saving phase completed.")
hmax_save_end = time.time()
print(f"[TIME] Hmax saving completed in {hmax_save_end - hmax_comp_end:.2f} seconds")
print(f"[TIME] Total elapsed: {hmax_save_end - start_time:.2f} seconds")


print("[INFO] Starting Excel file post-processing (fixing)...")
for excel in excel_files_fix:
    input_path = os.path.join(input_dir, excel)
    if os.path.exists(input_path):
        try:
            print(f"[INFO] Processing {excel}...")
            xl = pd.ExcelFile(input_path)
            output_path = os.path.join(output_dir, excel.replace('.xlsx', '_fixed.xlsx'))
            with pd.ExcelWriter(output_path, engine='openpyxl') as writer:
                for sheet_name in xl.sheet_names:
                    try:
                        df = xl.parse(sheet_name)
                        # Fix _hint column if it exists
                        if '_hint' in df.columns:
                            df['_hint'] = df['_hint'].apply(safe_eval)
                        # Apply fix_cell to all cells
                        df = df.map(fix_cell)
                        # Expand list columns
                        df = expand_list_columns(df)
                        # Drop entirely empty columns
                        df = df.dropna(how='all', axis=1)
                        # Save to sheet
                        df.to_excel(writer, sheet_name=sheet_name, index=False)
                    except Exception as e:
                        print(f"[WARNING] Error processing sheet '{sheet_name}' in {input_path}: {e}")
            print(f"[SUCCESS] Fixed Excel saved: {output_path}")
        except Exception as e:
            print(f"[ERROR] Error processing {input_path}: {e}")
    else:
        print(f"[WARNING] File not found: {input_path} (skipping)")
print("[INFO] All post-processing completed. Check 'results_fixed' directory for output files.")
