"""
Op3 Structural Visualization Demo.

Generates publication-quality figures using opsvis:
  1. Model geometry (nodes, elements, supports)
  2. First 3 mode shapes with frequencies
  3. Pushover force-displacement curve
  4. Pushover deformed shape
  5. Moment-rotation at foundation head

Output: validation/figures/

Usage:
    python scripts/visualize_op3.py
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

OUTPUT = REPO / "validation" / "figures"


def main():
    print("=" * 60)
    print("  Op3 Structural Visualization")
    print("=" * 60)

    from op3 import build_foundation, compose_tower_model
    from op3.visualization import (
        plot_model,
        plot_mode_shapes,
        plot_deformed,
        plot_pushover_curve,
        plot_moment_rotation,
    )
    from op3.opensees_foundations.builder import run_pushover_moment_rotation

    # ── Build model (Mode A fixed base, NREL 5MW) ──
    print("\n[1] Building NREL 5MW tower model (Mode A)...", flush=True)
    fnd = build_foundation(mode="fixed")
    model = compose_tower_model(
        rotor="nrel_5mw_baseline",
        tower="nrel_5mw_tower",
        foundation=fnd,
    )

    # ── Eigenvalue ──
    print("[2] Eigenvalue analysis...", flush=True)
    freqs = model.eigen(n_modes=3)
    print(f"    f1 = {freqs[0]:.4f} Hz")
    print(f"    f2 = {freqs[1]:.4f} Hz")
    print(f"    f3 = {freqs[2]:.4f} Hz")

    # ── Model geometry plot ──
    print("[3] Plotting model geometry...", flush=True)
    path = plot_model(output_dir=OUTPUT, title="NREL 5MW OC3 - Op3 Model")
    if path:
        print(f"    Saved: {path}")

    # ── Mode shapes ──
    print("[4] Plotting mode shapes...", flush=True)
    paths = plot_mode_shapes(n_modes=3, output_dir=OUTPUT, freqs=list(freqs))
    for p in paths:
        if p:
            print(f"    Saved: {p}")

    # ── Pushover ──
    print("[5] Running pushover (0.5 m target)...", flush=True)
    # Need fresh model for pushover (eigen may have changed state)
    fnd2 = build_foundation(mode="fixed")
    model2 = compose_tower_model(
        rotor="nrel_5mw_baseline",
        tower="nrel_5mw_tower",
        foundation=fnd2,
    )
    model2.eigen(n_modes=1)  # trigger build
    push = model2.pushover(target_disp_m=0.3, n_steps=30)

    if push.get("displacement_m"):
        print(f"    Steps: {len(push['displacement_m'])}")
        path = plot_pushover_curve(push, output_dir=OUTPUT,
                                   title="NREL 5MW Fixed-Base Pushover")
        if path:
            print(f"    Saved: {path}")

        # Deformed shape at final step
        print("[6] Plotting deformed shape...", flush=True)
        path = plot_deformed(output_dir=OUTPUT,
                             title="Pushover Deformed Shape (u=0.3m)")
        if path:
            print(f"    Saved: {path}")
    else:
        print(f"    Pushover error: {push.get('error', 'unknown')}")

    # ── Moment-rotation ──
    print("[7] Moment-rotation analysis...", flush=True)
    fnd3 = build_foundation(mode="fixed")
    model3 = compose_tower_model(
        rotor="nrel_5mw_baseline",
        tower="nrel_5mw_tower",
        foundation=fnd3,
    )
    model3.eigen(n_modes=1)

    mr = run_pushover_moment_rotation(model3, target_rotation_rad=0.01,
                                       n_steps=20)
    if mr.get("rotation_deg"):
        print(f"    Steps: {len(mr['rotation_deg'])}")
        print(f"    Max M: {max(mr['moment_MNm']):.1f} MNm at "
              f"{max(mr['rotation_deg']):.3f} deg")
        path = plot_moment_rotation(
            mr, output_dir=OUTPUT,
            title="NREL 5MW Foundation Moment-Rotation",
        )
        if path:
            print(f"    Saved: {path}")
    else:
        print(f"    M-theta error: {mr.get('error', 'unknown')}")

    # ── Mode B (PISA-derived) model ──
    print("\n[8] Mode B (PISA) model...", flush=True)
    try:
        from op3.foundations import foundation_from_pisa
        from op3.standards.pisa import SoilState
        profile = [
            SoilState(0.0, 5e7, 35, "sand"),
            SoilState(15.0, 1e8, 35, "sand"),
            SoilState(36.0, 1.5e8, 36, "sand"),
        ]
        fnd_pisa = foundation_from_pisa(
            diameter_m=6.0, embed_length_m=36.0, soil_profile=profile)
        model_pisa = compose_tower_model(
            rotor="nrel_5mw_baseline",
            tower="nrel_5mw_oc3_tower",
            foundation=fnd_pisa,
        )
        freqs_pisa = model_pisa.eigen(n_modes=3)
        print(f"    PISA f1 = {freqs_pisa[0]:.4f} Hz")

        path = plot_model(output_dir=OUTPUT,
                         title="NREL 5MW OC3 - Mode B (PISA)")
        if path:
            print(f"    Saved: {path}")

        paths = plot_mode_shapes(n_modes=2, output_dir=OUTPUT,
                                freqs=list(freqs_pisa))
        for p in paths:
            if p:
                print(f"    Saved: {p}")
    except Exception as e:
        print(f"    Mode B failed: {e}")

    # ── Summary ──
    print("\n" + "=" * 60)
    figs = list(OUTPUT.glob("*.png"))
    print(f"  Generated {len(figs)} figures in {OUTPUT}/")
    for f in sorted(figs):
        print(f"    {f.name}")
    print("=" * 60)

    return 0


if __name__ == "__main__":
    sys.exit(main())
