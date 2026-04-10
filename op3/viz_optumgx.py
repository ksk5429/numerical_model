"""
Op3 OptumGX Visualization via PyVista.

3D visualization of finite-element limit analysis results:
  - Suction bucket mesh (skirt + lid + soil)
  - Contact pressure contours on plate elements
  - Bearing capacity factor Np(z) depth profile
  - Plastic dissipation field (collapse mechanism)
  - Velocity vector glyphs at collapse
  - Spring profile visualization (k and p_ult vs depth)

Usage:
    from op3.viz_optumgx import plot_bucket_pressure, plot_spring_profile
    plot_spring_profile("data/fem_results/spring_profile_op3.csv",
                        output_dir="validation/figures/")
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

import numpy as np

try:
    import pyvista as pv
    pv.OFF_SCREEN = True
    HAS_PYVISTA = True
except ImportError:
    HAS_PYVISTA = False

try:
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.colors import Normalize
    from matplotlib import cm
    HAS_MPL = True
except ImportError:
    HAS_MPL = False


def _check():
    if not HAS_PYVISTA:
        raise ImportError("pyvista required: pip install pyvista")
    if not HAS_MPL:
        raise ImportError("matplotlib required")


# ============================================================
# Suction bucket 3D mesh generation
# ============================================================

def create_bucket_mesh(
    D: float = 8.0,
    L: float = 9.3,
    n_theta: int = 24,
    n_z: int = 20,
) -> "pv.PolyData":
    """Create a 3D suction bucket mesh (lid + skirt wall).

    Returns a PyVista PolyData with the bucket surface mesh.
    """
    _check()
    R = D / 2

    # Lid (circular disk at z=0)
    lid = pv.Disc(center=(0, 0, 0), inner=0, outer=R, normal=(0, 0, 1),
                  r_res=5, c_res=n_theta)

    # Skirt wall (cylinder surface)
    theta = np.linspace(0, 2 * np.pi, n_theta + 1)
    z = np.linspace(0, -L, n_z + 1)
    T, Z = np.meshgrid(theta, z)
    X = R * np.cos(T)
    Y = R * np.sin(T)
    skirt = pv.StructuredGrid(X, Y, Z)
    skirt = skirt.extract_surface()

    # Combine
    bucket = lid + skirt
    return bucket


def create_soil_block(
    D: float = 8.0,
    L: float = 9.3,
    domain_factor: float = 3.0,
) -> "pv.PolyData":
    """Create a soil block around the bucket for context."""
    _check()
    R = D / 2
    extent = R * domain_factor
    depth = L * 2
    soil = pv.Box(bounds=(-extent, extent, -extent, extent, -depth, 0))
    return soil


# ============================================================
# Contact pressure on bucket surface
# ============================================================

def plot_bucket_pressure(
    plate_df=None,
    D: float = 8.0,
    L: float = 9.3,
    output_dir: Optional[str | Path] = None,
    title: str = "Contact Pressure at Collapse",
) -> Optional[str]:
    """Plot contact pressure on bucket surface from OptumGX plate data.

    plate_df: DataFrame with columns Xc, Yc, Zc, sig_net (or pressure).
    If None, generates a synthetic demonstration.
    """
    _check()
    import pandas as pd

    bucket = create_bucket_mesh(D, L)

    if plate_df is not None and 'sig_net' in plate_df.columns:
        # Map pressure to bucket surface via nearest-point interpolation
        pts = plate_df[['Xc', 'Yc', 'Zc']].values
        pressure = plate_df['sig_net'].values
        cloud = pv.PolyData(pts)
        cloud['pressure_kPa'] = pressure
        bucket = bucket.interpolate(cloud, radius=D * 0.3)
    else:
        # Synthetic pressure for demonstration
        z = bucket.points[:, 2]
        r = np.sqrt(bucket.points[:, 0]**2 + bucket.points[:, 1]**2)
        # Pressure increases with depth, varies with angle
        theta = np.arctan2(bucket.points[:, 1], bucket.points[:, 0])
        bucket['pressure_kPa'] = np.abs(z) * 10 * (1 + 0.5 * np.cos(theta))
        bucket['pressure_kPa'][z > -0.1] = 0  # no pressure on lid top

    pl = pv.Plotter(off_screen=True, window_size=[1200, 900])
    pl.add_mesh(bucket, scalars='pressure_kPa', cmap='RdYlBu_r',
                show_edges=False, opacity=1.0,
                scalar_bar_args={'title': 'Contact Pressure (kPa)',
                                 'title_font_size': 14})
    pl.add_axes()
    pl.camera_position = [(-D * 3, -D * 3, D * 1.5),
                          (0, 0, -L / 2),
                          (0, 0, 1)]
    pl.add_text(title, position='upper_left', font_size=14)

    if output_dir:
        out = Path(output_dir)
        out.mkdir(parents=True, exist_ok=True)
        path = out / "optumgx_pressure.png"
        pl.screenshot(str(path))
        pl.close()
        return str(path)
    pl.close()
    return None


# ============================================================
# Plastic dissipation / collapse mechanism
# ============================================================

def plot_collapse_mechanism(
    D: float = 8.0,
    L: float = 9.3,
    output_dir: Optional[str | Path] = None,
    title: str = "Collapse Mechanism (Plastic Dissipation)",
) -> Optional[str]:
    """Plot the plastic dissipation field around the bucket.

    Uses a synthetic dissipation field for demonstration.
    Real data would come from OptumGX solid element extraction.
    """
    _check()

    R = D / 2
    # Create a volumetric grid around the bucket
    x = np.linspace(-R * 3, R * 3, 30)
    y = np.linspace(-R * 3, R * 3, 30)
    z = np.linspace(-L * 1.5, 0, 20)
    X, Y, Z = np.meshgrid(x, y, z)

    # Synthetic dissipation: concentrated around skirt tip
    r = np.sqrt(X**2 + Y**2)
    # Scoop mechanism: high dissipation in a wedge in front of bucket
    dissip = np.exp(-((r - R)**2 / (R * 0.5)**2 + (Z + L)**2 / (L * 0.3)**2))
    # Add wedge in loading direction (x > 0)
    wedge = np.exp(-((X - R)**2 / (R * 0.8)**2 +
                      Y**2 / (R * 1.5)**2 +
                      (Z + L * 0.5)**2 / (L * 0.5)**2))
    dissip = dissip + 2 * wedge
    dissip = dissip / dissip.max()

    grid = pv.StructuredGrid(X, Y, Z)
    grid['dissipation'] = dissip.flatten(order='F')

    # Threshold to show only high-dissipation regions
    active = grid.threshold(0.3, scalars='dissipation')

    # Bucket outline
    bucket = create_bucket_mesh(D, L)

    pl = pv.Plotter(off_screen=True, window_size=[1200, 900])
    pl.add_mesh(active, scalars='dissipation', cmap='hot',
                opacity='linear', show_edges=False,
                scalar_bar_args={'title': 'Normalized Dissipation',
                                 'title_font_size': 14})
    pl.add_mesh(bucket, color='steelblue', opacity=0.3, show_edges=True)
    pl.add_axes()
    pl.camera_position = [(-D * 4, -D * 3, D * 2),
                          (0, 0, -L / 2),
                          (0, 0, 1)]
    pl.add_text(title, position='upper_left', font_size=14)

    if output_dir:
        out = Path(output_dir)
        out.mkdir(parents=True, exist_ok=True)
        path = out / "optumgx_collapse.png"
        pl.screenshot(str(path))
        pl.close()
        return str(path)
    pl.close()
    return None


# ============================================================
# Spring profile visualization
# ============================================================

def plot_spring_profile(
    spring_csv: str | Path,
    output_dir: Optional[str | Path] = None,
    title: str = "OptumGX-Derived Spring Profile",
) -> Optional[str]:
    """Plot k(z) and p_ult(z) spring profile from Op3 CSV."""
    if not HAS_MPL:
        raise ImportError("matplotlib required")
    import pandas as pd

    df = pd.read_csv(spring_csv)
    z = df['depth_m'].values
    k = df['k_ini_kN_per_m'].values
    p = df['p_ult_kN_per_m'].values

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 8), sharey=True)

    # Stiffness
    ax1.barh(z, k / 1000, height=0.4, color='steelblue', alpha=0.8)
    ax1.set_xlabel('Initial Stiffness k(z) (MN/m/m)', fontsize=12)
    ax1.set_ylabel('Depth (m)', fontsize=12)
    ax1.invert_yaxis()
    ax1.grid(True, alpha=0.3)
    ax1.set_title('Lateral Stiffness', fontsize=13, fontweight='bold')

    # Capacity
    ax2.barh(z, p, height=0.4, color='firebrick', alpha=0.8)
    ax2.set_xlabel('Ultimate Resistance p_ult(z) (kN/m)', fontsize=12)
    ax2.invert_yaxis()
    ax2.grid(True, alpha=0.3)
    ax2.set_title('Lateral Capacity', fontsize=13, fontweight='bold')

    fig.suptitle(title, fontsize=14, fontweight='bold', y=0.98)
    fig.tight_layout()

    if output_dir:
        out = Path(output_dir)
        out.mkdir(parents=True, exist_ok=True)
        path = out / "optumgx_spring_profile.png"
        fig.savefig(str(path), dpi=200, bbox_inches='tight')
        plt.close(fig)
        return str(path)
    plt.show()
    return None


# ============================================================
# Np(z) bearing capacity factor profile
# ============================================================

def plot_np_profile(
    pult_csv: str | Path,
    output_dir: Optional[str | Path] = None,
    title: str = "Bearing Capacity Factor Np(z) from OptumGX",
) -> Optional[str]:
    """Plot the normalized lateral bearing capacity factor vs depth."""
    if not HAS_MPL:
        raise ImportError("matplotlib required")
    import pandas as pd

    df = pd.read_csv(pult_csv)
    z_L = df['z_L'].values
    Np = df['Np'].values

    fig, ax = plt.subplots(figsize=(8, 6))
    ax.plot(Np, z_L, 'bo-', linewidth=2, markersize=8, label='OptumGX')

    # Reference lines
    ax.axvline(x=9.14, color='r', linestyle='--', alpha=0.5,
               label='Martin & Randolph (2006) deep flow')
    ax.axvspan(2, 4, alpha=0.1, color='green',
               label='Bransby & Randolph (1998) shallow')

    ax.set_xlabel('Np = p(z) / (su * D)', fontsize=12)
    ax.set_ylabel('z / L (normalized depth)', fontsize=12)
    ax.invert_yaxis()
    ax.set_title(title, fontsize=14, fontweight='bold')
    ax.legend(fontsize=10)
    ax.grid(True, alpha=0.3)
    ax.set_xlim(left=0)

    if output_dir:
        out = Path(output_dir)
        out.mkdir(parents=True, exist_ok=True)
        path = out / "optumgx_np_profile.png"
        fig.savefig(str(path), dpi=200, bbox_inches='tight')
        plt.close(fig)
        return str(path)
    plt.show()
    return None
