"""
PISA cross-validation scaffold for Op^3 (T-008 / V-02).

Reproduces the Dunkirk and Cowden lab-test suite of the PISA
project (Byrne et al. 2020) against Op^3 Mode C and emits a
residual table suitable for the dissertation Appendix C and the
release validation report.

Status
------
SCAFFOLD ONLY. The PISA lab datasets are not yet imported into
the Op^3 tree. This script defines the full expected interface
and produces a structured JSON summary with "status":
"AWAITING_PISA_DATA" so that the release validation report can
register the absence of the benchmark without crashing.

When the PISA datasets are imported:

    1. Drop the lab-test data under
       ``validation/benchmarks/pisa/`` (Dunkirk, Cowden, with the
       five reference piles each)
    2. Implement ``_load_pisa_dataset()`` to parse the Byrne 2020
       load-displacement curves
    3. Implement ``_run_op3_against_pisa()`` to compose an Op^3
       Mode C foundation at each pile geometry and run the
       three-analysis (eigen, pushover, transient) validation
    4. Set ``VERIFICATION_READY = True``
    5. Re-run this script; it will then produce the residual
       table and cross-validation plot

References
----------
Byrne, B. W., Houlsby, G. T., Burd, H. J., et al. (2020). PISA
design model for monopiles for offshore wind turbines.
Geotechnique, 70(11), 1017–1035.
Burd, H. J., Taborda, D. M. G., Zdravkovic, L., et al. (2020).
PISA design model for monopiles for offshore wind turbines:
application to a marine sand. Geotechnique, 70(11), 1048–1066.
McAdam, R. A., Byrne, B. W., Houlsby, G. T., et al. (2020).
Monotonic laterally loaded pile testing in a dense marine sand
at Dunkirk. Geotechnique, 70(11), 986–998.
"""
from __future__ import annotations

import datetime as dt
import json
from pathlib import Path
from typing import Dict, List

REPO = Path(__file__).resolve().parents[1]
PISA_DIR = REPO / "validation" / "benchmarks" / "pisa"
OUT_DIR = REPO / "validation" / "release_report" / "pisa"

VERIFICATION_READY = False

# The five PISA reference piles (per Byrne 2020 Table 1)
PISA_PILES = [
    {"site": "Cowden", "id": "CM9",  "D_m": 2.0,  "L_m": 10.6},
    {"site": "Cowden", "id": "CS1",  "D_m": 0.273,"L_m": 2.74},
    {"site": "Cowden", "id": "CM2",  "D_m": 0.762,"L_m": 3.86},
    {"site": "Dunkirk","id": "DM7",  "D_m": 2.0,  "L_m": 10.6},
    {"site": "Dunkirk","id": "DS2",  "D_m": 0.273,"L_m": 2.74},
]


def _load_pisa_dataset(pile: Dict) -> Dict:
    """Load the Byrne 2020 load-displacement reference for one pile."""
    if not VERIFICATION_READY:
        return {"status": "AWAITING_PISA_DATA", "pile": pile["id"]}
    raise NotImplementedError("implement once dataset is imported")


def _run_op3_against_pisa(pile: Dict) -> Dict:
    """Run Op^3 Mode C three-analysis validation on one pile."""
    if not VERIFICATION_READY:
        return {"status": "AWAITING_PISA_DATA", "pile": pile["id"]}
    raise NotImplementedError("implement once dataset is imported")


def _compute_residuals(ref: Dict, op3: Dict) -> Dict:
    """Compute residuals between Op^3 prediction and PISA reference."""
    if not VERIFICATION_READY:
        return {"status": "AWAITING_PISA_DATA"}
    raise NotImplementedError("implement once dataset is imported")


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    summary = {
        "benchmark": "PISA cross-validation (Byrne 2020, Burd 2020, McAdam 2020)",
        "reference": "Geotechnique 70(11): 986-1035, 1048-1066",
        "target_framework_mode": "Op^3 Mode C (distributed BNWF)",
        "piles": PISA_PILES,
        "timestamp": dt.datetime.now().isoformat(timespec="seconds"),
    }

    if not VERIFICATION_READY:
        summary.update({
            "status": "AWAITING_VERIFY",
            "reason": (
                "PISA lab datasets (Cowden + Dunkirk) have not been "
                "imported into validation/benchmarks/pisa/ yet. This "
                "scaffold script reserves the entry in the release "
                "validation report and enumerates the five target "
                "piles that will be cross-validated when the data "
                "becomes available."
            ),
            "required_inputs": [
                f"{PISA_DIR}/cowden/{p['id']}_load_displacement.csv"
                for p in PISA_PILES if p["site"] == "Cowden"
            ] + [
                f"{PISA_DIR}/dunkirk/{p['id']}_load_displacement.csv"
                for p in PISA_PILES if p["site"] == "Dunkirk"
            ],
            "interface": [
                "_load_pisa_dataset(pile)",
                "_run_op3_against_pisa(pile)",
                "_compute_residuals(ref, op3)",
            ],
            "estimated_effort_days": 14,
        })
    else:
        summary["residuals"] = {}
        for pile in PISA_PILES:
            ref = _load_pisa_dataset(pile)
            op3 = _run_op3_against_pisa(pile)
            summary["residuals"][pile["id"]] = _compute_residuals(ref, op3)
        summary["status"] = "VERIFIED" if all(
            r.get("within_threshold", False)
            for r in summary["residuals"].values()
        ) else "FAILED_THRESHOLDS"

    out = OUT_DIR / "pisa_cross_validation_summary.json"
    out.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(f"wrote {out}")
    print(f"status: {summary['status']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
