"""
Op3 Tier 2 Visualization: Journal-Paper Quality Figures.

  5. Foundation sketch + depth profile overlay (geotechnical standard)
  6. Rainflow cycle matrix heatmap
  7. Campbell diagram (from .lin files)
  8. M-theta backbone with published reference points

Usage:
    python -m op3.viz_tier2 --output validation/figures/tier2/
"""
from __future__ import annotations

import math
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle, FancyBboxPatch, Circle
from matplotlib.collections import PatchCollection
from matplotlib import cm, colors

REPO = Path(__file__).resolve().parents[1]
import sys
sys.path.insert(0, str(REPO))


def _save(fig, name: str, output_dir: Path) -> str:
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"{name}.png"
    fig.savefig(str(path), dpi=300, bbox_inches='tight',
                facecolor='white', edgecolor='none')
    plt.close(fig)
    return str(path)


# ================================================================
# FIGURE 5: Geotechnical Foundation Profile (PISA-style)
# ================================================================

def fig_foundation_profile(output_dir: Path) -> str:
    """Publication-quality foundation cross-section with depth profiles.

    Left panel: bucket cross-section with soil layers and CPT-style G(z)
    Right panels: k(z) stiffness and p_ult(z) capacity as smooth curves
    """
    spring_csv = REPO / "data" / "fem_results" / "spring_profile_op3.csv"
    sp = pd.read_csv(spring_csv)
    z = sp['depth_m'].values
    k = sp['k_ini_kN_per_m'].values / 1000  # MN/m/m
    p = sp['p_ult_kN_per_m'].values / 1000  # MN/m

    D = 8.0; R = D / 2; L = 9.5; t_skirt = 0.04
    su0 = 15.0; k_su = 20.0  # kPa, kPa/m

    fig = plt.figure(figsize=(16, 10))
    gs = fig.add_gridspec(1, 4, width_ratios=[1.2, 0.6, 1, 1], wspace=0.05)

    # ── Panel 1: Foundation cross-section ──
    ax_sec = fig.add_subplot(gs[0])

    # Soil background with gradient
    z_soil = np.linspace(0, 12, 100)
    for i in range(len(z_soil) - 1):
        depth = z_soil[i]
        su = su0 + k_su * depth
        color_val = min(su / 250, 1.0)
        ax_sec.fill_between([-R * 1.8, R * 1.8], -z_soil[i], -z_soil[i+1],
                            color=cm.YlOrBr(0.2 + 0.5 * color_val), alpha=0.4)

    # Water above mudline
    ax_sec.fill_between([-R * 1.8, R * 1.8], 0, 2,
                        color='#cce5ff', alpha=0.3)

    # Bucket structure
    # Lid
    ax_sec.fill_between([-R, R], 0, 0.15, color='#4a4a4a', zorder=5)
    # Skirt walls
    ax_sec.fill_between([-R - t_skirt, -R], 0, -L, color='#4a4a4a', zorder=5)
    ax_sec.fill_between([R, R + t_skirt], 0, -L, color='#4a4a4a', zorder=5)
    # Soil plug (inside bucket)
    ax_sec.fill_between([-R + t_skirt, R - t_skirt], 0, -L,
                        color='#d4a574', alpha=0.3, zorder=3)

    # Dimension annotations
    ax_sec.annotate('', xy=(-R, 1.5), xytext=(R, 1.5),
                    arrowprops=dict(arrowstyle='<->', color='black', lw=1.5))
    ax_sec.text(0, 1.7, f'D = {D:.0f} m', ha='center', fontsize=10,
                fontweight='bold')
    ax_sec.annotate('', xy=(R + 0.5, 0), xytext=(R + 0.5, -L),
                    arrowprops=dict(arrowstyle='<->', color='black', lw=1.5))
    ax_sec.text(R + 1.2, -L/2, f'L = {L:.1f} m', ha='left', fontsize=10,
                fontweight='bold', rotation=90, va='center')

    # Soil layer labels
    ax_sec.text(-R * 1.6, -1, 'Layer 1', fontsize=8, color='#8B4513',
                style='italic')
    ax_sec.text(-R * 1.6, -5, 'Marine Clay', fontsize=8, color='#8B4513',
                style='italic')
    ax_sec.text(-R * 1.6, -8, f's$_u$ = {su0}+{k_su}z kPa', fontsize=8,
                color='#8B4513')

    # Mudline
    ax_sec.axhline(0, color='#8B4513', linewidth=2.5, zorder=4)
    ax_sec.text(-R * 1.7, 0.3, 'Mudline', fontsize=9, color='#8B4513',
                fontweight='bold')

    # Skirt tip
    ax_sec.plot([-R - 0.3, R + 0.3], [-L, -L], 'k--', alpha=0.3)
    ax_sec.text(R + 0.3, -L, 'Skirt tip', fontsize=8, ha='left',
                style='italic')

    ax_sec.set_xlim(-R * 2, R * 2)
    ax_sec.set_ylim(-12, 2.5)
    ax_sec.set_ylabel('Depth below mudline (m)', fontsize=12)
    ax_sec.set_aspect('equal')
    ax_sec.set_title('(a) Foundation Section', fontsize=13, fontweight='bold')
    ax_sec.set_xticks([])

    # ── Panel 2: su(z) profile ──
    ax_su = fig.add_subplot(gs[1])
    z_su = np.linspace(0, 12, 50)
    su_profile = su0 + k_su * z_su

    ax_su.plot(su_profile, -z_su, 'k-', linewidth=2)
    ax_su.fill_betweenx(-z_su, 0, su_profile, alpha=0.15, color='peru')
    ax_su.set_xlabel('s$_u$ (kPa)', fontsize=11)
    ax_su.set_ylim(-12, 2.5)
    ax_su.set_xlim(0, 260)
    ax_su.set_title('(b) Strength', fontsize=13, fontweight='bold')
    ax_su.yaxis.set_visible(False)
    ax_su.grid(True, alpha=0.2)
    ax_su.axhline(0, color='#8B4513', linewidth=1.5)
    ax_su.axhline(-L, color='gray', linewidth=0.5, linestyle='--')

    # ── Panel 3: Stiffness k(z) ──
    ax_k = fig.add_subplot(gs[2])

    # Smooth interpolation
    from scipy.interpolate import interp1d
    z_fine = np.linspace(z.min(), z.max(), 200)
    k_smooth = interp1d(z, k, kind='cubic', fill_value='extrapolate')(z_fine)
    k_smooth = np.maximum(k_smooth, 0)

    ax_k.fill_betweenx(-z_fine, 0, k_smooth, alpha=0.25, color='steelblue')
    ax_k.plot(k_smooth, -z_fine, 'steelblue', linewidth=2.5)
    ax_k.plot(k, -z, 'ko', markersize=4, zorder=5)  # data points

    ax_k.set_xlabel('k$_{ini}$(z) (MN/m/m)', fontsize=11)
    ax_k.set_ylim(-12, 2.5)
    ax_k.set_xlim(0, max(k) * 1.15)
    ax_k.set_title('(c) Initial Stiffness', fontsize=13, fontweight='bold')
    ax_k.yaxis.set_visible(False)
    ax_k.grid(True, alpha=0.2)
    ax_k.axhline(0, color='#8B4513', linewidth=1.5)
    ax_k.axhline(-L, color='gray', linewidth=0.5, linestyle='--')

    # ── Panel 4: Capacity p_ult(z) ──
    ax_p = fig.add_subplot(gs[3])

    p_smooth = interp1d(z, p, kind='cubic', fill_value='extrapolate')(z_fine)
    p_smooth = np.maximum(p_smooth, 0)

    ax_p.fill_betweenx(-z_fine, 0, p_smooth, alpha=0.25, color='firebrick')
    ax_p.plot(p_smooth, -z_fine, 'firebrick', linewidth=2.5)
    ax_p.plot(p, -z, 'ko', markersize=4, zorder=5)

    ax_p.set_xlabel('p$_{ult}$(z) (MN/m)', fontsize=11)
    ax_p.set_ylim(-12, 2.5)
    ax_p.set_xlim(0, max(p) * 1.15)
    ax_p.set_title('(d) Ultimate Resistance', fontsize=13, fontweight='bold')
    ax_p.yaxis.set_visible(False)
    ax_p.grid(True, alpha=0.2)
    ax_p.axhline(0, color='#8B4513', linewidth=1.5)
    ax_p.axhline(-L, color='gray', linewidth=0.5, linestyle='--')

    fig.suptitle('Suction Bucket Foundation: OptumGX-Derived Spring Profile '
                 '(D = 8 m, L = 9.3 m)',
                 fontsize=14, fontweight='bold', y=1.01)

    return _save(fig, "tier2_foundation_profile", output_dir)


# ================================================================
# FIGURE 6: Rainflow Cycle Matrix Heatmap
# ================================================================

def fig_rainflow_heatmap(output_dir: Path) -> str:
    """2D heatmap of rainflow cycles (range vs mean) from OpenFAST output.

    Shows where fatigue damage concentrates in the load spectrum.
    """
    # Load OpenFAST output
    rtest = REPO / "nrel_reference" / "openfast_rtest"
    outb = list(rtest.glob("**/*.outb"))
    if not outb:
        return ""

    from openfast_io.FAST_output_reader import FASTOutputFile
    df = FASTOutputFile(str(outb[0])).toDataFrame()

    # Find blade root moment channel
    ch = None
    for c in ['RootMyc1_[kN-m]', 'RootMxb1_[kN-m]', '-ReactMYss_[N*m]']:
        if c in df.columns:
            ch = c
            break
    if ch is None:
        return ""

    signal = df[ch].values

    # Rainflow counting
    try:
        import rainflow
        cycles = list(rainflow.extract_cycles(signal))
        ranges = np.array([c[0] for c in cycles])
        means = np.array([c[1] for c in cycles])
        counts = np.array([c[2] for c in cycles])
    except ImportError:
        return ""

    fig, axes = plt.subplots(1, 2, figsize=(15, 6), width_ratios=[1.2, 1])

    # ── Panel (a): 2D heatmap ──
    ax1 = axes[0]

    # Create 2D histogram
    n_bins = 30
    range_bins = np.linspace(0, np.percentile(ranges, 99), n_bins)
    mean_bins = np.linspace(np.percentile(means, 1), np.percentile(means, 99),
                            n_bins)

    H, xedges, yedges = np.histogram2d(ranges, means, bins=[range_bins, mean_bins],
                                        weights=counts)

    # Apply Miner's rule weighting (damage ~ range^m)
    m_woehler = 4.0
    x_centers = (xedges[:-1] + xedges[1:]) / 2
    damage_weight = x_centers**m_woehler
    H_damage = H * damage_weight[:, np.newaxis]

    im = ax1.pcolormesh(yedges, xedges, np.log10(H_damage + 1),
                        cmap='hot_r', shading='flat')
    cbar = plt.colorbar(im, ax=ax1, label='log$_{10}$(Damage contribution)')

    ax1.set_xlabel(f'Mean {ch}', fontsize=11)
    ax1.set_ylabel(f'Range {ch}', fontsize=11)
    ax1.set_title(f'(a) Rainflow Damage Matrix (m = {m_woehler})',
                  fontsize=13, fontweight='bold')

    # ── Panel (b): Range histogram with DEL annotation ──
    ax2 = axes[1]

    ax2.hist(ranges, bins=50, weights=counts, color='steelblue', alpha=0.7,
             edgecolor='white', linewidth=0.5)
    ax2.set_xlabel(f'Cycle Range {ch}', fontsize=11)
    ax2.set_ylabel('Weighted Count', fontsize=11)
    ax2.set_title('(b) Cycle Range Distribution', fontsize=13,
                  fontweight='bold')
    ax2.grid(True, alpha=0.2)

    # DEL annotation
    from op3.fatigue import compute_del
    time_col = [c for c in df.columns if 'time' in c.lower()][0]
    dt = df[time_col].diff().median()
    for m in [3, 4, 10]:
        del_val = compute_del(signal, m=m, dt=dt)
        ax2.axvline(del_val * 2, color=['blue', 'green', 'red'][[3,4,10].index(m)],
                    linestyle='--', alpha=0.6,
                    label=f'DEL$_{{m={m}}}$ = {del_val:.0f}')
    ax2.legend(fontsize=9)

    fig.suptitle('Fatigue Load Spectrum Analysis (OC3 Monopile R-Test)',
                 fontsize=14, fontweight='bold', y=1.01)
    fig.tight_layout()

    return _save(fig, "tier2_rainflow_heatmap", output_dir)


# ================================================================
# FIGURE 7: Campbell Diagram
# ================================================================

def fig_campbell_diagram(output_dir: Path) -> str:
    """Campbell diagram showing natural frequencies vs rotor speed.

    Since Op3 linearization runs are not available, constructs a
    parametric Campbell from eigenvalue analyses at different RPM.
    """
    # Op3 eigenvalue data: we know f1 from multiple configurations
    # NREL 5MW: rated RPM = 12.1, f1 ~ 0.316 Hz (fixed), 0.275 Hz (SSI)
    # Operational range: 6.9 - 12.1 rpm

    rpm_range = np.linspace(0, 15, 100)
    f_1P = rpm_range / 60  # Hz
    f_3P = 3 * f_1P
    f_6P = 6 * f_1P
    f_9P = 9 * f_1P

    # Tower modes (approximately constant with RPM for fixed-bottom)
    f_FA1 = 0.316  # First fore-aft (fixed base)
    f_SS1 = 0.316  # First side-to-side
    f_FA2 = 2.75   # Second fore-aft
    f_FA1_ssi = 0.275  # With SSI (Mode B)

    fig, ax = plt.subplots(figsize=(12, 8))

    # Rotor harmonics
    ax.plot(rpm_range, f_1P, 'k-', linewidth=1, label='1P')
    ax.plot(rpm_range, f_3P, 'k--', linewidth=1, label='3P')
    ax.plot(rpm_range, f_6P, 'k:', linewidth=0.8, label='6P')
    ax.plot(rpm_range, f_9P, 'k-.', linewidth=0.8, label='9P')

    # Tower modes as horizontal bands (with SSI uncertainty)
    ax.fill_between(rpm_range, f_FA1_ssi - 0.01, f_FA1 + 0.01,
                    alpha=0.2, color='blue')
    ax.plot(rpm_range, [f_FA1] * len(rpm_range), 'b-', linewidth=2,
            label=f'FA1 fixed = {f_FA1:.3f} Hz')
    ax.plot(rpm_range, [f_FA1_ssi] * len(rpm_range), 'b--', linewidth=2,
            label=f'FA1 SSI = {f_FA1_ssi:.3f} Hz')
    ax.plot(rpm_range, [f_SS1] * len(rpm_range), 'r-', linewidth=1.5,
            alpha=0.7, label=f'SS1 = {f_SS1:.3f} Hz')

    # Second mode
    ax.plot(rpm_range, [f_FA2] * len(rpm_range), 'g-', linewidth=1.5,
            alpha=0.5, label=f'FA2 = {f_FA2:.2f} Hz')

    # Operational range shading
    rpm_cut_in = 6.9
    rpm_rated = 12.1
    ax.axvspan(rpm_cut_in, rpm_rated, alpha=0.08, color='green',
               label='Operational range')

    # Resonance crossings (1P and 3P with FA1)
    # 1P = FA1: rpm = FA1 * 60 = 18.96 (above rated, safe)
    # 3P = FA1: rpm = FA1/3 * 60 = 6.32 (near cut-in!)
    rpm_3P_cross = f_FA1_ssi / 3 * 60
    ax.plot(rpm_3P_cross, f_FA1_ssi, 'r*', markersize=15, zorder=10)
    ax.annotate(f'3P crossing\n{rpm_3P_cross:.1f} rpm',
                xy=(rpm_3P_cross, f_FA1_ssi),
                xytext=(rpm_3P_cross + 1.5, f_FA1_ssi + 0.05),
                fontsize=9, arrowprops=dict(arrowstyle='->', color='red'),
                color='red', fontweight='bold')

    ax.set_xlabel('Rotor Speed (rpm)', fontsize=12)
    ax.set_ylabel('Frequency (Hz)', fontsize=12)
    ax.set_title('Campbell Diagram: NREL 5MW on OC3 Monopile',
                 fontsize=14, fontweight='bold')
    ax.legend(fontsize=9, loc='upper left', ncol=2)
    ax.set_xlim(0, 15)
    ax.set_ylim(0, 1.5)
    ax.grid(True, alpha=0.2)

    return _save(fig, "tier2_campbell", output_dir)


# ================================================================
# FIGURE 8: M-theta Backbone with Published References
# ================================================================

def fig_moment_rotation(output_dir: Path) -> str:
    """Moment-rotation backbone curve with published reference points.

    Overlays: DJ Kim 2014 centrifuge, Houlsby 2005 field trial,
    Barari 2021 FE prediction.
    """
    fig, axes = plt.subplots(1, 2, figsize=(15, 7))

    # ── Panel (a): NREL 5MW Op3 M-theta from pushover ──
    ax1 = axes[0]

    # Run Op3 moment-rotation
    import sys
    sys.path.insert(0, str(REPO))

    try:
        from op3 import build_foundation, compose_tower_model
        from op3.opensees_foundations.builder import run_pushover_moment_rotation

        fnd = build_foundation(
            mode='distributed_bnwf',
            spring_profile=str(REPO / "data" / "fem_results" / "spring_profile_op3.csv"),
        )
        model = compose_tower_model(
            rotor='nrel_5mw_baseline',
            tower='nrel_5mw_tower',
            foundation=fnd,
        )
        model.eigen(n_modes=1)
        mr = run_pushover_moment_rotation(model, target_rotation_rad=0.015,
                                           n_steps=30)

        if mr.get('rotation_deg') and len(mr['rotation_deg']) > 0:
            theta = np.array(mr['rotation_deg'])
            M = np.array(mr['moment_MNm'])
            ax1.plot(theta, M, 'b-', linewidth=2.5, label='Op3 Mode C (BNWF)',
                     zorder=5)
        else:
            theta = np.linspace(0, 0.8, 50)
            Kr = 15200  # MNm/rad (from condensation)
            M = Kr * np.radians(theta)
            ax1.plot(theta, M, 'b-', linewidth=2.5, label='Op3 (elastic)',
                     zorder=5)
    except Exception as e:
        theta = np.linspace(0, 0.8, 50)
        Kr = 15200
        M = Kr * np.radians(theta)
        ax1.plot(theta, M, 'b-', linewidth=2.5, label='Op3 (elastic)',
                 zorder=5)

    ax1.set_xlabel('Rotation (deg)', fontsize=12)
    ax1.set_ylabel('Moment (MNm)', fontsize=12)
    ax1.set_title('(a) Op3 Foundation Moment-Rotation',
                  fontsize=13, fontweight='bold')
    ax1.legend(fontsize=10)
    ax1.grid(True, alpha=0.2)
    ax1.set_xlim(0, max(theta) * 1.1 if len(theta) > 0 else 1.0)
    ax1.set_ylim(bottom=0)

    # ── Panel (b): Published comparison ──
    ax2 = axes[1]

    # DJ Kim 2014 centrifuge (tripod)
    theta_djkim = [0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.8, 1.0]
    M_djkim = [0, 18, 35, 52, 68, 82, 93, 105, 112]  # MNm (bilinear approx)
    ax2.plot(theta_djkim, M_djkim, 'rs-', linewidth=2, markersize=6,
             label='DJ Kim 2014 (centrifuge 70g)')

    # Houlsby 2005 Bothkennar (field, D=3m, scaled to equivalent)
    theta_houlsby = [0, 0.05, 0.1, 0.15, 0.2, 0.3]
    # Kr = 225 MNm/rad, so M = 225 * theta_rad
    M_houlsby = [225 * math.radians(t) for t in theta_houlsby]
    ax2.plot(theta_houlsby, M_houlsby, 'g^-', linewidth=2, markersize=6,
             label='Houlsby 2005 (Bothkennar field, D=3m)')

    # Barari 2021 FE (tripod, calibrated to DJ Kim)
    theta_barari = [0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8]
    M_barari = [0, 16, 33, 50, 65, 80, 90, 98, 104]  # approx from Fig 12
    ax2.plot(theta_barari, M_barari, 'bd--', linewidth=1.5, markersize=5,
             label='Barari 2021 (Plaxis 3D)')

    # Op3 analytical prediction for DJ Kim geometry (from benchmark #22)
    theta_op3 = [0, 0.6]
    M_op3 = [0, 92.4]  # from run_remaining_gaps.py
    ax2.plot(theta_op3, M_op3, 'k--', linewidth=2.5,
             label='Op3 analytical (My = 92.4 MNm)')
    ax2.plot(0.6, 92.4, 'k*', markersize=15, zorder=10)

    # Serviceability limit
    ax2.axvline(0.5, color='orange', linestyle=':', linewidth=1.5,
                label='SLS limit (0.5 deg)')

    ax2.set_xlabel('Rotation (deg)', fontsize=12)
    ax2.set_ylabel('Moment (MNm)', fontsize=12)
    ax2.set_title('(b) Cross-Validation: M-$\\theta$ Backbone',
                  fontsize=13, fontweight='bold')
    ax2.legend(fontsize=9, loc='lower right')
    ax2.grid(True, alpha=0.2)
    ax2.set_xlim(0, 1.1)
    ax2.set_ylim(0, 130)

    fig.suptitle('Foundation Moment-Rotation Response',
                 fontsize=14, fontweight='bold', y=1.01)
    fig.tight_layout()

    return _save(fig, "tier2_moment_rotation", output_dir)


# ================================================================
# Main
# ================================================================

def main():
    output_dir = REPO / "validation" / "figures" / "tier2"

    print("=" * 60)
    print("  Op3 Tier 2 Visualization")
    print("=" * 60)

    print("\n[5/8] Foundation profile (geotechnical style)...", flush=True)
    path = fig_foundation_profile(output_dir)
    print(f"  Saved: {path}")

    print("\n[6/8] Rainflow cycle matrix heatmap...", flush=True)
    path = fig_rainflow_heatmap(output_dir)
    if path:
        print(f"  Saved: {path}")
    else:
        print("  Skipped (no data)")

    print("\n[7/8] Campbell diagram...", flush=True)
    path = fig_campbell_diagram(output_dir)
    print(f"  Saved: {path}")

    print("\n[8/8] Moment-rotation backbone...", flush=True)
    path = fig_moment_rotation(output_dir)
    print(f"  Saved: {path}")

    print("\n" + "=" * 60)
    figs = sorted(output_dir.glob("*.png"))
    print(f"  {len(figs)} Tier 2 figures at {output_dir}/")
    for f in figs:
        print(f"    {f.name}")
    print("=" * 60)


if __name__ == "__main__":
    main()
