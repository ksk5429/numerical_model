"""
Shim entry point: Chapter 7 critical review recompute.

Invokes the authoritative analysis at
``F:/TREE_OF_THOUGHT/PHD/code/ch7_critical_review_recompute.py``
via explicit path execution. The PHD script computes the Tables
7.2, 7.3, 7.5 Bayesian fusion + VoI results that feed the Ch. 7
figures.

This shim exists so that a reviewer running from the Op^3 checkout
can reproduce the dissertation's Chapter 7 numerics with a single
command that also verifies PHD availability, reports the script's
provenance, and writes the output JSON alongside the other
dissertation artifacts.

Run
---
    python scripts/dissertation/run_ch7_critical_review.py
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from op3.data_sources import get_phd_root


def main():
    root = get_phd_root()
    if root is None:
        print("ERROR: PHD root not found. Set OP3_PHD_ROOT or ensure")
        print("       F:/TREE_OF_THOUGHT/PHD exists.")
        return 1

    script = root / "code/ch7_critical_review_recompute.py"
    if not script.exists():
        print(f"ERROR: PHD script missing: {script}")
        return 2

    print("=" * 72)
    print(" Op3 -> PHD shim: Chapter 7 critical review recompute")
    print("=" * 72)
    print(f"  PHD root : {root}")
    print(f"  script   : {script}")
    print()

    env = {**os.environ, "PYTHONUTF8": "1",
           "PYTHONPATH": str(Path(__file__).resolve().parents[2])}
    rc = subprocess.call(
        [sys.executable, str(script)],
        cwd=str(root),
        env=env,
    )
    return rc


if __name__ == "__main__":
    sys.exit(main())
