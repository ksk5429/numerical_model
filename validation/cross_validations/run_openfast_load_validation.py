"""
OpenFAST OC3 monopile load cross-validation against Jonkman (2009).

Reference:
    Jonkman, J. (2009). "Definition of the Floating System for Phase IV
    of OC3." NREL/TP-500-47535.  (and the underlying 5MW definition
    report: NREL/TP-500-38060.)

Expected values at rated wind speed (11.4 m/s, steady or time-averaged):
    - GenPwr       : ~5,000 kW
    - RotSpeed     : ~12.1 rpm
    - RootMyc1     : ~8,000 - 12,000 kN-m  (blade root flapwise, c-system)
    - TwrBsMyt     : ~50,000 - 80,000 kN-m  (tower base fore-aft)
      NOTE: The OC3 r-test outb stores SubDyn reaction moments instead.
            -ReactMYss is the mudline fore-aft reaction moment (N-m).

This script:
  1. Discovers all .outb files under the numerical_model_fresh tree.
  2. Reads the OC3 monopile reference r-test output.
  3. Reads the DLC 1.1 partial sweep (if present).
  4. Computes time-averaged and max values for key channels.
  5. Compares against Jonkman reference and prints a summary table.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional

import numpy as np

REPO = Path(__file__).resolve().parents[2]  # numerical_model_fresh

# --- Jonkman (2009) reference values at rated (11.4 m/s) ---
REFERENCE = {
    "GenPwr_[kW]": {"mean": 5000.0, "unit": "kW",
                    "tol_pct": 10, "note": "rated electrical power"},
    "RotSpeed_[rpm]": {"mean": 12.1, "unit": "rpm",
                       "tol_pct": 5, "note": "rated rotor speed"},
    "RootMyc1_[kN-m]": {"mean": 10000.0, "unit": "kN-m",
                        "tol_pct": 40,
                        "note": "blade root flapwise (turbulent, wide band)"},
}


def read_outb(filepath: str | Path):
    """Read an OpenFAST .outb or .out file, return a DataFrame."""
    from openfast_io.FAST_output_reader import FASTOutputFile
    return FASTOutputFile(str(filepath)).toDataFrame()


def summarize_channels(df, channels: list[str], t_skip: float = 30.0):
    """Compute mean and max for requested channels, skipping initial transient.

    Parameters
    ----------
    df : DataFrame
        OpenFAST output dataframe with Time_[s] as first column.
    channels : list of str
        Channel names (with units) to summarize.
    t_skip : float
        Seconds of initial transient to skip.
    """
    time_col = "Time_[s]" if "Time_[s]" in df.columns else df.columns[0]
    t_max = df[time_col].max()
    # If signal is shorter than t_skip, use 10% of duration as skip
    effective_skip = t_skip if t_max > t_skip * 1.5 else t_max * 0.1
    mask = df[time_col] >= effective_skip
    results = {}
    for ch in channels:
        if ch not in df.columns:
            continue
        vals = df.loc[mask, ch].to_numpy()
        if len(vals) == 0:
            continue
        results[ch] = {
            "mean": float(np.mean(vals)),
            "max": float(np.max(vals)),
            "min": float(np.min(vals)),
            "std": float(np.std(vals)),
        }
    return results


def find_outb_files(root: Path) -> dict[str, list[Path]]:
    """Discover .outb files grouped by category."""
    found = {
        "oc3_rtest": [],
        "dlc11_partial": [],
        "other": [],
    }
    # OC3 monopile r-test
    rtest = root / "nrel_reference" / "openfast_rtest"
    if rtest.exists():
        for f in rtest.rglob("*.outb"):
            if "OC3Mnpl" in f.name:
                found["oc3_rtest"].append(f)

    # DLC 1.1 partial sweep
    dlc = root / "validation" / "dlc11_partial"
    if dlc.exists():
        for f in dlc.rglob("*.outb"):
            found["dlc11_partial"].append(f)

    # Also check r-test_v5 for the same case
    rtest_v5 = root / "tools" / "r-test_v5" / "r-test" / "glue-codes" / "openfast"
    if rtest_v5.exists():
        for d in rtest_v5.iterdir():
            if "OC3Mnpl" in d.name and d.is_dir():
                for f in d.glob("*.outb"):
                    found["oc3_rtest"].append(f)

    return found


def validate_against_reference(stats: dict, label: str = "") -> list[dict]:
    """Compare computed stats against Jonkman reference.

    Returns a list of comparison dicts.
    """
    comparisons = []
    for ch, ref in REFERENCE.items():
        if ch not in stats:
            comparisons.append({
                "channel": ch, "ref_mean": ref["mean"],
                "computed_mean": None, "pct_diff": None,
                "status": "MISSING", "note": ref["note"],
            })
            continue
        computed = stats[ch]["mean"]
        pct_diff = 100.0 * (computed - ref["mean"]) / ref["mean"]
        ok = abs(pct_diff) <= ref["tol_pct"]
        comparisons.append({
            "channel": ch,
            "ref_mean": ref["mean"],
            "computed_mean": round(computed, 2),
            "computed_max": round(stats[ch]["max"], 2),
            "pct_diff": round(pct_diff, 1),
            "status": "PASS" if ok else "CHECK",
            "note": ref["note"],
        })
    return comparisons


def print_table(comparisons: list[dict], title: str = ""):
    """Pretty-print comparison table."""
    print(f"\n{'=' * 80}")
    print(f"  {title}")
    print(f"{'=' * 80}")
    hdr = f"{'Channel':<22} {'Ref Mean':>12} {'Computed':>12} {'Max':>12} {'Diff%':>8} {'Status':>8}"
    print(hdr)
    print("-" * 80)
    for c in comparisons:
        comp = f"{c['computed_mean']}" if c["computed_mean"] is not None else "---"
        cmax = f"{c.get('computed_max', '---')}"
        pdiff = f"{c['pct_diff']}%" if c["pct_diff"] is not None else "---"
        print(f"{c['channel']:<22} {c['ref_mean']:>12.1f} {comp:>12} {cmax:>12} {pdiff:>8} {c['status']:>8}")
    print("-" * 80)


def run_oc3_rtest_validation(files: list[Path]) -> Optional[list[dict]]:
    """Validate the NREL OC3 r-test output."""
    if not files:
        print("[INFO] No OC3 monopile r-test .outb files found.")
        return None

    f = files[0]
    print(f"[INFO] Reading OC3 r-test: {f}")
    df = read_outb(f)

    channels = list(REFERENCE.keys())
    # Also check SubDyn reaction moment as tower-base proxy
    extra = ["-ReactMYss_[N*m]", "YawBrMyp_[kN-m]"]
    stats = summarize_channels(df, channels + extra, t_skip=30.0)

    # Report SubDyn reaction moment separately
    if "-ReactMYss_[N*m]" in stats:
        react_my = stats["-ReactMYss_[N*m]"]
        print(f"\n  SubDyn mudline -ReactMYss: mean={react_my['mean']/1e3:.0f} kN-m, "
              f"max={react_my['max']/1e3:.0f} kN-m")
        print(f"  (Jonkman tower base ref: ~50,000-80,000 kN-m at rated)")

    if "YawBrMyp_[kN-m]" in stats:
        ybr = stats["YawBrMyp_[kN-m]"]
        print(f"  YawBrMyp (tower top FA moment): mean={ybr['mean']:.0f} kN-m, "
              f"max={ybr['max']:.0f} kN-m")

    comparisons = validate_against_reference(stats, label="OC3 r-test")
    print_table(comparisons, title="OC3 Monopile R-Test vs Jonkman (2009)")
    return comparisons


def run_dlc11_validation(files: list[Path]) -> Optional[list[dict]]:
    """Validate the DLC 1.1 sweep outputs, focusing on rated wind speed."""
    if not files:
        print("[INFO] No DLC 1.1 partial .outb files found.")
        return None

    # Sort by wind speed encoded in folder name
    import re
    rated_files = []
    all_stats = []

    for f in sorted(files):
        m = re.search(r"(\d+)mps", str(f))
        if m:
            ws = float(m.group(1)) / 10.0
        else:
            ws = float("nan")

        print(f"  [DLC1.1] {f.parent.name}: Ws={ws:.1f} m/s")
        df = read_outb(f)
        channels = list(REFERENCE.keys()) + ["-ReactMYss_[N*m]"]
        stats = summarize_channels(df, channels, t_skip=30.0)
        stats["_ws"] = ws
        stats["_path"] = str(f)
        all_stats.append(stats)

        if abs(ws - 11.4) < 0.5:
            rated_files.append((ws, stats))

    # Print overview
    print(f"\n{'=' * 80}")
    print("  DLC 1.1 Sweep Summary")
    print(f"{'=' * 80}")
    print(f"{'Wind [m/s]':>12} {'GenPwr mean':>14} {'RotSpd mean':>14} {'RootMyc1 mean':>16}")
    print("-" * 60)
    for s in all_stats:
        ws = s.get("_ws", float("nan"))
        gp = s.get("GenPwr_[kW]", {}).get("mean", float("nan"))
        rs = s.get("RotSpeed_[rpm]", {}).get("mean", float("nan"))
        rm = s.get("RootMyc1_[kN-m]", {}).get("mean", float("nan"))
        print(f"{ws:>12.1f} {gp:>14.1f} {rs:>14.2f} {rm:>16.1f}")

    if rated_files:
        ws, stats = rated_files[0]
        comparisons = validate_against_reference(stats, label=f"DLC1.1 @ {ws} m/s")
        print_table(comparisons, title=f"DLC 1.1 @ {ws:.1f} m/s vs Jonkman (2009)")
        return comparisons

    return None


def main():
    print("=" * 80)
    print("  OpenFAST OC3 Monopile Load Cross-Validation")
    print("  Reference: Jonkman (2009) NREL/TP-500-38060")
    print("=" * 80)

    found = find_outb_files(REPO)
    total = sum(len(v) for v in found.values())
    print(f"\n[INFO] Discovered {total} .outb files:")
    for cat, files in found.items():
        if files:
            print(f"  {cat}: {len(files)} file(s)")

    # --- OC3 R-Test ---
    run_oc3_rtest_validation(found["oc3_rtest"])

    # --- DLC 1.1 Sweep ---
    run_dlc11_validation(found["dlc11_partial"])

    print("\n[DONE] Load validation complete.")


if __name__ == "__main__":
    main()
