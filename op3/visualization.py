"""
Op3 Structural Visualization via opsvis.

Provides publication-quality figures of the OpenSeesPy model:
  - Model geometry (nodes, elements, supports)
  - Mode shapes from eigenvalue analysis
  - Pushover deformed shape
  - Section force diagrams (moment, shear, axial)

Usage:
    from op3 import build_foundation, compose_tower_model
    from op3.visualization import plot_all

    fnd = build_foundation(mode="fixed")
    model = compose_tower_model(rotor="nrel_5mw_baseline",
                                tower="nrel_5mw_tower",
                                foundation=fnd)
    freqs = model.eigen(n_modes=3)
    plot_all(model, freqs, output_dir="figures/")

All functions accept an optional `output_dir` to save PNG files.
If not provided, figures are displayed interactively (if backend allows).
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

import numpy as np

try:
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    HAS_MPL = True
except ImportError:
    HAS_MPL = False

try:
    import opsvis
    HAS_OPSVIS = True
except ImportError:
    HAS_OPSVIS = False


def _check_deps():
    if not HAS_MPL:
        raise ImportError("matplotlib is required for visualization")
    if not HAS_OPSVIS:
        raise ImportError("opsvis is required: pip install opsvis")


def _save_or_show(fig, name: str, output_dir: Optional[str | Path]):
    if output_dir:
        out = Path(output_dir)
        out.mkdir(parents=True, exist_ok=True)
        path = out / f"{name}.png"
        fig.savefig(str(path), dpi=200, bbox_inches='tight',
                    facecolor='white', edgecolor='none')
        plt.close(fig)
        return str(path)
    else:
        plt.show()
        return None


# ============================================================
# Model geometry
# ============================================================

def plot_model(
    output_dir: Optional[str | Path] = None,
    az_el: tuple[float, float] = (-60.0, 30.0),
    title: str = "Op3 Structural Model",
) -> Optional[str]:
    """Plot the OpenSeesPy model geometry (nodes, elements, supports).

    Must be called after model.eigen() or model.build() so the
    OpenSees domain is populated.
    """
    _check_deps()
    fig = plt.figure(figsize=(10, 12))
    ax = fig.add_subplot(111, projection='3d')

    opsvis.plot_model(
        node_labels=1,
        element_labels=0,
        offset_nd_label=False,
        az_el=az_el,
        local_axes=False,
        node_supports=True,
        ax=ax,
    )
    ax.set_title(title, fontsize=14, fontweight='bold')
    ax.set_xlabel('X (m)')
    ax.set_ylabel('Y (m)')
    ax.set_zlabel('Z (m)')

    return _save_or_show(fig, "op3_model", output_dir)


# ============================================================
# Mode shapes
# ============================================================

def plot_mode_shapes(
    n_modes: int = 3,
    output_dir: Optional[str | Path] = None,
    az_el: tuple[float, float] = (-60.0, 30.0),
    freqs: Optional[list[float]] = None,
) -> list[Optional[str]]:
    """Plot mode shapes from eigenvalue analysis.

    Must be called after model.eigen(n_modes >= n_modes).
    """
    _check_deps()
    paths = []

    for mode in range(1, n_modes + 1):
        fig = plt.figure(figsize=(8, 12))
        ax = fig.add_subplot(111, projection='3d')

        try:
            opsvis.plot_mode_shape(
                mode,
                sfac=False,
                nep=17,
                unDefoFlag=1,
                endDispFlag=1,
                az_el=az_el,
                node_supports=True,
                ax=ax,
            )
        except Exception as e:
            ax.text2D(0.5, 0.5, f"Mode {mode} failed:\n{e}",
                      transform=ax.transAxes, ha='center', fontsize=10)

        freq_str = f" (f = {freqs[mode-1]:.4f} Hz)" if freqs and len(freqs) >= mode else ""
        ax.set_title(f"Mode {mode}{freq_str}",
                     fontsize=14, fontweight='bold')
        ax.set_xlabel('X (m)')
        ax.set_ylabel('Y (m)')
        ax.set_zlabel('Z (m)')

        path = _save_or_show(fig, f"op3_mode_{mode}", output_dir)
        paths.append(path)

    return paths


# ============================================================
# Deformed shape (after pushover or static)
# ============================================================

def plot_deformed(
    scale_factor: float = 0.0,
    output_dir: Optional[str | Path] = None,
    az_el: tuple[float, float] = (-60.0, 30.0),
    title: str = "Deformed Shape",
) -> Optional[str]:
    """Plot deformed shape after a static analysis (pushover, etc.).

    scale_factor=0 means auto-scale.
    """
    _check_deps()
    fig = plt.figure(figsize=(10, 12))
    ax = fig.add_subplot(111, projection='3d')

    sfac = scale_factor if scale_factor > 0 else False
    opsvis.plot_defo(
        sfac=sfac,
        nep=17,
        unDefoFlag=1,
        interpFlag=1,
        az_el=az_el,
        node_supports=True,
        ax=ax,
    )
    ax.set_title(title, fontsize=14, fontweight='bold')
    ax.set_xlabel('X (m)')
    ax.set_ylabel('Y (m)')
    ax.set_zlabel('Z (m)')

    return _save_or_show(fig, "op3_deformed", output_dir)


# ============================================================
# Section forces
# ============================================================

def plot_section_forces(
    force_type: str = "Mz",
    output_dir: Optional[str | Path] = None,
    az_el: tuple[float, float] = (-60.0, 30.0),
    title: Optional[str] = None,
) -> Optional[str]:
    """Plot section force diagram after static analysis.

    force_type: 'N' (axial), 'Vy'/'Vz' (shear), 'My'/'Mz' (moment), 'T' (torsion)
    """
    _check_deps()
    fig = plt.figure(figsize=(10, 12))
    ax = fig.add_subplot(111, projection='3d')

    try:
        opsvis.section_force_diagram_3d(
            force_type,
            sfac=1.0,
            nep=17,
            dir_plt=0,
            node_supports=True,
            ax=ax,
        )
    except Exception as e:
        ax.text2D(0.5, 0.5, f"Section force {force_type} failed:\n{e}",
                  transform=ax.transAxes, ha='center', fontsize=10)

    if title is None:
        title = f"Section Force: {force_type}"
    ax.set_title(title, fontsize=14, fontweight='bold')
    ax.set_xlabel('X (m)')
    ax.set_ylabel('Y (m)')
    ax.set_zlabel('Z (m)')

    return _save_or_show(fig, f"op3_secforce_{force_type}", output_dir)


# ============================================================
# Pushover curve
# ============================================================

def plot_pushover_curve(
    pushover_result: dict,
    output_dir: Optional[str | Path] = None,
    title: str = "Pushover Curve",
) -> Optional[str]:
    """Plot force-displacement from pushover analysis."""
    _check_deps()

    disp = pushover_result.get("displacement_m", [])
    force = pushover_result.get("reaction_kN", [])
    if not disp or not force:
        return None

    fig, ax = plt.subplots(figsize=(10, 6))
    ax.plot(np.array(disp) * 1000, np.array(force) / 1000,
            'b-', linewidth=2)
    ax.set_xlabel('Hub Displacement (mm)', fontsize=12)
    ax.set_ylabel('Lateral Force (MN)', fontsize=12)
    ax.set_title(title, fontsize=14, fontweight='bold')
    ax.grid(True, alpha=0.3)
    ax.set_xlim(left=0)
    ax.set_ylim(bottom=0)

    return _save_or_show(fig, "op3_pushover_curve", output_dir)


# ============================================================
# Moment-rotation curve
# ============================================================

def plot_moment_rotation(
    mr_result: dict,
    output_dir: Optional[str | Path] = None,
    title: str = "Moment-Rotation at Foundation Head",
    ref_My: Optional[float] = None,
    ref_theta_y: Optional[float] = None,
) -> Optional[str]:
    """Plot M-theta from moment-rotation analysis."""
    _check_deps()

    theta = mr_result.get("rotation_deg", [])
    moment = mr_result.get("moment_MNm", [])
    if not theta or not moment:
        return None

    fig, ax = plt.subplots(figsize=(10, 6))
    ax.plot(theta, moment, 'b-', linewidth=2, label='Op3')

    if ref_My is not None and ref_theta_y is not None:
        ax.plot(ref_theta_y, ref_My, 'rs', markersize=12,
                label=f'Reference (My={ref_My} MNm)')
        ax.axhline(ref_My, color='r', linestyle='--', alpha=0.3)
        ax.axvline(ref_theta_y, color='r', linestyle='--', alpha=0.3)

    ax.set_xlabel('Rotation (deg)', fontsize=12)
    ax.set_ylabel('Moment (MNm)', fontsize=12)
    ax.set_title(title, fontsize=14, fontweight='bold')
    ax.legend(fontsize=11)
    ax.grid(True, alpha=0.3)
    ax.set_xlim(left=0)
    ax.set_ylim(bottom=0)

    return _save_or_show(fig, "op3_moment_rotation", output_dir)


# ============================================================
# Multi-panel summary
# ============================================================

def plot_all(
    model=None,
    freqs: Optional[list[float]] = None,
    pushover_result: Optional[dict] = None,
    mr_result: Optional[dict] = None,
    output_dir: Optional[str | Path] = None,
    n_modes: int = 3,
) -> dict[str, Optional[str]]:
    """Generate all available visualization figures.

    Returns a dict of {name: filepath_or_None}.
    """
    _check_deps()
    paths = {}

    # 1. Model geometry
    try:
        paths["model"] = plot_model(output_dir=output_dir)
    except Exception as e:
        print(f"  [WARN] Model plot failed: {e}")
        paths["model"] = None

    # 2. Mode shapes
    if freqs is not None:
        try:
            mode_paths = plot_mode_shapes(
                n_modes=min(n_modes, len(freqs)),
                output_dir=output_dir,
                freqs=freqs,
            )
            for i, p in enumerate(mode_paths, 1):
                paths[f"mode_{i}"] = p
        except Exception as e:
            print(f"  [WARN] Mode shape plot failed: {e}")

    # 3. Pushover curve
    if pushover_result:
        try:
            paths["pushover"] = plot_pushover_curve(
                pushover_result, output_dir=output_dir)
        except Exception as e:
            print(f"  [WARN] Pushover curve failed: {e}")

    # 4. Moment-rotation
    if mr_result:
        try:
            paths["moment_rotation"] = plot_moment_rotation(
                mr_result, output_dir=output_dir)
        except Exception as e:
            print(f"  [WARN] M-theta plot failed: {e}")

    return paths
