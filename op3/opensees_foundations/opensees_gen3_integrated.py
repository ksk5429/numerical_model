"""
OpenSeesPy Gen 3: Integrated Tripod BNWF Model
================================================
Merges Gen 1 architecture (full tripod, real tower, stress-relief scour)
with Gen 2 data source (CPT-pipeline CSVs, no Excel dependency).

Architecture (from Gen 1):
  - Full tripod with 3 suction buckets from SSOT_REAL_FINAL.txt
  - Real tapered tower (28 elements from manufacturer drawings)
  - Tripod substructure (main column, braces, legs)
  - Lumped masses at correct nodes (RNA, platforms, anodes)
  - Stress-relief alpha scour: alpha = sqrt((z-S)/z)

Data source (from Gen 2):
  - Spring stiffness from CPT → Gazetas pipeline CSV
  - Capacity from OptumGX plate pressure CSV
  - No Excel dependency

Outputs:
  - Eigenvalue analysis (natural frequencies)
  - Scour sensitivity sweep (0-5m)
  - Power-law fit: f/f0 = 1 - a*(S/D)^b
  - Centrifuge benchmark comparison

Author: Kyeong Sun Kim
Date: 2026-03-31
"""

import openseespy.opensees as ops
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from scipy.optimize import curve_fit
from pathlib import Path
from dataclasses import dataclass, field as dc_field
from typing import Dict, List, Tuple, Optional
import math
import re
import json

# ==============================================================================
# 1. CONFIGURATION
# ==============================================================================

# Paths — adjust these to your folder structure
SSOT_FILE = Path(__file__).parent / "SSOT_REAL_FINAL.txt"
SPRING_CSV = Path(r"F:\TREE_OF_THOUGHT\PHD\data\fem_results\gen1_spring_profile_from_excel.csv")
PIPELINE_DIR = Path(r"F:\FEM\OPTUM\pipeline\bnwf_pipeline\results")

# If running from PHD folder, try local paths first
if not SSOT_FILE.exists():
    SSOT_FILE = Path(r"F:\TREE_OF_THOUGHT\PHD\config\SSOT_REAL_FINAL.txt")
if not SPRING_CSV.exists():
    SPRING_CSV = PIPELINE_DIR / 'spring_stiffness_profile.csv'

# Tip spring parameters (from Gen 1 Excel Tip_Parameters sheet)
TIP_STIFFNESS_N = 2.564e7   # N/m
TIP_CAPACITY_N = 8.696e5    # N

# Foundation
BUCKET_DIAMETER = 8.0
BUCKET_RADIUS = 4.0
BUCKET_LENGTH = 9.3
NUM_RIBS = 4           # ribs per depth level per bucket
DZ = 0.5               # depth discretization (m)

# Calibration
SMALL_STRAIN_MODIFIER = 3.0    # dynamic/static stiffness ratio
SOIL_PLUG_DENSITY = 2000.0     # kg/m3
MARINE_GROWTH_THICK = 0.05     # m
MARINE_GROWTH_RHO = 1400.0     # kg/m3
WATER_RHO = 1025.0             # kg/m3
ADDED_MASS_COEFF = 1.0

# Centrifuge benchmark
BENCHMARK_SCOUR_NORM = 0.6     # S/D
BENCHMARK_FREQ_DROP = 0.053    # 5.3% at 0.6D

# Sweep
SCOUR_RANGE = np.arange(0.0, 5.1, 0.5)


# ==============================================================================
# 2. SSOT PARSER
# ==============================================================================

@dataclass
class StructuralModel:
    """Parsed structural model from SSOT_REAL_FINAL.txt."""
    E: float = 2.1e11
    G: float = 8.1e10
    rho_steel: float = 7850.0
    nodes: Dict[int, Tuple[float, float, float]] = dc_field(default_factory=dict)
    elements: List[dict] = dc_field(default_factory=list)
    lumped_masses: Dict[int, float] = dc_field(default_factory=dict)
    boundary_nodes: List[int] = dc_field(default_factory=lambda: [215, 225, 235])


def parse_ssot(filepath: Path) -> StructuralModel:
    """Parse SSOT_REAL_FINAL.txt into a StructuralModel."""
    model = StructuralModel()
    section = None

    with open(filepath, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                if '1. GLOBAL' in line:
                    section = 'MAT'
                elif '2. NODAL' in line:
                    section = 'MASS'
                elif '4. NODAL' in line:
                    section = 'NODES'
                elif '5. ELEMENT' in line:
                    section = 'TOWER'
                elif '6. ELEMENT' in line:
                    section = 'TRIPOD'
                elif '8. SECONDARY' in line:
                    section = 'SEC_MASS'
                elif '7. SOIL' in line:
                    section = 'CPT'
                continue

            if section == 'MAT':
                if 'DENSITY_RHO:' in line:
                    model.rho_steel = float(line.split(':')[1].split('#')[0])
                elif 'YOUNGS_MODULUS_E:' in line:
                    model.E = float(line.split(':')[1].split('#')[0])
                elif 'SHEAR_MODULUS_G:' in line:
                    model.G = float(line.split(':')[1].split('#')[0])

            elif section in ('MASS', 'SEC_MASS'):
                m = re.search(r'NODE_MASS_(\d+):\s*([\d.eE+\-]+)', line)
                if m:
                    nid = int(m.group(1))
                    mass = float(m.group(2))
                    model.lumped_masses[nid] = model.lumped_masses.get(nid, 0.0) + mass

            elif section == 'NODES':
                parts = line.split('#')[0].split()
                if len(parts) >= 4 and parts[0].isdigit():
                    model.nodes[int(parts[0])] = (
                        float(parts[1]), float(parts[2]), float(parts[3])
                    )

            elif section in ('TOWER', 'TRIPOD'):
                parts = line.split('#')[0].split()
                if len(parts) >= 6:
                    try:
                        model.elements.append({
                            'type': parts[0],
                            'n1': int(parts[1]),
                            'n2': int(parts[2]),
                            'D_top': float(parts[3]),
                            'D_bot': float(parts[4]),
                            'thk': float(parts[5]),
                        })
                    except (ValueError, IndexError):
                        pass

    return model


# ==============================================================================
# 3. PIPELINE DATA LOADER
# ==============================================================================

@dataclass
class PipelineData:
    """Spring stiffness and capacity from Gen 2 CPT pipeline."""
    df_stiffness: pd.DataFrame = dc_field(default_factory=pd.DataFrame)
    df_capacity: pd.DataFrame = dc_field(default_factory=pd.DataFrame)
    meta_stiffness: dict = dc_field(default_factory=dict)
    meta_capacity: dict = dc_field(default_factory=dict)


def load_pipeline_data(spring_csv: Path, pipeline_dir: Path) -> PipelineData:
    """Load spring properties from depth-varying CSV.

    Prefers gen1_spring_profile_from_excel.csv (depth-varying, N units).
    Falls back to Gen 2 pipeline CSVs (uniform, kN units) if not found.
    """
    data = PipelineData()

    if spring_csv.exists() and 'gen1' in spring_csv.name:
        # Depth-varying springs (already in N/m and N)
        df = pd.read_csv(spring_csv)
        data.df_stiffness = df
        data.df_capacity = df
        data.meta_stiffness = {'source': 'gen1_excel_export', 'units': 'N'}
        data.meta_capacity = {'source': 'gen1_excel_export', 'units': 'N'}
        print(f"    Using depth-varying springs: {spring_csv.name}")
    else:
        # Gen 2 pipeline (uniform, kN units)
        stiff_csv = pipeline_dir / 'spring_stiffness_profile.csv'
        cap_csv = pipeline_dir / 'capacity_profile.csv'
        if stiff_csv.exists():
            data.df_stiffness = pd.read_csv(stiff_csv)
        if cap_csv.exists():
            data.df_capacity = pd.read_csv(cap_csv)
        stiff_json = pipeline_dir / 'spring_stiffness_profile.json'
        cap_json = pipeline_dir / 'capacity_profile.json'
        if stiff_json.exists():
            with open(stiff_json) as f:
                data.meta_stiffness = json.load(f)
        if cap_json.exists():
            with open(cap_json) as f:
                data.meta_capacity = json.load(f)
        print(f"    Using Gen 2 pipeline springs (uniform)")

    return data


# ==============================================================================
# 4. MODEL BUILDER
# ==============================================================================

class Gen3Model:
    """Gen 3 integrated model: Gen 1 architecture + Gen 2 data."""

    def __init__(self, structural: StructuralModel, pipeline: PipelineData):
        self.struct = structural
        self.pipe = pipeline
        self._node_id = 10000
        self._ele_id = 10000
        self._mat_id = 10000
        self._sec_id = 10000
        self._transf_id = 100
        self.rib_nodes: List[int] = []

    def _next_node(self) -> int:
        t = self._node_id; self._node_id += 1; return t

    def _next_ele(self) -> int:
        t = self._ele_id; self._ele_id += 1; return t

    def _next_mat(self) -> int:
        t = self._mat_id; self._mat_id += 1; return t

    def _next_sec(self) -> int:
        t = self._sec_id; self._sec_id += 1; return t

    def _next_transf(self) -> int:
        t = self._transf_id; self._transf_id += 1; return t

    @staticmethod
    def _tube_props(D: float, t: float):
        """Section properties for a hollow circular tube."""
        Di = D - 2 * t
        A = (math.pi / 4) * (D**2 - Di**2)
        I = (math.pi / 64) * (D**4 - Di**4)
        J = 2 * I
        return A, I, I, J

    def build(self, scour_depth: float = 0.0):
        """Build the complete tripod model."""
        ops.wipe()
        ops.model('basic', '-ndm', 3, '-ndf', 6)
        self._node_id = 10000
        self._ele_id = 10000
        self._mat_id = 10000
        self._sec_id = 10000
        self._transf_id = 100
        self.rib_nodes = []

        # --- Structural nodes ---
        for nid, (x, y, z) in self.struct.nodes.items():
            ops.node(nid, x, y, z)

        # --- Beam elements (tower + tripod) ---
        for ele in self.struct.elements:
            self._build_beam(ele)

        # --- Foundation (3 buckets with ribs + soil springs) ---
        for bucket_center in self.struct.boundary_nodes:
            self._build_bucket(bucket_center, scour_depth)

        # --- Lumped masses ---
        for nid, mass in self.struct.lumped_masses.items():
            if nid in self.struct.nodes:
                ops.mass(nid, mass, mass, mass, 0, 0, 0)

        # --- Hydrodynamic effects (marine growth + added mass) ---
        self._apply_hydrodynamics()

        # --- Soil plug mass ---
        self._apply_soil_plug(scour_depth)

        # --- Ghost stiffness for numerical stability ---
        self._apply_ghost_stiffness()

    def _build_beam(self, ele: dict):
        """Build a beam-column element from SSOT element data."""
        n1, n2 = ele['n1'], ele['n2']
        if n1 not in self.struct.nodes or n2 not in self.struct.nodes:
            return

        c1 = self.struct.nodes[n1]
        c2 = self.struct.nodes[n2]
        L = math.sqrt(sum((a - b)**2 for a, b in zip(c1, c2)))
        dz = abs(c2[2] - c1[2])

        transf = self._next_transf()
        if L > 0 and dz / L > 0.99:
            ops.geomTransf('Linear', transf, 0, 1, 0)
        else:
            ops.geomTransf('Linear', transf, 0, 0, 1)

        D_avg = (ele['D_top'] + ele['D_bot']) / 2
        A, Iy, Iz, J = self._tube_props(D_avg, ele['thk'])
        mass_dens = A * self.struct.rho_steel * 1.05  # 5% contingency

        e_tag = self._next_ele()
        s_tag = self._next_sec()
        ops.section('Elastic', s_tag, self.struct.E, A, Iz, Iy, self.struct.G, J)
        ops.beamIntegration('Lobatto', e_tag, s_tag, 5)
        ops.element('forceBeamColumn', e_tag, n1, n2, transf, e_tag,
                    '-mass', mass_dens)

    def _build_bucket(self, center_nid: int, scour_depth: float):
        """Build one suction bucket with ribs and soil springs."""
        if center_nid not in self.struct.nodes:
            return

        cx, cy, cz = self.struct.nodes[center_nid]
        depths = np.arange(0, BUCKET_LENGTH + DZ / 2, DZ)

        transf_vert = self._next_transf()
        transf_horz = self._next_transf()
        ops.geomTransf('Linear', transf_vert, 0, 1, 0)
        ops.geomTransf('Linear', transf_horz, 0, 0, 1)

        # Rib section (skirt slice per rib)
        A_rib = (2 * math.pi * BUCKET_RADIUS * 0.05) / NUM_RIBS
        I_rib = 1.0

        for i_rib in range(NUM_RIBS):
            angle = 2 * math.pi * i_rib / NUM_RIBS
            rx = cx + BUCKET_RADIUS * math.cos(angle)
            ry = cy + BUCKET_RADIUS * math.sin(angle)

            # Top node (at bucket lid, connected to center by stiff link)
            top_nid = self._next_node()
            ops.node(top_nid, rx, ry, cz)

            lid_ele = self._next_ele()
            ops.element('elasticBeamColumn', lid_ele, center_nid, top_nid,
                        100.0, 1e14, 1e14, 100.0, 100.0, 100.0, transf_horz,
                        '-mass', 1.0)

            prev_nid = top_nid

            for i_depth, depth in enumerate(depths):
                if depth < 0.01:
                    continue

                curr_nid = self._next_node()
                ops.node(curr_nid, rx, ry, cz - depth)
                self.rib_nodes.append(curr_nid)

                # Rib element (vertical beam along skirt)
                rib_ele = self._next_ele()
                ops.element('elasticBeamColumn', rib_ele, prev_nid, curr_nid,
                            A_rib, self.struct.E, self.struct.G,
                            I_rib, I_rib, I_rib, transf_vert,
                            '-mass', A_rib * self.struct.rho_steel)

                # Soil springs (only below scour line)
                if depth > scour_depth:
                    self._add_spring(curr_nid, i_depth, depth, scour_depth)

                prev_nid = curr_nid

            # Tip spring at bucket base
            if BUCKET_LENGTH > scour_depth:
                self._add_tip_spring(prev_nid, BUCKET_LENGTH, scour_depth)

    def _add_spring(self, node: int, depth_idx: int, depth: float,
                    scour: float):
        """Add p-y and t-z springs with stress-relief alpha correction."""
        # Stress-relief factor
        sigma_old = depth * 10000.0  # gamma' * depth (approx)
        sigma_new = (depth - scour) * 10000.0
        if sigma_old <= 0 or sigma_new <= 0:
            return
        alpha = math.sqrt(sigma_new / sigma_old)

        # Get stiffness and capacity from data
        df = self.pipe.df_stiffness
        is_gen1 = self.pipe.meta_stiffness.get('source') == 'gen1_excel_export'

        if depth_idx >= len(df):
            return

        row = df.iloc[depth_idx]

        if is_gen1:
            # Gen 1 format: already in N, total per bucket (divide by NUM_RIBS)
            K_py = row['K_py_N_m'] / NUM_RIBS
            p_ult = row['p_ult_N'] / NUM_RIBS
            K_tz = row['K_tz_N_m'] / NUM_RIBS
            t_ult = row['t_ult_N'] / NUM_RIBS
        else:
            # Gen 2 format: in kN (multiply by 1000, divide by NUM_RIBS)
            K_py = row['K_py_node_kN_m'] * 1000 / NUM_RIBS
            K_tz = row['K_tz_node_kN_m'] * 1000 / NUM_RIBS
            df_c = self.pipe.df_capacity
            if depth_idx < len(df_c):
                p_ult = df_c.iloc[depth_idx]['p_ult_node_kN'] * 1000 / NUM_RIBS
                t_ult = df_c.iloc[depth_idx]['t_ult_node_kN'] * 1000 / NUM_RIBS
            else:
                p_ult = K_py * 0.1
                t_ult = K_tz * 0.1

        if K_py < 1 or p_ult <= 0:
            return

        # Apply stress-relief degradation
        K_py_mod = K_py * alpha
        p_ult_mod = p_ult * (alpha ** 2)
        K_tz_mod = K_tz * alpha
        t_ult_mod = t_ult * (alpha ** 2)

        # Half-displacement (corrected for small-strain)
        y50 = max((0.5 * p_ult_mod / K_py_mod) / SMALL_STRAIN_MODIFIER, 1e-6)
        z50 = max((0.5 * t_ult_mod / K_tz_mod) / SMALL_STRAIN_MODIFIER, 1e-6)

        # Create materials
        mat_py = self._next_mat()
        mat_tz = self._next_mat()
        ops.uniaxialMaterial('PySimple1', mat_py, 2, p_ult_mod, y50, 0.0)
        ops.uniaxialMaterial('TzSimple1', mat_tz, 2, t_ult_mod, z50, 0.0)

        # Anchor node (fixed)
        anc = self._next_node()
        coords = ops.nodeCoord(node)
        ops.node(anc, *coords)
        ops.fix(anc, 1, 1, 1, 1, 1, 1)

        # Zero-length element: lateral (x, y) + vertical (z)
        el = self._next_ele()
        ops.element('zeroLength', el, anc, node,
                    '-mat', mat_py, mat_py, mat_tz,
                    '-dir', 1, 2, 3)

    def _add_tip_spring(self, node: int, depth: float, scour: float):
        """Add Q-z spring at bucket tip."""
        sigma_old = depth * 10000.0
        sigma_new = (depth - scour) * 10000.0
        if sigma_new < 0:
            sigma_new = 0
        alpha = math.sqrt(sigma_new / sigma_old) if sigma_old > 0 else 0

        # Get tip capacity from pipeline metadata
        V_base = self.pipe.meta_capacity.get('V_base_kN', 0) * 1000  # N
        Kv_base = self.pipe.meta_stiffness.get('Kv_base_kN_m', 1e5) * 1000  # N/m

        q_ult = max(V_base / NUM_RIBS * (alpha ** 2), 1000)
        k_tip = max(Kv_base / NUM_RIBS * alpha, 1000)
        z50 = max((0.5 * q_ult / k_tip) / SMALL_STRAIN_MODIFIER, 1e-6)

        mat_qz = self._next_mat()
        ops.uniaxialMaterial('QzSimple1', mat_qz, 2, q_ult, z50)

        anc = self._next_node()
        coords = ops.nodeCoord(node)
        ops.node(anc, *coords)
        ops.fix(anc, 1, 1, 1, 1, 1, 1)

        el = self._next_ele()
        ops.element('zeroLength', el, anc, node, '-mat', mat_qz, '-dir', 3)

    def _apply_hydrodynamics(self):
        """Marine growth + added mass for submerged elements."""
        MSL = 0.0
        for ele in self.struct.elements:
            n1, n2 = ele['n1'], ele['n2']
            if n1 not in self.struct.nodes or n2 not in self.struct.nodes:
                continue

            c1, c2 = self.struct.nodes[n1], self.struct.nodes[n2]
            z_top = max(c1[2], c2[2])
            z_bot = min(c1[2], c2[2])

            if z_bot > MSL:
                continue

            L = math.sqrt(sum((a - b)**2 for a, b in zip(c1, c2)))
            L_sub = L if z_top <= MSL else L * ((MSL - z_bot) / (z_top - z_bot))

            D = (ele['D_top'] + ele['D_bot']) / 2
            De = D + 2 * MARINE_GROWTH_THICK

            M_bio = (math.pi / 4) * (De**2 - D**2) * MARINE_GROWTH_RHO * L_sub
            M_hyd = ADDED_MASS_COEFF * WATER_RHO * (math.pi / 4) * De**2 * L_sub
            M = M_bio + M_hyd

            if M > 0:
                ops.mass(n1, M / 2, M / 2, M / 2, 0, 0, 0)
                ops.mass(n2, M / 2, M / 2, M / 2, 0, 0, 0)

    def _apply_soil_plug(self, scour_depth: float):
        """Add soil plug mass inside buckets below scour line."""
        for bucket_center in self.struct.boundary_nodes:
            if bucket_center not in self.struct.nodes:
                continue
            cz = self.struct.nodes[bucket_center][2]
            scour_limit_z = cz - scour_depth

            area_plug = (math.pi * BUCKET_RADIUS**2) / NUM_RIBS

            for nid in self.rib_nodes:
                z = ops.nodeCoord(nid)[2]
                if z < scour_limit_z:
                    m_plug = area_plug * DZ * SOIL_PLUG_DENSITY
                    ops.mass(nid, m_plug, m_plug, 0, 0, 0, 0)

    def _apply_ghost_stiffness(self):
        """Small ghost springs for numerical stability."""
        mat_ghost = self._next_mat()
        ops.uniaxialMaterial('Elastic', mat_ghost, 1.0)

        for nid in ops.getNodeTags():
            anc = self._next_node()
            ops.node(anc, *ops.nodeCoord(nid))
            ops.fix(anc, 1, 1, 1, 1, 1, 1)
            el = self._next_ele()
            ops.element('zeroLength', el, anc, nid,
                        '-mat', *[mat_ghost] * 6, '-dir', 1, 2, 3, 4, 5, 6)

    def eigenvalue(self, n_modes: int = 3) -> List[float]:
        """Run eigenvalue analysis and return frequencies in Hz."""
        try:
            vals = ops.eigen(n_modes)
            return [math.sqrt(abs(v)) / (2 * math.pi) for v in vals]
        except Exception as e:
            print(f"  [Eigen WARNING] {e}")
            try:
                vals = ops.eigen('-fullGenLapack', n_modes)
                return [math.sqrt(abs(v)) / (2 * math.pi) for v in vals]
            except Exception as e2:
                print(f"  [Eigen ERROR] {e2}")
                return [0.0] * n_modes


# ==============================================================================
# 5. MAIN: SCOUR SWEEP + VALIDATION
# ==============================================================================

def power_law_drop(x, a, b):
    """f/f0 = 1 - a * (S/D)^b => drop = a * (S/D)^b"""
    return a * np.power(x, b)


def main():
    print("=" * 65)
    print("  OpenSeesPy Gen 3: Integrated Tripod BNWF Model")
    print("  Architecture: Gen 1 (SSOT tripod, stress-relief)")
    print("  Data source:  Gen 2 (CPT pipeline CSVs)")
    print("=" * 65)

    # Load data
    print(f"\n  Loading SSOT: {SSOT_FILE}")
    struct = parse_ssot(SSOT_FILE)
    print(f"    Nodes: {len(struct.nodes)}")
    print(f"    Elements: {len(struct.elements)}")
    print(f"    Lumped masses: {len(struct.lumped_masses)}")

    print(f"\n  Loading pipeline: {PIPELINE_DIR}")
    pipe = load_pipeline_data(PIPELINE_DIR)
    print(f"    Stiffness rows: {len(pipe.df_stiffness)}")
    print(f"    Capacity rows: {len(pipe.df_capacity)}")

    # Scour sweep
    print(f"\n  Scour sweep: {SCOUR_RANGE[0]:.0f}m to {SCOUR_RANGE[-1]:.0f}m")
    print(f"  {'Scour (m)':<10} {'f1 (Hz)':<12} {'f/f0':<10} {'Drop %':<10}")
    print("  " + "-" * 42)

    results = []
    base_freq = 0.0

    for i, scour in enumerate(SCOUR_RANGE):
        model = Gen3Model(struct, pipe)
        model.build(scour_depth=scour)
        freqs = model.eigenvalue(n_modes=3)
        f1 = freqs[0]

        if i == 0:
            base_freq = f1

        ratio = f1 / base_freq if base_freq > 0 else 0
        drop = (1 - ratio) * 100

        print(f"  {scour:<10.1f} {f1:<12.6f} {ratio:<10.6f} {drop:<10.2f}")
        results.append({
            'scour_m': scour,
            'S_D': scour / BUCKET_DIAMETER,
            'f1_Hz': f1,
            'f_f0': ratio,
            'drop_pct': drop,
        })

    # Power-law fit
    df = pd.DataFrame(results)
    valid = df['S_D'] > 0
    drops = df.loc[valid, 'drop_pct'].values / 100
    sd = df.loc[valid, 'S_D'].values

    try:
        popt, _ = curve_fit(power_law_drop, sd, drops, p0=[0.1, 1.5])
        a_fit, b_fit = popt
        print(f"\n  Power law: f/f0 = 1 - {a_fit:.4f} * (S/D)^{b_fit:.4f}")
    except Exception:
        a_fit, b_fit = 0, 0
        print("\n  Power law fit failed.")

    # Centrifuge benchmark
    if a_fit > 0:
        pred_drop = a_fit * BENCHMARK_SCOUR_NORM ** b_fit
        print(f"\n  --- Centrifuge Validation ---")
        print(f"  Benchmark (0.6D): 5.3% drop")
        print(f"  Gen 3 prediction: {pred_drop*100:.1f}% drop")
        print(f"  Error: {abs(pred_drop - BENCHMARK_FREQ_DROP)/BENCHMARK_FREQ_DROP*100:.1f}%")

    # Field comparison
    field_f0 = 0.2436  # Hz from MSSP paper
    print(f"\n  --- Field Comparison ---")
    print(f"  Gen 3 baseline: {base_freq:.4f} Hz")
    print(f"  Field measured:  {field_f0:.4f} Hz")
    print(f"  Error: {abs(base_freq - field_f0)/field_f0*100:.1f}%")

    # Summary
    print(f"\n{'='*65}")
    print(f"  SUMMARY")
    print(f"{'='*65}")
    print(f"  Baseline f1:        {base_freq:.4f} Hz ({abs(base_freq-field_f0)/field_f0*100:.1f}% vs field)")
    print(f"  Max drop (S=5m):    {df.iloc[-1]['drop_pct']:.2f}%")
    if a_fit > 0:
        print(f"  Power law:          f/f0 = 1 - {a_fit:.4f}*(S/D)^{b_fit:.2f}")
        print(f"  Centrifuge match:   {pred_drop*100:.1f}% vs 5.3% benchmark")
    print(f"  Architecture:       Tripod (3 buckets x {NUM_RIBS} ribs)")
    print(f"  Data source:        CPT pipeline (no Excel)")
    print(f"{'='*65}")

    # Save results
    out_dir = Path(__file__).parent
    df.to_csv(out_dir / 'gen3_scour_results.csv', index=False)
    print(f"\n  Saved: gen3_scour_results.csv")

    # Plot
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5))

    ax1.plot(df['S_D'], df['f1_Hz'], 'bo-', lw=2, label='Gen 3')
    ax1.axhline(y=field_f0, color='red', ls='--', label=f'Field f0={field_f0:.4f} Hz')
    ax1.set_xlabel('S/D')
    ax1.set_ylabel('f1 (Hz)')
    ax1.set_title('Gen 3: Natural frequency vs scour')
    ax1.legend()
    ax1.grid(True, alpha=0.3)

    ax2.plot(df['S_D'], df['f_f0'], 'bo-', lw=2, label='Gen 3')
    ax2.plot(BENCHMARK_SCOUR_NORM, 1 - BENCHMARK_FREQ_DROP, 'r*',
             ms=15, label='Centrifuge (0.6D)')
    if a_fit > 0:
        x_fit = np.linspace(0, 0.7, 50)
        y_fit = 1 - a_fit * np.power(x_fit, b_fit)
        ax2.plot(x_fit, y_fit, 'g--',
                 label=f'Fit: 1-{a_fit:.3f}(S/D)$^{{{b_fit:.2f}}}$')
    ax2.set_xlabel('S/D')
    ax2.set_ylabel('f/f0')
    ax2.set_title('Gen 3: Scour sensitivity validation')
    ax2.legend()
    ax2.grid(True, alpha=0.3)

    plt.tight_layout()
    plt.savefig(out_dir / 'gen3_validation.png', dpi=150, bbox_inches='tight')
    print(f"  Saved: gen3_validation.png")


if __name__ == '__main__':
    main()
