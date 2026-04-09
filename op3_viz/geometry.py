"""
Standalone geometry builders for the Op^3 viz package.

Produces Plotly Mesh3d-ready vertex/face arrays for:

* a tapered tower built from the section table returned by
  ``op3.opensees_foundations.site_a_real_tower.section_properties``
  (proprietary numeric content is loaded at runtime from a private
  data source; see ``op3.data_sources``)
* a generic three-bucket suction-bucket foundation
* an RNA box + rotor disk at the tower top

Dimensions used in the default scene are configurable; any values
that correspond to proprietary hardware are loaded from the private
data store and are **not** hard-coded in this module.

No external 3D stack required -- just numpy. Output format:

    {
        "x": list[float], "y": list[float], "z": list[float],
        "i": list[int], "j": list[int], "k": list[int],
        "nodal_z": np.ndarray  # per-vertex z (useful for field overlays)
    }
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import List

import numpy as np


def _ring(cx: float, cy: float, cz: float, radius: float, n: int = 32) -> np.ndarray:
    theta = np.linspace(0.0, 2.0 * math.pi, n, endpoint=False)
    return np.column_stack([
        cx + radius * np.cos(theta),
        cy + radius * np.sin(theta),
        np.full(n, cz),
    ])


def _tube_faces(n: int, ring_count: int) -> np.ndarray:
    """Triangle faces connecting consecutive rings of n vertices."""
    faces: List[List[int]] = []
    for r in range(ring_count - 1):
        a0 = r * n
        a1 = (r + 1) * n
        for i in range(n):
            j = (i + 1) % n
            faces.append([a0 + i, a0 + j, a1 + j])
            faces.append([a0 + i, a1 + j, a1 + i])
    return np.array(faces, dtype=int)


@dataclass
class Mesh:
    x: np.ndarray
    y: np.ndarray
    z: np.ndarray
    i: np.ndarray
    j: np.ndarray
    k: np.ndarray

    def to_plotly(self) -> dict:
        return dict(
            x=self.x.tolist(), y=self.y.tolist(), z=self.z.tolist(),
            i=self.i.tolist(), j=self.j.tolist(), k=self.k.tolist(),
        )


def build_site_a_tower(n_theta: int = 32) -> Mesh:
    """Build a Mesh3d of the real SiteA tower (tapered tube)."""
    from op3.opensees_foundations.site_a_real_tower import section_properties

    segs = section_properties()
    verts: List[np.ndarray] = []
    # Two rings per segment (bot, top) so OD can taper mid-segment
    for s in segs:
        r_bot = 0.5 * float(s["OD_m"])
        r_top = 0.5 * float(s["OD_m"])  # section is constant-OD within segment
        verts.append(_ring(0.0, 0.0, float(s["z_bot"]), r_bot, n_theta))
        verts.append(_ring(0.0, 0.0, float(s["z_top"]), r_top, n_theta))
    V = np.vstack(verts)
    F = _tube_faces(n_theta, ring_count=len(verts))
    return Mesh(V[:, 0], V[:, 1], V[:, 2], F[:, 0], F[:, 1], F[:, 2])


def build_tripod_bucket(
    r_leg: float | None = None,
    bucket_OD: float | None = None,
    bucket_L: float | None = None,
    z_mudline: float = 0.0,
    n_theta: int = 24,
) -> Mesh:
    """Three suction buckets arranged as a 120-deg symmetric tripod.

    Caller must pass the three dimensional parameters explicitly, or
    leave them ``None`` to fall back to a fully generic demonstration
    geometry (non-proprietary). Any site-specific numerical values
    **must not** be committed here -- load them from the private
    data store via ``op3.data_sources`` at runtime.

    Each bucket is a cylinder from ``z = z_mudline`` down to
    ``z = z_mudline - bucket_L``.
    """
    # Generic demonstration defaults (non-proprietary).
    if r_leg is None:
        r_leg = 10.0
    if bucket_OD is None:
        bucket_OD = 6.0
    if bucket_L is None:
        bucket_L = 6.0
    meshes: List[Mesh] = []
    bearings_deg = (0.0, 120.0, 240.0)  # generic symmetric tripod
    n_rings = 20  # enough stations along the skirt for a smooth colormap
    for bearing in bearings_deg:
        ang = math.radians(bearing)
        cx, cy = r_leg * math.cos(ang), r_leg * math.sin(ang)
        r = 0.5 * bucket_OD
        ring_zs = np.linspace(z_mudline, z_mudline - bucket_L, n_rings)
        rings = [_ring(cx, cy, float(rz), r, n_theta) for rz in ring_zs]
        V = np.vstack(rings)
        F = _tube_faces(n_theta, ring_count=n_rings)
        meshes.append(Mesh(V[:, 0], V[:, 1], V[:, 2], F[:, 0], F[:, 1], F[:, 2]))
    return _merge(meshes)


def build_rna(z_hub: float, box: tuple = (6.0, 4.0, 4.0)) -> Mesh:
    """Cosmetic nacelle box at the tower top. Visual only -- no Op^3
    result depends on the box dimensions."""
    lx, ly, lz = box
    cx = 0.0
    cy = 0.0
    cz = z_hub
    xs = np.array([-1, 1, 1, -1, -1, 1, 1, -1]) * 0.5 * lx + cx
    ys = np.array([-1, -1, 1, 1, -1, -1, 1, 1]) * 0.5 * ly + cy
    zs = np.array([0, 0, 0, 0, 1, 1, 1, 1]) * lz + cz
    faces = np.array([
        [0, 1, 2], [0, 2, 3],  # bottom
        [4, 6, 5], [4, 7, 6],  # top
        [0, 1, 5], [0, 5, 4],
        [1, 2, 6], [1, 6, 5],
        [2, 3, 7], [2, 7, 6],
        [3, 0, 4], [3, 4, 7],
    ])
    return Mesh(xs, ys, zs, faces[:, 0], faces[:, 1], faces[:, 2])


def build_rotor_disk(hub_z: float = 90.0, rotor_D: float = 120.0,
                     n_theta: int = 48) -> Mesh:
    """Rotor as a flat circular disk at the hub, perpendicular to x.

    The defaults are a generic 4 MW-class placeholder. Callers that
    need project-specific hub height / rotor diameter must pass them
    explicitly (loaded at runtime from the private data store).
    """
    r = 0.5 * rotor_D
    theta = np.linspace(0.0, 2.0 * math.pi, n_theta, endpoint=False)
    ring_y = r * np.cos(theta)
    ring_z = hub_z + r * np.sin(theta)
    ring_x = np.zeros_like(ring_y)
    xs = np.concatenate([[0.0], ring_x])
    ys = np.concatenate([[0.0], ring_y])
    zs = np.concatenate([[hub_z], ring_z])
    ii = np.zeros(n_theta, dtype=int)
    jj = np.arange(1, n_theta + 1)
    kk = np.roll(jj, -1); kk[-1] = 1
    return Mesh(xs, ys, zs, ii, jj, kk)


def _merge(meshes: List[Mesh]) -> Mesh:
    xs, ys, zs = [], [], []
    ii, jj, kk = [], [], []
    offset = 0
    for m in meshes:
        xs.append(m.x); ys.append(m.y); zs.append(m.z)
        ii.append(m.i + offset); jj.append(m.j + offset); kk.append(m.k + offset)
        offset += len(m.x)
    return Mesh(
        np.concatenate(xs), np.concatenate(ys), np.concatenate(zs),
        np.concatenate(ii), np.concatenate(jj), np.concatenate(kk),
    )


def build_full_scene() -> dict:
    """Return meshes for the default scene, keyed by part name.

    Geometry comes from ``section_properties()`` (loaded at runtime
    from the private data store via ``op3.data_sources``) plus
    generic placeholder foundation / rotor dimensions. No
    proprietary numeric values are hard-coded in this module.
    """
    tower = build_site_a_tower()
    tripod = build_tripod_bucket()  # generic placeholder dims
    z_top = float(tower.z.max())
    nacelle = build_rna(z_hub=z_top)
    rotor = build_rotor_disk(hub_z=z_top, rotor_D=120.0)
    return {"tower": tower, "tripod": tripod,
            "nacelle": nacelle, "rotor": rotor}


