"""
Op3 Advanced Visualization Demo: OptumGX + OpenFAST.

Generates figures for:
  - OptumGX: bucket pressure, collapse mechanism, spring profile, Np(z)
  - OpenFAST: time series, PSD, power curve, DEL

Usage:
    python scripts/visualize_optumgx_openfast.py
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

OUTPUT = REPO / "validation" / "figures"


def run_optumgx_viz():
    print("\n" + "=" * 60)
    print("  OptumGX Visualization (PyVista)")
    print("=" * 60)

    from op3.viz_optumgx import (
        plot_bucket_pressure,
        plot_collapse_mechanism,
        plot_spring_profile,
        plot_np_profile,
    )

    # Spring profile
    spring_csv = REPO / "data" / "fem_results" / "spring_profile_op3.csv"
    if spring_csv.exists():
        print("[1] Spring profile...", flush=True)
        path = plot_spring_profile(spring_csv, output_dir=OUTPUT)
        if path:
            print(f"    Saved: {path}")

    # Np(z) profile
    pult_csv = REPO / "validation" / "cross_validations" / "pult_depth_profile.csv"
    if pult_csv.exists():
        print("[2] Np(z) bearing capacity factor...", flush=True)
        path = plot_np_profile(pult_csv, output_dir=OUTPUT)
        if path:
            print(f"    Saved: {path}")

    # 3D bucket pressure (synthetic demo)
    print("[3] 3D bucket contact pressure...", flush=True)
    path = plot_bucket_pressure(output_dir=OUTPUT)
    if path:
        print(f"    Saved: {path}")

    # Collapse mechanism (synthetic demo)
    print("[4] Collapse mechanism (plastic dissipation)...", flush=True)
    path = plot_collapse_mechanism(output_dir=OUTPUT)
    if path:
        print(f"    Saved: {path}")


def run_openfast_viz():
    print("\n" + "=" * 60)
    print("  OpenFAST Visualization (welib + pCrunch)")
    print("=" * 60)

    from op3.viz_openfast import (
        plot_time_series,
        plot_psd,
        plot_power_curve,
        plot_del_bar,
        compute_dlc_statistics,
    )

    # Find .outb files
    rtest_dir = REPO / "nrel_reference" / "openfast_rtest"
    dlc_dir = REPO / "validation" / "dlc11_partial"

    # OC3 r-test time series
    rtest_outb = list(rtest_dir.glob("**/*.outb"))
    if rtest_outb:
        print(f"[5] OC3 r-test time series ({rtest_outb[0].name})...",
              flush=True)
        path = plot_time_series(rtest_outb[0], output_dir=OUTPUT,
                                title="OC3 Monopile R-Test")
        if path:
            print(f"    Saved: {path}")

        print("[6] PSD...", flush=True)
        path = plot_psd(rtest_outb[0], output_dir=OUTPUT)
        if path:
            print(f"    Saved: {path}")

        print("[7] DEL bar chart...", flush=True)
        path = plot_del_bar(rtest_outb[:1], output_dir=OUTPUT)
        if path:
            print(f"    Saved: {path}")

    # DLC 1.1 power curve
    dlc_outb = sorted(dlc_dir.glob("*.outb")) if dlc_dir.exists() else []
    if dlc_outb:
        print(f"[8] DLC 1.1 statistics ({len(dlc_outb)} runs)...", flush=True)
        channels = ['GenPwr_[kW]', 'RotSpeed_[rpm]', 'RootMyc1_[kN-m]']
        stats = compute_dlc_statistics(dlc_dir, channels=channels)
        if stats.get("stats_df") is not None:
            print(f"    {stats['n_runs']} runs, "
                  f"wind speeds: {stats['wind_speeds']}")

            print("[9] Power curve...", flush=True)
            path = plot_power_curve(stats, output_dir=OUTPUT)
            if path:
                print(f"    Saved: {path}")


def main():
    print("=" * 60)
    print("  Op3 Advanced Visualization Demo")
    print("=" * 60)

    run_optumgx_viz()
    run_openfast_viz()

    # Summary
    print("\n" + "=" * 60)
    figs = sorted(OUTPUT.glob("*.png"))
    print(f"  Total: {len(figs)} figures in {OUTPUT}/")
    for f in figs:
        print(f"    {f.name}")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
