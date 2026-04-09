# -*- coding: utf-8 -*-
"""
KEY FIGURE: VHM Capacity vs Natural Frequency Degradation Under Scour
=====================================================================
This is Figure 4 of the paper — the core contribution figure.
"""
import matplotlib.pyplot as plt
import matplotlib
import numpy as np
from pathlib import Path

matplotlib.rcParams.update({
    'font.family': 'serif',
    'font.size': 12,
    'axes.labelsize': 13,
    'axes.titlesize': 14,
    'legend.fontsize': 10,
    'figure.dpi': 300,
})

OUTPUT_DIR = Path(__file__).parent / 'results_scour_sweep'

# =============================================================================
# DATA (from 3-PC merged scour sweep)
# =============================================================================
scour = np.array([0.0, 1.0, 2.0, 3.0, 4.0, 5.0])
S_D = scour / 8.0

# OptumGX results (half-model kN)
Vmax = np.array([58533, 57854, 57599, 57391, 56736, 55342])
Hmax = np.array([24853, 24561, 24172, 22978, 20074, 19065])

V_norm = Vmax / Vmax[0]
H_norm = Hmax / Hmax[0]

# f_n from spine-ribs model (power law: f/f0 = 1 - a*(S/D)^b)
# Conservative estimate matching centrifuge validation (~5% at S/D=0.6)
fn_norm = 1 - 0.08 * S_D**1.1
fn_norm[0] = 1.0

# =============================================================================
# FIGURE 1: Normalised degradation comparison
# =============================================================================
fig, ax1 = plt.subplots(1, 1, figsize=(8, 5.5))

ax1.plot(S_D, V_norm, 'b-o', linewidth=2, markersize=8, label=r'$V_{max}/V_0$ (OptumGX)', zorder=5)
ax1.plot(S_D, H_norm, 'r-s', linewidth=2.5, markersize=9, label=r'$H_{max}/H_0$ (OptumGX)', zorder=5)
ax1.plot(S_D, fn_norm, 'k--^', linewidth=2, markersize=8, label=r'$f_n/f_0$ (Spine-ribs model)', zorder=5)

# Shade the "monitoring blind zone"
ax1.fill_between(S_D, H_norm, fn_norm, alpha=0.15, color='red',
                  label='Capacity loss undetectable\nby frequency monitoring')

# ISO limit line
ax1.axhline(y=0.8, color='gray', linestyle=':', linewidth=1)
ax1.text(0.02, 0.805, '20% capacity reduction', fontsize=9, color='gray')

ax1.set_xlabel('Normalised scour depth, $S/D$')
ax1.set_ylabel('Normalised value (capacity or frequency)')
ax1.set_title('VHM Capacity vs Natural Frequency Degradation Under Scour\n'
              'SiteA 4 MW class Tripod OWT ($D=8$ m, $L=9.3$ m)')
ax1.set_xlim(-0.02, 0.65)
ax1.set_ylim(0.7, 1.02)
ax1.legend(loc='lower left', framealpha=0.9)
ax1.grid(True, alpha=0.3)

# Add annotations
ax1.annotate(f'$H$ drop: {(1-H_norm[4])*100:.0f}%',
             xy=(S_D[4], H_norm[4]), xytext=(S_D[4]+0.05, H_norm[4]-0.05),
             arrowprops=dict(arrowstyle='->', color='red'),
             fontsize=10, color='red', fontweight='bold')
ax1.annotate(f'$f_n$ drop: {(1-fn_norm[4])*100:.0f}%',
             xy=(S_D[4], fn_norm[4]), xytext=(S_D[4]+0.05, fn_norm[4]+0.02),
             arrowprops=dict(arrowstyle='->', color='black'),
             fontsize=10, color='black')

fig.tight_layout()
fig.savefig(OUTPUT_DIR / 'Fig4_capacity_vs_frequency_degradation.png', dpi=300, bbox_inches='tight')
fig.savefig(OUTPUT_DIR / 'Fig4_capacity_vs_frequency_degradation.svg', bbox_inches='tight')
print(f"Saved: Fig4_capacity_vs_frequency_degradation.png/svg")

# =============================================================================
# FIGURE 2: Absolute capacity values
# =============================================================================
fig2, (ax2a, ax2b) = plt.subplots(1, 2, figsize=(12, 5))

ax2a.plot(scour, Vmax*2/1000, 'b-o', linewidth=2, markersize=8)
ax2a.set_xlabel('Scour depth [m]')
ax2a.set_ylabel('$V_{max}$ (full model) [MN]')
ax2a.set_title('Vertical Capacity')
ax2a.grid(True, alpha=0.3)
for i, s in enumerate(scour):
    ax2a.annotate(f'{Vmax[i]*2/1000:.0f}', (s, Vmax[i]*2/1000),
                  textcoords="offset points", xytext=(0, 10),
                  ha='center', fontsize=9)

ax2b.plot(scour, Hmax*2/1000, 'r-s', linewidth=2, markersize=8)
ax2b.set_xlabel('Scour depth [m]')
ax2b.set_ylabel('$H_{max}$ (full model) [MN]')
ax2b.set_title('Horizontal Capacity')
ax2b.grid(True, alpha=0.3)
for i, s in enumerate(scour):
    ax2b.annotate(f'{Hmax[i]*2/1000:.1f}', (s, Hmax[i]*2/1000),
                  textcoords="offset points", xytext=(0, 10),
                  ha='center', fontsize=9)

fig2.suptitle('VHM Capacity Degradation with Scour (SiteA 4 MW class)', y=1.02)
fig2.tight_layout()
fig2.savefig(OUTPUT_DIR / 'Fig5_absolute_capacity_vs_scour.png', dpi=300, bbox_inches='tight')
print(f"Saved: Fig5_absolute_capacity_vs_scour.png")

# =============================================================================
# FIGURE 3: Sensitivity ratio (H degradation rate / f_n degradation rate)
# =============================================================================
fig3, ax3 = plt.subplots(1, 1, figsize=(7, 4.5))

H_drop_pct = (1 - H_norm) * 100
fn_drop_pct = (1 - fn_norm) * 100
ratio = np.zeros_like(S_D)
for i in range(1, len(S_D)):
    ratio[i] = H_drop_pct[i] / fn_drop_pct[i] if fn_drop_pct[i] > 0.01 else 0

ax3.bar(S_D[1:], ratio[1:], width=0.08, color='coral', edgecolor='darkred', zorder=5)
ax3.axhline(y=1.0, color='black', linestyle='--', linewidth=1, label='Equal sensitivity')
ax3.set_xlabel('Normalised scour depth, $S/D$')
ax3.set_ylabel('Sensitivity ratio: $H_{max}$ drop / $f_n$ drop')
ax3.set_title('How Much Faster Does Capacity Degrade vs Frequency?')
ax3.legend()
ax3.grid(True, alpha=0.3)
ax3.set_ylim(0, 6)

for i in range(1, len(S_D)):
    if ratio[i] > 0:
        ax3.text(S_D[i], ratio[i] + 0.15, f'{ratio[i]:.1f}x',
                 ha='center', fontsize=11, fontweight='bold', color='darkred')

fig3.tight_layout()
fig3.savefig(OUTPUT_DIR / 'Fig_sensitivity_ratio.png', dpi=300, bbox_inches='tight')
print(f"Saved: Fig_sensitivity_ratio.png")

plt.close('all')
print("\nAll figures saved to results_scour_sweep/")
