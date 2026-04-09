# -*- coding: utf-8 -*-
"""
BNWF Pipeline Step 5: OpenSeesPy BNWF Foundation + Tower Model
===============================================================
Assembles a complete OWT model with:
  - Wheel-and-spoke BNWF foundation (PySimple1 + TzSimple1 + QzSimple1)
  - Stiffness from Gazetas/CPT (Step 3)
  - Capacity from OptumGX plate pressures (Step 4)
  - Simplified tower + RNA mass
  - Eigenvalue analysis for natural frequency

Input:  results/spring_stiffness_profile.csv (Step 3)
        results/spring_stiffness_profile.json (Step 3)
        results/capacity_profile.csv (Step 4)
        results/capacity_profile.json (Step 4)
Output: results/eigenvalue_results.json
        results/model_summary.json
"""
import openseespy.opensees as ops
import numpy as np
import pandas as pd
from pathlib import Path
import json
import math

RESULTS_DIR = Path(__file__).parent / 'results'

# =============================================================================
# STRUCTURAL CONSTANTS (SiteA 4MW OWT)
# =============================================================================
# Units: N, m, kg, s
E_STEEL = 210e9         # Pa
G_STEEL = 81e9          # Pa
RHO_STEEL = 7850.0      # kg/m3

# Bucket geometry
D_BUCKET = 8.0          # m
R_BUCKET = D_BUCKET / 2
L_SKIRT = float('nan')           # m
T_SKIRT = 0.025         # m
T_LID = 0.040           # m
DZ = 0.5                # m
N_DEPTH = int(L_SKIRT / DZ) + 1  # 19 depth levels (0 to -9.0m)
N_SPOKES = 24           # perimeter nodes per depth

# Tower
TOWER_HEIGHT = 95.0     # m above seabed
D_TOWER = 4.0           # m
T_TOWER = 0.035         # m
N_TOWER_ELEM = 20       # tower discretization

# RNA
MASS_RNA = 338000.0     # kg
RNA_IZ = 20_000_000.0   # kg*m2

# Bucket structural mass (per bucket for tripod; use full for mono)
MASS_BUCKET = 337000.0  # kg

# Unit conversion: pipeline outputs are in kN/m, OpenSees needs N/m
KN_TO_N = 1000.0

# Scour
SCOUR_DEPTH = 0.0       # m (default: no scour)

# Ghost stiffness for numerical stability
GHOST_K = 100.0         # N/m


# =============================================================================
# MODEL BUILDER
# =============================================================================
class BNWFModel:
    """
    OpenSeesPy BNWF model for suction bucket OWT.

    Architecture:
      - Backbone column (beam elements) from z=-L_SKIRT to z=0 (bucket)
      - Perimeter nodes at R_BUCKET connected by rigid links
      - p-y springs (PySimple1) on perimeter nodes (lateral)
      - t-z springs (TzSimple1) on perimeter nodes (vertical shaft friction)
      - q-z spring (QzSimple1) at base (tip bearing)
      - Base rotational spring (if needed for Kr deficit)
      - Tower beam elements from z=0 to z=TOWER_HEIGHT
      - RNA lumped mass at top
    """

    def __init__(self, scour_depth=0.0):
        self.scour = scour_depth
        self._mat_tag = 1
        self._ele_tag = 1
        self._node_tag = 1
        self.hub_node = None

    def _next_mat(self):
        t = self._mat_tag; self._mat_tag += 1; return t

    def _next_ele(self):
        t = self._ele_tag; self._ele_tag += 1; return t

    def _next_node(self):
        t = self._node_tag; self._node_tag += 1; return t

    def build(self):
        """Build the complete model."""
        ops.wipe()
        ops.model('basic', '-ndm', 3, '-ndf', 6)

        # Load pipeline data
        df_k = pd.read_csv(RESULTS_DIR / 'spring_stiffness_profile.csv')
        df_cap = pd.read_csv(RESULTS_DIR / 'capacity_profile.csv')
        with open(RESULTS_DIR / 'spring_stiffness_profile.json') as f:
            meta_k = json.load(f)
        with open(RESULTS_DIR / 'capacity_profile.json') as f:
            meta_cap = json.load(f)

        Kv_base = meta_k['Kv_base_kN_m'] * KN_TO_N  # N/m
        Kr_base = meta_k['Kr_base_kNm_rad'] * KN_TO_N  # N*m/rad
        H_base_cap = meta_cap.get('H_base_kN', 0) * KN_TO_N  # N

        # Depth nodes for foundation
        z_nodes = np.arange(0, -L_SKIRT - DZ/2, -DZ)  # 0, -0.5, ..., -9.0
        n_depth = len(z_nodes)

        # ==== BACKBONE NODES (along centerline) ====
        backbone_nodes = []
        for i, z in enumerate(z_nodes):
            nid = self._next_node()
            ops.node(nid, 0.0, 0.0, z)
            backbone_nodes.append(nid)

        # ==== TOWER NODES ====
        tower_dz = TOWER_HEIGHT / N_TOWER_ELEM
        tower_nodes = [backbone_nodes[0]]  # starts at mudline (z=0)
        for i in range(1, N_TOWER_ELEM + 1):
            z = i * tower_dz
            nid = self._next_node()
            ops.node(nid, 0.0, 0.0, z)
            tower_nodes.append(nid)
        self.hub_node = tower_nodes[-1]

        # ==== BUCKET BEAM ELEMENTS (backbone) ====
        A_skirt = np.pi * D_BUCKET * T_SKIRT
        I_skirt = np.pi * D_BUCKET**3 * T_SKIRT / 8
        J_skirt = 2 * I_skirt

        transf_tag = 1
        ops.geomTransf('Linear', transf_tag, 1, 0, 0)

        sec_skirt = self._next_mat()
        ops.section('Elastic', sec_skirt, E_STEEL, A_skirt,
                    I_skirt, I_skirt, G_STEEL, J_skirt)

        for i in range(len(backbone_nodes) - 1):
            etag = self._next_ele()
            itag = self._next_mat()
            ops.beamIntegration('Lobatto', itag, sec_skirt, 3)
            ops.element('forceBeamColumn', etag,
                        backbone_nodes[i], backbone_nodes[i+1],
                        transf_tag, itag)

        # ==== TOWER BEAM ELEMENTS ====
        A_tower = np.pi * D_TOWER * T_TOWER
        I_tower = np.pi * D_TOWER**3 * T_TOWER / 8
        J_tower = 2 * I_tower

        transf_tower = 2
        ops.geomTransf('Linear', transf_tower, 1, 0, 0)

        sec_tower = self._next_mat()
        ops.section('Elastic', sec_tower, E_STEEL, A_tower,
                    I_tower, I_tower, G_STEEL, J_tower)

        for i in range(len(tower_nodes) - 1):
            etag = self._next_ele()
            itag = self._next_mat()
            ops.beamIntegration('Lobatto', itag, sec_tower, 3)
            ops.element('forceBeamColumn', etag,
                        tower_nodes[i], tower_nodes[i+1],
                        transf_tower, itag)

        # ==== RNA MASS ====
        ops.mass(self.hub_node, MASS_RNA, MASS_RNA, MASS_RNA,
                 RNA_IZ, RNA_IZ, 0.0)

        # ==== BUCKET MASS (distributed) ====
        mass_per_node = MASS_BUCKET / n_depth
        for nid in backbone_nodes:
            ops.mass(nid, mass_per_node, mass_per_node, mass_per_node,
                     0, 0, 0)

        # ==== SOIL SPRINGS ====
        n_springs = 0

        for i, z in enumerate(z_nodes):
            depth_below_mudline = abs(z)
            depth_below_scour = depth_below_mudline - self.scour

            # Get stiffness and capacity at this depth index
            if i < len(df_k):
                K_py = df_k.iloc[i]['K_py_node_kN_m'] * KN_TO_N  # N/m
                K_tz = df_k.iloc[i]['K_tz_node_kN_m'] * KN_TO_N  # N/m
            else:
                K_py = GHOST_K
                K_tz = GHOST_K

            if i < len(df_cap):
                p_ult = df_cap.iloc[i]['p_ult_node_kN'] * KN_TO_N  # N
                t_ult = df_cap.iloc[i]['t_ult_node_kN'] * KN_TO_N  # N
            else:
                p_ult = 0
                t_ult = 0

            # Apply scour: springs above scour line are deactivated
            if depth_below_scour < 0:
                K_py = GHOST_K
                K_tz = GHOST_K
                p_ult = 0
                t_ult = 0

            # Skip if no capacity
            if p_ult <= 0:
                p_ult = K_py * 0.1  # small default
            if t_ult <= 0:
                t_ult = K_tz * 0.1

            # y50 = p_ult / (2 * K)
            y50_py = max(p_ult / (2 * K_py), 1e-6) if K_py > GHOST_K else 0.01
            z50_tz = max(t_ult / (2 * K_tz), 1e-6) if K_tz > GHOST_K else 0.01

            # Create ground anchor node
            anchor = self._next_node()
            ops.node(anchor, 0.0, 0.0, z)
            ops.fix(anchor, 1, 1, 1, 1, 1, 1)

            # p-y spring (horizontal X)
            mat_px = self._next_mat()
            ops.uniaxialMaterial('PySimple1', mat_px, 2, p_ult, y50_py, 0.0, 0.0)

            # p-y spring (horizontal Y)
            mat_py = self._next_mat()
            ops.uniaxialMaterial('PySimple1', mat_py, 2, p_ult, y50_py, 0.0, 0.0)

            # t-z spring (vertical)
            mat_tz = self._next_mat()
            ops.uniaxialMaterial('TzSimple1', mat_tz, 2, t_ult, z50_tz, 0.0)

            # Elastic for rotational DOFs (small)
            mat_rx = self._next_mat()
            ops.uniaxialMaterial('Elastic', mat_rx, GHOST_K)
            mat_ry = self._next_mat()
            ops.uniaxialMaterial('Elastic', mat_ry, GHOST_K)
            mat_rz = self._next_mat()
            ops.uniaxialMaterial('Elastic', mat_rz, GHOST_K)

            # zeroLength element: backbone → anchor
            etag = self._next_ele()
            ops.element('zeroLength', etag, anchor, backbone_nodes[i],
                        '-mat', mat_px, mat_py, mat_tz,
                        mat_rx, mat_ry, mat_rz,
                        '-dir', 1, 2, 3, 4, 5, 6)
            n_springs += 1

        # ==== BASE SPRINGS (tip bearing + rotational correction) ====
        base_node = backbone_nodes[-1]  # deepest backbone node
        base_anchor = self._next_node()
        ops.node(base_anchor, 0.0, 0.0, z_nodes[-1])
        ops.fix(base_anchor, 1, 1, 1, 1, 1, 1)

        # Q-z spring (vertical bearing at tip)
        V_base_cap = meta_cap.get('V_base_kN', 50000) * KN_TO_N
        if V_base_cap <= 0:
            V_base_cap = 50000 * KN_TO_N  # fallback
        z50_base = max(V_base_cap / (2 * Kv_base), 1e-6) if Kv_base > 0 else 0.01
        mat_qz = self._next_mat()
        ops.uniaxialMaterial('QzSimple1', mat_qz, 2, V_base_cap, z50_base, 0.0, 0.0)

        # Base horizontal shear spring
        mat_hbase = self._next_mat()
        H_base = max(H_base_cap, 1000)
        ops.uniaxialMaterial('PySimple1', mat_hbase, 2, H_base, 0.01, 0.0, 0.0)

        # Base rotational springs (Kr deficit)
        mat_rbase_x = self._next_mat()
        ops.uniaxialMaterial('Elastic', mat_rbase_x, max(Kr_base, GHOST_K))
        mat_rbase_y = self._next_mat()
        ops.uniaxialMaterial('Elastic', mat_rbase_y, max(Kr_base, GHOST_K))
        mat_rbase_z = self._next_mat()
        ops.uniaxialMaterial('Elastic', mat_rbase_z, GHOST_K)

        etag = self._next_ele()
        ops.element('zeroLength', etag, base_anchor, base_node,
                    '-mat', mat_hbase, mat_hbase, mat_qz,
                    mat_rbase_x, mat_rbase_y, mat_rbase_z,
                    '-dir', 1, 2, 3, 4, 5, 6)

        # Fix the deepest backbone node against torsion (prevent rigid body)
        # (all other DOFs are restrained by springs)

        print(f"  Model built:")
        print(f"    Backbone nodes:  {n_depth}")
        print(f"    Tower nodes:     {len(tower_nodes)}")
        print(f"    Soil springs:    {n_springs}")
        print(f"    Hub node:        {self.hub_node} at z={TOWER_HEIGHT}m")
        print(f"    Total nodes:     {self._node_tag - 1}")
        print(f"    Total elements:  {self._ele_tag - 1}")
        print(f"    Scour depth:     {self.scour}m")

        return {
            'n_backbone': n_depth,
            'n_tower': len(tower_nodes),
            'n_springs': n_springs,
            'n_nodes': self._node_tag - 1,
            'n_elements': self._ele_tag - 1,
        }

    def eigenvalue_analysis(self, n_modes=10):
        """Run eigenvalue analysis and return natural frequencies."""
        try:
            eigenvalues = ops.eigen(n_modes)
            freqs = [np.sqrt(abs(ev)) / (2 * np.pi) for ev in eigenvalues]
        except Exception as e:
            print(f"  WARNING: Eigenvalue failed: {e}")
            # Try with fewer modes
            try:
                eigenvalues = ops.eigen(3)
                freqs = [np.sqrt(abs(ev)) / (2 * np.pi) for ev in eigenvalues]
            except Exception as e2:
                print(f"  ERROR: {e2}")
                freqs = [0.0] * n_modes

        return freqs


# =============================================================================
# MAIN
# =============================================================================
if __name__ == "__main__":
    print("=" * 60)
    print("BNWF Pipeline Step 5: OpenSeesPy BNWF Model")
    print("=" * 60)

    # Check prerequisites
    for f in ['spring_stiffness_profile.csv', 'spring_stiffness_profile.json',
              'capacity_profile.csv', 'capacity_profile.json']:
        if not (RESULTS_DIR / f).exists():
            raise FileNotFoundError(f"Run Steps 1-4 first: {f}")

    # Build and run at zero scour
    print("\n  Building model (scour = 0.0m)...")
    model = BNWFModel(scour_depth=0.0)
    stats = model.build()

    print("\n  Running eigenvalue analysis...")
    freqs = model.eigenvalue_analysis(n_modes=10)

    print(f"\n  Natural frequencies:")
    for i, f in enumerate(freqs[:6]):
        label = ""
        if i == 0:
            label = " <-- 1st fore-aft/side-side"
        elif i == 1:
            label = " <-- 2nd mode"
        print(f"    Mode {i+1}: f = {f:.4f} Hz  (T = {1/f:.2f}s){label}"
              if f > 0 else f"    Mode {i+1}: f = 0.0000 Hz")

    # Scour sensitivity
    print("\n  Scour sensitivity study...")
    scour_depths = np.arange(0, 5.0, 0.5)
    scour_results = {'scour_m': [], 'f1_Hz': [], 'f2_Hz': [], 'f3_Hz': []}

    for sd in scour_depths:
        m = BNWFModel(scour_depth=sd)
        m.build()
        f = m.eigenvalue_analysis(n_modes=6)
        scour_results['scour_m'].append(sd)
        scour_results['f1_Hz'].append(f[0] if len(f) > 0 else 0)
        scour_results['f2_Hz'].append(f[1] if len(f) > 1 else 0)
        scour_results['f3_Hz'].append(f[2] if len(f) > 2 else 0)
        print(f"    Scour {sd:.1f}m: f1 = {f[0]:.4f} Hz" if f[0] > 0
              else f"    Scour {sd:.1f}m: FAILED")

    # Save results
    results = {
        'zero_scour': {
            'frequencies_Hz': [round(f, 6) for f in freqs[:10]],
            'f1_Hz': round(freqs[0], 6) if freqs[0] > 0 else None,
            'T1_s': round(1/freqs[0], 4) if freqs[0] > 0 else None,
        },
        'scour_sensitivity': scour_results,
        'model_stats': stats,
        'config': {
            'D': D_BUCKET, 'L': L_SKIRT, 'tower_H': TOWER_HEIGHT,
            'mass_RNA_kg': MASS_RNA, 'mass_bucket_kg': MASS_BUCKET,
            'N_spokes': N_SPOKES, 'N_depth': N_DEPTH,
        },
    }

    if len(scour_results['f1_Hz']) >= 2 and scour_results['f1_Hz'][0] > 0:
        f1_0 = scour_results['f1_Hz'][0]
        # Find scour depth where f drops by 5%
        for i, f in enumerate(scour_results['f1_Hz']):
            if f > 0 and f < 0.95 * f1_0:
                results['scour_5pct_drop_m'] = scour_results['scour_m'][i]
                break

    json_path = RESULTS_DIR / 'eigenvalue_results.json'
    with open(json_path, 'w') as f:
        json.dump(results, f, indent=2, default=str)

    # Summary
    print(f"\n{'='*60}")
    print("RESULTS SUMMARY")
    print(f"{'='*60}")
    print(f"  1st natural frequency: {freqs[0]:.4f} Hz  "
          f"(T = {1/freqs[0]:.2f}s)" if freqs[0] > 0 else
          "  1st natural frequency: FAILED")
    print(f"  Scour sensitivity: {len(scour_depths)} cases computed")
    if 'scour_5pct_drop_m' in results:
        print(f"  5% frequency drop at scour = "
              f"{results['scour_5pct_drop_m']:.1f}m")
    print(f"  Saved: {json_path.name}")
    print(f"{'='*60}")
