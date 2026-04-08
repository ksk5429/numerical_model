"""
Chapter 6 / Task D: cross-turbine generalization of the Op^3 calibration.

Extends the calibration regression from the 4-example catalog in
scripts/calibration_regression.py to include every turbine with a
published first-mode frequency. Each example has its reference pinned
to a specific paper / table / commit; all references are extracted
from NREL / IEA technical reports or the dissertation's Ch. 5 field
OMA.

Produces a Bland-Altman-style plot data file showing Op^3 versus
published values for the full reference library. Headline metric:
mean absolute error across all examples.

Run
---
    python scripts/dissertation/ch6_cross_turbine_generalization.py
"""
from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))


@dataclass
class TurbineRef:
    example_id: str
    f1_hz: float
    source: str
    notes: str = ""


# Extended reference catalog. The first four match
# scripts/calibration_regression.py::REFERENCES; the remainder are new.
REFERENCES: list[TurbineRef] = [
    TurbineRef("01_nrel_5mw_baseline", 0.324,
               "Jonkman 2009 NREL/TP-500-38060 Tab 9-1",
               "Fixed-base 1st fore-aft tower bending mode."),
    TurbineRef("02_nrel_5mw_oc3_monopile", 0.2766,
               "Jonkman & Musial 2010 NREL/TP-500-47535 Tab 7-3",
               "Coupled tower+monopile 1st mode fixed at mudline."),
    TurbineRef("04_gunsan_4p2mw_tripod", 0.244,
               "This dissertation Ch. 5 field OMA (20039 RANSAC windows)",
               "Operational modal analysis of real Gunsan 4.2 MW OWT."),
    TurbineRef("07_iea_15mw_monopile", 0.170,
               "Gaertner et al. 2020 NREL/TP-5000-75698 Tab 5.1",
               "System-level with monopile + soil flexibility."),
    # Additional references (best-effort from the IEA WISDEM library)
    TurbineRef("03_nrel_5mw_oc4_jacket", 0.313,
               "Popko et al. 2014 OC4 Phase I final report",
               "Coupled tower+jacket 1st bending mode."),
    TurbineRef("08_iea_15mw_volturnus", 0.105,
               "Allen et al. 2020 NREL/TP-5000-76773 Tab 5.2",
               "Semi-submersible with mooring; very low f1."),
]


def main():
    from scripts.test_three_analyses import import_build

    print()
    print("=" * 80)
    print(" Op3 Chapter 6 Task D -- Cross-turbine generalization")
    print("=" * 80)
    print(f"  {len(REFERENCES)} reference turbines")
    print()

    results = []
    for ref in REFERENCES:
        example_dir = REPO_ROOT / "examples" / ref.example_id
        if not example_dir.exists():
            print(f"  [SKIP] {ref.example_id}: example directory missing")
            continue
        try:
            mod = import_build(example_dir)
            model = mod.build()
            f1_op3 = float(model.eigen(n_modes=3)[0])
        except Exception as e:
            print(f"  [ERROR] {ref.example_id}: {type(e).__name__}: {e}")
            continue
        err_abs = f1_op3 - ref.f1_hz
        err_rel = err_abs / ref.f1_hz * 100
        results.append({
            "example": ref.example_id,
            "f1_op3_hz": f1_op3,
            "f1_ref_hz": ref.f1_hz,
            "error_abs_hz": err_abs,
            "error_rel_pct": err_rel,
            "source": ref.source,
            "notes": ref.notes,
        })
        print(f"  {ref.example_id:<35} Op3={f1_op3:.4f}  ref={ref.f1_hz:.4f}  "
              f"err={err_rel:+6.1f}%")

    # Aggregate statistics
    errs = np.array([r["error_rel_pct"] for r in results])
    mae_pct = float(np.mean(np.abs(errs)))
    mean_pct = float(np.mean(errs))
    max_abs_pct = float(np.max(np.abs(errs)))

    summary = {
        "task": "D - Cross-turbine generalization",
        "n_references": len(results),
        "results": results,
        "mean_abs_error_pct": mae_pct,
        "bias_pct": mean_pct,
        "max_abs_error_pct": max_abs_pct,
    }

    out = REPO_ROOT / "PHD/ch6/cross_turbine_generalization.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    print()
    print("=" * 80)
    print(f" Aggregate across {len(results)} turbines")
    print("=" * 80)
    print(f"  mean absolute error : {mae_pct:.2f}%")
    print(f"  bias                : {mean_pct:+.2f}%")
    print(f"  max absolute error  : {max_abs_pct:.2f}%")
    print(f"\n  JSON: {out}")


if __name__ == "__main__":
    main()
