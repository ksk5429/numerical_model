"""Three.js-compatible mesh generation for Op3 geometries.

All mesh data is generated server-side from physical dimensions and
returned as plain Python dicts that map cleanly onto Three.js
``BufferGeometry`` (vertices Float32, indices Uint32, optional
per-vertex colors).

Geometry is parametric (cylinders, discs, catenary etc.) -- not
synthetic data. Stress colormaps, when included, are applied to a
real ``stress_profile`` array supplied by the caller (typically the
output of an op3 capacity calculation); the helper never invents
stress values.

Coordinate system
-----------------
* +Y is up (Three.js convention)
* Mudline is at Y = 0
* +Y goes upward (toward sea surface), -Y goes into the soil
* Anchor / bucket axis is aligned with -Y
"""
from __future__ import annotations

from typing import Any

import numpy as np


# ---------------------------------------------------------------------------
# Primitive builders
# ---------------------------------------------------------------------------

def _create_cylinder(
    radius: float,
    height: float,
    n_segments: int = 32,
    y_top: float = 0.0,
) -> tuple[list[list[float]], list[list[int]]]:
    """Open-ended cylinder along -Y. Returns (vertices, faces).

    The cylinder runs from y_top (top edge) down to y_top - height
    (bottom edge). Faces are triangulated quads ordered for outward-
    facing normals when used as a skirt outer surface.
    """
    verts: list[list[float]] = []
    faces: list[list[int]] = []

    for i in range(n_segments + 1):
        ang = 2.0 * np.pi * i / n_segments
        x = radius * np.cos(ang)
        z = radius * np.sin(ang)
        verts.append([x, y_top, z])
        verts.append([x, y_top - height, z])

    for i in range(n_segments):
        a = 2 * i
        b = 2 * i + 1
        c = 2 * i + 2
        d = 2 * i + 3
        faces.append([a, b, d])
        faces.append([a, d, c])
    return verts, faces


def _create_disc(
    radius: float,
    n_segments: int = 32,
    y_offset: float = 0.0,
) -> tuple[list[list[float]], list[list[int]]]:
    """Flat circular disc in the X-Z plane at y_offset."""
    verts = [[0.0, y_offset, 0.0]]
    for i in range(n_segments + 1):
        ang = 2.0 * np.pi * i / n_segments
        verts.append([radius * np.cos(ang), y_offset, radius * np.sin(ang)])
    faces = [[0, i + 1, i + 2] for i in range(n_segments)]
    return verts, faces


def _create_sphere(
    radius: float,
    center: tuple[float, float, float],
    n_segments: int = 16,
) -> tuple[list[list[float]], list[list[int]]]:
    """UV sphere centred at ``center``."""
    cx, cy, cz = center
    verts: list[list[float]] = []
    for i in range(n_segments + 1):
        theta = np.pi * i / n_segments       # 0..pi
        for j in range(n_segments + 1):
            phi = 2.0 * np.pi * j / n_segments
            x = cx + radius * np.sin(theta) * np.cos(phi)
            y = cy + radius * np.cos(theta)
            z = cz + radius * np.sin(theta) * np.sin(phi)
            verts.append([x, y, z])
    faces: list[list[int]] = []
    stride = n_segments + 1
    for i in range(n_segments):
        for j in range(n_segments):
            a = i * stride + j
            b = a + 1
            c = a + stride
            d = c + 1
            faces.append([a, b, c])
            faces.append([b, d, c])
    return verts, faces


def _create_ground_plane(
    extent: float,
    n_segments: int = 16,
    y_offset: float = 0.0,
) -> tuple[list[list[float]], list[list[int]]]:
    """Flat square plane in X-Z at y_offset."""
    verts: list[list[float]] = []
    half = extent / 2.0
    step = extent / n_segments
    for i in range(n_segments + 1):
        for j in range(n_segments + 1):
            verts.append([-half + j * step, y_offset, -half + i * step])
    faces: list[list[int]] = []
    stride = n_segments + 1
    for i in range(n_segments):
        for j in range(n_segments):
            a = i * stride + j
            b = a + 1
            c = a + stride
            d = c + 1
            faces.append([a, c, b])
            faces.append([b, c, d])
    return verts, faces


def _create_box(
    size: tuple[float, float, float],
    center: tuple[float, float, float],
) -> tuple[list[list[float]], list[list[int]]]:
    """Axis-aligned box."""
    sx, sy, sz = (s / 2.0 for s in size)
    cx, cy, cz = center
    verts = [
        [cx - sx, cy - sy, cz - sz], [cx + sx, cy - sy, cz - sz],
        [cx + sx, cy + sy, cz - sz], [cx - sx, cy + sy, cz - sz],
        [cx - sx, cy - sy, cz + sz], [cx + sx, cy - sy, cz + sz],
        [cx + sx, cy + sy, cz + sz], [cx - sx, cy + sy, cz + sz],
    ]
    faces = [
        [0, 1, 2], [0, 2, 3],   # -Z face
        [4, 6, 5], [4, 7, 6],   # +Z face
        [0, 3, 7], [0, 7, 4],   # -X face
        [1, 5, 6], [1, 6, 2],   # +X face
        [3, 2, 6], [3, 6, 7],   # +Y face
        [0, 4, 5], [0, 5, 1],   # -Y face
    ]
    return verts, faces


def _create_scour_cavity(
    bucket_radius: float,
    scour_depth: float,
    extent: float,
    n_segments: int = 32,
) -> tuple[list[list[float]], list[list[int]]]:
    """Inverted truncated cone representing the scour hole around a
    foundation. The cavity is centred on the foundation axis, rises
    from y = 0 to y = -scour_depth at the bucket wall, and tapers
    outward to y = 0 at radius ``extent``."""
    verts: list[list[float]] = []
    n_rings = 4
    for ring in range(n_rings + 1):
        r = bucket_radius + (extent - bucket_radius) * ring / n_rings
        # smoother cosine taper from -scour_depth at r=R to 0 at r=extent
        t = ring / n_rings
        y = -scour_depth * (1.0 - t) ** 2
        for i in range(n_segments + 1):
            ang = 2.0 * np.pi * i / n_segments
            verts.append([r * np.cos(ang), y, r * np.sin(ang)])
    faces: list[list[int]] = []
    stride = n_segments + 1
    for ring in range(n_rings):
        for i in range(n_segments):
            a = ring * stride + i
            b = a + 1
            c = a + stride
            d = c + 1
            faces.append([a, b, c])
            faces.append([b, d, c])
    return verts, faces


def _compute_catenary(
    anchor_point: tuple[float, float, float],
    angle_deg: float,
    length_m: float,
    n_points: int = 50,
    horizontal_distance_m: float = 30.0,
) -> list[list[float]]:
    """Approximate catenary curve from the anchor padeye upward to a
    fairlead point.

    The catenary is parameterised by the chord vector and the
    "sag depth" which scales with (line_length - chord_length). For a
    single-line static visualisation this approximation is sufficient
    -- the real MoorPy solution lives behind the
    /api/anchor/installation endpoint when needed.
    """
    ax, ay, az = anchor_point
    # Fairlead position: project up at angle_deg from horizontal
    fx = ax + horizontal_distance_m * np.cos(np.radians(angle_deg))
    fy = ay + horizontal_distance_m * np.tan(np.radians(angle_deg))
    fz = az
    chord = np.hypot(fx - ax, fy - ay)
    sag = max(0.0, (length_m - chord) * 0.4)

    pts: list[list[float]] = []
    for k in range(n_points + 1):
        t = k / n_points
        x = ax + (fx - ax) * t
        y = ay + (fy - ay) * t
        z = az + (fz - az) * t
        # parabolic sag in -Y proportional to t(1-t)
        y -= sag * 4.0 * t * (1.0 - t)
        pts.append([float(x), float(y), float(z)])
    return pts


def _stress_to_colors(
    stress_values: np.ndarray,
    colormap: str = "jet",
    vmin: float | None = None,
    vmax: float | None = None,
) -> list[list[float]]:
    """Per-vertex RGB from a real stress array using a matplotlib colormap.

    Raises ValueError if the array is empty -- never invents values.
    """
    arr = np.asarray(stress_values, dtype=float)
    if arr.size == 0:
        raise ValueError("stress_values is empty; cannot build colormap")
    import matplotlib
    import matplotlib.colors as mcolors
    vmin = float(arr.min()) if vmin is None else float(vmin)
    vmax = float(arr.max()) if vmax is None else float(vmax)
    if vmax <= vmin:
        vmax = vmin + 1e-9
    norm = mcolors.Normalize(vmin=vmin, vmax=vmax)
    cmap = matplotlib.colormaps[colormap]
    colors: list[list[float]] = []
    for v in arr:
        r, g, b, _ = cmap(norm(v))
        colors.append([float(r), float(g), float(b)])
    return colors


def _translate(
    vertices: list[list[float]],
    offset: tuple[float, float, float],
) -> list[list[float]]:
    ox, oy, oz = offset
    return [[v[0] + ox, v[1] + oy, v[2] + oz] for v in vertices]


# ---------------------------------------------------------------------------
# Public mesh generators
# ---------------------------------------------------------------------------

def generate_suction_bucket_mesh(
    diameter_m: float,
    skirt_length_m: float,
    wall_thickness_mm: float = 25.0,
    scour_depth_m: float = 0.0,
    n_segments: int = 32,
    stress_profile: list[float] | None = None,
) -> dict[str, dict[str, Any]]:
    """Suction bucket: lid + outer skirt + soil surface (+ scour cavity)."""
    R = diameter_m / 2.0
    L = skirt_length_m

    components: dict[str, dict[str, Any]] = {}

    lid_v, lid_f = _create_disc(R, n_segments, y_offset=0.0)
    components["lid"] = {"vertices": lid_v, "faces": lid_f}

    sk_v, sk_f = _create_cylinder(R, L, n_segments, y_top=0.0)
    skirt_comp: dict[str, Any] = {"vertices": sk_v, "faces": sk_f}
    if stress_profile is not None:
        # Replicate per-depth stress to per-vertex (2 verts per ring).
        per_vertex = np.repeat(np.asarray(stress_profile, dtype=float),
                               2)[: len(sk_v)]
        skirt_comp["colors"] = _stress_to_colors(per_vertex)
    components["skirt_outer"] = skirt_comp

    if scour_depth_m > 0:
        cv_v, cv_f = _create_scour_cavity(R, scour_depth_m,
                                          extent=3.0 * R,
                                          n_segments=n_segments)
        components["scour_cavity"] = {"vertices": cv_v, "faces": cv_f}

    sf_v, sf_f = _create_ground_plane(
        extent=5.0 * R, n_segments=16, y_offset=-scour_depth_m,
    )
    components["soil_surface"] = {"vertices": sf_v, "faces": sf_f}

    return components


def generate_anchor_mesh(
    diameter_m: float,
    skirt_length_m: float,
    padeye_depth_m: float,
    mooring_angle_deg: float = 35.0,
    mooring_length_m: float = 50.0,
    n_segments: int = 32,
) -> dict[str, dict[str, Any]]:
    """Suction anchor: shaft + lid + padeye + mooring line + ground."""
    R = diameter_m / 2.0
    L = skirt_length_m

    comp: dict[str, dict[str, Any]] = {}

    body_v, body_f = _create_cylinder(R, L, n_segments, y_top=0.0)
    comp["anchor_body"] = {"vertices": body_v, "faces": body_f}

    lid_v, lid_f = _create_disc(R, n_segments, y_offset=0.0)
    comp["anchor_lid"] = {"vertices": lid_v, "faces": lid_f}

    pe_center = (R, -padeye_depth_m, 0.0)
    pe_v, pe_f = _create_sphere(0.3, pe_center, n_segments=12)
    comp["padeye"] = {"vertices": pe_v, "faces": pe_f}

    catenary_pts = _compute_catenary(
        anchor_point=pe_center,
        angle_deg=mooring_angle_deg,
        length_m=mooring_length_m,
        n_points=50,
    )
    comp["mooring_line"] = {
        "type": "line",
        "points": catenary_pts,
        "color": [1.0, 0.8, 0.0],
        "linewidth": 3,
    }

    soil_v, soil_f = _create_ground_plane(
        extent=5.0 * R, n_segments=16, y_offset=0.0,
    )
    comp["soil_surface"] = {"vertices": soil_v, "faces": soil_f}

    return comp


def generate_tripod_mesh(
    bucket_diameter_m: float,
    bucket_length_m: float,
    tripod_spacing_m: float,
    tower_height_m: float,
    scour_depth_m: float = 0.0,
    n_segments: int = 24,
) -> dict[str, dict[str, Any]]:
    """Three buckets at 120 degrees + braces + tower + nacelle."""
    comp: dict[str, dict[str, Any]] = {}
    angles = [0.0, 120.0, 240.0]

    for i, ang in enumerate(angles):
        x = tripod_spacing_m * np.cos(np.radians(ang))
        z = tripod_spacing_m * np.sin(np.radians(ang))
        bucket = generate_suction_bucket_mesh(
            bucket_diameter_m, bucket_length_m,
            scour_depth_m=scour_depth_m,
            n_segments=n_segments,
        )
        for key, sub in bucket.items():
            if "vertices" in sub:
                sub_t = dict(sub)
                sub_t["vertices"] = _translate(sub["vertices"], (x, 0.0, z))
                comp[f"bucket_{i}_{key}"] = sub_t

        comp[f"brace_{i}"] = {
            "type": "line",
            "points": [[x, 0.0, z],
                       [0.0, tower_height_m * 0.3, 0.0]],
            "color": [0.7, 0.7, 0.7],
            "linewidth": 5,
        }

    tower_v, tower_f = _create_cylinder(
        2.5, tower_height_m, n_segments, y_top=tower_height_m,
    )
    comp["tower"] = {"vertices": tower_v, "faces": tower_f}

    nac_v, nac_f = _create_box(
        (8.0, 4.0, 4.0), (0.0, tower_height_m + 2.0, 0.0),
    )
    comp["nacelle"] = {"vertices": nac_v, "faces": nac_f}

    comp["sea_surface"] = {
        "type": "water_plane",
        "extent": tripod_spacing_m * 4,
        "y_offset": bucket_length_m + 10.0,
        "opacity": 0.3,
        "color": [0.1, 0.4, 0.8],
    }

    return comp
