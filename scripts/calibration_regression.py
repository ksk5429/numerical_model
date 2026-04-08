"""
Per-example calibration regression test (Phase 1 / Task 1.3).

For each Op3 example with a published reference frequency, this
script runs the OpenSeesPy eigenvalue analysis, compares the first
tower bending mode against the documented reference, and reports
pass/fail against an explicit tolerance band.

Reference frequencies are committed here with full provenance so that
"calibration" is a falsifiable, version-controlled claim -- not a
moving goalpost.

Usage
-----
    python scripts/calibration_regression.py
    python scripts/calibration_regression.py --tol 0.05   # tighten band
    python scripts/calibration_regression.py --json out.json

Exit code is non-zero if any example exceeds its tolerance.
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, asdict
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

# ---------------------------------------------------------------------------
# Reference frequency catalog
# ---------------------------------------------------------------------------
# Each entry pins a published or measured reference for the first tower
# bending frequency, with citation. Tolerance is the +/- fractional band
# considered "calibrated" for that example. Use this catalog as the
# single source of truth -- do not edit values without updating the
# corresponding citation.

@dataclass
class Reference:
    example_id: str
    f1_hz: float
    tolerance: float
    boundary_condition: str   # "fixed" | "monopile-soil" | "tripod-soil" | ...
    source: str
    note: str = ""


REFERENCES: dict[str, Reference] = {
    "01_nrel_5mw_baseline": Reference(
        example_id="01_nrel_5mw_baseline",
        f1_hz=0.324,
        tolerance=0.05,
        boundary_condition="fixed",
        source="Jonkman et al. (2009), NREL/TP-500-38060, Table 9-1",
        note="Tower 1st fore-aft bending mode, full RNA, fixed at tower base.",
    ),
    "02_nrel_5mw_oc3_monopile": Reference(
        example_id="02_nrel_5mw_oc3_monopile",
        f1_hz=0.2766,
        tolerance=0.10,
        boundary_condition="monopile-soil-fixed-at-mudline",
        source="Jonkman & Musial (2010), NREL/TP-500-47535 (OC3 Phase II), Table 7-3",
        note="Coupled tower+monopile 1st bending mode, fixed at mudline; "
             "Op3 example 02 uses fixed-base monopile (no p-y springs).",
    ),
    "04_gunsan_4p2mw_tripod": Reference(
        example_id="04_gunsan_4p2mw_tripod",
        f1_hz=0.244,
        tolerance=0.05,
        boundary_condition="tripod-suction-bucket-as-built",
        source="Gunsan field measurement (PhD dissertation Ch. 5)",
        note="Operational modal analysis from accelerometer array, "
             "averaged across 20,039 RANSAC windows.",
    ),
    "07_iea_15mw_monopile": Reference(
        example_id="07_iea_15mw_monopile",
        f1_hz=0.17,
        tolerance=0.20,
        boundary_condition="monopile-soil-system",
        source="Gaertner et al. (2020), NREL/TP-5000-75698 (IEA 15 MW RWT), Table 5.1",
        note="System-level 1st tower bending including monopile and soil "
             "flexibility. Op3 example 07 is fixed-base monopile, so a "
             "wide tolerance band is applied until distributed BNWF (Mode C) "
             "is wired in.",
    ),
}


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

def run_eigen(example_id: str) -> float:
    """Run example build + eigenvalue and return first frequency in Hz."""
    from scripts.test_three_analyses import import_build

    example_dir = REPO_ROOT / "examples" / example_id
    if not example_dir.exists():
        raise FileNotFoundError(f"Example directory not found: {example_dir}")
    mod = import_build(example_dir)
    model = mod.build()
    freqs = model.eigen(n_modes=3)
    return float(freqs[0])


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tol", type=float, default=None,
                    help="Override per-example tolerance (fraction).")
    ap.add_argument("--json", type=str, default=None,
                    help="Write results JSON to this path.")
    args = ap.parse_args()

    print("=" * 78)
    print(" Op3 calibration regression -- Phase 1 / Task 1.3")
    print("=" * 78)

    results = []
    fail_count = 0
    for ex_id, ref in REFERENCES.items():
        tol = args.tol if args.tol is not None else ref.tolerance
        try:
            f1 = run_eigen(ex_id)
        except Exception as exc:  # noqa: BLE001
            print(f"  [ERROR] {ex_id}: {exc}")
            results.append({"example": ex_id, "status": "ERROR",
                            "error": str(exc)})
            fail_count += 1
            continue
        err = (f1 - ref.f1_hz) / ref.f1_hz
        within = abs(err) <= tol
        status = "PASS" if within else "FAIL"
        marker = "[OK] " if within else "[XX] "
        print(f"  {marker}{ex_id:<35} f1={f1:.4f} Hz  ref={ref.f1_hz:.4f}  "
              f"err={err:+6.1%}  tol=+/-{tol:.0%}  -> {status}")
        if not within:
            fail_count += 1
        results.append({
            "example": ex_id,
            "f1_hz": f1,
            "reference_hz": ref.f1_hz,
            "error_fraction": err,
            "tolerance": tol,
            "status": status,
            "boundary_condition": ref.boundary_condition,
            "source": ref.source,
            "note": ref.note,
        })

    print("=" * 78)
    print(f" {len(results) - fail_count}/{len(results)} examples within tolerance")
    print("=" * 78)

    if args.json:
        out = Path(args.json)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(results, indent=2), encoding="utf-8")
        print(f" JSON written: {out}")

    # Always also save to default location
    default_out = REPO_ROOT / "validation/benchmarks/calibration_regression.json"
    default_out.parent.mkdir(parents=True, exist_ok=True)
    default_out.write_text(json.dumps(results, indent=2), encoding="utf-8")

    return 1 if fail_count else 0


if __name__ == "__main__":
    sys.exit(main())
