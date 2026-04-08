"""
Op^3 OpenSeesPy model builder.

Implements the four foundation modes as OpenSeesPy element patterns
that all share a common tower-base interface. The public entry points
are called by the composer and cross-compare utilities; a user should
not need to call anything in this module directly.

Tag allocation convention (avoids collisions across rebuilds):

    1..999     reserved for tower element nodes
    1000..1099 tower base node (1000) + tower element tags (1001..1099)
    1100..1199 foundation interface nodes (6x6 Mode, BNWF anchor)
    1200..1999 BNWF spring soil nodes (Modes C, D)
    2000..2999 BNWF zero-length elements
    3000..3099 rotor-nacelle-assembly mass node
    9000..9999 temporary / analysis-only tags
"""
from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from op3.composer import TowerModel
    from op3.foundations import Foundation


# ============================================================
# Tower templates (simplified — one stick model per turbine)
# ============================================================

from pathlib import Path as _Path

_REPO_ROOT = _Path(__file__).resolve().parents[2]


def _ed(rel: str) -> str | None:
    p = _REPO_ROOT / rel
    return str(p) if p.exists() else None


# Optional NREL ElastoDyn deck per template. Each value is either a
# string (path to main ED file; tower properties auto-resolved via
# TwrFile) or a tuple (main_ed, tower_dat_override) when a template
# needs a different tower file from the main deck. RNA mass + inertia
# are always parsed from the main ED.
TOWER_ELASTODYN: dict = {
    # Onshore land-based 5 MW: reuse the OC3 main ED for RNA but point
    # at the canonical NRELOffshrBsline5MW_Onshore_ElastoDyn_Tower.dat
    # so example 01 reproduces the published 0.324 Hz fixed-base mode.
    "nrel_5mw_tower": (
        _ed("nrel_reference/openfast_rtest/5MW_OC3Mnpl_DLL_WTurb_WavesIrr/"
            "NRELOffshrBsline5MW_OC3Monopile_ElastoDyn.dat"),
        _ed("nrel_reference/openfast_rtest/5MW_Baseline/"
            "NRELOffshrBsline5MW_Onshore_ElastoDyn_Tower.dat"),
    ),
    # OC3 monopile reuses its own (lighter, less stiff) tower file.
    "nrel_5mw_oc3_tower": _ed(
        "nrel_reference/openfast_rtest/5MW_OC3Mnpl_DLL_WTurb_WavesIrr/"
        "NRELOffshrBsline5MW_OC3Monopile_ElastoDyn.dat"
    ),
    "iea_15mw_tower": _ed(
        "nrel_reference/iea_15mw/OpenFAST_monopile/"
        "IEA-15-240-RWT-Monopile_ElastoDyn.dat"
    ),
}


def _resolve_ed(template_name: str) -> tuple[str | None, str | None]:
    """Return (main_ed, tower_override) for a template name."""
    entry = TOWER_ELASTODYN.get(template_name)
    if entry is None:
        return None, None
    if isinstance(entry, tuple):
        return entry[0], entry[1]
    return entry, None


TOWER_TEMPLATES = {
    "nrel_5mw_tower": {
        "base_elev_m": 10.0,      # above mudline for OC3 monopile
        "hub_height_m": 90.0,
        "base_diameter_m": 6.0,
        "top_diameter_m": 3.87,
        "base_thickness_m": 0.027,
        "top_thickness_m": 0.019,
        "E_Pa": 2.1e11,
        "G_Pa": 8.1e10,
        "density_kg_m3": 8500.0,  # effective density incl. stiffeners
        "n_elements": 11,
    },
    "nrel_5mw_oc3_tower": {
        "base_elev_m": 10.0,
        "hub_height_m": 90.0,
        "base_diameter_m": 6.0,
        "top_diameter_m": 3.87,
        "base_thickness_m": 0.027,
        "top_thickness_m": 0.019,
        "E_Pa": 2.1e11,
        "G_Pa": 8.1e10,
        "density_kg_m3": 8500.0,
        "n_elements": 11,
    },
    "iea_15mw_tower": {
        "base_elev_m": 15.0,      # above mudline for monopile
        "hub_height_m": 150.0,
        "base_diameter_m": 10.0,
        "top_diameter_m": 6.5,
        "base_thickness_m": 0.041,
        "top_thickness_m": 0.021,
        "E_Pa": 2.0e11,
        "G_Pa": 7.9e10,
        "density_kg_m3": 8500.0,
        "n_elements": 15,
    },
    "gunsan_u136_tower": {
        "base_elev_m": 23.6,      # mudline to tower interface
        "hub_height_m": 96.3,
        "base_diameter_m": 4.2,
        "top_diameter_m": 3.5,
        "base_thickness_m": 0.020,
        "top_thickness_m": 0.020,
        "E_Pa": 2.1e11,
        "G_Pa": 8.1e10,
        "density_kg_m3": 8500.0,
        "n_elements": 12,
    },
    "iea_land_onshore_tower": {
        "base_elev_m": 0.0,
        "hub_height_m": 120.0,
        "base_diameter_m": 6.5,
        "top_diameter_m": 3.5,
        "base_thickness_m": 0.030,
        "top_thickness_m": 0.018,
        "E_Pa": 2.1e11,
        "G_Pa": 8.1e10,
        "density_kg_m3": 8500.0,
        "n_elements": 10,
    },
}


ROTOR_MASS_KG = {
    "nrel_5mw_baseline":   314_520.0,   # RNA mass
    "iea_15mw_rwt":        1_017_000.0,
    "unison_u136":         338_000.0,
    "nrel_1.72_103":       84_000.0,
    "nrel_2.8_127":        165_000.0,
    "vestas_v27":          10_000.0,
}


# ============================================================
# Main entry points
# ============================================================

def build_opensees_model(tower_model: "TowerModel") -> None:
    """Build the OpenSeesPy domain for a TowerModel.

    This function is called by TowerModel.build(). It wipes the current
    OpenSees domain, instantiates the tower stick model, attaches the
    foundation according to the chosen mode, and places the RNA mass
    at the hub node.
    """
    import openseespy.opensees as ops

    ops.wipe()
    ops.model("basic", "-ndm", 3, "-ndf", 6)

    tpl = TOWER_TEMPLATES.get(tower_model.tower_name)
    if tpl is None:
        raise ValueError(f"Unknown tower template: {tower_model.tower_name}")

    # Build tower stick nodes + elements
    base_node = 1000
    ed_main, ed_tower = _resolve_ed(tower_model.tower_name)
    if ed_main:
        hub_node = _build_tower_stick_from_elastodyn(
            ops, ed_main, base_node,
            n_segments=int(tpl.get("n_elements", 20)),
            ed_tower=ed_tower,
        )
    else:
        hub_node = _build_tower_stick(ops, tpl, base_node)

    # Attach foundation
    diag = attach_foundation(tower_model.foundation, base_node)
    if isinstance(diag, dict):
        tower_model.foundation.diagnostics.update(diag)

    # Place RNA mass + inertia at hub node. Prefer ElastoDyn-parsed
    # values when available; fall back to ROTOR_MASS_KG dict otherwise.
    if ed_main:
        from op3.opensees_foundations.tower_loader import load_elastodyn_rna
        rna = load_elastodyn_rna(ed_main)
        m_total = rna.total_rna_mass_kg
        I_x = 0.5 * (rna.hub_iner_kgm2 + rna.nac_yiner_kgm2)
        I_y = rna.hub_iner_kgm2
        I_z = rna.nac_yiner_kgm2

        # Rigid offset from tower top to nacelle CM:
        #   dx = NacCMxn (downwind), dy = 0, dz = Twr2Shft + NacCMzn
        # The eccentric mass is what raises NREL 5MW from 0.30 -> 0.32 Hz.
        dx = rna.nac_cm_xn_m
        dz = rna.twr2shft_m + rna.nac_cm_zn_m
        if abs(dx) + abs(dz) > 1e-6:
            # Place a CM node and rigid-link it to the tower top
            tower_top_xyz = ops.nodeCoord(hub_node)
            cm_tag = 3001
            ops.node(
                cm_tag,
                float(tower_top_xyz[0] + dx),
                float(tower_top_xyz[1]),
                float(tower_top_xyz[2] + dz),
            )
            # rigidLink "beam" enslaves all 6 DOF of cm_tag to hub_node
            ops.rigidLink("beam", hub_node, cm_tag)
            ops.mass(cm_tag, m_total, m_total, m_total, I_x, I_y, I_z)
        else:
            ops.mass(hub_node, m_total, m_total, m_total, I_x, I_y, I_z)
    else:
        rna_mass = ROTOR_MASS_KG.get(tower_model.rotor_name, 300_000.0)
        ops.mass(hub_node, rna_mass, rna_mass, rna_mass,
                 rna_mass * 10.0, rna_mass * 10.0, rna_mass * 10.0)


def _build_tower_stick_from_elastodyn(
    ops, ed_path: str, base_node: int, n_segments: int = 20,
    ed_tower: str | None = None,
) -> int:
    """
    Build a tower stick using byte-identical distributed properties
    parsed from an OpenFAST ElastoDyn deck. Each element receives
    EI and mass-per-length interpolated from the NREL station table.

    Convention: E is fixed at 2.1e11 Pa and I = EI/E is back-calculated
    so that bending modes match NREL exactly. Cross-sectional area is
    set to ``mass_kg_m / 7850`` so that ``rho * A`` reproduces the
    distributed mass when ``rho = 7850``. Axial and torsional modes
    are not the target of this calibration.
    """
    from op3.opensees_foundations.tower_loader import (
        load_elastodyn_tower, discretise,
    )

    tpl = load_elastodyn_tower(ed_path, ed_tower=ed_tower)
    elements = discretise(tpl, n_segments=n_segments)

    E_REF = 2.1e11
    G_REF = 8.1e10
    RHO_STEEL = 7850.0

    # Nodes
    n_nodes = len(elements) + 1
    z_first = elements[0]["z_bot"]
    ops.node(base_node, 0.0, 0.0, float(z_first))
    for i, el in enumerate(elements):
        tag = base_node + i + 1
        ops.node(tag, 0.0, 0.0, float(el["z_top"]))

    transf_tag = 1
    ops.geomTransf("Linear", transf_tag, 0.0, 1.0, 0.0)

    for i, el in enumerate(elements):
        m_kg_m = el["mass_kg_m"]
        EI_fa = el["EI_fa_Nm2"]
        EI_ss = el["EI_ss_Nm2"]
        Iy = EI_fa / E_REF
        Iz = EI_ss / E_REF
        A = max(m_kg_m / RHO_STEEL, 1.0e-6)
        Jx = Iy + Iz

        ops.element(
            "elasticBeamColumn",
            1000 + i + 1,
            base_node + i, base_node + i + 1,
            A, E_REF, G_REF, Jx, Iy, Iz,
            transf_tag,
            "-mass", m_kg_m,
        )

    return base_node + n_nodes - 1


def _build_tower_stick(ops, tpl: dict, base_node: int) -> int:
    """Create the tower stick-model nodes and elements. Returns the hub node tag."""
    import math

    n_el = tpl["n_elements"]
    base_z = tpl["base_elev_m"]
    hub_z = tpl["hub_height_m"]
    D_base = tpl["base_diameter_m"]
    D_top = tpl["top_diameter_m"]
    t_base = tpl["base_thickness_m"]
    t_top = tpl["top_thickness_m"]
    E = tpl["E_Pa"]
    G = tpl["G_Pa"]
    rho = tpl["density_kg_m3"]

    # Linear taper in diameter and thickness
    zs = np.linspace(base_z, hub_z, n_el + 1)
    Ds = np.linspace(D_base, D_top, n_el + 1)
    ts = np.linspace(t_base, t_top, n_el + 1)

    # Create nodes
    for i, z in enumerate(zs):
        tag = base_node + i
        ops.node(tag, 0.0, 0.0, float(z))

    # Geometric transformation
    transf_tag = 1
    ops.geomTransf("Linear", transf_tag, 0.0, 1.0, 0.0)

    # Create elements with average cross-section properties
    for i in range(n_el):
        D_avg = 0.5 * (Ds[i] + Ds[i + 1])
        t_avg = 0.5 * (ts[i] + ts[i + 1])
        R_o = 0.5 * D_avg
        R_i = R_o - t_avg
        A = math.pi * (R_o * R_o - R_i * R_i)
        Iy = math.pi * (R_o ** 4 - R_i ** 4) / 4
        Iz = Iy
        Jx = Iy + Iz

        node_i = base_node + i
        node_j = base_node + i + 1
        ele_tag = 1000 + i + 1
        ops.element(
            "elasticBeamColumn",
            ele_tag, node_i, node_j,
            A, E, G, Jx, Iy, Iz,
            transf_tag,
            "-mass", rho * A,
        )

    return base_node + n_el


# ============================================================
# Foundation mode dispatch
# ============================================================

def attach_foundation(foundation: "Foundation", base_node: int) -> dict:
    """Attach a foundation to the OpenSees domain at the given base node."""
    from op3.foundations import FoundationMode, apply_scour_relief
    import openseespy.opensees as ops

    diagnostics = {"mode": foundation.mode.value, "base_node": base_node}

    if foundation.mode == FoundationMode.FIXED:
        ops.fix(base_node, 1, 1, 1, 1, 1, 1)
        diagnostics["description"] = "fixed base (all 6 DOF constrained)"
        return diagnostics

    if foundation.mode == FoundationMode.STIFFNESS_6X6:
        K = foundation.stiffness_matrix
        diagnostics.update(_attach_stiffness_6x6(ops, K, base_node))
        return diagnostics

    if foundation.mode == FoundationMode.DISTRIBUTED_BNWF:
        df = apply_scour_relief(foundation.spring_table, foundation.scour_depth)
        diagnostics.update(_attach_distributed_bnwf(ops, df, base_node))
        return diagnostics

    if foundation.mode == FoundationMode.DISSIPATION_WEIGHTED:
        df = apply_scour_relief(foundation.spring_table, foundation.scour_depth)
        # Apply dissipation weights w(z) to stiffness and capacity per
        # the Mode D formulation in docs/MODE_D_DISSIPATION_WEIGHTED.md:
        #     w(D) = beta + (1 - beta) * (1 - D / D_max) ** alpha
        # If the dissipation_weights table already contains a 'w_z'
        # column, that takes precedence (back-compat). Otherwise the
        # weights are computed from a 'D_total_kJ' column using the
        # foundation's alpha / beta parameters.
        if foundation.dissipation_weights is not None:
            w = foundation.dissipation_weights.copy()
            if "w_z" not in w.columns:
                if "D_total_kJ" not in w.columns:
                    raise ValueError(
                        "Mode D requires either 'w_z' or 'D_total_kJ' column "
                        "in dissipation_weights")
                D = w["D_total_kJ"].values.astype(float)
                D_max = float(np.max(D)) if D.size else 0.0
                alpha = float(foundation.mode_d_alpha)
                beta = float(foundation.mode_d_beta)
                if D_max > 0:
                    w_z = beta + (1.0 - beta) * np.power(
                        np.clip(1.0 - D / D_max, 0.0, 1.0), alpha)
                else:
                    w_z = np.ones_like(D)
                w["w_z"] = w_z
            df = df.merge(w[["depth_m", "w_z"]], on="depth_m", how="left")
            df["w_z"] = df["w_z"].fillna(1.0)
            for col in ("k_ini_kN_per_m", "p_ult_kN_per_m"):
                if col in df.columns:
                    df[col] = df[col].values * df["w_z"].values
            diagnostics["mode_d_alpha"] = float(foundation.mode_d_alpha)
            diagnostics["mode_d_beta"] = float(foundation.mode_d_beta)
            diagnostics["mode_d_w_min"] = float(df["w_z"].min())
            diagnostics["mode_d_w_max"] = float(df["w_z"].max())
            df = df.drop(columns=["w_z"])
        diagnostics.update(_attach_distributed_bnwf(ops, df, base_node))
        diagnostics["description"] = "dissipation-weighted generalized BNWF"
        return diagnostics

    raise ValueError(f"Unknown foundation mode: {foundation.mode}")


# ============================================================
# Mode-specific builders
# ============================================================

def _attach_stiffness_6x6(ops, K: np.ndarray, base_node: int) -> dict:
    """Mode B: attach a single 6x6 zero-length element at the tower base."""
    ground_node = 1100
    ops.node(ground_node, 0.0, 0.0, 0.0)
    ops.fix(ground_node, 1, 1, 1, 1, 1, 1)

    # OpenSees doesn't directly accept a full 6x6; decompose into six
    # uniaxial materials for the diagonal terms. (For full off-diagonal
    # coupling, use zeroLengthCoupled or zeroLengthND which is an
    # extension we skip in this simplified baseline.)
    mat_tags = []
    for i in range(6):
        mat_tag = 100 + i
        k_diag = max(abs(float(K[i, i])), 1e3)
        ops.uniaxialMaterial("Elastic", mat_tag, k_diag)
        mat_tags.append(mat_tag)

    ele_tag = 2000
    ops.element("zeroLength", ele_tag, ground_node, base_node,
                "-mat", *mat_tags, "-dir", 1, 2, 3, 4, 5, 6)

    return {
        "description": "6x6 lumped stiffness (diagonal approximation)",
        "k_trace_kN_per_m": float(np.trace(K[:3, :3])),
        "k_rot_trace_kN_m_per_rad": float(np.trace(K[3:, 3:])),
    }


def _attach_distributed_bnwf(ops, spring_table, base_node: int) -> dict:
    """Mode C: build distributed p-y / t-z springs along the bucket skirt."""
    import pandas as pd

    if not isinstance(spring_table, pd.DataFrame):
        raise TypeError("spring_table must be a pandas DataFrame")
    if "depth_m" not in spring_table.columns or "k_ini_kN_per_m" not in spring_table.columns:
        raise ValueError(
            "spring_table missing required columns 'depth_m' and 'k_ini_kN_per_m'. "
            f"Got: {list(spring_table.columns)}"
        )

    # Foundation anchor node at mudline
    anchor = 1100
    # Check if node already exists
    ops.node(anchor, 0.0, 0.0, 0.0)
    ops.fix(anchor, 1, 1, 1, 1, 1, 1)

    # Couple the tower base to the anchor with a rigid link? No —
    # that would bypass the springs. Instead we couple with a
    # lumped equivalent spring computed from the depth integrals:

    total_kx = float(spring_table["k_ini_kN_per_m"].sum() * 1e3)   # kN/m -> N/m
    total_kz = total_kx * 3.0  # rough vertical-to-lateral ratio
    # Rotational: integrate k(z) * z^2 over depth
    depth_arr = spring_table["depth_m"].values
    k_arr = spring_table["k_ini_kN_per_m"].values * 1e3
    k_rot = float(np.sum(k_arr * depth_arr * depth_arr))

    mat_tags = [110, 111, 112, 113, 114, 115]
    diag_k = [total_kx, total_kx, total_kz, k_rot, k_rot, k_rot * 0.5]
    for t, k in zip(mat_tags, diag_k):
        ops.uniaxialMaterial("Elastic", t, max(k, 1e3))

    ele_tag = 2001
    ops.element("zeroLength", ele_tag, anchor, base_node,
                "-mat", *mat_tags, "-dir", 1, 2, 3, 4, 5, 6)

    return {
        "description": "distributed BNWF (static-equivalent 6-DOF zero-length)",
        "n_springs": int(len(spring_table)),
        "integrated_lateral_kN_per_m": float(total_kx / 1e3),
        "integrated_rotational_kN_m_per_rad": float(k_rot / 1e3),
    }


# ============================================================
# Analysis entry points
# ============================================================

def run_eigen_analysis(tower_model: "TowerModel", n_modes: int = 6) -> np.ndarray:
    """Run eigenvalue analysis and return natural frequencies in Hz."""
    import openseespy.opensees as ops

    # Use frequency eigenvalue solver
    omega2 = ops.eigen("-frequency", int(n_modes))
    omega2 = np.array(omega2)
    # Guard against negative or zero eigenvalues from spurious modes
    omega2 = np.where(omega2 > 0, omega2, np.nan)
    freqs = np.sqrt(omega2) / (2 * np.pi)
    return freqs


def run_pushover_analysis(tower_model: "TowerModel",
                          target_disp_m: float = 1.0,
                          n_steps: int = 50,
                          load_node: int | None = None) -> dict:
    """Run a static lateral pushover at the hub node and return the
    force-displacement curve.

    Returns a dict with keys 'displacement_m' and 'reaction_kN'.
    """
    import openseespy.opensees as ops

    # Identify the hub node (top of the tower stick)
    if load_node is None:
        # By convention the tower base is 1000 and the hub is 1000 + n_elements
        load_node = 1000 + 12   # safe upper bound, will be checked

    # Find the highest existing tower node
    max_node = 1000
    for tag in range(1000, 1100):
        try:
            ops.nodeCoord(tag)
            max_node = tag
        except Exception:
            break
    load_node = max_node

    # Apply a horizontal load pattern
    pattern_tag = 9100
    ts_tag = 9100
    try:
        ops.timeSeries("Linear", ts_tag)
        ops.pattern("Plain", pattern_tag, ts_tag)
        ops.load(load_node, 1.0, 0.0, 0.0, 0.0, 0.0, 0.0)

        # Static analysis with displacement control
        ops.constraints("Transformation")
        ops.numberer("RCM")
        ops.system("UmfPack")
        ops.test("NormDispIncr", 1e-6, 50, 0)
        ops.algorithm("Newton")
        d_step = target_disp_m / n_steps
        ops.integrator("DisplacementControl", load_node, 1, d_step)
        ops.analysis("Static")

        disps = []
        reacts = []
        for _ in range(n_steps):
            ok = ops.analyze(1)
            if ok != 0:
                break
            disps.append(float(ops.nodeDisp(load_node, 1)))
            try:
                reacts.append(float(ops.getLoadFactor(pattern_tag)))
            except Exception:
                reacts.append(np.nan)

        ops.remove("loadPattern", pattern_tag)
    except Exception as e:
        return {"displacement_m": [], "reaction_kN": [], "error": str(e)}

    return {
        "displacement_m": disps,
        "reaction_kN": reacts,
        "load_node": load_node,
    }


def run_transient_analysis(tower_model: "TowerModel",
                           duration_s: float = 10.0,
                           dt_s: float = 0.01,
                           damping_ratio: float = 0.01) -> dict:
    """Run a free vibration transient with an initial hub-node displacement.

    Returns a dict with 'time_s' and 'hub_disp_m' arrays.
    """
    import openseespy.opensees as ops

    # Find hub node (highest tower node tag)
    hub_node = 1000
    for tag in range(1000, 1100):
        try:
            ops.nodeCoord(tag)
            hub_node = tag
        except Exception:
            break

    try:
        # Apply initial displacement via a brief ramped pulse, then release
        ts_tag = 9200
        pat_tag = 9200
        ops.timeSeries("Linear", ts_tag)
        ops.pattern("Plain", pat_tag, ts_tag)
        ops.load(hub_node, 1e6, 0.0, 0.0, 0.0, 0.0, 0.0)

        # Rayleigh damping based on first eigenvalue
        try:
            omega2 = ops.eigen(1)
            omega = float(np.sqrt(max(omega2[0], 1e-6)))
            alphaM = 2 * damping_ratio * omega
            betaK = 0.0
            ops.rayleigh(alphaM, betaK, 0.0, 0.0)
        except Exception:
            pass

        ops.constraints("Transformation")
        ops.numberer("RCM")
        ops.system("UmfPack")
        ops.test("NormDispIncr", 1e-6, 50, 0)
        ops.algorithm("Newton")
        ops.integrator("Newmark", 0.5, 0.25)
        ops.analysis("Transient")

        n_steps = int(duration_s / dt_s)
        times = []
        disps = []
        for i in range(n_steps):
            ok = ops.analyze(1, dt_s)
            if ok != 0:
                break
            times.append(i * dt_s)
            disps.append(float(ops.nodeDisp(hub_node, 1)))

        ops.remove("loadPattern", pat_tag)
    except Exception as e:
        return {"time_s": [], "hub_disp_m": [], "error": str(e)}

    return {
        "time_s": times,
        "hub_disp_m": disps,
        "hub_node": hub_node,
    }


def run_static_condensation(tower_model: "TowerModel") -> np.ndarray:
    """Extract the 6x6 stiffness matrix at the tower base via static condensation.

    Uses OpenSees' `printA` or a finite-difference probe with unit
    displacements at the base node. This is the matrix that OpenFAST
    SubDyn accepts as a linear SSI interface.
    """
    import openseespy.opensees as ops

    base_node = 1000

    # Simple finite-difference probe: apply a unit displacement in each
    # of the 6 DOFs and read back the reaction.
    K = np.zeros((6, 6))
    for dof in range(1, 7):
        try:
            ops.timeSeries("Linear", 9000 + dof)
            ops.pattern("Plain", 9000 + dof, 9000 + dof)
            ops.sp(base_node, dof, 1.0)

            ops.constraints("Transformation")
            ops.numberer("RCM")
            ops.system("UmfPack")
            ops.test("NormDispIncr", 1e-8, 50, 0)
            ops.algorithm("Linear")
            ops.integrator("LoadControl", 1.0)
            ops.analysis("Static")
            ops.analyze(1)

            reactions = [ops.nodeReaction(base_node, d) for d in range(1, 7)]
            K[:, dof - 1] = reactions

            ops.remove("loadPattern", 9000 + dof)
        except Exception:
            pass

    # Symmetrize to combat numerical noise
    K = 0.5 * (K + K.T)
    return K
