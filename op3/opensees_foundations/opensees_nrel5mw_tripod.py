"""
OpenSeesPy Model for NREL 5MW OC3 Tripod
==========================================
Builds the same structure as SubDyn in OpenFAST, for comparison.

Purpose:
  1. Validate: OpenSeesPy eigenvalue vs OpenFAST eigenvalue
  2. Framework: prove OpenSeesPy can model any tripod (not just Gunsan)
  3. Compare: NREL 5MW fixed base vs Gunsan 4.2MW with SSI springs

Structure from: NRELOffshrBsline5MW_OC3Tripod_SubDyn.dat
  - 158 joints
  - 163 beam members
  - 3 base piles at z=-45m
  - Interface at z=+10m (tower connection)
  - Circular beam cross-sections: D=6m piles, D=1.2m legs, etc.

Tower + RNA from: ElastoDyn
  - Tower: hub height 90m, D~3.87-6.0m
  - RNA mass: 350,000 kg (approximate)
"""
import openseespy.opensees as ops
import numpy as np
import math
import sys

sys.stdout.reconfigure(encoding='utf-8')

print("=" * 65)
print("  NREL 5MW OC3 Tripod — OpenSeesPy Model")
print("=" * 65)

# ═══════════════════════════════════════════════════════════════════
# PARSE SUBDYN FILE
# ═══════════════════════════════════════════════════════════════════

subdyn_file = r"C:\Users\geolab\.claude\projects\f--TREE-OF-THOUGHT\8cda8629-6ce6-4bb7-a003-4536885cb5af\tool-results\b3qlt63o3.txt"

joints = {}  # {id: (x, y, z)}
members = []  # [{id, j1, j2, prop1, prop2, mtype}]
props = {}   # {id: {E, G, rho, D, t}}
react_joints = []
interf_joints = []

section = None
with open(subdyn_file, 'r', encoding='utf-8') as f:
    for line in f:
        l = line.strip()
        if not l or l.startswith('---') or l.startswith('('):
            continue

        if 'STRUCTURE JOINTS' in l:
            section = 'joints'; continue
        elif 'BASE REACTION' in l:
            section = 'react'; continue
        elif 'INTERFACE JOINTS' in l:
            section = 'interf'; continue
        elif 'MEMBERS ---' in l:
            section = 'members'; continue
        elif 'CIRCULAR BEAM' in l:
            section = 'props'; continue
        elif 'RECTANGULAR' in l or 'ARBITRARY' in l or 'CABLE' in l or 'RIGID' in l or 'SPRING' in l:
            section = None; continue
        elif 'COSINE' in l or 'CONCENTRATED' in l or 'OUTPUT' in l:
            section = None; continue

        parts = l.split()
        if not parts or not parts[0].replace('-', '').replace('.', '').isdigit():
            continue

        try:
            if section == 'joints' and len(parts) >= 5:
                jid = int(parts[0])
                joints[jid] = (float(parts[1]), float(parts[2]), float(parts[3]))

            elif section == 'react' and len(parts) >= 7:
                react_joints.append(int(parts[0]))

            elif section == 'interf' and len(parts) >= 7:
                interf_joints.append(int(parts[0]))

            elif section == 'members' and len(parts) >= 6:
                members.append({
                    'id': int(parts[0]), 'j1': int(parts[1]), 'j2': int(parts[2]),
                    'p1': int(parts[3]), 'p2': int(parts[4]),
                    'mtype': parts[5] if len(parts) > 5 else '1c'
                })

            elif section == 'props' and len(parts) >= 6:
                props[int(parts[0])] = {
                    'E': float(parts[1]), 'G': float(parts[2]),
                    'rho': float(parts[3]), 'D': float(parts[4]), 't': float(parts[5])
                }
        except (ValueError, IndexError):
            continue

print(f"  Parsed: {len(joints)} joints, {len(members)} members, {len(props)} prop sets")
print(f"  Base reactions: joints {react_joints}")
print(f"  Interface: joints {interf_joints}")
print(f"  Properties:")
for pid, p in props.items():
    print(f"    Set {pid}: D={p['D']:.3f}m, t={p['t']:.3f}m, rho={p['rho']:.0f}")

# ═══════════════════════════════════════════════════════════════════
# BUILD OPENSEESPY MODEL
# ═══════════════════════════════════════════════════════════════════

print(f"\n  Building OpenSeesPy model...")

ops.wipe()
ops.model('basic', '-ndm', 3, '-ndf', 6)

# Create all SubDyn joints
for jid, (x, y, z) in joints.items():
    ops.node(jid, x, y, z)

# Fix base reaction joints
for rj in react_joints:
    ops.fix(rj, 1, 1, 1, 1, 1, 1)

# Create beam elements
transf_id = 1
elem_count = 0

for mem in members:
    j1, j2 = mem['j1'], mem['j2']
    pid = mem['p1']

    if j1 not in joints or j2 not in joints:
        continue
    if pid not in props:
        # Use default property set 1
        pid = 1
        if pid not in props:
            continue

    p = props[pid]
    c1, c2 = joints[j1], joints[j2]
    dx, dy, dz = c2[0]-c1[0], c2[1]-c1[1], c2[2]-c1[2]
    L = math.sqrt(dx**2 + dy**2 + dz**2)

    if L < 0.01:
        continue

    # Geometric transformation
    if abs(dz) / L > 0.99:
        ops.geomTransf('Linear', transf_id, 1, 0, 0)
    else:
        ops.geomTransf('Linear', transf_id, 0, 0, 1)

    # Section properties
    D, t = p['D'], p['t']
    Di = D - 2 * t
    A = math.pi / 4 * (D**2 - Di**2)
    I = math.pi / 64 * (D**4 - Di**4)
    J = 2 * I

    # Element
    ops.element('elasticBeamColumn', mem['id'] + 10000, j1, j2,
                A, p['E'], p['G'], J, I, I, transf_id,
                '-mass', A * p['rho'])

    transf_id += 1
    elem_count += 1

print(f"  Created {elem_count} beam elements")

# ═══════════════════════════════════════════════════════════════════
# ADD TOWER + RNA (simplified, from ElastoDyn specs)
# ═══════════════════════════════════════════════════════════════════

# Tower from interface (z=10m) to hub (z=87.6m)
# NREL 5MW tower: D_base=6.0m, D_top=3.87m, t=0.019-0.027m
# Simplified: 10 uniform segments

tower_base_z = 10.0
tower_top_z = 87.6
n_tower = 10
tower_dz = (tower_top_z - tower_base_z) / n_tower

D_tower_base = 6.0
D_tower_top = 3.87
t_tower = 0.027
E_steel = 2.1e11
G_steel = 8.1e10
rho_tower = 8500.0  # includes paint, flanges, etc.

# Interface joint (52) is at z=10.0
tower_nodes = [52]  # start from interface joint
next_nid = 1000

for i in range(1, n_tower + 1):
    z = tower_base_z + i * tower_dz
    nid = next_nid + i
    ops.node(nid, 0.0, 0.0, z)
    tower_nodes.append(nid)

# Tower elements
for i in range(len(tower_nodes) - 1):
    n1, n2 = tower_nodes[i], tower_nodes[i + 1]
    frac = i / n_tower
    D = D_tower_base + frac * (D_tower_top - D_tower_base)
    Di = D - 2 * t_tower
    A = math.pi / 4 * (D**2 - Di**2)
    I = math.pi / 64 * (D**4 - Di**4)
    J = 2 * I

    tid = transf_id; transf_id += 1
    ops.geomTransf('Linear', tid, 1, 0, 0)
    eid = 20000 + i
    ops.element('elasticBeamColumn', eid, n1, n2,
                A, E_steel, G_steel, J, I, I, tid,
                '-mass', A * rho_tower)

# RNA mass at top
hub_node = tower_nodes[-1]
RNA_mass = 350000.0  # kg (approximate for NREL 5MW)
ops.mass(hub_node, RNA_mass, RNA_mass, RNA_mass, 0, 0, 0)

print(f"  Tower: {n_tower} elements, hub at z={tower_top_z}m")
print(f"  RNA mass: {RNA_mass:.0f} kg at node {hub_node}")
print(f"  Total nodes: {len(ops.getNodeTags())}")

# ═══════════════════════════════════════════════════════════════════
# EIGENVALUE ANALYSIS
# ═══════════════════════════════════════════════════════════════════

print(f"\n  Running eigenvalue analysis...")

try:
    n_modes = 6
    vals = ops.eigen(n_modes)
    freqs = [math.sqrt(abs(v)) / (2 * math.pi) for v in vals]

    print(f"\n  === NREL 5MW OC3 TRIPOD NATURAL FREQUENCIES ===")
    print(f"  {'Mode':<6} {'Freq (Hz)':<12} {'Period (s)':<12}")
    print(f"  " + "-" * 30)
    for i, f in enumerate(freqs):
        T = 1 / f if f > 0 else 0
        label = ""
        if i == 0: label = " ← 1st FA"
        elif i == 1: label = " ← 1st SS"
        elif i == 2: label = " ← 2nd"
        print(f"  {i+1:<6} {f:<12.4f} {T:<12.2f}{label}")

except Exception as e:
    print(f"  Eigenvalue failed: {e}")
    # Try fullGenLapack
    try:
        vals = ops.eigen('-fullGenLapack', 6)
        freqs = [math.sqrt(abs(v)) / (2 * math.pi) for v in vals]
        print(f"  fullGenLapack results:")
        for i, f in enumerate(freqs):
            print(f"    Mode {i+1}: {f:.4f} Hz")
    except Exception as e2:
        print(f"  fullGenLapack also failed: {e2}")
        freqs = [0] * 6

# ═══════════════════════════════════════════════════════════════════
# COMPARISON WITH OPENFAST AND GUNSAN
# ═══════════════════════════════════════════════════════════════════

print(f"\n{'='*65}")
print(f"  COMPARISON")
print(f"{'='*65}")

# NREL 5MW reference frequency (from literature)
# OC3 Phase II: f1 ≈ 0.312 Hz (fore-aft), f2 ≈ 0.312 Hz (side-side)
f1_ref = 0.312  # Hz (from OC3 Phase II report)

print(f"  NREL 5MW OC3 Tripod:")
print(f"    OpenSeesPy f1:    {freqs[0]:.4f} Hz")
print(f"    Reference (OC3):  {f1_ref:.4f} Hz")
if freqs[0] > 0:
    print(f"    Error:            {abs(freqs[0] - f1_ref) / f1_ref * 100:.1f}%")

print(f"\n  Gunsan 4.2MW (v4 dissipation):")
print(f"    OpenSeesPy f1:    0.2367 Hz")
print(f"    Field measured:   0.2436 Hz")
print(f"    Error:            2.8%")

print(f"\n  Key differences:")
print(f"    NREL: fixed base at z=-45m (no soil flexibility)")
print(f"    Gunsan: BNWF springs from OptumGX (real SSI)")
print(f"    NREL: 158 SubDyn joints + tower")
print(f"    Gunsan: 52 structural + 216 spring nodes")

print(f"\n  Both models built in OpenSeesPy.")
print(f"  The Gunsan model adds soil-structure interaction")
print(f"  that the NREL reference completely lacks.")
print(f"{'='*65}")
