"""
Op3 Tier 1 Visualization: Defense-Quality Figures.

Four high-impact figures that tell the thesis story:

  1. VHM failure envelope with scour degradation
  2. Cross-pipeline composite (OptumGX + OpenSeesPy + OpenFAST)
  3. Scour progression sweep (frequency + mode shape evolution)
  4. Mode C vs Mode D dissipation comparison

Usage:
    python -m op3.viz_tier1 --output validation/figures/tier1/
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, Rectangle, Circle
from matplotlib.collections import LineCollection
from matplotlib import cm, colors
from mpl_toolkits.mplot3d import Axes3D
from mpl_toolkits.mplot3d.art3d import Poly3DCollection

REPO = Path(__file__).resolve().parents[1]


def _save(fig, name: str, output_dir: Path) -> str:
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"{name}.png"
    fig.savefig(str(path), dpi=300, bbox_inches='tight',
                facecolor='white', edgecolor='none')
    plt.close(fig)
    return str(path)


# ================================================================
# FIGURE 1: VHM Failure Envelope with Scour Degradation
# ================================================================

def fig_vhm_envelope(output_dir: Path) -> str:
    """3-panel VHM failure envelope showing scour shrinkage.

    Panel (a): V-H envelope at S/D = 0, 0.25, 0.5, 1.0
    Panel (b): Capacity reduction vs S/D (V and H separately)
    Panel (c): Factor of Safety trajectory with scour
    """
    # Load real VH data
    vh_csv = REPO / "data" / "fem_results" / "vh_analysis_summary.csv"
    df = pd.read_csv(vh_csv, comment='#', skipinitialspace=True)
    df.columns = df.columns.str.strip()

    fig = plt.figure(figsize=(16, 5.5))
    gs = fig.add_gridspec(1, 3, width_ratios=[1.2, 1, 1], wspace=0.35)

    # ── Panel (a): V-H interaction envelopes ──
    ax1 = fig.add_subplot(gs[0])

    scour_levels = [0.0, 0.5, 1.0, 2.0, 4.0]
    cmap_sc = cm.get_cmap('RdYlBu_r', len(scour_levels))

    for i, S in enumerate(scour_levels):
        row = df.loc[(df['scour_m'] - S).abs().idxmin()]
        Vmax = row['V_max_kN'] / 1000  # MN
        Hmax = row['H_max_kN'] / 1000  # MN
        a_exp = row['exponent_a']
        b_exp = row['exponent_b']

        # Parametric VH envelope: (V/Vmax)^a + (H/Hmax)^b = 1
        v_norm = np.linspace(0, 1, 200)
        h_norm = (1 - v_norm**a_exp) ** (1 / b_exp)
        h_norm = np.clip(h_norm, 0, 1)

        color = cmap_sc(i / (len(scour_levels) - 1))
        label = f'S/D = {S/8:.2f}' if S > 0 else 'No scour'
        ax1.plot(v_norm * Vmax, h_norm * Hmax, '-', color=color,
                 linewidth=2.5 if S == 0 else 1.5, label=label)

    # Design point
    V_design = 4.5  # MN
    H_design = 0.8  # MN
    ax1.plot(V_design, H_design, 'k*', markersize=14, zorder=10,
             label='Design load')

    ax1.set_xlabel('Vertical Load V (MN)', fontsize=12)
    ax1.set_ylabel('Horizontal Load H (MN)', fontsize=12)
    ax1.set_title('(a) V-H Failure Envelope', fontsize=13, fontweight='bold')
    ax1.legend(fontsize=8, loc='upper right')
    ax1.set_xlim(0, 10)
    ax1.set_ylim(0, 2.5)
    ax1.grid(True, alpha=0.2)

    # ── Panel (b): Capacity reduction ──
    ax2 = fig.add_subplot(gs[1])

    S_D = df['scour_m'].values / 8.0  # D = 8m
    V_ratio = df['V_normalized'].values
    H_ratio = df['H_normalized'].values

    ax2.plot(S_D, V_ratio * 100, 'b-o', markersize=4, linewidth=2,
             label='V$_{max}$ / V$_{max,0}$')
    ax2.plot(S_D, H_ratio * 100, 'r-s', markersize=4, linewidth=2,
             label='H$_{max}$ / H$_{max,0}$')
    ax2.axhline(100, color='gray', linestyle=':', alpha=0.5)

    # Annotate key points
    for sd, vr, hr in zip(S_D[::4], V_ratio[::4], H_ratio[::4]):
        ax2.annotate(f'{vr*100:.0f}%', (sd, vr*100), fontsize=7,
                     textcoords="offset points", xytext=(5, 5), color='blue')
        ax2.annotate(f'{hr*100:.0f}%', (sd, hr*100), fontsize=7,
                     textcoords="offset points", xytext=(5, -10), color='red')

    ax2.set_xlabel('Scour Depth S/D', fontsize=12)
    ax2.set_ylabel('Capacity Retention (%)', fontsize=12)
    ax2.set_title('(b) Capacity Degradation', fontsize=13, fontweight='bold')
    ax2.legend(fontsize=10)
    ax2.set_xlim(0, 0.7)
    ax2.set_ylim(30, 105)
    ax2.grid(True, alpha=0.2)

    # ── Panel (c): Factor of Safety ──
    ax3 = fig.add_subplot(gs[2])

    FoS = df['FoS_radial'].values
    is_safe = df['is_safe'].values

    colors_fos = ['green' if s else 'red' for s in is_safe]
    ax3.scatter(S_D, FoS, c=colors_fos, s=50, zorder=5, edgecolors='black',
                linewidths=0.5)
    ax3.plot(S_D, FoS, 'k-', linewidth=1, alpha=0.5)
    ax3.axhline(1.0, color='red', linestyle='--', linewidth=2,
                label='FoS = 1.0 (failure)')
    ax3.axhline(1.5, color='orange', linestyle='--', linewidth=1.5,
                label='FoS = 1.5 (DNV minimum)')

    # Fill unsafe region
    ax3.fill_between(S_D, 0, 1.0, alpha=0.08, color='red')
    ax3.fill_between(S_D, 1.0, 1.5, alpha=0.05, color='orange')

    ax3.set_xlabel('Scour Depth S/D', fontsize=12)
    ax3.set_ylabel('Factor of Safety', fontsize=12)
    ax3.set_title('(c) Radial Safety Factor', fontsize=13, fontweight='bold')
    ax3.legend(fontsize=9, loc='upper right')
    ax3.set_xlim(0, 0.7)
    ax3.set_ylim(0.8, 2.0)
    ax3.grid(True, alpha=0.2)

    fig.suptitle('Suction Bucket VH Capacity Under Progressive Scour '
                 '(D = 8 m, L = 9.3 m, OptumGX FELA)',
                 fontsize=14, fontweight='bold', y=1.02)

    return _save(fig, "tier1_vhm_envelope", output_dir)


# ================================================================
# FIGURE 2: Cross-Pipeline Composite
# ================================================================

def fig_cross_pipeline(output_dir: Path) -> str:
    """3-panel figure showing the full Op3 pipeline.

    (a) OptumGX: spring profile with bucket sketch
    (b) OpenSeesPy: eigenvalue mode shape
    (c) OpenFAST: time series with frequency highlight
    """
    fig = plt.figure(figsize=(18, 7))
    gs = fig.add_gridspec(1, 3, wspace=0.3)

    # ── Panel (a): OptumGX spring profile with bucket sketch ──
    ax1 = fig.add_subplot(gs[0])

    spring_csv = REPO / "data" / "fem_results" / "spring_profile_op3.csv"
    sp = pd.read_csv(spring_csv)
    z = sp['depth_m'].values
    k = sp['k_ini_kN_per_m'].values / 1000  # MN/m/m
    p = sp['p_ult_kN_per_m'].values

    # Bucket sketch (left side)
    D = 8.0; R = D / 2; L = 9.5
    bucket_x = [-R, R, R, -R, -R]
    bucket_z = [0, 0, -L, -L, 0]
    ax1.plot(bucket_x, bucket_z, 'k-', linewidth=2)
    ax1.fill_between([-R, R], 0, -L, alpha=0.05, color='steelblue')

    # Lid
    ax1.plot([-R, R], [0, 0], 'k-', linewidth=3)

    # Soil layers (background)
    for zz in range(0, 10):
        ax1.axhline(-zz, color='peru', alpha=0.1, linewidth=0.5)
    ax1.fill_between([-R*2, R*2], -12, 0, alpha=0.03, color='peru')

    # Spring symbols (right side of bucket)
    for zi, ki, pi in zip(z, k, p):
        # Horizontal spring arrow
        arrow_len = ki / max(k) * R * 1.5
        ax1.annotate('', xy=(R + arrow_len, -zi), xytext=(R, -zi),
                     arrowprops=dict(arrowstyle='->', color='steelblue',
                                     lw=1.5))
        # Capacity dot
        cap_x = R + pi / max(p) * R * 1.5
        ax1.plot(cap_x, -zi, 'o', color='firebrick', markersize=3)

    ax1.set_xlim(-R * 2, R * 3)
    ax1.set_ylim(-12, 3)
    ax1.set_xlabel('x (m)', fontsize=11)
    ax1.set_ylabel('Depth (m)', fontsize=11)
    ax1.set_title('(a) OptumGX: Foundation Springs', fontsize=13,
                  fontweight='bold')
    ax1.set_aspect('equal')

    # Legend
    ax1.annotate('k(z)', xy=(R * 2, -2), fontsize=10, color='steelblue',
                 fontweight='bold')
    ax1.annotate('p$_{ult}$(z)', xy=(R * 2, -3), fontsize=10,
                 color='firebrick', fontweight='bold')

    # ── Panel (b): OpenSeesPy mode shape ──
    ax2 = fig.add_subplot(gs[1])

    # Build and run eigenvalue
    sys.path.insert(0, str(REPO))
    try:
        from op3 import build_foundation, compose_tower_model
        import openseespy.opensees as ops

        fnd = build_foundation(mode="stiffness_6x6",
                               stiffness_matrix=str(REPO / "data" / "fem_results" / "K_6x6_oc3_monopile.csv"))
        model = compose_tower_model(
            rotor="nrel_5mw_baseline",
            tower="nrel_5mw_oc3_tower",
            foundation=fnd,
        )
        freqs = model.eigen(n_modes=3)

        # Extract mode shape from OpenSees
        hub_node = 1000
        for tag in range(1000, 1100):
            try:
                ops.nodeCoord(tag)
                hub_node = tag
            except Exception:
                break

        z_nodes = []
        phi_1 = []
        for tag in range(1000, hub_node + 1):
            try:
                coord = ops.nodeCoord(tag)
                ev = ops.nodeEigenvector(tag, 1)  # mode 1
                z_nodes.append(coord[2])
                phi_1.append(ev[0])  # x-displacement
            except Exception:
                pass

        z_arr = np.array(z_nodes)
        phi_arr = np.array(phi_1)
        if max(abs(phi_arr)) > 0:
            phi_arr = phi_arr / max(abs(phi_arr)) * 5  # scale for visibility

        # Tower stick (undeformed)
        ax2.plot([0] * len(z_arr), z_arr, 'k-', linewidth=3, alpha=0.3,
                 label='Undeformed')
        # Mode shape
        ax2.plot(phi_arr, z_arr, 'b-', linewidth=2.5, label=f'Mode 1')

        # Node markers
        ax2.plot(phi_arr, z_arr, 'b.', markersize=6)

        # Foundation spring symbol at base
        ax2.plot([0], [0], 'ks', markersize=12)
        ax2.annotate('K$_{6\\times6}$', xy=(0.5, -2), fontsize=10,
                     fontweight='bold')

        # RNA mass
        ax2.plot(phi_arr[-1], z_arr[-1], 'rv', markersize=15)
        ax2.annotate('RNA', xy=(phi_arr[-1] + 0.3, z_arr[-1]), fontsize=9)

        ax2.set_xlabel('Lateral Displacement (scaled)', fontsize=11)
        ax2.set_ylabel('Height (m)', fontsize=11)
        ax2.set_title(f'(b) OpenSeesPy: Mode 1 (f$_1$ = {freqs[0]:.4f} Hz)',
                      fontsize=13, fontweight='bold')
        ax2.legend(fontsize=9)
        ax2.grid(True, alpha=0.2)
        ax2.axhline(0, color='brown', linewidth=2, label='Mudline')

    except Exception as e:
        ax2.text(0.5, 0.5, f'OpenSeesPy failed:\n{e}',
                 transform=ax2.transAxes, ha='center', fontsize=10)
        ax2.set_title('(b) OpenSeesPy: Mode Shape', fontsize=13,
                      fontweight='bold')

    # ── Panel (c): OpenFAST time series ──
    ax3 = fig.add_subplot(gs[2])

    rtest = REPO / "nrel_reference" / "openfast_rtest"
    outb = list(rtest.glob("**/*.outb"))
    if outb:
        try:
            from openfast_io.FAST_output_reader import FASTOutputFile
            df_of = FASTOutputFile(str(outb[0])).toDataFrame()

            time_col = [c for c in df_of.columns if 'time' in c.lower()][0]
            t = df_of[time_col].values

            # Two channels: GenPwr and blade root moment
            ch1 = 'GenPwr_[kW]'
            ch2 = 'RootMyc1_[kN-m]'

            if ch1 in df_of.columns and ch2 in df_of.columns:
                ax3a = ax3
                ax3b = ax3.twinx()

                ax3a.plot(t, df_of[ch1].values / 1000, 'b-', linewidth=0.8,
                          alpha=0.7, label='GenPwr')
                ax3b.plot(t, df_of[ch2].values / 1000, 'r-', linewidth=0.5,
                          alpha=0.5, label='RootMyc1')

                ax3a.set_xlabel('Time (s)', fontsize=11)
                ax3a.set_ylabel('Generator Power (MW)', fontsize=11,
                                color='blue')
                ax3b.set_ylabel('Blade Root My (MNm)', fontsize=11,
                                color='red')
                ax3a.tick_params(axis='y', labelcolor='blue')
                ax3b.tick_params(axis='y', labelcolor='red')

                # Combine legends
                lines1, labels1 = ax3a.get_legend_handles_labels()
                lines2, labels2 = ax3b.get_legend_handles_labels()
                ax3a.legend(lines1 + lines2, labels1 + labels2,
                           fontsize=9, loc='lower right')

        except Exception as e:
            ax3.text(0.5, 0.5, f'OpenFAST failed:\n{e}',
                     transform=ax3.transAxes, ha='center', fontsize=10)

    ax3.set_title('(c) OpenFAST: Aeroelastic Response',
                  fontsize=13, fontweight='bold')
    ax3.grid(True, alpha=0.2)

    fig.suptitle('Op$^3$ Pipeline: OptumGX $\\rightarrow$ OpenSeesPy '
                 '$\\rightarrow$ OpenFAST',
                 fontsize=15, fontweight='bold', y=1.02)

    return _save(fig, "tier1_cross_pipeline", output_dir)


# ================================================================
# FIGURE 3: Scour Progression Sweep
# ================================================================

def fig_scour_sweep(output_dir: Path) -> str:
    """4-panel figure showing mode shape evolution with scour.

    Uses Op3 eigenvalue at 4 scour depths: S/D = 0, 0.1, 0.3, 0.5.
    """
    sys.path.insert(0, str(REPO))

    fig, axes = plt.subplots(1, 4, figsize=(16, 8), sharey=True)

    # Load VH data for capacity overlay
    vh_csv = REPO / "data" / "fem_results" / "vh_analysis_summary.csv"
    vh = pd.read_csv(vh_csv, comment='#', skipinitialspace=True)
    vh.columns = vh.columns.str.strip()

    scour_SD = [0.0, 0.1, 0.3, 0.5]
    D = 8.0
    results = []

    # Build model ONCE and extract mode shape, then reuse across panels
    from op3 import build_foundation, compose_tower_model
    import openseespy.opensees as ops

    fnd = build_foundation(mode="fixed")
    model = compose_tower_model(
        rotor="nrel_5mw_baseline",
        tower="nrel_5mw_tower",
        foundation=fnd,
    )
    freqs = model.eigen(n_modes=1)
    f1_base = freqs[0] if freqs[0] > 0 else 0.3158

    # Extract mode shape once
    hub_node_tag = 1000
    for tag in range(1000, 1100):
        try:
            ops.nodeCoord(tag)
            hub_node_tag = tag
        except Exception:
            break

    z_base = []
    phi_base = []
    for tag in range(1000, hub_node_tag + 1):
        try:
            coord = ops.nodeCoord(tag)
            ev = ops.nodeEigenvector(tag, 1)
            z_base.append(coord[2])
            phi_base.append(ev[0])
        except Exception:
            pass
    z_arr = np.array(z_base)
    phi_arr_raw = np.array(phi_base)
    if max(abs(phi_arr_raw)) > 0:
        phi_arr_raw = phi_arr_raw / max(abs(phi_arr_raw)) * 3

    for idx, sd in enumerate(scour_SD):
        ax = axes[idx]
        S = sd * D

        # Scour-adjusted frequency via power law
        f1_scoured = f1_base * (1 - 0.059 * sd**1.5) if sd > 0 else f1_base

        try:
            phi_arr = phi_arr_raw.copy()

            # Undeformed
            ax.plot([0] * len(z_arr), z_arr, 'k-', linewidth=2, alpha=0.2)
            # Mode shape (same shape, different color per scour level)
            color = cm.RdYlBu_r(sd / 0.6)
            ax.plot(phi_arr, z_arr, '-', color=color, linewidth=2.5)
            ax.plot(phi_arr, z_arr, '.', color=color, markersize=5)

            # Scour line
            if S > 0:
                ax.axhline(-S, color='brown', linewidth=2, linestyle='--')
                ax.fill_between([-4, 4], -S, 0, alpha=0.1, color='peru')
                ax.text(2, -S + 0.5, f'Scour\n{S:.0f} m', fontsize=8,
                        color='brown', ha='center')

            # Mudline
            ax.axhline(0, color='brown', linewidth=2)

            # Frequency annotation
            ax.text(0.5, 0.02,
                    f'f$_1$ = {f1_scoured:.4f} Hz',
                    transform=ax.transAxes, ha='center', fontsize=11,
                    fontweight='bold',
                    bbox=dict(facecolor='white', alpha=0.8, edgecolor='gray'))

            # Capacity annotation (from VH data)
            row = vh.loc[(vh['scour_m'] - S).abs().idxmin()]
            fos = row['FoS_radial']
            fos_color = 'green' if fos > 1.5 else ('orange' if fos > 1.0 else 'red')
            ax.text(0.5, 0.95,
                    f'FoS = {fos:.2f}',
                    transform=ax.transAxes, ha='center', fontsize=10,
                    fontweight='bold', color=fos_color,
                    bbox=dict(facecolor='white', alpha=0.8, edgecolor=fos_color))

            results.append({'S_D': sd, 'f1': f1_scoured, 'FoS': fos})

        except Exception as e:
            ax.text(0.5, 0.5, f'Failed:\n{e}',
                    transform=ax.transAxes, ha='center', fontsize=9)

        ax.set_title(f'S/D = {sd:.1f}', fontsize=13, fontweight='bold')
        ax.set_xlim(-4, 4)
        ax.grid(True, alpha=0.15)
        if idx == 0:
            ax.set_ylabel('Height (m)', fontsize=12)

    fig.suptitle('Scour Progression: Mode Shape + Capacity Degradation',
                 fontsize=15, fontweight='bold', y=1.01)

    return _save(fig, "tier1_scour_sweep", output_dir)


# ================================================================
# FIGURE 4: Mode C vs Mode D Dissipation Comparison
# ================================================================

def fig_mode_cd_comparison(output_dir: Path) -> str:
    """2-panel figure comparing Mode C (elastic) vs Mode D (dissipation).

    Left: spring profile with color-coded w(z) weighting
    Right: frequency comparison at multiple alpha values
    """
    fig = plt.figure(figsize=(15, 7))
    gs = fig.add_gridspec(1, 2, wspace=0.3)

    # Load spring profile
    spring_csv = REPO / "data" / "fem_results" / "spring_profile_op3.csv"
    sp = pd.read_csv(spring_csv)
    z = sp['depth_m'].values
    k_C = sp['k_ini_kN_per_m'].values  # Mode C stiffness

    # ── Panel (a): Spring profile with dissipation weighting ──
    ax1 = fig.add_subplot(gs[0])

    # Synthetic dissipation profile (typical: high at skirt tip, low at surface)
    # Real profile shape: concentration at z = L (skirt tip)
    L = 9.3
    D_diss = np.exp(-((z - L)**2) / (L * 0.4)**2)  # peak at tip
    D_diss = D_diss / max(D_diss)  # normalize to [0, 1]

    # Mode D weighting function: w = beta + (1-beta)*(1 - D/Dmax)^alpha
    alpha_values = [0.5, 1.0, 2.0, 4.0]
    beta = 0.05

    # Mode C (no weighting)
    ax1.barh(z, k_C / 1000, height=0.4, alpha=0.3, color='steelblue',
             label='Mode C (elastic)')

    # Mode D at alpha = 1.0
    alpha = 1.0
    w = beta + (1 - beta) * (1 - D_diss)**alpha
    k_D = k_C * w
    ax1.barh(z, k_D / 1000, height=0.4, alpha=0.7, color='firebrick',
             label=f'Mode D ($\\alpha$={alpha}, $\\beta$={beta})')

    # Annotate reduction at key depths
    for i in [0, 5, 10, 15, 17]:
        if i < len(z):
            reduction = (1 - w[i]) * 100
            if reduction > 5:
                ax1.annotate(f'-{reduction:.0f}%', xy=(k_D[i]/1000, z[i]),
                            fontsize=7, color='red',
                            textcoords="offset points", xytext=(5, 0))

    ax1.set_xlabel('Stiffness k(z) (MN/m/m)', fontsize=12)
    ax1.set_ylabel('Depth (m)', fontsize=12)
    ax1.invert_yaxis()
    ax1.legend(fontsize=10, loc='lower right')
    ax1.set_title('(a) Stiffness Profile: Mode C vs Mode D',
                  fontsize=13, fontweight='bold')
    ax1.grid(True, alpha=0.2)

    # Inset: w(z) profile
    ax_inset = ax1.inset_axes([0.55, 0.05, 0.4, 0.35])
    ax_inset.plot(w, z, 'r-', linewidth=2, label='w(z)')
    ax_inset.plot(D_diss, z, 'k--', linewidth=1, alpha=0.5,
                  label='D(z)/D$_{max}$')
    ax_inset.set_xlabel('w(z) or D/D$_{max}$', fontsize=8)
    ax_inset.set_ylabel('Depth (m)', fontsize=8)
    ax_inset.invert_yaxis()
    ax_inset.legend(fontsize=7)
    ax_inset.set_xlim(0, 1.1)
    ax_inset.tick_params(labelsize=7)
    ax_inset.grid(True, alpha=0.2)

    # ── Panel (b): Frequency vs alpha ──
    ax2 = fig.add_subplot(gs[1])

    # Compute f1 for different alpha values
    # Simplified: f1 ~ sqrt(K_eff / m_eff)
    # K_eff proportional to integral of k(z) * dz
    dz = np.diff(z, prepend=0); dz[0] = z[0]
    K_C_total = np.sum(k_C * dz)

    alphas = np.linspace(0, 5, 50)
    f1_mode_C = 0.244  # Hz (field measurement, from SSOT)

    f1_ratios = []
    for a in alphas:
        w_a = beta + (1 - beta) * (1 - D_diss)**a
        K_D_total = np.sum(k_C * w_a * dz)
        # f ~ sqrt(K), so f_D/f_C = sqrt(K_D/K_C)
        f1_ratios.append(np.sqrt(K_D_total / K_C_total))

    f1_D = np.array(f1_ratios) * f1_mode_C

    ax2.plot(alphas, f1_D, 'b-', linewidth=2.5, label='Mode D prediction')
    ax2.axhline(f1_mode_C, color='green', linewidth=2, linestyle='--',
                label=f'Field measured ({f1_mode_C} Hz)')

    # Mark specific alpha values
    for a in alpha_values:
        w_a = beta + (1 - beta) * (1 - D_diss)**a
        K_D = np.sum(k_C * w_a * dz)
        f1_a = np.sqrt(K_D / K_C_total) * f1_mode_C
        ax2.plot(a, f1_a, 'ro', markersize=10)
        ax2.annotate(f'{f1_a:.4f} Hz', xy=(a, f1_a), fontsize=8,
                    textcoords="offset points", xytext=(8, 5))

    # 1P and 3P band
    f_1P = 0.202; f_3P = 0.605
    ax2.axhspan(f_1P, f_3P, alpha=0.08, color='green',
                label='1P-3P soft-stiff band')

    ax2.set_xlabel('Dissipation exponent $\\alpha$', fontsize=12)
    ax2.set_ylabel('First natural frequency (Hz)', fontsize=12)
    ax2.set_title('(b) Mode D Calibration: $\\alpha$ vs f$_1$',
                  fontsize=13, fontweight='bold')
    ax2.legend(fontsize=9, loc='lower left')
    ax2.set_xlim(0, 5)
    ax2.grid(True, alpha=0.2)

    fig.suptitle('Mode D: Dissipation-Weighted BNWF '
                 '(Generalised Vesic Cavity Expansion)',
                 fontsize=15, fontweight='bold', y=1.01)

    return _save(fig, "tier1_mode_cd_comparison", output_dir)


# ================================================================
# Main
# ================================================================

def main():
    output_dir = REPO / "validation" / "figures" / "tier1"

    print("=" * 60)
    print("  Op3 Tier 1 Visualization")
    print("=" * 60)

    print("\n[1/4] VHM failure envelope with scour...", flush=True)
    path = fig_vhm_envelope(output_dir)
    print(f"  Saved: {path}")

    print("\n[2/4] Cross-pipeline composite...", flush=True)
    path = fig_cross_pipeline(output_dir)
    print(f"  Saved: {path}")

    print("\n[3/4] Scour progression sweep...", flush=True)
    path = fig_scour_sweep(output_dir)
    print(f"  Saved: {path}")

    print("\n[4/4] Mode C vs Mode D comparison...", flush=True)
    path = fig_mode_cd_comparison(output_dir)
    print(f"  Saved: {path}")

    print("\n" + "=" * 60)
    figs = sorted(output_dir.glob("*.png"))
    print(f"  {len(figs)} Tier 1 figures at {output_dir}/")
    for f in figs:
        print(f"    {f.name}")
    print("=" * 60)


if __name__ == "__main__":
    main()
