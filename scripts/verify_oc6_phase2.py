"""
OC6 Phase II benchmark verification scaffold for Op^3 (T-007 / V-01).

Reproduces the Bergua et al. 2021 OC6 Phase II benchmark
(NREL/TP-5000-79989) against Op^3 Mode C and emits a residual
table suitable for the dissertation Appendix C and the release
validation report.

Status
------
SCAFFOLD ONLY. The OC6 Phase II deck is not yet imported into the
Op^3 tree. This script defines the full expected interface and
produces a structured JSON summary with "status": "AWAITING_DECK"
so that the release validation report can register the absence
of the benchmark without crashing.

When the OC6 deck is imported:

    1. Drop the deck files under ``validation/benchmarks/oc6_phase2/``
       in the tree (input OpenFAST files, reference time series)
    2. Implement ``_load_oc6_reference()`` to parse the Bergua 2021
       time-series tables
    3. Implement ``_run_op3_against_oc6()`` to compose an Op^3
       OpenFAST run with the OC6 input conditions
    4. Set ``VERIFICATION_READY = True``
    5. Re-run this script; it will then produce the residual table
       and plot and update the release validation report entry

Reference
---------
Bergua, R., Robertson, A., Jonkman, J., et al. (2021). OC6 Project
Phase II: Verification of an Aerodynamic Response Model for
Floating Wind Turbines under Surging Motion.
NREL/TP-5000-79989. https://www.nrel.gov/docs/fy22osti/79989.pdf
"""
from __future__ import annotations

import datetime as dt
import json
from pathlib import Path
from typing import Dict

REPO = Path(__file__).resolve().parents[1]
OC6_DIR = REPO / "validation" / "benchmarks" / "oc6_phase2"
OUT_DIR = REPO / "validation" / "release_report" / "oc6_phase2"

VERIFICATION_READY = False  # flip to True when the deck is imported


def _load_oc6_reference() -> Dict:
    """Load the Bergua 2021 reference time series.

    TODO: parse the OC6 Phase II reference data distributed with
    NREL/TP-5000-79989. Expected format is tab-separated columns
    for time, platform surge, pitch, tower base fore-aft moment,
    rotor thrust, rotor torque. Frequencies reported include
    surge, pitch, and first tower fore-aft.
    """
    if not VERIFICATION_READY:
        return {"status": "AWAITING_DECK", "reason": "OC6 deck not imported"}
    raise NotImplementedError("implement once deck is imported")


def _run_op3_against_oc6() -> Dict:
    """Run Op^3 Mode C against the OC6 Phase II input conditions.

    TODO: compose an Op^3 model with the OC6 floating platform
    stiffness matrix, dispatch the OpenFAST runner, and read the
    resulting time series.
    """
    if not VERIFICATION_READY:
        return {"status": "AWAITING_DECK"}
    raise NotImplementedError("implement once deck is imported")


def _compute_residuals(ref: Dict, op3: Dict) -> Dict:
    """Compute element-wise residuals and summary statistics.

    TODO: compute RMSE, normalised RMSE, peak error, and phase
    error per channel. Compare against the Bergua 2021 'quality
    metrics' thresholds.
    """
    if not VERIFICATION_READY:
        return {"status": "AWAITING_DECK"}
    raise NotImplementedError("implement once deck is imported")


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    summary = {
        "benchmark": "OC6 Phase II (Bergua 2021)",
        "reference": "NREL/TP-5000-79989",
        "target_framework_mode": "Op^3 Mode C (distributed BNWF)",
        "timestamp": dt.datetime.now().isoformat(timespec="seconds"),
    }

    if not VERIFICATION_READY:
        summary.update({
            "status": "AWAITING_VERIFY",
            "reason": (
                "OC6 Phase II reference deck has not been imported "
                "into validation/benchmarks/oc6_phase2/ yet. This "
                "scaffold script reserves the entry in the release "
                "validation report and defines the interface that "
                "will run automatically once the deck is present."
            ),
            "required_inputs": [
                f"{OC6_DIR}/input/*.fst",
                f"{OC6_DIR}/reference/bergua_2021_timeseries.csv",
                f"{OC6_DIR}/reference/quality_metrics.yaml",
            ],
            "interface": [
                "_load_oc6_reference()",
                "_run_op3_against_oc6()",
                "_compute_residuals(ref, op3)",
            ],
            "estimated_effort_days": 14,
        })
    else:
        ref = _load_oc6_reference()
        op3 = _run_op3_against_oc6()
        summary["residuals"] = _compute_residuals(ref, op3)
        summary["status"] = "VERIFIED" if all(
            r.get("within_threshold") for r in summary["residuals"].values()
        ) else "FAILED_THRESHOLDS"

    out = OUT_DIR / "oc6_phase2_summary.json"
    out.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(f"wrote {out}")
    print(f"status: {summary['status']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
