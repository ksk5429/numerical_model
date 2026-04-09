"""
Adapter that turns real Op^3 computations into vertex-intensity arrays
for ``op3_viz.dash_app``.

All functions accept an ``op3_viz.geometry.Mesh`` (the SiteA tower
mesh) and return a numpy array of length ``len(mesh.x)`` suitable for
Plotly ``Mesh3d(intensity=...)``.

The mapping strategy is simple and robust: the tower is a stack of
tubes, so the mesh z-coordinate uniquely identifies a structural
height. We interpolate any (z, value) signal onto the vertex z's.
"""
from __future__ import annotations

import numpy as np

from .geometry import Mesh


def _interp_on_z(mesh: Mesh, z_ref: np.ndarray, v_ref: np.ndarray) -> np.ndarray:
    """Linearly interpolate (z_ref, v_ref) onto mesh vertex z's."""
    order = np.argsort(z_ref)
    z_s = np.asarray(z_ref, dtype=float)[order]
    v_s = np.asarray(v_ref, dtype=float)[order]
    return np.interp(np.asarray(mesh.z, dtype=float), z_s, v_s,
                     left=v_s[0], right=v_s[-1])


# ------------------------------------------------------------------
# 1. Real eigen-mode shape from a composed Op^3 model
# ------------------------------------------------------------------

def real_mode_shape(mesh: Mesh, mode_index: int = 1,
                    foundation_mode: str = "fixed") -> np.ndarray:
    """Build a minimal SiteA Op^3 model, run eigen, return the
    horizontal amplitude sqrt(u_x^2 + u_y^2) of the requested mode
    interpolated onto the tower mesh.

    Raises RuntimeError if the eigen run or eigenvector extraction
    fails -- we never silently fall back to an analytical shape, so
    the UI label "Real eigenmode" is always truthful.
    """
    import openseespy.opensees as ops
    from op3 import build_foundation, compose_tower_model

    f = build_foundation(mode=foundation_mode)
    model = compose_tower_model(
        rotor="ref_4mw_owt",
        tower="site_a_rt1_tower",
        foundation=f,
        damping_ratio=0.01,
    )
    model.eigen(n_modes=max(3, mode_index + 1))

    z_nodes, u_nodes = [], []
    for tag in range(1000, 1100):
        try:
            coord = ops.nodeCoord(tag)
        except Exception:
            break
        try:
            u = ops.nodeEigenvector(tag, int(mode_index))
        except Exception:
            continue
        z_nodes.append(float(coord[2]) if len(coord) >= 3 else float(coord[-1]))
        # Horizontal magnitude -- mode 1 may be side-side (u_y) and
        # mode 2 fore-aft (u_x); either way the bending amplitude is
        # sqrt(u_x^2 + u_y^2), not a single component.
        ux = float(u[0]) if len(u) >= 1 else 0.0
        uy = float(u[1]) if len(u) >= 2 else 0.0
        u_nodes.append((ux * ux + uy * uy) ** 0.5)
    if len(z_nodes) < 2:
        raise RuntimeError(
            f"eigenvector extraction failed: {len(z_nodes)} samples")
    z_arr = np.array(z_nodes)
    u_arr = np.array(u_nodes)
    u_arr = u_arr / max(u_arr.max(), 1e-12)
    return _interp_on_z(mesh, z_arr, u_arr)


# ------------------------------------------------------------------
# 2. Mode D dissipation-weighted stiffness overlay from real data
# ------------------------------------------------------------------

def _load_w_dissip_profile() -> tuple[np.ndarray, np.ndarray]:
    """Return (z_soil [m, positive down], w_dissip [-]) from the real
    OptumGX v4 spring table.

    Schema (PHD/data/optumgx/dissipation/spring_params_v4_dissipation.csv):
        z_m, su_kPa, w_dissip, Np, k_ini_kNm3, ...   (19 rows, z = 0.5..9.5 m)
    """
    import pandas as pd
    from op3.data_sources import site_a_spring_params

    path = site_a_spring_params()
    df = pd.read_csv(path)
    if "w_dissip" not in df.columns or "z_m" not in df.columns:
        raise RuntimeError(
            f"unexpected schema in {path}: {list(df.columns)}")
    return (df["z_m"].to_numpy(dtype=float),
            df["w_dissip"].to_numpy(dtype=float))


def real_dissipation_weight_on_tripod(tripod_mesh: Mesh) -> np.ndarray:
    """Paint w_dissip onto the tripod bucket mesh.

    Tripod vertices have z in [-bucket_L, 0] (below mudline). The
    soil table has positive-downward z in [0.5, 9.5] m. We map
    ``z_soil = -z_vertex`` to get the physically correct overlay:
    depth below mudline -> dissipation weight.
    """
    z_soil, w = _load_w_dissip_profile()
    depth = -np.asarray(tripod_mesh.z, dtype=float)   # mudline at 0
    depth = np.clip(depth, z_soil.min(), z_soil.max())
    order = np.argsort(z_soil)
    return np.interp(depth, z_soil[order], w[order])


# ------------------------------------------------------------------
# 3. Bending stress proxy from section properties
# ------------------------------------------------------------------

def bending_stress_proxy(mesh: Mesh, Mtop_kNm: float = 0.0,
                         F_hub_kN: float = 1000.0) -> np.ndarray:
    """Evaluate sigma(z) = M(z) * c(z) / I(z) using the real 27-segment
    SiteA tower section properties and a cantilever with a tip load.

    Moment arm is (z_top - z); M(z) = F * (z_top - z). Section I(z) and
    OD(z) come from ``section_properties()``.
    """
    from op3.opensees_foundations.site_a_real_tower import section_properties
    segs = section_properties()

    z_seg = np.array([0.5 * (s["z_bot"] + s["z_top"]) for s in segs])
    I_seg = np.array([float(s["I_m4"]) for s in segs])
    c_seg = np.array([0.5 * float(s["OD_m"]) for s in segs])
    z_top = float(max(s["z_top"] for s in segs))

    M_seg = (F_hub_kN * 1e3) * (z_top - z_seg) + Mtop_kNm * 1e3
    sigma = M_seg * c_seg / np.maximum(I_seg, 1e-12)  # Pa
    return _interp_on_z(mesh, z_seg, sigma / 1e6)      # MPa
