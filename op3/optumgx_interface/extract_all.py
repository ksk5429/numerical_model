# -*- coding: utf-8 -*-
"""
Universal OptumGX Output Extraction Module
===========================================
Extracts ALL available data from plate and solid elements at collapse.
Copy this file alongside any PC script that needs it.

Usage:
    from extract_all import extract_full_output
    plates_df, solids_df, summary = extract_full_output(mod.output)
"""
import numpy as np
import pandas as pd
import re


def _parse(attr):
    """Parse any OptumGX attribute to Python numeric."""
    if attr is None:
        return None
    if isinstance(attr, (int, float)):
        return attr
    if isinstance(attr, np.ndarray):
        return attr.tolist()
    if isinstance(attr, (list, tuple)):
        return [float(x) if isinstance(x, (int, float, np.floating)) else x for x in attr]
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


def _get(obj, name):
    """Safely get and parse a property."""
    return _parse(getattr(obj, name, None))


def _expand(row, prefix, val):
    """Expand a list value into numbered columns."""
    if isinstance(val, list):
        for j, v in enumerate(val, 1):
            row[f'{prefix}_{j}'] = v
    elif val is not None:
        row[prefix] = val


def extract_plates(output):
    """
    Extract ALL plate element data.

    Returns DataFrame with columns:
      Coordinates: X_1,2,3, Y_1,2,3, Z_1,2,3
      Pressures:   sigma_plus_1,2,3, sigma_minus_1,2,3, tau_plus_1,2,3, tau_minus_1,2,3
      Forces:      Fq_x_1..N, Fq_y_1..N, Fq_z_1..N
      Membrane:    n1_1,2,3, n2_1,2,3, nxy_1,2,3, nx_1,2,3, ny_1,2,3
      Moments:     m1_1,2,3, m2_1,2,3, mxy_1,2,3, mx_1,2,3, my_1,2,3
      Collapse:    cm_u_norm_1,2,3, cm_u_x_1,2,3, cm_u_y_1,2,3, cm_u_z_1,2,3
      Dissipation: dissip_total_1..N, dissip_shear_1..N
      Strains:     strain_total (raw)
    """
    rows = []
    for plate in output.plate:
        row = {}

        # Material
        if hasattr(plate, 'general'):
            row['material'] = _get(plate.general, 'material_name')

        # Topology
        if hasattr(plate, 'topology'):
            top = plate.topology
            for c in ['X', 'Y', 'Z']:
                _expand(row, c, _get(top, c))

        if not hasattr(plate, 'results'):
            rows.append(row)
            continue

        res = plate.results

        # Total pressures
        if hasattr(res, 'total_pressures'):
            tp = res.total_pressures
            for prop in ['sigma_plus', 'sigma_minus', 'tau_plus', 'tau_minus']:
                _expand(row, prop, _get(tp, prop))

        # Nodal forces
        if hasattr(res, 'nodal_forces'):
            nf = res.nodal_forces
            for prop in ['q_x', 'q_y', 'q_z']:
                _expand(row, f'Fq_{prop[2:]}', _get(nf, prop))

        # Membrane forces
        if hasattr(res, 'membrane_forces'):
            mf = res.membrane_forces
            for prop in ['nx', 'ny', 'nxy', 'n1', 'n2']:
                _expand(row, f'mem_{prop}', _get(mf, prop))

        # Plate moments
        if hasattr(res, 'plate_moments'):
            pm = res.plate_moments
            for prop in ['mx', 'my', 'mxy', 'm1', 'm2']:
                _expand(row, f'mom_{prop}', _get(pm, prop))

        # Collapse mechanism
        if hasattr(res, 'collapse_mechanism'):
            cm = res.collapse_mechanism
            for prop in ['u_norm', 'u_x', 'u_y', 'u_z']:
                _expand(row, f'cm_{prop}', _get(cm, prop))

        # Plasticity / dissipation
        if hasattr(res, 'plasticity'):
            pl = res.plasticity
            for prop in ['total_dissipation', 'shear_dissipation']:
                _expand(row, f'dissip_{prop.split("_")[0]}', _get(pl, prop))

        # Strains
        if hasattr(res, 'strains'):
            st = res.strains
            if hasattr(st, 'total_strains'):
                _expand(row, 'strain_total', _get(st, 'total_strains'))

        rows.append(row)
    return pd.DataFrame(rows)


def extract_solids(output, max_elements=None):
    """
    Extract ALL solid element data.

    Returns DataFrame with columns:
      Coordinates: X_1..4, Y_1..4, Z_1..4
      Stresses:    sig_x_1..4, sig_y_1..4, sig_z_1..4, tau_xy_1..4, ...
                   sig_1_1..4, sig_2_1..4, sig_3_1..4, p_1..4, q_1..4
      Strains:     eps_total_x_1..4, ..., eps_plastic_x_1..4, ...
      Collapse:    cm_u_norm_1..4, cm_u_x_1..4, cm_u_y_1..4, cm_u_z_1..4
      Dissipation: dissip_total_1..4, dissip_shear_1..4
      Forces:      Fq_x_1..N, Fq_y_1..N, Fq_z_1..N
    """
    rows = []
    count = 0
    for solid in output.solid:
        if max_elements and count >= max_elements:
            break
        count += 1
        row = {}

        if hasattr(solid, 'general'):
            row['material'] = _get(solid.general, 'material_name')

        if hasattr(solid, 'topology'):
            top = solid.topology
            for c in ['X', 'Y', 'Z']:
                _expand(row, c, _get(top, c))

        if not hasattr(solid, 'results'):
            rows.append(row)
            continue

        res = solid.results

        # Final stresses
        if hasattr(res, 'final_stresses'):
            fs = res.final_stresses
            if hasattr(fs, 'total_stresses'):
                ts = fs.total_stresses
                # total_stresses is a nested object with labeled values
                stress_props = ['sigma_x', 'sigma_y', 'sigma_z', 'tau_xy',
                                'sigma_1', 'sigma_2', 'sigma_3',
                                't', 's', 'q', 'p', 'theta']
                if hasattr(ts, '__iter__'):
                    # It's a labels list — try each
                    for sp in stress_props:
                        _expand(row, f'sig_{sp}', _get(fs, sp) if hasattr(fs, sp) else None)
                else:
                    _expand(row, 'stress_raw', _get(fs, 'total_stresses'))

        # Strains (total + plastic)
        if hasattr(res, 'strains'):
            st = res.strains
            for stype in ['total_strains', 'plastic_strains']:
                if hasattr(st, stype):
                    sub = getattr(st, stype)
                    prefix = 'eps_t' if 'total' in stype else 'eps_p'
                    strain_props = ['epsilon_x', 'epsilon_y', 'epsilon_z',
                                    'gamma_xy', 'gamma_yz',
                                    'epsilon_1', 'epsilon_2', 'epsilon_3',
                                    'epsilon_v', 'epsilon_q']
                    for sp in strain_props:
                        _expand(row, f'{prefix}_{sp}', _get(sub, sp) if hasattr(sub, sp) else None)
                    # If individual props don't work, try raw
                    if not any(k.startswith(prefix) for k in row):
                        _expand(row, f'{prefix}_raw', _get(st, stype))

        # Collapse mechanism
        if hasattr(res, 'collapse_mechanism'):
            cm = res.collapse_mechanism
            for prop in ['u_norm', 'u_x', 'u_y', 'u_z']:
                _expand(row, f'cm_{prop}', _get(cm, prop))

        # Plasticity / dissipation
        if hasattr(res, 'plasticity'):
            pl = res.plasticity
            for prop in ['total_dissipation', 'shear_dissipation']:
                _expand(row, f'dissip_{prop.split("_")[0]}', _get(pl, prop))

        # Nodal forces
        if hasattr(res, 'nodal_forces'):
            nf = res.nodal_forces
            for prop in ['q_x', 'q_y', 'q_z']:
                _expand(row, f'Fq_{prop[2:]}', _get(nf, prop))

        rows.append(row)
    return pd.DataFrame(rows)


def extract_summary(output):
    """
    Extract global and critical result summaries (single values).
    """
    summary = {}

    # Global
    try:
        gr = output.global_results
        summary['load_multiplier'] = _get(gr, 'load_multiplier')
        summary['max_displacement'] = _get(gr, 'max_displacement')
        summary['factor_of_safety'] = _get(gr, 'factor_of_safety')
    except: pass

    # Critical
    try:
        cr = output.critical_results
        for attr in ['u_solid_norm_max', 'u_plate_norm_max',
                     'du_solid_x_max', 'du_solid_y_max', 'du_solid_z_max',
                     'sx_effective_max', 'sx_effective_min',
                     'sz_effective_max', 'sz_effective_min']:
            val = _get(cr, attr)
            if val is not None:
                summary[f'cr_{attr}'] = val
    except: pass

    return summary


def extract_full_output(output, save_dir=None, tag=''):
    """
    Extract everything from an OptumGX output object.

    Parameters
    ----------
    output : OptumGX StageOutput
    save_dir : Path or None. If provided, saves CSVs.
    tag : str. Prefix for filenames.

    Returns
    -------
    plates_df, solids_df, summary_dict
    """
    plates_df = extract_plates(output)
    solids_df = extract_solids(output)
    summary = extract_summary(output)

    # Add computed geometry to plates
    if 'X_1' in plates_df.columns:
        for coord in ['X', 'Y', 'Z']:
            cols = [c for c in plates_df.columns if c.startswith(f'{coord}_')]
            if cols:
                plates_df[f'{coord}c'] = plates_df[cols].mean(axis=1)

    # Compute dissipation statistics for summary
    dissip_cols = [c for c in solids_df.columns if c.startswith('dissip_total_')]
    if dissip_cols:
        all_dissip = solids_df[dissip_cols].values.flatten()
        all_dissip = all_dissip[~np.isnan(all_dissip)]
        if len(all_dissip) > 0:
            summary['total_dissipation_kJ'] = float(np.sum(all_dissip))
            summary['mean_dissipation_kJ'] = float(np.mean(all_dissip))
            summary['n_elements_with_dissip'] = int(np.sum(all_dissip > 0.01 * np.max(all_dissip)))
            summary['n_elements_total'] = len(solids_df)
            summary['mobilised_fraction'] = summary['n_elements_with_dissip'] / max(summary['n_elements_total'], 1)

    # Collapse mechanism statistics
    cm_cols = [c for c in solids_df.columns if c.startswith('cm_u_norm_')]
    if cm_cols:
        all_u = solids_df[cm_cols].values.flatten()
        all_u = all_u[~np.isnan(all_u)]
        if len(all_u) > 0:
            summary['cm_u_norm_max'] = float(np.max(all_u))
            summary['cm_u_norm_mean'] = float(np.mean(all_u))
            summary['n_mobilised_50pct'] = int(np.sum(all_u > 0.5 * np.max(all_u)))

    # Save if directory provided
    if save_dir is not None:
        save_dir.mkdir(parents=True, exist_ok=True)
        prefix = f'{tag}_' if tag else ''
        plates_df.to_csv(save_dir / f'{prefix}plates.csv', index=False)
        solids_df.to_csv(save_dir / f'{prefix}solids.csv', index=False)

    return plates_df, solids_df, summary
