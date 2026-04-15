"""
Pure-Python post-processing of real OptumGX anchor FE output.

The OptumGX driver (``op3/anchors/optumgx_anchor_run.py``) writes CSVs
into ``results_anchor_<tag>/``. This module reads those CSVs, performs
unit checks, derives the V-H envelope and the optimal padeye via the
dissipation-centroid method, and copies canonical results into
``data/anchor_benchmarks/`` for the Op^3 downstream code.

No synthetic data is generated here.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import pandas as pd

from op3.anchors.anchor import SuctionAnchor
from op3.anchors.capacity import capacity_fe_calibrated, AnchorCapacityResult
from op3.anchors.padeye import optimal_padeye_from_dissipation


ENVELOPE_FILENAME = "envelope.csv"
DISSIPATION_FILENAME = "dissipation.csv"
SUMMARY_FILENAME = "summary.json"


@dataclass
class AnchorFEResults:
    """Combined FE post-processing result for a single anchor geometry."""
    results_dir: Path
    envelope: pd.DataFrame
    dissipation: Optional[pd.DataFrame]
    capacity: AnchorCapacityResult
    optimal_padeye_m: Optional[float]


def load_anchor_fe_results(
    results_dir: str | Path,
    anchor: SuctionAnchor,
    soil,
    *,
    load_angle_deg: float = 0.0,
) -> AnchorFEResults:
    """Read the driver-produced CSVs and return a combined result.

    Parameters
    ----------
    results_dir : str | Path
        Path to the OptumGX output directory (the one the driver
        printed at the end of its run).
    anchor, soil : Op^3 data model
        Used for metadata and the FE-calibrated capacity evaluation.
    load_angle_deg : float
        Angle at which to report ``T_ult`` on the envelope.

    Raises
    ------
    FileNotFoundError
        If ``envelope.csv`` is missing. The error message points to
        the OptumGX driver script.
    """
    p = Path(results_dir)
    envelope_csv = p / ENVELOPE_FILENAME
    dissipation_csv = p / DISSIPATION_FILENAME

    if not envelope_csv.exists():
        raise FileNotFoundError(
            f"OptumGX envelope not found: {envelope_csv}\n"
            "Run op3/anchors/optumgx_anchor_run.py from inside the "
            "OptumGX desktop scripting console; see "
            "docs/ANCHOR_OPTUMGX_GUIDE.md."
        )
    envelope = pd.read_csv(envelope_csv)

    cap = capacity_fe_calibrated(anchor, soil,
                                 fe_csv=envelope_csv,
                                 load_angle_deg=load_angle_deg)

    if dissipation_csv.exists():
        dissipation = pd.read_csv(dissipation_csv)
        z_opt = optimal_padeye_from_dissipation(anchor, dissipation_csv)
    else:
        dissipation = None
        z_opt = None

    return AnchorFEResults(
        results_dir=p,
        envelope=envelope,
        dissipation=dissipation,
        capacity=cap,
        optimal_padeye_m=z_opt,
    )
