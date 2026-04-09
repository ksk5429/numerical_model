"""
Compliance audit wiring for the Op^3 web application.

Runs the existing DNV-ST-0126 and IEC 61400-3 conformance scripts
from ``scripts/`` in a subprocess and returns their JSON summaries
as a compact dict the Dash tab can render as a clause-by-clause
table.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Dict, List

REPO = Path(__file__).resolve().parents[1]
DNV_SCRIPT = REPO / "scripts" / "dnv_st_0126_conformance.py"
IEC_SCRIPT = REPO / "scripts" / "iec_61400_3_conformance.py"


def run_dnv_audit() -> Dict:
    """Invoke the DNV-ST-0126 audit script and return its summary."""
    return _run_script(DNV_SCRIPT, "dnv_st_0126")


def run_iec_audit() -> Dict:
    """Invoke the IEC 61400-3 audit script and return its summary."""
    return _run_script(IEC_SCRIPT, "iec_61400_3")


def _run_script(script: Path, label: str) -> Dict:
    if not script.exists():
        return {
            "status": "missing",
            "script": str(script),
            "label": label,
            "clauses": [],
            "message": f"audit script not found at {script}",
        }
    try:
        proc = subprocess.run(
            [sys.executable, str(script), "--json"],
            cwd=REPO, capture_output=True, text=True, timeout=300,
        )
    except subprocess.TimeoutExpired:
        return {
            "status": "timeout",
            "label": label,
            "clauses": [],
            "message": "audit exceeded 5 min timeout",
        }

    summary: Dict = {"status": "ok", "label": label, "return_code": proc.returncode}
    # Try to parse JSON from stdout; fall back to raw stdout
    try:
        summary["body"] = json.loads(proc.stdout)
    except json.JSONDecodeError:
        summary["stdout"] = proc.stdout[-2000:]
        summary["stderr"] = proc.stderr[-500:]
    return summary


def dispatch_dlc_run(family: str, wind_speeds: List[float], tmax_s: float
                     ) -> Dict:
    """Dispatch an OpenFAST DLC sweep run in a detached subprocess.

    Returns an envelope with the process handle and the output
    directory the caller can poll for completion.
    """
    runner = REPO / "scripts" / "dlc11_overnight_runner.py"
    if family != "1.1" or not runner.exists():
        return {
            "status": "unsupported",
            "family": family,
            "message": f"DLC {family} runner not available at {runner}",
        }
    # Non-blocking dispatch; user polls validation/dlc11_partial/ for the
    # latest sweep directory.
    proc = subprocess.Popen(
        [sys.executable, str(runner),
         "--wind-speeds", ",".join(str(w) for w in wind_speeds),
         "--tmax", str(tmax_s)],
        cwd=REPO,
    )
    return {
        "status": "dispatched",
        "family": family,
        "pid": proc.pid,
        "watch_dir": str(REPO / "validation" / "dlc11_partial"),
    }
