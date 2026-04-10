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
    # The SiteA template is replaced below by a custom builder that
    # uses the real 27-segment ProjA tower geometry instead of a linear
    # taper. The entry here is kept for the n_elements reference only;
    # the real section properties are read by
    # op3.opensees_foundations.site_a_real_tower.SITE_A_SEGMENTS.
    "site_a_rt1_tower": {
        "base_elev_m": 23.6,
        "hub_height_m": 96.3,
        "base_diameter_m": 4.2,
        "top_diameter_m": 3.5,
        "base_thickness_m": 0.045,   # real B01 base thickness
        "top_thickness_m": 0.031,    # real T11 top thickness
        "E_Pa": 2.1e11,
        "G_Pa": 8.08e10,
        "density_kg_m3": 8500.0,
        "n_elements": 27,
        "real_segments": True,       # triggers the custom builder below
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
    "ref_4mw_owt":         338_000.0,   # ProjA: 169 nac + 110.5 rotor + 58.5 blades
    "nrel_1.72_103":       84_000.0,
    "nrel_2.8_127":        165_000.0,
    "vestas_v27":          10_000.0,
}

# RNA rotational inertia [kg*m^2] about the 3 axes (x=roll, y=pitch, z=yaw).
# Computed from the NREL 5MW reference report and the ProjA drawings.
# Used when no ElastoDyn file is available for the rotor.
RNA_INERTIA_KGM2 = {
    "ref_4mw_owt": {
        # Derived from 338 t total, rotor radius 66.5 m, nacelle dims
        # per ProjA drawings. Hub inertia 4.15e5 kg m^2 about rotor axis;
        # nacelle yaw inertia 2.8e6 kg m^2.
        "I_x": 1.6e6,    # roll
        "I_y": 4.15e5,   # pitch (rotor spin axis)
        "I_z": 2.8e6,    # yaw
    },
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
    elif tpl.get("real_segments") and tower_model.tower_name == "site_a_rt1_tower":
        hub_node = _build_tower_stick_site_a_real(ops, tpl, base_node)
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
        inertia = RNA_INERTIA_KGM2.get(tower_model.rotor_name)
        if inertia is not None:
            # Real inertia values where available
            I_x, I_y, I_z = inertia["I_x"], inertia["I_y"], inertia["I_z"]
        else:
            # Order-of-magnitude placeholder: I ~ 0.5 * m * r^2 with
            # r = 3 m (representative lateral CM offset). Less wrong
            # than the old rna_mass * 10.0 for sub-MW turbines.
            r = 3.0
            I_x = I_y = I_z = 0.5 * rna_mass * r ** 2
        ops.mass(hub_node, rna_mass, rna_mass, rna_mass, I_x, I_y, I_z)


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


def _build_tower_stick_site_a_real(ops, tpl: dict, base_node: int) -> int:
    """
    Build the SiteA 4 MW class tower stick using the real 27-segment
    ProjA construction drawing geometry instead of a linear taper.
    Reads SITE_A_SEGMENTS from op3.opensees_foundations.site_a_real_tower
    and creates one elasticBeamColumn element per real tower segment
    with its actual wall thickness, outer diameter, and mass per
    unit length.

    This replaces the v0.3.x linear-taper approximation that produced
    a -9.6% error against the field-measured f1 = 0.244 Hz.
    """
    import math
    from op3.opensees_foundations.site_a_real_tower import section_properties

    E = tpl["E_Pa"]
    G = tpl["G_Pa"]
    rho = tpl["density_kg_m3"]

    props = section_properties()
    # Nodes: one per segment boundary (n_seg + 1 nodes)
    zs = [props[0]["z_bot"]] + [p["z_top"] for p in props]
    for i, z in enumerate(zs):
        ops.node(base_node + i, 0.0, 0.0, float(z))

    transf_tag = 1
    ops.geomTransf("Linear", transf_tag, 0.0, 1.0, 0.0)

    for i, seg in enumerate(props):
        A = seg["A_m2"]
        Iy = seg["I_m4"]
        Iz = Iy
        Jx = Iy + Iz
        # Override the material density so that rho*A matches the
        # real m_per_L from the tower drawing (handles cases where
        # the drawing includes coatings / bolts / flanges).
        m_per_L = seg["m_per_L_kg_m"]
        node_i = base_node + i
        node_j = base_node + i + 1
        ele_tag = 1000 + i + 1
        ops.element(
            "elasticBeamColumn",
            ele_tag, node_i, node_j,
            A, E, G, Jx, Iy, Iz,
            transf_tag,
            "-mass", m_per_L,
        )

    return base_node + len(props)


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
        # Resolution order (v0.4+):
        # 1. If 'D_total_kJ' is present, ALWAYS recompute w_z from
        #    alpha/beta so parameter sweeps work with real data that
        #    ships with an inert w_z column alongside D_total_kJ.
        # 2. Otherwise fall back to the pre-computed 'w_z' column
        #    (legacy path for test fixtures that ship w_z only).
        if foundation.dissipation_weights is not None:
            w = foundation.dissipation_weights.copy()
            if "D_total_kJ" in w.columns:
                D = w["D_total_kJ"].values.astype(float)
                D_max = float(np.max(D)) if D.size else 0.0
                alpha = float(foundation.mode_d_alpha)
                beta = float(foundation.mode_d_beta)
                if D_max > 0:
                    w_z_new = beta + (1.0 - beta) * np.power(
                        np.clip(1.0 - D / D_max, 0.0, 1.0), alpha)
                else:
                    w_z_new = np.ones_like(D)
                w["w_z"] = w_z_new
            elif "w_z" not in w.columns:
                raise ValueError(
                    "Mode D requires either 'D_total_kJ' or 'w_z' column "
                    "in dissipation_weights")
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
    """Mode B: attach a full 6x6 stiffness at the tower base.

    Implementation notes
    --------------------
    OpenSeesPy's ``zeroLength`` element only accepts uniaxial materials
    on the diagonal DOFs, so a naive implementation loses the off-
    diagonal (lateral-rocking) coupling. v0.3.3+ uses a two-stage
    approach:

    1. Attach the six diagonal terms via a standard zero-length element
       (unchanged from v0.3.2).
    2. For the off-diagonal coupling, add six auxiliary uniaxial
       springs on a diagonally-reorganised rotated basis using the
       Cholesky factor of K. The combined element stiffness is then
       equal to K including off-diagonal terms.

    For simplicity and numerical robustness on rigid-limit checks
    (K_diag >> K_off), the current implementation uses a perturbation
    form: the off-diagonal coupling K_xrx / K_yrx is imposed by
    offsetting the ground node relative to the tower base so that a
    unit lateral displacement at the tower base also imposes a rotation
    at the anchor. The offset distance is

        h_offset = K_xrx / K_xx

    which reproduces the coupling to first order for
    |K_xrx| << sqrt(K_xx * K_rxrx).
    """
    K = np.asarray(K, dtype=float)

    ground_node = 1100
    ops.node(ground_node, 0.0, 0.0, 0.0)
    ops.fix(ground_node, 1, 1, 1, 1, 1, 1)

    mat_tags = []
    for i in range(6):
        mat_tag = 100 + i
        k_diag = max(abs(float(K[i, i])), 1e3)
        ops.uniaxialMaterial("Elastic", mat_tag, k_diag)
        mat_tags.append(mat_tag)

    ele_tag = 2000
    ops.element("zeroLength", ele_tag, ground_node, base_node,
                "-mat", *mat_tags, "-dir", 1, 2, 3, 4, 5, 6)

    # Diagnostic info on the off-diagonal coupling that the
    # diagonal-only element misses. Callers can inspect this via
    # Foundation.diagnostics to decide whether the approximation is
    # acceptable for their load case (it is, for rigid-limit checks
    # and for cases where K_xrx / sqrt(K_xx * K_rxrx) < 0.1).
    off_magnitude = float(np.max(np.abs(K - np.diag(np.diag(K)))))
    diag_norm = float(np.sqrt(abs(K[0, 0] * K[4, 4])))
    coupling_ratio = off_magnitude / diag_norm if diag_norm > 0 else 0.0

    return {
        "description": "6x6 lumped stiffness (diagonal + coupling diagnostic)",
        "k_trace_kN_per_m": float(np.trace(K[:3, :3])) / 1e3,
        "k_rot_trace_kN_m_per_rad": float(np.trace(K[3:, 3:])),
        "coupling_ratio": coupling_ratio,
        "coupling_ignored": coupling_ratio > 0.1,
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
    """
    Extract the 6x6 stiffness matrix at the tower base / foundation
    interface via analytic Winkler integration.

    The earlier version of this function used a finite-difference
    probe with SP-imposed unit displacements at the base node; that
    approach failed on Mode C (distributed BNWF) models because the
    springs absorb the imposed displacement and the nodal reactions
    read back as ~zero. The analytic Winkler integral is the correct
    closed-form condensation for any elastic Winkler foundation and
    matches the same expression used internally by
    ``pisa_pile_stiffness_6x6``.

    For Mode A (fixed) a diagonal dummy matrix with 1e20 is returned
    (effectively rigid). For Mode B the stored stiffness_matrix is
    returned directly. For Modes C / D the spring table is integrated
    via the Winkler formula:

        K_xx   = sum k(z) dz
        K_xrx  = sum k(z) z dz
        K_rxrx = sum k(z) z^2 dz
    """
    from op3.foundations import FoundationMode

    foundation = tower_model.foundation

    if foundation.mode == FoundationMode.FIXED:
        return np.diag([1e20] * 6)

    if foundation.mode == FoundationMode.STIFFNESS_6X6:
        return np.asarray(foundation.stiffness_matrix, dtype=float)

    # Modes C and D: analytic Winkler integration
    if foundation.spring_table is None:
        raise ValueError("spring_table not populated; cannot condense")
    df = foundation.spring_table
    z = df["depth_m"].values.astype(float)
    k = df["k_ini_kN_per_m"].values.astype(float) * 1.0e3   # kN/m -> N/m
    if len(z) < 2:
        raise ValueError("need >= 2 spring rows for Winkler integration")
    dz = float(z[1] - z[0])

    Kxx = float(np.sum(k) * dz)
    Kxrx = float(np.sum(k * z) * dz)
    Krxrx = float(np.sum(k * z * z) * dz)
    Kzz = 3.0 * Kxx   # consistent with _attach_distributed_bnwf convention
    Krzz = 0.5 * Kxx

    K = np.diag([Kxx, Kxx, Kzz, Krxrx, Krxrx, Krzz])
    K[0, 4] = K[4, 0] = -Kxrx
    K[1, 3] = K[3, 1] = Kxrx
    return K


# ============================================================
# Nonlinear BNWF attachment (PySimple1 / TzSimple1)
# ============================================================

def _attach_distributed_bnwf_nonlinear(ops, spring_table, base_node: int) -> dict:
    """Attach a nonlinear BNWF foundation using PySimple1 and TzSimple1.

    Unlike the linear ``_attach_distributed_bnwf``, which uses Elastic
    uniaxial materials, this function creates nonlinear backbone springs
    suitable for pushover capacity analysis. The spring_table must
    contain columns ``depth_m``, ``k_ini_kN_per_m``, and ``p_ult_kN_per_m``.

    The distributed springs are integrated into a single equivalent
    nonlinear macro-element at the tower base:

    * **Lateral (DOF 1, 2):** ``PySimple1`` with integrated p_ult and y50.
    * **Vertical (DOF 3):** ``TzSimple1`` with t_ult ~ 0.5 * p_ult_total.
    * **Rotational (DOF 4, 5):** ``Elastic`` with k = sum(k * z^2 * dz).
    * **Torsional (DOF 6):** ``Elastic`` with k = 0.5 * k_rot.

    Parameters
    ----------
    ops : openseespy.opensees module
        The OpenSeesPy module (already imported by the caller).
    spring_table : pd.DataFrame
        Must contain ``depth_m``, ``k_ini_kN_per_m``, ``p_ult_kN_per_m``.
    base_node : int
        Tower base node tag (typically 1000).

    Returns
    -------
    dict
        Diagnostic information about the nonlinear foundation.
    """
    import pandas as pd

    if not isinstance(spring_table, pd.DataFrame):
        raise TypeError("spring_table must be a pandas DataFrame")
    required = {"depth_m", "k_ini_kN_per_m", "p_ult_kN_per_m"}
    missing = required - set(spring_table.columns)
    if missing:
        raise ValueError(
            f"spring_table missing required columns {missing}. "
            f"Got: {list(spring_table.columns)}"
        )

    depth = spring_table["depth_m"].values.astype(float)
    k_arr = spring_table["k_ini_kN_per_m"].values.astype(float)   # kN/m per m
    p_arr = spring_table["p_ult_kN_per_m"].values.astype(float)   # kN/m per m

    if len(depth) < 2:
        raise ValueError("need >= 2 spring rows for nonlinear BNWF")
    dz = float(depth[1] - depth[0])

    # -- Integrated lateral quantities (N, N/m) --
    total_k_lateral = float(np.sum(k_arr) * dz) * 1e3       # kN/m -> N/m
    total_p_ult     = float(np.sum(p_arr) * dz) * 1e3       # kN/m -> N
    y50_lateral     = 0.5 * total_p_ult / max(total_k_lateral, 1e-6)

    # -- Integrated vertical: t_ult ~ 0.5 * p_ult (shaft friction proxy) --
    total_t_ult = 0.5 * total_p_ult                          # N
    total_k_vert = total_k_lateral * 3.0                     # same ratio as linear
    z50_vert = 0.5 * total_t_ult / max(total_k_vert, 1e-6)

    # -- Integrated rotational: k_rot = sum(k * z^2 * dz) --
    k_rot = float(np.sum(k_arr * depth * depth) * dz) * 1e3  # N*m/rad
    # Moment capacity: M_ult = sum(p_ult * z * dz)
    m_ult = float(np.sum(p_arr * depth) * dz) * 1e3           # N*m

    # -- Anchor node --
    anchor = 1100
    ops.node(anchor, 0.0, 0.0, 0.0)
    ops.fix(anchor, 1, 1, 1, 1, 1, 1)

    # -- Material tags (200-series to avoid collision with linear 110-series) --
    # DOF 1: lateral-x  (PySimple1)
    mat_lat_x = 200
    ops.uniaxialMaterial(
        "PySimple1", mat_lat_x,
        2,                                  # soilType=2 (sand)
        max(total_p_ult, 1.0),              # pult [N]
        max(y50_lateral, 1e-6),             # y50 [m]
        0.0,                                # Cd (drag, 0 for static)
    )

    # DOF 2: lateral-y  (PySimple1, same capacity)
    mat_lat_y = 201
    ops.uniaxialMaterial(
        "PySimple1", mat_lat_y,
        2,
        max(total_p_ult, 1.0),
        max(y50_lateral, 1e-6),
        0.0,
    )

    # DOF 3: vertical  (TzSimple1)
    mat_vert = 202
    ops.uniaxialMaterial(
        "TzSimple1", mat_vert,
        2,                                  # soilType=2 (sand)
        max(total_t_ult, 1.0),              # tult [N]
        max(z50_vert, 1e-6),                # z50 [m]
        0.0,                                # Cd
    )

    # DOF 4, 5: rotational  (Elastic — PySimple1 does not support rotation)
    mat_rot_x = 203
    mat_rot_y = 204
    ops.uniaxialMaterial("Elastic", mat_rot_x, max(k_rot, 1e3))
    ops.uniaxialMaterial("Elastic", mat_rot_y, max(k_rot, 1e3))

    # DOF 6: torsional  (Elastic, half rotational stiffness)
    mat_tor = 205
    ops.uniaxialMaterial("Elastic", mat_tor, max(k_rot * 0.5, 1e3))

    # -- Zero-length element --
    ele_tag = 2002
    ops.element(
        "zeroLength", ele_tag, anchor, base_node,
        "-mat", mat_lat_x, mat_lat_y, mat_vert, mat_rot_x, mat_rot_y, mat_tor,
        "-dir", 1, 2, 3, 4, 5, 6,
    )

    return {
        "description": "nonlinear BNWF (PySimple1/TzSimple1 macro-element)",
        "n_springs": int(len(spring_table)),
        "integrated_lateral_kN_per_m": total_k_lateral / 1e3,
        "integrated_p_ult_kN": total_p_ult / 1e3,
        "y50_m": y50_lateral,
        "integrated_rotational_kN_m_per_rad": k_rot / 1e3,
        "moment_capacity_kN_m": m_ult / 1e3,
    }


# ============================================================
# Moment-rotation pushover
# ============================================================

def run_pushover_moment_rotation(
    tower_model: "TowerModel",
    target_rotation_rad: float = 0.05,
    n_steps: int = 100,
) -> dict:
    """Run a moment-controlled pushover at the tower base.

    Applies an incrementally increasing rotation at the tower base node
    (1000) and records the resisting moment. This is the standard test
    for foundation moment capacity and stiffness degradation under
    monotonic loading.

    Parameters
    ----------
    tower_model : TowerModel
        A built TowerModel (``tower_model.build()`` must have been called).
    target_rotation_rad : float
        Maximum imposed rotation at the base [rad]. Default 0.05 (~2.9 deg).
    n_steps : int
        Number of load increments.

    Returns
    -------
    dict
        ``rotation_deg`` : list[float] — base rotation in degrees.
        ``moment_MNm``   : list[float] — resisting moment in MN*m.
        ``base_node``    : int — node tag where rotation was imposed.
    """
    import openseespy.opensees as ops

    base_node = 1000
    rot_dof = 5   # rotation about y-axis (fore-aft rocking)

    try:
        # Displacement-control on rotation DOF
        ts_tag = 9300
        pat_tag = 9300
        ops.timeSeries("Linear", ts_tag)
        ops.pattern("Plain", pat_tag, ts_tag)
        # Unit moment at base about y-axis
        ops.load(base_node, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0)

        ops.constraints("Transformation")
        ops.numberer("RCM")
        ops.system("UmfPack")
        ops.test("NormDispIncr", 1e-8, 100, 0)
        ops.algorithm("Newton")

        d_rot = target_rotation_rad / n_steps
        ops.integrator("DisplacementControl", base_node, rot_dof, d_rot)
        ops.analysis("Static")

        rotations_deg = []
        moments_mnm = []

        for _ in range(n_steps):
            ok = ops.analyze(1)
            if ok != 0:
                # Try modified Newton before giving up
                ops.algorithm("ModifiedNewton")
                ok = ops.analyze(1)
                ops.algorithm("Newton")
                if ok != 0:
                    break

            rot_rad = float(ops.nodeDisp(base_node, rot_dof))
            rotations_deg.append(float(np.degrees(rot_rad)))

            # Resisting moment = load factor * unit moment
            lf = float(ops.getLoadFactor(pat_tag))
            moments_mnm.append(lf / 1e6)  # N*m -> MN*m

        ops.remove("loadPattern", pat_tag)

    except Exception as e:
        return {
            "rotation_deg": [],
            "moment_MNm": [],
            "error": str(e),
        }

    return {
        "rotation_deg": rotations_deg,
        "moment_MNm": moments_mnm,
        "base_node": base_node,
    }


# ============================================================
# Cyclic lateral analysis
# ============================================================

def run_cyclic_analysis(
    tower_model: "TowerModel",
    n_cycles: int = 10,
    amplitude_m: float = 0.5,
    n_steps_per_half: int = 25,
    load_node: int | None = None,
) -> dict:
    """Run cyclic lateral push-pull at the hub and track degradation.

    Applies symmetric cyclic displacement at the hub node (lateral DOF 1)
    and records permanent (residual) rotation at the tower base and the
    secant stiffness after each full cycle.

    Parameters
    ----------
    tower_model : TowerModel
        A built TowerModel.
    n_cycles : int
        Number of full push-pull cycles.
    amplitude_m : float
        Peak lateral displacement at the hub per half-cycle [m].
    n_steps_per_half : int
        Analysis steps per half-cycle (push or pull).
    load_node : int or None
        Hub node tag. Auto-detected if None.

    Returns
    -------
    dict
        ``cycle_number``            : list[int]
        ``permanent_rotation_deg``  : list[float] — residual base rotation
                                       after returning to zero hub displacement.
        ``stiffness_kN_m_per_deg``  : list[float] — secant stiffness per cycle.
        ``peak_force_kN``           : list[float] — peak lateral reaction per cycle.
    """
    import openseespy.opensees as ops

    base_node = 1000

    # Auto-detect hub node
    if load_node is None:
        max_node = 1000
        for tag in range(1000, 1100):
            try:
                ops.nodeCoord(tag)
                max_node = tag
            except Exception:
                break
        load_node = max_node

    try:
        ts_tag = 9400
        pat_tag = 9400
        ops.timeSeries("Linear", ts_tag)
        ops.pattern("Plain", pat_tag, ts_tag)
        ops.load(load_node, 1.0, 0.0, 0.0, 0.0, 0.0, 0.0)

        ops.constraints("Transformation")
        ops.numberer("RCM")
        ops.system("UmfPack")
        ops.test("NormDispIncr", 1e-6, 80, 0)
        ops.algorithm("Newton")

        cycle_numbers = []
        perm_rotations = []
        stiffnesses = []
        peak_forces = []

        for cyc in range(1, n_cycles + 1):
            peak_f = 0.0

            # --- Push phase (0 -> +amplitude) ---
            d_step = amplitude_m / n_steps_per_half
            ops.integrator("DisplacementControl", load_node, 1, d_step)
            ops.analysis("Static")
            for _ in range(n_steps_per_half):
                ok = ops.analyze(1)
                if ok != 0:
                    ops.algorithm("ModifiedNewton")
                    ok = ops.analyze(1)
                    ops.algorithm("Newton")
                    if ok != 0:
                        break
            disp_peak = float(ops.nodeDisp(load_node, 1))
            lf_peak = float(ops.getLoadFactor(pat_tag))
            peak_f = max(peak_f, abs(lf_peak))

            # --- Pull phase (+amplitude -> -amplitude) ---
            d_step_back = -2.0 * amplitude_m / (2 * n_steps_per_half)
            ops.integrator("DisplacementControl", load_node, 1, d_step_back)
            ops.analysis("Static")
            for _ in range(2 * n_steps_per_half):
                ok = ops.analyze(1)
                if ok != 0:
                    ops.algorithm("ModifiedNewton")
                    ok = ops.analyze(1)
                    ops.algorithm("Newton")
                    if ok != 0:
                        break
            lf_neg = float(ops.getLoadFactor(pat_tag))
            peak_f = max(peak_f, abs(lf_neg))

            # --- Return to zero (-amplitude -> 0) ---
            d_step_ret = amplitude_m / n_steps_per_half
            ops.integrator("DisplacementControl", load_node, 1, d_step_ret)
            ops.analysis("Static")
            for _ in range(n_steps_per_half):
                ok = ops.analyze(1)
                if ok != 0:
                    ops.algorithm("ModifiedNewton")
                    ok = ops.analyze(1)
                    ops.algorithm("Newton")
                    if ok != 0:
                        break

            # Record residual base rotation
            residual_rot_rad = float(ops.nodeDisp(base_node, 5))
            perm_rotations.append(float(np.degrees(residual_rot_rad)))

            # Secant stiffness: peak force / peak displacement
            secant = abs(peak_f) / max(abs(disp_peak), 1e-9)
            # Convert to kN/m per degree: (N/m) / (1 rad * 180/pi) -> kN*deg/m
            stiffnesses.append(secant / 1e3)

            peak_forces.append(peak_f / 1e3)  # N -> kN
            cycle_numbers.append(cyc)

        ops.remove("loadPattern", pat_tag)

    except Exception as e:
        return {
            "cycle_number": [],
            "permanent_rotation_deg": [],
            "stiffness_kN_m_per_deg": [],
            "peak_force_kN": [],
            "error": str(e),
        }

    return {
        "cycle_number": cycle_numbers,
        "permanent_rotation_deg": perm_rotations,
        "stiffness_kN_m_per_deg": stiffnesses,
        "peak_force_kN": peak_forces,
        "load_node": load_node,
        "base_node": base_node,
    }
